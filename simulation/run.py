"""Live simulator process: paces the shared engine and bridges it to MQTT.

Usage: python -m simulation.run --seed 42 --speed 10
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import time
from typing import Any

import paho.mqtt.client as mqtt

from modules.telemetry import topics
from simulation.engine.core import Envelope, FactorySimulation
from simulation.factory.layout import build_factory
from simulation.scenarios.catalog import build_scenario

log = logging.getLogger("twinx.simulation")
STEP_WALL_S = 0.1
MAX_SPEED = 100.0


class LiveRunner:
    def __init__(self, seed: int, speed: float, host: str, port: int, scale: int) -> None:
        self.seed = seed
        self.speed = speed
        self.host = host
        self.port = port
        self.paused = False
        self.inbox: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue(maxsize=1000)
        self.publish_failures = 0
        self.spec = build_factory(scale)
        self.factory = self.spec.factory_id
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=f"twinx-sim-{os.getpid()}"
        )
        self.client.max_queued_messages_set(20000)
        self.client.reconnect_delay_set(min_delay=1, max_delay=15)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.sim = self._new_sim()

    def _new_sim(self) -> FactorySimulation:
        return FactorySimulation(
            seed=self.seed, sink=self._publish, spec=self.spec, wall_clock=True
        )

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        log.info("connected to broker: %s", reason_code)
        client.subscribe(topics.commands(self.factory, "+"), qos=1)
        client.subscribe(topics.control(self.factory), qos=1)

    def _on_message(self, client, userdata, message) -> None:
        try:
            payload = json.loads(message.payload)
        except ValueError:
            log.warning("discarded malformed message on %s", message.topic)
            return
        kind = "control" if message.topic.endswith("/control") else "command"
        try:
            self.inbox.put_nowait((kind, payload))
        except queue.Full:
            log.warning("inbox full; dropped %s", kind)

    def _publish(self, envelope: Envelope, _: float) -> None:
        qos = 0 if envelope.kind in ("telemetry", "network") else 1
        result = self.client.publish(envelope.topic, json.dumps(envelope.payload), qos=qos)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.publish_failures += 1

    def _handle_inbox(self) -> None:
        while True:
            try:
                kind, payload = self.inbox.get_nowait()
            except queue.Empty:
                return
            try:
                if kind == "command":
                    # Commands run between engine steps, so state changes stay atomic.
                    self.sim.submit_command(
                        payload["device_id"],
                        payload["command"],
                        payload.get("value"),
                        payload.get("command_id", ""),
                    )
                else:
                    self._control(payload)
            except (KeyError, ValueError, TypeError, StopIteration) as exc:
                log.warning("rejected %s: %r", kind, exc)

    def _control(self, payload: dict[str, Any]) -> None:
        action = payload["action"]
        if action == "pause":
            self.paused = True
        elif action == "resume":
            self.paused = False
        elif action == "speed":
            self.speed = min(max(float(payload["value"]), 0.1), MAX_SPEED)
        elif action == "reset":
            self.sim = self._new_sim()
        elif action == "scenario":
            scenario = build_scenario(payload["scenario_id"], at_s=0, **payload.get("params", {}))
            self.sim.schedule(scenario, relative=True)
        else:
            raise ValueError(f"unknown action {action}")
        log.info("control: %s", payload)

    def run(self, duration_wall_s: float | None = None) -> None:
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()
        started = time.monotonic()
        next_step = started
        try:
            while duration_wall_s is None or time.monotonic() - started < duration_wall_s:
                self._handle_inbox()
                if not self.paused:
                    self.sim.run(self.sim.env.now + self.speed * STEP_WALL_S)
                next_step += STEP_WALL_S
                delay = next_step - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    # Fell behind: do not try to catch up in a burst.
                    next_step = time.monotonic()
        finally:
            self.client.loop_stop()
            self.client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=int(os.getenv("SIM_SEED", "42")))
    parser.add_argument("--speed", type=float, default=float(os.getenv("SIM_SPEED", "10")))
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--duration", type=float, default=None, help="Wall seconds, then exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    LiveRunner(args.seed, args.speed, args.host, args.port, args.scale).run(args.duration)


if __name__ == "__main__":
    main()
