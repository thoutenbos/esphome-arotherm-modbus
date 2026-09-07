# Register map: complete known structure

Everything this project knows about every message this bus carries, one row
per register (or per unbroken span of registers that are statistically
indistinguishable from each other - see "How to read the range rows"
below), across all six register blocks.

## Message framing (applies to every block below)

Every message is a standard Modbus RTU ADU: address (`01`, always this
device), function code (`0x03` Read Holding Registers or `0x10` Write
Multiple Registers), a function-specific body, and a CRC-16 (poly
`0xA001`, init `0xFFFF`). A read transaction is
a short *request* (which registers, how many) followed by a *response*
carrying the values - the response never repeats its own starting
address, so the firmware (and this document) attributes a response's
registers to the block by matching its *register count* against the
counts below, the same technique `format_registers_()` and
`decode_message_()` both rely on. A write transaction is a
request carrying the values themselves, acknowledged by an 8-byte echo of
the address/count.

| block | op | start address | register count | request/notification bytes | data-carrying message |
|---|---|---|---|---|---|
| `0x1000` | write (`0x10`) | `0x1000` | 26 | 61-byte write request (carries the data), 8-byte ack | the write request itself |
| `0x1100` | write (`0x10`) | `0x1100` | 15 | 39-byte write request, 8-byte ack | the write request itself |
| `0x1200` | write (`0x10`) | `0x1200` | 25 | 59-byte write request, 8-byte ack | the write request itself |
| `0x2000` | read (`0x03`) | `0x2000` | 34 | 8-byte read request | 73-byte read response |
| `0x2100` | read (`0x03`) | `0x2100` | 98 | 8-byte read request | 201-byte read response |
| `0x2200` | read (`0x03`) | `0x2200` | 73 | 8-byte read request | 151-byte read response |

All six repeat in a fixed order roughly once every 1.2s.

## How to read the range rows

Where no per-register distinction has ever been found - a span that has
only ever been seen holding one constant value, or that varies but has
never matched anything in `ebusd` even loosely - one row covers the whole
span rather than repeating the same "unknown" fact register by register.
Every register address in every block is accounted for below, either
individually or inside exactly one such range; nothing is omitted.

**Status legend:**
- **Confirmed** - matched a specific `ebusd` field to the standard this
  project holds for a "real" match (median and/or p90 absolute difference
  effectively 0 over a full session, or an exact structural fact like a
  byte-for-byte echo). Published as an HA sensor unless noted otherwise.
- **Confirmed (structural)** - a fact about the register's behavior
  (always this exact value, echoes another block's payload) established
  with certainty, but not a decoded physical quantity - nothing to
  publish, because there is no field identity to publish it *as*.
- **Lead** - a plausible but not-fully-confirmed match: a looser
  statistical fit, a value range that's merely "plausible," or a
  correlation not yet checked against a real physical event.
- **Unknown** - no candidate identity found, or not yet examined at all.

---

## Write block `0x1000` (26 registers, `0x1000`-`0x1019`)


| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x1000` | 0 | demand mode | — (no direct `ebusd` field; correlates with `RunDataStatuscode`'s state transitions) | raw integer (no scale) | **Confirmed** | published as `demand_mode`; not telemetry - the controller's own command (`0`=idle, `2`=DHW demand observed so far). Leads `ebusd`'s corresponding `RunDataStatuscode` report by 24-33s in the one full cycle observed |
| `0x1001` | 1 | unknown | — | — | Unknown | always `0x0000` this session |
| `0x1002` | 2 | compressor speed (filtered/smoothed echo of `0x2010`) | `hmux0_rundatacompressorspeed` | `/10`, rps | **Confirmed (structural)** | leads `0x2010` smoothly by a couple of seconds during ramp-up but lags badly on the way down (distinct dynamics from the true target at `0x2122` not published |
| `0x1003` | 3 | building pump power | `hmux0_rundatabuildingcpumppower` | `/10`, % | **Confirmed** | tracked point-for-point within ~1% at all 54 real timestamped `ebusd` values; first write-block field ever decoded and published |
| `0x1004` | 4 | unknown, structurally tied to the demand cycle | — (spurious match only) | — | **Confirmed (structural)** | steps with the demand cycle but its stop-side transition lags `0x1000`'s own by ~9 minutes, unlike the tight-lockstep registers; not published, meaning unclear |
| `0x1005` | 5 | condensor outlet temp (echo of `0x200A`) | `hmux0_rundatacondensoroutlettemp` | `/16` (D2C), °C | **Confirmed (structural)** | median diff 0.0625°C, p90 0.375°C; not published from here (would duplicate `condensor_outlet_temp`) |
| `0x1006` | 6 | separator/marker | — | — | **Confirmed (structural)** | always exactly `0x8000`, every occurrence, whole session - same head/tail marker the old byte-grammar noticed; meaning still unexplained |
| `0x1007` | 7 | flow temp (echo of `0x200C`) | `hmux0_rundataflowtemp` (and `ctlv3_hc1flowtemp`) | `/16` (D2C), °C | **Confirmed (structural)** | median diff 0.0625°C, p90 0.250°C; not published from here (would duplicate `flow_temp`) |
| `0x1008` | 8 | return temp (echo of `0x200D`) | `hmux0_rundatareturntemp` | `/16` (D2C), °C | **Confirmed (structural)** | median diff 0.0625°C, p90 0.188°C; not published from here (would duplicate `return_temp`) |
| `0x1009` | 9 | outside/ambient temperature | `hmux0_status01_temp_2` **and** `ctlv3_displayedoutsidetemp` | `/16` (D2C), °C | **Confirmed** | published as `outside_temp` |
| `0x100A` | 10 | unknown, likely a building-circuit-flow echo | — (spurious match only against `BuildingCircuitFlow`, but same session-wide ceiling, `1219`, as the confirmed `0x2014`) | — | **Lead** | 84 distinct values, `0x0000`-`0x04C3` (0-1219) this session; overshoots to a peak then eases back down rather than holding a setpoint's flat step - read as another echo, not a request |
| `0x100B`-`0x1011` | 11-17 (7 registers) | unknown | — | — | Unknown | constant at zero |
| `0x1012` | 18 | unknown, secondary demand-cycle flag | — | — | **Confirmed (structural)** | steps within 1-2s of the primary demand echo (`0x2001`) at start; not published, meaning unclear |
| `0x1013` | 19 | unknown | — | — | Unknown | constant at zero this session |
| `0x1014` | 20 | unknown, tracks the demand cycle | — (soft lead only, `/100` against `RunDataBuildingCPumpPower`) | `/100`(soft lead) | **Lead** | 337 distinct values, `0x0000`-`0x1BF9` (0-7161) this session; non-zero only while `demand_mode` is active, decays with the stop-side ramp; not a confirmed identity |
| `0x1015`-`0x1018` | 21-24 (4 registers) | unknown/placeholder | — | — | Unknown | constant all session (`0xFFFF` at 21-23, `0` at 24) |
| `0x1019` | 25 | requested flow temperature | `hmux0_rundataflowtempdesired` | `/16` (D2C), °C | **Confirmed** | published as `requested_flow_temp`; a genuine setpoint (only 7 distinct raw values all session: idle ~20°C, a one-sample 75°C transient, then a steady 80°C for the whole DHW cycle, 0°C once demand clears) - steps in the same write message as `demand_mode` at both start and stop; matches `ebusd`'s `RunDataFlowTempDesired` (`"80"`) exactly |

## Write block `0x1100` (15 registers, `0x1100`-`0x110E`)

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x1100` | 0 | unknown | — | — | Unknown | always `0x0000` (0) |
| `0x1101` | 1 | unknown | — | — | Unknown | always `0x012C` (300) |
| `0x1102` | 2 | unknown | — | — | Unknown | always `0x4650` (18000) |
| `0x1103` | 3 | unknown | — | — | Unknown | always `0x0010` (16) |
| `0x1104` | 4 | unknown | — | — | Unknown | always `0x8001` (32769) |
| `0x1105`-`0x110A` | 5-10 (6 registers) | unknown | — | — | Unknown | always `0x0000` (0), each individually |
| `0x110B`-`0x110C` | 11-12 (2 registers) | unknown | — | — | Unknown | always `0x0001` (1), each individually |
| `0x110D`-`0x110E` | 13-14 (2 registers) | unknown | — | — | Unknown | always `0x0000` (0), each individually |

Every register in this block is constant across the whole session, but
not all at the same value - this rules out "uninitialized/all-zero" as
the explanation, consistent with (but not proof of) static configuration
rather than telemetry. Finding an identity for any of them needs a
session spanning an actual change (reconfiguration, firmware update,
commissioning), the same limitation as `0x2200`'s static registers.

## Write block `0x1200` (25 registers, `0x1200`-`0x1218`)

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x1200`-`0x1201` | 0-1 (2 registers) | unknown, not string content | — | — | Unknown | always `0xFFFF` (65535), each individually - not printable ASCII, so not part of the string below; likely framing |
| `0x1202`-`0x1214` | 2-20 (19 registers) | ASCII serial/model string | — (no `ebusd` equivalent - this is a device identity string, not telemetry) | ASCII text | **Confirmed (structural)**, identity only | confirmed to carry a 25-character ASCII serial/model string which byte(s) of which register hold which character has not been individually mapped |
| `0x1215`-`0x1218` | 21-24 (4 registers) | unknown, not string content | — | — | Unknown | constant all session, not all the same value: `0x0001` (1) at offset 21, `0x0000` (0) at 22-23, `0xFFFF` (65535) at 24 - none printable ASCII, so not part of the string above; likely framing |

## Read block `0x2000` (34 registers, `0x2000`-`0x2021`)

| register | offset | field / identity | `ebusd` match | scale | status | HA sensor |
|---|---|---|---|---|---|---|
| `0x2000` | 0 | unknown | — | — | Unknown | — (2 distinct values, `0x0000`-`0x0002` (0-2) - the same two values write-block `demand_mode` itself takes; worth checking as a possible read-side echo of `demand_mode`, not yet done) |
| `0x2001` | 1 | demand echo (two-state: `0` or `1205`) | — (rejected as `hmux0_buildingcircuitflow` - that was coincidence; the two-state shape is a real flag, not noise) | — | **Confirmed (structural)** | — (steps in lockstep with write-block `demand_mode` at every real transition checked; not published, redundant with `demand_mode`) |
| `0x2002` | 2 | unknown, part of the prerun-to-active handoff cluster | — | — | **Confirmed (structural)** | — (68 distinct values, `0x0000`-`0x0336` (0-822); steps at the 12:16:15 handoff, then rises then falls across the rest of an active cycle - doesn't track any confirmed register's shape; |
| `0x2003` | 3 | unknown, part of the prerun-to-active handoff cluster | — | — | **Confirmed (structural)** | — (36 distinct values, `0x0000`-`0x01F4` (0-500); steps at the 12:16:15 handoff, then declines slowly across the rest of an active cycle; not a confirmed identity |
| `0x2004`-`0x2006` | 4-6 (3 registers) | unknown | — | — | Unknown | — (always `0x0000`, each individually - confirmed still constant even under real compressor load, not just at idle) |
| `0x2007` | 7 | compressor inlet temp | `hmux0_rundatacompressorinlettemp` | `/16` (D2C), °C | **Confirmed** | `compressor_inlet_temp` |
| `0x2008` | 8 | compressor outlet temp | `hmux0_rundatacompressoroutlettemp` | `/16` (D2C), °C | **Confirmed** | `compressor_outlet_temp` |
| `0x2009` | 9 | EEV outlet temp | `hmux0_rundataeevoutlettemp` | `/16` (D2C), °C | **Confirmed** | `eev_outlet_temp` |
| `0x200A` | 10 | condensor outlet temp | `hmux0_rundatacondensoroutlettemp` | `/16` (D2C), °C | **Confirmed** | `condensor_outlet_temp` |
| `0x200B` | 11 | air inlet temp | `hmux0_rundataairinlettemp` (also `hmux0_airintaketemp`, same sensor under two names) | `/16` (D2C), °C | **Confirmed** | `air_inlet_temp` |
| `0x200C` | 12 | flow temp | `hmux0_rundataflowtemp` (also `hmux0_status01_temp` and `ctlv3_hc1flowtemp`) | `/16` (D2C), °C | **Confirmed** | `flow_temp` |
| `0x200D` | 13 | return temp | `hmux0_rundatareturntemp` (also `hmux0_status01_temp_1`) | `/16` (D2C), °C | **Confirmed** | `return_temp` |
| `0x200E` | 14 | low (refrigerant-side) pressure | `hmux0_kmkreisniederdruck` | `/10`, bar | **Confirmed exact** | `low_pressure` |
| `0x200F` | 15 | high (refrigerant-side) pressure | `hmux0_rundatahighpressure` | `/10`, bar | **Confirmed** | `high_pressure` |
| `0x2010` | 16 | compressor speed | `hmux0_rundatacompressorspeed` | `/10`, rps | **Confirmed exact** | `compressor_speed` |
| `0x2011` | 17 | fan1 speed | `hmux0_rundatafan1speed` | raw integer (no scale), rpm | **Confirmed** | `fan1_speed`; also readable (unpublished) at `0x2019` |
| `0x2012` | 18 | unknown | — | — | Unknown | — (always `0x0000`) |
| `0x2013` | 19 | water (hydraulic-circuit) pressure | `hmux0_flowpressure` / `ctlv3_waterpressure` (same physical sensor relayed by two eBUS devices under two different names) | `/10`, bar | **Confirmed exact** | `water_pressure` |
| `0x2014` | 20 | building circuit flow | `hmux0_buildingcircuitflow` | raw integer (no scale), l/h | **Confirmed** | `building_circuit_flow` |
| `0x2015` | 21 | run phase | — (no direct `ebusd` field; tracks `RunDataStatuscode`'s state machine) | raw integer (no scale) | **Confirmed** | `run_phase`; a low-latency internal state code (`0`=idle, `1`=active, `6`=post-run, plus transitional codes `2`/`4` seen only during shutdown) |
| `0x2016`-`0x2017` | 22-23 (2 registers) | unknown | — | — | Unknown | — (always `0x0000`, each individually) |
| `0x2018` | 24 | electric power consumption (echo of `0x211B`, weaker fit) | `hmux0_rundataelectricpowerconsumption` | raw integer (no scale), W | **Confirmed (structural)** | — (median diff 37.42 W, looser than `0x211B`'s 7.45 W; not published) |
| `0x2019` | 25 | fan1 speed (echo of `0x2011`) | `hmux0_rundatafan1speed` | raw integer (no scale), rpm | **Confirmed (structural)** | — (identical sequence to `0x2011`; not published, redundant with `fan1_speed`) |
| `0x201A` | 26 | unknown | — | — | Unknown | — (always `0x0000`) |
| `0x201B` | 27 | unknown | — | — | Unknown | — (23 distinct values, `0x0000`-`0x316A` (0-12650); real variation, not yet checked against any `ebusd` candidate) |
| `0x201C` | 28 | unknown | — | — | Unknown | — (79 distinct values, `0x0000`-`0x2710` (0-10000); real variation, not yet checked against any `ebusd` candidate) |
| `0x201D` | 29 | electric power consumption (echo of `0x211B`, weaker fit) | `hmux0_rundataelectricpowerconsumption` | raw integer (no scale), W | **Confirmed (structural)** | — (identical sequence to `0x2018`; not published, redundant with `0x211B`) |
| `0x201E` | 30 | unknown | — | — | Unknown | — (60 distinct values, `0x0000`-`0x1EAA` (0-7850); a correction to this register's earlier "constant 0.0, not examined under load" note - it varies substantially once real load data is checked) |
| `0x201F` | 31 | unknown | — | — | Unknown | — (67 distinct values, `0x0000`-`0x2648` (0-9800); same correction as `0x201E`) |
| `0x2020` | 32 | unknown | — | — | Unknown | — (94 distinct values, `0x0000`-`0x04B9` (0-1209); same correction as `0x201E`) |
| `0x2021` | 33 | unknown, possibly a percentage/position | — | none tried beyond raw | **Lead** | — (79 distinct values, `0x0640`-`0x2D50` (1600-11600); idle value `1600` is `100.0` at `/16`, consistent with a percentage or position field, but not checked against any `ebusd` candidate over its full range) |

## Read block `0x2100` (98 registers, `0x2100`-`0x2161`)

| register | offset | field / identity | `ebusd` match | scale | status | HA sensor |
|---|---|---|---|---|---|---|
| `0x2100`-`0x2118` | 0-24 (25 registers) | placeholder | — | — | **Confirmed (structural)** | — (constant `0xFFFF` in every occurrence seen; meaning unexplained) |
| `0x2119` | 25 | unknown | — | — | **Confirmed (structural)** | — (constant `0` in every occurrence seen) |
| `0x211A` | 26 | unknown | — | — | **Confirmed (structural)** | — (constant `1` in every occurrence seen) |
| `0x211B` | 27 | electric power consumption | `hmux0_rundataelectricpowerconsumption` | raw integer (no fixed-point scale), W | **Confirmed** | `electric_power_consumption` |
| `0x211C` | 28 | unknown - rolling counter | — (no `ebusd` field matched) | — | Unknown | — (0 most of the time, else counts up 1,2,3,...,179 before resetting - a tick/sequence counter, not a physical reading) |
| `0x211D`-`0x211F` | 29-31 (3 registers) | unknown | — | — | **Confirmed (structural)** | — (constant `1` in every occurrence seen, all three) |
| `0x2120` | 32 | EEV position (absolute) | `hmux0_rundataeevpositionabs` | raw integer (no fixed-point scale), deg | **Confirmed exact** | `eev_position` |
| `0x2121` | 33 | unknown, part of the shutdown lockout cluster | — | — | **Confirmed (structural)** | — (stays off its idle value for 6-7 minutes after `ebusd` already reports `RunDataStatuscode = S100_Standby` - an internal minimum-off-time/anti-short-cycle timer invisible to `ebusd`; not published, meaning/unit unclear) |
| `0x2122` | 34 | compressor speed target (not an echo) | `hmux0_rundatacompressorspeed` | `/10`, rps | **Confirmed** | published as `compressor_speed_target`; snaps to the newly commanded value the instant a demand starts or stops - `compressor_speed` (`0x2010`) only catches up over the following several seconds of ramp. Previously misclassified as a third echo location on a diff-statistic basis alone; distinguishing it needed lining up individual samples through a real ramp |
| `0x2123` | 35 | unknown | — | — | Unknown | 108 distinct values, `0x0000`-`0x028A` (0-650) |
| `0x2124` | 36 | unknown | — | — | Unknown | always `0x0000` |
| `0x2125` | 37 | unknown | — | — | Unknown | always `0x0001` (1) |
| `0x2126` | 38 | unknown | — | — | Unknown | 632 distinct values, `0x010A`-`0x0461` (266-1121) |
| `0x2127` | 39 | unknown | — | — | Unknown | always `0x0000` |
| `0x2128` | 40 | unknown | — | — | Unknown | 200 distinct values, `0x0058`-`0x016C` (88-364) |
| `0x2129` | 41 | subcooling (looser fit than `0x212A`) | `hmux0_istwertunterkuehlung` | `/16` (D2C), K | **Lead** | — (median 0.0025°C, p90 0.37°C - real but looser than `0x212A`'s exact fit; not published) |
| `0x212A` | 42 | subcooling (actual) | `hmux0_istwertunterkuehlung` | `/16` (D2C), K | **Confirmed exact** | `subcooling` |
| `0x212B` | 43 | unknown | — | — | Unknown | always `0x0000` |
| `0x212C` | 44 | superheat (actual) | `hmux0_istwertueberthitzung` | `/16` (D2C), K | **Confirmed** | `superheat` |
| `0x212D` | 45 | EEV position status | `hmux0_statuseevposition` | `/10`, % | **Confirmed** | `eev_position_status`; distinct physical quantity from the absolute-degree `eev_position` at `0x2120`/`0x2141` |
| `0x212E` | 46 | unknown, part of the shutdown lockout cluster | — | — | **Confirmed (structural)** | — (same 6-7 minute post-`Standby` lockout behavior as `0x2121`; not published) |
| `0x212F`-`0x2136` | 47-54 (8 registers) | unknown | — | — | Unknown | always `0x0000`, each individually |
| `0x2137` | 55 | unknown | — | — | Unknown | always `0x0500` (1280) |
| `0x2138` | 56 | unknown | — | — | Unknown | always `0x04B0` (1200) |
| `0x2139` | 57 | unknown | — | — | Unknown | always `0x00C8` (200) |
| `0x213A`-`0x213E` | 58-62 (5 registers) | unknown | — | — | Unknown | always `0x0000`, each individually |
| `0x213F` | 63 | unknown | — | — | Unknown | 2 distinct values, `0x3E4C`/`0x4000` (15948/16384) |
| `0x2140` | 64 | unknown | — | — | Unknown | 2 distinct values, `0x0000`/`0xCCCD` (0/52429) |
| `0x2141` | 65 | EEV position (echo of `0x2120`) | `hmux0_rundataeevpositionabs` | raw integer (no scale), deg | **Confirmed (structural)** | — (would duplicate `eev_position`) |
| `0x2142` | 66 | unknown | — | — | Unknown | always `0x0037` (55) |
| `0x2143` | 67 | unknown | — | — | Unknown | always `0x020D` (525) |
| `0x2144` | 68 | unknown, tight stop-side flag | — | — | **Confirmed (structural)** | — (4 distinct values, `0x0000`-`0x0004` (0-4), over the full session - more states than the single `1`->`3` transition described where this register is discussed, which only covered the stop window specifically; steps in tight lockstep with the stop-side `demand_mode` clear; not published, meaning unclear) |
| `0x2145` | 69 | unknown | — | — | Unknown | 3631 distinct values, `0x0000`-`0x1102` (0-4354) - the densest unidentified register in this block by far |
| `0x2146` | 70 | unknown | — | — | Unknown | 2050 distinct values, `0x0000`-`0x0945` (0-2373) |
| `0x2147`-`0x214D` | 71-77 (7 registers) | unknown | — | — | Unknown | always `0x0000`, each individually |
| `0x214E` | 78 | unknown | — | — | Unknown | 4 distinct values, `0x0000`-`0x0010` (0-16); steps once right after the compressor ramp begins at the 12:16:15 handoff |
| `0x214F` | 79 | unknown | — | — | Unknown | 247 distinct values, `0x0000`-`0x02B9` (0-697) |
| `0x2150`-`0x2152` | 80-82 (3 registers) | unknown | — | — | Unknown | always `0x0000`, each individually |
| `0x2153` | 83 | unknown | — | — | Unknown | 116 distinct values, `0x0000`-`0x01CB` (0-459) |
| `0x2154` | 84 | unknown | — | — | Unknown | always `0x0000` |
| `0x2155` | 85 | unknown | — | — | Unknown | 139 distinct values, `0x00E7`-`0x0197` (231-407) |
| `0x2156` | 86 | unknown | — | — | Unknown | always `0x0000` |
| `0x2157` | 87 | unknown | — | — | Unknown | 2 distinct values, `0x0000`/`0xFE20` (0/65056) |
| `0x2158` | 88 | unknown | — | — | Unknown | always `0x0000` |
| `0x2159` | 89 | unknown | — | — | Unknown | always `0x06C0` (1728) |
| `0x215A` | 90 | unknown | — | — | Unknown | always `0x0168` (360) |
| `0x215B` | 91 | unknown | — | — | Unknown | always `0x0000` |
| `0x215C` | 92 | unknown, part of the shutdown lockout cluster | — | — | **Confirmed (structural)** | — (2 distinct values, `0x0000`/`0x0096` (0/150); same 6-7 minute post-`Standby` lockout behavior as `0x2121`/`0x212E`; not published) |
| `0x215D`-`0x2161` | 93-97 (5 registers) | unknown | — | — | Unknown | always `0x0000`, each individually |

## Read block `0x2200` (73 registers, `0x2200`-`0x2248`)

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x2200`-`0x2202` | 0-2 (3 registers) | unknown | — (no `ebusd` equivalent expected - this looks like device identity/config, not telemetry) | — | **Confirmed (structural)**, identity unknown | always `0x0001` (1), each individually |
| `0x2203` | 3 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0195` (405) |
| `0x2204` | 4 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0004` (4) |
| `0x2205` | 5 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0007` (7) |
| `0x2206`-`0x2207` | 6-7 (2 registers) | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0xFFFF` (65535), each individually |
| `0x2208` | 8 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0258` (600) |
| `0x2209` | 9 | unknown, not static | — (nothing tried so far lines up) | none tried beyond raw | **Lead** | correction to this block's earlier "entirely constant" characterization - varies substantially across the full `2026-09-06_112859` session (488 distinct values, `0x0000`-`0xBFD6`, 0-49110); no clean ramp or step-and-hold shape found yet |
| `0x220A` | 10 | unknown, not static | — (nothing tried so far lines up) | none tried beyond raw | **Lead** | same correction - 2506 distinct values, `0x0000`-`0xFFE0` (0-65504), erratic rather than smooth; low 3 bits always zero (a hint of real structure, not pure noise) |
| `0x220B` | 11 | unknown | — (no `ebusd` equivalent expected - this looks like device identity/config, not telemetry) | — | **Confirmed (structural)**, identity unknown | always `0x0001` (1) |
| `0x220C`-`0x2217` | 12-23 (12 registers) | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0000` (0), each individually |
| `0x2218` | 24 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x000D` (13) |
| `0x2219` | 25 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0010` (16) |
| `0x221A` | 26 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x012C` (300) |
| `0x221B` | 27 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0258` (600) |
| `0x221C` | 28 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0000` (0) |
| `0x221D` | 29 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x43F0` (17392) |
| `0x221E` | 30 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0000` (0) |
| `0x221F` | 31 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x4566` (17766) |
| `0x2220` | 32 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0001` (1) |
| `0x2221` | 33 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0000` (0) |
| `0x2222` | 34 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0001` (1) |
| `0x2223` | 35 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x42F0` (17136) |
| `0x2224` | 36 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0000` (0) |
| `0x2225` | 37 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0032` (50) |
| `0x2226`-`0x2246` | 38-70 (33 registers) | readback of write block `0x1200`'s payload | — | matches `0x1200` byte-for-byte, whatever that payload's own encoding is | **Confirmed (structural)** | same write-then-read-back relationship already established between `0x1000` and its matching read registers; includes the ASCII serial/model string bytes, since those live in `0x1200`'s payload |
| `0x2247` | 71 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0001` (1) |
| `0x2248` | 72 | unknown | — | — | **Confirmed (structural)**, identity unknown | always `0x0000` (0) |


---

Two more published sensors are not in these tables at all: `Thermal
Power Delivery` and `Heat Pump COP` are computed in ESPHome from
four of the register-backed sensors above (`flow_temp`, `return_temp`,
`building_circuit_flow`, `electric_power_consumption`), not decoded from
any register of their own.
