"""Who may command which simulated actuator, and under what evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from simulation.actuators.limits import validate_command

AUTO_CONFIDENCE = 0.8
LOW_IMPACT_MIN_SPEED = 0.5


class Impact(StrEnum):
    LOW = "low"
    HIGH = "high"


class Decision(StrEnum):
    ALLOW = "allow"
    NEEDS_APPROVAL = "needs_approval"
    DENY = "deny"


@dataclass(frozen=True)
class Authorization:
    decision: Decision
    impact: Impact
    reason: str


def classify_impact(command: str, value: float | None) -> Impact:
    if command == "set_speed" and value is not None and value >= LOW_IMPACT_MIN_SPEED:
        return Impact.LOW
    return Impact.HIGH


def authorize(
    command: str,
    value: float | None,
    confidence: float | None = None,
    approved_by: str | None = None,
) -> Authorization:
    """Deny out-of-limit commands always; otherwise automation needs low impact and confidence.

    A human approver may authorize any valid command, because the reviewer rather than
    the model then owns the decision.
    """
    impact = classify_impact(command, value)
    limits = validate_command(command, value)
    if not limits.accepted:
        return Authorization(Decision.DENY, impact, limits.detail)
    if approved_by:
        return Authorization(Decision.ALLOW, impact, f"approved by {approved_by}")
    if impact is Impact.HIGH:
        return Authorization(Decision.NEEDS_APPROVAL, impact, "high-impact command")
    if confidence is None or confidence < AUTO_CONFIDENCE:
        shown = "unknown" if confidence is None else f"{confidence:.2f}"
        return Authorization(
            Decision.NEEDS_APPROVAL, impact, f"confidence {shown} below {AUTO_CONFIDENCE}"
        )
    return Authorization(Decision.ALLOW, impact, f"low impact, confidence {confidence:.2f}")
