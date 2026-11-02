"""Deterministic local protection that runs on the gateway with or without the cloud.

Limits act on the median of redundant sensors, so one manipulated sensor cannot
trigger or suppress an action. No ML output reaches this code path.
"""

from __future__ import annotations

from dataclasses import dataclass

TEMP_DERATE_C = 105.0
TEMP_TRIP_C = 130.0
VIB_DERATE_MM_S = 7.1
VIB_TRIP_MM_S = 9.0
VIB_TRIP_DERATED_MM_S = 5.0
DERATE_SPEED = 0.6
MIN_VOTES = 2


@dataclass(frozen=True)
class EdgeAction:
    machine_id: str
    command: str
    value: float | None
    reason: str


class EdgePolicy:
    def __init__(self) -> None:
        self._derated: set[str] = set()
        self._tripped: set[str] = set()

    def clear(self, machine_id: str) -> None:
        self._derated.discard(machine_id)
        self._tripped.discard(machine_id)

    def evaluate(
        self, machine_id: str, medians: dict[str, float], votes: dict[str, int]
    ) -> list[EdgeAction]:
        def trusted(signal: str) -> float | None:
            return medians.get(signal) if votes.get(signal, 0) >= MIN_VOTES else None

        temp = trusted("winding_temp_c")
        vib = trusted("vibration_mm_s")
        if machine_id in self._tripped:
            return []
        # Vibration scales with speed, so a derated machine trips at a lower limit.
        vib_trip = VIB_TRIP_DERATED_MM_S if machine_id in self._derated else VIB_TRIP_MM_S
        if (temp is not None and temp >= TEMP_TRIP_C) or (vib is not None and vib >= vib_trip):
            self._tripped.add(machine_id)
            return [EdgeAction(machine_id, "stop", None, f"interlock trip temp={temp} vib={vib}")]
        if machine_id not in self._derated and (
            (temp is not None and temp >= TEMP_DERATE_C)
            or (vib is not None and vib >= VIB_DERATE_MM_S)
        ):
            self._derated.add(machine_id)
            return [
                EdgeAction(
                    machine_id, "set_speed", DERATE_SPEED, f"edge derate temp={temp} vib={vib}"
                )
            ]
        return []
