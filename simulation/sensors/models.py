"""Measurement model: calibration error, noise, quantisation, range and tampering."""

from __future__ import annotations

import numpy as np

from simulation.factory.layout import SIGNALS, SensorSpec


class Sensor:
    def __init__(self, spec: SensorSpec, rng: np.random.Generator) -> None:
        self.spec = spec
        self.signal = SIGNALS[spec.signal]
        self.rng = rng
        self.gain = 1.0 + float(rng.normal(0.0, 0.002))
        self.offset = float(rng.normal(0.0, 0.3 * self.signal.noise_sigma))
        # Contained attack state, set only by the sensor-manipulation scenario.
        self.bias = 0.0
        self.bias_target = 0.0
        self.bias_ramp_per_s = 0.0
        self.frozen_value: float | None = None
        self.freeze_requested = False

    def advance_attack(self, dt: float) -> None:
        if self.bias != self.bias_target:
            step = self.bias_ramp_per_s * dt
            delta = self.bias_target - self.bias
            self.bias = (
                self.bias_target if abs(delta) <= step else self.bias + np.sign(delta) * step
            )

    def read(self, true_value: float) -> float:
        noisy = self.gain * true_value + self.offset + self.rng.normal(0.0, self.signal.noise_sigma)
        value = float(np.clip(noisy + self.bias, self.signal.low, self.signal.high))
        value = round(value / self.signal.resolution) * self.signal.resolution
        value = round(value, 4)
        if self.freeze_requested:
            if self.frozen_value is None:
                self.frozen_value = value
            return self.frozen_value
        return value

    def clear_attack(self) -> None:
        self.bias = self.bias_target = self.bias_ramp_per_s = 0.0
        self.freeze_requested = False
        self.frozen_value = None
