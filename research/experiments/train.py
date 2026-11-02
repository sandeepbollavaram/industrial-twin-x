"""Train and evaluate all models with run-grouped splits.

Usage: python -m research.experiments.train

Evaluation uses held-out simulation runs. No window from a test run is seen in training,
which avoids temporal leakage between overlapping windows of one trajectory.
"""

from __future__ import annotations

import argparse
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from modules.anomaly_detection.detectors import (
    HybridDetector,
    IsolationForestDetector,
    StatisticalBaseline,
)
from modules.anomaly_detection.features import FEATURE_NAMES
from modules.fault_diagnosis.classifier import FAULT_CLASSES, FaultClassifier, rule_predict
from modules.predictive_maintenance.models import (
    HORIZON_S,
    DegradationRegressor,
    FailureRiskModel,
)
from research.metrics.metrics import detection_metrics, summarize, sustained_first_alarm

DATA = Path("research/datasets/generated/windows.csv.gz")
MODEL_DIR = Path("research/models/current")
REPORT_DIR = Path("research/reports/ai-evaluation")
FAULTS = ("bearing_wear", "overheating", "pump_leak")


def features_of(frame: pd.DataFrame) -> np.ndarray:
    return frame[list(FEATURE_NAMES)].to_numpy(float)


def timing(test: pd.DataFrame, detector) -> dict:
    """Detection latency and lead time on the faulted machine of each held-out fault run."""
    out: dict[str, dict] = {}
    for fault in FAULTS:
        latencies: list[float] = []
        leads: list[float] = []
        missed = 0
        runs = test[(test["run_label"] == fault) & test["target"] & (test["label"] != "failed")]
        for _, run in runs.groupby("run_id"):
            run = run.sort_values("t")
            after = run[run["t"] > run["onset"].iloc[0]]
            scores = detector.score(features_of(after), after["kind"].to_numpy())
            alarm = sustained_first_alarm(after["t"].to_numpy(), scores)
            if alarm is None:
                missed += 1
                continue
            latencies.append(alarm - run["onset"].iloc[0])
            failed_at = run["failure_time"].iloc[0]
            if not np.isnan(failed_at):
                leads.append(failed_at - alarm)
        out[fault] = {
            "detection_latency_s": summarize(latencies),
            "lead_time_before_failure_s": summarize(leads),
            "missed_runs": missed,
            "runs": int(runs["run_id"].nunique()),
        }
    return out


def false_alarm_rate(test: pd.DataFrame, detector) -> dict:
    """Sustained false alarms per machine-hour on machines with no fault in that run."""
    healthy = test[(test["label"] == "normal") & ~test["target"]]
    alarms = 0
    machine_hours = 0.0
    for _, group in healthy.groupby(["run_id", "machine_id"]):
        group = group.sort_values("t")
        scores = detector.score(features_of(group), group["kind"].to_numpy())
        machine_hours += len(group) * 30.0 / 3600.0
        if sustained_first_alarm(group["t"].to_numpy(), scores) is not None:
            alarms += 1
    return {
        "machines_with_sustained_false_alarm": alarms,
        "machine_hours": machine_hours,
        "per_machine_hour": alarms / machine_hours if machine_hours else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    frame = pd.read_csv(DATA)
    usable = frame[frame["label"] != "failed"]
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=args.seed)
    train_idx, test_idx = next(splitter.split(usable, groups=usable["run_id"]))
    train, test = usable.iloc[train_idx], usable.iloc[test_idx]
    overlap = set(train["run_id"]) & set(test["run_id"])
    if overlap:
        raise RuntimeError(f"run leakage across split: {overlap}")

    normal_train = train[train["label"] == "normal"]
    X_normal, k_normal = features_of(normal_train), normal_train["kind"].to_numpy()
    baseline = StatisticalBaseline().fit(X_normal, k_normal)
    forest = IsolationForestDetector(seed=args.seed).fit(X_normal, k_normal)
    hybrid = HybridDetector(baseline, forest)

    labelled = test[test["label"] != "pending"]
    y_true = (labelled["label"] != "normal").to_numpy()
    X_test, k_test = features_of(labelled), labelled["kind"].to_numpy()
    anomaly: dict[str, dict[str, Any]] = {}
    for name, model in (
        ("statistical_baseline", baseline),
        ("isolation_forest", forest),
        ("hybrid", hybrid),
    ):
        anomaly[name] = {
            **detection_metrics(y_true, model.score(X_test, k_test)),
            "timing": timing(test, model),
            "false_alarms": false_alarm_rate(test, model),
        }

    class_train = train[train["label"] != "pending"]
    classifier = FaultClassifier(seed=args.seed).fit(
        features_of(class_train), class_train["kind"].to_numpy(), class_train["label"].to_numpy()
    )
    predicted, _ = classifier.predict(X_test, k_test)
    rules = rule_predict(X_test)
    truth = labelled["label"].to_numpy()
    labels = list(FAULT_CLASSES)
    fault_diagnosis: dict[str, Any] = {
        "random_forest": {
            "macro_f1": float(f1_score(truth, predicted, average="macro", labels=labels)),
            "report": classification_report(
                truth, predicted, labels=labels, output_dict=True, zero_division=0
            ),
            "confusion_matrix": confusion_matrix(truth, predicted, labels=labels).tolist(),
        },
        "rule_baseline": {
            "macro_f1": float(f1_score(truth, rules, average="macro", labels=labels)),
            "confusion_matrix": confusion_matrix(truth, rules, labels=labels).tolist(),
        },
        "labels": labels,
    }

    # Degradation regression covers wear trajectories and healthy machines.
    deg_mask_train = train["label"].isin(["normal", "bearing_wear", "pending"]) & train[
        "run_label"
    ].isin(["normal", "bearing_wear"])
    deg_mask_test = test["label"].isin(["normal", "bearing_wear", "pending"]) & test[
        "run_label"
    ].isin(["normal", "bearing_wear"])
    deg_train, deg_test = train[deg_mask_train], test[deg_mask_test]
    degradation = DegradationRegressor(seed=args.seed).fit(
        features_of(deg_train), deg_train["kind"].to_numpy(), deg_train["wear"].to_numpy()
    )
    deg_pred = degradation.predict(features_of(deg_test), deg_test["kind"].to_numpy())
    vib_index = list(FEATURE_NAMES).index("vibration_per_speed")
    linear = LinearRegression().fit(
        features_of(deg_train)[:, [vib_index]], deg_train["wear"].to_numpy()
    )
    linear_pred = linear.predict(features_of(deg_test)[:, [vib_index]])
    mean_pred = np.full(len(deg_test), deg_train["wear"].mean())
    degradation_eval = {
        "target": "hidden simulated bearing wear state in [0, 1]",
        "gradient_boosting_mae": float(mean_absolute_error(deg_test["wear"], deg_pred)),
        "linear_vibration_baseline_mae": float(mean_absolute_error(deg_test["wear"], linear_pred)),
        "mean_predictor_baseline_mae": float(mean_absolute_error(deg_test["wear"], mean_pred)),
    }

    risk_train = train
    risk = FailureRiskModel(seed=args.seed).fit(
        features_of(risk_train),
        risk_train["kind"].to_numpy(),
        risk_train["fail_soon"].to_numpy(),
        risk_train["run_id"].to_numpy(),
    )
    risk_y = test["fail_soon"].to_numpy()
    risk_pred = risk.predict_proba(features_of(test), test["kind"].to_numpy())
    prevalence = float(risk_train["fail_soon"].mean())
    bins = np.linspace(0, 1, 6)
    reliability = []
    for low, high in zip(bins[:-1], bins[1:], strict=True):
        mask = (risk_pred >= low) & (risk_pred <= high if high == 1 else risk_pred < high)
        if mask.sum():
            reliability.append(
                {
                    "bin": [float(low), float(high)],
                    "n": int(mask.sum()),
                    "mean_predicted": float(risk_pred[mask].mean()),
                    "observed_rate": float(risk_y[mask].mean()),
                }
            )
    risk_eval = {
        "horizon_s": HORIZON_S,
        "definition": "Functional failure of the machine within the horizon, simulated runs only",
        "roc_auc": float(roc_auc_score(risk_y, risk_pred)),
        "brier": float(brier_score_loss(risk_y, risk_pred)),
        "prevalence_baseline_brier": float(
            brier_score_loss(risk_y, np.full(len(risk_y), prevalence))
        ),
        "reliability": reliability,
        "note": "Not a remaining useful life model. Not validated on real equipment.",
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    bundle = {
        "isolation_forest": forest,
        "statistical_baseline": baseline,
        "hybrid": hybrid,
        "fault_classifier": classifier,
        "degradation": degradation,
        "failure_risk": risk,
        "version": version,
    }
    joblib.dump(bundle, MODEL_DIR / "bundle.joblib", compress=3)
    metrics: dict[str, Any] = {
        "simulated_data": True,
        "split": {
            "method": "GroupShuffleSplit by run_id",
            "seed": args.seed,
            "train_runs": int(train["run_id"].nunique()),
            "test_runs": int(test["run_id"].nunique()),
            "train_windows": len(train),
            "test_windows": len(test),
        },
        "anomaly_detection": anomaly,
        "fault_diagnosis": fault_diagnosis,
        "degradation": degradation_eval,
        "failure_risk": risk_eval,
    }
    metadata: dict[str, object] = {
        "version": version,
        "features": list(FEATURE_NAMES),
        "feature_preprocessing": "per-kind StandardScaler in detectors; none in forests",
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "seed": args.seed,
        "split": metrics["split"],
    }
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    compact = {
        name: {
            k: anomaly[name][k]
            for k in ("precision", "recall", "f1", "roc_auc", "false_positive_rate")
        }
        for name in anomaly
    }
    print(json.dumps(compact, indent=1))
    for name, result in anomaly.items():
        latency = {
            fault: (
                result["timing"][fault]["detection_latency_s"]["mean"],
                result["timing"][fault]["missed_runs"],
                result["timing"][fault]["runs"],
            )
            for fault in FAULTS
        }
        print(name, "latency_mean/missed/runs", latency, "false", result["false_alarms"])
    print(
        "fault macro f1 rf",
        fault_diagnosis["random_forest"]["macro_f1"],
        "rules",
        fault_diagnosis["rule_baseline"]["macro_f1"],
    )
    print("degradation", degradation_eval)
    print("risk", {k: risk_eval[k] for k in ("roc_auc", "brier", "prevalence_baseline_brier")})
    print("reliability", reliability)


if __name__ == "__main__":
    main()
