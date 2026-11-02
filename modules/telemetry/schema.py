"""Versioned message schemas. NaN and infinity are rejected at the boundary."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Finite = Annotated[float, Field(allow_inf_nan=False)]


class TelemetryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    factory_id: str
    zone_id: str
    machine_id: str
    gateway_id: str
    device_id: str
    timestamp: float = Field(gt=0, allow_inf_nan=False, description="Unix seconds at source")
    sim_time: float = Field(ge=0, allow_inf_nan=False)
    sequence: int = Field(ge=0)
    scenario_id: str
    status: str
    readings: dict[str, Finite] = Field(min_length=1)
    replayed: bool = False


class StatusMessage(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    device_id: str
    machine_id: str
    sim_time: float
    status: str
    detail: str = ""
    command_id: str | None = None
    accepted: bool | None = None


class AlertMessage(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    source: str
    machine_id: str | None = None
    sim_time: float
    severity: Literal["info", "warning", "critical"]
    code: str
    message: str


class CommandMessage(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    command_id: str
    device_id: str
    command: str
    value: Finite | None = None
    issued_by: str
