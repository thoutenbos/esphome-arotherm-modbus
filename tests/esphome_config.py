#!/usr/bin/env python3
"""
Runs `esphome config` on the example arotherm-modbus.yaml against the
component in this checkout (not the copy on GitHub `main` its
external_components block points at), in two variants:

  vwz-ai       the example as shipped
  split-plus   with the commented aroTHERM Split plus block applied, as
               README.md "Differences between units" describes

so a schema change in __init__.py that breaks either config is caught.
Needs ESPHome installed (`pip install esphome`); dummy secrets are supplied.

Usage: python3 tests/esphome_config.py
"""
import base64
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(REPO, "arotherm-modbus.yaml")

SECRETS = """wifi_ssid: test
wifi_password: testtest
api_encryption_key: "%s"
ota_password: test
"""

SPLIT_PLUS_DROPPED = ("water_pressure", "building_circuit_flow", "run_phase", "requested_flow_temp")


def local_source(text):
    text = text.replace("type: git", "type: local")
    text = re.sub(r"url: \S+", "path: " + os.path.join(REPO, "components"), text)
    return re.sub(r"\n\s+ref: \S+", "", text)


def split_plus(text):
    out, skipping = [], False
    for line in text.splitlines():
        m = re.match(r"^  ([a-z0-9_]+):\s*$", line)
        if m:
            skipping = m.group(1) in SPLIT_PLUS_DROPPED
        elif not line.startswith("    "):
            skipping = False
        if skipping:
            continue
        # uncomment the Split plus block
        line = re.sub(r"^  # (building_circuit_flow_split:)", r"  \1", line)
        line = re.sub(r"^  #   (id|name): ", r"    \1: ", line)
        out.append(line)
    result = "\n".join(out) + "\n"
    if "\n  building_circuit_flow_split:" not in result:
        raise SystemExit("Split plus block not found in arotherm-modbus.yaml")
    return result


def main():
    example = local_source(open(EXAMPLE).read())
    failed = False
    with tempfile.TemporaryDirectory() as work:
        key = base64.b64encode(os.urandom(32)).decode()  # ESPHome rejects an all-zero key
        open(os.path.join(work, "secrets.yaml"), "w").write(SECRETS % key)
        for name, text in (("vwz-ai", example), ("split-plus", split_plus(example))):
            path = os.path.join(work, "arotherm-modbus-%s.yaml" % name)
            open(path, "w").write(text)
            proc = subprocess.run(["esphome", "config", path], capture_output=True, text=True)
            ok = proc.returncode == 0
            print("  %-4s esphome config (%s)" % ("ok" if ok else "FAIL", name))
            if not ok:
                failed = True
                print(proc.stdout[-4000:] + proc.stderr[-4000:])
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
