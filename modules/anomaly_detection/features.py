"""Sliding-window features per rotating machine.

Samples are binned by telemetry period and reduced to the median across redundant
sensors first, so a single bad sensor has limited influence on any feature.
"""

from __future__ import annotations

from collections import defaultdict, deque

import numpy as np

from simulation.factory.layout import MachineSpec

WINDOW_S = 120.0
HOP_S = 30.0
BIN_S = 5.0
KINDS = ("motor", "conveyor", "robot", "pump")
BASE_SIGNALS = (
    "speed",
    "current",
    "power",
    "winding_temp_c",
    "bearing_temp_c",
    "vibration_mm_s",
    "flow",
    "suction",
    "pressure_bar",
)
STATS = ("mean", "std", "slope")
FEATURE_NAMES = tuple(f"{s}_{stat}" for s in BASE_SIGNALS for stat in STATS) + (
    "vibration_per_speed",
    "leak_ratio",
    "pressure_per_speed2",
    "power_per_speed",
)
_RATED_FLOW = 120.0
_SQRT3_V_PF = 1.732 * 400.0 * 0.86 / 1000.0


class MachineWindow:
    def __init__(self, spec: MachineSpec) -> None:
        self.spec = spec
        self.rated_current = max(spec.rated_power_kw, 1e-6) / _SQRT3_V_PF
        self.samples: dict[str, deque[tuple[float, float]]] = defaultdict(deque)

    def add(self, sim_time: float, signal: str, value: float) -> None:
        self.samples[signal].append((sim_time, value))

    def _prune(self, now: float) -> None:
        cutoff = now - WINDOW_S
        for series in self.samples.values():
            while series and series[0][0] < cutoff:
                series.popleft()

    def _binned(self, signal: str) -> tuple[np.ndarray, np.ndarray]:
        bins: dict[int, list[float]] = defaultdict(list)
        for t, v in self.samples.get(signal, ()):
            bins[int(t // BIN_S)].append(v)
        if not bins:
            return np.empty(0), np.empty(0)
        keys = sorted(bins)
        return np.array(keys, float) * BIN_S, np.array([np.median(bins[k]) for k in keys])

    def features(self, now: float) -> dict[str, float] | None:
        """Return features, or None when the window has too little data to be meaningful."""
        self._prune(now)
        scale = {
            "rpm": ("speed", max(self.spec.rated_rpm, 1.0)),
            "current_a": ("current", self.rated_current),
            "power_kw": ("power", max(self.spec.rated_power_kw, 1e-6)),
            "winding_temp_c": ("winding_temp_c", 1.0),
            "bearing_temp_c": ("bearing_temp_c", 1.0),
            "vibration_mm_s": ("vibration_mm_s", 1.0),
            "flow_m3h": ("flow", _RATED_FLOW),
            "suction_flow_m3h": ("suction", _RATED_FLOW),
            "pressure_bar": ("pressure_bar", 1.0),
        }
        out = {name: 0.0 for name in FEATURE_NAMES}
        means: dict[str, float] = {}
        coverage = 0
        for signal, (name, divisor) in scale.items():
            times, values = self._binned(signal)
            if len(values) == 0:
                continue
            values = values / divisor
            means[name] = float(values.mean())
            out[f"{name}_mean"] = means[name]
            out[f"{name}_std"] = float(values.std())
            if len(values) >= 3:
                # Per-minute trend.
                out[f"{name}_slope"] = float(np.polyfit(times - times[0], values, 1)[0] * 60.0)
            if signal == "rpm":
                coverage = len(values)
        if coverage < 0.5 * WINDOW_S / BIN_S:
            return None
        speed = max(means.get("speed", 0.0), 0.05)
        out["vibration_per_speed"] = means.get("vibration_mm_s", 0.0) / speed
        out["power_per_speed"] = means.get("power", 0.0) / speed
        out["pressure_per_speed2"] = means.get("pressure_bar", 0.0) / speed**2
        if means.get("suction", 0.0) > 0.01:
            out["leak_ratio"] = 1.0 - means.get("flow", 0.0) / means["suction"]
        return out


def to_vector(features: dict[str, float]) -> np.ndarray:
    return np.array([features[name] for name in FEATURE_NAMES], dtype=float)
