"use client";

import { MachineTable } from "@/components/MachineTable";
import { SimulationControls } from "@/components/SimulationControls";
import { Empty, PageHeader, Panel, severityOfAlert, Stat, Status } from "@/components/ui";
import { formatNumber, formatSimTime } from "@/lib/api";
import { useLive } from "@/lib/live";

export default function OverviewPage() {
  const { overview } = useLive();
  const counts = overview?.counts;
  return (
    <>
      <PageHeader
        title="Overview"
        description="Current state of the virtual factory. All machines, sensors and faults are simulated."
      />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Machines" value={counts?.machines ?? "n/a"} note={`${counts?.zones ?? "n/a"} zones`} />
        <Stat
          label="Devices reporting"
          value={counts ? `${counts.devices_reporting} / ${counts.devices}` : "n/a"}
          note={`${counts?.sensors ?? "n/a"} sensors`}
        />
        <Stat label="Open incidents" value={counts?.open_incidents ?? "n/a"} />
        <Stat label="Messages per second" value={formatNumber(overview?.pipeline.rate_per_s)} />
        <Stat
          label="Pipeline latency p95"
          value={`${formatNumber(overview?.pipeline.latency_ms_p95, 0)} ms`}
          note="Source to central, wall clock"
        />
        <Stat
          label="DB batch write"
          value={`${formatNumber(overview?.infrastructure.write_latency_ms, 0)} ms`}
          note={`${overview?.infrastructure.rows_dropped ?? 0} rows dropped`}
        />
      </div>
      <div className="mb-4">
        <Panel title="Simulation controls"><SimulationControls /></Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <Panel title="Machines" flush>
          {overview ? <MachineTable machines={overview.machines} /> : <Empty>Waiting for the API.</Empty>}
        </Panel>
        <Panel title="Recent alerts" flush>
          {overview?.alerts.length ? (
            <ul>
              {overview.alerts.slice(0, 12).map((alert, index) => (
                <li key={index} className="border-b px-3 py-2 text-[13px]" style={{ borderColor: "var(--line)" }}>
                  <div className="flex items-center justify-between gap-2">
                    <Status severity={severityOfAlert(alert.severity)} label={alert.code.replace(/_/g, " ")} />
                    <span className="num text-[12px]" style={{ color: "var(--ink-3)" }}>
                      {formatSimTime(alert.sim_time)}
                    </span>
                  </div>
                  <div className="mt-1 break-words text-[12px]" style={{ color: "var(--ink-2)" }}>
                    {alert.message}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No alerts in this run.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}
