// Host-side stand-in for ESPHome's esphome/core/component.h: just enough of
// Component for arotherm_modbus.cpp to compile and run off-device.
#pragma once

#include <functional>
#include <string>

namespace esphome {

class Component {
 public:
  virtual ~Component() = default;
  virtual void setup() {}
  virtual void loop() {}
  void mark_failed() { this->failed_ = true; }
  bool is_failed() const { return this->failed_; }

 protected:
  bool failed_{false};
};

}  // namespace esphome
