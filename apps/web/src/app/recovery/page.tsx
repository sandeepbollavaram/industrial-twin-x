"use client";

import { useState } from "react";
import { Empty, ErrorNote, PageHeader, Panel, severityOfState, Status } from "@/components/ui";
import { formatNumber, formatSimTime, Incident, postJson, usePoll } from "@/lib/api";

export default function RecoveryPage() {
  const { data, refresh } = usePoll<Incident[]>("/api/v1/recovery/incidents", 2000);
  const [operator, setOperator] = useState("");
  const [error, setError] = useState<string | null>(null);

  const act = async (incident: Incident, action: string) => {
    try {
      await postJson(`/api/v1/recovery/incidents/${incident.incident_id}/${action}`, { operator });
      setError(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  };
  const named = operator.trim().length > 0;

  return (
    <>
      <PageHeader
        title="Recovery Operations"
        description="Incident state machine and audit trail. High-impact commands and low-confidence diagnoses wait here for a named operator."
      />
      <ErrorNote message={error} />
      <div className="mb-3 flex items-center gap-2">
        <label htmlFor="operator">Operator name</label>
        <input id="operator" className="input" value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="Required to act" />
      </div>
      {data?.length ? (
        <div className="grid gap-3">
          {data.map((incident) => {
            const open = incident.closed_at === null;
            return (
              <Panel
                key={incident.incident_id}
                title={`${incident.machine_id}: ${incident.fault.replace(/_/g, " ")}`}
                action={<Status severity={severityOfState(incident.state)} label={incident.state.replace(/_/g, " ")} />}
              >
                <p className="mb-2 text-[13px]" style={{ color: "var(--ink-2)" }}>
                  Confidence {formatNumber(incident.confidence, 2)}. Source: {incident.source}.
                  Proposed action: {incident.command ?? "none"}{incident.value !== null ? ` ${incident.value}` : ""}.
                </p>
                {open && (
                  <div className="mb-3 flex flex-wrap gap-2">
                    {incident.state === "awaiting_approval" && (
                      <>
                        <button className="btn btn-primary" disabled={!named} onClick={() => act(incident, "approve")}>Approve action</button>
                        <button className="btn" disabled={!named} onClick={() => act(incident, "reject")}>Reject</button>
                      </>
                    )}
                    <button className="btn" disabled={!named} onClick={() => act(incident, "repair")}>Record maintenance complete</button>
                  </div>
                )}
                <details open={open}>
                  <summary className="cursor-pointer text-[13px]">Audit trail ({incident.audit.length})</summary>
                  <table className="data mt-2">
                    <thead><tr><th>Sim time</th><th>State</th><th>Actor</th><th>Detail</th></tr></thead>
                    <tbody>
                      {incident.audit.map((entry, index) => (
                        <tr key={index}>
                          <td className="num">{formatSimTime(entry.sim_time)}</td>
                          <td>{entry.state.replace(/_/g, " ")}</td>
                          <td>{entry.actor}</td>
                          <td className="text-[12px]">{entry.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              </Panel>
            );
          })}
        </div>
      ) : (
        <Panel><Empty>No incidents in this run.</Empty></Panel>
      )}
    </>
  );
}
