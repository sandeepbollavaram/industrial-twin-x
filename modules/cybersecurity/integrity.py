"""Physics-based sensor integrity checks using redundant sensors on separate devices."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import median

SLOW_SIGNAL_TOLERANCE = {
    "winding_temp_c": 4.0,
    "bearing_temp_c": 4.0,
    "vibration_mm_s": 0.6,
    "pressure_bar": 0.3,
    "fluid_temp_c": 2.0,
    "transformer_temp_c": 3.0,
}
FROZEN_SIGNALS = frozenset(SLOW_SIGNAL_TOLERANCE) | {"rpm", "flow_m3h", "suction_flow_m3h"}
MIN_PEERS = 3
DISAGREE_COUNT = 6
FROZEN_COUNT = 12


@dataclass(frozen=True)
class IntegrityFinding:
    sensor_id: str
    device_id: str
    machine_id: str
    signal: str
    kind: str
    sim_time: float
    detail: str


class IntegrityMonitor:
    def __init__(self) -> None:
        self.latest: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
        self.disagree: dict[str, int] = defaultdict(int)
        self.repeat: dict[str, tuple[float, int]] = {}
        self.quarantined: set[str] = set()
        self.findings: list[IntegrityFinding] = []

    def is_quarantined(self, device_id: str, signal: str) -> bool:
        return f"{device_id}.{signal}" in self.quarantined

    def release_machine(self, machine_id: str) -> None:
        self.quarantined = {s for s in self.quarantined if not s.startswith(f"{machine_id}-")}
        for key in list(self.latest):
            if key[0] == machine_id:
                del self.latest[key]
        self.disagree.clear()
        self.repeat.clear()

    def observe(
        self,
        machine_id: str,
        device_id: str,
        sim_time: float,
        readings: dict[str, float],
        machine_running: bool = True,
    ) -> list[IntegrityFinding]:
        new: list[IntegrityFinding] = []
        for signal, value in readings.items():
            sensor_id = f"{device_id}.{signal}"
            if sensor_id in self.quarantined:
                continue
            finding = self._check_frozen(sensor_id, signal, value, machine_running)
            kind_detail = finding
            if kind_detail is None and signal in SLOW_SIGNAL_TOLERANCE:
                kind_detail = self._check_disagreement(machine_id, device_id, signal, value)
            if kind_detail is not None:
                kind, detail = kind_detail
                record = IntegrityFinding(
                    sensor_id, device_id, machine_id, signal, kind, sim_time, detail
                )
                self.quarantined.add(sensor_id)
                self.findings.append(record)
                new.append(record)
        return new

    def _check_frozen(
        self, sensor_id: str, signal: str, value: float, running: bool
    ) -> tuple[str, str] | None:
        if signal not in FROZEN_SIGNALS or not running or value == 0.0:
            self.repeat.pop(sensor_id, None)
            return None
        last = self.repeat.get(sensor_id)
        count = last[1] + 1 if last and last[0] == value else 1
        self.repeat[sensor_id] = (value, count)
        if count >= FROZEN_COUNT:
            return "sensor_frozen", f"value {value} repeated {count} samples despite expected noise"
        return None

    def _check_disagreement(
        self, machine_id: str, device_id: str, signal: str, value: float
    ) -> tuple[str, str] | None:
        sensor_id = f"{device_id}.{signal}"
        latest = self.latest[(machine_id, signal)]
        latest[sensor_id] = value
        peers = [v for s, v in latest.items() if s != sensor_id and s not in self.quarantined]
        if len(peers) < MIN_PEERS:
            return None
        reference = median(peers)
        tolerance = SLOW_SIGNAL_TOLERANCE[signal]
        if abs(value - reference) > tolerance:
            self.disagree[sensor_id] += 1
        else:
            self.disagree[sensor_id] = 0
        if self.disagree[sensor_id] >= DISAGREE_COUNT:
            return "sensor_disagreement", (
                f"value {value:.2f} differs from peer median {reference:.2f} by more than "
                f"{tolerance} for {DISAGREE_COUNT} samples"
            )
        return None
