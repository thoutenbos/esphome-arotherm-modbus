# Contributing

This component decodes a Modbus RTU link for Vaillant heatpumps. 
36 sensors are published from the 271 registers; the rest range from
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

**A capture from your unit** is the most useful thing you can attach: a
raw dump of the bus bytes (from an RS-485 bridge) or a few poll cycles of
this component's `DEBUG` log. Both contain your units' serial numbers in
clear text (write block `0x1200`, read block `0x2200`) - scrub them first:

```
python3 tests/tools/import_capture.py --raw dump.bin --out scrubbed.bin
python3 tests/tools/import_capture.py esphome.log --count 36 --out scrubbed.hex
```

## If something doesn't work

Open an issue with your ESPHome version, ESP32 board, RS-485 module, and
(if the component doesn't decode anything at all) a snippet of the debug
log around a captured message, scrubbed as above.

## Changing the component

Run the test suite before opening a PR - it needs only Python 3 and a C++
compiler, no ESPHome or ESP32:

```
python3 tests/run_tests.py
```

It replays the captures in `tests/data/` through the real C++ and compares
every published value against an independent reference decoder; see
[`tests/README.md`](tests/README.md). If your change is meant to alter what
gets published, re-record the expected summaries with
`python3 tests/run_tests.py --update` and include the `tests/expected/`
diff in the PR so the change is visible. A PR adding support for another
unit should add a short scrubbed capture of it as a new dataset.

## Scope

This repository ships the ESPHome component, its protocol documentation,
and the test suite with a few short, scrubbed captures as test data. It
does not include the full raw capture logs or the correlation/analysis
scripts used to originally reverse-engineer the register map. A PR proposing a new register identification is
very welcome.
