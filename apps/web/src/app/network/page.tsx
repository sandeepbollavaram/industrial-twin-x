"use client";

import { Empty, PageHeader, Panel, Stat, Status } from "@/components/ui";
import { formatNumber, Severity, usePoll } from "@/lib/api";

type Gateway = {
  gateway_id: string;
  state: string;
  backlog: number;
  submitted: number;
  delivered: number;
  lost_network: number;
  lost_outage: number;
  lost_overflow: number;
  replayed: number;
  extra_latency_s: number;
  loss_prob: number;
};
type Network = { gateways: Gateway[]; gaps: number; duplicates: number; out_of_order: number; rate_per_s: number };
const STATE: Record<string, Severity> = { online: "good", isolated: "warning", down: "critical" };

export default function NetworkPage() {
  const { data } = usePoll<Network>("/api/v1/network", 2000);
  return (
    <>
      <PageHeader
        title="Network Monitoring"
        description="Simulated gateway uplinks and message accounting. Latency and loss here are injected by the simulator's network model."
      />
      <div className="mb-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat label="Messages per second" value={formatNumber(data?.rate_per_s)} />
        <Stat label="Sequence gaps" value={data?.gaps ?? "n/a"} />
        <Stat label="Out of order" value={data?.out_of_order ?? "n/a"} note="Includes backlog replay" />
        <Stat label="Duplicates" value={data?.duplicates ?? "n/a"} />
      </div>
      <Panel title="Gateways" flush>
        {data?.gateways.length ? (
          <table className="data">
            <thead><tr><th>Gateway</th><th>State</th><th className="text-right">Submitted</th><th className="text-right">Delivered</th><th className="text-right">Delivery ratio</th><th className="text-right">Lost</th><th className="text-right">Backlog</th><th className="text-right">Replayed</th><th className="text-right">Added latency s</th><th className="text-right">Loss</th></tr></thead>
            <tbody>
              {data.gateways.map((g) => (
                <tr key={g.gateway_id}>
                  <td className="font-medium">{g.gateway_id}</td>
                  <td><Status severity={STATE[g.state] ?? "idle"} label={g.state} /></td>
                  <td className="num text-right">{g.submitted}</td>
                  <td className="num text-right">{g.delivered}</td>
                  <td className="num text-right">{g.submitted ? formatNumber(g.delivered / g.submitted, 3) : "n/a"}</td>
                  <td className="num text-right">{g.lost_network + g.lost_outage + g.lost_overflow}</td>
                  <td className="num text-right">{g.backlog}</td>
                  <td className="num text-right">{g.replayed}</td>
                  <td className="num text-right">{formatNumber(g.extra_latency_s, 2)}</td>
                  <td className="num text-right">{formatNumber(g.loss_prob * 100, 0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>No gateway reports yet. Start the simulator.</Empty>
        )}
      </Panel>
    </>
  );
}
