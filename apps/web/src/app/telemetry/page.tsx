"use client";

import { useState } from "react";
import { SignalChart } from "@/components/SignalChart";
import { Empty, ErrorNote, PageHeader, Panel } from "@/components/ui";
import { usePoll } from "@/lib/api";
import { useLive } from "@/lib/live";

export default function TelemetryPage() {
  const { overview } = useLive();
  const [machineId, setMachineId] = useState("MTR-A01");
  const { data, error } = usePoll<Record<string, { t: number; v: number }[]>>(
    `/api/v1/telemetry/${machineId}?limit=720`,
    2000,
  );
  const signals = data ? Object.keys(data).sort() : [];
  return (
    <>
      <PageHeader
        title="Telemetry"
        description="Live simulated sensor readings, shown as the median across redundant sensors. Each signal has its own scale."
      />
      <ErrorNote message={error} />
      <div className="mb-3 flex items-center gap-2">
        <label htmlFor="machine">Machine</label>
        <select id="machine" className="input" value={machineId} onChange={(e) => setMachineId(e.target.value)}>
          {(overview?.machines ?? []).map((m) => (
            <option key={m.machine_id} value={m.machine_id}>{m.machine_id}: {m.name}</option>
          ))}
        </select>
      </div>
      {signals.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {signals.map((signal) => (
            <Panel key={signal}>
              <SignalChart signal={signal} points={data![signal]} />
            </Panel>
          ))}
        </div>
      ) : (
        <Panel><Empty>No telemetry yet. Start the simulator to see readings.</Empty></Panel>
      )}
    </>
  );
}
