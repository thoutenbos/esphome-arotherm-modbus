from __future__ import annotations

from dataclasses import dataclass

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor, time
from esphome.const import (
    CONF_ID,
    CONF_TIME_ID,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    UNIT_CELSIUS,
    UNIT_PERCENT,
    UNIT_WATT,
)

CODEOWNERS = ["@thoutenbos"]
DEPENDENCIES = ["time"]
AUTO_LOAD = ["sensor"]
MULTI_CONF = True

arotherm_modbus_ns = cg.esphome_ns.namespace("arotherm_modbus")
AroThermModbus = arotherm_modbus_ns.class_("AroThermModbus", cg.Component)
Scale = arotherm_modbus_ns.enum("AroThermModbus::Scale", is_class=True)

CONF_RX_PIN = "rx_pin"
CONF_BAUD_RATE = "baud_rate"


@dataclass(frozen=True)
class SensorDef:
    key: str
    register: int
    scale: str  # "raw", "div10", or "d2c" - see AroThermModbus::Scale
    unit: str | None = None
    device_class: str | None = None
    accuracy_decimals: int = 2
    icon: str = "mdi:help-circle-outline"


_SCALE_CODE = {"raw": Scale.RAW, "div10": Scale.DIV10, "d2c": Scale.D2C}

SENSORS = [
    # 0x2000 block (34-register read response)
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

    # 0x2100 block (98-register read response)
    SensorDef("electric_power_consumption", 0x211B, "raw", UNIT_WATT, DEVICE_CLASS_POWER, 0, "mdi:lightning-bolt"),
    SensorDef("eev_position", 0x2120, "raw", "deg", None, 0, "mdi:valve"),
    SensorDef("compressor_speed_target", 0x2122, "div10", "rps", None, 1, "mdi:sync-circle"),
    SensorDef("subcooling", 0x212A, "d2c", "K", DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("superheat", 0x212C, "d2c", "K", DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("eev_position_status", 0x212D, "div10", UNIT_PERCENT, None, 1, "mdi:valve"),

    # 0x1000 block (26-register write request)
    SensorDef("demand_mode", 0x1000, "raw", None, None, 0, "mdi:motion-play-outline"),
    SensorDef("building_pump_power", 0x1003, "div10", UNIT_PERCENT, DEVICE_CLASS_POWER_FACTOR, 1, "mdi:pump"),
    SensorDef("outside_temp", 0x1009, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
    SensorDef("requested_flow_temp", 0x1019, "d2c", UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, 2, "mdi:thermometer"),
]

_BY_KEY = {d.key: d for d in SENSORS}
assert len(_BY_KEY) == len(SENSORS), "duplicate SensorDef key"


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
