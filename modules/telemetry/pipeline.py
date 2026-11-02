"""Central processing, independent of MQTT and the database.

Live mode feeds it from the broker. Tests and experiments feed it from the simulator
directly, so all of them exercise the same logic.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from modules.anomaly_detection.features import HOP_S, MachineWindow, to_vector
from modules.cybersecurity.integrity import IntegrityMonitor
from modules.digital_twin.engine import TwinEngine
from modules.fault_diagnosis.classifier import rule_diagnosis
from modules.predictive_maintenance.models import recommend
from modules.recovery_engine.manager import Incident, IncidentManager
from modules.telemetry.schema import AlertMessage, CommandMessage, StatusMessage, TelemetryMessage
from simulation.factory.layout import ROTATING_KINDS, FactorySpec

SUSTAIN_WINDOWS = 2
ANOMALY_LIMIT = 1.0


@dataclass
class Assessment:
    machine_id: str
    sim_time: float
    anomaly_score: float
    is_anomaly: bool
    fault: str
    confidence: float
    degradation: float | None
    failure_risk: float | None
    recommendation: dict[str, str]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


Observer = Callable[[str, dict[str, Any]], None]
CommandTransport = Callable[[CommandMessage], None]


class CentralPipeline:
    def __init__(
        self,
        spec: FactorySpec,
        ai: Any | None = None,
        transport: CommandTransport | None = None,
        observer: Observer | None = None,
        auto_diagnose: bool = True,
    ) -> None:
        self.spec = spec
        self.ai = ai
        self.transport = transport
        self.observer = observer
        self.auto_diagnose = auto_diagnose
        self.lock = threading.RLock()
        self.twin = TwinEngine(spec)
        self.integrity = IntegrityMonitor()
        self.manager = IncidentManager(self._send_machine_command, self._verify, self._audit)
        self.windows = {
            m.machine_id: MachineWindow(m) for m in spec.machines if m.kind in ROTATING_KINDS
        }
        self.last_eval: dict[str, float] = {}
        self.streak: dict[str, int] = {}
        self.assessments: dict[str, Assessment] = {}
        self.alerts: deque[dict[str, Any]] = deque(maxlen=500)
        self.network: dict[str, Any] = {"gateways": []}
        self.invalid_messages = 0
        self.accepted_messages = 0
        self.sim_time = 0.0
        self.scenario_id = "normal"
        self.first_detection: dict[str, float] = {}
        self.alarm_history: dict[str, list[float]] = {}

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self.observer:
            self.observer(kind, payload)

    def _audit(self, incident: Incident, entry: dict[str, Any]) -> None:
        self._emit("audit", {"incident": incident.to_dict(), "entry": entry})

    # ------------------------------------------------------------------ ingestion

    def handle(self, kind: str, payload: dict[str, Any], arrival: float | None = None) -> None:
        with self.lock:
            if kind == "telemetry":
                self.handle_telemetry(payload)
            elif kind == "alert":
                self.handle_alert(payload)
            elif kind == "status":
                self.handle_status(payload)
            elif kind == "network":
                self.network = payload

    def handle_telemetry(self, payload: dict[str, Any]) -> bool:
        try:
            message = TelemetryMessage.model_validate(payload)
        except ValidationError:
            self.invalid_messages += 1
            return False
        if not self.twin.ingest(message):
            return False
        self.accepted_messages += 1
        self._emit("telemetry", message.model_dump())
        self.scenario_id = message.scenario_id
        if message.replayed:
            return True
        if message.sim_time < self.sim_time - 2 * HOP_S:
            self._reset_analytics()
        self.sim_time = max(self.sim_time, message.sim_time)
        findings = self.integrity.observe(
            message.machine_id,
            message.device_id,
            message.sim_time,
            message.readings,
            machine_running=message.status == "running",
        )
        for finding in findings:
            self._on_integrity(finding)
        window = self.windows.get(message.machine_id)
        if window is not None:
            for signal, value in message.readings.items():
                if not self.integrity.is_quarantined(message.device_id, signal):
                    window.add(message.sim_time, signal, value)
            if self.auto_diagnose:
                self._maybe_assess(message.machine_id, message.sim_time)
        self.manager.tick(self.sim_time)
        return True

    def _reset_analytics(self) -> None:
        """Simulation clock moved backwards: a new run started, so old windows are invalid."""
        self.sim_time = 0.0
        self.last_eval.clear()
        self.streak.clear()
        self.assessments.clear()
        self.integrity = IntegrityMonitor()
        for machine_id, window in self.windows.items():
            self.windows[machine_id] = MachineWindow(window.spec)
        self.manager.incidents.clear()

    def _on_integrity(self, finding: Any) -> None:
        alert = {
            "schema_version": "1.0",
            "source": "integrity-monitor",
            "machine_id": finding.machine_id,
            "sim_time": finding.sim_time,
            "severity": "critical",
            "code": finding.kind,
            "message": f"{finding.sensor_id}: {finding.detail}. Sensor quarantined.",
        }
        self.handle_alert(alert)
        self._emit("finding", finding.__dict__)
        self.first_detection.setdefault(f"tamper:{finding.machine_id}", finding.sim_time)

    def handle_alert(self, payload: dict[str, Any]) -> None:
        try:
            alert = AlertMessage.model_validate(payload)
        except ValidationError:
            self.invalid_messages += 1
            return
        record = alert.model_dump()
        self.alerts.appendleft(record)
        self._emit("alert", record)
        if alert.machine_id and alert.code.startswith("edge_"):
            command = alert.code.removeprefix("edge_")
            self.alarm_history.setdefault(alert.machine_id, []).append(alert.sim_time)
            self.manager.report_edge_action(
                alert.machine_id, command, alert.sim_time, alert.message
            )

    def handle_status(self, payload: dict[str, Any]) -> None:
        try:
            status = StatusMessage.model_validate(payload)
        except ValidationError:
            self.invalid_messages += 1
            return
        self._emit("status", status.model_dump())
        if status.accepted:
            if status.detail == "device isolated":
                self.twin.set_isolated(status.device_id, True)
            elif status.detail == "device released":
                self.twin.set_isolated(status.device_id, False)

    # ------------------------------------------------------------------ analytics

    def _maybe_assess(self, machine_id: str, now: float) -> None:
        if now - self.last_eval.get(machine_id, -1e9) < HOP_S:
            return
        self.last_eval[machine_id] = now
        window = self.windows[machine_id]
        features = window.features(now)
        if features is None:
            return
        assessment = self._assess(machine_id, window.spec.kind, now, features)
        self.assessments[machine_id] = assessment
        self._emit("assessment", assessment.to_dict())
        if assessment.is_anomaly:
            self.streak[machine_id] = self.streak.get(machine_id, 0) + 1
        else:
            self.streak[machine_id] = 0
        if self.streak.get(machine_id, 0) >= SUSTAIN_WINDOWS:
            self.alarm_history.setdefault(machine_id, []).append(now)
        if self.streak.get(machine_id, 0) >= SUSTAIN_WINDOWS and assessment.fault != "normal":
            self.manager.report_fault(machine_id, assessment.fault, assessment.confidence, now)

    def _assess(
        self, machine_id: str, kind: str, now: float, features: dict[str, float]
    ) -> Assessment:
        x = to_vector(features)
        if self.ai is not None:
            return self.ai.assess(machine_id, kind, now, x)
        fault, confidence = rule_diagnosis(x)
        return Assessment(
            machine_id,
            now,
            2.0 if fault != "normal" else 0.0,
            fault != "normal",
            fault,
            confidence,
            None,
            None,
            recommend(0.0, 0.0, fault),
            "rules",
        )

    # ------------------------------------------------------------------ commands

    def _send_machine_command(
        self, machine_id: str, command: str, value: float | None, reference: str
    ) -> None:
        self.send_device_command(
            self.spec.controller_of(machine_id), command, value, "recovery-engine", reference
        )
        if command == "repair":
            self.integrity.release_machine(machine_id)

    def send_device_command(
        self,
        device_id: str,
        command: str,
        value: float | None,
        issued_by: str,
        command_id: str | None = None,
    ) -> CommandMessage:
        message = CommandMessage(
            command_id=command_id or uuid.uuid4().hex[:12],
            device_id=device_id,
            command=command,
            value=value,
            issued_by=issued_by,
        )
        if command == "set_speed":
            self.twin.set_desired(device_id, speed_fraction=value)
        elif command in ("start", "stop"):
            self.twin.set_desired(device_id, run_state=command)
        self._emit("command", message.model_dump())
        if self.transport:
            self.transport(message)
        return message

    def _verify(self, machine_id: str, fault: str) -> bool:
        signal = self.twin.machine_signal
        if fault == "overheating":
            temp = signal(machine_id, "winding_temp_c")
            return temp is not None and temp < 100.0
        if fault == "bearing_wear":
            vib = signal(machine_id, "vibration_mm_s")
            return vib is not None and vib < 7.1
        if fault == "pump_leak":
            rpm = signal(machine_id, "rpm")
            return rpm is not None and rpm < 100.0
        if fault == "edge_protection":
            temp = signal(machine_id, "winding_temp_c")
            vib = signal(machine_id, "vibration_mm_s")
            return temp is not None and vib is not None and temp < 100.0 and vib < 7.1
        return False


class TrainedAI:
    """Wraps persisted models behind the assessment interface."""

    def __init__(self, bundle: dict[str, Any]) -> None:
        self.bundle = bundle
        self.detector = bundle["statistical_baseline"]
        self.classifier = bundle["fault_classifier"]
        self.degradation = bundle["degradation"]
        self.risk = bundle["failure_risk"]

    def assess(self, machine_id: str, kind: str, now: float, x: np.ndarray) -> Assessment:
        X = x.reshape(1, -1)
        kinds = np.array([kind])
        score = float(self.detector.score(X, kinds)[0])
        labels, probs = self.classifier.predict(X, kinds)
        fault, confidence = str(labels[0]), float(probs[0])
        degradation = float(self.degradation.predict(X, kinds)[0])
        risk = float(self.risk.predict_proba(X, kinds)[0])
        return Assessment(
            machine_id,
            now,
            score,
            score > ANOMALY_LIMIT,
            fault,
            confidence,
            degradation,
            risk,
            recommend(risk, degradation, fault),
            "model",
        )
