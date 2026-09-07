# Contributing

This component decodes a Modbus RTU link for Vaillant heatpumps. 
24 of 271 registers are confirmed; the rest range from
"confirmed real but not decoded" down to "genuinely unknown" - see
[`REGISTERS.md`](REGISTERS.md) for the complete picture, including the
exact value range observed for every still-unidentified register. If you
have a similar heat pump, there are a few ways to help.

## If you have a similar unit

**Different model, same link (a Vaillant that moved the outdoor <->
hydraulic-station link off eBUS onto RS-485/Modbus - see README.md "Which
heat pumps this applies to")**: flash this component as-is and open an
issue with:

- The exact model/part numbers of your outdoor unit, indoor unit, and any
  gateway/interface between them.
- Whether the sensor values in `README.md`'s "Decoded fields" table look
  physically plausible on your system (right ballpark, right units).
- Anything that looks wrong or missing - a register this project marked
  "unknown" that you can identify from your own `ebusd` setup or a
  service manual, or a sensor that reads implausible values on your unit.

**A register you can identify**: if you run `ebusd` alongside this
module and can correlate a specific `REGISTERS.md` "unknown" row against
a real `ebusd` field over an actual state change, open an issue or PR
with:

- The register address and the `ebusd` field it matches.
- The scale that fits (raw integer, `/10`, or D2C `/16` are the three
  used elsewhere on this bus - try those first).
- Enough of your own data (a few real transition timestamps and both
  sides' values at each one) for the claim to be checked, not just a
  single-snapshot coincidence.

## If something doesn't work

Open an issue with your ESPHome version, ESP32 board, RS-485 module, and
(if the component doesn't decode anything at all) a snippet of the debug
log around a captured message.

## Scope

This repository ships the ESPHome component and its protocol
documentation only. It does not include the raw capture logs or the
correlation/analysis scripts used to originally reverse-engineer the
register map. A PR proposing a new register identification is
very welcome.
