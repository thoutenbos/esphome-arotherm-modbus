# Register map

What is known about every register on the Modbus link between a Vaillant
aroTHERM 75/8.1 outdoor unit and its VWZ AI indoor interface: the bus, the
271 registers, and the sequences the machine runs through.

This file states the current findings only. Section 9 describes the evidence
behind them; earlier readings that were withdrawn are in the git history of
this file.

Contents:

1. [The bus](#1-the-bus)
2. [Encodings](#2-encodings)
3. [Status legend](#3-status-legend)
4. [Register tables](#4-register-tables)
5. [State machines and sequences](#5-state-machines-and-sequences)
6. [Formulas and identities](#6-formulas-and-identities)
7. [How this machine behaves](#7-how-this-machine-behaves)
8. [Open questions](#8-open-questions)
9. [Where these findings come from](#9-where-these-findings-come-from)

---

## 1. The bus

Standard Modbus RTU at 19,200 baud. The indoor interface is the master and the
outdoor unit is slave `01`. Every message is address, function code, body and
CRC-16 (polynomial `0xA001`, initial value `0xFFFF`).

Six blocks are exchanged in a fixed cycle of **1.2004 s**:

| phase | block | operation | registers | data rides in |
|---|---|---|---|---|
| +0.000 s | `0x2000` | read (`0x03`) | 34 | 73-byte response |
| +0.186 s | `0x1000` | write (`0x10`) | 26 | 61-byte request |
| +0.449 s | `0x2200` | read | 73 | 151-byte response |
| +0.584 s | `0x1200` | write | 25 | 59-byte request |
| +0.877 s | `0x2100` | read | 98 | 201-byte response |
| +0.976 s | `0x1100` | write | 15 | 39-byte request |

**Direction.** A `0x1xxx` register is written by the controller, so it is a
command, a setting, a value the controller computed, or an acknowledgement of
something the outdoor unit reported ([5.11](#511-who-decides-what)). A
`0x2xxx` register is read from the outdoor unit, so it is something the
outdoor unit measures or computes. Nothing sensed indoors (cylinder
temperature, room temperature) appears on the read side.

**Attributing a read response.** A response does not carry its own address.
It belongs to the read request seen just before it. Only when no request was
seen (after boot, or a lost request) does the firmware fall back to matching
the register count.

**Other units.** An aroTHERM plus 7 kW with VWZ AI reads 35 registers from
`0x2000`. An aroTHERM Split plus reads 32 from `0x2000` and writes 25, 14 and
24 registers to the three write blocks; on that unit the circuit flow is only
in `0x100A`.

**Block phase matters when comparing registers.** `0x2100` is read 0.877 s
after `0x2000` and 0.323 s before the next one. Two registers in different
blocks that change "one poll apart" may have changed together.

## 2. Encodings

| name | meaning |
|---|---|
| D2C, `/16` | signed 16-bit, `value = raw / 16`. Every temperature and temperature difference |
| `/10` | signed 16-bit, `raw / 10`. Pressures (bar), compressor speeds (rps), percentages |
| `/50` | `raw / 50`. Voltages; the registers only ever hold multiples of 50, so 1 V is the resolution |
| `/1000` | `raw / 1000`. Currents in A; the registers hold multiples of 100, so 0.1 A is the resolution |
| raw | signed 16-bit integer |
| unsigned raw | unsigned 16-bit integer. Timers and powers, which run past 32,767 |
| f32 | big-endian IEEE-754 single spanning two registers, high word first |
| ASCII | two characters per register, high byte first, padded with `<` or `X` |

## 3. Status legend

- **Confirmed** - matched an independent reference (an `ebusd` field, a
  certified meter, an owner-supplied fact) or an exact identity against other
  confirmed registers.
- **Structural** - an exact fact about behaviour (an echo, a flag, a constant
  tied to a measured timer) without a physical quantity of its own.
- **Lead** - a reading that fits, but that nothing has confirmed.
- **Unknown** - moves, or is constant, with no identified meaning.

A register that is only a Lead or Unknown is not published as a sensor in
this release, even where it moves - with one exception. `Fault Code`
(`0x2100`) is published although its row reads Lead: the one code seen,
`9998`, is F.9998 on the Vaillant display and `0xFFFF` is "none", so what the
sensor reports is the code the machine is showing. The row stays a Lead only
because no second code has appeared to test the encoding.

## 4. Register tables

Registers not listed individually inside a range have only ever held the
value shown. "Echo" means an exact or near-exact copy of the named register,
not published as a sensor.

### 4.1 Write block `0x1000` (26 registers)

Written by the controller every cycle. A mixed payload: one command, several
values echoed back to the outdoor unit, and values the controller computed.

| register | identity | scale | status | sensor |
|---|---|---|---|---|
| `0x1000` | **demand mode**: `0` idle, `1` space heating, `2` hot water, `4` installer test program ([5.13](#513-settings-and-test-programs)), `5` defrost, `6` re-initialise (written for 5-10 s after the controller regains an outdoor unit it had lost, [5.12](#512-power-up-and-loss-of-communication)). The controller originates 0/1/2; for `5` it follows the outdoor unit's `0x2000` by 0.19 s | raw | Confirmed | `Demand Mode` |
| `0x1001` | constant `0` | | Unknown | |
| `0x1002` | **compressor speed command.** While the controller modulates, the outdoor unit's target `0x2122` takes this value on its next read. `0` in the pre-run and through a defrost, when the outdoor unit runs its own schedule ([5.11](#511-who-decides-what)) | `/10`, rps | Structural | `Compressor Speed Command` |
| `0x1003` | building circuit pump command | `/10`, % | Confirmed | `Building Pump Power` |
| `0x1004` | **episode-active flag**, set by the controller. `Run Phase` follows it 1-6 polls later | raw | Structural | `Episode Active` |
| `0x1005` | condenser outlet temperature, echo of `0x200A`. `0x8000` once the outdoor unit has not answered for about 5 s | D2C | Structural | |
| `0x1006` | **refrigerant temperature at the gas side of the plate heat exchanger** (condenser inlet) on a unit that has an indoor unit; constant `0x8000`, the "no value" marker, on this monoblock. A Split plus reads 22.7-75.2 °C here, above its own condensing temperature as superheated discharge gas must be, and uses it for the superheat while the circuit is reversed ([9](#9-where-these-findings-come-from)). Not published here: `0x8000` publishes nothing | D2C, °C | **Confirmed** (on a Split plus) | `Condensor Inlet Temp` |
| `0x1007` | flow temperature, echo of `0x200C` | D2C | Structural | |
| `0x1008` | return temperature, echo of `0x200D` | D2C | Structural | |
| `0x1009` | outside temperature, as the controller uses it (damped). `0x8000` in the controller's first write after it boots | D2C, °C | Confirmed | `Outside Temp` |
| `0x100A` | building circuit flow, exact echo of `0x2014`. On the Split plus the only flow reading | raw, l/h | Confirmed | `Building Circuit Flow` (`building_circuit_flow_split`, Split plus) |
| `0x100B` | **test program step**, used with `Demand Mode` 4: `4` air venting, `6` forced defrost. The outdoor unit echoes it in `0x2005` | raw | Structural | |
| `0x100C`-`0x1011` | constant `0` | | Unknown | |
| `0x1012` | **outdoor unit is in hot-water mode**: `1` exactly when `0x2000 == 2`. Its edges are the moment the diverter valve moves | raw, 0/1 | Structural | `Hot Water Mode Active` |
| `0x1013` | constant `0` | | Unknown | |
| `0x1014` | **heat output**, computed by the controller from flow and the flow/return pair, and consumed by the outdoor unit's defrost logic ([6.1](#61-heat-output-0x1014)) | unsigned raw, W | Confirmed | `Heat Output` |
| `0x1015`-`0x1017` | constant `0xFFFF` | | Unknown | |
| `0x1018` | **re-initialise flag**: `1` together with `Demand Mode` 6, otherwise `0` | raw, 0/1 | Structural | `Re-initialise Flag` |
| `0x1019` | **requested flow temperature** ([6.8](#68-requested-flow-temperature-0x1019)) | D2C, °C | Confirmed | `Requested Flow Temp` |

### 4.2 Write block `0x1100` (15 registers)

Static configuration.

| register | identity | scale | status | sensor |
|---|---|---|---|---|
| `0x1100` | constant `0` | | Unknown | |
| `0x1101` | constant `300` | | Unknown | |
| `0x1102` | constant `18000`. 180.00 on a `/100` scale, the length of the post-stop countdown `0x211C`; a coincidence of value | | Lead | |
| `0x1103` | constant `16` | | Unknown | |
| `0x1104` | constant `0x8001` | | Unknown | |
| `0x1105`-`0x1108` | constant `0` | | Unknown | |
| `0x1109` | **flow/return calibration** (Vaillant D.003). The machine sets it itself; it has been seen to step from `0` to `-1`, `-4`, `-5` and `-3` over a few weeks. The controller re-measures it while the pump circulates with no heat input: the last change came at the end of a pump run in the venting program, with the return reading 3 counts above the flow. One count is 1/16 K, so `-5` is -0.3125 K | D2C, K | Confirmed | `Flow-Return Calibration` |
| `0x110A` | constant `0` | | Unknown | |
| `0x110B`-`0x110C` | constant `1` | | Unknown | |
| `0x110D` | **silent mode active**: `1` while the controller's noise-reduction program runs. The outdoor unit drops `Compressor Speed Max` to 84.0 rps in the same poll | raw, 0/1 | Structural | `Silent Mode Active` |
| `0x110E` | constant `0` | | Unknown | |

### 4.3 Write block `0x1200` (25 registers)

Identity, written by the controller.

| register | identity | scale | status | sensor |
|---|---|---|---|---|
| `0x1200`-`0x1201` | constant `0xFFFF` | | Unknown | |
| `0x1202` | constant `10` | | Unknown | |
| `0x1203` | first character of the serial number, in the low byte | ASCII | Confirmed | `Serial Number` |
| `0x1204`-`0x1214` | characters 2-28 of the **serial number**, then `<` padding. Confirmed against the unit's type plate | ASCII | Confirmed | `Serial Number` |
| `0x1215`-`0x1218` | constants `1`, `0`, `0`, `0xFFFF` | | Unknown | |

### 4.4 Read block `0x2000` (34 registers)

| register | identity | scale | status | sensor |
|---|---|---|---|---|
| `0x2000` | **mode the outdoor unit is actually in**, same codes as `0x1000`. Follows the request by 1.2 s from idle and by 91.2 s when changing between heating and hot water with the compressor running. Originates `5` (defrost). `4` during an installer test program | raw | Structural | `Outdoor Mode` |
| `0x2001` | **requested building circuit flow** ([6.9](#69-circuit-flow-request-0x2001)) | raw, l/h | Confirmed | `Building Circuit Flow Target` |
| `0x2002` | **upper bound of the permitted compressor speed** ([6.6](#66-compressor-speed-window-0x2002-0x2003)) | `/10`, rps | Confirmed | `Compressor Speed Max` |
| `0x2003` | **lower bound of the permitted compressor speed**, the modulation floor | `/10`, rps | Confirmed | `Compressor Speed Min` |
| `0x2004` | `1` for two polls at the end of the forced-defrost test, otherwise `0`. Possibly "test step complete"; seen once | raw | Lead | |
| `0x2005` | **test program step**, echo of `0x100B` one poll later | raw | Structural | `Test Program` |
| `0x2006` | **defrost sequence in progress**: `1` exactly while `0x2144` is in `{5,6,7,8,9,11}` | raw, 0/1 | Confirmed | `Defrost Sequence` |
| `0x2007` | compressor inlet temperature | D2C, °C | Confirmed | `Compressor Inlet Temp` |
| `0x2008` | compressor outlet temperature. A pipe sensor: it peaks near 54 °C on a 60 °C charge, so it is not the discharge gas temperature | D2C, °C | Confirmed | `Compressor Outlet Temp` |
| `0x2009` | expansion valve outlet temperature | D2C, °C | Confirmed | `EEV Outlet Temp` |
| `0x200A` | condenser outlet temperature | D2C, °C | Confirmed | `Condensor Outlet Temp` |
| `0x200B` | air inlet temperature | D2C, °C | Confirmed | `Air Inlet Temp` |
| `0x200C` | flow temperature (calibrated) | D2C, °C | Confirmed | `Flow Temp` |
| `0x200D` | return temperature (calibrated) | D2C, °C | Confirmed | `Return Temp` |
| `0x200E` | refrigerant low pressure | `/10`, bar | Confirmed | `Low Pressure` |
| `0x200F` | refrigerant high pressure | `/10`, bar | Confirmed | `High Pressure` |
| `0x2010` | compressor speed, measured | `/10`, rps | Confirmed | `Compressor Speed` |
| `0x2011` | fan speed, measured | raw, rpm | Confirmed | `Fan1 Speed` |
| `0x2012` | constant `0` | | Unknown | |
| `0x2013` | water pressure | `/10`, bar | Confirmed | `Water Pressure` |
| `0x2014` | **building circuit flow**, the flow sensor. Within 2% of a MID-certified heat meter in every mode | raw, l/h | Confirmed | `Building Circuit Flow` |
| `0x2015` | **run phase** ([5.9](#59-run-phase-0x2015)) | raw | Confirmed | `Run Phase` |
| `0x2016`-`0x2017` | constant `0` | | Unknown | |
| `0x2018` | electric power, **echo of `0x201D`** - not of `0x211B` | raw, W | Structural | `Compressor Power` |
| `0x2019` | fan speed, echo of `0x2011` | raw, rpm | Structural | |
| `0x201A` | constant `0` | | Unknown | |
| `0x201B` | **mains voltage**. `0` while the drive sleeps (idle beyond the 480 s lockout) | `/50`, V | Confirmed | `Mains Voltage` |
| `0x201C` | **mains current**, rounded up to the next 0.1 A ([6.3](#63-mains-current-0x201c)) | `/1000`, A | Confirmed | `Mains Current` (`active_current`) |
| `0x201D` | **the drive's own mains power**, copied to `0x2018` in the same read. Not `0x211B`, which adds the fan and standby load: the two agree in 0.0099% of samples while `0x2018` equals `0x201D` in **99.615%** of 344,398. Exact in four of the seven captures that carry the block; the residue is 8, 392 and 926 frames differing by only -40 to +6 W, about a third of them matching the neighbouring sample - one-poll transients while the power ramps, with no block skew available to blame since both ride the same `0x2000` response. The 37 W median gap to `ebusd`'s consumption field is the fan and standby load this figure excludes | raw, W | Structural | |
| `0x201E` | compressor motor voltage. **2.33 V per rps at every speed** from 20 to 90 rps (48 V at 20, 70 V at 30, 140 V at 60), never above the mains voltage and reaching it at top speed. Each poll carries about ±4 V of noise that is the same size at every speed and follows nothing else on the bus, so it is a raw instantaneous sample; average it before reading anything into it. The scale is not ten times too high: on `/500` the motor's apparent power would be a tenth of the electrical power it is drawing | `/50`, V | Lead (strong) | |
| `0x201F` | compressor motor current. Zero exactly when the compressor is stopped. A quantity proportional to torque fits equally well | `/1000`, A | Lead (strong) | |
| `0x2020` | a second flow-like figure. Zero exactly when the pump is stopped, within a few percent of `0x2014`, with a gap that follows the pump's operating point ([6.10](#610-the-second-flow-figure-0x2020)) | raw | Unknown | |
| `0x2021` | `0x201C + 1600` | raw | Structural | |

### 4.5 Read block `0x2100` (98 registers)

| register | identity | scale | status | sensor |
|---|---|---|---|---|
| `0x2100` | **fault code**, as shown on the Vaillant display: `9998` is F.9998, loss of communication. `0xFFFF` when there is none. Only this one code has been seen | unsigned raw | Lead (strong) | `Fault Code` |
| `0x2101`-`0x2118` | constant `0xFFFF`. Most likely further fault slots | | Lead | |
| `0x2119` | constant `0` | | Unknown | |
| `0x211A` | constant `1` | | Unknown | |
| `0x211B` | **electric power consumption**. Reads about 4.7% below a separate meter at normal load. It does not include the circulation pump: it reads 6 W with the pump at 100% and nothing else running | raw, W | Confirmed | `Electric Power Consumption` |
| `0x211C` | **hold-off countdown**: 180 s from every compressor stop, 485 s from the moment a lost controller is heard again. The fault code clears when it reaches 0 ([5.4](#54-stop-sequence), [5.12](#512-power-up-and-loss-of-communication)) | raw, s | Structural | `Hold-off Countdown` |
| `0x211D` | constant `1`, except in the outdoor unit's last response before it lost power, where it read `0`. Possibly a supply-present flag; seen once | raw | Lead | |
| `0x211E`-`0x211F` | constant `1` | | Unknown | |
| `0x2120` | expansion valve position, absolute | raw, steps | Confirmed | `EEV Position` |
| `0x2121` | lockout flag: `0` from the start hand-off until 480 s after the compressor stops, `1` otherwise | raw | Structural | `Lockout Flag` |
| `0x2122` | **compressor speed target** the drive is working to: the controller's command `0x1002` while modulating, the outdoor unit's own schedule at a start, a stop and in a defrost | `/10`, rps | Confirmed | `Compressor Speed Target` |
| `0x2123` | **fan speed target**. Leads the measured speed by 1-2 polls and sits just above it | raw, rpm | Structural | `Fan Speed Target` |
| `0x2124` | constant `0` | | Unknown | |
| `0x2125` | constant `1` | | Unknown | |
| `0x2126` | **condensing temperature**. `condensing - condenser outlet` gives the subcooling to within 1 count in 98.4% of running polls ([6.4](#64-refrigerant-cycle-identities)) | D2C, °C | Confirmed | `Condensing Temp` |
| `0x2127` | constant `0` | | Unknown | |
| `0x2128` | **evaporating temperature**. `compressor inlet - evaporating` approximates the superheat - centred, but only 77% within 1 count ([6.4](#64-refrigerant-cycle-identities)). Keeps reporting its own quantity while the circuit is reversed, where a Split plus instead sets it equal to `0x200A`: here it equals that register in 6 of 1,330 reversed polls, and no other register matches it in even half of them | D2C, °C | Confirmed | `Evaporating Temp` |
| `0x2129` | **subcooling target**, not a looser copy of `0x212A`. A Split plus reports a plain setpoint here - 4.0 K heating, 5.0 K at a hot-water start, 1.0 K in state 5 - and on this machine it is clamped below at exactly **64 = 4.0 K**, never taking a value between 1 and 63: in the 41,855 running polls where the measured subcooling is under 4.0 K it reads only 64-68. It is not a pure setpoint here, taking 23-49 distinct values per capture, so the reading is the floor rather than the whole quantity. The Split plus identity `0x2129 == 0x215F` does **not** port: `0x215F` is constant 0 in all fourteen captures | D2C, K | Lead | |
| `0x212A` | **subcooling** | D2C, K | Confirmed | `Subcooling` |
| `0x212B` | constant `0` | | Unknown | |
| `0x212C` | **superheat** | D2C, K | Confirmed | `Superheat` |
| `0x212D` | expansion valve position, percent | `/10`, % | Confirmed | `EEV Position Status` |
| `0x212E` | lockout flag, the inverse of `0x2121` | raw | Structural | |
| `0x212F`-`0x2130` | constant `0` here. On a Split plus `0x212F` **switches a heater of about 180 W**, so the output exists in the protocol and is unused on this machine ([9](#9-where-these-findings-come-from)) | | Unknown | |
| `0x2131` | **refrigerant circuit reversed**: `1` exactly while `0x2144` is in `{6,7,8}` | raw, 0/1 | Confirmed | `Defrost Active` |
| `0x2132`-`0x2136` | constant `0` | | Unknown | |
| `0x2137` | **de-rated temperature ceiling** ([6.5](#65-de-rated-temperature-ceiling-0x2137)). Which temperature it caps is a Lead | D2C, °C | Confirmed (curve) | `Derated Temp Ceiling` |
| `0x2138` | constant `1200`: the 120.0 rps at which `0x2002` clamps | `/10`, rps | Lead | |
| `0x2139` | constant `200`: **the stored modulation floor**, which `0x2003` is never allowed below. `0x2003 >= 0x2139` in **174,131 samples with 0 violations**, and `0x2003` sits exactly on it in 41-98% of frames in the four recent captures; the two older ones floor at 251 and 286, above it. A Split plus carries **300** here and floors its own `0x2003` at exactly 300 - the same relation on a machine whose minimum is 30.0 rps where this one's is 20.0 ([9](#9-where-these-findings-come-from)) | `/10`, rps | Confirmed | |
| `0x213A` | defrost-sequence flag, identical to `0x2006` | raw, 0/1 | Structural | |
| `0x213B`-`0x213E` | constant `0` here. On a Split plus `0x213B` is set in exactly the cycles `0x212F` is, and that data cannot tell the two apart | | Unknown | |
| `0x213F`:`0x2140` | **compressor slew limit**: how fast the speed target may move. `2.0` or `0.2` ([6.7](#67-compressor-slew-limit-0x213f)) | f32, rps/s | Confirmed | `Compressor Slew Limit` |
| `0x2141` | expansion valve position, echo of `0x2120` | raw | Structural | |
| `0x2142` | **expansion valve lower limit**. Constant `55` here, so this machine alone cannot show it is one; a Split plus moves it - 70 while running, about 225 falling back after a defrost, and 0 while the circuit is reversed - which is a valve floor and nothing else ([9](#9-where-these-findings-come-from)) | raw, steps | Lead | |
| `0x2143` | constant `525`: the valve's end stop, reached before every defrost | raw, steps | Lead | |
| `0x2144` | **demand and defrost state machine** ([5.1](#51-the-demand-state-machine-0x2144)) | raw | Confirmed | `Demand State` |
| `0x2145` | **compressor speed stable time**: seconds since the speed last left a ±3.0% band. Consumed by the frost model ([5.7](#57-the-frost-model-and-the-defrost-decision)) | unsigned raw, s | Confirmed | `Compressor Speed Stable Time` |
| `0x2146` | **fan target stable time**: seconds since the fan speed target last left a ±3.0% band. Runs whenever the fan target is set | unsigned raw, s | Confirmed | `Fan Target Stable Time` |
| `0x2147` | **defrost reference heat output**: the clean-coil reference ([5.7](#57-the-frost-model-and-the-defrost-decision)) | unsigned raw, W | Confirmed | `Defrost Reference Heat Output` |
| `0x2148` | **defrost reference attempt**: which attempt at taking that reference this is. `0`-`4` seen | raw, count | Confirmed | `Defrost Reference Attempt` |
| `0x2149` | a clamped curve in evaporating temperature, top value `176`. Non-zero exactly when the previous poll's evaporating temperature is at or below -0.50 °C in state `3`. What uses it is unknown | raw | Unknown (gate Structural) | |
| `0x214A` | constant `0` | | Unknown | |
| `0x214B` | **frost-model speed term**: about 11.3-12.0 x the raw compressor speed, sampled and held. Rescales the reference `0x2147`. Non-zero only while the frost model is live | unsigned raw | Structural (quantity a Lead) | |
| `0x214C` | **time since the last defrost** ended. `0` during a defrost, before the season's first, and again from 18.2 h after one: it reaches 65,535, drops to `0` and stays | unsigned raw, s | Confirmed | `Time Since Defrost` |
| `0x214D` | constant `0` | | Unknown | |
| `0x214E` | **compressor ramp state**, a bitfield ([5.8](#58-compressor-ramp-state-0x214e)) | bits | Structural | `Compressor Ramp State` (text) |
| `0x214F` | drive power-stage temperature. Sits 4.5 K above air inlet at part load and 15 K above at 60 rps; non-zero exactly while `0x215C` is | D2C, °C | Lead | |
| `0x2150`-`0x2152` | constant `0` | | Unknown | |
| `0x2153` | drive ambient temperature. Sits 3.2-4.8 K above air inlet in every capture; same gate | D2C, °C | Lead | |
| `0x2154` | constant `0` | | Unknown | |
| `0x2155` | evaporating temperature one poll late on another scale: `0.6343 x 0x2128 + 175.6` | raw | Structural | |
| `0x2156` | a linear curve in air inlet temperature, on the same gate as `0x2149`; the two are never non-zero apart | raw | Unknown (gate Structural) | |
| `0x2157` | `-480` while the fan target is set, `-288` while the circuit is reversed, `0` otherwise. On D2C these read -30.0 and -18.0 °C | raw | Unknown (gate Structural) | |
| `0x2158` | a pulse about 0.3 s wide at the head of a defrost, caught once | raw, 0/1 | Lead | |
| `0x2159` | constant `1728` | | Unknown | |
| `0x215A` | constant `360` | | Unknown | |
| `0x215B` | constant `0` | | Unknown | |
| `0x215C` | **demand window**: `150` from the start hand-off until 482 s after the compressor stops, else `0`. The gate for `0x214F` and `0x2153` | raw | Structural | `Demand Window` |
| `0x215D`-`0x215F` | constant `0` | | Unknown | |
| `0x2160`:`0x2161` | **defrost capacity loss**: how far the heat output is below the reference, in percent ([6.2](#62-defrost-capacity-loss-0x2160)) | f32, % | Confirmed | `Defrost Capacity Loss` |

### 4.6 Read block `0x2200` (73 registers)

Identity and stored parameters. Only `0x2209`:`0x220A` moves.

| register | identity | scale | status | sensor |
|---|---|---|---|---|
| `0x2200`-`0x2202` | constant `1` | | Unknown | |
| `0x2203`-`0x2205` | **firmware version**, e.g. `405`, `4`, `7` for 405.4.7, confirmed against the unit's display | raw | Confirmed | `Firmware Version` (text) |
| `0x2206`-`0x2207` | constant `0xFFFF` | | Unknown | |
| `0x2208` | constant `600`. One of two 600 s constants (with `0x221B`); the frost gate and the defrost re-arm interval are both 600 s | raw, s | Lead | |
| `0x2209`:`0x220A` | **flow minus return, uncalibrated**. Within 0.012 K of the certified heat meter | f32, K | Confirmed | `Delta T` |
| `0x220B` | constant `1` | | Unknown | |
| `0x220C`-`0x2217` | constant `0` | | Unknown | |
| `0x2218` | constant `13` | | Unknown | |
| `0x2219` | constant `16` | | Unknown | |
| `0x221A` | constant `300`: the frost model's 300 s blanking window | raw, s | Lead | |
| `0x221B` | constant `600`; see `0x2208` | raw, s | Lead | |
| `0x221C` | constant `0` | | Unknown | |
| `0x221D`:`0x221E` | **post-stop lockout**, `480.0` | f32, s | Structural | `Lockout Duration` |
| `0x221F` | constant `17766` | | Unknown | |
| `0x2220` | constant `1` | | Unknown | |
| `0x2221` | constant `0` | | Unknown | |
| `0x2222` | constant `1` | | Unknown | |
| `0x2223`:`0x2224` | stored constant `120.0` | f32 | Structural | |
| `0x2225` | constant `50` | | Unknown | |
| `0x2226`-`0x2236` | readback of the serial number, characters 2-28 | ASCII | Confirmed | |
| `0x2237`-`0x2246` | a second 30-character identity string, padded with `X`, not present in block `0x1200`. Which part it names is unknown | ASCII | Structural | |
| `0x2247` | constant `1` | | Unknown | |
| `0x2248` | constant `0` | | Unknown | |

---

## 5. State machines and sequences

Times are in seconds. A poll is 1.2 s, so every timing carries that
granularity. Counts such as "10 of 10" are over the captures described in
[section 9](#9-where-these-findings-come-from).

### 5.1 The demand state machine (`0x2144`)

`Demand State`. One machine covers demand and defrost.

| state | meaning | how long |
|---|---|---|
| `0` | idle | |
| `1` | pre-run: pump and fan running, compressor not yet commanded | 60 s |
| `3` | running | |
| `4` | fan run-on after the compressor has stopped | 64 s or 604 s ([5.4](#54-stop-sequence)) |
| `5` | defrost: prepare | 44-46 s |
| `6` | defrost: valve reverses | 10-11 s |
| `7` | defrost: melt | 236-412 s |
| `8` | defrost: valve returns | 10 s |
| `9` | defrost: settle | 5-6 s |
| `11` | defrost: recovery | 79-80 s |

Transitions: `0 -> 1 -> 3 -> 4 -> 0` for a demand, and
`3 -> 5 -> 6 -> 7 -> 8 -> 9 -> 11 -> 3` for a defrost. State `10` has never
been seen. A change between heating and hot water happens inside state `3`.

Other registers are projections of this machine:

| register | equals |
|---|---|
| `0x2006`, `0x213A`, `0x2000 == 5`, `0x1000 == 5` | state in `{5,6,7,8,9,11}` |
| `0x2131` | state in `{6,7,8}` |

### 5.2 Three levels of "on"

Three signals describe activity at different levels, and they are not
interchangeable.

| signal | what it follows | typical span |
|---|---|---|
| the house circuit's own heat request (controller side, not on this bus) | the house wants heat | hours to days |
| `Run Phase` (`0x2015`) | the heat pump's heating episode | spans many demand cycles |
| `Demand Mode` (`0x1000`) | the outdoor unit is asked to run now | tens of minutes to hours |

Inside one long heating request the demand cycles on and off (eight times in
18 hours on a cold day) while the run phase stays at `1`. A run phase of `1`
therefore does not mean the compressor is running. Use `Demand Mode` or
`Compressor Speed` for that.

### 5.3 Start sequence

Offsets from the poll in which `Demand Mode` leaves `0`. Identical at 10 of 10
starts, for heating and hot water alike.

| offset | event |
|---|---|
| 0 | `Demand Mode` 0 -> 1 or 2. `Requested Flow Temp` takes its demand value. The pump is commanded |
| +1.2 | the outdoor unit accepts: `0x2000` follows, `Building Circuit Flow Target` 0 -> 1205, `Fan Speed Target` 0 -> 220, `Run Phase` -> 1 |
| +2.4 | `Demand State` 0 -> 1, `0x2157` -> -480, `Fan Target Stable Time` starts |
| +8 to +10 | the fan turns |
| +61.2 | **hand-off**: `Compressor Speed Target` 0 -> 50.0 rps, the speed window opens at [50, 60] rps, `0x2121` 1 -> 0. One restart, four minutes after a stop, opened at 40.0 rps and [40, 60] instead |
| +62.4 | `Demand State` 1 -> 3; the drive wakes (`Mains Voltage` leaves 0) |
| +63.6 | `Demand Window` 0 -> 150; the drive temperatures start reading |
| +67 to +70 | the compressor turns. `Compressor Ramp State` goes `Starting` -> `Ramping up` |
| +89 to +91 | the compressor reaches 50 rps; `Compressor Ramp State` -> `At speed` |
| +80 to +91 | `Heat Output` leaves 0, once warm water reaches the flow and return sensors |
| +241 | **start window ends**, 180 s after the hand-off: `Compressor Slew Limit` 2.0 -> 0.2, the speed window is released to its weather-dependent bounds, and the controller modulates |

So a demand does not start the compressor. It starts a 60 s pre-run of pump
and fan, then three minutes at a fixed 50-60 rps, and only then free
modulation. The expansion valve rests at 250 steps while idle and through the
pre-run.


### 5.4 Stop sequence

Offsets from the poll in which the compressor speed reaches 0.

| offset | event |
|---|---|
| -2 to -23 | `Demand Mode` -> 0. One poll later `Compressor Speed Target` -> 0 and `Compressor Slew Limit` -> 2.0. The compressor coasts down: 2 s from 20-30 rps, about 20 s from 60 rps. `Compressor Ramp State` shows `Ramping down to stop` |
| 0 | compressor at 0. `Demand State` 3 -> 4, the speed window closes, `Compressor Ramp State` -> `Off`, **`Hold-off Countdown` starts at 179** |
| +25 to +46 | refrigerant high and low pressure have equalised |
| +64 **or** +604 | **end of the fan run-on**: `Fan Speed Target` -> 0, `0x2000` -> 0, `Building Circuit Flow Target` -> 0, `0x2157` -> 0; one poll later `Demand State` 4 -> 0 and the fan stops |
| +180 | `Hold-off Countdown` reaches 0. Nothing else on the bus changes |
| +480 | **the drive sleeps** (`Mains Voltage` and the power echo `0x2018` -> 0), `0x2121` -> 1, `0x212E` -> 0 |
| +482 | `Demand Window` -> 0; the drive temperatures stop reading |

**Fan run-on length depends on the air temperature.** 64 s at an air inlet of
9.6 °C or above (6 of 6 stops), 604 s at 6.1 °C or below (4 of 4). The
threshold lies between the two. `Demand State` 4 lasts exactly as long.

**The hold-off countdown** runs for 180 s after every compressor stop, and
**the outdoor unit enforces it.** In the one capture where a demand came back
early, the controller raised `Demand Mode` again 24 s after the stop, with 156 s
still on the countdown. The outdoor unit left its own mode word at 0 and
accepted the demand in the very poll the countdown reached 0; the pre-run
followed and the compressor turned 242 s after it had stopped. So 180 s is the
outdoor unit's minimum off-time, and **the 480 s is not a restart lock**: it is
only how long the drive stays awake after a stop. The controller did not wait
for either.

**The pump.** In milder weather the pump stops with the fan run-on. In
colder weather it keeps circulating between demands at a fixed 70-72%
command (about 990 l/h), with no flow target.

When the heating episode itself ends, `Run Phase` goes 1 -> 6 at the end of
the fan run-on and unwinds as in [5.9](#59-run-phase-0x2015).


### 5.5 Changing between heating and hot water

The compressor keeps running. Offsets from the poll in which `Demand Mode`
changes.

**Heating to hot water** (2 of 2):

| offset | event |
|---|---|
| 0 | `Demand Mode` 1 -> 2, `Requested Flow Temp` -> its hot-water value. `Compressor Slew Limit` -> 2.0 and the speed window is fixed at [30, 50] rps; the speed is driven up towards 50 |
| +91.2 | **the diverter valve moves**: `0x2000` 1 -> 2 and `Hot Water Mode Active` 0 -> 1 in the same poll, the circuit flow jumps (1150 -> 1440 l/h), `Fan Speed Target` -> 650 |
| +110 | the window is released and `Compressor Slew Limit` -> 0.2. The pump is regulated down until the flow sits on its 1205 l/h target |

**Hot water to heating** (2 of 2):

| offset | event |
|---|---|
| 0 | `Demand Mode` 2 -> 1, `Requested Flow Temp` -> its heating value. `Compressor Slew Limit` -> 2.0, the window is fixed at [30, 50] rps, and the speed is wound down from 60 rps (`Compressor Ramp State` shows `Ramping down`) |
| +91.2 | **the diverter valve moves**: `0x2000` 2 -> 1 and `Hot Water Mode Active` 1 -> 0, `Fan Speed Target` drops to its heating value, the flow dips (1205 -> 950 l/h) and recovers within about 15 s. `Building Circuit Flow Target` starts easing from 1205 towards 1098 |
| +110 | the window is released and `Compressor Slew Limit` -> 0.2 |
| +125 | 34 s after the valve moved, the return temperature starts to collapse as the last cylinder-loop water leaves the heat exchanger, and the flow target snaps back to 1205 |

A hot-water charge that ends with no heating demand behind it stops instead,
by the stop sequence, and `Hot Water Mode Active` clears 84-86 s after the
demand.


### 5.6 Defrost sequence

The outdoor unit decides ([5.7](#57-the-frost-model-and-the-defrost-decision))
and the controller acknowledges: `0x2000` goes to `5` and the controller's
`Demand Mode` follows 0.19 s later. Five defrosts were captured, four in one
night and a fifth five days later, and all five ran identically except for the
length of the melt.

| `Demand State` | length | what happens |
|---|---|---|
| `5` prepare | 44-46 s | `Defrost Sequence` sets. The frost model is zeroed in the first poll. The compressor is wound back to 28.0 rps and the expansion valve driven to its 525-step stop. `Compressor Slew Limit` -> 2.0 and the speed window closes: the defrost runs its own speed schedule |
| `6` reverse | 10-11 s | `Defrost Active` sets and the four-way valve reverses: within two polls the high-low pressure spread collapses from 5.3-5.5 bar to 0.2-1.1 bar. The fan stops 49-50 s after the sequence began. `0x2157` reads -288 |
| `7` melt | 236-412 s | the outdoor coil is the condenser. The compressor is stepped up in stages, 40 -> 50 -> 55 -> 65 -> 70 -> 80 rps, each a `Ramping up`. Heat is taken from the house: the flow temperature falls |
| `8` return | 10 s | the compressor is wound down (`Ramping down`), the fan target returns and the valve switches back |
| `9` settle | 5-6 s | `Defrost Active` clears at the bottom of the ramp, near 50 rps |
| `11` recovery | 79-80 s | normal circuit, compressor at 60.0 rps, fan running. Ends with the flow back at 26-27 °C |
| `3` | | `Defrost Sequence` clears, 85-87 s after the fan restarted. `Time Since Defrost` starts counting from 1. `Compressor Slew Limit` -> 0.2 |

Everything but the melt is fixed: 135-139 s of overhead per defrost.
`Defrost Sequence` brackets the whole event and is the signal to use for "heat
is being taken out of the house". `Defrost Active` brackets only the reversed
circuit.

### 5.7 The frost model and the defrost decision

The machine defrosts on demand, by comparing the heat it delivers with what it
delivered when the coil was clean. All of it is visible on the bus.

**Stage 1: the gate.** The frost model goes live once the evaporating
temperature has been continuously at or below -0.50 °C, with the compressor
running and no defrost in progress, for **600 s**. The frost-model speed term
`0x214B` becomes non-zero at that moment and returns to zero the moment the
coil warms through the gate. Two captures show near misses of 571 and 592 s,
and the model never went live in them.

**Stage 2: the re-arm interval.** `Defrost Reference Attempt` (`0x2148`) goes
`0 -> 1` when the model is live **and** `Time Since Defrost` has reached 600.
That is a minimum of 600 s between the end of one defrost and the start of
measuring for the next. Whenever `Time Since Defrost` reads 0 - before the
season's first defrost, and again once it has rolled over 18.2 h after one -
the counter stays at `0` and the next stages proceed without it. Both cases
have been captured, each ending in a normal defrost.

**Stage 3: taking the reference.** The reference needs a steady compressor.

1. When `Compressor Speed Stable Time` reaches **60 s**, the speed term
   `0x214B` is sampled.
2. If the speed then stays inside its ±3% band for a further **180 s**, the
   reference arms: `Defrost Reference Heat Output` (`0x2147`) takes the **mean
   of `Heat Output` over those 180 s** (to the watt at five armings, within
   2 W at a sixth).
3. If the speed leaves the band first, `Defrost Reference Attempt` goes up by
   one. The next sample waits for **150 s** of stable speed, again followed by
   the 180 s.

`Defrost Reference Attempt` therefore records how many tries it took. `1`
means the first try; values up to `4` have been seen. A high count means the
reference was taken late, with some frost already on the coil.

**Stage 4: tracking.** Once armed, `Defrost Capacity Loss`
(`0x2160`:`0x2161`) is live:

    capacity loss = 100 x (1 - heat output / reference)      [%]

Negative values mean the output is above the reference and are normal. When
the compressor speed changes, the capacity loss is frozen while the heat
output settles at the new speed, and then the reference is rescaled in
proportion to the speed term. The freeze lasts **300 s, and longer if the
speed is not yet steady**: the re-latch comes 300 s after the freeze began if
`Compressor Speed Stable Time` is at 60 s or more by then, and otherwise at
the moment it reaches 60 s (14 of 14 re-latches in two captures; the four
delayed ones took 322-375 s).

**Stage 5: the trigger.** A defrost is commanded once `Defrost Capacity Loss`
has been at or above **15.0** continuously for **60 s**. Eleven defrosts are on
record and all eleven end a 59-61 s dwell; none of the 19 other excursions
above 15.0 lasted beyond 29 s. The eleventh was
captured after the rule was written and fits it: one excursion above 15.0 in
the capture, 58.8 s between its first and last poll, then the command.

In all five captured defrosts the dwell began at a re-latch: the capacity loss
had been frozen below 15, the reference stepped up with the compressor speed,
and the unfrozen value was above 15 from its first poll. So in practice a
defrost comes one minute after a re-latch that lands above the threshold.

**Stage 6: reset.** In the first poll of the defrost the whole model is
zeroed: `0x2147`, `0x2148`, `0x2149`, `0x214B`, `0x214C`, `0x2156`,
`0x2160`:`0x2161`. `Time Since Defrost` restarts when the sequence ends.

Two consequences:

- **The outdoor unit consumes `Heat Output`.** The controller's heat
  calculation, written in block `0x1000`, is the input to the defrost
  decision.
- **The flow/return calibration shifts the trigger.** `Heat Output` is built
  from the calibrated temperature pair, and the offset is subtracted from both
  the reference and the current value. At a 1.8 K differential and a
  -0.3125 K offset, a true loss of 12.4% already reads as 15%.


### 5.8 Compressor ramp state (`0x214E`)

A bitfield, published as text.

| bit | value | meaning |
|---|---|---|
| 0 | 1 | drive on |
| 2 | 4 | at speed |
| 3 | 8 | ramping up |
| 4 | 16 | ramping down |

Bit 0 is set with exactly one of the other three, except in the two transient
values below.

| value | text | when |
|---|---|---|
| `0` | Off | compressor stopped |
| `1` | Starting | one or two polls after the drive is enabled |
| `5` | At speed | the speed moves by at most 0.1 rps per poll |
| `9` | Ramping up | the speed rose by 1.2 rps or more in the last poll: every start, each stage of a defrost, each recovery |
| `17` | Ramping down | the speed fell by as much with the drive still on: defrost entry, the end of a melt, leaving hot water |
| `16` | Ramping down to stop | the ramp-down of a stop |

The classification from measured speed reproduces the register in all but 35
of 206,617 polls. A ramp is the 2.0 rps/s regime of
[6.7](#67-compressor-slew-limit-0x213f) being used.


### 5.9 Run phase (`0x2015`)

| value | meaning |
|---|---|
| `0` | idle |
| `1` | a heating or hot-water episode is in progress. Held across demand cycles |
| `6` | post-episode lockout: everything stopped, standby power |
| `1` or `2`, then `4` | exit path from `6`: one poll, then four seconds at `4`, then `0` |

`Run Phase` leaves `1` only when the episode ends, not at each compressor
stop. It goes to `6` at the end of the fan run-on and returns to `0` about
490 s later.

### 5.10 The two stability timers

`Compressor Speed Stable Time` (`0x2145`) and `Fan Target Stable Time`
(`0x2146`) are the same construction on two variables. Each counts seconds
since its variable last moved more than **3.0%** from the value it held when
the timer was last zeroed. The band is cumulative: a slow drift resets the
timer once it has added up to 3%.

- The compressor timer resets every 8-9 s while the speed is ramping, a
  handful of times in a hot-water charge at a fixed 60 rps, and free-runs for
  hours at a steady speed. The frost model reads it
  ([5.7](#57-the-frost-model-and-the-defrost-decision)).
- The fan timer runs whenever the fan target is set, including the pre-run and
  the run-on, and is zero through a defrost. In hot water the fan target is
  constant and the timer runs from fan start to fan stop. In heating it resets
  each time the air temperature has drifted about 0.5 K. Nothing has been
  found that reads it.


### 5.11 Who decides what

A read-side value that changes in the same poll as a written one changed
first, because the `0x2000` read is 0.19 s older than the `0x1000` write. A
written value that shows up in a read one poll later originated with the
controller.

| decision | made by | evidence |
|---|---|---|
| start and end of a demand, heating or hot water | controller | `Demand Mode` is written; the outdoor unit's `0x2000` follows |
| requested flow temperature | controller | written |
| pump command | controller | written; the flow follows 3 polls later. The controller regulates the pump to the flow the outdoor unit asks for in `0x2001` |
| **compressor speed while modulating** | **controller** | on the 8,867 polls in which `0x1002` moved, the target read one poll later equals it in 77% and the target read in the same poll in 4% |
| the bounds and the rate for that speed | outdoor unit | `0x2002`, `0x2003` and `0x213F` are read. The controller's command stays inside the window in 99.5% of polls |
| compressor speed at a start, a stop and in a defrost | outdoor unit | the target moves first; `0x1002` reads `0` through the pre-run and through all 1,231 defrost polls, and picks up from the target afterwards |
| fan, expansion valve, four-way valve | outdoor unit | nothing on the write side corresponds |
| when to defrost | outdoor unit | `0x2000` goes to `5` first; the controller's `Demand Mode` follows in the same poll |
| the moment of a heating/hot-water changeover | outdoor unit | `0x2000` changes first, 91.2 s after the request; the controller's `0x1012` follows in the same poll and the diverter valve, which the controller drives, moves then |
| heating episode active | controller | `0x1004` leads `Run Phase` by 1-6 polls |
| heat output figure | controller | `0x1014` is computed and written; the outdoor unit uses it for the defrost decision |
| flow/return calibration | controller | `0x1109` is written |

So the outdoor unit is not a self-contained heat pump taking a setpoint. The
speed control loop lives in the controller; the outdoor unit publishes the
envelope it may work in, protects itself, and takes over for the sequences it
owns.


### 5.12 Power-up and loss of communication

From three captures made for the purpose, all with the heat pump idle: the indoor unit powered off for two minutes, the outdoor unit
powered off for two minutes, and the bus between them interrupted for two
minutes.

**The outdoor unit never transmits on its own.** With no controller polling
it the bus is silent, for 119 and 120 s in the two captures that show it.

**A device that powers up announces itself once** with ten bytes that are not
Modbus: `55 AA 00 FF 01 03 07 80 C0 E0`. The indoor unit sent them when it
booted and the outdoor unit sent the same ten when it booted. The first four
are a line test pattern; the last six are not a valid Modbus message.

**Controller boot.** After the announcement the controller:

1. reads 6 registers from `0x2200` four times, about 100 ms apart. The answer
   is `1, 1, 1, 405, 4, 7`: three identity words and the firmware version;
2. starts the regular six-step cycle with the `0x2200` read. The three write
   blocks carry their usual constants from the first write;
3. writes `0x8000` for the outside temperature once, then the real value;
   `Requested Flow Temp` reads 0 for the first two writes.

No other function code, register block or exception response appears.

**Outdoor unit boot.** Its first answers are complete, and the identity block
is correct from the first read. A few values need one to three polls to
settle and read 0 until then: `0x2137`, `0x2138`, `0x2139`, `0x213F`,
`0x2142`, `0x2143`, `0x2159`, `0x215A`, `0x211B`, `0x2209`. `Time Since
Defrost` restarts from 0, so it does not survive a power cut.

**A controller with no outdoor unit** keeps polling in the same order at the
same 1.2 s pace, with no retries and no change of pattern (290 unanswered
requests in 116 s). After about 5 s without an answer it replaces the echoed
temperatures `0x1005`, `0x1007`, `0x1008` with `0x8000`.

**When the controller gets the outdoor unit back** it writes `Demand Mode` 6
and `0x1018` = 1, for 4 writes after the outdoor unit's reboot and 9 after the
bus interruption, then returns to 0. The outdoor unit's own mode word stays at
0 throughout. A controller that has itself just booted does not do this.

**An outdoor unit that lost its controller** reports it when the controller
returns:

| | |
|---|---|
| first poll after the gap | `Fault Code` reads 9998, `Hold-off Countdown` starts at 485 |
| for the next 485 s | the fault stays, whatever the controller writes |
| countdown reaches 0 | `Fault Code` returns to `0xFFFF` one poll later |

How long the outdoor unit waits before raising the fault is not known: nothing
can be read from it while the controller is silent. An outdoor unit that was
itself powered off comes back with no fault and no countdown.

**The controller holds off too.** In both power-cycle captures heating was
requested a few minutes after communication returned. The controller set its
episode flag `0x1004` and started the pump, ramping it up from 4%, but did not
raise `Demand Mode` until 521 s and 530 s after communication had returned.
From there the start sequence of [5.3](#53-start-sequence) ran as usual.


### 5.13 Settings and test programs

From a capture in which settings were changed one at a time.

**A power limit is not on this bus.** With an EEBus limit of 300 W, then 500 W,
then 600 W, then none, no written register changed apart from the demand
itself. The controller enforces the limit with the two things it controls:

| limit | what the controller did | measured power |
|---|---|---|
| 300 W | ended the demand. The machine cannot run that low: 28.6 rps drew 478 W | 6 W |
| 500 W | raised the demand again. Through the 180 s start window the speed is fixed by the outdoor unit at 40 rps | 680 W, above the limit |
| 600 W | once modulating, brought the speed command down to 33 rps | 560 W |
| none | the same operating point | 590 W |

So a limit below the start window's draw is exceeded for three minutes at
every start, and a limit below the minimum speed's draw stops the machine.

**Silent mode is one flag.** While the noise-reduction program was active
the controller wrote `0x110D` = 1. `Compressor Speed Max` fell
from 118.2 to 84.0 rps in the same poll and returned in the poll the flag
cleared. Nothing else in the write blocks changed. Only the one level has been
seen.

**Installer test programs use `Demand Mode` 4** with the step in `0x100B`. The
outdoor unit answers with `0x2000` = 4 and echoes the step in `0x2005`.

| program | `0x100B` | what happens |
|---|---|---|
| P.06 air venting | `4` | the pump alone: 71 s at 100%, 19 s off, repeated for 15 minutes. `Run Phase` goes to 1 and 6 with it. Compressor and fan stay off |
| P.12 defrost | `6` | a normal start sequence, then 60 s after the hand-off the outdoor unit goes into the defrost sequence of [5.6](#56-defrost-sequence) on its own: prepare 18 s, reverse 10 s, melt 78 s, then the usual return and recovery. At the end `0x2004` reads 1 for two polls and the controller clears the step |

The forced defrost is the first one seen that the frost model did not ask
for, and it shows a master can command one.

**The flow/return calibration is measured in the venting program.** `0x1109`
went from -5 to -3 at the end of one of the pump runs, where flow and return
had read 357 and 360 for a minute with no heat input. So the controller sets
the calibration to the difference between the two sensors when they must be
seeing the same water.

**The circulation pump is not in the outdoor unit's power figure**: 329 polls
with the pump at 100% and compressor and fan off all read 6 W.


---

## 6. Formulas and identities

### 6.1 Heat output (`0x1014`)

    heat output [W] = round(k x flow [l/h] x (flow temp - return temp) [1/16 K])

with all three inputs taken from the same `0x1000` write (`0x100A`, `0x1007`,
`0x1008`). `k` is 0.07222 in heating and 0.07223 in hot water, which is
`rho x cp` of water near 4.16 MJ/(m3.K). Exact to the watt in 89-99% of polls
and within 1 W in the rest.

It is non-zero only while the compressor runs and appears 12-22 s after the
compressor starts.

**It reads low at small differentials.** It uses the calibrated temperature
pair, so it inherits the `0x1109` offset. At a 1.7-1.8 K heating differential
and a -0.3125 K offset it reads 18-19% below the true output. `Delta T`
(`0x2209`) is uncalibrated and is the better basis for a heat figure.

### 6.2 Defrost capacity loss (`0x2160`)

    capacity loss [%] = 100 x (1 - heat output / defrost reference heat output)

with the heat output taken from two writes earlier. Within 0.05 in every one
of 20,315 polls in which the value changed in the capture it was derived
from, and in every one of 3,230 in a later capture.

### 6.3 Mains current (`0x201C`)

    mains current [mA] = ceil(1000 x power / voltage / 100) x 100

with power `0x2018` and voltage `0x201B` from the same read. Exact in 74-75%
of polls and within one 0.1 A step in over 99.99%. The mains voltage agrees
with a separate mains voltage sensor to a median of 0.2 V over 31 hours.

### 6.4 Refrigerant cycle identities

    subcooling = condensing temp - condenser outlet temp      (0x212A = 0x2126 - 0x200A)
    superheat  = compressor inlet temp - evaporating temp      (0x212C = 0x2007 - 0x2128)

They are what identify `0x2126` and `0x2128`, but **neither is exact**, and the
earlier claim that both were is withdrawn. Over 252,017 normal-mode polls with
the compressor turning, in the eleven captures that carry both blocks:

| identity | exact | within 1 count | within 2 | median deviation |
|---|---|---|---|---|
| subcooling | 72.96% | **98.40%** | 98.40% | 0 |
| superheat | 32.09% | 77.05% | 92.22% | 0 |

Subcooling is a rounding residue and nothing more: the controller rounds the
difference it computes once, while this sums two values each already rounded to
1/16 K. Superheat is looser than that - 1st and 99th percentiles of -11 and +8
counts, so 0.7 K tails - and is an approximation, not an identity. Pairing the
blocks one poll earlier or later makes both worse, so the 0.877 s read gap
between `0x2000` and `0x2100` is not the cause. Outside a run both degrade
sharply, subcooling to a 99th percentile of +385 counts, because neither
quantity means anything with the compressor stopped.

**The superheat form is model-specific.** An aroTHERM Split plus computes it
from the measured expansion-valve outlet temperature instead,
`0x212C = 0x2007 - 0x2009`, exact to 1 count there; on this machine that form
is 0.04% exact while running, with a median deviation of **+16 counts** - which
is just the gap between the two sensors, `0x2009` sitting a median 0.4-1.1 K
above `0x2128` in the recent captures and 6.9 K above in the earliest ones.
The same difference runs the other way: `0x2007 - 0x2128` is off by up to
14.9 K on the Split plus. Each machine is consistent with itself and the two
choose different sensors, so neither map is wrong
([9](#9-where-these-findings-come-from)).


### 6.5 De-rated temperature ceiling (`0x2137`)

80.00 °C whenever the evaporating temperature is above -5.00 °C. Below that
it follows two straight segments in the raw evaporating temperature `e`
(`0x2128`), taking the lower:

    ceiling_raw = round(1290 + e x 2/15)           from -5 down to -20 degC
    ceiling_raw = round(1916.65 + 2.0947 x e)      below -20 degC

That is a fall of 0.13 K per K down to -20 °C evaporating (78.0 °C there) and
2.1 K per K below it (70.0 °C at -23.75 °C). All 4,087 de-rated polls in four
captures fit within 2 counts.

The shape is that of a compressor envelope's upper edge, which favours the
condensing temperature as the thing it limits. That is a Lead: nothing has
come within 9.9 K of the ceiling. The compressor outlet temperature is ruled
out, having run above it without any reaction.


### 6.6 Compressor speed window (`0x2002`, `0x2003`)

The two bounds form one object: both zero or both non-zero, lower never above
upper, and the measured speed lies inside them in 99.5% of polls. The window
is closed (both zero) when idle, in the pre-run and through a defrost.

**Lower bound, `Compressor Speed Min`.** A function of air inlet temperature,
the same in both demand modes:

| air inlet | lower bound |
|---|---|
| at or below 4.94 °C | 30.0 rps |
| 5.0 to 5.3 °C | a 0.375 K transition |
| 5.38 to 13.3 °C | 20.0 rps |
| above 16.8 °C | rises with air temperature, 25 to 32 rps |

The controller tracks to this bound, and while pinned on it the flow
temperature is above its setpoint 96% of the time. This is the modulation
floor behind short cycling in mild weather.

**Upper bound, `Compressor Speed Max`.** In heating, 120.0 rps below about
7.7 °C air inlet, falling about 4.5 rps per K above that (97-98 rps at 12 °C).
Hot water follows a flatter, higher line. It moves at most 0.4 rps per poll.
On some nights it slides down to exactly 60.0 rps for hours; what selects
that is an open question.

**Fixed windows.** [50, 60] rps for 180 s after every start (once [40, 60]), and [30, 50] rps
for about 110 s around every change between heating and hot water.

### 6.7 Compressor slew limit (`0x213F`)

The maximum rate at which `Compressor Speed Target` moves.

| value | when | observed maximum |
|---|---|---|
| 2.0 rps/s | idle, the first 180 s after a start, the 110 s of a mode change, a whole defrost | 2.07 rps/s |
| 0.2 rps/s | free modulation | 0.26 rps/s |


### 6.8 Requested flow temperature (`0x1019`)

| situation | value |
|---|---|
| hot water | a fixed hot-water flow setpoint: 80 °C (after one poll at 75 °C) or 53 °C have been seen, depending on the controller's settings |
| space heating | the heating circuit's weather-compensated setpoint, modulated by the controller (25-29 °C in these captures) |
| idle | `max(20.0, 23.47 - 0.175 x outside temp)` °C, recomputed continuously. Not the heating curve |

### 6.9 Circuit flow request (`0x2001`)

1205 l/h whenever a demand is active, `0` otherwise.

- When the pump has headroom, the measured flow sits on it: median 1205 l/h,
  5th to 95th percentile 1199-1211.
- When the pump is at 100% the flow can fall short: 1115-1172 l/h on the
  reference installation, whose heating circuit is too restrictive for the
  pump to reach the request.
- The flow is essentially never above it (62 of 173,550 settled polls).
- After hot water hands over to heating the request is eased to 1098 l/h over
  34 s ([5.5](#55-changing-between-heating-and-hot-water)).
- At `0` the pump is not regulated to a flow: it runs at a fixed command.


### 6.10 The second flow figure (`0x2020`)

Not the circuit flow: the certified heat meter follows `0x2014` within 2% in
every mode and departs from this register by -4.9% to +1.6%. The ratio of
`0x2020` to `0x2014` follows the pump's operating point:

| situation | pump command | ratio |
|---|---|---|
| pump only, compressor off | 72% | 0.990 |
| pump only, compressor off | 100% | 1.032 |
| heating | 100% | 1.031-1.038 |
| hot water | 65-67% | 0.964-0.982 |

It is zero exactly when the pump is stopped, leads the flow sensor by 1-3
polls and has twice its jitter. That fits a flow estimated from the pump
rather than sensed. It is not a clean function of the pump command alone, so
this is a Lead.

It is also **monoblock-only**. A Split plus reads 32 registers from `0x2000`,
not 34, so `0x2020` and `0x2021` do not exist there and no capture from one can
say anything about either ([9](#9-where-these-findings-come-from)).

### 6.11 Fan-linked value (`0x2157`)

`-480` while `Fan Speed Target` is non-zero, `-288` on the poll after
`Defrost Active` sets and until it clears, `0` otherwise. Wrong in 43 of
321,992 polls, all at edges.

---

## 7. How this machine behaves

**The expansion valve regulates subcooling, not superheat.** The subcooling
setpoint moves several times in a cycle and the measurement follows it; the
superheat setpoint is a fixed 0 and the measured superheat sits just above
zero. A superheat near 0 K is normal on this unit and is not a fault signal.
Neither setpoint is on this bus.

**Electric power reads low.** `Electric Power Consumption` is about 4.7% below
a separate electricity meter at normal load and about 7% below when throttled
hard. It reads 6-8 W in standby and does not include the roughly 30 W base
trace heater.

**Hot water and heating run differently.** Hot water holds the compressor
near 60 rps with a constant fan target of 649-650 rpm and a regulated
1205 l/h. Heating modulates between the window bounds, up to 96 rps observed,
with the pump at 100%.

**The drive sleeps.** From 480 s after a stop until the next start hand-off,
the drive-side registers (`0x201B`-`0x201F`, `0x214F`, `0x2153`) read zero.

**No register is a packed status word** in the way `ebusd`'s `Status07` is.
`0x214E` is the one bitfield. Every other flag is a whole register.

**Idle correlations mislead.** With the compressor off every temperature
decays to ambient, so every temperature register correlates with every other.
Comparisons are only meaningful over running samples.

---

## 8. Open questions

**Quantity unknown**

| register | what would settle it |
|---|---|
| `0x2020` | a pump sweep at a fixed valve position (installer test D.027) |
| `0x2149`, `0x2156` | finding what reads the two curves; the defrost decision does not |
| `0x2157` | what -480 and -288 are |

**Leads awaiting confirmation**

| register | what would settle it |
|---|---|
| `0x201E`, `0x201F` | a clamp meter on a compressor lead |
| `0x214F`, `0x2153` | the installer sensor test, or a run with the fan blocked |
| `0x214B` | whether the number is a speed or a suction volume flow |
| `0x2158` | a second sighting |

**Identified, with one thing open**

| register | open point |
|---|---|
| `0x2137` | which temperature it caps. Needs an 80 °C hot-water charge with the evaporator below -5 °C |
| `0x2002` | what pulls it down to exactly 60 rps on some nights |
| `0x2146` | what reads the fan stability timer |
| the 60 s dwell | whether a dip below 15.0 inside the minute restarts it. Needs more defrosts |

**Not on the bus, or not found**

- The base trace heater (about 30 W, on at or below roughly 2.9 °C). Finding
  it needs a capture with a cold idle; none exists.
- The subcooling and superheat setpoints, the true discharge gas temperature,
  and the cylinder temperature. A Split plus carries the first of these on
  `0x2129` = `0x215F` ([9](#9-where-these-findings-come-from)); this machine holds both at
  `0`.

**About 190 registers have never moved.** Passive capture cannot identify
them beyond the constants labelled above by value.

---

## 9. Where these findings come from

Passive captures of the bus on one **VWZ AI + aroTHERM 75/8.1** installation,
taken through autumn 2026 and deliberately different in character: two
hot-water charges, a 17-hour pure standby, short and day-long space heating,
a first cold capture with four defrosts and two hot-water charges inside
heating, and further nights of heating at 2-13 °C. Two captures arrived after
the rules above were written and served as out-of-sample tests: in the first
every rule held except the single-segment form of the `0x2137` curve, which
became the two segments in [6.5](#65-de-rated-temperature-ceiling-0x2137); the
second contained a defrost, and the capacity-loss formula, the reference
arming, the attempt counter, the 60 s dwell and the defrost sequence all held.
Four short captures were made for a purpose: an indoor unit power cycle, an
outdoor unit power cycle and a two-minute bus interruption, all idle
([5.12](#512-power-up-and-loss-of-communication)), and a settings sweep
([5.13](#513-settings-and-test-programs)). Logged sensor data supplied six
further defrosts.

All captures reassemble to 100% CRC-valid messages in the same six block
shapes. Where a register was checked against something outside the bus, the
references were `ebusd` polling the same heat pump over eBUS, an
MID-certified heat meter on the same water circuit, a separate electricity
meter on the outdoor unit's supply, a separate mains voltage sensor, and the
unit's own type plate and display.

**Another machine.** Ten excerpts of an **aroTHERM Split plus** - outdoor
VWL 75/8.2 with indoor VWL 77/8.2 IS, firmware 405.3.3 - were contributed in
[issue #4](https://github.com/thoutenbos/esphome-arotherm-modbus/issues/4)
and are used for the cross-model checks above; they are the
`tests/data/split-plus_*.hex` datasets. Its blocks are shorter in four places
(`0x1000` 25, `0x1100` 14, `0x1200` 24, `0x2000` 32), so `0x1019`, `0x110E`,
`0x1218`, `0x2020` and `0x2021` are absent there. The aroTHERM plus 7 kW in
[section 1](#1-the-bus) was reported by its owner; on it only the registers
named there have been checked.

Two published sensors in the example configuration are computed in ESPHome
rather than read from a register: `Heat Pump COP` (`Heat Output` over
`Electric Power Consumption`) and `Carnot Efficiency`.
