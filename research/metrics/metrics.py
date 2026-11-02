"""Metric helpers. Each returns None rather than a number when it is undefined."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score


def detection_metrics(y_true: np.ndarray, scores: np.ndarray, limit: float = 1.0) -> dict:
    y_pred = scores > limit
    negatives = int((~y_true).sum())
    auc = roc_auc_score(y_true, scores) if 0 < y_true.sum() < len(y_true) else None
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": None if auc is None else float(auc),
        "false_positive_rate": float((y_pred & ~y_true).sum() / negatives) if negatives else None,
        "positives": int(y_true.sum()),
        "negatives": negatives,
    }


def sustained_first_alarm(
    times: np.ndarray, scores: np.ndarray, limit: float = 1.0, sustain: int = 2
) -> float | None:
    """Time of the first alarm held for `sustain` consecutive windows."""
    streak = 0
    for t, s in zip(times, scores, strict=True):
        streak = streak + 1 if s > limit else 0
        if streak >= sustain:
            return float(t)
    return None


def summarize(values: Sequence[float | None]) -> dict:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    array = np.array(clean, dtype=float)
    return {
        "n": len(clean),
        "mean": float(array.mean()),
        "std": float(array.std(ddof=1)) if len(clean) > 1 else 0.0,
        "min": float(array.min()),
        "max": float(array.max()),
    }
