"use client";

import { Empty, PageHeader, Panel, Status } from "@/components/ui";
import { formatNumber, Severity } from "@/lib/api";
import { useLive } from "@/lib/live";

const LEVEL: Record<string, Severity> = { high: "critical", medium: "warning", low: "good" };

export default function MaintenancePage() {
  const { overview } = useLive();
  const rows = (overview?.machines ?? [])
    .filter((m) => m.assessment)
    .sort((a, b) => (b.assessment!.failure_risk ?? 0) - (a.assessment!.failure_risk ?? 0));
  return (
    <>
      <PageHeader
        title="Predictive Maintenance"
        description="Risk score for failure within 15 simulated minutes and estimated degradation. The score ranks machines; it is not a validated remaining useful life and is only evaluated on simulated data."
      />
      <Panel title="Machines by risk" flush>
        {rows.length ? (
          <table className="data">
            <thead><tr><th>Machine</th><th>Priority</th><th className="text-right">Risk score</th><th className="text-right">Degradation estimate</th><th>Recommendation</th></tr></thead>
            <tbody>
              {rows.map((m) => {
                const a = m.assessment!;
                return (
                  <tr key={m.machine_id}>
                    <td><div className="font-medium">{m.machine_id}</div><div className="text-[12px]" style={{ color: "var(--ink-3)" }}>{m.name}</div></td>
                    <td><Status severity={LEVEL[a.recommendation.level] ?? "idle"} label={a.recommendation.level} /></td>
                    <td className="num text-right">{formatNumber(a.failure_risk, 2)}</td>
                    <td className="num text-right">{formatNumber(a.degradation, 2)}</td>
                    <td>{a.recommendation.action}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <Empty>No assessments yet. Start the simulator and wait for the first window.</Empty>
        )}
      </Panel>
    </>
  );
}
