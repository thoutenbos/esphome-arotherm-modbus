# Changelog

All notable changes to this component. Sensors are listed by their
configuration key, with the name used in the example
[`arotherm-modbus.yaml`](arotherm-modbus.yaml) and the register they read;
[`REGISTERS.md`](REGISTERS.md) has the evidence for each.

## [v0.10.0] - 2026-11-19

Eleven new sensors, "no sensor fitted" handling, and the outdoor unit's
side of power-up, loss of communication and the installer settings. No
breaking changes: every key of v0.9.1 is still there with the same meaning.
This version has 64 sensors (61 numeric, 3 text); four of them are commented
out in the example configuration.

### Added

| key | name | register | what it is |
|---|---|---|---|
| `compressor_speed_command` | Compressor Speed Command | `0x1002` | rps - the controller's speed command, which the outdoor unit's target follows while modulating |
| `condensor_inlet_temp` | Condensor Inlet Temp | `0x1006` | °C - refrigerant at the gas side of the plate heat exchanger, on units with an indoor unit (aroTHERM Split plus); unknown on a monoblock |
| `outdoor_mode` | Outdoor Mode | `0x2000` | the mode the outdoor unit is actually in, in the same codes as Demand Mode |
| `compressor_power` | Compressor Power | `0x2018` | W - the drive's own mains power, without the fan and standby load |
| `holdoff_countdown` | Hold-off Countdown | `0x211C` | s - the outdoor unit's minimum off-time after a compressor stop (180 s), and the 485 s after a lost controller returns |
| `fault_code` | Fault Code | `0x2100` | the fault code on the Vaillant display (`9998` = F.9998), `65535` when there is none. Only one code has been seen so far |
| `silent_mode_active` | Silent Mode Active | `0x110D` | `1` while the controller's noise-reduction program runs |

Commented out in the example configuration, for diagnostics:

| key | name | register | what it is |
|---|---|---|---|
| `episode_active` | Episode Active | `0x1004` | the controller's heating/hot-water episode flag, which `Run Phase` follows |
| `lockout_flag` | Lockout Flag | `0x2121` | clear from the start hand-off until 480 s after the compressor stops |
| `reinitialise_flag` | Re-initialise Flag | `0x1018` | set together with `Demand Mode` 6 |
| `test_program` | Test Program | `0x2005` | the step of an installer test program |

Component:

- **"No sensor fitted" publishes nothing.** `0x8000` on any temperature
  register and `0xFFFF` on `water_pressure` used to be published scaled
  (-2048 °C, -0.1 bar); the entity now stays unknown instead. This mostly
  affects the aroTHERM Split plus, whose water pressure register is not
  fitted, and every unit's outside temperature in the first poll after the
  controller boots.
- A 32-register response with no request before it - right after boot on an
  aroTHERM Split plus - is now placed in `0x2000` instead of being dropped.
- Bytes that cannot be framed as a message are logged at `DEBUG` as
  `UNFRAMED` lines instead of being dropped silently. That includes the
  ten-byte announcement a unit sends once when it powers up.

Tests: ten aroTHERM Split plus datasets from
[#4](https://github.com/thoutenbos/esphome-arotherm-modbus/issues/4), and
unit cases for the behaviour above.

### Changed

- **`demand_mode`** has two more values: `4` while an installer test
  program runs (with the step in `test_program`), and `6` for a few seconds
  after the controller regains an outdoor unit it had lost.
- **`compressor_speed_target`** is documented as what it is: the
  controller's command while modulating, the outdoor unit's own schedule at
  a start, a stop and in a defrost.
- **`REGISTERS.md`**:
  - New sections on who decides what (the speed control loop lives in the
    controller; the outdoor unit sets the envelope and owns start, stop and
    defrost), power-up and loss of communication, and the installer settings
    and test programs (an EEBus power limit is not on the bus; silent mode
    is one flag; the forced-defrost test runs the normal defrost sequence).
  - The 180 s countdown is the outdoor unit's enforced minimum off-time, and
    the 480 s lockout is only how long the drive stays awake - not a restart
    lock.
  - The refrigerant identities are close but not exact: `condensing -
    condensor outlet` matches `subcooling` within one count in 98% of running
    polls, `compressor inlet - evaporating` matches `superheat` more loosely.
    An aroTHERM Split plus computes its superheat from the expansion valve
    outlet temperature instead.
  - Cross-checked against the aroTHERM Split plus capture: `0x2139` is the
    stored modulation floor that `Compressor Speed Min` never goes below (300
    on the Split plus, 200 here), and `0x2142` is most likely the expansion
    valve's lower limit.
  - The defrost reference re-latch can take longer than 300 s when the
    compressor speed is not yet steady.
- **Example configuration:** the new sensors, a "Faults and settings"
  group, and the four diagnostic sensors as comments.

## [v0.9.1] - 2026-11-11

First release candidate, and the first tagged version. Changes are listed
against the previous state of `main`, which had 36 sensors; this version has
53 (50 numeric, 3 text).

### Breaking changes

Configurations that use these keys fail validation and need updating:

- **`load_step` (`0x201C`) is replaced by `active_current`** (`Mains
  Current`). The register turned out to be the unit's mains current, not a
  percentage: it is now published in A (`raw / 1000`, 0.1 A resolution)
  instead of `%` (`raw / 100`).
- **`compressor_run_time` (`0x2146`) is replaced by `fan_target_stable_time`**
  (`Fan Target Stable Time`). The register is not the compressor's run time:
  it counts the seconds since the fan speed *target* last moved more than 3%,
  and runs whenever the fan target is set, including before the compressor
  starts and after it stops.
- **`flow_rate_secondary` (`0x2020`) is removed.** What this second
  flow-like figure measures is still not established, so it is no longer
  published.

### Added

Sensors:

| key | name | register | what it is |
|---|---|---|---|
| `heat_output` | Heat Output | `0x1014` | W - the heat output the controller computes and the outdoor unit's defrost logic uses |
| `hot_water_mode_active` | Hot Water Mode Active | `0x1012` | `1` while the outdoor unit is in hot-water mode; the edges mark the diverter valve moving |
| `building_circuit_flow_target` | Building Circuit Flow Target | `0x2001` | l/h - the flow the outdoor unit asks for (1205 l/h during a demand) |
| `compressor_speed_min` | Compressor Speed Min | `0x2003` | rps - lower bound of the permitted compressor speed, the modulation floor |
| `compressor_speed_max` | Compressor Speed Max | `0x2002` | rps - upper bound of the permitted compressor speed |
| `compressor_slew_limit` | Compressor Slew Limit | `0x213F`:`0x2140` | rps/s - how fast the speed target may move (2.0 or 0.2) |
| `compressor_speed_stable_time` | Compressor Speed Stable Time | `0x2145` | s - since the compressor speed last moved more than 3% |
| `fan_target_stable_time` | Fan Target Stable Time | `0x2146` | s - since the fan speed target last moved more than 3% (replaces `compressor_run_time`, see above) |
| `mains_voltage` | Mains Voltage | `0x201B` | V |
| `active_current` | Mains Current | `0x201C` | A (replaces `load_step`, see above) |
| `demand_window` | Demand Window | `0x215C` | `150` from the compressor start hand-off until 482 s after it stops |
| `defrost_sequence` | Defrost Sequence | `0x2006` | `1` for the whole defrost, from preparation to recovery |
| `defrost_active` | Defrost Active | `0x2131` | `1` while the refrigerant circuit is reversed |
| `defrost_capacity_loss` | Defrost Capacity Loss | `0x2160`:`0x2161` | % below the clean-coil reference; a defrost is commanded after 60 s at or above 15 |
| `defrost_reference_heat_output` | Defrost Reference Heat Output | `0x2147` | W - the clean-coil reference |
| `defrost_reference_attempt` | Defrost Reference Attempt | `0x2148` | which attempt at taking that reference this is |
| `time_since_defrost` | Time Since Defrost | `0x214C` | s - since the last defrost ended |

Text sensors (new: the component can now publish text):

| key | name | register | what it is |
|---|---|---|---|
| `serial_number` | Serial Number | `0x1203`-`0x1214` | the unit's 28-character serial number |
| `firmware_version` | Firmware Version | `0x2203`-`0x2205` | `major.minor.patch` |
| `compressor_ramp_state` | Compressor Ramp State | `0x214E` | `Off`, `Starting`, `At speed`, `Ramping up`, `Ramping down`, `Ramping down to stop`; published on change only |

Component:

- Text sensors, and the `/50` and `/1000` scales.
- Timers and powers are read as **unsigned** 16-bit values, so they no
  longer go negative past 32,767.

### Changed

- **`demand_mode`** (`0x1000`) has a fifth value, `5`, for defrost.
- **`demand_state`** (`0x2144`) is a ten-state machine: besides `0` idle,
  `1` pre-run, `3` running and `4` fan run-on, it steps through `5`, `6`,
  `7`, `8`, `9` and `11` during a defrost.
- **`derated_temp_ceiling`** (`0x2137`): the de-rating starts below -5 °C
  evaporating and follows two straight segments, not one.
- **Example configuration:**
  - `Heat Pump COP` is now `Heat Output` divided by `Electric Power
    Consumption`, and is still unavailable while the compressor is stopped.
  - `Flow/Return Calibration` is renamed `Flow-Return Calibration` (same
    entity ID in Home Assistant).
  - Sensors are grouped by topic, and every new sensor is included.
- **`REGISTERS.md`** is rewritten as a statement of the current findings:
  register tables per block, the state machines and sequences (start, stop,
  heating/hot-water changeover, defrost, the frost model and the defrost
  decision), the formulas behind the derived registers, how the machine
  behaves, and the open questions.

### Removed

- `flow_rate_secondary` (`0x2020`) - see Breaking changes.
- `Thermal Power Delivery` from the example configuration. `Heat Pump COP`
  now uses the `Heat Output` register instead. To keep an independent heat
  figure, add a template sensor computing `building_circuit_flow x delta_t x
  4.186 / 3600` (kW); unlike `Heat Output` it is not affected by the
  flow/return calibration.

### Upgrading

1. Remove `load_step`, `compressor_run_time` and `flow_rate_secondary` from
   your configuration.
2. Add `active_current` and `fan_target_stable_time` if you want those
   registers. They create new entities with new IDs, so Home Assistant keeps
   the old ones' history but does not carry it over.
3. Copy whichever new sensors you want from the example configuration.
4. If your configuration references `id(thermal_power_delivery)`, keep your
   own template sensor for it or switch to `heat_output`.
