"""
Independent Python reference for what the component should do with a byte
stream: find the Modbus RTU ADUs in it, decode them into sensor values, and
format the per-register debug dump.

Written from the protocol rules (README.md, REGISTERS.md) rather than
translated from arotherm_modbus.cpp, so a bug in the C++ shows up as a
disagreement instead of being copied here. The one thing shared with the
component is the sensor table: register address and scale per sensor are
read straight out of components/arotherm_modbus/__init__.py, so a newly
added SensorDef is covered by the tests without touching this file.

Also holds the serial-number scrubber used for every capture checked into
tests/data/ (see tools/import_capture.py).
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENT_INIT = os.path.join(REPO, "components", "arotherm_modbus", "__init__.py")

SLAVE_ADDRESS = 0x01
READ = 0x03
WRITE = 0x10

# Fallback block for a read response that does not follow a matching read
# request (e.g. the very first message after boot, or a dropped request):
# the register counts seen on the VWZ AI / aroTHERM 75/8.1.
FALLBACK_BLOCK_BY_COUNT = {34: 0x2000, 98: 0x2100, 73: 0x2200}


# --------------------------------------------------------------------------
# CRC / framing


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def crc_valid(adu: bytes) -> bool:
    if len(adu) < 4:
        return False
    crc = crc16_modbus(adu[:-2])
    return adu[-2] == (crc & 0xFF) and adu[-1] == (crc >> 8)


def with_crc(body: bytes) -> bytes:
    crc = crc16_modbus(body)
    return bytes(body) + bytes((crc & 0xFF, crc >> 8))


def split_adus(stream: bytes) -> list[bytes]:
    """Every CRC-valid ADU in a raw byte stream, in order. Bytes that are not
    part of one are skipped one at a time until a valid ADU starts."""
    out = []
    i = 0
    n = len(stream)
    while i + 8 <= n:
        if stream[i] == SLAVE_ADDRESS and stream[i + 1] in (READ, WRITE):
            candidates = [8]  # read request / write ack: fixed length
            if stream[i + 1] == READ:
                candidates.append(3 + stream[i + 2] + 2)  # read response
            else:
                candidates.append(7 + stream[i + 6] + 2)  # write request
            for length in candidates:
                if i + length <= n and crc_valid(stream[i:i + length]):
                    out.append(bytes(stream[i:i + length]))
                    i += length
                    break
            else:
                i += 1
            continue
        i += 1
    return out


def regs_of(payload: bytes) -> list[int]:
    return [(payload[k] << 8) | payload[k + 1] for k in range(0, len(payload), 2)]


def classify(adu: bytes, last_request: tuple[int, int] | None = None) -> str:
    """Short human-readable shape of an ADU, e.g. 'read-response 0x2000+35'."""
    if len(adu) < 4 or not crc_valid(adu):
        return "invalid"
    func = adu[1]
    if len(adu) == 8:
        start, count = (adu[2] << 8) | adu[3], (adu[4] << 8) | adu[5]
        kind = "read-request" if func == READ else "write-ack"
        return "%s 0x%04X+%d" % (kind, start, count)
    if func == WRITE:
        start, count = (adu[2] << 8) | adu[3], (adu[4] << 8) | adu[5]
        return "write-request 0x%04X+%d" % (start, count)
    n_regs = adu[2] // 2
    base = attribute_read_response(n_regs, last_request)
    return "read-response %s+%d" % ("0x%04X" % base if base is not None else "?", n_regs)


# --------------------------------------------------------------------------
# Sensor table (shared with the component on purpose - see module docstring)


@dataclass(frozen=True)
class SensorSpec:
    key: str
    register: int
    scale: str  # "raw" | "div10" | "d2c"


def load_sensors(path: str = COMPONENT_INIT) -> list[SensorSpec]:
    """SensorDef(key, register, scale, ...) entries of SENSORS in __init__.py,
    read with ast so ESPHome does not need to be installed."""
    tree = ast.parse(open(path).read(), path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SENSORS" for t in node.targets):
            specs = []
            for call in node.value.elts:
                key, register, scale = (ast.literal_eval(a) for a in call.args[:3])
                specs.append(SensorSpec(key, register, scale))
            return specs
    raise RuntimeError("no SENSORS table in " + path)


def signed16(raw: int) -> int:
    return raw - 0x10000 if raw & 0x8000 else raw


def scale_value(scale: str, raw: int) -> float:
    v = signed16(raw)
    if scale == "d2c":
        return v / 16.0
    if scale == "div10":
        return v / 10.0
    if scale == "raw":
        return float(v)
    raise ValueError(scale)


# --------------------------------------------------------------------------
# Decoder


def attribute_read_response(n_regs: int, last_request: tuple[int, int] | None) -> int | None:
    """Start register of a read response. The response carries no address of
    its own: it belongs to the read request just before it when the register
    counts agree, otherwise fall back to the VWZ AI block lengths."""
    if last_request is not None and last_request[1] == n_regs and last_request[0] != 0:
        return last_request[0]
    return FALLBACK_BLOCK_BY_COUNT.get(n_regs)


class ReferenceDecoder:
    """Feed it ADUs in bus order; it returns what the component should
    publish and log for each."""

    def __init__(self, sensors: list[SensorSpec]):
        self.sensors = sensors
        self.last_request: tuple[int, int] | None = None

    def block_of(self, adu: bytes):
        """(start_register, [raw register values]) carried by a data-bearing
        ADU, else None. Updates the read-request tracking as a side effect."""
        if not crc_valid(adu):
            return None
        func = adu[1]
        if len(adu) == 8:
            if func == READ:
                self.last_request = ((adu[2] << 8) | adu[3], (adu[4] << 8) | adu[5])
            return None
        if func == WRITE:
            if len(adu) < 9:
                return None
            start, count, byte_count = (adu[2] << 8) | adu[3], (adu[4] << 8) | adu[5], adu[6]
            if byte_count != 2 * count or len(adu) != 7 + byte_count + 2:
                return None
            return start, regs_of(adu[7:7 + byte_count])
        if func == READ:
            byte_count = adu[2]
            if byte_count % 2 or len(adu) != 3 + byte_count + 2:
                return None
            base = attribute_read_response(byte_count // 2, self.last_request)
            if base is None:
                return None
            return base, regs_of(adu[3:3 + byte_count])
        return None

    def feed(self, adu: bytes):
        """-> (publishes, regs_dump). publishes is [(key, value)] in sensor
        table order; regs_dump is the expected `regs=[...]` log text or ''."""
        request_before = self.last_request
        block = self.block_of(adu)
        if block is None:
            return [], ""
        start, regs = block
        publishes = [
            (s.key, scale_value(s.scale, regs[s.register - start]))
            for s in self.sensors
            if start <= s.register < start + len(regs)
        ]
        # The debug dump only names registers it can place with certainty:
        # a read response needs the matching request seen just before it.
        dump = ""
        if adu[1] == WRITE or (request_before is not None and request_before[1] == len(regs)):
            dump = " ".join("%04X=%04X(%.2f)" % (start + i, r, signed16(r) / 16.0) for i, r in enumerate(regs))
        return publishes, dump


# --------------------------------------------------------------------------
# Serial-number scrubbing

# A Vaillant serial / identity string on this bus: a long run of digits and
# capitals (optionally '<'-padded), e.g. "21262780000495163133810546N8<<<<<<<".
SERIAL_RUN = re.compile(rb"[0-9A-Z<]{12,}")
REDACTED_CHAR = ord("0")


def _is_serial(run: bytes) -> bool:
    return sum(c in b"0123456789" for c in run) >= 8 and any(c != REDACTED_CHAR for c in run if c != ord("<"))


def find_serials(data: bytes) -> list[bytes]:
    return [m.group() for m in SERIAL_RUN.finditer(data) if _is_serial(m.group())]


def scrub_adu(adu: bytes) -> bytes:
    """Replace every serial-like ASCII run with '0's (keeping '<' padding and
    the length) and re-seal the CRC, so the ADU still frames and decodes."""
    was_valid = crc_valid(adu)
    out = bytearray(adu)
    for m in SERIAL_RUN.finditer(adu):
        if _is_serial(m.group()):
            for k in range(m.start(), m.end()):
                if out[k] != ord("<"):
                    out[k] = REDACTED_CHAR
    if bytes(out) != adu and was_valid:
        out = bytearray(with_crc(bytes(out[:-2])))
    return bytes(out)


def scrub_stream(stream: bytes) -> bytes:
    """scrub_adu() for every ADU found in a raw stream, in place, leaving the
    bytes between ADUs untouched apart from serial runs."""
    out = bytearray(stream)
    pos = 0
    for adu in split_adus(stream):
        at = stream.index(adu, pos)
        out[at:at + len(adu)] = scrub_adu(adu)
        pos = at + len(adu)
    for m in SERIAL_RUN.finditer(bytes(out)):
        if _is_serial(m.group()):
            for k in range(m.start(), m.end()):
                if out[k] != ord("<"):
                    out[k] = REDACTED_CHAR
    return bytes(out)
