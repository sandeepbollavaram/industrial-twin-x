"""Degradation estimation and calibrated short-horizon failure risk.

The risk model estimates the probability of functional failure within a fixed horizon
in simulated runs. It is not a remaining useful life predictor and is not validated
against real equipment.
"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.model_selection import GroupKFold

from modules.fault_diagnosis.classifier import with_kind

HORIZON_S = 900.0


class DegradationRegressor:
    def __init__(self, seed: int = 0) -> None:
        self.model = GradientBoostingRegressor(
            n_estimators=150, max_depth=3, learning_rate=0.08, random_state=seed
        )

    def fit(self, X: np.ndarray, kinds: np.ndarray, wear: np.ndarray) -> DegradationRegressor:
        self.model.fit(with_kind(X, kinds), wear)
        return self

    def predict(self, X: np.ndarray, kinds: np.ndarray) -> np.ndarray:
        return np.clip(self.model.predict(with_kind(X, kinds)), 0.0, 1.0)


class FailureRiskModel:
    def __init__(self, seed: int = 0) -> None:
        self.seed = seed
        self.model: CalibratedClassifierCV | None = None

    def fit(
        self, X: np.ndarray, kinds: np.ndarray, y: np.ndarray, groups: np.ndarray
    ) -> FailureRiskModel:
        features = with_kind(X, kinds)
        # Calibration folds are grouped by run so no trajectory appears on both sides.
        folds = list(GroupKFold(n_splits=3).split(features, y, groups))
        base = RandomForestClassifier(
            n_estimators=60,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=self.seed,
            n_jobs=1,
        )
        self.model = CalibratedClassifierCV(base, method="isotonic", cv=folds).fit(features, y)
        return self

    def predict_proba(self, X: np.ndarray, kinds: np.ndarray) -> np.ndarray:
        assert self.model is not None
        return self.model.predict_proba(with_kind(X, kinds))[:, 1]


def recommend(risk: float, degradation: float, fault: str) -> dict[str, str]:
    if risk >= 0.6 or degradation >= 0.7:
        level, action = "high", "Schedule immediate inspection and reduce load"
    elif risk >= 0.25 or degradation >= 0.4:
        level, action = "medium", "Plan maintenance at the next production window"
    else:
        level, action = "low", "Continue routine monitoring"
    # The risk model predicts a future failure, so it falls to zero once a threshold has
    # passed. A fault diagnosed now must never read as routine.
    if fault != "normal":
        level = "high"
    if fault == "pump_leak":
        action = "Inspect discharge line for leakage"
    elif fault == "overheating":
        action = "Inspect cooling path and reduce load"
    elif fault == "bearing_wear":
        action = "Plan bearing inspection and replacement"
    return {"level": level, "action": action}
