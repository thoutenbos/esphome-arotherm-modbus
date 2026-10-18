// Host-side stand-in for ESPHome's esphome/core/log.h: every ESP_LOGx call
// goes to esphome::test_log(), which tests/harness.cpp implements.
#pragma once

namespace esphome {
void test_log(char level, const char *tag, const char *format, ...) __attribute__((format(printf, 3, 4)));
}  // namespace esphome

#define ESP_LOGE(tag, ...) ::esphome::test_log('E', tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) ::esphome::test_log('W', tag, __VA_ARGS__)
#define ESP_LOGI(tag, ...) ::esphome::test_log('I', tag, __VA_ARGS__)
#define ESP_LOGCONFIG(tag, ...) ::esphome::test_log('C', tag, __VA_ARGS__)
#define ESP_LOGD(tag, ...) ::esphome::test_log('D', tag, __VA_ARGS__)
#define ESP_LOGV(tag, ...) ::esphome::test_log('V', tag, __VA_ARGS__)
