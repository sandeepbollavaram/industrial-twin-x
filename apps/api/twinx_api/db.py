"""Relational schema. Migrations live in infrastructure/database/alembic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    machine_id: Mapped[str] = mapped_column(String(32), index=True)
    zone_id: Mapped[str] = mapped_column(String(8))
    gateway_id: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(32))
    sensors: Mapped[list] = mapped_column(JSONB)


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (Index("ix_telemetry_machine_time", "machine_id", "sim_time"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(String(32))
    sim_time: Mapped[float] = mapped_column(Float)
    source_timestamp: Mapped[float] = mapped_column(Float)
    sequence: Mapped[int] = mapped_column(BigInteger)
    scenario_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    readings: Mapped[dict] = mapped_column(JSONB)
    replayed: Mapped[bool] = mapped_column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    sim_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEntry(Base):
    """Recovery audit log. Application code only ever inserts into this table."""

    __tablename__ = "recovery_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(32), index=True)
    machine_id: Mapped[str] = mapped_column(String(32))
    fault: Mapped[str] = mapped_column(String(32))
    sim_time: Mapped[float] = mapped_column(Float)
    event: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TwinState(Base):
    __tablename__ = "twin_state"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reported: Mapped[dict] = mapped_column(JSONB)
    desired: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    last_sequence: Mapped[int] = mapped_column(BigInteger)
    received: Mapped[int] = mapped_column(Integer)
    gaps: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
