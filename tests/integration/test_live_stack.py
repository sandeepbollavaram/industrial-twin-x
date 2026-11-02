"""End-to-end through real Mosquitto and PostgreSQL. Needs: docker compose up -d"""

import json
import socket
import threading
import time

import paho.mqtt.client as mqtt
import pytest
from sqlalchemy import create_engine, text
from twinx_api.runtime import Runtime
from twinx_api.settings import Settings

from simulation.run import LiveRunner

pytestmark = pytest.mark.integration


def service_up(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def settings():
    config = Settings()
    if not (
        service_up(config.mqtt_host, config.mqtt_port)
        and service_up(config.postgres_host, config.postgres_port)
    ):
        pytest.skip("Docker Compose services are not running")
    return config


def wait_for(predicate, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def stack(settings):
    runtime = Runtime(settings)
    runtime.start()
    assert wait_for(lambda: runtime.mqtt_connected, 15)
    runner = LiveRunner(99, 20.0, settings.mqtt_host, settings.mqtt_port, 1)
    thread = threading.Thread(target=runner.run, args=(45.0,), daemon=True)
    thread.start()
    yield runtime, runner
    thread.join(timeout=60)
    runtime.stop()


def test_all_devices_report_through_broker(stack):
    runtime, _ = stack
    assert wait_for(lambda: runtime.overview()["counts"]["devices_reporting"] == 100, 30), (
        runtime.overview()["counts"]
    )
    assert runtime.pipeline.invalid_messages == 0


def test_telemetry_is_persisted(stack, settings):
    runtime, _ = stack
    assert wait_for(lambda: runtime.writer.written > 100, 30)
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        rows = connection.execute(text("select count(*) from telemetry")).scalar_one()
        devices = connection.execute(text("select count(*) from devices")).scalar_one()
    assert rows > 100
    assert devices == 100


def test_command_round_trip_changes_simulated_machine(stack):
    runtime, runner = stack
    runtime.pipeline.send_device_command("CNV-A03-controller", "set_speed", 0.7, "test")
    assert wait_for(lambda: runner.sim.machines["CNV-A03"].speed_cmd == pytest.approx(0.7), 10)
    assert wait_for(lambda: runtime.pipeline.twin.machine_signal("CNV-A03", "rpm") < 0.8 * 960, 20)


def test_malformed_broker_message_is_counted(stack, settings):
    runtime, _ = stack
    before = runtime.pipeline.invalid_messages
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twinx-test")
    client.connect(settings.mqtt_host, settings.mqtt_port)
    client.loop_start()
    topic = "industrial-twin-x/factory/plant-01/zone/A/device/ghost/telemetry"
    client.publish(topic, json.dumps({"device_id": "ghost"}), qos=1).wait_for_publish(5)
    client.publish(topic, "not json", qos=1).wait_for_publish(5)
    assert wait_for(lambda: runtime.pipeline.invalid_messages >= before + 2, 10)
    client.loop_stop()
    client.disconnect()
