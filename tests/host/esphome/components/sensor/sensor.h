// Host-side stand-in for ESPHome's sensor::Sensor: records every published
// state and hands it to an optional callback.
#pragma once

#include <cmath>
#include <functional>

namespace esphome {
namespace sensor {

class Sensor {
 public:
  void publish_state(float state) {
    this->state = state;
    if (this->on_publish)
      this->on_publish(state);
  }
  float state{NAN};
  std::function<void(float)> on_publish;
};

}  // namespace sensor
}  // namespace esphome
