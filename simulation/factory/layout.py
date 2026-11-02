"""Static factory description: zones, gateways, machines, devices and sensors.

Scale 1 gives 3 zones, 5 gateways, 10 machines, 100 devices and 300 sensors.
Scale 5 gives the 500-device target. Devices are plain data, not processes.
"""

from __future__ import annotations

from dataclasses import dataclass

DEVICES_PER_MACHINE = 10
SENSORS_PER_DEVICE = 3
ROTATING_KINDS = frozenset({"motor", "conveyor", "robot", "pump"})


@dataclass(frozen=True)
class SignalSpec:
    unit: str
    noise_sigma: float
    resolution: float
    low: float
    high: float


SIGNALS: dict[str, SignalSpec] = {
    "rpm": SignalSpec("rpm", 2.0, 0.1, 0, 4000),
    "current_a": SignalSpec("A", 0.08, 0.01, 0, 2000),
    "power_kw": SignalSpec("kW", 0.05, 0.01, 0, 2000),
    "winding_temp_c": SignalSpec("degC", 0.25, 0.01, -40, 250),
    "bearing_temp_c": SignalSpec("degC", 0.25, 0.01, -40, 250),
    "vibration_mm_s": SignalSpec("mm/s", 0.05, 0.001, 0, 60),
    "health_pct": SignalSpec("%", 0.3, 0.1, 0, 100),
    "flow_m3h": SignalSpec("m3/h", 0.4, 0.01, 0, 1000),
    "suction_flow_m3h": SignalSpec("m3/h", 0.4, 0.01, 0, 1000),
    "pressure_bar": SignalSpec("bar", 0.02, 0.001, 0, 25),
    "level_pct": SignalSpec("%", 0.1, 0.01, 0, 100),
    "valve_pct": SignalSpec("%", 0.1, 0.1, 0, 100),
    "fluid_temp_c": SignalSpec("degC", 0.1, 0.01, -10, 120),
    "voltage_v": SignalSpec("V", 0.4, 0.1, 0, 500),
    "transformer_temp_c": SignalSpec("degC", 0.2, 0.01, -40, 200),
    "air_temp_c": SignalSpec("degC", 0.1, 0.01, -40, 80),
    "humidity_pct": SignalSpec("%", 0.3, 0.1, 0, 100),
}

ROTATING_SIGNALS = (
    "rpm",
    "current_a",
    "power_kw",
    "winding_temp_c",
    "bearing_temp_c",
    "vibration_mm_s",
    "health_pct",
)
KIND_SIGNALS: dict[str, tuple[str, ...]] = {
    "motor": ROTATING_SIGNALS,
    "conveyor": ROTATING_SIGNALS,
    "robot": ROTATING_SIGNALS,
    "pump": ROTATING_SIGNALS + ("flow_m3h", "suction_flow_m3h", "pressure_bar"),
    "tank": ("level_pct", "flow_m3h", "pressure_bar", "valve_pct", "fluid_temp_c"),
    "power": ("current_a", "voltage_v", "power_kw", "transformer_temp_c", "health_pct"),
    "environment": ("air_temp_c", "humidity_pct", "current_a", "power_kw"),
}
ROLES = (
    "controller",
    "drive",
    "meter",
    "node-a",
    "node-b",
    "node-c",
    "node-d",
    "node-e",
    "node-f",
    "monitor",
)


@dataclass(frozen=True)
class SensorSpec:
    sensor_id: str
    device_id: str
    signal: str


@dataclass(frozen=True)
class DeviceSpec:
    device_id: str
    machine_id: str
    zone_id: str
    gateway_id: str
    role: str
    index: int
    sensors: tuple[SensorSpec, ...]


@dataclass(frozen=True)
class MachineSpec:
    machine_id: str
    name: str
    kind: str
    zone_id: str
    gateway_id: str
    rated_rpm: float
    rated_power_kw: float
    position: tuple[float, float]
    group: int


@dataclass(frozen=True)
class GatewaySpec:
    gateway_id: str
    zone_id: str


@dataclass(frozen=True)
class ZoneSpec:
    zone_id: str
    name: str


@dataclass(frozen=True)
class FactorySpec:
    factory_id: str
    zones: tuple[ZoneSpec, ...]
    gateways: tuple[GatewaySpec, ...]
    machines: tuple[MachineSpec, ...]
    devices: tuple[DeviceSpec, ...]

    def machine(self, machine_id: str) -> MachineSpec:
        return next(m for m in self.machines if m.machine_id == machine_id)

    def device(self, device_id: str) -> DeviceSpec:
        return next(d for d in self.devices if d.device_id == device_id)

    def controller_of(self, machine_id: str) -> str:
        return f"{machine_id}-controller"

    @property
    def sensor_count(self) -> int:
        return sum(len(d.sensors) for d in self.devices)


# code, name, kind, zone, gateway suffix, rated rpm, rated kW, x, z
_TEMPLATE = (
    ("MTR-A01", "Main Drive Motor 1", "motor", "A", "A1", 1480, 15, -14, -5),
    ("MTR-A02", "Main Drive Motor 2", "motor", "A", "A1", 1480, 15, -14, 5),
    ("CNV-A03", "Assembly Conveyor", "conveyor", "A", "A2", 960, 7.5, -7, -5),
    ("ROB-A04", "Welding Robot Cell", "robot", "A", "A2", 2800, 5.5, -7, 5),
    ("PMP-B01", "Feed Pump 1", "pump", "B", "B1", 2900, 22, 2, -5),
    ("PMP-B02", "Feed Pump 2", "pump", "B", "B1", 2900, 22, 2, 5),
    ("TNK-B03", "Process Water Tank", "tank", "B", "B1", 0, 0, 8, 0),
    ("PDU-C01", "Distribution Unit Zone A", "power", "C", "C1", 0, 0, 15, -5),
    ("PDU-C02", "Distribution Unit Zone B", "power", "C", "C1", 0, 0, 15, 5),
    ("ENV-C03", "Environmental Station", "environment", "C", "C2", 0, 0, 20, 0),
)
_ZONES = (
    ZoneSpec("A", "Manufacturing"),
    ZoneSpec("B", "Pumping and Fluid Systems"),
    ZoneSpec("C", "Power and Environmental Monitoring"),
)
_GATEWAYS = (("A1", "A"), ("A2", "A"), ("B1", "B"), ("C1", "C"), ("C2", "C"))


def _suffix(group: int) -> str:
    return "" if group == 0 else f"-S{group + 1}"


def build_factory(scale: int = 1, factory_id: str = "plant-01") -> FactorySpec:
    if scale < 1:
        raise ValueError("scale must be at least 1")
    gateways: list[GatewaySpec] = []
    machines: list[MachineSpec] = []
    devices: list[DeviceSpec] = []
    device_index = 0
    for group in range(scale):
        suffix = _suffix(group)
        gateways.extend(GatewaySpec(f"GW-{g}{suffix}", z) for g, z in _GATEWAYS)
        for code, name, kind, zone, gw, rpm, kw, x, z in _TEMPLATE:
            machine_id = f"{code}{suffix}"
            gateway_id = f"GW-{gw}{suffix}"
            machines.append(
                MachineSpec(
                    machine_id,
                    name,
                    kind,
                    zone,
                    gateway_id,
                    rpm,
                    kw,
                    (float(x), float(z) + 16.0 * group),
                    group,
                )
            )
            signals = KIND_SIGNALS[kind]
            for i, role in enumerate(ROLES):
                device_id = f"{machine_id}-{role}"
                # Rotating assignment gives every signal redundant sensors on separate
                # devices, which the integrity checks and edge voting depend on.
                chosen = [
                    signals[(i * SENSORS_PER_DEVICE + j) % len(signals)]
                    for j in range(SENSORS_PER_DEVICE)
                ]
                sensors = tuple(SensorSpec(f"{device_id}.{s}", device_id, s) for s in chosen)
                devices.append(
                    DeviceSpec(device_id, machine_id, zone, gateway_id, role, device_index, sensors)
                )
                device_index += 1
    return FactorySpec(factory_id, _ZONES, tuple(gateways), tuple(machines), tuple(devices))
