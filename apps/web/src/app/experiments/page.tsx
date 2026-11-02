"use client";

import { Empty, PageHeader, Panel } from "@/components/ui";
import { formatNumber, usePoll } from "@/lib/api";

type Metric = { n: number; mean: number | null; std: number | null };
type Entry = {
  group: string;
  runs: number;
  failures: number;
  delivery_ratio: Metric;
  detection_time_s: Metric;
  recovery_time_s: Metric;
  machine_downtime_s: Metric;
};
type Summary = { available: boolean; seeds?: number[]; duration_s?: number; model_version?: string; summary?: Record<string, Entry> };

const cell = (metric: Metric, digits = 0) =>
  metric.n ? `${formatNumber(metric.mean, digits)} ± ${formatNumber(metric.std, digits)}` : "n/a";

export default function ExperimentsPage() {
  const { data } = usePoll<Summary>("/api/v1/experiments", 0);
  return (
    <>
      <PageHeader
        title="Experiments"
        description="Results of the repeated experiment runner, read from its output. Values are mean ± SD across seeds, measured in simulation only."
      />
      <Panel title={data?.seeds ? `${data.seeds.length} seeds, ${data.duration_s} simulated seconds per run` : "Results"} flush>
        {data?.summary ? (
          <table className="data">
            <thead><tr><th>Condition</th><th>Group</th><th className="text-right">Machine failures</th><th className="text-right">Downtime s</th><th className="text-right">Detection s</th><th className="text-right">Recovery s</th><th className="text-right">Delivery ratio</th></tr></thead>
            <tbody>
              {Object.entries(data.summary).map(([name, entry]) => (
                <tr key={name}>
                  <td className="font-medium">{name.replace(/_/g, " ")}</td>
                  <td>{entry.group}</td>
                  <td className="num text-right">{entry.failures} / {entry.runs}</td>
                  <td className="num text-right">{cell(entry.machine_downtime_s)}</td>
                  <td className="num text-right">{cell(entry.detection_time_s)}</td>
                  <td className="num text-right">{cell(entry.recovery_time_s)}</td>
                  <td className="num text-right">{cell(entry.delivery_ratio, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>No results yet. Run: python -m research.experiments.run_experiments</Empty>
        )}
      </Panel>
    </>
  );
}
