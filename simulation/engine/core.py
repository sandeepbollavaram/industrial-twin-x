"""Shared SimPy engine: one process advances every virtual device.

The engine knows nothing about MQTT. Delivered messages go to a sink callable, so the
same code runs live over a broker and headless in tests and experiments.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import simpy

from modules.edge_computing.policy import EdgePolicy
from modules.telemetry import topics
from simulation.actuators.limits import CommandResult, validate_command
from simulation.devices.machines import (
    AmbientModel,
    Conveyor,
    EnvironmentStation,
    Machine,
    PowerUnit,
    Pump,
    RobotCell,
    RotatingMachine,
    Tank,
)
from simulation.factory.layout import FactorySpec, build_factory
from simulation.network.gateway import VirtualGateway
from simulation.scenarios.catalog import Scenario, ScenarioEvent
from simulation.sensors.models import Sensor

BASE_EPOCH = 1_767_225_600.0  # Fixed origin so headless output is byte-for-byte reproducible.


@dataclass
class Envelope:
    kind: str
    topic: str
    payload: dict[str, Any]
    replayed: bool = False


Sink = Callable[[Envelope, float], None]


def _null_sink(_: Envelope, __: float) -> None:
    return None


class FactorySimulation:
    def __init__(
        self,
        seed: int = 42,
        scenarios: tuple[Scenario, ...] | list[Scenario] = (),
        sink: Sink = _null_sink,
        spec: FactorySpec | None = None,
        telemetry_period_s: float = 5.0,
        edge_enabled: bool = True,
        wall_clock: bool = False,
        ambient_offset_s: float = 8 * 3600,
    ) -> None:
        self.seed = seed
        self.spec = spec or build_factory()
        self.sink = sink
        self.telemetry_period_s = telemetry_period_s
        self.edge_enabled = edge_enabled
        self.wall_clock = wall_clock
        self.env = simpy.Environment()
        self.active_scenario = "normal"

        # Spawn by stable index so adding a consumer of randomness elsewhere cannot
        # shift the stream of any existing component.
        root = np.random.SeedSequence(seed)
        machine_seeds, sensor_seeds, gateway_seeds, ambient_seed = root.spawn(4)
        machine_rngs = machine_seeds.spawn(len(self.spec.machines))
        sensor_rngs = iter(sensor_seeds.spawn(self.spec.sensor_count))
        gateway_rngs = gateway_seeds.spawn(len(self.spec.gateways))

        self.ambient = AmbientModel(np.random.default_rng(ambient_seed), ambient_offset_s)
        self.machines = self._build_machines(machine_rngs)
        self.gateways = {
            g.gateway_id: VirtualGateway(g.gateway_id, np.random.default_rng(s))
            for g, s in zip(self.spec.gateways, gateway_rngs, strict=True)
        }
        self.sensors: dict[str, Sensor] = {}
        for device in self.spec.devices:
            for sensor in device.sensors:
                self.sensors[sensor.sensor_id] = Sensor(
                    sensor, np.random.default_rng(next(sensor_rngs))
                )
        self.sequences: dict[str, int] = defaultdict(int)
        self.isolated_devices: set[str] = set()
        self.edge = {g: EdgePolicy() for g in self.gateways}
        self.edge_samples: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self.edge_actions: list[dict[str, Any]] = []
        self.command_log: list[dict[str, Any]] = []

        self.env.process(self._physics_loop())
        self.env.process(self._telemetry_loop())
        self.env.process(self._network_loop())
        if edge_enabled:
            self.env.process(self._edge_loop())
        for scenario in scenarios:
            self.schedule(scenario)

    def _build_machines(self, rngs: list[np.random.SeedSequence]) -> dict[str, Machine]:
        machines: dict[str, Machine] = {}
        specs = list(zip(self.spec.machines, rngs, strict=True))
        rotating = {
            "motor": RotatingMachine,
            "conveyor": Conveyor,
            "robot": RobotCell,
            "pump": Pump,
        }
        for spec, seq in specs:
            if spec.kind in rotating:
                machines[spec.machine_id] = rotating[spec.kind](spec, np.random.default_rng(seq))
        for spec, seq in specs:
            rng = np.random.default_rng(seq)
            group = [
                m
                for m in machines.values()
                if isinstance(m, RotatingMachine) and m.spec.group == spec.group
            ]
            if spec.kind == "tank":
                pumps = [m for m in group if isinstance(m, Pump)]
                machines[spec.machine_id] = Tank(spec, rng, pumps)
            elif spec.kind == "power":
                served = "A" if spec.machine_id.startswith("PDU-C01") else "B"
                loads = [m for m in group if m.spec.zone_id == served]
                machines[spec.machine_id] = PowerUnit(spec, rng, loads)
            elif spec.kind == "environment":
                machines[spec.machine_id] = EnvironmentStation(spec, rng)
        return machines

    # ------------------------------------------------------------------ scheduling

    def schedule(self, scenario: Scenario, relative: bool = False) -> None:
        offset = self.env.now if relative else 0.0
        self.active_scenario = scenario.scenario_id
        for event in scenario.events:
            self.env.process(self._fire(event, offset))

    def _fire(self, event: ScenarioEvent, offset: float):
        yield self.env.timeout(max(0.0, event.at_s + offset - self.env.now))
        self._apply_event(event)

    def _apply_event(self, event: ScenarioEvent) -> None:
        p = event.params
        match event.action:
            case "set_wear_rate":
                self.machines[event.target].wear_rate = p["rate"]  # type: ignore[attr-defined]
            case "set_cooling":
                self.machines[event.target].cooling_target = p["factor"]  # type: ignore[attr-defined]
            case "set_leak":
                self.machines[event.target].leak_target = p["fraction"]  # type: ignore[attr-defined]
            case "gateway_process":
                self.gateways[event.target].process_up = p["up"]
            case "gateway_link":
                self.gateways[event.target].link_up = p["up"]
            case "gateway_network":
                self.gateways[event.target].extra_latency_s = p["latency"]
                self.gateways[event.target].loss_prob = p["loss"]
            case "sensor_bias":
                sensor = self.sensors[event.target]
                sensor.bias_target = p["bias"]
                sensor.bias_ramp_per_s = p["ramp"]
            case "sensor_freeze":
                self.sensors[event.target].freeze_requested = True
            case _:
                raise ValueError(f"unknown scenario action {event.action}")

    # ------------------------------------------------------------------ processes

    def _physics_loop(self):
        ordered = sorted(
            self.machines.values(), key=lambda m: m.spec.kind in ("tank", "power", "environment")
        )
        while True:
            t = self.env.now
            self.ambient.step(t, 1.0)
            for machine in ordered:
                machine.step(t, 1.0, self.ambient)
            for sensor in self.sensors.values():
                sensor.advance_attack(1.0)
            yield self.env.timeout(1.0)

    def _timestamp(self) -> float:
        return time.time() if self.wall_clock else BASE_EPOCH + self.env.now

    def _telemetry_loop(self):
        period = int(self.telemetry_period_s)
        devices = self.spec.devices
        while True:
            tick = int(self.env.now)
            # Stagger devices across the period so the broker sees a smooth rate.
            for device in devices:
                if device.index % period == tick % period:
                    self._publish_device(device)
            yield self.env.timeout(1.0)

    def _publish_device(self, device) -> None:
        machine = self.machines[device.machine_id]
        truth = machine.signals()
        readings = {
            s.signal: self.sensors[s.sensor_id].read(truth[s.signal]) for s in device.sensors
        }
        gateway = self.gateways[device.gateway_id]
        if gateway.process_up:
            samples = self.edge_samples[device.machine_id]
            for signal, value in readings.items():
                samples[signal][device.device_id] = value
        if device.device_id in self.isolated_devices:
            return
        sequence = self.sequences[device.device_id]
        self.sequences[device.device_id] = sequence + 1
        payload = {
            "schema_version": "1.0",
            "factory_id": self.spec.factory_id,
            "zone_id": device.zone_id,
            "machine_id": device.machine_id,
            "gateway_id": device.gateway_id,
            "device_id": device.device_id,
            "timestamp": self._timestamp(),
            "sim_time": float(self.env.now),
            "sequence": sequence,
            "scenario_id": self.active_scenario,
            "status": machine.status,
            "readings": readings,
        }
        topic = topics.telemetry(self.spec.factory_id, device.zone_id, device.device_id)
        gateway.submit(Envelope("telemetry", topic, payload), self.env.now)

    def _network_loop(self):
        gateways = list(self.gateways.values())
        last_report = 0.0
        while True:
            now = self.env.now
            for gateway in gateways:
                for arrival, envelope in gateway.tick(now):
                    if envelope.replayed:
                        envelope.payload["replayed"] = True
                    self.sink(envelope, arrival)
            if now - last_report >= 5.0:
                last_report = now
                self.sink(
                    Envelope(
                        "network", topics.network(self.spec.factory_id), self.network_snapshot()
                    ),
                    now,
                )
            yield self.env.timeout(1.0)

    def _edge_loop(self):
        while True:
            yield self.env.timeout(self.telemetry_period_s)
            for machine_id, samples in self.edge_samples.items():
                machine = self.machines[machine_id]
                if not isinstance(machine, RotatingMachine):
                    continue
                gateway = self.gateways[machine.spec.gateway_id]
                if not gateway.process_up:
                    continue
                medians = {s: statistics.median(v.values()) for s, v in samples.items() if v}
                votes = {s: len(v) for s, v in samples.items()}
                for action in self.edge[gateway.gateway_id].evaluate(machine_id, medians, votes):
                    result = machine.apply_command(action.command, action.value)
                    record = {
                        "sim_time": float(self.env.now),
                        "machine_id": machine_id,
                        "command": action.command,
                        "value": action.value,
                        "reason": action.reason,
                        "accepted": result.accepted,
                    }
                    self.edge_actions.append(record)
                    severity = "critical" if action.command == "stop" else "warning"
                    gateway.submit(
                        Envelope(
                            "alert",
                            topics.alerts(self.spec.factory_id),
                            {
                                "schema_version": "1.0",
                                "source": gateway.gateway_id,
                                "machine_id": machine_id,
                                "sim_time": float(self.env.now),
                                "severity": severity,
                                "code": f"edge_{action.command}",
                                "message": action.reason,
                            },
                        ),
                        self.env.now,
                    )

    # ------------------------------------------------------------------ commands

    def submit_command(
        self, device_id: str, command: str, value: float | None = None, command_id: str = ""
    ) -> CommandResult:
        """A command arriving from central. It needs a working uplink to reach the device."""
        device = self.spec.device(device_id)
        gateway = self.gateways[device.gateway_id]
        if not (gateway.process_up and gateway.link_up):
            result = CommandResult(False, f"{gateway.gateway_id} unreachable")
        else:
            check = validate_command(command, value)
            if not check.accepted:
                result = check
            elif command == "isolate":
                self.isolated_devices.add(device_id)
                result = CommandResult(True, "device isolated")
            elif command == "release":
                self.isolated_devices.discard(device_id)
                result = CommandResult(True, "device released")
            else:
                machine = self.machines[device.machine_id]
                result = machine.apply_command(command, value)
                if result.accepted and command in ("repair", "start"):
                    self.edge[gateway.gateway_id].clear(device.machine_id)
                    if command == "repair":
                        self._clear_sensor_attacks(device.machine_id)
        self.command_log.append(
            {
                "sim_time": float(self.env.now),
                "device_id": device_id,
                "command": command,
                "value": value,
                "accepted": result.accepted,
                "detail": result.detail,
            }
        )
        gateway.submit(
            Envelope(
                "status",
                topics.status(self.spec.factory_id, device_id),
                {
                    "schema_version": "1.0",
                    "device_id": device_id,
                    "machine_id": device.machine_id,
                    "sim_time": float(self.env.now),
                    "status": self.machines[device.machine_id].status,
                    "detail": result.detail,
                    "command_id": command_id,
                    "accepted": result.accepted,
                },
            ),
            self.env.now,
        )
        return result

    def _clear_sensor_attacks(self, machine_id: str) -> None:
        for sensor_id, sensor in self.sensors.items():
            if sensor_id.startswith(f"{machine_id}-"):
                sensor.clear_attack()

    # ------------------------------------------------------------------ inspection

    def network_snapshot(self) -> dict[str, Any]:
        return {
            "sim_time": float(self.env.now),
            "gateways": [
                {
                    "gateway_id": g.gateway_id,
                    "state": g.state,
                    "backlog": g.backlog,
                    "submitted": g.stats.submitted,
                    "delivered": g.stats.delivered,
                    "lost_network": g.stats.lost_network,
                    "lost_outage": g.stats.lost_outage,
                    "lost_overflow": g.stats.lost_overflow,
                    "replayed": g.stats.replayed,
                    "extra_latency_s": g.extra_latency_s,
                    "loss_prob": g.loss_prob,
                }
                for g in self.gateways.values()
            ],
        }

    def truth(self, machine_id: str) -> dict[str, Any]:
        """Hidden ground truth, for evaluation only."""
        return self.machines[machine_id].truth()

    def run(self, until: float) -> None:
        self.env.run(until=until)
