#!/usr/bin/env python3
"""
Test suite for the arotherm_modbus component. Needs only python3 and a C++17
compiler (g++ or clang++; set CXX to pick one) - no ESPHome, no ESP32.

The real components/arotherm_modbus/arotherm_modbus.cpp is compiled on the
host against the stand-in ESPHome headers in tests/host/ together with
tests/harness.cpp, and fed bytes through the same process_byte_() entry
point the UART path uses: framing, CRC checks, read-request tracking,
decoding, and the debug log line are all the shipped code.

What is checked:

  unit       the hand-written scenarios in unit_cases.py, each against its
             explicit expected publishes (and the reference decoder).
  datasets   every capture in data/datasets.json, replayed as one byte
             stream with no timing cues, must
               - frame into exactly the ADUs the capture holds,
               - publish exactly what the independent reference decoder in
                 modbus_ref.py says (same sensors, same order, same values),
               - log the same regs=[...] dump the reference formats,
               - meet the dataset's own expectations in datasets.json,
               - give the same result with line noise injected between ADUs,
               - match its recorded summary in expected/<dataset>.json.
  hygiene    no serial number in any file under data/, and every sensor
             key in the example arotherm-modbus.yaml exists.

After an intended behaviour change, review and re-record the summaries:

  tests/run_tests.py --update      # rewrites expected/*.json; check the diff

Usage: tests/run_tests.py [-v] [-k SUBSTRING] [--update] [--keep-build DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modbus_ref  # noqa: E402
import unit_cases  # noqa: E402

REPO = modbus_ref.REPO
COMPONENT_DIR = os.path.join(REPO, "components", "arotherm_modbus")
DATA_DIR = os.path.join(HERE, "data")
EXPECTED_DIR = os.path.join(HERE, "expected")
EXAMPLE_YAML = os.path.join(REPO, "arotherm-modbus.yaml")

TOLERANCE = 1e-4
IDLE_GAP_US = 5000
NOISE = [b"\x00", b"\xff\xff", b"\x01", b"\x01\x03", b"\x01\x10\x10\x00", b"\x01\x03\x44\x00\x01", b"\x55\xaa"]

ADU_LOG = re.compile(r"len=(\d+) \[([0-9A-F ]+)\](?: ascii=\[.*?\])?(?: regs=\[(.*)\])?$")


# --------------------------------------------------------------------------
# Building and driving the harness


def build_harness(build_dir: str) -> str:
    cxx = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++") or "c++"
    exe = os.path.join(build_dir, "arotherm_harness")
    cmd = [cxx, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror",
           "-I", os.path.join(HERE, "host"), "-I", COMPONENT_DIR,
           "-o", exe, os.path.join(HERE, "harness.cpp"), os.path.join(COMPONENT_DIR, "arotherm_modbus.cpp")]
    subprocess.run(cmd, check=True)
    return exe


class Run:
    """What the firmware did with one input: the ADUs it logged, in order,
    each with the publishes its decode produced and its regs=[...] dump,
    plus any warning/error log lines."""

    def __init__(self):
        self.adus: list[tuple[bytes, list[tuple[str, float]], str]] = []
        self.problems: list[str] = []
        self.pending: list[tuple[str, float]] = []


def run_firmware(exe: str, sensors, streams: list[list[bytes]]) -> list[Run]:
    """Feed each stream (a list of byte chunks, bus-idle between chunks) to a
    fresh component instance."""
    lines = ["S %04X %s" % (s.register, s.scale.upper()) for s in sensors]
    for chunks in streams:
        lines.append("N")
        for chunk in chunks:
            for k in range(0, len(chunk), 256):
                lines.append("B " + chunk[k:k + 256].hex(" "))
            lines.append("I %d" % IDLE_GAP_US)
        lines.append("E")
    proc = subprocess.run([exe], input="\n".join(lines) + "\n", capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("harness failed (%d): %s" % (proc.returncode, proc.stderr))

    runs, cur = [], Run()
    for line in proc.stdout.splitlines():
        if line == "E":
            if cur.pending:
                cur.problems.append("publishes not followed by an ADU log line: %r" % cur.pending)
            runs.append(cur)
            cur = Run()
        elif line.startswith("P "):
            _, idx, value = line.split()
            cur.pending.append((sensors[int(idx)].key, float(value)))
        elif line.startswith("L "):
            level, msg = line[2], line[4:]
            m = ADU_LOG.search(msg) if level == "D" else None
            if m:
                adu = bytes.fromhex(m.group(2))
                if int(m.group(1)) != len(adu):
                    cur.problems.append("logged len %s for %d bytes" % (m.group(1), len(adu)))
                cur.adus.append((adu, cur.pending, m.group(3) or ""))
                cur.pending = []
            else:
                cur.problems.append("log %s: %s" % (level, msg))
    return runs


def run_reference(sensors, adus: list[bytes]):
    dec = modbus_ref.ReferenceDecoder(sensors)
    return [dec.feed(a) for a in adus]


# --------------------------------------------------------------------------
# Comparisons


def same_publishes(got, want) -> bool:
    return len(got) == len(want) and all(
        gk == wk and abs(gv - wv) <= TOLERANCE for (gk, gv), (wk, wv) in zip(got, want))


def compare_to_reference(run: Run, sensors, expected_adus: list[bytes], errors: list[str], label: str):
    got_adus = [a for a, _, _ in run.adus]
    if got_adus != expected_adus:
        for i, (g, w) in enumerate(zip(got_adus, expected_adus)):
            if g != w:
                errors.append("%s: ADU #%d framed as %s, expected %s" % (label, i, g.hex(" "), w.hex(" ")))
                break
        else:
            errors.append("%s: framed %d ADUs, expected %d" % (label, len(got_adus), len(expected_adus)))
        return
    for i, ((adu, pubs, dump), (want_pubs, want_dump)) in enumerate(
            zip(run.adus, run_reference(sensors, expected_adus))):
        if not same_publishes(pubs, want_pubs):
            errors.append("%s: ADU #%d %s\n      published %s\n      reference %s"
                          % (label, i, modbus_ref.classify(adu), pubs, want_pubs))
        if dump != want_dump:
            errors.append("%s: ADU #%d regs dump differs\n      logged    [%s]\n      reference [%s]"
                          % (label, i, dump[:200], want_dump[:200]))
    errors.extend("%s: %s" % (label, p) for p in run.problems)


def summarize(run: Run, sensors) -> dict:
    shapes: dict[str, int] = {}
    last_request = None
    for adu, _, _ in run.adus:
        shape = modbus_ref.classify(adu, last_request)
        shapes[shape] = shapes.get(shape, 0) + 1
        if len(adu) == 8 and adu[1] == modbus_ref.READ:
            last_request = ((adu[2] << 8) | adu[3], (adu[4] << 8) | adu[5])
    values: dict[str, list[float]] = {}
    for _, pubs, _ in run.adus:
        for k, v in pubs:
            values.setdefault(k, []).append(v)
    r = lambda v: round(v, 4)  # noqa: E731
    return {
        "adus": len(run.adus),
        "shapes": dict(sorted(shapes.items())),
        "sensors": {s.key: {"published": len(values[s.key]), "first": r(values[s.key][0]),
                            "last": r(values[s.key][-1]), "min": r(min(values[s.key])),
                            "max": r(max(values[s.key]))}
                    for s in sensors if s.key in values},
        "never_published": [s.key for s in sensors if s.key not in values],
    }


def check_expectations(summary: dict, expect: dict, errors: list[str], label: str):
    published = summary["sensors"]
    for key in expect.get("published", []):
        if key not in published:
            errors.append("%s: %s was never published" % (label, key))
    for key in expect.get("not_published", []):
        if key in published:
            errors.append("%s: %s was published but should not be" % (label, key))
    for key, want in expect.get("values", {}).items():
        if key not in published:
            errors.append("%s: %s was never published (expected %s)" % (label, key, want))
            continue
        lo, hi = (want, want) if not isinstance(want, list) else want
        for stat in ("min", "max"):
            v = published[key][stat]
            if not (lo - TOLERANCE <= v <= hi + TOLERANCE):
                errors.append("%s: %s %s is %s, expected within [%s, %s]" % (label, key, stat, v, lo, hi))
    for shape, count in expect.get("shapes", {}).items():
        if summary["shapes"].get(shape, 0) != count:
            errors.append("%s: %d x %s, expected %d" % (label, summary["shapes"].get(shape, 0), shape, count))


# --------------------------------------------------------------------------
# Datasets


def load_dataset(path: str) -> tuple[list[bytes], list[bytes]]:
    """-> (chunks to feed, CRC-valid ADUs the stream holds)."""
    if path.endswith(".bin"):
        stream = open(path, "rb").read()
        return [stream], modbus_ref.split_adus(stream)
    adus = []
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if line:
            adus.append(bytes.fromhex(line))
    return adus, [a for a in adus if modbus_ref.crc_valid(a)]


def with_noise(adus: list[bytes]) -> list[bytes]:
    """The same ADUs as one stream with junk between them (deterministic),
    plus trailing filler so a junk prefix claiming a long length near the
    end cannot hold back the last real ADU."""
    out = bytearray()
    for i, adu in enumerate(adus):
        out += NOISE[i % len(NOISE)] + adu
    out += bytes(300)
    return [bytes(out)]


def test_datasets(exe, sensors, args, errors) -> int:
    manifest = json.load(open(os.path.join(DATA_DIR, "datasets.json")))
    selected = [d for d in manifest if not args.k or args.k in d["file"]]
    streams, meta = [], []
    for d in selected:
        chunks, adus = load_dataset(os.path.join(DATA_DIR, d["file"]))
        streams += [chunks, with_noise(adus)]
        meta.append((d, adus))
    runs = run_firmware(exe, sensors, streams)

    for i, (d, adus) in enumerate(meta):
        name = os.path.splitext(d["file"])[0]
        clean, noisy = runs[2 * i], runs[2 * i + 1]
        before = len(errors)
        compare_to_reference(clean, sensors, adus, errors, name)
        compare_to_reference(noisy, sensors, adus, errors, name + " (with noise)")

        summary = summarize(clean, sensors)
        check_expectations(summary, d.get("expect", {}), errors, name)
        golden = os.path.join(EXPECTED_DIR, name + ".json")
        if args.update:
            with open(golden, "w") as f:
                json.dump(summary, f, indent=1)
                f.write("\n")
        elif not os.path.exists(golden):
            errors.append("%s: no %s - run with --update to record it" % (name, os.path.relpath(golden, REPO)))
        elif json.load(open(golden)) != summary:
            want = json.load(open(golden))
            diffs = [k for k in sorted(set(want["sensors"]) | set(summary["sensors"]))
                     if want["sensors"].get(k) != summary["sensors"].get(k)]
            errors.append("%s: summary differs from %s (adus %s -> %s, shapes %s, sensors %s); "
                          "run with --update if intended"
                          % (name, os.path.relpath(golden, REPO), want["adus"], summary["adus"],
                             "same" if want["shapes"] == summary["shapes"] else "changed", diffs or "same"))
        status = "ok" if len(errors) == before else "FAIL"
        print("  %-4s %-45s %3d ADUs, %2d sensors published" % (status, name, len(adus), len(summary["sensors"])))
        if args.verbose:
            for k, v in summary["sensors"].items():
                print("         %-28s last %-10s range %s .. %s" % (k, v["last"], v["min"], v["max"]))
    return len(selected)


def test_unit(exe, sensors, args, errors) -> int:
    cases = [c for c in unit_cases.CASES if not args.k or args.k in c["name"]]
    runs = run_firmware(exe, sensors, [c["chunks"] for c in cases])
    for case, run in zip(cases, runs):
        before = len(errors)
        stream = b"".join(case["chunks"])
        expected_adus = modbus_ref.split_adus(stream)
        compare_to_reference(run, sensors, expected_adus, errors, case["name"])
        got = [p for _, pubs, _ in run.adus for p in pubs]
        if not same_publishes(got, case["publish"]):
            errors.append("%s:\n      published %s\n      expected  %s" % (case["name"], got, case["publish"]))
        if "adus" in case and len(run.adus) != case["adus"]:
            errors.append("%s: framed %d ADUs, expected %d" % (case["name"], len(run.adus), case["adus"]))
        print("  %-4s %s" % ("ok" if len(errors) == before else "FAIL", case["name"]))
    return len(cases)


def test_hygiene(sensors, errors) -> int:
    for name in sorted(os.listdir(DATA_DIR)):
        data = open(os.path.join(DATA_DIR, name), "rb").read()
        if name.endswith(".hex"):
            data = b"".join(bytes.fromhex(line.split(b"#", 1)[0].decode())
                            for line in data.splitlines() if line.split(b"#", 1)[0].strip())
        found = modbus_ref.find_serials(data)
        if found:
            errors.append("data/%s contains serial-like data %r - import it with tools/import_capture.py"
                          % (name, found[0]))
    manifest = {d["file"] for d in json.load(open(os.path.join(DATA_DIR, "datasets.json")))}
    for name in sorted(os.listdir(DATA_DIR)):
        if name != "datasets.json" and name not in manifest:
            errors.append("data/%s is not listed in data/datasets.json" % name)

    keys = {s.key for s in sensors}
    in_block = False
    for line in open(EXAMPLE_YAML):
        if re.match(r"^arotherm_modbus:", line):
            in_block = True
            continue
        if in_block and re.match(r"^\S", line):
            break
        m = re.match(r"^  #? ?([a-z0-9_]+):", line) if in_block else None
        if m and m.group(1) not in ("time_id", "rx_pin", "baud_rate", "id") and m.group(1) not in keys:
            errors.append("arotherm-modbus.yaml uses unknown sensor key %s" % m.group(1))
    print("  ok   data files scrubbed and listed, example config keys valid"
          if not errors else "  FAIL hygiene")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="print every dataset's sensor ranges")
    ap.add_argument("-k", help="only run unit cases / datasets whose name contains this")
    ap.add_argument("--update", action="store_true", help="re-record expected/*.json from the current firmware")
    ap.add_argument("--keep-build", metavar="DIR", help="build the harness in DIR instead of a temp dir")
    args = ap.parse_args()

    sensors = modbus_ref.load_sensors()
    build_dir = args.keep_build or tempfile.mkdtemp(prefix="arotherm-tests-")
    os.makedirs(build_dir, exist_ok=True)
    try:
        exe = build_harness(build_dir)
        errors: list[str] = []
        print("unit cases")
        n = test_unit(exe, sensors, args, errors)
        print("datasets")
        n += test_datasets(exe, sensors, args, errors)
        print("hygiene")
        hygiene_errors: list[str] = []
        n += test_hygiene(sensors, hygiene_errors)
        errors += hygiene_errors
    finally:
        if not args.keep_build:
            shutil.rmtree(build_dir, ignore_errors=True)

    if errors:
        print("\n%d problem(s):" % len(errors))
        for e in errors:
            print("  - " + e)
        print("\nFAIL")
        sys.exit(1)
    print("\n%d checks passed%s" % (n, " (expected/*.json re-recorded)" if args.update else ""))


if __name__ == "__main__":
    main()
