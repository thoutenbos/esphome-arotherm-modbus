from __future__ import annotations

from dataclasses import dataclass

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor, text_sensor, time
from esphome.const import (
    CONF_ID,
    CONF_TIME_ID,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_DURATION,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    UNIT_CELSIUS,
    UNIT_PERCENT,
    UNIT_VOLT,
    UNIT_WATT,
)

CODEOWNERS = ["@thoutenbos"]
DEPENDENCIES = ["time"]
AUTO_LOAD = ["sensor", "text_sensor"]
MULTI_CONF = True

arotherm_modbus_ns = cg.esphome_ns.namespace("arotherm_modbus")
AroThermModbus = arotherm_modbus_ns.class_("AroThermModbus", cg.Component)
Scale = arotherm_modbus_ns.enum("AroThermModbus::Scale", is_class=True)
TextKind = arotherm_modbus_ns.enum("AroThermModbus::TextKind", is_class=True)

CONF_RX_PIN = "rx_pin"
CONF_BAUD_RATE = "baud_rate"


@dataclass(frozen=True)
class SensorDef:
    key: str
    register: int
    scale: str  # "raw", "uraw", "div10", "div50", "div100", "div1000", "d2c" or "f32" - see AroThermModbus::Scale
    unit: str | None = None
    device_class: str | None = None
    accuracy_decimals: int = 2
    icon: str = "mdi:help-circle-outline"


_SCALE_CODE = {"raw": Scale.RAW, "uraw": Scale.URAW, "div10": Scale.DIV10, "div100": Scale.DIV100,
               "div50": Scale.DIV50, "div1000": Scale.DIV1000, "d2c": Scale.D2C, "f32": Scale.F32}

SENSORS = [
    SensorDef("demand_mode", 0x1000, "raw", None, None, 0, "mdi:motion-play-outline"),
    SensorDef("building_pump_power", 0x1003, "div10", UNIT_PERCENT, DEVICE_CLASS_POWER_FACTOR, 1, "mdi:pump"),
    SensorDef("outside_temp", 0x1009, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("building_circuit_flow_split", 0x100A, "raw", "l/h", None, 0, "mdi:pump"),
    SensorDef("hot_water_mode_active", 0x1012, "raw", None, None, 0, "mdi:water-boiler"),
    SensorDef("heat_output", 0x1014, "uraw", UNIT_WATT, DEVICE_CLASS_POWER, 0, "mdi:radiator"),
    SensorDef("requested_flow_temp", 0x1019, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("flow_return_calibration", 0x1109, "d2c", "K", DEVICE_CLASS_TEMPERATURE, 4, "mdi:tune-variant"),
    SensorDef("building_circuit_flow_target", 0x2001, "raw", "l/h", None, 0, "mdi:pump"),
    SensorDef("compressor_speed_max", 0x2002, "div10", "rps", None, 1, "mdi:arrow-collapse-up"),
    SensorDef("compressor_speed_min", 0x2003, "div10", "rps", None, 1, "mdi:arrow-collapse-down"),
    SensorDef("defrost_sequence", 0x2006, "raw", None, None, 0, "mdi:snowflake-alert"),
    SensorDef("compressor_inlet_temp", 0x2007, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("compressor_outlet_temp", 0x2008, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("eev_outlet_temp", 0x2009, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("condensor_outlet_temp", 0x200A, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("air_inlet_temp", 0x200B, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("flow_temp", 0x200C, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("return_temp", 0x200D, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("low_pressure", 0x200E, "div10", "bar", DEVICE_CLASS_PRESSURE, 2, "mdi:gauge"),
    SensorDef("high_pressure", 0x200F, "div10", "bar", DEVICE_CLASS_PRESSURE, 2, "mdi:gauge"),
    SensorDef("compressor_speed", 0x2010, "div10", "rps", None, 1, "mdi:sync"),
    SensorDef("fan1_speed", 0x2011, "raw", "rpm", None, 1, "mdi:fan"),
    SensorDef("water_pressure", 0x2013, "div10", "bar", DEVICE_CLASS_PRESSURE, 2, "mdi:gauge"),
    SensorDef("building_circuit_flow", 0x2014, "raw", "l/h", None, 0, "mdi:pump"),
    SensorDef("run_phase", 0x2015, "raw", None, None, 0, "mdi:state-machine"),
    SensorDef("mains_voltage", 0x201B, "div50", UNIT_VOLT, DEVICE_CLASS_VOLTAGE, 0, "mdi:sine-wave"),
    SensorDef("active_current", 0x201C, "div1000", "A", DEVICE_CLASS_CURRENT, 2, "mdi:current-ac"),
    SensorDef("electric_power_consumption", 0x211B, "raw", UNIT_WATT, DEVICE_CLASS_POWER, 0, "mdi:lightning-bolt"),
    SensorDef("eev_position", 0x2120, "raw", "deg", None, 0, "mdi:valve"),
    SensorDef("compressor_speed_target", 0x2122, "div10", "rps", None, 1, "mdi:sync-circle"),
    SensorDef("fan_speed_target", 0x2123, "raw", "rpm", None, 0, "mdi:fan-clock"),
    SensorDef("condensing_temp", 0x2126, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer-chevron-up"),
    SensorDef("evaporating_temp", 0x2128, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:snowflake-thermometer"),
    SensorDef("subcooling", 0x212A, "d2c", "K", DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("superheat", 0x212C, "d2c", "K", DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("eev_position_status", 0x212D, "div10", UNIT_PERCENT, None, 1, "mdi:valve"),
    SensorDef("defrost_active", 0x2131, "raw", None, None, 0, "mdi:snowflake-melt"),
    SensorDef("derated_temp_ceiling", 0x2137, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:arrow-collapse-down"),
    SensorDef("compressor_slew_limit", 0x213F, "f32", "rps/s", None, 1, "mdi:speedometer-slow"),
    SensorDef("demand_state", 0x2144, "raw", None, None, 0, "mdi:ray-start-end"),
    SensorDef("compressor_speed_stable_time", 0x2145, "uraw", "s", DEVICE_CLASS_DURATION, 0, "mdi:timer-check-outline"),
    SensorDef("fan_target_stable_time", 0x2146, "uraw", "s", DEVICE_CLASS_DURATION, 0, "mdi:fan-clock"),
    SensorDef("defrost_reference_heat_output", 0x2147, "uraw", UNIT_WATT, DEVICE_CLASS_POWER, 0, "mdi:radiator"),
    SensorDef("defrost_reference_attempt", 0x2148, "raw", None, None, 0, "mdi:counter"),
    SensorDef("time_since_defrost", 0x214C, "uraw", "s", DEVICE_CLASS_DURATION, 0, "mdi:timer-sand"),
    SensorDef("demand_window", 0x215C, "raw", None, None, 0, "mdi:timer-lock-outline"),
    SensorDef("defrost_capacity_loss", 0x2160, "f32", UNIT_PERCENT, None, 2, "mdi:snowflake-melt"),
    SensorDef("delta_t", 0x2209, "f32", "K", DEVICE_CLASS_TEMPERATURE, 3, "mdi:delta"),
    SensorDef("lockout_duration", 0x221D, "f32", "s", DEVICE_CLASS_DURATION, 0, "mdi:timer-lock-outline"),
]


@dataclass(frozen=True)
class TextSensorDef:
    key: str
    register: int
    kind: str  # "firmware_version", "compressor_ramp_state" or "serial_number" - see AroThermModbus::TextKind
    icon: str = "mdi:help-circle-outline"


_KIND_CODE = {"firmware_version": TextKind.FIRMWARE_VERSION,
              "compressor_ramp_state": TextKind.COMPRESSOR_RAMP_STATE,
              "serial_number": TextKind.SERIAL_NUMBER}

TEXT_SENSORS = [
    TextSensorDef("serial_number", 0x1203, "serial_number", "mdi:barcode"),
    TextSensorDef("compressor_ramp_state", 0x214E, "compressor_ramp_state", "mdi:chart-bell-curve-cumulative"),
    TextSensorDef("firmware_version", 0x2203, "firmware_version", "mdi:chip"),
]

_BY_KEY = {d.key: d for d in SENSORS + TEXT_SENSORS}
assert len(_BY_KEY) == len(SENSORS) + len(TEXT_SENSORS), "duplicate SensorDef key"


def _sensor_schema(sensor_def: SensorDef):
    kwargs = {"accuracy_decimals": sensor_def.accuracy_decimals, "state_class": STATE_CLASS_MEASUREMENT,
              "icon": sensor_def.icon}
    if sensor_def.unit is not None:
        kwargs["unit_of_measurement"] = sensor_def.unit
    if sensor_def.device_class is not None:
        kwargs["device_class"] = sensor_def.device_class
    return sensor.sensor_schema(**kwargs)


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(AroThermModbus),
            cv.Required(CONF_TIME_ID): cv.use_id(time.RealTimeClock),
            cv.Required(CONF_RX_PIN): cv.int_range(min=0, max=39),
            cv.Optional(CONF_BAUD_RATE, default=19200): cv.int_range(min=1200, max=921600),
            **{cv.Optional(d.key): _sensor_schema(d) for d in SENSORS},
            **{cv.Optional(d.key): text_sensor.text_sensor_schema(icon=d.icon) for d in TEXT_SENSORS},
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_on(["esp32"]),
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_rx_pin(config[CONF_RX_PIN]))
    cg.add(var.set_baud_rate(config[CONF_BAUD_RATE]))

    time_ = await cg.get_variable(config[CONF_TIME_ID])
    cg.add(var.set_time(time_))

    for sensor_def in SENSORS:
        if sensor_def.key in config:
            sens = await sensor.new_sensor(config[sensor_def.key])
            cg.add(var.add_sensor(sensor_def.register, _SCALE_CODE[sensor_def.scale], sens))

    for text_def in TEXT_SENSORS:
        if text_def.key in config:
            sens = await text_sensor.new_text_sensor(config[text_def.key])
            cg.add(var.add_text_sensor(text_def.register, _KIND_CODE[text_def.kind], sens))
