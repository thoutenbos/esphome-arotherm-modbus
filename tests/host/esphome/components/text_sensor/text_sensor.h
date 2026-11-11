// Host-side stand-in for ESPHome's text_sensor::TextSensor: records every
// published state and hands it to an optional callback.
#pragma once

#include <functional>
#include <string>

namespace esphome {
namespace text_sensor {

class TextSensor {
 public:
  void publish_state(const std::string &state) {
    this->state = state;
    if (this->on_publish)
      this->on_publish(state);
  }
  std::string state;
  std::function<void(const std::string &)> on_publish;
};

}  // namespace text_sensor
}  // namespace esphome
