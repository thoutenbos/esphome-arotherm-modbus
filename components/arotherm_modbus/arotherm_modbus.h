#pragma once

#include <atomic>
#include <cstdint>
#include <cstring>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/components/time/real_time_clock.h"

namespace esphome {
namespace arotherm_modbus {

class AroThermModbus : public Component {
 public:
  void setup() override;
  void loop() override;

  void set_rx_pin(int pin) { this->rx_pin_ = pin; }
  void set_baud_rate(uint32_t baud) { this->baud_rate_ = baud; }
  void set_time(time::RealTimeClock *time) { this->time_ = time; }

  enum class Scale : uint8_t {
    RAW,
    // As RAW, but the register is read as unsigned: timers and powers that
    // run past 32,767.
    URAW,
    DIV10,
    DIV50,
    DIV100,
    DIV1000,
    D2C,
    // Big-endian IEEE-754 single spanning THIS register and the next one.
    F32,
  };

  void add_sensor(uint16_t register_address, Scale scale, sensor::Sensor *sensor) {
    this->sensors_.push_back({register_address, scale, sensor});
  }

  // Registers published as text rather than as a number.
  enum class TextKind : uint8_t {
    // Three consecutive registers, "major.minor.patch".
    FIRMWARE_VERSION,
    // The compressor ramp bitfield at 0x214E, spelled out.
    COMPRESSOR_RAMP_STATE,
    // 28 ASCII characters: the low byte of this register, then both bytes of
    // each of the next 17, padded with '<'.
    SERIAL_NUMBER,
  };

  void add_text_sensor(uint16_t register_address, TextKind kind, text_sensor::TextSensor *sensor) {
    this->text_sensors_.push_back({register_address, kind, sensor, false, ""});
  }

 protected:
  static constexpr uint8_t SLAVE_ADDRESS = 0x01;
  enum FunctionCode : uint8_t {
    FUNCTION_READ_HOLDING_REGISTERS = 0x03,
    FUNCTION_WRITE_MULTIPLE_REGISTERS = 0x10,
  };
  static constexpr size_t ADU_ADDRESS_LEN = 1;
  static constexpr size_t ADU_FUNCTION_LEN = 1;
  static constexpr size_t ADU_REGISTER_FIELD_LEN = 2;
  static constexpr size_t ADU_BYTE_COUNT_LEN = 1;
  static constexpr size_t ADU_CRC_LEN = 2;
  static constexpr size_t FIXED_ADU_LEN =
      ADU_ADDRESS_LEN + ADU_FUNCTION_LEN + ADU_REGISTER_FIELD_LEN + ADU_REGISTER_FIELD_LEN + ADU_CRC_LEN;
  static constexpr size_t READ_RESPONSE_HEADER_LEN = ADU_ADDRESS_LEN + ADU_FUNCTION_LEN + ADU_BYTE_COUNT_LEN;
  static constexpr size_t READ_RESPONSE_BYTE_COUNT_OFFSET = ADU_ADDRESS_LEN + ADU_FUNCTION_LEN;
  static constexpr size_t WRITE_REQUEST_HEADER_LEN = ADU_ADDRESS_LEN + ADU_FUNCTION_LEN + ADU_REGISTER_FIELD_LEN +
                                                      ADU_REGISTER_FIELD_LEN + ADU_BYTE_COUNT_LEN;
  static constexpr size_t WRITE_REQUEST_BYTE_COUNT_OFFSET =
      ADU_ADDRESS_LEN + ADU_FUNCTION_LEN + ADU_REGISTER_FIELD_LEN + ADU_REGISTER_FIELD_LEN;
  static constexpr size_t MAX_ADU_LEN = 256;
  static constexpr uint32_t STUCK_ADU_TIMEOUT_US = 100000;
  static constexpr int RX_PRESSURE_BYTES = 128;
  static bool looks_like_adu_start_(const std::vector<uint8_t> &adu);
  static size_t expected_adu_length_(const std::vector<uint8_t> &adu);
  // One received byte: append it to the ADU being assembled and log/decode
  // every ADU that completes. Everything after the UART goes through here,
  // which is also where tests/harness.cpp feeds captured bytes in.
  void process_byte_(uint8_t byte, uint32_t now_us);
  void try_complete_adus_();
  void log_and_decode_(size_t len);
  std::string format_registers_(const uint8_t *data, size_t len);
  // Start register and count of the most recent read request, used to
  // attribute the following read response (which carries no address).
  uint16_t last_read_start_reg_{0};
  uint16_t last_read_count_{0};
  void decode_message_(const uint8_t *data, size_t len);
  void publish_block_(const uint8_t *data, size_t header_len, uint16_t base_register, size_t count);
  static float scale_value_(Scale scale, int32_t raw);
  static std::string ramp_state_text_(uint16_t raw);
  static uint16_t crc16_modbus_(const uint8_t *data, size_t len);
  static bool modbus_crc_valid_(const uint8_t *data, size_t len);

  std::string timestamp_();
  static std::string to_hex_(const uint8_t *data, size_t len);
  static std::string find_ascii_(const uint8_t *data, size_t len);

  int rx_pin_{-1};
  uint32_t baud_rate_{19200};

#ifdef USE_ESP32
  void push_rx_byte_(uint8_t b, int64_t ts_us);
  static void uart_isr_(void *arg);

  struct RxByte {
    uint8_t byte;
    int64_t ts_us;
  };
  static constexpr size_t RX_RING_SIZE = 2048;
  RxByte rx_ring_[RX_RING_SIZE];
  std::atomic<uint32_t> rx_head_{0};
  std::atomic<uint32_t> rx_tail_{0};
  std::atomic<uint32_t> rx_overflow_{0};
  uint32_t rx_overflow_last_reported_{0};
  void *uart_isr_handle_{nullptr};

  void setup_uart_();
#endif
  bool pop_byte_(uint8_t *out_byte, uint32_t *out_us);
  uint32_t now_us_();
  int rx_waiting_();

  std::vector<uint8_t> adu_;
  uint32_t adu_start_us_{0};
  uint32_t last_byte_us_{0};
  uint32_t prev_adu_end_us_{0};
  bool have_prev_adu_{false};
  uint32_t seq_{0};
  int rx_peak_{0};
  uint32_t rx_pressure_events_{0};

  time::RealTimeClock *time_{nullptr};

  struct RegisterSensor {
    uint16_t register_address;
    Scale scale;
    sensor::Sensor *sensor;
  };
  std::vector<RegisterSensor> sensors_;

  // Text is published on change only: the bus repeats every register about
  // once a second, and a state string that has not moved is not news.
  struct RegisterTextSensor {
    uint16_t register_address;
    TextKind kind;
    text_sensor::TextSensor *sensor;
    bool published;
    std::string last;
  };
  std::vector<RegisterTextSensor> text_sensors_;
};

}  // namespace arotherm_modbus
}  // namespace esphome
