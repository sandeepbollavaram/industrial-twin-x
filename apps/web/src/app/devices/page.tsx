"use client";

import { useState } from "react";
import { Empty, ErrorNote, PageHeader, Panel, Status } from "@/components/ui";
import { formatNumber, SIGNAL_LABELS, usePoll } from "@/lib/api";
import { useLive } from "@/lib/live";

type Twin = {
  device_id: string;
  role: string;
  gateway_id: string;
  status: string;
  reported: Record<string, number>;
  desired: Record<string, unknown>;
  last_sequence: number;
  received: number;
  gaps: number;
  isolated: boolean;
};

export default function DevicesPage() {
  const { overview } = useLive();
  const [machineId, setMachineId] = useState("MTR-A01");
  const { data, error } = usePoll<Twin[]>(`/api/v1/devices?machine_id=${machineId}`);
  return (
    <>
      <PageHeader
        title="Device Explorer"
        description="Digital twin state of each virtual device: reported readings, desired state, and message accounting."
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
      <Panel title="Devices" flush>
        {data ? (
          <table className="data">
            <thead>
              <tr><th>Device</th><th>Role</th><th>Status</th><th>Reported</th><th>Desired</th><th className="text-right">Seq</th><th className="text-right">Received</th><th className="text-right">Gaps</th></tr>
            </thead>
            <tbody>
              {data.map((twin) => (
                <tr key={twin.device_id}>
                  <td className="font-medium">{twin.device_id}</td>
                  <td>{twin.role}</td>
                  <td>
                    <Status
                      severity={twin.isolated ? "warning" : twin.status === "running" ? "good" : twin.status === "failed" ? "critical" : "idle"}
                      label={twin.isolated ? "isolated" : twin.status}
                    />
                  </td>
                  <td className="text-[12px]">
                    {Object.entries(twin.reported).map(([signal, value]) => (
                      <div key={signal}>
                        <span style={{ color: "var(--ink-3)" }}>{SIGNAL_LABELS[signal] ?? signal}: </span>
                        <span className="num">{formatNumber(value, 2)}</span>
                      </div>
                    ))}
                  </td>
                  <td className="text-[12px]">{Object.keys(twin.desired).length ? JSON.stringify(twin.desired) : "None"}</td>
                  <td className="num text-right">{twin.last_sequence}</td>
                  <td className="num text-right">{twin.received}</td>
                  <td className="num text-right">{twin.gaps}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>Loading devices.</Empty>
        )}
      </Panel>
    </>
  );
}
