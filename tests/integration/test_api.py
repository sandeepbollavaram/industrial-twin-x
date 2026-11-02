"""API tests run against the app with no broker or database."""

import pytest
from fastapi.testclient import TestClient
from twinx_api.main import app
from twinx_api.runtime import Runtime
from twinx_api.settings import Settings

from modules.recovery_engine.manager import State


@pytest.fixture
def client(tmp_path):
    settings = Settings(model_path=str(tmp_path / "absent.joblib"))
    app.state.runtime = Runtime(settings, connect=False)
    with TestClient(app) as test_client:
        yield test_client
    app.state.runtime = None


def test_health_reports_fallback_mode(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_version"] is None


def test_overview_shape(client):
    body = client.get("/api/v1/overview").json()
    assert body["simulated"] is True
    assert body["counts"]["devices"] == 100
    assert body["counts"]["sensors"] == 300
    assert len(body["machines"]) == 10


def test_unknown_resources_return_404(client):
    assert client.get("/api/v1/devices/ghost").status_code == 404
    assert client.get("/api/v1/telemetry/ghost").status_code == 404
    assert client.post("/api/v1/scenarios/ghost/start", json={}).status_code == 404


def test_scenarios_listed(client):
    ids = {s["scenario_id"] for s in client.get("/api/v1/scenarios").json()}
    assert {"bearing_degradation", "pump_leakage", "sensor_manipulation"} <= ids


def test_unapproved_high_impact_command_is_forbidden(client):
    response = client.post(
        "/api/v1/commands", json={"device_id": "MTR-A01-controller", "command": "stop"}
    )
    assert response.status_code == 403


def test_unattributed_low_impact_command_is_forbidden(client):
    response = client.post(
        "/api/v1/commands",
        json={"device_id": "MTR-A01-controller", "command": "set_speed", "value": 0.8},
    )
    assert response.status_code == 403


def test_out_of_limit_command_is_rejected_even_when_approved(client):
    response = client.post(
        "/api/v1/commands",
        json={
            "device_id": "MTR-A01-controller",
            "command": "set_speed",
            "value": 9.0,
            "approved_by": "alice",
        },
    )
    assert response.status_code == 422


def test_approved_command_updates_desired_state(client):
    response = client.post(
        "/api/v1/commands",
        json={
            "device_id": "MTR-A01-controller",
            "command": "set_speed",
            "value": 0.8,
            "approved_by": "alice",
        },
    )
    assert response.status_code == 200
    twin = client.get("/api/v1/devices/MTR-A01-controller").json()
    assert twin["desired"]["speed_fraction"] == 0.8


def test_incident_approval_flow(client):
    manager = app.state.runtime.pipeline.manager
    incident = manager.report_fault("PMP-B01", "pump_leak", 0.99, 10.0)
    assert incident.state is State.AWAITING_APPROVAL
    url = f"/api/v1/recovery/incidents/{incident.incident_id}"
    assert client.post(f"{url}/approve", json={"operator": ""}).status_code == 422
    assert client.post(f"{url}/approve", json={"operator": "alice"}).status_code == 200
    assert incident.state is State.MITIGATING
    assert client.post(f"{url}/approve", json={"operator": "alice"}).status_code == 409
    listed = client.get("/api/v1/recovery/incidents").json()
    assert listed[0]["state"] == "mitigating"


def test_scenario_start_reports_missing_broker(client):
    assert client.post("/api/v1/scenarios/normal/start", json={}).status_code == 503


def test_websocket_pushes_snapshot(client):
    with client.websocket_connect("/ws/live") as socket:
        assert socket.receive_json()["counts"]["machines"] == 10
