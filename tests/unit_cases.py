"""
Hand-written scenarios for tests/run_tests.py: one per decoding rule, each
with the outcome spelled out explicitly. The captured datasets in
tests/data/ show the component works on real traffic; these pin down the
edges that real traffic only hits by chance.

A case is a list of byte chunks fed in order (with a bus-idle gap between
chunks) and the exact (sensor key, value) publishes expected, in order.
"""
import struct

from modbus_ref import with_crc


def request(start, count):
    return with_crc(bytes([0x01, 0x03, start >> 8, start & 0xFF, count >> 8, count & 0xFF]))


def response(regs):
    body = bytes([0x01, 0x03, 2 * len(regs)])
    for r in regs:
        body += bytes([(r >> 8) & 0xFF, r & 0xFF])
    return with_crc(body)


def write(start, regs):
    body = bytes([0x01, 0x10, start >> 8, start & 0xFF, len(regs) >> 8, len(regs) & 0xFF, 2 * len(regs)])
    for r in regs:
        body += bytes([(r >> 8) & 0xFF, r & 0xFF])
    return with_crc(body)


def write_ack(start, count):
    return with_crc(bytes([0x01, 0x10, start >> 8, start & 0xFF, count >> 8, count & 0xFF]))


def block_2000(n):
    """n registers of a 0x2000 block: register 0x20xx holds xx * 16 + 1,
    so every D2C sensor reads xx + 1/16 and the source offset is obvious."""
    return [i * 16 + 1 for i in range(n)]


def expect_2000(n):
    """Publishes for block_2000(n) with the default sensor table."""
    d2c = lambda i: i + 1 / 16  # noqa: E731
    raw = lambda i: float(i * 16 + 1)  # noqa: E731
    div10 = lambda i: (i * 16 + 1) / 10  # noqa: E731
    div50 = lambda i: (i * 16 + 1) / 50  # noqa: E731
    div1000 = lambda i: (i * 16 + 1) / 1000  # noqa: E731
    table = [
        ("building_circuit_flow_target", 0x01, raw), ("compressor_speed_max", 0x02, div10), ("compressor_speed_min", 0x03, div10),
        ("defrost_sequence", 0x06, raw),
        ("compressor_inlet_temp", 0x07, d2c), ("compressor_outlet_temp", 0x08, d2c),
        ("eev_outlet_temp", 0x09, d2c), ("condensor_outlet_temp", 0x0A, d2c),
        ("air_inlet_temp", 0x0B, d2c), ("flow_temp", 0x0C, d2c), ("return_temp", 0x0D, d2c),
        ("low_pressure", 0x0E, div10), ("high_pressure", 0x0F, div10),
        ("compressor_speed", 0x10, div10), ("fan1_speed", 0x11, raw),
        ("water_pressure", 0x13, div10), ("building_circuit_flow", 0x14, raw), ("run_phase", 0x15, raw),
        ("mains_voltage", 0x1B, div50), ("active_current", 0x1C, div1000),
    ]
    return [(k, f(off)) for k, off, f in table if off < n]


def block_2100():
    regs = [0xFFFF] * 98
    regs[0x1B] = 1234       # electric_power_consumption, W
    regs[0x20] = 350        # eev_position
    regs[0x22] = 456        # compressor_speed_target, 45.6 rps
    regs[0x23] = 610        # fan_speed_target, rpm
    regs[0x26] = 600        # condensing_temp 37.5 C
    regs[0x28] = 0xFFB0     # evaporating_temp -5.0 C (signed)
    regs[0x2A] = 60         # subcooling 3.75 K
    regs[0x2C] = 0xFFDA     # superheat -2.375 K (signed)
    regs[0x2D] = 0xFF9C     # eev_position_status -10.0 % (signed)
    regs[0x31] = 0          # defrost_active
    regs[0x37] = 1276       # derated_temp_ceiling 79.75 C
    regs[0x44] = 3          # demand_state: running
    regs[0x45] = 41         # compressor_speed_stable_time, s
    regs[0x46] = 2373       # fan_target_stable_time, s
    regs[0x48] = 1          # defrost_reference_attempt
    regs[0x4C] = 40000      # time_since_defrost, s - above 32,767, so it must read unsigned
    regs[0x4E] = 9          # compressor_ramp_state: drive on, ramping up (text sensor)
    regs[0x3F:0x41] = [0x3E4C, 0xCCCD]  # compressor_slew_limit 0.2 rps/s
    regs[0x47] = 2907       # defrost_reference_heat_output, W
    regs[0x5C] = 150        # demand_window
    regs[0x60:0x62] = [0x4030, 0x0000]  # defrost_capacity_loss 2.75 %
    return regs


EXPECT_2100 = [
    ("electric_power_consumption", 1234.0), ("eev_position", 350.0),
    ("compressor_speed_target", 45.6), ("fan_speed_target", 610.0), ("condensing_temp", 37.5),
    ("evaporating_temp", -5.0), ("subcooling", 3.75), ("superheat", -2.375), ("eev_position_status", -10.0),
    ("defrost_active", 0.0), ("derated_temp_ceiling", 79.75), ("compressor_slew_limit", 0.2), ("demand_state", 3.0),
    ("compressor_speed_stable_time", 41.0), ("fan_target_stable_time", 2373.0),
    ("defrost_reference_heat_output", 2907.0), ("defrost_reference_attempt", 1.0),
    ("time_since_defrost", 40000.0), ("demand_window", 150.0),
    ("defrost_capacity_loss", 2.75),
]


def f32_regs(value):
    """The two registers (high word first) of a big-endian IEEE-754 single."""
    raw = struct.unpack(">HH", struct.pack(">f", value))
    return list(raw)


def block_2200(delta_t=1.8125, lockout=480.0, n=73):
    regs = [0] * 73
    regs[0x09:0x0B] = f32_regs(delta_t)   # delta_t, K
    regs[0x1D:0x1F] = f32_regs(lockout)   # lockout_duration, s
    return regs[:n]


def block_1100(calibration=0xFFFB):
    regs = [0, 300, 18000, 16, 0x8001, 0, 0, 0, 0, calibration, 0, 1, 1, 0, 0]
    return regs


def block_1000(n=26):
    regs = [0] * n
    regs[0x00] = 1          # demand_mode: space heating
    regs[0x03] = 849        # building_pump_power 84.9 %
    regs[0x09] = 0xFFB8     # outside_temp -4.5 C (signed)
    regs[0x0A] = 1213       # building_circuit_flow_split, l/h
    regs[0x12] = 1          # hot_water_mode_active
    regs[0x14] = 2604       # heat_output, W
    if n > 0x19:
        regs[0x19] = 35 * 16  # requested_flow_temp 35 C
    return regs


EXPECT_1000 = [
    ("demand_mode", 1.0), ("building_pump_power", 84.9), ("outside_temp", -4.5),
    ("building_circuit_flow_split", 1213.0), ("hot_water_mode_active", 1.0), ("heat_output", 2604.0), ("requested_flow_temp", 35.0),
]

def block_2100_ramp(state):
    regs = block_2100()
    regs[0x4E] = state
    return regs


def block_2200_version(n=73):
    regs = block_2200()
    regs[0x03:0x06] = [405, 4, 7]
    return regs[:n]


def block_1200(serial="21000000000000000000000000N8", n=25):
    """The 0x1200 write block around a 28-character serial (a made-up one)."""
    padded = (serial + "<" * 35)[:35]
    regs = [0xFFFF, 0xFFFF, 0x000A, ord(padded[0])]
    regs += [(ord(padded[i]) << 8) | ord(padded[i + 1]) for i in range(1, 35, 2)]
    regs += [1, 0, 0, 0xFFFF]
    return regs[:n]


CASES = [
    {
        "name": "text: serial number from the 0x1200 write block, padding dropped, published once",
        "chunks": [write(0x1200, block_1200()), write_ack(0x1200, 25),
                   write(0x1200, block_1200()), write_ack(0x1200, 25)],
        "publish": [],
        "text": [("serial_number", "21000000000000000000000000N8")],
    },
    {
        "name": "text: a serial number cut off by the end of its block is not published",
        "chunks": [write(0x1200, block_1200(n=20)), write_ack(0x1200, 20)],
        "publish": [],
        "text": [],
    },
    {
        "name": "text: firmware version from 0x2203-0x2205, published once while unchanged",
        "chunks": [request(0x2200, 73), response(block_2200_version()),
                   request(0x2200, 73), response(block_2200_version())],
        "publish": [("delta_t", 1.8125), ("lockout_duration", 480.0)] * 2,
        "text": [("firmware_version", "405.4.7")],
    },
    {
        "name": "text: a firmware version cut off by the end of its block is not published",
        "chunks": [request(0x2200, 5), response(block_2200_version(n=5))],
        "publish": [],
        "text": [],
    },
    {
        "name": "text: compressor ramp state follows the bitfield and republishes only on change",
        "chunks": [request(0x2100, 98), response(block_2100_ramp(5)),
                   request(0x2100, 98), response(block_2100_ramp(5)),
                   request(0x2100, 98), response(block_2100_ramp(17)),
                   request(0x2100, 98), response(block_2100_ramp(16)),
                   request(0x2100, 98), response(block_2100_ramp(0)),
                   request(0x2100, 98), response(block_2100_ramp(0x21))],
        "publish": EXPECT_2100 * 6,
        "text": [("compressor_ramp_state", "At speed"), ("compressor_ramp_state", "Ramping down"),
                 ("compressor_ramp_state", "Ramping down to stop"), ("compressor_ramp_state", "Off"),
                 ("compressor_ramp_state", "drive on, bit 5")],
    },
    {
        "name": "0x2200 block: delta_t and lockout_duration are 32-bit floats over two registers",
        "chunks": [request(0x2200, 73), response(block_2200())],
        "publish": [("delta_t", 1.8125), ("lockout_duration", 480.0)],
    },
    {
        "name": "a float whose low word falls outside the block is not published",
        # A 10-register read of 0x2200 ends at 0x2209, the float's high word.
        "chunks": [request(0x2200, 10), response(block_2200(n=10))],
        "publish": [],
    },
    {
        "name": "a float that decodes to NaN or infinity is not published",
        "chunks": [request(0x2200, 73), response(block_2200(delta_t=float("nan"), lockout=float("inf")))],
        "publish": [],
    },
    {
        "name": "negative float, and a 73-register response with no request falls back to 0x2200",
        "chunks": [response(block_2200(delta_t=-0.0625))],
        "publish": [("delta_t", -0.0625), ("lockout_duration", 480.0)],
    },
    {
        "name": "0x1100 write block: flow_return_calibration is signed and /16 (-5 -> -0.3125 K)",
        "chunks": [write(0x1100, block_1100()), write_ack(0x1100, 15)],
        "publish": [("flow_return_calibration", -0.3125)],
    },
    {
        "name": "0x1100 write block with 14 registers (Split plus) still carries the calibration",
        "chunks": [write(0x1100, block_1100(0)[:14]), write_ack(0x1100, 14)],
        "publish": [("flow_return_calibration", 0.0)],
    },
    {
        "name": "read response attributed to its request (VWZ AI, 34 registers)",
        "chunks": [request(0x2000, 34), response(block_2000(34))],
        "publish": expect_2000(34),
    },
    {
        "name": "aroTHERM Split plus: 0x2000 read with 32 registers (PR #3)",
        "chunks": [request(0x2000, 32), response(block_2000(32))],
        "publish": expect_2000(32),
    },
    {
        "name": "aroTHERM plus + VWZ AI: 0x2000 read with 35 registers (issue #2)",
        "chunks": [request(0x2000, 35), response(block_2000(35))],
        "publish": expect_2000(35),
    },
    {
        "name": "response before any request falls back to the register count (boot)",
        "chunks": [response(block_2000(34))],
        "publish": expect_2000(34),
    },
    {
        "name": "response before any request with an unknown count is dropped",
        "chunks": [response(block_2000(32))],
        "publish": [],
    },
    {
        "name": "request lost: 98-register response after a 0x2000 request is still 0x2100",
        "chunks": [request(0x2000, 34), response(block_2100())],
        "publish": EXPECT_2100,
    },
    {
        "name": "request lost: response whose count matches neither request nor fallback is dropped",
        "chunks": [request(0x2000, 34), response(block_2000(32))],
        "publish": [],
    },
    {
        "name": "0x2100 block, signed values",
        "chunks": [request(0x2100, 98), response(block_2100())],
        "publish": EXPECT_2100,
    },
    {
        "name": "0x1000 write block, incl. building_circuit_flow_split (0x100A)",
        "chunks": [write(0x1000, block_1000()), write_ack(0x1000, 26)],
        "publish": EXPECT_1000,
    },
    {
        "name": "0x1000 write block with 25 registers (Split plus) has no requested_flow_temp",
        "chunks": [write(0x1000, block_1000(25)), write_ack(0x1000, 25)],
        "publish": [p for p in EXPECT_1000 if p[0] != "requested_flow_temp"],
    },
    {
        "name": "write ack and read request alone publish nothing",
        "chunks": [write_ack(0x1000, 26), request(0x2000, 34)],
        "publish": [],
    },
    {
        "name": "corrupted CRC is skipped and the framer resyncs on the next ADU",
        "chunks": [request(0x2000, 34),
                   response(block_2000(34))[:-1] + b"\x00",
                   request(0x2000, 34), response(block_2000(34))],
        "publish": expect_2000(34),
        "adus": 3,
    },
    {
        "name": "ADUs back to back in one chunk, with line noise in between",
        # "01 03 44" looks like the start of a 73-byte read response; the
        # framer has to give up on it once 73 bytes fail the CRC and find
        # the real ADUs inside those bytes.
        "chunks": [b"\x00\xff\x01\x03\x44" + request(0x2000, 34) + b"\x01" + response(block_2000(34))
                   + write(0x1000, block_1000())],
        "publish": expect_2000(34) + EXPECT_1000,
        "adus": 3,
    },
    {
        "name": "ADU trickling in one byte at a time",
        "chunks": [bytes([b]) for b in request(0x2100, 98) + response(block_2100())],
        "publish": EXPECT_2100,
    },
]
