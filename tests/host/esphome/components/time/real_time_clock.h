// Host-side stand-in for ESPHome's time::RealTimeClock: a clock frozen at a
// fixed, valid time so the component's log timestamps are reproducible.
#pragma once

namespace esphome {
namespace time {

struct ESPTime {
  int year{2026};
  int month{1};
  int day_of_month{1};
  int hour{0};
  int minute{0};
  int second{0};
  bool valid{true};
  bool is_valid() const { return this->valid; }
};

class RealTimeClock {
 public:
  ESPTime now() { return this->fixed; }
  ESPTime fixed{};
};

}  // namespace time
}  // namespace esphome
