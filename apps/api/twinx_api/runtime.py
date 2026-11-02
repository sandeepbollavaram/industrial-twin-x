"""Long-lived services behind the API: MQTT bridge, pipeline and batched persistence."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import joblib
import paho.mqtt.client as mqtt
from sqlalchemy import Engine, create_engine, insert, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modules.telemetry import topics
from modules.telemetry.pipeline import CentralPipeline, TrainedAI
from modules.telemetry.schema import CommandMessage
from simulation.factory.layout import build_factory
from twinx_api.db import AuditEntry, Device, Event, Telemetry, TwinState
from twinx_api.settings import Settings

log = logging.getLogger("twinx.api")
QUEUE_LIMIT = 20000
BATCH_LIMIT = 500
FLUSH_INTERVAL_S = 1.0
TWIN_SYNC_S = 5.0
HISTORY_POINTS = 720


class BatchWriter(threading.Thread):
    """Bounded queue drained in batches. On overload it drops and counts, never blocks ingest."""

    def __init__(self, engine) -> None:
        super().__init__(daemon=True, name="batch-writer")
        self.engine = engine
        self.queue: queue.Queue[tuple[Any, dict]] = queue.Queue(maxsize=QUEUE_LIMIT)
        self.stop_event = threading.Event()
        self.dropped = 0
        self.written = 0
        self.failed_batches = 0
        self.latency_ms: deque[float] = deque(maxlen=200)
        self.connected = False

    def put(self, table: Any, row: dict) -> None:
        try:
            self.queue.put_nowait((table, row))
        except queue.Full:
            self.dropped += 1

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.flush()
            self.stop_event.wait(FLUSH_INTERVAL_S)
        self.flush()

    def flush(self) -> None:
        while not self.queue.empty():
            batches: dict[Any, list[dict]] = defaultdict(list)
            for _ in range(BATCH_LIMIT):
                try:
                    table, row = self.queue.get_nowait()
                except queue.Empty:
                    break
                batches[table].append(row)
            started = time.perf_counter()
            count = sum(len(rows) for rows in batches.values())
            try:
                with self.engine.begin() as connection:
                    for table, rows in batches.items():
                        connection.execute(insert(table), rows)
                self.written += count
                self.connected = True
                self.latency_ms.append((time.perf_counter() - started) * 1000.0)
            except Exception as exc:  # A database outage must not stop the digital twin.
                self.failed_batches += 1
                self.dropped += count
                self.connected = False
                log.warning("batch write failed: %s", type(exc).__name__)
                return


class Runtime:
    def __init__(self, settings: Settings | None = None, connect: bool = True) -> None:
        self.settings = settings or Settings()
        self.spec = build_factory(factory_id=self.settings.factory_id)
        self.ai_version: str | None = None
        self.pipeline = CentralPipeline(
            self.spec, ai=self._load_ai(), transport=self._send_command, observer=self._observe
        )
        self.history: dict[str, dict[str, deque[tuple[float, float]]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=HISTORY_POINTS))
        )
        self.findings: deque[dict[str, Any]] = deque(maxlen=200)
        self.commands: deque[dict[str, Any]] = deque(maxlen=200)
        self.message_times: deque[float] = deque(maxlen=5000)
        self.latency_ms: deque[float] = deque(maxlen=1000)
        self.last_sim_time = 0.0
        self.mqtt_connected = False
        self.mqtt_reconnects = 0
        self.engine: Engine | None = None
        self.writer: BatchWriter | None = None
        self.client: mqtt.Client | None = None
        self.stopping = threading.Event()
        self.connect = connect

    def _load_ai(self) -> TrainedAI | None:
        path = Path(self.settings.model_path)
        if not path.exists():
            log.warning("no trained models at %s; using rule-based diagnosis", path)
            return None
        bundle = joblib.load(path)
        self.ai_version = bundle["version"]
        return TrainedAI(bundle)

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if not self.connect:
            return
        self.engine = create_engine(self.settings.database_url, pool_pre_ping=True, pool_size=3)
        self.writer = BatchWriter(self.engine)
        self._seed_registry()
        self.writer.start()
        threading.Thread(target=self._twin_sync_loop, daemon=True, name="twin-sync").start()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twinx-api")
        client.max_queued_messages_set(1000)
        client.reconnect_delay_set(min_delay=1, max_delay=15)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=30)
        client.loop_start()
        self.client = client

    def stop(self) -> None:
        self.stopping.set()
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        if self.writer:
            self.writer.stop_event.set()
            self.writer.join(timeout=5)

    def _seed_registry(self) -> None:
        rows = [
            {
                "device_id": d.device_id,
                "machine_id": d.machine_id,
                "zone_id": d.zone_id,
                "gateway_id": d.gateway_id,
                "role": d.role,
                "sensors": [s.signal for s in d.sensors],
            }
            for d in self.spec.devices
        ]
        assert self.engine is not None and self.writer is not None
        try:
            with self.engine.begin() as connection:
                connection.execute(pg_insert(Device).values(rows).on_conflict_do_nothing())
            self.writer.connected = True
        except Exception as exc:
            log.warning("registry seed failed: %s", type(exc).__name__)

    def _twin_sync_loop(self) -> None:
        assert self.engine is not None
        while not self.stopping.wait(TWIN_SYNC_S):
            rows = [
                {
                    "device_id": t["device_id"],
                    "reported": t["reported"],
                    "desired": t["desired"],
                    "status": t["status"],
                    "last_sequence": t["last_sequence"],
                    "received": t["received"],
                    "gaps": t["gaps"],
                }
                for t in self.pipeline.twin.snapshot()
                if t["received"]
            ]
            if not rows:
                continue
            statement = pg_insert(TwinState).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=["device_id"],
                set_={
                    c: statement.excluded[c]
                    for c in ("reported", "desired", "status", "last_sequence", "received", "gaps")
                },
            )
            try:
                with self.engine.begin() as connection:
                    connection.execute(statement)
            except Exception as exc:
                log.warning("twin sync failed: %s", type(exc).__name__)

    # ------------------------------------------------------------------ MQTT

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = not reason_code.is_failure
        root = topics.ROOT + f"/{self.spec.factory_id}"
        client.subscribe(f"{root}/zone/+/device/+/telemetry", qos=0)
        client.subscribe(f"{root}/device/+/status", qos=1)
        client.subscribe(f"{root}/alerts", qos=1)
        client.subscribe(f"{root}/network", qos=0)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self.mqtt_connected = False
        self.mqtt_reconnects += 1

    def _on_message(self, client, userdata, message) -> None:
        try:
            payload = json.loads(message.payload)
        except ValueError:
            self.pipeline.invalid_messages += 1
            return
        topic = message.topic
        if topic.endswith("/telemetry"):
            kind = "telemetry"
        elif topic.endswith("/status"):
            kind = "status"
        elif topic.endswith("/alerts"):
            kind = "alert"
        else:
            kind = "network"
        self.pipeline.handle(kind, payload)

    def _send_command(self, command: CommandMessage) -> None:
        if self.client is None:
            return
        self.client.publish(
            topics.commands(self.spec.factory_id, command.device_id),
            command.model_dump_json(),
            qos=1,
        )

    def control(self, payload: dict[str, Any]) -> bool:
        if self.client is None or not self.mqtt_connected:
            return False
        topic = topics.control(self.spec.factory_id)
        return self.client.publish(topic, json.dumps(payload), qos=1).rc == mqtt.MQTT_ERR_SUCCESS

    # ------------------------------------------------------------------ observation

    def _observe(self, kind: str, payload: dict[str, Any]) -> None:
        if kind == "telemetry":
            if not payload["replayed"] and payload["sim_time"] < self.last_sim_time - 60.0:
                # The simulator was reset: earlier charts and logs belong to another run.
                self.history.clear()
                self.findings.clear()
                self.commands.clear()
            if not payload["replayed"]:
                self.last_sim_time = payload["sim_time"]
            now = time.time()
            self.message_times.append(now)
            if not payload["replayed"]:
                self.latency_ms.append(max(0.0, (now - payload["timestamp"]) * 1000.0))
            for signal, value in payload["readings"].items():
                self.history[payload["machine_id"]][signal].append((payload["sim_time"], value))
            if self.writer:
                self.writer.put(
                    Telemetry,
                    {
                        "device_id": payload["device_id"],
                        "machine_id": payload["machine_id"],
                        "sim_time": payload["sim_time"],
                        "source_timestamp": payload["timestamp"],
                        "sequence": payload["sequence"],
                        "scenario_id": payload["scenario_id"],
                        "status": payload["status"],
                        "readings": payload["readings"],
                        "replayed": payload["replayed"],
                    },
                )
            return
        if kind == "finding":
            self.findings.appendleft(payload)
        elif kind == "command":
            self.commands.appendleft(payload)
        if not self.writer:
            return
        if kind == "audit":
            incident, entry = payload["incident"], payload["entry"]
            self.writer.put(
                AuditEntry,
                {
                    "incident_id": incident["incident_id"],
                    "machine_id": incident["machine_id"],
                    "fault": incident["fault"],
                    "sim_time": entry["sim_time"],
                    "event": entry["event"],
                    "actor": entry["actor"],
                    "detail": entry["detail"][:500],
                    "state": entry["state"],
                },
            )
        elif kind in ("alert", "command", "finding", "status"):
            self.writer.put(
                Event, {"kind": kind, "sim_time": payload.get("sim_time"), "payload": payload}
            )

    # ------------------------------------------------------------------ views

    def database_ok(self) -> bool:
        if self.engine is None:
            return False
        try:
            with self.engine.connect() as connection:
                connection.execute(text("select 1"))
            return True
        except Exception:
            return False

    def message_rate(self, window_s: float = 10.0) -> float:
        cutoff = time.time() - window_s
        return sum(1 for t in tuple(self.message_times) if t >= cutoff) / window_s

    def machine_view(self, machine_id: str) -> dict[str, Any]:
        spec = self.spec.machine(machine_id)
        twins = self.pipeline.twin.snapshot(machine_id)
        signals: dict[str, float] = {}
        for twin in twins:
            for signal in twin["reported"]:
                if signal not in signals:
                    value = self.pipeline.twin.machine_signal(machine_id, signal)
                    if value is not None:
                        signals[signal] = value
        status = next((t["status"] for t in twins if t["received"]), "unknown")
        assessment = self.pipeline.assessments.get(machine_id)
        incident = self.pipeline.manager.open_for(machine_id)
        return {
            "machine_id": machine_id,
            "name": spec.name,
            "kind": spec.kind,
            "zone_id": spec.zone_id,
            "gateway_id": spec.gateway_id,
            "position": spec.position,
            "status": status,
            "signals": signals,
            "assessment": assessment.to_dict() if assessment else None,
            "incident": incident.to_dict() if incident else None,
            "quarantined": sorted(
                s for s in self.pipeline.integrity.quarantined if s.startswith(f"{machine_id}-")
            ),
        }

    def overview(self) -> dict[str, Any]:
        with self.pipeline.lock:
            machines = [self.machine_view(m.machine_id) for m in self.spec.machines]
            incidents = list(self.pipeline.manager.incidents.values())
            alerts = list(self.pipeline.alerts)[:20]
            twins = self.pipeline.twin.snapshot()
        latencies = sorted(self.latency_ms)
        writes = list(self.writer.latency_ms) if self.writer else []
        return {
            "simulated": True,
            "sim_time": self.pipeline.sim_time,
            "scenario_id": self.pipeline.scenario_id,
            "counts": {
                "zones": len(self.spec.zones),
                "gateways": len(self.spec.gateways),
                "machines": len(self.spec.machines),
                "devices": len(self.spec.devices),
                "sensors": self.spec.sensor_count,
                "devices_reporting": sum(1 for t in twins if t["received"]),
                "open_incidents": sum(1 for i in incidents if i.closed_at is None),
            },
            "machines": machines,
            "alerts": alerts,
            "pipeline": {
                "accepted": self.pipeline.accepted_messages,
                "invalid": self.pipeline.invalid_messages,
                "rate_per_s": self.message_rate(),
                "latency_ms_p50": latencies[len(latencies) // 2] if latencies else None,
                "latency_ms_p95": latencies[int(len(latencies) * 0.95)] if latencies else None,
            },
            "infrastructure": {
                "mqtt_connected": self.mqtt_connected,
                "mqtt_reconnects": self.mqtt_reconnects,
                "database_connected": bool(self.writer and self.writer.connected),
                "rows_written": self.writer.written if self.writer else 0,
                "rows_dropped": self.writer.dropped if self.writer else 0,
                "write_latency_ms": sum(writes) / len(writes) if writes else None,
                "model_version": self.ai_version,
            },
        }
