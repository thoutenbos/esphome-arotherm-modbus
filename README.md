# esphome-arotherm-modbus

A passive ESP32/ESPHome component that sniffs the internal RS-485 link
between a Vaillant aroTHERM-family outdoor unit and its indoor hydraulic
station/appliance interface, and exposes the decoded readings as Home
Assistant sensors - without ever being able to write to the bus.

Confirmed against a **Vaillant VWZ AI <-> AroTHERM 75/8.1** installation
(the same physical link Vaillant also uses on aroTHERM split/split plus
units - see "Which heat pumps this applies to" below). The bus turned out
to be genuine Modbus RTU carrying Vaillant's own register map, not eBUS.

> **[`REGISTERS.md`](REGISTERS.md)**: one table per
> register block, every register's known identity/scale/`ebusd` mapping or
> an explicit "unknown," covering the complete 271-register structure, not
> just the 24 currently published as sensors. This file covers the
> hardware, wiring, and installation.

## Which heat pumps this applies to

Vaillant's older/other generations run **eBUS** (different electrical
characteristics than RS-485) between the outdoor unit and the indoor
hydraulic station - the active open-source decoder for that is
[ebusd](https://github.com/john30/ebusd) +
[ebusd-configuration](https://github.com/john30/ebusd-configuration), and
this component's own protocol identification leans on `ebusd`'s field
definitions for cross-reference.

The **newer generation** moved specifically the outdoor-compressor <->
indoor-hydraulic-station link off eBUS and onto this Modbus RTU link
instead.

No public register map for this link could be found before this project 
- if you have a similar unit and want to help extend the register map, see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Why it's passive

Three independent layers, any one of which alone is enough:

1. **Hardware**: the RS-485 transceiver's TX pin is not connected
   to the ESP32 board.
2. **UART config**: the component configures its hardware UART itself
   with only an `rx_pin` - it never calls `uart_set_pin()` with a TX pin,
   so the ESP32 UART peripheral has no pin to drive even in software.
3. **Firmware**: this component only ever reads its hardware UART's
   receive FIFO. It has no write path at all, on any pin.

Tap the sniffer's A/B leads directly across the existing bus wiring (e.g.
at a spare screw terminal, or in parallel with an existing device's A/B
pins). Don't add termination resistors at the sniffer - it's a tap, not a
bus endpoint, and adding termination there would load the bus.

If the bus carries mains-adjacent voltages or you want extra peace of
mind, use an opto-isolated RS-485 module instead of a bare MAX485
breakout.

## Hardware

- Any ESP32 dev board
- An RS-485-to-TTL transceiver breakout (MAX485, MAX3485, SP3485, or an
  opto-isolated module)

Wiring:

| RS-485 module | ESP32 |
|---|---|
| A | bus A |
| B | bus B |
| RO | ESP32 GPIO21 |
| DE + RE | GND (tied together, permanently) |
| DI | not connected |

`rx_pin: 21` in the example config matches this; any input-capable ESP32
pin works if you wire elsewhere.

## Installation

1. Copy [`arotherm-modbus.yaml`](arotherm-modbus.yaml) into
   your own ESPHome config directory and fill in your own `secrets.yaml`
   (`wifi_ssid`, `wifi_password`, `api_encryption_key`, an OTA password).
2. The `external_components:` block already points at this repository -
   pin `ref:` to a release tag once one exists, rather than tracking
   `main`, so an upstream change can't surprise a working install.
3. Flash: `esphome run modbus-sniffer.yaml` (first flash needs a USB
   cable; subsequent updates go out over Wi-Fi/OTA).
3. Add the device in Home Assistant via the ESPHome integration as usual -
   it will expose the register-decoded sensors below plus 2 calculated
   sensors. Every sensor publishes nothing until a matching message has
   actually been seen since boot - no data right after a fresh flash is
   expected, not a fault.

## Decoded fields

The firmware validates every reassembled message against the standard
Modbus RTU CRC-16 and decodes by function code and register count.

| HA sensor | register | notes |
|---|---|---|
| `Compressor Inlet Temp` | `0x2007` | °C, D2C (`raw / 16`) |
| `Compressor Outlet Temp` | `0x2008` | °C, D2C |
| `EEV Outlet Temp` | `0x2009` | °C, D2C |
| `Condensor Outlet Temp` | `0x200A` | °C, D2C |
| `Air Inlet Temp` | `0x200B` | °C, D2C |
| `Flow Temp` | `0x200C` | °C, D2C |
| `Return Temp` | `0x200D` | °C, D2C |
| `Outside Temp` | `0x1009` (write block `0x1000`) | °C, D2C |
| `High Pressure` | `0x200F` | bar, `raw / 10` |
| `Water Pressure` | `0x2013` | bar, `raw / 10` |
| `Low Pressure` | `0x200E` | bar, `raw / 10` |
| `Compressor Speed` | `0x2010` | rps, `raw / 10` - the heat pump's actual, real-time speed |
| `Compressor Speed Target` | `0x2122` | rps, `raw / 10` - the *commanded* speed; snaps to a new value instantly on a demand start/stop, while Compressor Speed only catches up over the following several seconds |
| `Fan1 Speed` | `0x2011` | rpm, raw integer |
| `Building Pump Power` | `0x1003` (write block `0x1000`) | %, `raw / 10` |
| `EEV Position` | `0x2120` | degrees, raw integer (absolute valve opening) |
| `EEV Position Status` | `0x212D` | %, `raw / 10` - distinct from EEV Position |
| `Subcooling` | `0x212A` | K, D2C (a temperature *difference*) |
| `Superheat` | `0x212C` | K, D2C |
| `Electric Power Consumption` | `0x211B` | W, raw integer |
| `Building Circuit Flow` | `0x2014` | l/h, raw integer |
| `Demand Mode` | `0x1000` (write block `0x1000`, offset 0) | not telemetry - the controller's own on/off command. `0`=idle, `2`=domestic-hot-water demand observed so far; other demand types (e.g. space heating) haven't been captured yet |
| `Requested Flow Temp` | `0x1019` (write block `0x1000`) | °C, D2C - the flow-temperature setpoint bundled with the demand command above |
| `Run Phase` | `0x2015` | raw integer - a low-latency internal state code (`0`=idle, `1`=active, `6`=post-run) |

Temperatures are eBUS's D2C convention (`degrees C = raw / 16`, signed
16-bit big-endian) - the same fixed-point convention eBUS uses, even
though the framing around it is genuine Modbus, not eBUS-derived.

### Calculated values

Two more sensors are computed entirely in ESPHome
(`platform: template` in the example config), not decoded from any
register: `Thermal Power Delivery` (kW - flow temp, return temp,
and building circuit flow combined via the standard sensible-heat
formula) and `Heat Pump COP` (unitless - thermal power delivered
divided by electric power consumption, unpublished below 50 W electric
draw) (assumes pure water, not a glycol mix).

### What's not decoded yet

271 registers exist across six blocks; 24 are published as sensors above.
The rest are either confirmed structural facts with no physical quantity
to publish (echoes of an already-published register, placeholders, a
static identity/config readback), a lead not yet solid enough to trust,
or genuinely unknown - see `REGISTERS.md` for the complete register-by-
register breakdown, including exact value ranges observed for every
still-unidentified register. If you have a similar unit and want to help
narrow these down, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Reading the debug log

Raw message logging stays on regardless of what's decoded as a sensor -
every reassembled, CRC-valid message is logged at `DEBUG` with its hex
dump and, for the two largest read blocks, a full per-register dump.

## License

[GPL-3.0](LICENSE).
