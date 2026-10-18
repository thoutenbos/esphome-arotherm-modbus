#!/usr/bin/env python3
"""
Turn (part of) a real bus capture into a test dataset under tests/data/,
with every serial number scrubbed out.

Two kinds of input:

  * an ESPHome debug log of this component (or of its predecessor
    modbus_sniffer), plain or gzipped, or a capture-session directory of
    them (frames.000.log.gz, frames.001.log.gz, ...). Every
    `len=N [01 03 ...]` line is one ADU; everything else on the line
    (timestamps, ascii=[...], regs=[...]) is dropped - the regs=[...]
    and ascii=[...] fields repeat the serial number in clear text.
    Written out as a .hex dataset: one ADU per line.

  * --raw: a plain binary dump of the bus bytes (what an RS-485 to
    TCP/USB bridge records). Written out as a .bin dataset, byte for byte,
    so the component's own framer gets tested on it.

Serial numbers (a long run of digits and capitals, see
modbus_ref.SERIAL_RUN) are overwritten with '0's of the same length and
each touched ADU gets a fresh CRC, so it still frames and decodes exactly
like the original. The output is re-checked before it is written.

Examples:

  # 3 poll cycles (12 ADUs each) from the middle of a session
  import_capture.py ~/captures/2026-09-08_122950 --skip 300000 --align 0x1100 \\
      --count 36 --out tests/data/vwz-ai_idle.hex --note "VWZ AI idle"

  # a raw dump attached to an issue
  import_capture.py --raw raw_idle.txt --out tests/data/issue-2_idle.bin

Then add the dataset to tests/data/datasets.json and run
`tests/run_tests.py --update` once to record its expected output.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import modbus_ref  # noqa: E402

FRAME_LINE = re.compile(r"\blen=\d+ \[([0-9A-Fa-f ]+)\]")


def log_parts(path: str) -> list[str]:
    if os.path.isdir(path):
        parts = glob.glob(os.path.join(path, "frames.*.log*"))
        number = lambda p: int(re.search(r"frames\.(\d+)\.log", p).group(1))  # noqa: E731
        # a part being compressed may briefly exist both plain and gzipped
        by_number = {}
        for p in sorted(parts):
            by_number.setdefault(number(p), p)
        return [by_number[k] for k in sorted(by_number)]
    return [path]


def read_log_adus(path: str):
    for part in log_parts(path):
        opener = gzip.open if part.endswith(".gz") else open
        with opener(part, "rt", errors="replace") as f:
            for line in f:
                if "TOKEN" in line:
                    continue  # pre-Modbus single-byte fragments; not usable
                m = FRAME_LINE.search(line)
                if m:
                    yield bytes.fromhex(m.group(1))


def select(adus, skip: int, count: int, align: int | None):
    taken = []
    first = None
    for i, adu in enumerate(adus):
        if i < skip:
            continue
        if align is not None and not taken:
            if not (len(adu) > 8 and adu[1] == modbus_ref.WRITE and ((adu[2] << 8) | adu[3]) == align):
                continue
        if first is None:
            first = i
        taken.append(adu)
        if len(taken) >= count:
            break
    return first, taken


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="log file, capture-session directory, or (with --raw) binary dump")
    ap.add_argument("--out", required=True, help="dataset file to write (.hex or .bin)")
    ap.add_argument("--raw", action="store_true", help="source is a raw binary bus dump")
    ap.add_argument("--skip", type=int, default=0, help="ADUs to skip first (log input)")
    ap.add_argument("--count", type=int, default=36, help="ADUs to keep (log input; 12 = one poll cycle)")
    ap.add_argument("--align", type=lambda s: int(s, 0), default=None,
                    help="after --skip, start at the next write request to this block, e.g. 0x1100")
    ap.add_argument("--note", default="", help="free text for the dataset header (log input)")
    args = ap.parse_args()

    if args.raw:
        data = modbus_ref.scrub_stream(open(args.source, "rb").read())
        left = modbus_ref.find_serials(data)
        if left:
            raise SystemExit("serial-like data survived scrubbing: %r" % left)
        open(args.out, "wb").write(data)
        print("wrote %d bytes (%d ADUs) to %s" % (len(data), len(modbus_ref.split_adus(data)), args.out))
        return

    first, adus = select(read_log_adus(args.source), args.skip, args.count, args.align)
    if not adus:
        raise SystemExit("no ADUs selected")
    adus = [modbus_ref.scrub_adu(a) for a in adus]
    for a in adus:
        if modbus_ref.find_serials(a):
            raise SystemExit("serial-like data survived scrubbing in %s" % a.hex(" "))

    with open(args.out, "w") as f:
        f.write("# source: %s, ADUs %d-%d, serial numbers zeroed\n"
                % (os.path.basename(os.path.normpath(args.source)), first, first + len(adus) - 1))
        if args.note:
            f.write("# %s\n" % args.note)
        for a in adus:
            f.write(a.hex(" ").upper() + "\n")
    print("wrote %d ADUs to %s" % (len(adus), args.out))


if __name__ == "__main__":
    main()
