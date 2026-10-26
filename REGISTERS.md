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
address, so the firmware attributes a response's registers to the read
request seen just before it (its start register and count), in both
`decode_message_()` and `format_registers_()`. Only a response with no
matching request in front of it (the first one after boot, or one whose
request was lost) falls back to matching its *register count* against the
VWZ AI counts below. A write transaction is a
request carrying the values themselves, acknowledged by an 8-byte echo of
the address/count.

Each register is a big-endian 16-bit word, normally read as a signed
integer at one of the scales in the tables (raw, `/10`, `/100`, or D2C
`/16`). A handful of register *pairs* instead hold one big-endian IEEE-754
32-bit float, high word first - see "32-bit floats on this bus".

| block | op | start address | register count | request/notification bytes | data-carrying message |
|---|---|---|---|---|---|
| `0x1000` | write (`0x10`) | `0x1000` | 26 | 61-byte write request (carries the data), 8-byte ack | the write request itself |
| `0x1100` | write (`0x10`) | `0x1100` | 15 | 39-byte write request, 8-byte ack | the write request itself |
| `0x1200` | write (`0x10`) | `0x1200` | 25 | 59-byte write request, 8-byte ack | the write request itself |
| `0x2000` | read (`0x03`) | `0x2000` | 34 | 8-byte read request | 73-byte read response |
| `0x2100` | read (`0x03`) | `0x2100` | 98 | 8-byte read request | 201-byte read response |
| `0x2200` | read (`0x03`) | `0x2200` | 73 | 8-byte read request | 151-byte read response |

All six repeat in a fixed order roughly once every 1.2s.

The counts above are the **VWZ AI + aroTHERM 75/8.1** this map was built on.
Other units carry the same layout with different block lengths:

| block | VWZ AI + aroTHERM 75/8.1 | VWZ AI + aroTHERM plus 7 kW ([#2](https://github.com/thoutenbos/esphome-arotherm-modbus/issues/2)) | aroTHERM Split plus, VWL 75/8.2 + VWL 77/8.2 IS ([#3](https://github.com/thoutenbos/esphome-arotherm-modbus/pull/3)) |
|---|---|---|---|
| `0x1000` | 26 | 26 | 25 (ends at `0x1018`; no `0x1019`) |
| `0x1100` | 15 | 15 | 14 |
| `0x1200` | 25 | 25 | 24 |
| `0x2000` | 34 | 35 (one extra register, `0x2022`) | 32 (ends at `0x201F`) |
| `0x2100` | 98 | 98 | 98 |
| `0x2200` | 73 | 73 | 73 |

On both other units the registers that were checked (`0x2007`-`0x2011`,
`0x212A`, `0x212C`, `0x211B`) decode with the offsets and scales below.
The split unit's indoor unit owns the water side, so some `0x2000`
registers are empty there: `0x2013` (water pressure) reads `0xFFFF`,
`0x2014` (building circuit flow) always `0`, `0x2015` (run phase) `0` even
with the compressor running - the flow is in `0x100A` instead.

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

## Where these tables come from

The tables below were built from five capture sessions on one **VWZ AI +
aroTHERM 75/8.1** installation, deliberately different in character: two
domestic-hot-water cycles end to end, a 17-hour pure-standby session, a
short space-heating session that starts mid-run, and a ~23-hour session of
space heating end to end (several heating starts and stops, one hot-water
charge and a long idle gap, with `demand_mode` taking all three values).
Together they hold about 2.4 million messages; all reassemble to 100%
CRC-valid messages in the same six block shapes, with no shape appearing in
one session but not another. Where a note below says "in every capture", it
has been checked in all five.

Where a register was cross-checked against something outside the bus, the
references were `ebusd` (polling the same heat pump over eBUS), an
independent electricity meter on the outdoor unit's supply, and an
MID-certified heat meter on the same water circuit.

**A note on one `ebusd` reference field.** `hmux0_status01_temp_4` is the
domestic-hot-water **storage (cylinder) temperature**, per the `Status01`
field layout in [MarkBovee/vaillant-ebus](https://github.com/MarkBovee/vaillant-ebus)
(flow, return, outside, hot water, storage, pump state) - verified against
live values, where `temp` tracked `RunDataFlowTemp`, `temp_1`
`RunDataReturnTemp`, and `temp_2` the outside temperature. It is unusually
useful as a reference because it swings 37-66 °C across a cycle while
everything else decays toward ambient. Every register was tested against it
at three scales: the best fit was a median absolute difference of 6.0 K with
a p90 of 22.5 K, and the closest "matches" are constants that happen to sit
mid-range. **The outdoor unit does not see the cylinder temperature on this
bus** - it is an indoor-side measurement, and it is ruled out as an identity
for every unknown register here.

**Constancy is per-regime, not absolute.** All 271 registers appear in
every session. Classifying each one against all five captures at once:

| class | count | meaning |
|---|---|---|
| constant | 201 | the same single value in every capture |
| **configuration** | **1** | constant within each capture but *different between them* - `0x1109`, the flow/return calibration, which `ebusd` names outright |
| regime-dependent | 49 | moves in some captures and is frozen in others - alive only in a demand mode or operating state the rest never reached |
| always moving | 20 | varies in every capture, standby included |

So 201 is the number of registers nothing in these captures has moved - not
the number that cannot move. The 49 regime-dependent ones are the proof:
`0x2149` and `0x2156` looked like hard zeros until a cold capture arrived,
and `0x2137` held 80.00 °C in four sessions before de-rating in the fifth.
Read every "constant in every capture" note below as exactly that, and
nothing stronger.

The standby session bounds how much of the map is *operational* rather than
static: only the 20 always-moving registers vary at all with the heat pump
idle - `0x1005`, `0x1007`-`0x1009`, `0x1019`, `0x2007`-`0x200F`, `0x2126`,
`0x2128`, `0x212C`, `0x2155`, `0x2209`, `0x220A`.

> **A warning about correlations measured in standby.** With the
> compressor off, every temperature in the machine decays to ambient, so
> *every* temperature register correlates with outside temperature at
> r > 0.93 - including ones already confirmed to be something else
> entirely. A high positive correlation measured in standby is that
> shared-baseline coincidence, not evidence of identity. `0x1019` is the
> one exception, and only because its correlation is *negative*: a register
> that moves opposite to ambient cannot be explained by everything decaying
> toward ambient together.

> **And one about zeros.** A first pass matched most unknowns to
> "compressor speed x 0.1" with a median absolute difference of exactly 0.0.
> That is nonsense: both series are zero for most of a session that is half
> idle, so the median was measuring the idle stretch and nothing else. Every
> comparison here is taken over compressor-running samples with the unknown
> non-zero.

## Direction: which registers are telemetry and which are commands

Each block's data appears in exactly one frame kind, and the other kind of
that pair carries no data at all:

| block | data rides in | direction |
|---|---|---|
| `0x1000` / `0x1100` / `0x1200` | **write request** (acks carry nothing) | controller -> outdoor unit |
| `0x2000` / `0x2100` / `0x2200` | **read response** (requests carry nothing) | outdoor unit -> controller |

So a `0x1xxx` register is something the controller **commands**, and a
`0x2xxx` register is something the outdoor unit **reports**. That is a hard
constraint on identity: every `0x2xxx` unknown is a measurement or a value
computed *on the outdoor unit*, which rules out anything sensed indoors -
the cylinder temperature above, but equally room temperature, zone state,
or any controller-side setpoint.

## The demand cycle, timed

Two complete domestic-hot-water cycles were captured. They differ in length -
76 and 93 minutes of compressor run - but every transition below landed at
the **same offset in both**, to within the ~1.2 s poll granularity. Offsets
are from the `demand_mode` edge.

| offset | event |
|---|---|
| +0 s | `demand_mode` 0 -> 2 and `requested_flow_temp` 20 -> 75 in the *same* write |
| +1 s | `run_phase` 0 -> 1 |
| +2 s | `requested_flow_temp` 75 -> 80; `demand_state` (`0x2144`) 0 -> 1; building pump begins ramping |
| +9 s | fan 1 starts |
| +61 s | the handoff cluster steps together: `0x2122` 0 -> 500, `0x2002` 0 -> 600, `0x2003` 0 -> 500, `0x2121` 1 -> 0, `0x212E` 0 -> 1 |
| +67 s | compressor speed leaves 0 - **exactly 6 s after the commanded target**, in both cycles |

So a demand does not start the compressor: it starts a **60-second prerun**
of pump and fan, and only then is a speed commanded. The 6 s lead of
`0x2122` over `0x2010` is what makes `compressor_speed_target` a *command*
rather than a third echo.

The stop side, offsets from the `demand_mode` clear:

| offset | event |
|---|---|
| +0 s | `demand_mode` 2 -> 0 and `requested_flow_temp` 80 -> 0 in the same write |
| +1 s | `0x2122` commanded target -> 0; `0x2002`, `0x2003` return to idle; `demand_state` -> 4, then 0 |
| +20 s | compressor speed reaches 0 (it coasts down; the command went to 0 nineteen seconds earlier) |
| +84 s | building pump -> 0 |
| +85 s | `run_phase` 1 -> 6 (85 s after a hot-water cycle, 68 s after a space-heating episode ends - see below) |
| +86 s | fan 1 -> 0 |
| +481 to +504 s | `0x2121`, `0x212E` and `0x215C` return to their idle values, within a second or two of each other |
| +491 s | `run_phase` reaches 0 |

**`run_phase` 6 is a lockout, not an overrun.** Sampled mid-window,
everything is already stopped - compressor 0, fan 0, pump 0, building-circuit
flow 0 - and electrical draw is 7-8 W, the standby figure. The lockout is a
stored parameter: `0x221D`:`0x221E` is the float **480.0**, and timed from
the moment compressor speed reaches 0 the lockout measures 480-482 s over
six clears (published as `lockout_duration`). Timed from the demand clear
it looks like 482-503 s, but that spread is just the compressor's variable
coast-down.

`run_phase` leaves 6 by a fixed five-second exit path on the way to idle: a
one-second code (`2` or `1`), then code `4` for exactly four seconds, then
`0`. That is where the "transitional codes" on `0x2015` come from - they are
not rare glitches but a deterministic shutdown sequence.

## `run_phase` tracks the heating episode, not the demand cycle

The timed table above comes from captures in which one `demand_mode` cycle
*was* the whole heating episode, so `run_phase` appeared to follow
`demand_mode` one-for-one. Over a longer stretch of cold-weather operation
it does not:

| signal | behaviour over ~22 h |
|---|---|
| `ctlv3 hc1status` (the house circuit's own request) | one unbroken 18-hour request |
| `demand_mode` (`0x1000`) | cycled `1`/`0` **eight times** inside that window, runs of 61-374 min separated by 22-35 min off periods |
| `run_phase` (`0x2015`) | held `1` the whole time, through every one of those `demand_mode` cycles |

`run_phase` left `1` only when the house-circuit request itself ended,
going to `6` at +68 s and then running the usual lockout. So the three
signals sit at different levels:

- **`hc1status`** - the house is calling for heat (hours to days).
- **`demand_mode`** - the outdoor unit is running *now*, cycling within that
  call as the flow setpoint is met (tens of minutes to hours).
- **`run_phase`** - the heat pump's own episode state, which spans many
  `demand_mode` cycles and only unwinds when the call above it ends.

A `run_phase` of `1` therefore does **not** mean the compressor is running,
and should not be used as a "heat pump is on" signal - `demand_mode`,
`demand_state` or `compressor_speed` is the right one for that.

## What the expansion valve actually controls

This machine regulates **subcooling**, not superheat. That is worth stating
plainly, because a near-zero superheat looks alarming if you assume it is the
controlled variable. Over a space-heating cycle, from `ebusd`'s own setpoint
and actual fields:

| | setpoint | actual |
|---|---|---|
| subcooling | `0.0` -> `6.44` -> `9.81` -> `7.56` -> `7.06` -> `6.94` over 40 min | `6.94` - tracking it exactly |
| superheat | `0.0`, unchanged for the whole cycle and for days before it | `0.19`-`0.31`, sitting just above zero |

A setpoint that moves five times in forty minutes while the measurement
follows it is a controlled variable. A setpoint pinned at `0.0` that never
moves is not. The valve holds subcooling and lets superheat land wherever
it lands, which is just above zero - a deliberate design, since superheated
vapour transfers heat poorly and coil area spent making superheat is wasted
evaporator.

So **`superheat` (`0x212C`) is not a health signal on this unit.** It is
supposed to be ~0; an occasional single-count dip to -0.0625 °C is D2C
quantisation jittering around zero, not liquid return. What *would* matter
is subcooling departing from its setpoint, or a sustained and materially
negative superheat. Neither setpoint is mapped to a register yet.

## Two registers close the refrigerant cycle (`0x2126`, `0x2128`)

Both are in the `0x2100` read response, so both are outdoor-unit
measurements. Each was tested against an *identity* rather than a
correlation - if the register is the quantity, the residual is zero, and no
amount of shared shape can fake that:

| test | identity | median residual | p90 |
|---|---|---|---|
| is `0x2126` the condensing temperature? | `0x2126/16 - cond_outlet/16 == subcooling` | **+0.000 K** | 0.062 K (one LSB) |
| is `0x2128` the evaporating temperature? | `compr_inlet/16 - 0x2128/16 == superheat` | **+0.000 K** | 0.125 K (two LSB) |

Both close to the quantisation step over 8,815 running samples. The physics
agrees independently:

- `0x2128` spanned **-12.56 to +11.62 °C**, and air inlet minus evaporating
  has a median of **+4.56 K** (p10 +3.12, p90 +7.19) - a textbook
  evaporator approach.
- `0x2126` spanned **8.88 to 47.62 °C** in space heating, and condensing
  minus flow has a median of **+1.75 K** (p10 +1.12, p90 +2.00) - a textbook
  condenser approach.

These are the first two registers on this bus with no `ebusd` counterpart at
all, and together with the confirmed pressures, superheat and subcooling
they complete the refrigerant cycle. Published as `condensing_temp` and
`evaporating_temp`.

## `0x2137` is a frost de-rate on an 80.00 °C ceiling

It is pinned at exactly `0x0500` (1280 = 80.00 °C at `/16`) in every idle
sample **and in every running sample where the evaporating temperature is
at or above 0 °C**. It only ever leaves the ceiling when the evaporator is
below freezing:

| evaporating temperature | running samples | of which dipped |
|---|---|---|
| at or above 0 °C | 8,446 | **0 (0.0%)** |
| below 0 °C | 369 | 104 (28.2%) |

Inside the dips it tracks the evaporating temperature at rho +0.994, and
the dips span evaporating -12.56 to -5.00 °C. Fitting the shortfall:

    0x2137/16 = 80.00 + 0.069 x T_evap  °C       (R2 0.774)

which puts the knee near **-2.2 °C evaporating** and the deepest observed
excursion at 1.06 K below the ceiling. That is why the warmer captures call
it a constant: the evaporator never went near -2 °C.

Read as a **maximum temperature that is de-rated as the evaporator frosts**.
80.00 °C is exactly the flow setpoint hot water drives (see `0x1019`), which
makes "maximum flow temperature" the leading candidate, though the de-rate is
small enough that a computed envelope limit fits equally well. Published as
`derated_temp_ceiling` to be watched through a cold spell; the identity is a
reading, the behaviour is the fact.

## `0x201B`-`0x2021` is one record

Read as a group rather than individually, this range stops looking like
seven unrelated unknowns. **Quantisation splits it cleanly:**

| register | GCD of all values | max | max/100 |
|---|---|---|---|
| `0x201B` | **50** | 12,650 | 126.50 |
| `0x201C` | **100** | 10,100 | 101.00 (`load_step`) |
| `0x201D` | 1 | 2,393 | - (electric-power echo) |
| `0x201E` | **50** | 11,400 | 114.00 |
| `0x201F` | **100** | 9,800 | 98.00 |
| `0x2020` | 1 | 1,283 | 12.83 |
| `0x2021` | 100 | - | `0x201C` + 1600 |

So `0x201B`, `0x201E` and `0x201F` carry the same x100 encoding as
`0x201C` - four percentage-like values in a row, resolved to 1.0 or 0.5.
Only `0x201D` and `0x2020` are continuous, and `0x201D` is the known power
echo.

**They update as a unit, at two speeds.** When any one of them changes,
`0x2020` is in the same frame 92-97% of the time. But the group divides by
rate: `0x201B`, `0x201D`, `0x201E` and `0x2020` change 7-10x more often than
`0x201C`, `0x201F` and `0x2021` - and the slow trio is exactly the set
quantised to 100.

**`0x201C` is a percentage** (`load_step`). It is a multiple of 100 in
100.000% of 40,608 samples across every capture, the highest value ever
seen is **10,100 - exactly 101**, and `0x2021 - 0x201C` is exactly 1600 in
99.66% of them. What it is a percentage *of* is **not** established, and the
obvious guesses fail: `ceil(4 x power / 100)` matches 69.6% of
space-heating samples but only 2-4% of hot-water ones, so "100% = 2500 W
input" does not survive a hot-water cycle, and compressor speed sits a flat
7 rps away from it. It is not current either, and there is no voltage
register on this bus: all 271 were scanned for one sitting in a mains
(200-270) or DC-bus (330-430) band and varying like a supply, and the only
hits are single-valued constants or already-identified temperatures.

**`0x2020` is a second flow *reading*** (`flow_rate_secondary`), and the
one register of the group whose behaviour is pinned down. It is **exactly 0
in every sample where the pump is stopped**, and non-zero whenever the pump
runs - including pump-only periods with the compressor off. So it follows
the hydraulic circuit, not the refrigerant cycle. Against the confirmed
`building_circuit_flow` it is a near-copy with a **mode-dependent factor**:

| mode | `0x2020 / 0x2014` | p5 - p95 |
|---|---|---|
| space heating (two captures) | **1.0381**, **1.0376** | 1.027 - 1.049 |
| hot water (three captures) | **0.9693**, **0.9675**, **0.9810** | 0.956 - 0.993 |
| pump-only idle | 0.9767 | 0.967 - 1.008 |

One capture contains both modes, and the ratio steps between them **inside
that capture**, so the factor switches with the demand - i.e. with the
diverter valve - rather than drifting. Within a mode it holds across flow
bands.

Against an MID-certified heat meter on the same circuit, `0x2014` sits
0.6-1.0% *above* the meter in both modes - what two independent meters on
the same water look like - while `0x2020` departs by -4.9% to +0.8%
depending on mode. So `building_circuit_flow` is correctly named and is the
flow to use. `0x2020` cannot be a second flow either: this is a single
series loop with one pump, so whatever the diverter is doing, the same water
passes the heat pump and the active branch.

**Pump speed is ruled out**, which was the obvious way to have one flow and
two registers. The affinity laws would make pump power the cube of speed;
`log(pump power)` against `log(0x2020)` has exponents of 0.58, 1.13, 1.21,
1.26 and -0.02 across the captures, never near 3, and flow against it wants
intercepts of -333 to +216 l/h rather than zero.

The departure from the building circuit is near-symmetric - **+3.8%** under
space heating and **-3.3%** under hot water - which reads as one signed
correction applied per flow path. The leading explanation is that both
registers carry the **same single flow** and one has a path-dependent
calibration applied (a flow sensor's calibration does depend on the pipework
upstream of it, and the diverter changes that). Untested.

Why earlier sweeps missed it: while the machine runs the pump is held at a
fixed speed, so `0x2014` and `0x2020` are *both* near-constant, and
correlating two constants measures nothing. The right tool was a ratio, not
a correlation.

## 32-bit floats on this bus, starting with `0x2209`:`0x220A`

Every early test treated each register as an independent 16-bit scalar,
which is exactly why this pair resisted for so long: neither half means
anything alone. Taken together as a **big-endian IEEE-754 single** (high
word first), they decode to a finite, sanely-scaled value in **24,228 of
24,228 samples** - a random 32-bit pattern would be a denormal, an infinity
or an absurd magnitude far more often than not. What it carries is
**flow minus return**:

    float = 1.00632 x (flow - return) + 0.25225
    R2 0.9969, median residual 0.019 K, over 11,751 running samples

and the offset is not noise. `float - (flow - return)` has a median of
**exactly +0.2500 K**, which is 4/16 - precisely the `-4` that
`ebusd`'s `hmux0_calibrationvlrl` and register `0x1109` held at the time. So
the float is the differential *before* the flow/return calibration and the
D2C `flow_temp`/`return_temp` registers carry it *after*:

    delta_t - (flow_temp - return_temp)  =  -flow_return_calibration  K

The identity held again when the calibration later moved to `-5`
(0.3125 K), and on a second, unrelated unit: the aroTHERM plus 7 kW dump in
[#2](https://github.com/thoutenbos/esphome-arotherm-modbus/issues/2) has a
calibration of `+5` and a `delta_t` 0.31 K below `flow - return`.

**The uncalibrated figure is the one that agrees with the certified meter.**
Over ten steady hours at minimum modulation:

| heat-pump-side figure | vs certified heat meter delta T | as a fraction |
|---|---|---|
| `delta_t` (the float) | median **-0.012 K** | **-0.6%** |
| `flow_temp - return_temp` (calibrated D2C) | median **-0.262 K** | **-14.1%** |

So the calibration is not a correction toward truth - it moves the
machine's own differential *below* the certified meter by
`calibration / 16` K, which at the ~1.8 K delta of minimum modulation is a
14% under-read, and anything computed from the pair inherits it. The float
is also continuous, where the D2C pair quantises to 1/16 K (3.5% of that
1.8 K delta). Published as `delta_t`, and used for the example config's
`Thermal Power Delivery`.

**It is the only float among the registers that move.** All 268 adjacent
pairs across all six blocks were swept with the same test, skipping pairs
where either half is constant (a constant high word is just a narrow scalar,
not evidence of a float), and exactly one pair passed. But that rule is
right for telemetry and exactly wrong for stored parameters, which are
constant by definition - run the other way it finds three more, all
constants or two-state:

| pair | value(s) | meaning |
|---|---|---|
| `0x213F`:`0x2140` | `2.0` at idle, `0.2` while a demand runs | unresolved - a control period or a deadband would both fit |
| `0x221D`:`0x221E` | `480.0` | the post-stop lockout in seconds - published as `lockout_duration` |
| `0x2223`:`0x2224` | `120.0` | a parameter; what it configures is unknown |

## The flow/return calibration moves on its own (`0x1109`)

`0x1109` is the one register whose value *changed between captures*:
`0` in the three late-summer sessions, `0xFFFC` (**-4** signed) in the two
autumn ones - and `ebusd` reads `CalibrationVLRL` as `0` and `-4` over the
same two groups. Its history on this installation is `0` all summer, then
`-1`, `-4` and `-5` within about four weeks of the heating season starting,
each a single clean step; the last change was reported by this component
and by `ebusd` at the same time, over two separate buses.

**The machine writes this itself** - it is not an installer setting, and
`ebusd`'s definition carries only a read row for it. What drives it is not
known, and the obvious guess is wrong: it is not simply the offset the unit
sees between its probes at standstill (standstill `delta_t` would give +1,
-3, -10 and -13 counts where the stored values were 0, 0, 0 and -4).

Note the units: `ebusd` declares the parameter in K with no divisor, so it
prints the raw value, but the machine applies it in **1/16 K** steps - the
D2C LSB. `-5` means **-0.3125 K**, not -5 K. It is published as
`flow_return_calibration`, scaled `/16`, because every step widens the gap
between `delta_t` and `flow_temp - return_temp` and nothing else announces
it.

## Two run timers (`0x2146`, `0x2145`)

Both sit at exactly zero whenever the compressor is stopped and rise while
it runs. Fitting each against the wall clock, one row per uninterrupted run:

| register | runs fitted | slope | intercept | R2 | median residual |
|---|---|---|---|---|---|
| `0x2146` | 4 | 0.9997 | -0.1 to -0.5 s | 1.0000 | **0.2-0.4 s** |
| `0x2145` | 4 | 0.9987-0.9990 | -72 to -308 s | 1.0000 | 1.0-2.6 s |

So `0x2146` is **seconds since the compressor started**, to within half a
second over runs as long as 5 h - published as `compressor_run_time`. (On
the aroTHERM plus 7 kW dump in #2 it reads 1127-1133 and counts up with the
compressor stopped, so it may mean something else on that unit.)

`0x2145` is a different animal. It also reads 0 at the compressor start, but
within one run it resets 27-49 times, cycling 0..7 every ~8 s through the
opening minutes before free-running to thousands - the apparent intercept
above is an artefact of fitting a line through those resets. It behaves
like a timer zeroed whenever some condition fails and allowed to accumulate
only once it holds. The condition is in the speed-control path: compressor
speed changes in 84% of reset frames against a 3% baseline. But it is not
simply "time since the speed changed": only about one speed change in ten
produces a reset, and the size of the change does not separate them.

## Remaining leads and open questions

Re-fitted against all five captures rather than one, with every relation
checked for the *same coefficients in every capture*. That test matters more
than R2: a single-session fit put `0x214F` at R2 0.98 against compressor
outlet temperature and the next capture gave 0.19. Three relations survive:

| register | relation | per capture | verdict |
|---|---|---|---|
| `0x2155` | `0x2155/10 - evaporating_temp` = **+17.6 to +17.8 K** | R2 0.9993-0.9999 | the evaporating temperature on a `/10` scale with an offset zero |
| `0x2141` | **equals** `0x2120` | equal in 99.2-100% of samples | an echo of the absolute EEV position |
| `0x2021` | **equals** `0x201C` + 1600 | exact in 99.5-100% of samples | not an independent quantity |

`0x2155` was previously recorded as `6.5843 x lowpress - 69.1`, and as "not
the evaporating temperature" because it failed the superheat identity by a
median -8.5 K. Both were right about the data and wrong about the cause: the
identity failed by a constant because the register carries a fixed offset.

**`0x214F` and `0x2153` remain unexplained**, but are characterised well
enough to rule out most of the field:

- **Neither is a sensor.** Both read *exactly* zero whenever the compressor
  is stopped and are never zero while it runs. A thermistor reads ambient
  when the machine is off, not 0.
- **Both are smooth, and start seeded.** At the first running sample each
  jumps from 0 to a value that scales with how warm the machine already is,
  then climbs monotonically for well over 90 s, long after compressor speed
  has plateaued.
- **Both follow condensing temperature across modes**, with a gap that grows
  with lift - how discharge superheat behaves.

| hypothesis | what rules it out |
|---|---|
| subcooling or superheat **setpoint** | slope 17.4 against `SollwertUnterkuehlung` where a /64 copy needs 64.0; R2 0.36 |
| a rescaled copy of compressor outlet temp `0x2008` | raw-to-raw slope swings 0.36 to 0.56 between captures; a fixed-point rescale gives one slope |
| a protected discharge gas temperature | no ceiling in the distribution, and /4 = 174 °C is not physical |
| a low-pass filtered copy of any mapped register | sweeping tau 0-1800 s barely moves the fit |
| a per-run accumulator like `0x2145`/`0x2146` | neither is monotonic |

**What would settle it: a defrost.** No capture contains one. In defrost
the cycle reverses: the outdoor coil becomes the condenser, evaporating and
condensing swap roles, and every refrigerant-side quantity inverts while
every water-side one does not. A register that follows the inversion is
refrigerant-side; one that ignores it is not. A winter capture will provide
that for free.

**Refrigerant-side quantities a monoblock reports that are still unmapped**,
as candidates to test against a defrost capture: true discharge gas
temperature (`0x2008` tops out at 54 °C, far too cool to be it); inverter
heatsink or IPM temperature; DC bus voltage and compressor phase current;
the subcooling and superheat *setpoints*; target condensing temperature;
refrigerant mass flow; defrost state and counters; compressor envelope limit
flags.

## Are any registers packed bitfields?

No. Prompted by `ebusd`'s own `Status07`, which packs a heat pump's status
into labelled bits, every bit of all 271 registers was tested against six
known binary states derived from already-confirmed registers (compressor
running, demand asserted, fan running, pump running, run phase active /
post-run).

The naive test is worthless, and it is worth recording why: it returns 41
"flag bits" at over 99% agreement, but a register that goes from zero to a
large value has *bits* that switch with it, so every bit of compressor
speed, fan speed or low pressure "matches" the state perfectly. What settles
it is asking whether the register is a flag word at all. Across an active
session only three unknown registers take a small enough set of values to be
one, and each is a whole-register two-state value:

| register | values | tracks | standby |
|---|---|---|---|
| `0x1012` | `0`, `1` | pump running (99.98%) | constant `0` |
| `0x2000` | `0`, `2` | `demand_mode` echo (99.33%) | constant `0` |
| `0x2001` | `0`, `1205` | pump running (99.98%) | constant `0` |

So this bus carries no `Status07`-style packed status word.

---

## Write block `0x1000` (26 registers, `0x1000`-`0x1019`)

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x1000` | 0 | demand mode | — (tracks `RunDataStatuscode`'s state transitions) | raw | **Confirmed** | published as `demand_mode`. The controller's own command, not telemetry: `0`=idle, `1`=space heating, `2`=domestic hot water (`1` also confirmed on the Split plus). Hot water drives a fixed 80 °C `requested_flow_temp` and caps the compressor near 60 rps; space heating modulates and reaches ~96 rps. Leads `ebusd`'s `RunDataStatuscode` by 24-33 s |
| `0x1001` | 1 | unknown | — | — | Unknown | `0` in every capture |
| `0x1002` | 2 | compressor speed, smoothed echo of `0x2010` | `hmux0_rundatacompressorspeed` | `/10`, rps | **Confirmed (structural)** | leads `0x2010` by a couple of seconds on the ramp but lags badly on the way down; not published |
| `0x1003` | 3 | building pump power | `hmux0_rundatabuildingcpumppower` | `/10`, % | **Confirmed** | published as `building_pump_power`; tracked within ~1% at every timestamped `ebusd` value |
| `0x1004` | 4 | unit-active flag | — | raw | **Confirmed (structural)** | `1` whenever `run_phase` is `1` or `6`, `0` otherwise, in every capture and both demand modes. It outlasts `demand_mode` because it follows the phase, which holds through the post-stop lockout. Not published; redundant with `run_phase` |
| `0x1005` | 5 | condensor outlet temp, echo of `0x200A` | `hmux0_rundatacondensoroutlettemp` | `/16` (D2C), °C | **Confirmed (structural)** | median diff 0.0625 °C; not published |
| `0x1006` | 6 | separator/marker | — | — | **Confirmed (structural)** | exactly `0x8000` in every frame of every capture; meaning unexplained |
| `0x1007` | 7 | flow temp, echo of `0x200C` | `hmux0_rundataflowtemp` | `/16` (D2C), °C | **Confirmed (structural)** | median diff 0.0625 °C; not published |
| `0x1008` | 8 | return temp, echo of `0x200D` | `hmux0_rundatareturntemp` | `/16` (D2C), °C | **Confirmed (structural)** | median diff 0.0625 °C; not published |
| `0x1009` | 9 | outside/ambient temperature | `hmux0_status01_temp_2`, `ctlv3_displayedoutsidetemp` | `/16` (D2C), °C | **Confirmed** | published as `outside_temp` |
| `0x100A` | 10 | building circuit flow | `hmux0_buildingcircuitflow` (via `0x2014`) | raw, l/h | **Confirmed** | published as `building_circuit_flow_split`. On the VWZ AI an exact echo of `0x2014`: identical to the `0x2014` read just before it in every `0x1000` write checked (well over 100,000, across space heating, hot water and standby, and in the #2 dump). On the aroTHERM Split plus the only flow reading (`0x2014` is always 0 there), matching the indoor unit's display: 1213 vs 1204 l/h space heating, 1397 vs 1392-1400 l/h hot water |
| `0x100B`-`0x1011` | 11-17 (7 registers) | unknown | — | — | Unknown | `0` in every capture |
| `0x1012` | 18 | secondary demand-cycle flag | — | — | **Confirmed (structural)** | two-state `0`/`1`, follows the pump running; steps within 1-2 s of the demand echo `0x2001`. Not published |
| `0x1013` | 19 | unknown | — | — | Unknown | `0` in every capture |
| `0x1014` | 20 | unknown | — | — | Unknown | 0-10611 pooled; non-zero only while a demand is active, decaying on the stop ramp. Fitted against every confirmed register the best R2 is 0.84 and the slope changes sign between captures - no identity |
| `0x1015`-`0x1018` | 21-24 (4 registers) | unknown/placeholder | — | — | Unknown | constant in every capture: `0xFFFF` at 21-23, `0` at 24 |
| `0x1019` | 25 | requested flow temperature (not on the Split plus, whose block is 25 registers) | `hmux0_rundataflowtempdesired` | `/16` (D2C), °C | **Confirmed** | published as `requested_flow_temp`; steps in the same write as `demand_mode`. Three regimes. **Hot water**: a one-sample 75 °C transient, then 80 °C, then `0` at the clear. **Idle**: a live weather-dependent value recomputed in standby - on the reference installation `max(20.0, 23.47 - 0.175 x outside_temp)` °C to a residual sd of 0.02 K. **Space heating**: neither - starts high (~59.5 °C for about six minutes) and then modulates with the heating circuit. The idle relation is *not* the heating curve, which asks for much more under a real call |

## Write block `0x1100` (15 registers, `0x1100`-`0x110E`)

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x1100` | 0 | unknown | — | — | Unknown | `0` in every capture |
| `0x1101` | 1 | unknown | — | — | Unknown | `300` in every capture |
| `0x1102` | 2 | unknown | — | — | Unknown | `18000` in every capture |
| `0x1103` | 3 | unknown | — | — | Unknown | `16` in every capture |
| `0x1104` | 4 | unknown | — | — | Unknown | `32769` (`0x8001`) in every capture |
| `0x1105`-`0x1108` | 5-8 (4 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x1109` | 9 | **flow/return calibration** (Vaillant D.003) | `hmux0_calibrationvlrl` | **`/16` (D2C), K**, signed | **Confirmed** | published as `flow_return_calibration`. The one register whose value *changed between captures*, in step with `ebusd`'s `CalibrationVLRL` both times; written by the machine itself. `ebusd` prints the raw value, but the machine applies it in 1/16 K: `-5` means **-0.3125 K**. See "The flow/return calibration moves on its own". `+5` in the #2 dump |
| `0x110A` | 10 | unknown | — | — | Unknown | `0` in every capture |
| `0x110B`-`0x110C` | 11-12 (2 registers) | unknown | — | — | Unknown | `1` in every capture, each individually |
| `0x110D`-`0x110E` | 13-14 (2 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |

This block is static configuration, which `0x1109` demonstrates rather than
merely suggests: when a setting actually changed, the register carrying it
changed with it and `ebusd` named it. The others are constant only because
nothing reconfigured them across these captures.

## Write block `0x1200` (25 registers, `0x1200`-`0x1218`)

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x1200`-`0x1201` | 0-1 (2 registers) | framing | — | — | Unknown | `0xFFFF` in every capture, each individually - not printable ASCII |
| `0x1202` | 2 | unknown | — | — | Unknown | `0x000A` in every capture |
| `0x1203`-`0x1214` | 3-20 (18 registers) | **serial number** | — (a device identity string, not telemetry) | ASCII, two characters per register, big-endian | **Confirmed** | the unit's 28-character Vaillant serial number, from the low byte of `0x1203` through `0x1214`, `<`-padded to 35 characters. The captures under `tests/data/` have it overwritten with `0`s |
| `0x1215`-`0x1218` | 21-24 (4 registers) | framing | — | — | Unknown | constant in every capture, not all alike: `1`, `0`, `0`, `0xFFFF` |

## Read block `0x2000` (34 registers, `0x2000`-`0x2021`)

| register | offset | field / identity | `ebusd` match | scale | status | HA sensor |
|---|---|---|---|---|---|---|
| `0x2000` | 0 | read-side echo of `demand_mode` | — | — | **Confirmed (structural)** | — (matches the write-side value in 99.33% of samples; the disagreements are a second of transition lag. Unpublished as redundant) |
| `0x2001` | 1 | demand echo, two-state `0`/`1205` | — | — | **Confirmed (structural)** | — (steps in lockstep with `demand_mode`; unpublished as redundant) |
| `0x2002` | 2 | unknown, part of the prerun-to-active handoff cluster | — | — | Unknown | — (0-1135 pooled; steps at the handoff, then rises and falls across an active cycle. Swept against every confirmed register: best R2 0.41, and the sign of the slope is not stable. No identity) |
| `0x2003` | 3 | unknown, part of the prerun-to-active handoff cluster | — | — | Unknown | — (0-500 pooled; steps at the handoff, then declines slowly across an active cycle. Best R2 0.47 against compressor outlet, with the slope varying 10x between captures. No identity) |
| `0x2004`-`0x2006` | 4-6 (3 registers) | unknown | — | — | Unknown | — (`0` in every capture, each individually, under load as well as at idle) |
| `0x2007` | 7 | compressor inlet temp | `hmux0_rundatacompressorinlettemp` | `/16` (D2C), °C | **Confirmed** | `compressor_inlet_temp` |
| `0x2008` | 8 | compressor outlet temp | `hmux0_rundatacompressoroutlettemp` | `/16` (D2C), °C | **Confirmed** | `compressor_outlet_temp`. Peaks at 54 °C even on a hot-water charge, far too cool for true discharge gas - a pipe temperature downstream of the compressor; the machine's hottest point is not in this map |
| `0x2009` | 9 | EEV outlet temp | `hmux0_rundataeevoutlettemp` | `/16` (D2C), °C | **Confirmed** | `eev_outlet_temp` |
| `0x200A` | 10 | condensor outlet temp | `hmux0_rundatacondensoroutlettemp` | `/16` (D2C), °C | **Confirmed** | `condensor_outlet_temp` |
| `0x200B` | 11 | air inlet temp | `hmux0_rundataairinlettemp` (also `hmux0_airintaketemp`, same sensor under two names) | `/16` (D2C), °C | **Confirmed** | `air_inlet_temp` |
| `0x200C` | 12 | flow temp, after the flow/return calibration | `hmux0_rundataflowtemp` (also `hmux0_status01_temp` and `ctlv3_hc1flowtemp`) | `/16` (D2C), °C | **Confirmed** | `flow_temp` |
| `0x200D` | 13 | return temp, after the flow/return calibration | `hmux0_rundatareturntemp` (also `hmux0_status01_temp_1`) | `/16` (D2C), °C | **Confirmed** | `return_temp` |
| `0x200E` | 14 | low (refrigerant-side) pressure | `hmux0_kmkreisniederdruck` | `/10`, bar | **Confirmed exact** | `low_pressure` |
| `0x200F` | 15 | high (refrigerant-side) pressure | `hmux0_rundatahighpressure` | `/10`, bar | **Confirmed** | `high_pressure` |
| `0x2010` | 16 | compressor speed | `hmux0_rundatacompressorspeed` | `/10`, rps | **Confirmed exact** | `compressor_speed` |
| `0x2011` | 17 | fan1 speed | `hmux0_rundatafan1speed` | raw, rpm | **Confirmed** | `fan1_speed`; also readable (unpublished) at `0x2019` |
| `0x2012` | 18 | unknown | — | — | Unknown | — (`0` in every capture) |
| `0x2013` | 19 | water (hydraulic-circuit) pressure | `hmux0_flowpressure` / `ctlv3_waterpressure` (same physical sensor relayed by two eBUS devices) | `/10`, bar | **Confirmed exact** | `water_pressure` |
| `0x2014` | 20 | building circuit flow | `hmux0_buildingcircuitflow` | raw, l/h | **Confirmed** | `building_circuit_flow`; within 1% of an independent certified heat meter in both demand modes |
| `0x2015` | 21 | run phase | — (tracks `RunDataStatuscode`'s state machine) | raw | **Confirmed** | `run_phase`; `0`=idle, `1`=active (the whole heating episode, not one compressor run), `6`=post-stop lockout, plus a fixed `2`/`1` -> `4` -> `0` exit sequence. See "`run_phase` tracks the heating episode" |
| `0x2016`-`0x2017` | 22-23 (2 registers) | unknown | — | — | Unknown | — (`0` in every capture, each individually) |
| `0x2018` | 24 | electric power consumption, echo of `0x211B` (weaker fit) | `hmux0_rundataelectricpowerconsumption` | raw, W | **Confirmed (structural)** | — (median diff 37.42 W against `ebusd`, looser than `0x211B`'s 7.45 W; not published) |
| `0x2019` | 25 | fan1 speed, echo of `0x2011` | `hmux0_rundatafan1speed` | raw, rpm | **Confirmed (structural)** | — (identical sequence; not published) |
| `0x201A` | 26 | unknown | — | — | Unknown | — (`0` in every capture) |
| `0x201B` | 27 | unknown | — | — | Unknown | — (0-12650 pooled, every value a multiple of **50**, so `/100` gives 0.5 steps over 111.5-126.5 while running. Part of the `0x201B`-`0x2021` record. `0x201B/0x2020` is 9.2-10.4, close to 10 but not fixed. No identity) |
| `0x201C` | 28 | load step, 1% resolution | — | `/100`, % | **Lead** | `load_step`. A multiple of 100 in every sample, peaking at exactly 101. What it is a percentage *of* is unresolved - see "`0x201B`-`0x2021` is one record" |
| `0x201D` | 29 | electric power consumption, echo of `0x211B` | `hmux0_rundataelectricpowerconsumption` | raw, W | **Confirmed (structural)** | — (identical sequence to `0x2018`; not published) |
| `0x201E` | 30 | unknown, scales with compressor speed | — | — | Unknown | — (0-11400 pooled, every value a multiple of **50**. The ratio to raw `0x2010` is a clean **12.00** in both hot-water cycles but **11.42** and **11.67** in space heating, so an earlier single-capture `11.4731 x compr_rps` fit was measuring one operating point) |
| `0x201F` | 31 | unknown | — | — | Unknown | — (0-9800 pooled, every value a multiple of **100**, the same encoding as `load_step`. Against electric power R2 is 0.94-0.98 every capture but the slope runs 1.29 to 4.09 - correlated with load without being a copy of it) |
| `0x2020` | 32 | a second flow *reading* | — | raw, l/h | **Lead** | `flow_rate_secondary`. `0` whenever the pump is stopped; otherwise `0x2014` times a factor that switches with the diverter (~1.038 space heating, ~0.97 hot water). Not the flow a certified meter sees, and not a second circuit - see "`0x201B`-`0x2021` is one record". Not in the Split plus `0x2000` block |
| `0x2021` | 33 | `0x201C` plus a fixed 1600 | — | `/100`, % | **Confirmed (structural)** | — (`0x2021 - 0x201C` is exactly **+1600** in 99.5-100% of samples in every capture; the idle value 1600 is simply `load_step` 0. Unpublished as redundant) |
| `0x2022` | 34 | unknown, only on the 35-register variant (aroTHERM plus 7 kW + VWZ AI, #2) | — | — | Unknown | — (`0xFFFF` throughout the one idle dump available) |

## Read block `0x2100` (98 registers, `0x2100`-`0x2161`)

| register | offset | field / identity | `ebusd` match | scale | status | HA sensor |
|---|---|---|---|---|---|---|
| `0x2100`-`0x2118` | 0-24 (25 registers) | placeholder | — | — | **Confirmed (structural)** | — (`0xFFFF` in every capture; meaning unexplained) |
| `0x2119` | 25 | unknown | — | — | Unknown | — (`0` in every capture) |
| `0x211A` | 26 | unknown | — | — | Unknown | — (`1` in every capture) |
| `0x211B` | 27 | electric power consumption | `hmux0_rundataelectricpowerconsumption` | raw, W | **Confirmed** | `electric_power_consumption`. Reads ~4.7% low against an independent electricity meter at normal load, ~7% when heavily throttled - a near-constant ratio, not an offset |
| `0x211C` | 28 | 180-second countdown | — | raw, s | **Lead** | — (zero 98-99% of the time. When it runs it counts **down** from 179 to 1 over exactly 178-179 s, never rising. The episodes are not aligned to compressor edges, so what starts it is unresolved) |
| `0x211D`-`0x211F` | 29-31 (3 registers) | unknown | — | — | Unknown | — (`1` in every capture, all three) |
| `0x2120` | 32 | EEV position (absolute) | `hmux0_rundataeevpositionabs` | raw, deg | **Confirmed exact** | `eev_position` |
| `0x2121` | 33 | post-stop lockout flag | — | — | **Confirmed (structural)** | — (two-state; steps at the prerun-to-active handoff, and holds off its idle value for 481-504 s after the demand clears, matching `run_phase` 6. Not published) |
| `0x2122` | 34 | compressor speed target (not an echo) | `hmux0_rundatacompressorspeed` | `/10`, rps | **Confirmed** | `compressor_speed_target`; snaps to the newly commanded value the instant a demand starts or stops - `compressor_speed` (`0x2010`) follows 6 s later on a start and coasts down over ~20 s on a stop |
| `0x2123` | 35 | fan speed target | — | raw, rpm | **Lead** | `fan_speed_target`. Against measured `fan1_speed` the slope is 0.943-0.979 across four captures at R2 0.967-0.999 - stable, and sitting just above the measured speed as a target should |
| `0x2124` | 36 | unknown | — | — | Unknown | `0` in every capture |
| `0x2125` | 37 | unknown | — | — | Unknown | `1` in every capture |
| `0x2126` | 38 | **condensing temperature** | — (no `ebusd` field carries it) | `/16` (D2C), °C | **Confirmed** | `condensing_temp`. Proved by identity: `condensing - condensor_outlet` equals the confirmed subcooling to 0.000 K |
| `0x2127` | 39 | unknown | — | — | Unknown | `0` in every capture |
| `0x2128` | 40 | **evaporating temperature** | — (no `ebusd` field carries it) | `/16` (D2C), °C, signed | **Confirmed** | `evaporating_temp`. Proved by identity: `compressor_inlet - evaporating` equals the confirmed superheat |
| `0x2129` | 41 | subcooling, looser copy of `0x212A` | `hmux0_istwertunterkuehlung` | `/16` (D2C), K | **Lead** | — (median diff 0.0025 °C but p90 0.37 °C, against `0x212A`'s exact fit; not published) |
| `0x212A` | 42 | subcooling (actual) | `hmux0_istwertunterkuehlung` | `/16` (D2C), K | **Confirmed exact** | `subcooling`. The **controlled** variable of the expansion-valve loop |
| `0x212B` | 43 | unknown | — | — | Unknown | `0` in every capture - consistent with (but weak evidence for) the always-zero superheat setpoint |
| `0x212C` | 44 | superheat (actual) | `hmux0_istwertueberthitzung` | `/16` (D2C), K | **Confirmed** | `superheat`. An outcome, not a controlled variable - its setpoint is `0.0` |
| `0x212D` | 45 | EEV position status | `hmux0_statuseevposition` | `/10`, % | **Confirmed** | `eev_position_status`; a distinct quantity from the absolute-degree `0x2120` |
| `0x212E` | 46 | post-stop lockout flag | — | — | **Confirmed (structural)** | — (steps at the handoff; clears 481-503 s after the demand clear, within a second of `0x2121` and `0x215C`; not published) |
| `0x212F`-`0x2136` | 47-54 (8 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x2137` | 55 | de-rated temperature ceiling | — | `/16` (D2C), °C | **Lead** | `derated_temp_ceiling`. Exactly 80.00 °C unless the evaporator is below about -2.2 °C, then `80.00 + 0.069 x T_evap`. See "`0x2137` is a frost de-rate" |
| `0x2138` | 56 | unknown | — | — | Unknown | `1200` in every capture |
| `0x2139` | 57 | unknown | — | — | Unknown | `200` in every capture |
| `0x213A`-`0x213E` | 58-62 (5 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x213F`:`0x2140` | 63-64 | a two-state float parameter | — | big-endian IEEE-754 single spanning the pair | **Confirmed (structural)** | — (not two scalars: exactly `0x4000 0x0000` and `0x3E4C 0xCCCD`, the float32 encodings of **2.0** and **0.2**. 2.0 whenever the machine is idle, 0.2 while a demand runs, in both modes and every capture. A control period or a deadband would both fit) |
| `0x2141` | 65 | EEV position, echo of `0x2120` | `hmux0_rundataeevpositionabs` | raw, deg | **Confirmed (structural)** | — (equal to `0x2120` in 99.2-100% of samples in four captures; the differences are a single count of sampling lag, with rare transients during fast valve moves. Not published) |
| `0x2142` | 66 | unknown | — | — | Unknown | `55` in every capture |
| `0x2143` | 67 | unknown | — | — | Unknown | `525` in every capture |
| `0x2144` | 68 | **demand state machine** | — | raw | **Confirmed** | `demand_state`. A clean four-state sequence, identical in every capture and both demand modes: `0` idle -> **`1`** the instant the demand asserts -> `3` running -> **`4`** the instant it clears -> `0`. Both edges land within 1 s. The most precise demand-edge marker on the bus |
| `0x2145` | 69 | a stability timer, repeatedly reset | — | raw, s | **Lead** | — (`0` at every compressor start, then resets 27-49 times in the opening minutes before free-running to thousands; the resets cluster on speed-control changes. See "Two run timers") |
| `0x2146` | 70 | **compressor run time** | — (no `ebusd` field carries it) | raw, s | **Confirmed** | `compressor_run_time`. Zero whenever stopped; while running, slope 0.9997 against the wall clock at R2 1.0000, median residual 0.2-0.4 s over runs as long as 5 h |
| `0x2147`-`0x2148` | 71-72 (2 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x2149` | 73 | post-start episode value, paired with `0x2156` | — | — | **Lead** | — (see `0x2156`) |
| `0x214A`-`0x214D` | 74-77 (4 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x214E` | 78 | start/stop state machine | — | raw | **Confirmed (structural)** | — (`0` idle -> `9` transient 36-72 s after a demand asserts -> `5` running -> `16` or `0` at the clear. Same shape in every capture and both demand modes, but on a slower clock than `0x2144`. Not published) |
| `0x214F` | 79 | unknown | — | — | Unknown | — (145-697 pooled. Exactly zero whenever the compressor is stopped and never zero while it runs, so not a sensor. Rises *with* compressor outlet temperature without being it. See "Remaining leads") |
| `0x2150`-`0x2152` | 80-82 (3 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x2153` | 83 | unknown | — | — | Unknown | — (163-459 pooled, same exact-zero-when-stopped behaviour; the weakest-explained register left. Does not track `0x214F`. See "Remaining leads") |
| `0x2154` | 84 | unknown | — | — | Unknown | `0` in every capture |
| `0x2155` | 85 | evaporating temperature on an offset scale | — | `/10` °C with a fixed offset | **Lead** | — (`0x2155/10 - evaporating_temp` is **+17.64 to +17.83 K** with a 5-95% spread of only ±0.1 K - the combined quantisation of the two registers - at R2 0.9993-0.9999 in every capture, standby included, over -7 to +29 °C. An encoding, not physics. Not published; redundant with `evaporating_temp`) |
| `0x2156` | 86 | post-start episode value, paired with `0x2149` | — | — | **Lead** | — (`0x2149` and `0x2156` are never non-zero apart. Episodes begin 30-112 s after a compressor start and last 263-439 s; `0x2149` peaks at exactly 176 every time, `0x2156` at 400-422. They fire in both demand modes but only in the colder captures (air inlet 9.5-13.2 °C), never at 14.4-29.4 °C - which points at a low-ambient start routine with a threshold near 14 °C) |
| `0x2157` | 87 | demand-active flag carrying -480 | — | `/16` gives -30.0 °C | **Confirmed (structural)** | — (exactly `0` at idle and `0xFE20` = -480 whenever a demand is active, in both modes and every capture. Asserts the same second the demand does and clears 66-87 s after it, well before the lockout ends. As `/16` a round -30.0 °C, which would suit a limit enabled only while running. Not published) |
| `0x2158` | 88 | unknown | — | — | Unknown | `0` in every capture |
| `0x2159` | 89 | unknown | — | — | Unknown | `1728` in every capture |
| `0x215A` | 90 | unknown | — | — | Unknown | `360` in every capture |
| `0x215B` | 91 | unknown | — | — | Unknown | `0` in every capture |
| `0x215C` | 92 | post-stop lockout flag | — | — | **Confirmed (structural)** | — (`0`/`150`; clears 483-504 s after the demand clear, within a second or two of `0x2121` and `0x212E`, and holds through the whole of `run_phase` 6. Not published) |
| `0x215D`-`0x2161` | 93-97 (5 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |

## Read block `0x2200` (73 registers, `0x2200`-`0x2248`)

This block is device identity and stored configuration: 69 of its 73
registers are constant in every capture. Three of the constants are not
scalars but IEEE-754 floats spanning a register pair, in the same
big-endian word order as `delta_t` at `0x2209`.

| register | offset | field / identity | `ebusd` match | scale | status | notes |
|---|---|---|---|---|---|---|
| `0x2200`-`0x2202` | 0-2 (3 registers) | unknown | — | — | Unknown | `1` in every capture, each individually |
| `0x2203` | 3 | unknown, plausibly a firmware version field | — | — | Unknown | `405` in every capture |
| `0x2204` | 4 | unknown, plausibly a firmware version field | — | — | Unknown | `4` in every capture |
| `0x2205` | 5 | unknown, plausibly a firmware version field | — | — | Unknown | `7` in every capture - `0x2203`-`0x2205` read like a `405.4.7`-style version number, but nothing in the captures varies to test that |
| `0x2206`-`0x2207` | 6-7 (2 registers) | unknown | — | — | Unknown | `0xFFFF` in every capture, each individually |
| `0x2208` | 8 | unknown | — | — | Unknown | `600` in every capture |
| `0x2209` | 9 | **flow minus return, before the flow/return calibration** | — | big-endian IEEE-754 single spanning `0x2209`:`0x220A`, K | **Confirmed** | published as `delta_t`. The only float pair among the *moving* registers. `delta_t - (flow_temp - return_temp) = -flow_return_calibration`; matches a certified heat meter to a median -0.012 K where the calibrated pair is -0.262 K low. See "32-bit floats on this bus" |
| `0x220A` | 10 | low word of the float at `0x2209` | — | part of `0x2209` | **Confirmed (structural)** | not a scalar; meaningless alone |
| `0x220B` | 11 | unknown | — | — | Unknown | `1` in every capture |
| `0x220C`-`0x2217` | 12-23 (12 registers) | unknown | — | — | Unknown | `0` in every capture, each individually |
| `0x2218` | 24 | unknown | — | — | Unknown | `13` in every capture |
| `0x2219` | 25 | unknown | — | — | Unknown | `16` in every capture |
| `0x221A` | 26 | unknown | — | — | Unknown | `300` in every capture |
| `0x221B` | 27 | unknown | — | — | Unknown | `600` in every capture |
| `0x221C` | 28 | unknown | — | — | Unknown | `0` in every capture |
| `0x221D`:`0x221E` | 29-30 | **post-stop lockout, in seconds** | — | big-endian IEEE-754 single spanning the pair, s | **Confirmed** | published as `lockout_duration`. `0x43F0 0x0000` = **480.0** in every capture (and in the #2 dump). Timed from the moment compressor speed reaches 0, the measured lockout is 480, 481, 481, 481, 481 and 482 s over six clears - a stored float matching a measured timer to within the 1.2 s sampling |
| `0x221F` | 31 | unknown | — | — | Unknown | `17766` (`0x4566`) in every capture. Shaped like a float high word, but `0x2220` is `1`, not `0`, so the pair does not decode to a round value and this is left as a scalar |
| `0x2220` | 32 | unknown | — | — | Unknown | `1` in every capture |
| `0x2221` | 33 | unknown | — | — | Unknown | `0` in every capture |
| `0x2222` | 34 | unknown | — | — | Unknown | `1` in every capture |
| `0x2223`:`0x2224` | 35-36 | stored float constant `120.0` | — | big-endian IEEE-754 single spanning the pair | **Confirmed (structural)** | `0x42F0 0x0000` = **120.0** in every capture. A parameter; what it configures is unknown |
| `0x2225` | 37 | unknown | — | — | Unknown | `50` in every capture - its low byte is the first character of the serial readback that follows, as `0x1203`'s is in `0x1200` |
| `0x2226`-`0x2236` | 38-54 (17 registers) | readback of the serial number | — | ASCII, as `0x1204`-`0x1214` | **Confirmed** | byte-for-byte identical to `0x1204`-`0x1214` in every capture. Overwritten with `0`s in `tests/data/` |
| `0x2237`-`0x2246` | 55-70 (16 registers) | a second identity string | — | ASCII, two characters per register | **Confirmed (structural)** | a 30-character ASCII string with `XX` padding, constant in every capture and **not** present anywhere in write block `0x1200` - most likely the other unit's serial or article number. Overwritten with `0`s in `tests/data/` |
| `0x2247` | 71 | unknown | — | — | Unknown | `1` in every capture |
| `0x2248` | 72 | unknown | — | — | Unknown | `0` in every capture |

---

Three more published sensors are not in these tables at all: `Thermal
Power Delivery`, `Heat Pump COP` and `Carnot Efficiency` are computed in
ESPHome from the register-backed sensors above (`building_circuit_flow`,
`delta_t` - or `flow_temp`/`return_temp` until it has been seen -,
`electric_power_consumption`, `compressor_speed` and `air_inlet_temp`), not
decoded from any register of their own.
