"use client";

import { PageHeader, Panel, Status } from "@/components/ui";
import { API_URL, formatNumber, usePoll } from "@/lib/api";

type Health = { status: string; mqtt_connected: boolean; database_connected: boolean; model_version: string | null };
type Factory = { factory_id: string; zones: { zone_id: string; name: string }[]; gateways: { gateway_id: string; zone_id: string }[] };
type Row = [string, React.ReactNode];

function Rows({ rows }: { rows: Row[] }) {
  return (
    <dl className="text-[13px]">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-4 border-b py-1.5 last:border-0" style={{ borderColor: "var(--line)" }}>
          <dt style={{ color: "var(--ink-2)" }}>{label}</dt>
          <dd className="text-right">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function SettingsPage() {
  const { data: health, error } = usePoll<Health>("/health", 3000);
  const { data: factory } = usePoll<Factory>("/api/v1/factory", 0);
  const flag = (ok: boolean | undefined, name: string) => (
    <Status severity={ok ? "good" : "critical"} label={ok ? `${name} connected` : `${name} offline`} />
  );
  return (
    <>
      <PageHeader title="System Settings" description="Read-only runtime configuration. Change values in .env and restart the services." />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Services">
          <Rows rows={[
            ["API", <Status key="a" severity={error ? "critical" : "good"} label={error ? "Offline" : `${API_URL}`} />],
            ["MQTT broker", flag(health?.mqtt_connected, "Broker")],
            ["PostgreSQL", flag(health?.database_connected, "Database")],
            ["Model version", health?.model_version ?? "Rule-based fallback"],
          ]} />
        </Panel>
        <Panel title="Factory">
          <Rows rows={[
            ["Factory ID", factory?.factory_id ?? "n/a"],
            ["Zones", factory ? factory.zones.map((z) => `${z.zone_id}: ${z.name}`).join(", ") : "n/a"],
            ["Gateways", factory?.gateways.map((g) => g.gateway_id).join(", ") ?? "n/a"],
            ["Telemetry period", `${formatNumber(5, 0)} simulated seconds per device`],
          ]} />
        </Panel>
      </div>
    </>
  );
}
