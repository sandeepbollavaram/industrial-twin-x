"""Incident lifecycle: an explicit state machine with an append-only audit trail."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from modules.recovery_engine.authorization import Decision, authorize

VERIFY_S = 300.0
COMMAND_OF = {
    "bearing_wear": ("set_speed", 0.6),
    "overheating": ("set_speed", 0.6),
    "pump_leak": ("stop", None),
}


class State(StrEnum):
    DETECTED = "detected"
    DIAGNOSED = "diagnosed"
    AWAITING_APPROVAL = "awaiting_approval"
    MITIGATING = "mitigating"
    VERIFYING = "verifying"
    RECOVERED = "recovered"
    ESCALATED = "escalated"
    REJECTED = "rejected"


TRANSITIONS: dict[State, frozenset[State]] = {
    State.DETECTED: frozenset({State.DIAGNOSED, State.MITIGATING}),
    State.DIAGNOSED: frozenset({State.AWAITING_APPROVAL, State.MITIGATING, State.ESCALATED}),
    State.AWAITING_APPROVAL: frozenset({State.MITIGATING, State.REJECTED}),
    State.MITIGATING: frozenset({State.VERIFYING, State.ESCALATED}),
    State.VERIFYING: frozenset({State.RECOVERED, State.ESCALATED}),
    State.ESCALATED: frozenset({State.AWAITING_APPROVAL, State.MITIGATING, State.RECOVERED}),
    State.RECOVERED: frozenset(),
    State.REJECTED: frozenset(),
}
OPEN_STATES = frozenset(set(State) - {State.RECOVERED, State.REJECTED})


class InvalidTransition(Exception):
    pass


@dataclass
class Incident:
    incident_id: str
    machine_id: str
    fault: str
    confidence: float
    opened_at: float
    source: str
    state: State = State.DETECTED
    command: str | None = None
    value: float | None = None
    mitigated_at: float | None = None
    closed_at: float | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "machine_id": self.machine_id,
            "fault": self.fault,
            "confidence": self.confidence,
            "opened_at": self.opened_at,
            "source": self.source,
            "state": self.state.value,
            "command": self.command,
            "value": self.value,
            "mitigated_at": self.mitigated_at,
            "closed_at": self.closed_at,
            "audit": list(self.audit),
        }


CommandSender = Callable[[str, str, float | None, str], None]
AuditSink = Callable[[Incident, dict[str, Any]], None]


class IncidentManager:
    def __init__(
        self,
        send_command: CommandSender,
        verifier: Callable[[str, str], bool],
        on_audit: AuditSink | None = None,
    ) -> None:
        self.send_command = send_command
        self.verifier = verifier
        self.on_audit = on_audit
        self.incidents: dict[str, Incident] = {}

    def open_for(self, machine_id: str) -> Incident | None:
        return next(
            (
                i
                for i in self.incidents.values()
                if i.machine_id == machine_id and i.state in OPEN_STATES
            ),
            None,
        )

    def _log(self, incident: Incident, now: float, event: str, actor: str, detail: str) -> None:
        entry = {
            "sim_time": now,
            "event": event,
            "actor": actor,
            "detail": detail,
            "state": incident.state.value,
        }
        incident.audit.append(entry)
        if self.on_audit:
            self.on_audit(incident, entry)

    def _to(self, incident: Incident, state: State, now: float, actor: str, detail: str) -> None:
        if state not in TRANSITIONS[incident.state]:
            raise InvalidTransition(f"{incident.state} -> {state}")
        incident.state = state
        if state in (State.RECOVERED, State.REJECTED):
            incident.closed_at = now
        self._log(incident, now, "transition", actor, detail)

    def report_fault(
        self, machine_id: str, fault: str, confidence: float, now: float, source: str = "ai"
    ) -> Incident:
        existing = self.open_for(machine_id)
        if existing:
            return existing
        incident = Incident(uuid.uuid4().hex[:12], machine_id, fault, confidence, now, source)
        self.incidents[incident.incident_id] = incident
        self._log(incident, now, "opened", source, f"{fault} confidence {confidence:.2f}")
        self._to(incident, State.DIAGNOSED, now, source, f"diagnosis {fault}")
        if fault not in COMMAND_OF:
            self._to(incident, State.ESCALATED, now, "recovery-engine", "no automatic playbook")
            return incident
        incident.command, incident.value = COMMAND_OF[fault]
        verdict = authorize(incident.command, incident.value, confidence=confidence)
        if verdict.decision is Decision.ALLOW:
            self._mitigate(incident, now, "recovery-engine", verdict.reason)
        else:
            self._to(incident, State.AWAITING_APPROVAL, now, "recovery-engine", verdict.reason)
        return incident

    def report_edge_action(
        self, machine_id: str, command: str, now: float, detail: str
    ) -> Incident:
        """The edge already acted locally, so central records the action and verifies it."""
        incident = self.open_for(machine_id)
        if incident is None:
            incident = Incident(
                uuid.uuid4().hex[:12], machine_id, "edge_protection", 1.0, now, "edge"
            )
            self.incidents[incident.incident_id] = incident
            self._log(incident, now, "opened", "edge", detail)
        if incident.state in (State.DETECTED, State.DIAGNOSED, State.AWAITING_APPROVAL):
            incident.command = command
            incident.mitigated_at = now
            self._to(incident, State.MITIGATING, now, "edge", detail)
        else:
            self._log(incident, now, "edge_action", "edge", detail)
        return incident

    def approve(self, incident_id: str, approver: str, now: float) -> Incident:
        incident = self.incidents[incident_id]
        if incident.state is not State.AWAITING_APPROVAL or incident.command is None:
            raise InvalidTransition(f"cannot approve in state {incident.state}")
        verdict = authorize(incident.command, incident.value, approved_by=approver)
        if verdict.decision is not Decision.ALLOW:
            raise InvalidTransition(verdict.reason)
        self._mitigate(incident, now, approver, verdict.reason)
        return incident

    def reject(self, incident_id: str, approver: str, now: float) -> Incident:
        incident = self.incidents[incident_id]
        self._to(incident, State.REJECTED, now, approver, "rejected by operator")
        return incident

    def request_repair(self, incident_id: str, approver: str, now: float) -> Incident:
        """Simulated maintenance completion: a human-only, high-impact command."""
        incident = self.incidents[incident_id]
        if incident.state not in OPEN_STATES:
            raise InvalidTransition(f"incident already closed: {incident.state}")
        verdict = authorize("repair", None, approved_by=approver)
        self.send_command(incident.machine_id, "repair", None, incident.incident_id)
        self._log(incident, now, "command", approver, f"repair: {verdict.reason}")
        if State.RECOVERED in TRANSITIONS[incident.state]:
            self._to(incident, State.RECOVERED, now, approver, "maintenance completed")
        else:
            incident.state = State.ESCALATED
            self._to(incident, State.RECOVERED, now, approver, "maintenance completed")
        return incident

    def _mitigate(self, incident: Incident, now: float, actor: str, reason: str) -> None:
        assert incident.command is not None
        self.send_command(
            incident.machine_id, incident.command, incident.value, incident.incident_id
        )
        incident.mitigated_at = now
        self._to(incident, State.MITIGATING, now, actor, f"{incident.command}: {reason}")

    def tick(self, now: float) -> None:
        """Advance time-based states; the verifier decides from reported twin state."""
        for incident in self.incidents.values():
            if incident.state is State.MITIGATING and incident.mitigated_at is not None:
                if now - incident.mitigated_at >= 30.0:
                    self._to(incident, State.VERIFYING, now, "recovery-engine", "verifying effect")
            elif incident.state is State.VERIFYING and incident.mitigated_at is not None:
                if now - incident.mitigated_at >= VERIFY_S:
                    if self.verifier(incident.machine_id, incident.fault):
                        self._to(incident, State.RECOVERED, now, "recovery-engine", "stable")
                    else:
                        self._to(
                            incident, State.ESCALATED, now, "recovery-engine", "fault persists"
                        )
