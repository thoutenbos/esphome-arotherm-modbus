#pragma once

#include <atomic>
#include <cstdint>
#include <cstring>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
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
    DIV10,
    D2C,
  };

  void add_sensor(uint16_t register_address, Scale scale, sensor::Sensor *sensor) {
    this->sensors_.push_back({register_address, scale, sensor});
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
  void try_complete_adus_();
  void log_and_decode_(size_t len);
  std::string format_registers_(const uint8_t *data, size_t len);
  uint16_t last_read_start_reg_{0};
  uint16_t last_read_count_{0};
  void decode_message_(const uint8_t *data, size_t len);
  void publish_block_(const uint8_t *data, size_t header_len, uint16_t base_register, size_t count);
  static float scale_value_(Scale scale, int32_t raw);
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
};

}  // namespace arotherm_modbus
}  // namespace esphome
