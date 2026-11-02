"use client";

import { useCallback, useEffect, useState } from "react";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/live";

export type Assessment = {
  machine_id: string;
  sim_time: number;
  anomaly_score: number;
  is_anomaly: boolean;
  fault: string;
  confidence: number;
  degradation: number | null;
  failure_risk: number | null;
  recommendation: { level: string; action: string };
  source: string;
};

export type AuditEntry = {
  sim_time: number;
  event: string;
  actor: string;
  detail: string;
  state: string;
};

export type Incident = {
  incident_id: string;
  machine_id: string;
  fault: string;
  confidence: number;
  opened_at: number;
  source: string;
  state: string;
  command: string | null;
  value: number | null;
  mitigated_at: number | null;
  closed_at: number | null;
  audit: AuditEntry[];
};

export type Machine = {
  machine_id: string;
  name: string;
  kind: string;
  zone_id: string;
  gateway_id: string;
  position: [number, number];
  status: string;
  signals: Record<string, number>;
  assessment: Assessment | null;
  incident: Incident | null;
  quarantined: string[];
};

export type Alert = {
  source: string;
  machine_id: string | null;
  sim_time: number;
  severity: string;
  code: string;
  message: string;
};

export type Overview = {
  simulated: boolean;
  sim_time: number;
  scenario_id: string;
  counts: Record<string, number>;
  machines: Machine[];
  alerts: Alert[];
  pipeline: {
    accepted: number;
    invalid: number;
    rate_per_s: number;
    latency_ms_p50: number | null;
    latency_ms_p95: number | null;
  };
  infrastructure: {
    mqtt_connected: boolean;
    mqtt_reconnects: number;
    database_connected: boolean;
    rows_written: number;
    rows_dropped: number;
    write_latency_ms: number | null;
    model_version: string | null;
  };
};

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(API_URL + path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

export async function postJson<T>(path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(API_URL + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof detail.detail === "string" ? detail.detail : "Request failed");
  }
  return response.json();
}

export function usePoll<T>(path: string | null, intervalMs = 3000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!path) return;
    try {
      setData(await getJson<T>(path));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  }, [path]);

  useEffect(() => {
    const first = setTimeout(refresh, 0);
    if (intervalMs <= 0) return () => clearTimeout(first);
    const timer = setInterval(refresh, intervalMs);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh, intervalMs]);

  return { data, error, refresh };
}

export function formatSimTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export function formatNumber(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "n/a" : value.toFixed(digits);
}

export const SIGNAL_LABELS: Record<string, string> = {
  rpm: "Speed (rpm)",
  current_a: "Current (A)",
  power_kw: "Power (kW)",
  winding_temp_c: "Winding temperature (°C)",
  bearing_temp_c: "Bearing temperature (°C)",
  vibration_mm_s: "Vibration (mm/s)",
  health_pct: "Device health (%)",
  flow_m3h: "Delivered flow (m³/h)",
  suction_flow_m3h: "Suction flow (m³/h)",
  pressure_bar: "Pressure (bar)",
  level_pct: "Tank level (%)",
  valve_pct: "Valve position (%)",
  fluid_temp_c: "Fluid temperature (°C)",
  voltage_v: "Voltage (V)",
  transformer_temp_c: "Transformer temperature (°C)",
  air_temp_c: "Air temperature (°C)",
  humidity_pct: "Humidity (%)",
};

export type Severity = "good" | "warning" | "critical" | "idle";

export function machineSeverity(machine: Machine): { severity: Severity; label: string } {
  if (machine.status === "failed") return { severity: "critical", label: "Failed" };
  if (machine.incident) {
    return { severity: "warning", label: machine.incident.state.replace(/_/g, " ") };
  }
  if (machine.quarantined.length) return { severity: "warning", label: "Sensor quarantined" };
  if (machine.status === "stopped") return { severity: "idle", label: "Stopped" };
  if (machine.status === "unknown") return { severity: "idle", label: "No data" };
  if (machine.assessment?.is_anomaly) return { severity: "warning", label: "Anomaly" };
  return { severity: "good", label: "Running" };
}
