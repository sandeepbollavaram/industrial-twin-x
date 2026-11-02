import json

import pytest

from modules.telemetry.schema import TelemetryMessage
from simulation.engine.core import Envelope, FactorySimulation
from simulation.factory.layout import build_factory
from simulation.scenarios.catalog import CATALOG, build_scenario


def capture(seed=1, scenarios=(), until=300.0, **kwargs):
    messages: list[dict] = []

    def sink(envelope: Envelope, arrival: float) -> None:
        messages.append({"kind": envelope.kind, "arrival": arrival, "payload": envelope.payload})

    sim = FactorySimulation(seed=seed, scenarios=scenarios, sink=sink, **kwargs)
    sim.run(until)
    return sim, messages


def test_factory_meets_target_size():
    spec = build_factory()
    assert (len(spec.zones), len(spec.gateways), len(spec.machines)) == (3, 5, 10)
    assert len(spec.devices) == 100
    assert spec.sensor_count == 300
    assert len(build_factory(5).devices) == 500


def test_same_seed_is_byte_identical():
    _, first = capture(seed=7)
    _, second = capture(seed=7)
    assert json.dumps(first) == json.dumps(second)


def test_different_seed_differs():
    _, first = capture(seed=7)
    _, second = capture(seed=8)
    assert json.dumps(first) != json.dumps(second)


def test_all_telemetry_validates_against_schema():
    _, messages = capture()
    telemetry = [m for m in messages if m["kind"] == "telemetry"]
    assert telemetry
    for message in telemetry:
        TelemetryMessage.model_validate(message["payload"])


def test_telemetry_hides_ground_truth():
    _, messages = capture(scenarios=[build_scenario("bearing_degradation")], until=700)
    for message in messages:
        if message["kind"] == "telemetry":
            assert "wear" not in message["payload"]["readings"]
            assert "fault" not in json.dumps(message["payload"])


@pytest.mark.parametrize("scenario_id", sorted(CATALOG))
def test_every_scenario_runs(scenario_id):
    sim, messages = capture(scenarios=[build_scenario(scenario_id)], until=1800)
    assert messages
    assert sim.env.now == 1800


def test_normal_operation_is_stable():
    sim, _ = capture(until=3600)
    assert not any(m.failed for m in sim.machines.values())
    assert not sim.edge_actions


def test_gateway_outage_loses_messages_and_recovers():
    sim, _ = capture(scenarios=[build_scenario("gateway_outage")], until=1200)
    stats = sim.gateways["GW-A1"].stats
    assert stats.lost_outage > 0
    assert sim.gateways["GW-A1"].state == "online"
    assert sim.gateways["GW-B1"].stats.lost_outage == 0


def test_link_loss_buffers_and_flushes_without_loss():
    scenario = build_scenario("telemetry_backlog", at_s=100, duration_s=300)
    sim, messages = capture(scenarios=[scenario], until=1500)
    gateway = sim.gateways["GW-A1"]
    assert gateway.stats.replayed > 0
    assert gateway.backlog == 0
    assert gateway.stats.lost_overflow == 0
    replayed = [m for m in messages if m["payload"].get("replayed")]
    assert replayed
    per_device: dict[str, list[int]] = {}
    for message in messages:
        if message["kind"] == "telemetry" and message["payload"]["gateway_id"] == "GW-A1":
            per_device.setdefault(message["payload"]["device_id"], []).append(
                message["payload"]["sequence"]
            )
    for sequences in per_device.values():
        assert sorted(sequences) == list(range(len(sequences)))


def test_network_degradation_drops_and_delays():
    sim, _ = capture(scenarios=[build_scenario("network_degradation", at_s=10)], until=500)
    assert sim.gateways["GW-B1"].stats.lost_network > 0


def test_device_isolation_stops_its_telemetry():
    sim, messages = capture(until=30)
    assert sim.submit_command("MTR-A01-node-a", "isolate").accepted
    count = len(messages)
    sim.run(100)
    new = [m for m in messages[count:] if m["kind"] == "telemetry"]
    assert new
    assert all(m["payload"]["device_id"] != "MTR-A01-node-a" for m in new)


def test_command_fails_when_uplink_is_down():
    scenario = build_scenario("central_disconnection", at_s=5, duration_s=100)
    sim, _ = capture(scenarios=[scenario], until=20)
    result = sim.submit_command("MTR-A01-controller", "stop")
    assert not result.accepted
    assert "unreachable" in result.detail
