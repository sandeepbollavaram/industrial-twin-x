"""Hard actuator limits enforced by the simulated device, whoever sends the command."""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_RUNNING_SPEED = 0.3
MAX_SPEED = 1.0
KNOWN_COMMANDS = frozenset({"set_speed", "stop", "start", "repair", "isolate", "release"})


@dataclass(frozen=True)
class CommandResult:
    accepted: bool
    detail: str


def validate_command(name: str, value: float | None) -> CommandResult:
    if name not in KNOWN_COMMANDS:
        return CommandResult(False, f"unknown command {name}")
    if name == "set_speed":
        if value is None or not math.isfinite(value):
            return CommandResult(False, "set_speed requires a finite value")
        if not MIN_RUNNING_SPEED <= value <= MAX_SPEED:
            return CommandResult(
                False, f"speed {value} outside safe range {MIN_RUNNING_SPEED}-{MAX_SPEED}"
            )
    return CommandResult(True, "valid")
