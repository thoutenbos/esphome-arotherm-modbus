#include "arotherm_modbus.h"
#include "esphome/core/log.h"
#include "esphome/core/hal.h"

#ifdef USE_ESP32
#include "driver/uart.h"
#include "hal/uart_ll.h"
#include "hal/uart_hal.h"
#include "esp_timer.h"
#include "esp_intr_alloc.h"
#include "soc/uart_periph.h"
#include "esp_attr.h"
#endif

namespace esphome {
namespace arotherm_modbus {

static const char *const TAG = "arotherm_modbus";

#ifdef USE_ESP32
static constexpr uart_port_t MODBUS_UART_NUM = UART_NUM_2;

void IRAM_ATTR AroThermModbus::uart_isr_(void *arg) {
  auto *self = static_cast<AroThermModbus *>(arg);
  uart_dev_t *hw = UART_LL_GET_HW(MODBUS_UART_NUM);
  uart_hal_context_t hal{};
  hal.dev = hw;
  while (uart_hal_get_rxfifo_len(&hal) > 0) {
    uint8_t b;
    int rd_len = 1;
    uart_hal_read_rxfifo(&hal, &b, &rd_len);
    self->push_rx_byte_(b, esp_timer_get_time());
  }
  uart_ll_clr_intsts_mask(hw, uart_ll_get_intsts_mask(hw));
}

void IRAM_ATTR AroThermModbus::push_rx_byte_(uint8_t b, int64_t ts_us) {
  const uint32_t head = this->rx_head_.load(std::memory_order_relaxed);
  const uint32_t next = (head + 1) & (RX_RING_SIZE - 1);
  if (next == this->rx_tail_.load(std::memory_order_acquire)) {
    this->rx_overflow_.fetch_add(1, std::memory_order_relaxed);
    return;
  }
  this->rx_ring_[head].byte = b;
  this->rx_ring_[head].ts_us = ts_us;
  this->rx_head_.store(next, std::memory_order_release);
}
#endif  // USE_ESP32

std::string AroThermModbus::to_hex_(const uint8_t *data, size_t len) {
  static const char *hex_chars = "0123456789ABCDEF";
  std::string out;
  out.reserve(len * 3);
  for (size_t i = 0; i < len; i++) {
    if (i > 0)
      out += ' ';
    out += hex_chars[(data[i] >> 4) & 0x0F];
    out += hex_chars[data[i] & 0x0F];
  }
  return out;
}

std::string AroThermModbus::find_ascii_(const uint8_t *data, size_t len) {
  static constexpr size_t MIN_RUN = 4;
  std::string out;
  size_t i = 0;
  while (i < len) {
    size_t start = i;
    while (i < len && data[i] >= 0x20 && data[i] <= 0x7E)
      i++;
    if (i - start >= MIN_RUN) {
      if (!out.empty())
        out += ", ";
      out += '"';
      out.append(reinterpret_cast<const char *>(data + start), i - start);
      out += '"';
    } else if (i == start) {
      i++;
    }
  }
  return out;
}

std::string AroThermModbus::timestamp_() {
  if (this->time_ == nullptr)
    return "??";
  auto t = this->time_->now();
  if (!t.is_valid())
    return "??";
  char buf[24];
  snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d", t.year, t.month, t.day_of_month, t.hour, t.minute,
            t.second);
  return buf;
}

void AroThermModbus::setup() {
  this->adu_.reserve(MAX_ADU_LEN);
#ifdef USE_ESP32
  this->setup_uart_();
#else
  ESP_LOGE(TAG, "arotherm_modbus requires ESP32 - this build target doesn't have the raw UART FIFO "
                "access it needs");
  this->mark_failed();
#endif
}

#ifdef USE_ESP32
void AroThermModbus::setup_uart_() {
  if (this->rx_pin_ < 0) {
    ESP_LOGE(TAG, "rx_pin is not set - cannot start");
    this->mark_failed();
    return;
  }

  uart_config_t cfg = {};
  cfg.baud_rate = (int) this->baud_rate_;
  cfg.data_bits = UART_DATA_8_BITS;
  cfg.parity = UART_PARITY_DISABLE;
  cfg.stop_bits = UART_STOP_BITS_1;
  cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  cfg.source_clk = UART_SCLK_APB;
  esp_err_t err = uart_param_config(MODBUS_UART_NUM, &cfg);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "uart_param_config failed (%d)", (int) err);
    this->mark_failed();
    return;
  }

  err = uart_set_pin(MODBUS_UART_NUM, UART_PIN_NO_CHANGE, this->rx_pin_, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "uart_set_pin(rx=%d) failed (%d)", this->rx_pin_, (int) err);
    this->mark_failed();
    return;
  }

  err = esp_intr_alloc(uart_periph_signal[MODBUS_UART_NUM].irq, 0, &AroThermModbus::uart_isr_, this,
                        reinterpret_cast<intr_handle_t *>(&this->uart_isr_handle_));
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "esp_intr_alloc failed (%d)", (int) err);
    this->mark_failed();
    return;
  }

  uart_intr_config_t intr_conf = {};
  intr_conf.intr_enable_mask = UART_INTR_RXFIFO_FULL;
  intr_conf.rxfifo_full_thresh = 1;
  intr_conf.rx_timeout_thresh = 0;
  intr_conf.txfifo_empty_intr_thresh = 0;
  err = uart_intr_config(MODBUS_UART_NUM, &intr_conf);
  if (err != ESP_OK) {
    ESP_LOGE(TAG, "uart_intr_config failed (%d)", (int) err);
    this->mark_failed();
    return;
  }

  ESP_LOGCONFIG(TAG, "Raw hardware UART reception active on UART%d, rx=GPIO%d, %u baud", (int) MODBUS_UART_NUM,
                this->rx_pin_, this->baud_rate_);
}
#endif  // USE_ESP32

bool AroThermModbus::pop_byte_(uint8_t *out_byte, uint32_t *out_us) {
#ifdef USE_ESP32
  const uint32_t tail = this->rx_tail_.load(std::memory_order_relaxed);
  const uint32_t head = this->rx_head_.load(std::memory_order_acquire);
  if (tail == head)
    return false;
  *out_byte = this->rx_ring_[tail].byte;
  *out_us = (uint32_t) this->rx_ring_[tail].ts_us;
  this->rx_tail_.store((tail + 1) & (RX_RING_SIZE - 1), std::memory_order_release);
  return true;
#else
  (void) out_byte;
  (void) out_us;
  return false;
#endif
}

uint32_t AroThermModbus::now_us_() {
#ifdef USE_ESP32
  return (uint32_t) esp_timer_get_time();
#else
  return 0;
#endif
}

int AroThermModbus::rx_waiting_() {
#ifdef USE_ESP32
  const uint32_t head = this->rx_head_.load(std::memory_order_acquire);
  const uint32_t tail = this->rx_tail_.load(std::memory_order_relaxed);
  return (int) ((head - tail) & (RX_RING_SIZE - 1));
#else
  return 0;
#endif
}

void AroThermModbus::loop() {
  if (this->is_failed())
    return;
#ifdef USE_ESP32
  const uint32_t ovf = this->rx_overflow_.load(std::memory_order_relaxed);
  if (ovf != this->rx_overflow_last_reported_) {
    ESP_LOGW(TAG, "receive ring buffer overflow: %u byte(s) dropped since boot - this capture is no "
                  "longer reliable from that point; the ring may need to be larger, or loop() is being "
                  "starved by something else",
             ovf);
    this->rx_overflow_last_reported_ = ovf;
  }
#endif

  int waiting = this->rx_waiting_();
  if (waiting > this->rx_peak_)
    this->rx_peak_ = waiting;
  if (waiting >= RX_PRESSURE_BYTES) {
    this->rx_pressure_events_++;
    ESP_LOGW(TAG, "receive backlog %d bytes (peak %d, %u times) - messages may be at "
                  "risk of loss; treat traces from this run with suspicion",
             waiting, this->rx_peak_, this->rx_pressure_events_);
  }

  bool got_byte = false;
  uint8_t byte;
  uint32_t now;
  while (this->pop_byte_(&byte, &now)) {
    got_byte = true;
    if (this->adu_.empty())
      this->adu_start_us_ = now;
    this->adu_.push_back(byte);
    this->last_byte_us_ = now;
    this->try_complete_adus_();
  }

  if (!got_byte && !this->adu_.empty() && this->now_us_() - this->last_byte_us_ > STUCK_ADU_TIMEOUT_US) {
    ESP_LOGW(TAG, "[%s] incomplete message discarded after %ums idle: [%s]", this->timestamp_().c_str(),
             (unsigned) (STUCK_ADU_TIMEOUT_US / 1000), to_hex_(this->adu_.data(), this->adu_.size()).c_str());
    this->adu_.clear();
  }
}

bool AroThermModbus::looks_like_adu_start_(const std::vector<uint8_t> &adu) {
  if (adu.size() < ADU_ADDRESS_LEN + ADU_FUNCTION_LEN)
    return false;
  if (adu[0] != SLAVE_ADDRESS)
    return false;
  return adu[1] == FUNCTION_READ_HOLDING_REGISTERS || adu[1] == FUNCTION_WRITE_MULTIPLE_REGISTERS;
}

size_t AroThermModbus::expected_adu_length_(const std::vector<uint8_t> &adu) {
  if (adu.size() < FIXED_ADU_LEN)
    return 0;
  if (modbus_crc_valid_(adu.data(), FIXED_ADU_LEN))
    return FIXED_ADU_LEN;
  const bool is_read = adu[1] == FUNCTION_READ_HOLDING_REGISTERS;
  const size_t byte_count_offset = is_read ? READ_RESPONSE_BYTE_COUNT_OFFSET : WRITE_REQUEST_BYTE_COUNT_OFFSET;
  const size_t header_len = is_read ? READ_RESPONSE_HEADER_LEN : WRITE_REQUEST_HEADER_LEN;
  return header_len + adu[byte_count_offset] + ADU_CRC_LEN;
}

void AroThermModbus::try_complete_adus_() {
  while (true) {
    if (this->adu_.size() < ADU_ADDRESS_LEN + ADU_FUNCTION_LEN)
      return;  // wait for address + function
    if (!looks_like_adu_start_(this->adu_)) {
      this->adu_.erase(this->adu_.begin());
      continue;
    }
    const size_t want = expected_adu_length_(this->adu_);
    if (want == 0)
      return;
    if (want > MAX_ADU_LEN) {
      this->adu_.erase(this->adu_.begin());
      continue;
    }
    if (this->adu_.size() < want)
      return;
    if (modbus_crc_valid_(this->adu_.data(), want)) {
      this->log_and_decode_(want);
      this->adu_.erase(this->adu_.begin(), this->adu_.begin() + want);
      this->prev_adu_end_us_ = this->last_byte_us_;
      this->have_prev_adu_ = true;
      continue;
    }
    this->adu_.erase(this->adu_.begin());
  }
}

void AroThermModbus::log_and_decode_(size_t len) {
  this->seq_++;
  const uint8_t *data = this->adu_.data();
  this->decode_message_(data, len);
  std::string regs = this->format_registers_(data, len);

  std::string ts = this->timestamp_();
  std::string gap = this->have_prev_adu_
                         ? std::to_string(this->adu_start_us_ - this->prev_adu_end_us_) + "us"
                         : "n/a (first message seen)";
  std::string hex = to_hex_(data, len);
  std::string ascii = find_ascii_(data, len);
  std::string ascii_suffix = ascii.empty() ? "" : " ascii=[" + ascii + "]";
  std::string regs_suffix = regs.empty() ? "" : " regs=[" + regs + "]";
  ESP_LOGD(TAG, "[%s] #%u gap=%s len=%u [%s]%s%s", ts.c_str(), this->seq_, gap.c_str(), (unsigned) len, hex.c_str(),
            ascii_suffix.c_str(), regs_suffix.c_str());
}

std::string AroThermModbus::format_registers_(const uint8_t *data, size_t len) {
  const uint8_t func = data[1];
  uint16_t start_reg = 0;
  size_t n_regs = 0;
  const uint8_t *payload = nullptr;

  if (func == FUNCTION_READ_HOLDING_REGISTERS) {
    if (len == FIXED_ADU_LEN) {
      this->last_read_start_reg_ = (uint16_t) ((data[2] << 8) | data[3]);
      this->last_read_count_ = (uint16_t) ((data[4] << 8) | data[5]);
      return "";
    }
    const uint8_t byte_count = data[READ_RESPONSE_BYTE_COUNT_OFFSET];
    if (byte_count % 2 != 0 || (size_t) (READ_RESPONSE_HEADER_LEN + byte_count + ADU_CRC_LEN) != len)
      return "";
    n_regs = byte_count / 2;
    if (n_regs != this->last_read_count_)
      return "";
    start_reg = this->last_read_start_reg_;
    payload = data + READ_RESPONSE_HEADER_LEN;
  } else if (func == FUNCTION_WRITE_MULTIPLE_REGISTERS) {
    if (len == FIXED_ADU_LEN)
      return "";
    start_reg = (uint16_t) ((data[2] << 8) | data[3]);
    const uint16_t count = (uint16_t) ((data[4] << 8) | data[5]);
    const uint8_t byte_count = data[WRITE_REQUEST_BYTE_COUNT_OFFSET];
    if (byte_count != count * 2 || (size_t) (WRITE_REQUEST_HEADER_LEN + byte_count + ADU_CRC_LEN) != len)
      return "";
    n_regs = count;
    payload = data + WRITE_REQUEST_HEADER_LEN;
  } else {
    return "";
  }

  std::string out;
  out.reserve(n_regs * 17);
  char buf[24];
  for (size_t i = 0; i < n_regs; i++) {
    const uint16_t raw = (uint16_t) ((payload[2 * i] << 8) | payload[2 * i + 1]);
    snprintf(buf, sizeof(buf), "%s%04X=%04X(%.2f)", i ? " " : "", (unsigned) (start_reg + i), raw,
              (int16_t) raw / 16.0f);
    out += buf;
  }
  return out;
}

uint16_t AroThermModbus::crc16_modbus_(const uint8_t *data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int b = 0; b < 8; b++) {
      if (crc & 1) {
        crc = (uint16_t) ((crc >> 1) ^ 0xA001);
      } else {
        crc = (uint16_t) (crc >> 1);
      }
    }
  }
  return crc;
}

bool AroThermModbus::modbus_crc_valid_(const uint8_t *data, size_t len) {
  if (len < 4)
    return false;
  uint16_t crc = crc16_modbus_(data, len - 2);
  return data[len - 2] == (crc & 0xFF) && data[len - 1] == ((crc >> 8) & 0xFF);
}

float AroThermModbus::scale_value_(Scale scale, int32_t raw) {
  switch (scale) {
    case Scale::DIV10:
      return raw / 10.0f;
    case Scale::D2C:
      return raw / 16.0f;
    case Scale::RAW:
    default:
      return (float) raw;
  }
}

void AroThermModbus::publish_block_(const uint8_t *data, size_t header_len, uint16_t base_register, size_t count) {
  for (const auto &rs : this->sensors_) {
    if (rs.register_address < base_register || rs.register_address >= base_register + count)
      continue;
    const size_t offset = rs.register_address - base_register;
    const size_t byte_off = header_len + ADU_REGISTER_FIELD_LEN * offset;
    const int32_t raw = (int16_t) ((data[byte_off] << 8) | data[byte_off + 1]);
    rs.sensor->publish_state(scale_value_(rs.scale, raw));
  }
}

void AroThermModbus::decode_message_(const uint8_t *data, size_t len) {
  if (!modbus_crc_valid_(data, len))
    return;

  if (len >= ADU_ADDRESS_LEN + ADU_FUNCTION_LEN && data[1] == FUNCTION_WRITE_MULTIPLE_REGISTERS) {
    if (len < WRITE_REQUEST_HEADER_LEN + ADU_CRC_LEN)
      return;
    const uint16_t start_reg = (uint16_t) ((data[2] << 8) | data[3]);
    const uint16_t count = (uint16_t) ((data[4] << 8) | data[5]);
    const uint8_t byte_count = data[WRITE_REQUEST_BYTE_COUNT_OFFSET];
    if (byte_count != count * 2 || (size_t) (WRITE_REQUEST_HEADER_LEN + byte_count + ADU_CRC_LEN) != len)
      return; 
    this->publish_block_(data, WRITE_REQUEST_HEADER_LEN, start_reg, count);
    return;
  }

  if (len < READ_RESPONSE_HEADER_LEN + ADU_CRC_LEN || data[1] != FUNCTION_READ_HOLDING_REGISTERS)
    return;

  const uint8_t byte_count = data[READ_RESPONSE_BYTE_COUNT_OFFSET];
  if (byte_count % 2 != 0 || (size_t) (READ_RESPONSE_HEADER_LEN + byte_count + ADU_CRC_LEN) != len)
    return;
  const size_t n_regs = byte_count / 2;

  uint16_t base_register;
  if (n_regs == 34) {
    base_register = 0x2000;
  } else if (n_regs == 98) {
    base_register = 0x2100;
  } else if (n_regs == 73) {
    base_register = 0x2200;
  } else {
    return;
  }
  this->publish_block_(data, READ_RESPONSE_HEADER_LEN, base_register, n_regs);
}

}  // namespace arotherm_modbus
}  // namespace esphome
