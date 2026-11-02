"use client";

import { Empty, PageHeader, Panel } from "@/components/ui";
import { formatNumber, usePoll } from "@/lib/api";

export default function ReportsPage() {
  const { data } = usePoll<{ path: string; size: number }[]>("/api/v1/reports", 0);
  return (
    <>
      <PageHeader
        title="Reports"
        description="Files generated under research/reports by the training and experiment runners. Open them from that folder in the project."
      />
      <Panel title="Generated files" flush>
        {data?.length ? (
          <table className="data">
            <thead><tr><th>File</th><th className="text-right">Size KB</th></tr></thead>
            <tbody>
              {data.map((report) => (
                <tr key={report.path}>
                  <td className="font-medium">{report.path}</td>
                  <td className="num text-right">{formatNumber(report.size / 1024)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>No reports have been generated.</Empty>
        )}
      </Panel>
    </>
  );
}
