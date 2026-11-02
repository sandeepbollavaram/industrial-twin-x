"""Per-machine-kind anomaly detectors, each trained on normal windows only."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from modules.anomaly_detection.features import FEATURE_NAMES

THRESHOLD_QUANTILE = 0.995
_MEAN_INDEX = [i for i, n in enumerate(FEATURE_NAMES) if n.endswith("_mean")]


class StatisticalBaseline:
    """Largest absolute z-score over window means. This is the comparison baseline."""

    name = "statistical_baseline"

    def __init__(self) -> None:
        self.mu: dict[str, np.ndarray] = {}
        self.sigma: dict[str, np.ndarray] = {}
        self.threshold: dict[str, float] = {}

    def fit(self, X: np.ndarray, kinds: np.ndarray) -> StatisticalBaseline:
        for kind in np.unique(kinds):
            subset = X[kinds == kind][:, _MEAN_INDEX]
            self.mu[kind] = subset.mean(axis=0)
            self.sigma[kind] = np.maximum(subset.std(axis=0), 1e-6)
            scores = np.abs((subset - self.mu[kind]) / self.sigma[kind]).max(axis=1)
            self.threshold[kind] = float(np.quantile(scores, THRESHOLD_QUANTILE))
        return self

    def score(self, X: np.ndarray, kinds: np.ndarray) -> np.ndarray:
        """Score divided by the threshold, so values above 1 are anomalous for any kind."""
        out = np.zeros(len(X))
        for kind in np.unique(kinds):
            mask = kinds == kind
            z = np.abs((X[mask][:, _MEAN_INDEX] - self.mu[kind]) / self.sigma[kind]).max(axis=1)
            out[mask] = z / max(self.threshold[kind], 1e-6)
        return out


class IsolationForestDetector:
    name = "isolation_forest"

    def __init__(self, seed: int = 0, n_estimators: int = 100) -> None:
        self.seed = seed
        self.n_estimators = n_estimators
        self.models: dict[str, tuple[StandardScaler, IsolationForest]] = {}
        self.offset: dict[str, float] = {}
        self.threshold: dict[str, float] = {}

    def fit(self, X: np.ndarray, kinds: np.ndarray) -> IsolationForestDetector:
        for kind in np.unique(kinds):
            subset = X[kinds == kind]
            scaler = StandardScaler().fit(subset)
            forest = IsolationForest(
                n_estimators=self.n_estimators,
                contamination="auto",
                random_state=self.seed,
                n_jobs=1,
            ).fit(scaler.transform(subset))
            self.models[kind] = (scaler, forest)
            scores = -forest.score_samples(scaler.transform(subset))
            self.offset[kind] = float(np.median(scores))
            self.threshold[kind] = float(np.quantile(scores, THRESHOLD_QUANTILE))
        return self

    def score(self, X: np.ndarray, kinds: np.ndarray) -> np.ndarray:
        """Margin-normalised score: 1.0 sits exactly on the fitted threshold."""
        out = np.zeros(len(X))
        for kind in np.unique(kinds):
            mask = kinds == kind
            scaler, forest = self.models[kind]
            raw = -forest.score_samples(scaler.transform(X[mask]))
            margin = max(self.threshold[kind] - self.offset[kind], 1e-6)
            out[mask] = (raw - self.offset[kind]) / margin
        return out


class HybridDetector:
    """Alarm when either detector alarms: level shifts from the baseline, shape from the forest."""

    name = "hybrid"

    def __init__(self, baseline: StatisticalBaseline, forest: IsolationForestDetector) -> None:
        self.baseline = baseline
        self.forest = forest

    def score(self, X: np.ndarray, kinds: np.ndarray) -> np.ndarray:
        return np.maximum(self.baseline.score(X, kinds), self.forest.score(X, kinds))
