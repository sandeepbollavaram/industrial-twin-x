"""Generate a labelled windowed dataset from simulated runs.

Usage: python -m research.datasets.generate --runs-per-class 12 --seed 1000

All data is simulated. Edge protection is off so fault trajectories run their natural
course. Hidden state (wear, leak) is used only for labels, never as features.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from modules.anomaly_detection.features import FEATURE_NAMES, HOP_S, MachineWindow
from modules.predictive_maintenance.models import HORIZON_S
from simulation.devices.machines import Pump, RotatingMachine
from simulation.engine.core import Envelope, FactorySimulation
from simulation.factory.layout import ROTATING_KINDS, build_factory
from simulation.scenarios.catalog import build_scenario

OUT_DIR = Path("research/datasets/generated")
DURATION_S = 3600.0
LEAK_FAILURE = 0.30
ROTATING = ("MTR-A01", "MTR-A02", "CNV-A03", "ROB-A04", "PMP-B01", "PMP-B02")
PLAN = {
    "normal": ("normal", (None,)),
    "bearing_wear": ("bearing_degradation", ROTATING),
    "overheating": ("motor_overheating", ROTATING),
    "pump_leak": ("pump_leakage", ("PMP-B01", "PMP-B02")),
}


def is_manifest(label: str, machine: RotatingMachine, wear0: float, temp0: float) -> bool:
    """Whether the fault has physically developed enough to be observable at all."""
    if label == "bearing_wear":
        return machine.wear - wear0 >= 0.10
    if label == "overheating":
        return machine.winding_temp - temp0 >= 8.0
    if label == "pump_leak":
        return isinstance(machine, Pump) and machine.leak >= 0.03
    return False


def simulate_run(job: dict) -> list[dict]:
    rng = np.random.default_rng(job["seed"])
    label = job["label"]
    scenario_id, targets = PLAN[label]
    severity = float(rng.uniform(0.7, 1.3))
    onset = float(rng.uniform(300, 900))
    # Runs start at a random time of day so "normal" covers the whole diurnal cycle.
    ambient_offset = float(rng.uniform(0, 86400))
    target = targets[int(rng.integers(len(targets)))]
    params = {} if label == "normal" else {"machine": target, "at_s": onset, "severity": severity}
    scenario = build_scenario(scenario_id, **params)

    spec = build_factory()
    windows = {m.machine_id: MachineWindow(m) for m in spec.machines if m.kind in ROTATING_KINDS}

    def sink(envelope: Envelope, _: float) -> None:
        if envelope.kind == "telemetry":
            window = windows.get(envelope.payload["machine_id"])
            if window is not None:
                for signal, value in envelope.payload["readings"].items():
                    window.add(envelope.payload["sim_time"], signal, value)

    sim = FactorySimulation(
        seed=job["seed"],
        scenarios=[scenario],
        sink=sink,
        spec=spec,
        edge_enabled=False,
        ambient_offset_s=ambient_offset,
    )
    rows: list[dict] = []
    failure_time: dict[str, float] = {}
    wear0: dict[str, float] = {}
    temp0: dict[str, float] = {}
    t = HOP_S
    while t <= DURATION_S:
        sim.run(t)
        for machine_id, window in windows.items():
            machine = sim.machines[machine_id]
            assert isinstance(machine, RotatingMachine)
            if t <= onset:
                wear0[machine_id] = machine.wear
                temp0[machine_id] = machine.winding_temp
            functional_failure = machine.failed or getattr(machine, "leak", 0.0) >= LEAK_FAILURE
            if functional_failure and machine_id not in failure_time:
                failure_time[machine_id] = t
            features = window.features(t)
            if features is None:
                continue
            is_target = machine_id == target and t > onset
            if machine.failed:
                row_label = "failed"
            elif not is_target:
                row_label = "normal"
            elif is_manifest(label, machine, wear0[machine_id], temp0[machine_id]):
                row_label = label
            else:
                row_label = "pending"
            rows.append(
                {
                    "run_id": job["run_id"],
                    "seed": job["seed"],
                    "scenario": scenario_id,
                    "run_label": label,
                    "machine_id": machine_id,
                    "kind": window.spec.kind,
                    "target": machine_id == target,
                    "onset": onset,
                    "severity": severity,
                    "t": t,
                    "label": row_label,
                    "wear": machine.wear,
                    **features,
                }
            )
        t += HOP_S
    for row in rows:
        failed_at = failure_time.get(row["machine_id"])
        row["failure_time"] = failed_at if failed_at is not None else np.nan
        row["fail_soon"] = bool(failed_at is not None and 0 <= failed_at - row["t"] <= HORIZON_S)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-per-class", type=int, default=12)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    jobs = []
    next_seed = args.seed
    for label in PLAN:
        for i in range(args.runs_per_class):
            jobs.append({"run_id": f"{label}-{i:03d}", "label": label, "seed": next_seed})
            next_seed += 1
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(simulate_run, jobs))
    frame = pd.DataFrame([row for rows in results for row in rows])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT_DIR / "windows.csv.gz", index=False)
    manifest = {
        "simulated": True,
        "runs_per_class": args.runs_per_class,
        "base_seed": args.seed,
        "duration_s": DURATION_S,
        "features": list(FEATURE_NAMES),
        "rows": len(frame),
        "label_counts": frame["label"].value_counts().to_dict(),
        "horizon_s": HORIZON_S,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest["label_counts"]), "rows", len(frame))


if __name__ == "__main__":
    main()
