"""Lumped-parameter physical models, integrated with explicit Euler at 1 s.

These are simplified engineering models chosen for plausible behaviour, not models
calibrated against a specific real machine.
"""

from __future__ import annotations

import math

import numpy as np

from simulation.actuators.limits import CommandResult, validate_command
from simulation.factory.layout import MachineSpec

SQRT3 = math.sqrt(3.0)
WINDING_FAILURE_C = 140.0
VIBRATION_BASE = 0.9


class AmbientModel:
    """Diurnal hall temperature and humidity with slow stochastic drift."""

    def __init__(self, rng: np.random.Generator, offset_s: float = 8 * 3600) -> None:
        self.rng = rng
        self.offset_s = offset_s
        self.drift = 0.0
        self.temp_c = 25.0
        self.humidity_pct = 50.0
        self.extra_c = 0.0

    def step(self, t: float, dt: float) -> None:
        self.drift += -self.drift * dt / 1800.0 + 0.01 * math.sqrt(dt) * self.rng.normal()
        phase = 2 * math.pi * (t + self.offset_s) / 86400.0
        self.temp_c = 25.0 + 4.0 * math.sin(phase - math.pi / 2) + self.drift + self.extra_c
        self.humidity_pct = float(np.clip(50.0 - 1.5 * (self.temp_c - 25.0), 5.0, 95.0))


class Machine:
    def __init__(self, spec: MachineSpec, rng: np.random.Generator) -> None:
        self.spec = spec
        self.rng = rng
        self.running = True
        self.failed = False
        self.failure_reason: str | None = None
        self.output_units = 0.0
        self.downtime_s = 0.0

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        return "running" if self.running else "stopped"

    def step(self, t: float, dt: float, ambient: AmbientModel) -> None:
        raise NotImplementedError

    def signals(self) -> dict[str, float]:
        raise NotImplementedError

    def apply_command(self, name: str, value: float | None) -> CommandResult:
        return CommandResult(False, f"{name} not supported by {self.spec.kind}")

    def truth(self) -> dict[str, float | str | bool]:
        return {"status": self.status, "failed": self.failed}


class RotatingMachine(Machine):
    """Induction-motor-driven asset with thermal and bearing wear state."""

    def __init__(self, spec: MachineSpec, rng: np.random.Generator) -> None:
        super().__init__(spec, rng)
        self.speed_cmd = 1.0
        self.speed = 1.0
        self.load_noise = 0.0
        self.load = self._base_load(0.0)
        self.wear = float(rng.uniform(0.0, 0.05))
        self.wear_rate = 0.0
        self.cooling = 1.0
        self.cooling_target = 1.0
        self.cooling_ramp_s = 300.0
        self.h = 30.0 * spec.rated_power_kw / 15.0
        self.thermal_c = 9000.0 * spec.rated_power_kw / 15.0
        self.efficiency = 0.90
        self.voltage = 400.0
        self.power_factor = 0.86
        self.power_kw = 0.0
        self.current_a = 0.0
        self.winding_temp = 25.0 + self._loss_w() / self.h
        self.bearing_temp = 25.0 + 18.0
        self._update_electrical()

    def _base_load(self, t: float) -> float:
        return 0.70 + 0.05 * math.sin(2 * math.pi * t / 1800.0)

    def _shaft_fraction(self) -> float:
        return self.load * self.speed * (1.0 + 0.2 * self.wear)

    def _loss_w(self) -> float:
        rated_w = self.spec.rated_power_kw * 1000.0
        fixed = 0.027 * rated_w * self.speed
        copper = 0.085 * rated_w * self._shaft_fraction() ** 2
        return fixed + copper

    def _update_electrical(self) -> None:
        if self.running and not self.failed:
            self.power_kw = self.spec.rated_power_kw * self._shaft_fraction() / self.efficiency
        else:
            self.power_kw = 0.0
        self.current_a = self.power_kw * 1000.0 / (SQRT3 * self.voltage * self.power_factor)

    def step(self, t: float, dt: float, ambient: AmbientModel) -> None:
        self.load_noise += -self.load_noise * dt / 120.0 + 0.002 * math.sqrt(dt) * self.rng.normal()
        self.load = float(np.clip(self._base_load(t) + self.load_noise, 0.05, 1.2))

        target = self.speed_cmd if self.running and not self.failed else 0.0
        self.speed += (target - self.speed) * min(1.0, dt / 8.0)
        self._update_electrical()

        ramp = dt / self.cooling_ramp_s
        self.cooling += float(np.clip(self.cooling_target - self.cooling, -ramp, ramp))
        loss = self._loss_w() if self.power_kw > 0 else 0.0
        dtemp = loss - self.h * self.cooling * (self.winding_temp - ambient.temp_c)
        self.winding_temp += dtemp / self.thermal_c * dt

        bearing_target = ambient.temp_c + 18.0 * self.speed + 45.0 * self.wear * self.speed
        self.bearing_temp += (bearing_target - self.bearing_temp) * dt / 400.0

        accel = 1.0 + 4.0 * self.wear
        self.wear += (1e-8 + self.wear_rate * accel) * self.speed**2 * dt
        self.wear = min(self.wear, 1.0)

        if not self.failed:
            if self.wear >= 1.0:
                self._fail("bearing_seizure")
            elif self.winding_temp >= WINDING_FAILURE_C:
                self._fail("winding_insulation_failure")
        if self.running and not self.failed:
            self.output_units += self.speed * dt
        else:
            self.downtime_s += dt

    def _fail(self, reason: str) -> None:
        self.failed = True
        self.failure_reason = reason

    def vibration(self) -> float:
        s = self.speed
        return VIBRATION_BASE * min(s * 4, 1.0) + 0.7 * s**2 + 8.5 * self.wear**2 * s

    def health_estimate(self) -> float:
        # On-board self-diagnostic: derived from observable quantities, never hidden wear.
        vib_excess = max(0.0, self.vibration() - 2.0)
        temp_excess = max(0.0, self.winding_temp - 90.0)
        return float(np.clip(100.0 - 8.0 * vib_excess - 1.2 * temp_excess, 0.0, 100.0))

    def signals(self) -> dict[str, float]:
        return {
            "rpm": self.speed * self.spec.rated_rpm,
            "current_a": self.current_a,
            "power_kw": self.power_kw,
            "winding_temp_c": self.winding_temp,
            "bearing_temp_c": self.bearing_temp,
            "vibration_mm_s": self.vibration(),
            "health_pct": self.health_estimate(),
        }

    def apply_command(self, name: str, value: float | None) -> CommandResult:
        check = validate_command(name, value)
        if not check.accepted:
            return check
        if name == "repair":
            self.repair()
        elif self.failed:
            return CommandResult(False, "machine failed; repair required")
        elif name == "set_speed":
            assert value is not None
            self.speed_cmd = value
            self.running = True
        elif name == "stop":
            self.running = False
        elif name == "start":
            self.running = True
        else:
            return CommandResult(False, f"{name} not supported by {self.spec.kind}")
        return CommandResult(True, "applied")

    def repair(self) -> None:
        self.wear = 0.02
        self.wear_rate = 0.0
        self.cooling = self.cooling_target = 1.0
        self.failed = False
        self.failure_reason = None
        self.running = True
        self.speed_cmd = 1.0

    def truth(self) -> dict[str, float | str | bool]:
        return {
            "status": self.status,
            "failed": self.failed,
            "wear": self.wear,
            "winding_temp": self.winding_temp,
            "cooling": self.cooling,
            "speed": self.speed,
            "output_units": self.output_units,
            "downtime_s": self.downtime_s,
        }


class Conveyor(RotatingMachine):
    def _base_load(self, t: float) -> float:
        # Product batches enter the belt on a fixed cycle.
        return 0.72 if (t % 240.0) < 150.0 else 0.50


class RobotCell(RotatingMachine):
    def _base_load(self, t: float) -> float:
        return 0.40 + 0.35 * max(0.0, math.sin(2 * math.pi * t / 60.0))


class Pump(RotatingMachine):
    """Centrifugal pump following the affinity laws, with a discharge-side leak."""

    def __init__(self, spec: MachineSpec, rng: np.random.Generator) -> None:
        self.rated_flow = 120.0
        self.leak = 0.0
        self.leak_target = 0.0
        self.leak_ramp_s = 600.0
        super().__init__(spec, rng)

    def _base_load(self, t: float) -> float:
        return 0.68

    def _shaft_fraction(self) -> float:
        return self.load * self.speed**3 * (1.0 + 0.2 * self.wear) * (1.0 + 0.35 * self.leak)

    def step(self, t: float, dt: float, ambient: AmbientModel) -> None:
        ramp = dt / self.leak_ramp_s
        self.leak += float(np.clip(self.leak_target - self.leak, -ramp, ramp))
        super().step(t, dt, ambient)

    @property
    def suction_flow(self) -> float:
        return self.rated_flow * self.speed * (1.0 + 0.5 * self.leak)

    @property
    def delivered_flow(self) -> float:
        return self.suction_flow * (1.0 - self.leak)

    def pressure(self) -> float:
        head = 6.0 * self.speed**2 - 1.5 * (self.suction_flow / self.rated_flow) ** 2
        return max(0.0, head * (1.0 - 0.9 * self.leak))

    def signals(self) -> dict[str, float]:
        values = super().signals()
        values.update(
            flow_m3h=self.delivered_flow,
            suction_flow_m3h=self.suction_flow,
            pressure_bar=self.pressure(),
        )
        return values

    def repair(self) -> None:
        super().repair()
        self.leak = self.leak_target = 0.0

    def truth(self) -> dict[str, float | str | bool]:
        values = super().truth()
        values["leak"] = self.leak
        return values


class Tank(Machine):
    """Mass balance on a vertical tank with a proportional level controller."""

    def __init__(self, spec: MachineSpec, rng: np.random.Generator, pumps: list[Pump]) -> None:
        super().__init__(spec, rng)
        self.pumps = pumps
        self.volume_m3 = 400.0
        self.capacity_m3 = 400.0 / 0.6
        self.height_m = 8.0
        self.valve = 0.5
        self.out_flow = 0.0
        self.fluid_temp = 22.0

    @property
    def level_pct(self) -> float:
        return 100.0 * self.volume_m3 / self.capacity_m3

    def step(self, t: float, dt: float, ambient: AmbientModel) -> None:
        inflow = sum(p.delivered_flow for p in self.pumps)
        self.valve = float(np.clip(0.5 + 0.04 * (self.level_pct - 60.0), 0.0, 1.0))
        self.out_flow = self.valve * 2.0 * sum(p.rated_flow for p in self.pumps)
        self.volume_m3 += (inflow - self.out_flow) * dt / 3600.0
        self.volume_m3 = float(np.clip(self.volume_m3, 0.0, self.capacity_m3))
        self.fluid_temp += (ambient.temp_c - 3.0 - self.fluid_temp) * dt / 7200.0

    def signals(self) -> dict[str, float]:
        return {
            "level_pct": self.level_pct,
            "flow_m3h": self.out_flow,
            "pressure_bar": 0.0981 * self.height_m * self.level_pct / 100.0,
            "valve_pct": 100.0 * self.valve,
            "fluid_temp_c": self.fluid_temp,
        }


class PowerUnit(Machine):
    """Aggregates downstream load; bus voltage droops with current."""

    def __init__(
        self, spec: MachineSpec, rng: np.random.Generator, loads: list[RotatingMachine]
    ) -> None:
        super().__init__(spec, rng)
        self.loads = loads
        self.base_kw = 3.0
        self.power_kw = 0.0
        self.current_a = 0.0
        self.voltage = 400.0
        self.transformer_temp = 45.0

    def step(self, t: float, dt: float, ambient: AmbientModel) -> None:
        self.power_kw = self.base_kw + sum(m.power_kw for m in self.loads)
        self.voltage = 400.0 - 0.06 * self.current_a
        self.current_a = self.power_kw * 1000.0 / (SQRT3 * self.voltage * 0.9)
        target = ambient.temp_c + 12.0 + 0.0012 * self.current_a**2 * 0.05
        self.transformer_temp += (target - self.transformer_temp) * dt / 1800.0

    def signals(self) -> dict[str, float]:
        return {
            "current_a": self.current_a,
            "voltage_v": self.voltage,
            "power_kw": self.power_kw,
            "transformer_temp_c": self.transformer_temp,
            "health_pct": 100.0 - max(0.0, self.transformer_temp - 85.0),
        }


class EnvironmentStation(Machine):
    def __init__(self, spec: MachineSpec, rng: np.random.Generator) -> None:
        super().__init__(spec, rng)
        self.air_temp = 25.0
        self.humidity = 50.0
        self.fan_kw = 1.5

    def step(self, t: float, dt: float, ambient: AmbientModel) -> None:
        self.air_temp = ambient.temp_c
        self.humidity = ambient.humidity_pct
        self.fan_kw = float(np.clip(1.5 + 0.2 * (self.air_temp - 25.0), 0.5, 4.0))

    def signals(self) -> dict[str, float]:
        return {
            "air_temp_c": self.air_temp,
            "humidity_pct": self.humidity,
            "current_a": self.fan_kw * 1000.0 / (SQRT3 * 400.0 * 0.85),
            "power_kw": self.fan_kw,
        }
