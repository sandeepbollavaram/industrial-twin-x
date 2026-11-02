"""Digital twin state: reported state from telemetry, desired state from operators."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from modules.telemetry.schema import TelemetryMessage
from simulation.factory.layout import FactorySpec


@dataclass
class DeviceTwin:
    device_id: str
    machine_id: str
    zone_id: str
    gateway_id: str
    role: str
    reported: dict[str, float] = field(default_factory=dict)
    desired: dict[str, Any] = field(default_factory=dict)
    status: str = "unknown"
    last_sequence: int = -1
    last_sim_time: float = -1.0
    last_seen_wall: float | None = None
    received: int = 0
    gaps: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    isolated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "machine_id": self.machine_id,
            "zone_id": self.zone_id,
            "gateway_id": self.gateway_id,
            "role": self.role,
            "reported": dict(self.reported),
            "desired": dict(self.desired),
            "status": self.status,
            "last_sequence": self.last_sequence,
            "last_sim_time": self.last_sim_time,
            "last_seen_wall": self.last_seen_wall,
            "received": self.received,
            "gaps": self.gaps,
            "duplicates": self.duplicates,
            "out_of_order": self.out_of_order,
            "isolated": self.isolated,
        }


class TwinEngine:
    """Registry-backed twin store. Stale or duplicate data never overwrites newer state."""

    def __init__(self, spec: FactorySpec) -> None:
        self.spec = spec
        self._lock = threading.RLock()
        self.twins = {
            d.device_id: DeviceTwin(d.device_id, d.machine_id, d.zone_id, d.gateway_id, d.role)
            for d in spec.devices
        }
        self.rejected_unknown = 0

    def ingest(self, message: TelemetryMessage) -> bool:
        """Return True when the message was accepted as new data."""
        with self._lock:
            twin = self.twins.get(message.device_id)
            if twin is None:
                self.rejected_unknown += 1
                return False
            if message.sequence == 0 and twin.last_sequence > 0:
                # Sequence restarted, so the simulator was reset.
                twin.last_sequence = -1
                twin.reported.clear()
            if message.sequence == twin.last_sequence:
                twin.duplicates += 1
                return False
            twin.received += 1
            twin.last_seen_wall = time.time()
            if message.sequence < twin.last_sequence:
                # Late or replayed data still gets persisted, but state stays current.
                twin.out_of_order += 1
                return True
            if message.sequence > twin.last_sequence + 1:
                twin.gaps += message.sequence - twin.last_sequence - 1
            twin.last_sequence = message.sequence
            twin.last_sim_time = message.sim_time
            twin.status = message.status
            twin.reported.update(message.readings)
            return True

    def set_desired(self, device_id: str, **values: Any) -> None:
        with self._lock:
            self.twins[device_id].desired.update(values)

    def delta(self, device_id: str) -> dict[str, Any]:
        """Desired values not yet matched by reported values."""
        with self._lock:
            twin = self.twins[device_id]
            return {k: v for k, v in twin.desired.items() if twin.reported.get(k) != v}

    def set_isolated(self, device_id: str, isolated: bool) -> None:
        with self._lock:
            self.twins[device_id].isolated = isolated

    def snapshot(self, machine_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [
                t.to_dict()
                for t in self.twins.values()
                if machine_id is None or t.machine_id == machine_id
            ]

    def machine_signal(self, machine_id: str, signal: str) -> float | None:
        """Median of reported values across redundant sensors."""
        with self._lock:
            values = sorted(
                t.reported[signal]
                for t in self.twins.values()
                if t.machine_id == machine_id and signal in t.reported
            )
        return values[len(values) // 2] if values else None
