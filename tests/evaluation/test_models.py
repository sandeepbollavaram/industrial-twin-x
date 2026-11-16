import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from modules.anomaly_detection.detectors import (
    HybridDetector,
    IsolationForestDetector,
    StatisticalBaseline,
)
from modules.anomaly_detection.features import FEATURE_NAMES, MachineWindow, to_vector
from modules.fault_diagnosis.classifier import FaultClassifier, rule_diagnosis
from modules.predictive_maintenance.models import recommend
from research.metrics.metrics import detection_metrics, summarize, sustained_first_alarm
from simulation.factory.layout import build_factory

SPEC = build_factory()
N = len(FEATURE_NAMES)


def blob(rng, n, shift=0.0):
    return rng.normal(0.0, 1.0, (n, N)) + shift


def test_window_needs_enough_coverage():
    window = MachineWindow(SPEC.machine("MTR-A01"))
    window.add(100.0, "rpm", 1480.0)
    assert window.features(100.0) is None


def test_median_binning_resists_one_bad_sensor():
    clean, attacked = (MachineWindow(SPEC.machine("MTR-A01")) for _ in range(2))
    for t in np.arange(0.0, 120.0, 5.0):
        for w in (clean, attacked):
            w.add(t, "rpm", 1480.0)
            w.add(t, "winding_temp_c", 60.0)
            w.add(t, "winding_temp_c", 60.0)
        attacked.add(t, "winding_temp_c", 300.0)
    a, b = clean.features(120.0), attacked.features(120.0)
    assert a["winding_temp_c_mean"] == b["winding_temp_c_mean"]


def test_vector_order_is_stable():
    features = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
    assert to_vector(features).tolist() == list(range(N))


def test_detectors_separate_shifted_data():
    rng = np.random.default_rng(0)
    kinds = np.array(["motor"] * 2000)
    train = blob(rng, 2000)
    baseline = StatisticalBaseline().fit(train, kinds)
    forest = IsolationForestDetector(seed=0, n_estimators=30).fit(train, kinds)
    hybrid = HybridDetector(baseline, forest)
    test_kinds = np.array(["motor"] * 200)
    for model in (baseline, forest, hybrid):
        assert (model.score(blob(rng, 200, 8.0), test_kinds) > 1).mean() > 0.9
        assert (model.score(blob(rng, 200), test_kinds) > 1).mean() < 0.1


def test_hybrid_alarms_when_either_detector_does():
    rng = np.random.default_rng(1)
    kinds = np.array(["motor"] * 1000)
    train = blob(rng, 1000)
    baseline = StatisticalBaseline().fit(train, kinds)
    forest = IsolationForestDetector(seed=0, n_estimators=20).fit(train, kinds)
    x = blob(rng, 50, 3.0)
    k = kinds[:50]
    combined = HybridDetector(baseline, forest).score(x, k)
    assert np.array_equal(combined, np.maximum(baseline.score(x, k), forest.score(x, k)))


def test_classifier_is_reproducible_for_a_seed():
    rng = np.random.default_rng(2)
    X = blob(rng, 300)
    kinds = np.array(["motor"] * 300)
    y = np.array(["normal", "overheating", "bearing_wear"] * 100)
    first = FaultClassifier(seed=3).fit(X, kinds, y).predict(X[:20], kinds[:20])
    second = FaultClassifier(seed=3).fit(X, kinds, y).predict(X[:20], kinds[:20])
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])


def test_group_split_has_no_run_leakage():
    frame = pd.DataFrame({"run_id": np.repeat([f"r{i}" for i in range(20)], 10)})
    train, test = next(
        GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=0).split(
            frame, groups=frame["run_id"]
        )
    )
    assert not set(frame.iloc[train]["run_id"]) & set(frame.iloc[test]["run_id"])


def test_rules_identify_each_fault():
    x = np.zeros(N)
    assert rule_diagnosis(x)[0] == "normal"
    index = {n: i for i, n in enumerate(FEATURE_NAMES)}
    for feature, value, fault in [
        ("leak_ratio", 0.2, "pump_leak"),
        ("winding_temp_c_mean", 95.0, "overheating"),
        ("vibration_per_speed", 4.0, "bearing_wear"),
    ]:
        sample = np.zeros(N)
        sample[index[feature]] = value
        assert rule_diagnosis(sample)[0] == fault


def test_recommendation_levels():
    assert recommend(0.01, 0.05, "normal")["level"] == "low"
    assert recommend(0.3, 0.1, "normal")["level"] == "medium"
    assert recommend(0.9, 0.1, "bearing_wear")["level"] == "high"
    assert "bearing" in recommend(0.9, 0.1, "bearing_wear")["action"]


def test_metrics_values():
    y = np.array([True, True, False, False])
    metrics = detection_metrics(y, np.array([2.0, 0.5, 0.1, 2.0]))
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["false_positive_rate"] == 0.5


def test_undefined_metrics_are_none():
    assert detection_metrics(np.array([False, False]), np.array([0.0, 0.0]))["roc_auc"] is None
    assert summarize([None])["mean"] is None


def test_sustained_alarm_ignores_single_spike():
    times = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    assert sustained_first_alarm(times, np.array([2, 0, 2, 2, 0.0])) == 3.0
    assert sustained_first_alarm(times, np.array([2, 0, 2, 0, 2.0])) is None


def test_diagnosed_fault_is_never_routine_even_at_zero_risk():
    # Past a failure threshold the short-horizon risk is zero, but the fault is still present.
    for fault in ("pump_leak", "overheating", "bearing_wear"):
        result = recommend(0.0, 0.02, fault)
        assert result["level"] == "high"
        assert "routine" not in result["action"]
