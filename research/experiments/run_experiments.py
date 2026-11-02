"""Repeated resilience and IoT experiments under identical seeds and conditions.

Usage: python -m research.experiments.run_experiments --seeds 5

Every condition runs the same simulator and central pipeline code as live mode, without
MQTT and the database, so results are repeatable. All results are from simulation.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import psutil

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from modules.telemetry.pipeline import CentralPipeline, TrainedAI
from modules.telemetry.schema import CommandMessage
from research.metrics.metrics import summarize
from simulation.devices.machines import RotatingMachine
from simulation.engine.core import Envelope, FactorySimulation
from simulation.factory.layout import build_factory
from simulation.scenarios.catalog import build_scenario

MODEL = Path("research/models/current/bundle.joblib")
RUNS = Path("research/experiments/runs")
REPORT = Path("research/reports/experiments")
DURATION_S = 3600.0
BASE_SEED = 5000  # Disjoint from the training dataset seeds (1000 onward).


@dataclass(frozen=True)
class Condition:
    name: str
    group: str
    scenarios: tuple[str, ...]
    edge: bool = True
    central: bool = True
    machine: str | None = None


CONDITIONS = (
    Condition("normal_control", "control", ("normal",)),
    Condition(
        "overheat_edge_central", "overheating", ("motor_overheating",), True, True, "MTR-A02"
    ),
    Condition(
        "overheat_central_only", "overheating", ("motor_overheating",), False, True, "MTR-A02"
    ),
    Condition("overheat_edge_only", "overheating", ("motor_overheating",), True, False, "MTR-A02"),
    Condition(
        "overheat_unprotected", "overheating", ("motor_overheating",), False, False, "MTR-A02"
    ),
    Condition(
        "overheat_disconnect_edge",
        "disconnection",
        ("motor_overheating", "central_disconnection_long"),
        True,
        True,
        "MTR-A02",
    ),
    Condition(
        "overheat_disconnect_no_edge",
        "disconnection",
        ("motor_overheating", "central_disconnection_long"),
        False,
        True,
        "MTR-A02",
    ),
    Condition("bearing_edge_central", "bearing", ("bearing_degradation",), True, True, "MTR-A01"),
    Condition("bearing_unprotected", "bearing", ("bearing_degradation",), False, False, "MTR-A01"),
    Condition("leak_edge_central", "leak", ("pump_leakage",), True, True, "PMP-B01"),
    Condition("gateway_outage", "network", ("gateway_outage",)),
    Condition("network_degradation", "network", ("network_degradation",)),
    Condition("telemetry_backlog", "network", ("telemetry_backlog",)),
    Condition("sensor_bias", "security", ("sensor_manipulation",), True, True, "MTR-A01"),
    Condition("sensor_replay", "security", ("sensor_replay",), True, True, "MTR-A01"),
)
_bundle: Any = None


def _ai() -> TrainedAI:
    global _bundle
    if _bundle is None:
        _bundle = TrainedAI(joblib.load(MODEL))
    return _bundle


def _scenario(name: str):
    if name == "central_disconnection_long":
        return build_scenario("central_disconnection", at_s=500, duration_s=2800)
    return build_scenario(name)


def run_one(job: tuple[Condition, int]) -> dict[str, Any]:
    condition, seed = job
    spec = build_factory()
    scenarios = [_scenario(s) for s in condition.scenarios]
    arrivals = {"telemetry": 0}
    latencies: list[float] = []
    backlog_peak = [0]
    holder: dict[str, FactorySimulation] = {}

    def deliver(command: CommandMessage) -> None:
        holder["sim"].submit_command(
            command.device_id, command.command, command.value, command.command_id
        )

    pipeline = (
        CentralPipeline(
            spec,
            ai=_ai(),
            transport=deliver,
        )
        if condition.central
        else None
    )

    def sink(envelope: Envelope, arrival: float) -> None:
        if envelope.kind == "telemetry":
            arrivals["telemetry"] += 1
            if not envelope.replayed:
                latencies.append(arrival - envelope.payload["sim_time"])
        elif envelope.kind == "network":
            backlog_peak[0] = max(
                backlog_peak[0], *(g["backlog"] for g in envelope.payload["gateways"])
            )
        if pipeline is not None:
            pipeline.handle(envelope.kind, envelope.payload)

    process = psutil.Process()
    cpu_before = process.cpu_times()
    started = time.perf_counter()
    sim = FactorySimulation(
        seed=seed, scenarios=scenarios, sink=sink, spec=spec, edge_enabled=condition.edge
    )
    holder["sim"] = sim
    sim.run(DURATION_S)
    wall = time.perf_counter() - started
    cpu_after = process.cpu_times()

    stats = [g.stats for g in sim.gateways.values()]
    submitted = sum(s.submitted for s in stats)
    delivered = sum(s.delivered for s in stats)
    rotating = [m for m in sim.machines.values() if isinstance(m, RotatingMachine)]
    result: dict[str, Any] = {
        "condition": condition.name,
        "group": condition.group,
        "seed": seed,
        "messages_sent": submitted,
        "messages_received": delivered,
        "delivery_ratio": delivered / submitted if submitted else None,
        "lost_network": sum(s.lost_network for s in stats),
        "lost_outage": sum(s.lost_outage for s in stats),
        "replayed": sum(s.replayed for s in stats),
        "backlog_peak": backlog_peak[0],
        "latency_mean_s": sum(latencies) / len(latencies) if latencies else None,
        "throughput_msgs_per_sim_s": arrivals["telemetry"] / DURATION_S,
        "wall_s": wall,
        "events_per_wall_s": delivered / wall,
        "cpu_s": (cpu_after.user + cpu_after.system) - (cpu_before.user + cpu_before.system),
        "rss_mb": process.memory_info().rss / 1e6,
        "total_output_units": sum(m.output_units for m in rotating),
        "total_downtime_s": sum(m.downtime_s for m in rotating),
        "edge_actions": len(sim.edge_actions),
    }
    # With the compound scenarios the first entry is the machine fault.
    onset = scenarios[0].onset_s
    if condition.machine:
        machine = sim.machines[condition.machine]
        assert isinstance(machine, RotatingMachine)
        result.update(
            machine_failed=machine.failed,
            failure_reason=machine.failure_reason,
            machine_downtime_s=machine.downtime_s,
            machine_output_units=machine.output_units,
            peak_edge_action_time=sim.edge_actions[0]["sim_time"] if sim.edge_actions else None,
        )
    if pipeline is not None:
        first = pipeline.first_detection
        key = condition.machine or ""
        if condition.group == "security":
            detected = first.get(f"tamper:{key}")
        else:
            # Only alarms after onset count; earlier ones are false alarms, reported below.
            alarms = pipeline.alarm_history.get(key, [])
            detected = next((t for t in alarms if onset is not None and t >= onset), None)
        result["detection_time_s"] = (
            detected - onset if detected is not None and onset is not None else None
        )
        result["sustained_alarms_before_onset"] = sum(
            1 for t in pipeline.alarm_history.get(key, []) if onset is not None and t < onset
        )
        result["incident_states"] = sorted(
            i.state.value for i in pipeline.manager.incidents.values()
        )
        result["incident_count"] = len(pipeline.manager.incidents)
        result["healthy_machine_incidents"] = sum(
            1 for i in pipeline.manager.incidents.values() if i.machine_id != condition.machine
        )
        recovered = [
            (i.closed_at or i.opened_at) - i.opened_at
            for i in pipeline.manager.incidents.values()
            if i.machine_id == condition.machine and i.state.value == "recovered"
        ]
        result["recovery_time_s"] = min(recovered) if recovered else None
        result["integrity_findings"] = len(pipeline.integrity.findings)
        result["false_quarantines"] = sum(
            1
            for f in pipeline.integrity.findings
            if condition.group != "security" or not f.sensor_id.startswith("MTR-A01-node-a.")
        )
        result["invalid_messages"] = pipeline.invalid_messages
    result["pid"] = os.getpid()
    return result


METRICS = (
    "delivery_ratio",
    "latency_mean_s",
    "throughput_msgs_per_sim_s",
    "backlog_peak",
    "detection_time_s",
    "recovery_time_s",
    "machine_downtime_s",
    "machine_output_units",
    "total_output_units",
    "total_downtime_s",
    "healthy_machine_incidents",
    "sustained_alarms_before_onset",
    "integrity_findings",
    "false_quarantines",
    "events_per_wall_s",
    "cpu_s",
    "rss_mb",
)


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["condition"]].append(result)
    summary = {}
    for name, runs in grouped.items():
        entry: dict[str, Any] = {"group": runs[0]["group"], "runs": len(runs)}
        for metric in METRICS:
            entry[metric] = summarize([r.get(metric) for r in runs])
        entry["failures"] = sum(1 for r in runs if r.get("machine_failed"))
        summary[name] = entry
    return summary


# Validated reference palette: single-hue bars carry magnitude; labels carry identity.
SERIES_COLOR = "#2a78d6"
INK = "#3c3c3c"
GRID = "#e1e0dd"


def bar_figure(summary: dict, names: list[str], metric: str, title: str, unit: str, path: Path):
    labels = [n for n in names if summary[n][metric]["n"]]
    values = [summary[n][metric]["mean"] for n in labels]
    errors = [summary[n][metric]["std"] for n in labels]
    figure, axis = plt.subplots(figsize=(8, 0.55 * len(labels) + 1.5))
    axis.barh(
        labels,
        values,
        xerr=errors,
        color=SERIES_COLOR,
        height=0.55,
        error_kw={"ecolor": INK, "linewidth": 1},
    )
    axis.invert_yaxis()
    axis.set_xlabel(unit, color=INK)
    axis.set_title(title, loc="left", color=INK, fontsize=11)
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(colors=INK, length=0)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    seeds = [BASE_SEED + i for i in range(args.seeds)]
    jobs = [(condition, seed) for condition in CONDITIONS for seed in seeds]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_one, jobs))

    RUNS.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    (RUNS / "raw_results.json").write_text(json.dumps(results, indent=1))
    summary = aggregate(results)
    metadata = joblib.load(MODEL)["version"]
    document = {
        "available": True,
        "simulated": True,
        "duration_s": DURATION_S,
        "seeds": seeds,
        "workers": args.workers,
        "model_version": metadata,
        "conditions": [c.__dict__ for c in CONDITIONS],
        "summary": summary,
    }
    (REPORT / "summary.json").write_text(json.dumps(document, indent=1))

    overheating = [
        "overheat_edge_central",
        "overheat_central_only",
        "overheat_edge_only",
        "overheat_unprotected",
        "overheat_disconnect_edge",
        "overheat_disconnect_no_edge",
    ]
    bar_figure(
        summary,
        overheating,
        "machine_downtime_s",
        "Faulted motor downtime in one simulated hour (mean, 1 SD)",
        "seconds",
        REPORT / "overheating_downtime.png",
    )
    bar_figure(
        summary,
        ["normal_control", "gateway_outage", "network_degradation", "telemetry_backlog"],
        "delivery_ratio",
        "Message delivery ratio by network condition (mean, 1 SD)",
        "ratio",
        REPORT / "delivery_ratio.png",
    )
    detection = [n for n in summary if summary[n]["detection_time_s"]["n"]]
    bar_figure(
        summary,
        detection,
        "detection_time_s",
        "Detection time after fault onset (mean, 1 SD)",
        "simulated seconds",
        REPORT / "detection_time.png",
    )
    for name, entry in summary.items():
        print(
            name,
            "fail",
            entry["failures"],
            "/",
            entry["runs"],
            "dr",
            round(entry["delivery_ratio"]["mean"], 3),
            "det",
            entry["detection_time_s"]["mean"],
            "rec",
            entry["recovery_time_s"]["mean"],
            "down",
            entry["machine_downtime_s"]["mean"],
            "healthyinc",
            entry["healthy_machine_incidents"]["mean"],
            "falseq",
            entry["false_quarantines"]["mean"],
            "wall/run",
            round(1 / max(entry["events_per_wall_s"]["mean"], 1e-9) * 72000, 1),
        )


if __name__ == "__main__":
    main()
