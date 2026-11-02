import pytest

from modules.cybersecurity.integrity import DISAGREE_COUNT, FROZEN_COUNT, IntegrityMonitor
from modules.digital_twin.engine import TwinEngine
from modules.recovery_engine.authorization import Decision, Impact, authorize
from modules.recovery_engine.manager import IncidentManager, InvalidTransition, State
from modules.telemetry.pipeline import CentralPipeline
from modules.telemetry.schema import TelemetryMessage
from simulation.engine.core import Envelope, FactorySimulation
from simulation.factory.layout import build_factory
from simulation.scenarios.catalog import build_scenario

SPEC = build_factory()


def message(sequence=0, device="MTR-A01-controller", **overrides):
    base = {
        "factory_id": "plant-01",
        "zone_id": "A",
        "machine_id": "MTR-A01",
        "gateway_id": "GW-A1",
        "device_id": device,
        "timestamp": 1000.0,
        "sim_time": float(sequence),
        "sequence": sequence,
        "scenario_id": "normal",
        "status": "running",
        "readings": {"rpm": 1480.0},
    }
    return {**base, **overrides}


# ----- telemetry validation


@pytest.mark.parametrize(
    "bad",
    [
        {"readings": {}},
        {"readings": {"rpm": float("nan")}},
        {"readings": {"rpm": float("inf")}},
        {"sequence": -1},
        {"schema_version": "9.9"},
        {"unexpected": 1},
    ],
)
def test_invalid_telemetry_is_counted_not_applied(bad):
    pipeline = CentralPipeline(SPEC, auto_diagnose=False)
    assert pipeline.handle_telemetry(message(**bad)) is False
    assert pipeline.invalid_messages == 1
    assert pipeline.twin.twins["MTR-A01-controller"].received == 0


# ----- twin state


def test_twin_tracks_gaps_duplicates_and_order():
    twin = TwinEngine(SPEC)
    for sequence, value in [(1, 1.0), (1, 9.0), (5, 5.0), (3, 3.0)]:
        twin.ingest(TelemetryMessage.model_validate(message(sequence, readings={"rpm": value})))
    state = twin.twins["MTR-A01-controller"]
    assert state.duplicates == 1
    assert state.gaps == 4
    assert state.out_of_order == 1
    assert state.last_sequence == 5
    assert state.reported["rpm"] == 5.0


def test_twin_rejects_unknown_device():
    twin = TwinEngine(SPEC)
    assert not twin.ingest(TelemetryMessage.model_validate(message(device="ghost")))
    assert twin.rejected_unknown == 1


def test_twin_desired_reported_delta():
    twin = TwinEngine(SPEC)
    twin.set_desired("MTR-A01-controller", rpm=900.0)
    assert twin.delta("MTR-A01-controller") == {"rpm": 900.0}
    twin.ingest(TelemetryMessage.model_validate(message(1, readings={"rpm": 900.0})))
    assert twin.delta("MTR-A01-controller") == {}


# ----- authorization


def test_out_of_limit_is_denied_even_with_human_approval():
    assert authorize("set_speed", 5.0, approved_by="alice").decision is Decision.DENY


def test_low_confidence_never_auto_executes():
    verdict = authorize("set_speed", 0.6, confidence=0.5)
    assert verdict.decision is Decision.NEEDS_APPROVAL


def test_missing_confidence_never_auto_executes():
    assert authorize("set_speed", 0.6).decision is Decision.NEEDS_APPROVAL


@pytest.mark.parametrize("command", ["stop", "repair", "isolate"])
def test_high_impact_needs_approval_at_full_confidence(command):
    verdict = authorize(command, None, confidence=1.0)
    assert verdict.impact is Impact.HIGH
    assert verdict.decision is Decision.NEEDS_APPROVAL


def test_low_impact_high_confidence_is_allowed():
    assert authorize("set_speed", 0.6, confidence=0.95).decision is Decision.ALLOW


def test_deep_speed_cut_is_high_impact():
    assert authorize("set_speed", 0.35, confidence=0.99).decision is Decision.NEEDS_APPROVAL


# ----- recovery state machine


def manager(verified=True):
    sent: list[tuple] = []
    return (
        IncidentManager(lambda *a: sent.append(a), lambda m, f: verified),
        sent,
    )


def test_high_confidence_derate_runs_to_recovery_with_audit():
    mgr, sent = manager()
    incident = mgr.report_fault("M", "overheating", 0.95, 100.0)
    assert incident.state is State.MITIGATING
    assert sent[0][1:3] == ("set_speed", 0.6)
    mgr.tick(140.0)
    assert incident.state is State.VERIFYING
    mgr.tick(500.0)
    assert incident.state is State.RECOVERED
    assert incident.closed_at == 500.0
    states = [e["state"] for e in incident.audit]
    assert states == ["detected", "diagnosed", "mitigating", "verifying", "recovered"]


def test_failed_verification_escalates():
    mgr, _ = manager(verified=False)
    incident = mgr.report_fault("M", "overheating", 0.95, 0.0)
    mgr.tick(40.0)
    mgr.tick(400.0)
    assert incident.state is State.ESCALATED


def test_low_confidence_waits_for_human_and_sends_nothing():
    mgr, sent = manager()
    incident = mgr.report_fault("M", "overheating", 0.5, 0.0)
    assert incident.state is State.AWAITING_APPROVAL
    assert sent == []
    mgr.approve(incident.incident_id, "alice", 10.0)
    assert incident.state is State.MITIGATING
    assert len(sent) == 1
    assert incident.audit[-1]["actor"] == "alice"


def test_pump_stop_requires_approval_even_at_full_confidence():
    mgr, sent = manager()
    incident = mgr.report_fault("P", "pump_leak", 1.0, 0.0)
    assert incident.state is State.AWAITING_APPROVAL
    assert sent == []


def test_rejection_closes_and_sends_nothing():
    mgr, sent = manager()
    incident = mgr.report_fault("P", "pump_leak", 1.0, 0.0)
    mgr.reject(incident.incident_id, "alice", 5.0)
    assert incident.state is State.REJECTED
    assert sent == []
    with pytest.raises(InvalidTransition):
        mgr.approve(incident.incident_id, "alice", 6.0)


def test_only_one_open_incident_per_machine():
    mgr, _ = manager()
    first = mgr.report_fault("M", "overheating", 0.95, 0.0)
    assert mgr.report_fault("M", "bearing_wear", 0.95, 1.0) is first


def test_repair_recovers_from_any_open_state():
    mgr, sent = manager()
    incident = mgr.report_fault("P", "pump_leak", 1.0, 0.0)
    mgr.request_repair(incident.incident_id, "alice", 5.0)
    assert incident.state is State.RECOVERED
    assert sent[-1][1] == "repair"


# ----- integrity


def feed(monitor, values, sensor_device, signal="winding_temp_c", machine="M"):
    findings = []
    for i, value in enumerate(values):
        for peer in ("M-p1", "M-p2", "M-p3"):
            monitor.observe(machine, peer, float(i), {signal: 60.0 + (i % 3) * 0.1})
        findings += monitor.observe(machine, sensor_device, float(i), {signal: value})
    return findings


def test_disagreeing_sensor_is_quarantined():
    monitor = IntegrityMonitor()
    findings = feed(monitor, [90.0 + 0.1 * i for i in range(DISAGREE_COUNT + 2)], "M-x")
    assert [f.kind for f in findings] == ["sensor_disagreement"]
    assert monitor.is_quarantined("M-x", "winding_temp_c")


def test_frozen_sensor_is_quarantined():
    monitor = IntegrityMonitor()
    findings = feed(monitor, [60.1] * (FROZEN_COUNT + 2), "M-x")
    assert [f.kind for f in findings] == ["sensor_frozen"]


def test_stopped_machine_is_not_flagged_as_frozen():
    monitor = IntegrityMonitor()
    for i in range(FROZEN_COUNT * 2):
        found = monitor.observe("M", "M-x", float(i), {"rpm": 5.0}, machine_running=False)
        assert found == []


# ----- pipeline with the simulator, no broker or database


def closed_loop(scenarios, until=2400.0, edge=True):
    holder = {}
    pipeline = CentralPipeline(
        SPEC,
        transport=lambda c: holder["sim"].submit_command(
            c.device_id, c.command, c.value, c.command_id
        ),
    )

    def sink(envelope: Envelope, arrival: float) -> None:
        pipeline.handle(envelope.kind, envelope.payload)

    sim = FactorySimulation(seed=11, scenarios=scenarios, sink=sink, spec=SPEC, edge_enabled=edge)
    holder["sim"] = sim
    sim.run(until)
    return sim, pipeline


def test_end_to_end_overheating_is_detected_mitigated_and_recovers():
    sim, pipeline = closed_loop([build_scenario("motor_overheating")], until=3000)
    incident = next(i for i in pipeline.manager.incidents.values() if i.machine_id == "MTR-A02")
    assert incident.fault in ("overheating", "edge_protection")
    assert incident.state in (State.RECOVERED, State.VERIFYING, State.ESCALATED)
    assert not sim.machines["MTR-A02"].failed
    assert sim.machines["MTR-A02"].speed_cmd == pytest.approx(0.6)


def test_sensor_manipulation_is_caught_and_causes_no_machine_action():
    sim, pipeline = closed_loop([build_scenario("sensor_manipulation")], until=1500)
    assert "MTR-A01-node-a.winding_temp_c" in pipeline.integrity.quarantined
    assert not sim.edge_actions
    assert sim.machines["MTR-A01"].speed_cmd == 1.0


def test_sensor_replay_is_caught():
    _, pipeline = closed_loop([build_scenario("sensor_replay")], until=1000)
    assert "MTR-A01-node-a.winding_temp_c" in pipeline.integrity.quarantined


def test_normal_run_raises_no_integrity_findings():
    _, pipeline = closed_loop([], until=1800)
    assert pipeline.integrity.findings == []


def test_disconnection_keeps_edge_protection_and_backfills_twin():
    scenarios = [
        build_scenario("motor_overheating"),
        build_scenario("central_disconnection", at_s=900, duration_s=1200),
    ]
    sim, pipeline = closed_loop(scenarios, until=2800)
    assert sim.edge_actions, "edge must act while central is unreachable"
    assert not sim.machines["MTR-A02"].failed
    assert sum(g.stats.replayed for g in sim.gateways.values()) > 0
    assert any(a["code"] == "edge_set_speed" for a in pipeline.alerts)


def test_simulator_reset_clears_analytics():
    _, pipeline = closed_loop([], until=300)
    twin = pipeline.twin.twins["MTR-A01-controller"]
    assert twin.last_sequence > 0
    pipeline.handle_telemetry(message(0, sim_time=1.0))
    assert pipeline.sim_time == 1.0
    assert twin.last_sequence == 0
