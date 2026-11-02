"""Virtual gateway uplink with outage, latency, loss and bounded store-and-forward."""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class GatewayStats:
    submitted: int = 0
    delivered: int = 0
    lost_network: int = 0
    lost_outage: int = 0
    lost_overflow: int = 0
    replayed: int = 0


@dataclass
class VirtualGateway:
    gateway_id: str
    rng: np.random.Generator
    buffer_limit: int = 20000
    flush_per_s: int = 60
    base_latency_s: float = 0.02
    jitter_s: float = 0.01
    extra_latency_s: float = 0.0
    loss_prob: float = 0.0
    process_up: bool = True
    link_up: bool = True
    stats: GatewayStats = field(default_factory=GatewayStats)
    _buffer: deque[Any] = field(default_factory=deque)
    _inflight: list[tuple[float, int, Any]] = field(default_factory=list)
    _counter: int = 0

    @property
    def backlog(self) -> int:
        return len(self._buffer)

    @property
    def state(self) -> str:
        if not self.process_up:
            return "down"
        return "online" if self.link_up else "isolated"

    def submit(self, envelope: Any, now: float) -> None:
        self.stats.submitted += 1
        if not self.process_up:
            self.stats.lost_outage += 1
            return
        if not self.link_up or self._buffer:
            if len(self._buffer) >= self.buffer_limit:
                self._buffer.popleft()
                self.stats.lost_overflow += 1
            self._buffer.append(envelope)
            return
        self._transmit(envelope, now)

    def _transmit(self, envelope: Any, now: float) -> None:
        if self.loss_prob > 0.0 and self.rng.random() < self.loss_prob:
            self.stats.lost_network += 1
            return
        delay = self.base_latency_s + self.extra_latency_s + self.rng.exponential(self.jitter_s)
        self._counter += 1
        heapq.heappush(self._inflight, (now + delay, self._counter, envelope))

    def tick(self, now: float, dt: float = 1.0) -> list[tuple[float, Any]]:
        """Flush the backlog at a bounded rate and return messages now due."""
        if self.process_up and self.link_up:
            for _ in range(min(int(self.flush_per_s * dt), len(self._buffer))):
                envelope = self._buffer.popleft()
                envelope.replayed = True
                self.stats.replayed += 1
                self._transmit(envelope, now)
        due: list[tuple[float, Any]] = []
        while self._inflight and self._inflight[0][0] <= now:
            arrival, _, envelope = heapq.heappop(self._inflight)
            due.append((arrival, envelope))
        self.stats.delivered += len(due)
        return due
