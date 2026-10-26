// Host test harness: runs the real components/arotherm_modbus/arotherm_modbus.cpp
// (compiled against the stand-in ESPHome headers in tests/host/) on bytes
// read from stdin, and prints everything it publishes and logs. Driven by
// tests/run_tests.py; not meant to be used by hand, but it can be:
//
//   S 2007 D2C            register a sensor (index = order of S lines)
//   B 01 03 20 00 00 22   feed bytes; the clock advances one 19200-baud
//                         character time (573 us) per byte
//   I 150000              advance the clock (bus idle)
//   N                     start over with a fresh component, same sensors
//   E                     echo "E" (marks the end of a case in the output)
//
// Output, one event per line, in the order the component produced them:
//
//   P <sensor index> <value>
//   L <level> <message>

#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "arotherm_modbus.h"

namespace esphome {

void test_log(char level, const char *tag, const char *format, ...) {
  (void) tag;
  char buf[4096];
  va_list args;
  va_start(args, format);
  vsnprintf(buf, sizeof(buf), format, args);
  va_end(args);
  printf("L %c %s\n", level, buf);
}

}  // namespace esphome

using esphome::arotherm_modbus::AroThermModbus;

namespace {

constexpr uint32_t BYTE_US = 573;  // 11 bits (8N1 + start) at 19200 baud

// Exposes the protected byte entry point; everything else is the real class.
class Harness : public AroThermModbus {
 public:
  using AroThermModbus::process_byte_;
};

struct SensorDef {
  uint16_t reg;
  AroThermModbus::Scale scale;
};

AroThermModbus::Scale parse_scale(const std::string &s) {
  if (s == "RAW")
    return AroThermModbus::Scale::RAW;
  if (s == "DIV10")
    return AroThermModbus::Scale::DIV10;
  if (s == "DIV100")
    return AroThermModbus::Scale::DIV100;
  if (s == "D2C")
    return AroThermModbus::Scale::D2C;
  if (s == "F32")
    return AroThermModbus::Scale::F32;
  fprintf(stderr, "unknown scale %s\n", s.c_str());
  exit(2);
}

}  // namespace

int main() {
  esphome::time::RealTimeClock clock;
  std::vector<SensorDef> defs;
  std::vector<std::unique_ptr<esphome::sensor::Sensor>> sensors;
  std::unique_ptr<Harness> component;
  uint32_t now_us = 1000000;

  auto rebuild = [&]() {
    component = std::make_unique<Harness>();
    component->set_time(&clock);
    sensors.clear();
    for (size_t i = 0; i < defs.size(); i++) {
      auto s = std::make_unique<esphome::sensor::Sensor>();
      s->on_publish = [i](float v) { printf("P %zu %.6f\n", i, v); };
      component->add_sensor(defs[i].reg, defs[i].scale, s.get());
      sensors.push_back(std::move(s));
    }
  };
  rebuild();

  std::string line;
  while (std::getline(std::cin, line)) {
    std::istringstream in(line);
    std::string cmd;
    if (!(in >> cmd))
      continue;
    if (cmd == "S") {
      std::string reg, scale;
      in >> reg >> scale;
      defs.push_back({(uint16_t) std::stoul(reg, nullptr, 16), parse_scale(scale)});
      rebuild();
    } else if (cmd == "B") {
      std::string hex;
      while (in >> hex) {
        now_us += BYTE_US;
        component->process_byte_((uint8_t) std::stoul(hex, nullptr, 16), now_us);
      }
    } else if (cmd == "I") {
      unsigned long us;
      in >> us;
      now_us += (uint32_t) us;
    } else if (cmd == "N") {
      rebuild();
    } else if (cmd == "E") {
      printf("E\n");
    } else {
      fprintf(stderr, "unknown command %s\n", cmd.c_str());
      return 2;
    }
  }
  return 0;
}
