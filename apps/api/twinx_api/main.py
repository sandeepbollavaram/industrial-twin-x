"""REST and WebSocket API. Bound to localhost in development; see security-design.md."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select

from modules.recovery_engine.authorization import Decision, authorize
from modules.recovery_engine.manager import InvalidTransition
from simulation.scenarios.catalog import CATALOG, build_scenario
from twinx_api.db import AuditEntry
from twinx_api.runtime import Runtime

REPORTS = Path("research/reports")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = getattr(app.state, "runtime", None) or Runtime()
    app.state.runtime = runtime
    runtime.start()
    yield
    runtime.stop()


app = FastAPI(title="Industrial Twin-X API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


class CommandRequest(BaseModel):
    device_id: str
    command: str
    value: float | None = None
    approved_by: str | None = Field(default=None, max_length=64)


class OperatorAction(BaseModel):
    operator: str = Field(min_length=1, max_length=64)


class ScenarioRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ControlRequest(BaseModel):
    action: str
    value: float | None = None


@app.get("/health")
def health(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    return {
        "status": "ok",
        "mqtt_connected": runtime.mqtt_connected,
        "database_connected": runtime.database_ok(),
        "model_version": runtime.ai_version,
    }


@app.get("/api/v1/overview")
def overview(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    return runtime.overview()


@app.get("/api/v1/factory")
def factory(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    spec = runtime.spec
    return {
        "factory_id": spec.factory_id,
        "zones": [z.__dict__ for z in spec.zones],
        "gateways": [g.__dict__ for g in spec.gateways],
        "machines": [runtime.machine_view(m.machine_id) for m in spec.machines],
    }


@app.get("/api/v1/devices")
def devices(
    machine_id: str | None = None, runtime: Runtime = Depends(get_runtime)
) -> list[dict[str, Any]]:
    return runtime.pipeline.twin.snapshot(machine_id)


@app.get("/api/v1/devices/{device_id}")
def device(device_id: str, runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    twin = runtime.pipeline.twin.twins.get(device_id)
    if twin is None:
        raise HTTPException(404, "unknown device")
    return {**twin.to_dict(), "delta": runtime.pipeline.twin.delta(device_id)}


@app.get("/api/v1/telemetry/{machine_id}")
def telemetry(
    machine_id: str,
    limit: int = Query(default=240, ge=1, le=720),
    runtime: Runtime = Depends(get_runtime),
) -> dict[str, list[dict[str, float]]]:
    if machine_id not in {m.machine_id for m in runtime.spec.machines}:
        raise HTTPException(404, "unknown machine")
    series = runtime.history.get(machine_id, {})
    return {
        signal: [{"t": t, "v": v} for t, v in list(points)[-limit:]]
        for signal, points in list(series.items())
    }


@app.get("/api/v1/ai")
def ai(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    path = REPORTS / "ai-evaluation" / "metrics.json"
    return {
        "model_version": runtime.ai_version,
        "mode": "trained models" if runtime.ai_version else "rule-based fallback",
        "assessments": [a.to_dict() for a in list(runtime.pipeline.assessments.values())],
        "evaluation": json.loads(path.read_text()) if path.exists() else None,
    }


@app.get("/api/v1/network")
def network(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    twins = runtime.pipeline.twin.snapshot()
    return {
        **runtime.pipeline.network,
        "gaps": sum(t["gaps"] for t in twins),
        "duplicates": sum(t["duplicates"] for t in twins),
        "out_of_order": sum(t["out_of_order"] for t in twins),
        "rate_per_s": runtime.message_rate(),
    }


@app.get("/api/v1/security")
def security(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    return {
        "findings": list(runtime.findings),
        "quarantined": sorted(runtime.pipeline.integrity.quarantined),
        "isolated_devices": [
            t["device_id"] for t in runtime.pipeline.twin.snapshot() if t["isolated"]
        ],
        "invalid_messages": runtime.pipeline.invalid_messages,
        "commands": list(runtime.commands),
    }


@app.get("/api/v1/recovery/incidents")
def incidents(runtime: Runtime = Depends(get_runtime)) -> list[dict[str, Any]]:
    with runtime.pipeline.lock:
        items = [i.to_dict() for i in runtime.pipeline.manager.incidents.values()]
    return sorted(items, key=lambda i: i["opened_at"], reverse=True)


@app.get("/api/v1/recovery/audit")
def audit(
    limit: int = Query(default=100, ge=1, le=500), runtime: Runtime = Depends(get_runtime)
) -> list[dict[str, Any]]:
    if runtime.engine is None:
        return []
    statement = select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit)
    with runtime.engine.connect() as connection:
        return [
            {
                "id": r.id,
                "incident_id": r.incident_id,
                "machine_id": r.machine_id,
                "sim_time": r.sim_time,
                "event": r.event,
                "actor": r.actor,
                "detail": r.detail,
                "state": r.state,
            }
            for r in connection.execute(statement)
        ]


def _incident_action(runtime: Runtime, incident_id: str, method: str, operator: str) -> dict:
    manager = runtime.pipeline.manager
    if incident_id not in manager.incidents:
        raise HTTPException(404, "unknown incident")
    with runtime.pipeline.lock:
        try:
            incident = getattr(manager, method)(incident_id, operator, runtime.pipeline.sim_time)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc)) from exc
        return incident.to_dict()


@app.post("/api/v1/recovery/incidents/{incident_id}/approve")
def approve(
    incident_id: str, body: OperatorAction, runtime: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    return _incident_action(runtime, incident_id, "approve", body.operator)


@app.post("/api/v1/recovery/incidents/{incident_id}/reject")
def reject(
    incident_id: str, body: OperatorAction, runtime: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    return _incident_action(runtime, incident_id, "reject", body.operator)


@app.post("/api/v1/recovery/incidents/{incident_id}/repair")
def repair(
    incident_id: str, body: OperatorAction, runtime: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    return _incident_action(runtime, incident_id, "request_repair", body.operator)


@app.post("/api/v1/commands")
def command(body: CommandRequest, runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    if body.device_id not in runtime.pipeline.twin.twins:
        raise HTTPException(404, "unknown device")
    # An operator request carries no model confidence, so low-impact commands need a name too.
    verdict = authorize(body.command, body.value, approved_by=body.approved_by)
    if verdict.decision is Decision.DENY:
        raise HTTPException(422, verdict.reason)
    if verdict.decision is Decision.NEEDS_APPROVAL:
        raise HTTPException(403, f"approval required: {verdict.reason}")
    message = runtime.pipeline.send_device_command(
        body.device_id, body.command, body.value, body.approved_by or "operator"
    )
    return {"command_id": message.command_id, "impact": verdict.impact, "reason": verdict.reason}


@app.get("/api/v1/scenarios")
def scenarios() -> list[dict[str, str]]:
    return [
        {"scenario_id": k, "description": build_scenario(k).description} for k in sorted(CATALOG)
    ]


@app.post("/api/v1/scenarios/{scenario_id}/start")
def start_scenario(
    scenario_id: str, body: ScenarioRequest, runtime: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    if scenario_id not in CATALOG:
        raise HTTPException(404, "unknown scenario")
    sent = runtime.control(
        {"action": "scenario", "scenario_id": scenario_id, "params": body.params}
    )
    if not sent:
        raise HTTPException(503, "broker unavailable")
    return {"started": scenario_id}


@app.post("/api/v1/simulation/control")
def simulation_control(
    body: ControlRequest, runtime: Runtime = Depends(get_runtime)
) -> dict[str, Any]:
    if body.action not in ("pause", "resume", "speed", "reset"):
        raise HTTPException(422, "unknown action")
    if not runtime.control(body.model_dump()):
        raise HTTPException(503, "broker unavailable")
    return {"action": body.action}


def _read_reports() -> list[dict[str, Any]]:
    if not REPORTS.exists():
        return []
    return [
        {
            "path": str(p.relative_to(REPORTS)).replace("\\", "/"),
            "size": p.stat().st_size,
        }
        for p in sorted(REPORTS.rglob("*"))
        if p.is_file() and p.suffix in (".json", ".png", ".csv", ".md")
    ]


@app.get("/api/v1/reports")
def reports() -> list[dict[str, Any]]:
    return _read_reports()


@app.get("/api/v1/experiments")
def experiments() -> dict[str, Any]:
    path = REPORTS / "experiments" / "summary.json"
    return json.loads(path.read_text()) if path.exists() else {"available": False}


@app.websocket("/ws/live")
async def live(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime: Runtime = websocket.app.state.runtime
    try:
        while True:
            snapshot = await asyncio.to_thread(runtime.overview)
            await websocket.send_json(snapshot)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
