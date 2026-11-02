"""Fault classification with a random forest, plus a rule-based fallback and baseline."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from modules.anomaly_detection.features import FEATURE_NAMES, KINDS

FAULT_CLASSES = ("normal", "bearing_wear", "overheating", "pump_leak")


def with_kind(X: np.ndarray, kinds: np.ndarray) -> np.ndarray:
    one_hot = np.stack([(kinds == k).astype(float) for k in KINDS], axis=1)
    return np.hstack([X, one_hot])


class FaultClassifier:
    def __init__(self, seed: int = 0) -> None:
        self.model = RandomForestClassifier(
            n_estimators=100,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=1,
        )

    def fit(self, X: np.ndarray, kinds: np.ndarray, labels: np.ndarray) -> FaultClassifier:
        self.model.fit(with_kind(X, kinds), labels)
        return self

    def predict(self, X: np.ndarray, kinds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        probs = self.model.predict_proba(with_kind(X, kinds))
        return self.model.classes_[probs.argmax(axis=1)], probs.max(axis=1)


_INDEX = {n: i for i, n in enumerate(FEATURE_NAMES)}


def rule_diagnosis(x: np.ndarray) -> tuple[str, float]:
    """Hand-written thresholds. Used as the baseline and when no model is trained."""
    if x[_INDEX["leak_ratio"]] > 0.05:
        return "pump_leak", 0.6
    if x[_INDEX["winding_temp_c_mean"]] > 85.0:
        return "overheating", 0.6
    if x[_INDEX["vibration_per_speed"]] > 2.2:
        return "bearing_wear", 0.6
    return "normal", 0.6


def rule_predict(X: np.ndarray) -> np.ndarray:
    return np.array([rule_diagnosis(row)[0] for row in X])
