# Tests

```
python3 tests/run_tests.py          # host tests: python3 + g++ or clang++ (CXX=...)
python3 tests/esphome_config.py     # `esphome config` on the example yaml (needs esphome)
```

Both run in GitHub Actions on every push and pull request
(`.github/workflows/tests.yml`).

## How it works

`run_tests.py` compiles the real `components/arotherm_modbus/arotherm_modbus.cpp`
on the host, against the stand-in ESPHome headers in [`host/`](host/), together
with [`harness.cpp`](harness.cpp). The harness feeds bytes in through
`process_byte_()` - the same function `loop()` hands every received UART byte
to - so framing, CRC checks, read-request tracking, decoding and the
`DEBUG` log line are all the shipped code. Only the ESP32 UART interrupt and
ring buffer are not exercised.

What the component publishes and logs is compared against
[`modbus_ref.py`](modbus_ref.py), an independent Python reference decoder
written from the protocol rules rather than translated from the C++. The
sensor table (key, register, scale) is the one thing they share: it is read
from `components/arotherm_modbus/__init__.py`, so a new `SensorDef` is
covered automatically.

| check | what it catches |
|---|---|
| **unit** - [`unit_cases.py`](unit_cases.py) | one scenario per decoding rule with the expected publishes written out: request attribution for 32/34/35-register `0x2000` blocks, the count fallback after boot or a lost request, dropping what can't be placed, signed values, the `0x1000` write block with and without `0x1019`, CRC errors, line noise, byte-at-a-time arrival |
| **framing** | every dataset, fed as one byte stream with no timing cues, must frame into exactly the ADUs it holds - and again with junk injected between every ADU |
| **decode** | every ADU must publish exactly what the reference decoder says: same sensors, same order, same values (to 1e-4) |
| **debug log** | the `regs=[...]` dump must match the reference's formatting of the same registers |
| **expectations** | per-dataset facts in [`data/datasets.json`](data/datasets.json) (block shapes, which sensors appear, known values), written by hand |
| **summary** | per-dataset ADU shapes and per-sensor count/first/last/min/max must match [`expected/`](expected/) - any behaviour change shows up as a diff there |
| **hygiene** | no serial number in any file in `data/`, every data file listed in the manifest, every sensor key in `arotherm-modbus.yaml` exists |

## Datasets

All short excerpts, serial numbers zeroed (CRCs recomputed):

| file | unit | what it covers |
|---|---|---|
| `issue-2_arotherm-plus-vwz-ai_idle.bin` | aroTHERM plus 7 kW + VWZ AI | raw bus bytes from [#2](https://github.com/thoutenbos/esphome-arotherm-modbus/issues/2): standby, 35-register `0x2000` block |
| `vwz-ai_boot.hex` | aroTHERM 75/8.1 + VWZ AI | first ADUs after boot: a response before any request |
| `vwz-ai_idle.hex` | aroTHERM 75/8.1 + VWZ AI | standby |
| `vwz-ai_missed-request.hex` | aroTHERM 75/8.1 + VWZ AI | a lost `0x2100` read request (real bus capture) |
| `vwz-ai_dhw-start.hex` | aroTHERM 75/8.1 + VWZ AI | hot water demand starting |
| `vwz-ai_dhw-running.hex` | aroTHERM 75/8.1 + VWZ AI | hot water, compressor at 60 rps |
| `vwz-ai_dhw-stop.hex` | aroTHERM 75/8.1 + VWZ AI | hot water demand ending, compressor ramping down |
| `vwz-ai_space-heating.hex` | aroTHERM 75/8.1 + VWZ AI | space heating (`demand_mode` 1) |

No aroTHERM Split plus capture is available yet; its 32-register `0x2000`
block and 25-register `0x1000` block are covered by unit cases.

`.hex` files hold one ADU per line as hex bytes (`#` starts a comment); `.bin`
files are raw bus bytes exactly as received.

## After changing the component

- **Run the tests.** A failure in *decode* or *framing* means the C++ and the
  reference disagree - fix whichever is wrong.
- **If the change is meant to alter what is published**, update
  `modbus_ref.py` (if a decoding rule changed) and re-record the summaries:

  ```
  python3 tests/run_tests.py --update
  git diff tests/expected/
  ```

  and check that the diff shows exactly the intended change.

Useful options: `-v` prints every dataset's sensor ranges, `-k TEXT` runs only
unit cases / datasets whose name contains `TEXT`, `--keep-build DIR` keeps the
compiled harness.

## Adding a capture

Use [`tools/import_capture.py`](tools/import_capture.py) - it zeroes the serial
numbers (write block `0x1200` and read block `0x2200` carry them in ASCII) and
re-seals each touched ADU's CRC. It reads this component's (or the older
`modbus_sniffer`'s) `DEBUG` log, a capture-session directory of them, or a raw
binary dump:

```
python3 tests/tools/import_capture.py esphome.log --skip 1000 --align 0x1100 --count 36 \
    --out tests/data/<unit>_<situation>.hex --note "what this shows"
python3 tests/tools/import_capture.py --raw dump.bin --out tests/data/<unit>_<situation>.bin
```

`--count 36` is three poll cycles; `--align 0x1100` starts at a cycle boundary.
Keep captures short - a few cycles are enough to cover a situation. Then add an
entry to `data/datasets.json` (with a few hand-checked `expect` values) and run
`python3 tests/run_tests.py --update` once to record its summary.
