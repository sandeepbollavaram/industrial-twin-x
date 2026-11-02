"use client";

import { Empty, PageHeader, Panel, Stat } from "@/components/ui";
import { formatSimTime, usePoll } from "@/lib/api";

type Finding = { sensor_id: string; kind: string; sim_time: number; detail: string };
type Command = { command_id: string; device_id: string; command: string; value: number | null; issued_by: string };
type Security = {
  findings: Finding[];
  quarantined: string[];
  isolated_devices: string[];
  invalid_messages: number;
  commands: Command[];
};

export default function SecurityPage() {
  const { data } = usePoll<Security>("/api/v1/security", 2000);
  return (
    <>
      <PageHeader
        title="Cybersecurity"
        description="Contained simulation of sensor manipulation. Redundant sensors are cross-checked, and suspect sensors are excluded from analytics and edge decisions."
      />
      <div className="mb-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat label="Integrity findings" value={data?.findings.length ?? "n/a"} />
        <Stat label="Quarantined sensors" value={data?.quarantined.length ?? "n/a"} />
        <Stat label="Isolated devices" value={data?.isolated_devices.length ?? "n/a"} />
        <Stat label="Rejected messages" value={data?.invalid_messages ?? "n/a"} note="Failed schema validation" />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Integrity findings" flush>
          {data?.findings.length ? (
            <table className="data">
              <thead><tr><th>Sim time</th><th>Sensor</th><th>Type</th><th>Evidence</th></tr></thead>
              <tbody>
                {data.findings.map((f) => (
                  <tr key={f.sensor_id + f.sim_time}>
                    <td className="num">{formatSimTime(f.sim_time)}</td>
                    <td className="font-medium">{f.sensor_id}</td>
                    <td>{f.kind.replace(/_/g, " ")}</td>
                    <td className="text-[12px]">{f.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty>No findings. Inject sensor manipulation from the Overview page to test this.</Empty>
          )}
        </Panel>
        <Panel title="Actuator command log" flush>
          {data?.commands.length ? (
            <table className="data">
              <thead><tr><th>Device</th><th>Command</th><th>Issued by</th></tr></thead>
              <tbody>
                {data.commands.map((c) => (
                  <tr key={c.command_id + c.command}>
                    <td className="font-medium">{c.device_id}</td>
                    <td>{c.command}{c.value !== null ? ` ${c.value}` : ""}</td>
                    <td>{c.issued_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty>No commands have been issued.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}
