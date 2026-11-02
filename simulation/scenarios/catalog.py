"""Contained, scripted scenarios. Every fault exists only inside the simulator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScenarioEvent:
    at_s: float
    action: str
    target: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    events: tuple[ScenarioEvent, ...]
    # Ground truth for evaluation; never published in telemetry.
    fault_label: str = "normal"
    fault_machine: str | None = None
    onset_s: float | None = None


def normal(**_: Any) -> Scenario:
    return Scenario("normal", "No injected fault.", ())


def bearing_degradation(
    machine: str = "MTR-A01", at_s: float = 600, severity: float = 1.0
) -> Scenario:
    return Scenario(
        "bearing_degradation",
        "Bearing wear accelerates; vibration and bearing temperature rise.",
        (ScenarioEvent(at_s, "set_wear_rate", machine, {"rate": 1.5e-4 * severity}),),
        "bearing_wear",
        machine,
        at_s,
    )


def motor_overheating(
    machine: str = "MTR-A02", at_s: float = 600, severity: float = 1.0
) -> Scenario:
    return Scenario(
        "motor_overheating",
        "Cooling degrades (blocked fan or duct) and winding temperature climbs.",
        (ScenarioEvent(at_s, "set_cooling", machine, {"factor": 0.28 / severity}),),
        "overheating",
        machine,
        at_s,
    )


def pump_leakage(machine: str = "PMP-B01", at_s: float = 600, severity: float = 1.0) -> Scenario:
    return Scenario(
        "pump_leakage",
        "A discharge-side leak opens; pressure and delivered flow fall.",
        (ScenarioEvent(at_s, "set_leak", machine, {"fraction": 0.35 * severity}),),
        "pump_leak",
        machine,
        at_s,
    )


def gateway_outage(
    gateway: str = "GW-A1", at_s: float = 600, duration_s: float = 300, **_: Any
) -> Scenario:
    return Scenario(
        "gateway_outage",
        "Gateway process fails. Telemetry is lost and edge policies stop for its machines.",
        (
            ScenarioEvent(at_s, "gateway_process", gateway, {"up": False}),
            ScenarioEvent(at_s + duration_s, "gateway_process", gateway, {"up": True}),
        ),
        onset_s=at_s,
    )


def network_degradation(
    gateway: str = "GW-B1",
    at_s: float = 600,
    duration_s: float = 600,
    latency_s: float = 0.8,
    loss: float = 0.10,
    **_: Any,
) -> Scenario:
    return Scenario(
        "network_degradation",
        "Uplink suffers added latency and packet loss.",
        (
            ScenarioEvent(at_s, "gateway_network", gateway, {"latency": latency_s, "loss": loss}),
            ScenarioEvent(at_s + duration_s, "gateway_network", gateway, {"latency": 0, "loss": 0}),
        ),
        onset_s=at_s,
    )


def sensor_manipulation(
    device: str = "MTR-A01-node-a", signal: str = "winding_temp_c", at_s: float = 600, **_: Any
) -> Scenario:
    return Scenario(
        "sensor_manipulation",
        "One sensor reports a falsely rising value, simulating tampered data.",
        (ScenarioEvent(at_s, "sensor_bias", f"{device}.{signal}", {"bias": 60.0, "ramp": 0.2}),),
        "sensor_tamper",
        device.rsplit("-", 2)[0],
        at_s,
    )


def sensor_replay(
    device: str = "MTR-A01-node-a", signal: str = "winding_temp_c", at_s: float = 600, **_: Any
) -> Scenario:
    return Scenario(
        "sensor_replay",
        "One sensor repeats a frozen value, simulating a replay attack.",
        (ScenarioEvent(at_s, "sensor_freeze", f"{device}.{signal}"),),
        "sensor_tamper",
        device.rsplit("-", 2)[0],
        at_s,
    )


def central_disconnection(at_s: float = 600, duration_s: float = 600, **_: Any) -> Scenario:
    gateways = ("GW-A1", "GW-A2", "GW-B1", "GW-C1", "GW-C2")
    events = []
    for gateway in gateways:
        events.append(ScenarioEvent(at_s, "gateway_link", gateway, {"up": False}))
        events.append(ScenarioEvent(at_s + duration_s, "gateway_link", gateway, {"up": True}))
    return Scenario(
        "central_disconnection",
        "Central services are unreachable. Gateways run edge policies and buffer telemetry.",
        tuple(sorted(events, key=lambda e: e.at_s)),
        onset_s=at_s,
    )


def telemetry_backlog(
    gateway: str = "GW-A1", at_s: float = 600, duration_s: float = 900, **_: Any
) -> Scenario:
    return Scenario(
        "telemetry_backlog",
        "A long uplink loss builds a backlog that is flushed at a bounded rate on recovery.",
        (
            ScenarioEvent(at_s, "gateway_link", gateway, {"up": False}),
            ScenarioEvent(at_s + duration_s, "gateway_link", gateway, {"up": True}),
        ),
        onset_s=at_s,
    )


CATALOG: dict[str, Callable[..., Scenario]] = {
    "normal": normal,
    "bearing_degradation": bearing_degradation,
    "motor_overheating": motor_overheating,
    "pump_leakage": pump_leakage,
    "gateway_outage": gateway_outage,
    "network_degradation": network_degradation,
    "sensor_manipulation": sensor_manipulation,
    "sensor_replay": sensor_replay,
    "central_disconnection": central_disconnection,
    "telemetry_backlog": telemetry_backlog,
}


def build_scenario(scenario_id: str, **params: Any) -> Scenario:
    if scenario_id not in CATALOG:
        raise KeyError(f"unknown scenario {scenario_id}")
    return CATALOG[scenario_id](**params)
