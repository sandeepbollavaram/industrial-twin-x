"use client";

import { useState } from "react";
import { postJson, usePoll } from "@/lib/api";
import { ErrorNote } from "./ui";

export function SimulationControls() {
  const { data: scenarios } = usePoll<{ scenario_id: string; description: string }[]>(
    "/api/v1/scenarios",
    0,
  );
  const [selected, setSelected] = useState("bearing_degradation");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const send = async (path: string, body: unknown, done: string) => {
    try {
      await postJson(path, body);
      setError(null);
      setMessage(done);
    } catch (err) {
      setMessage(null);
      setError(err instanceof Error ? err.message : "Request failed");
    }
  };
  const control = (action: string, value?: number) =>
    send("/api/v1/simulation/control", { action, value }, `Sent: ${action} ${value ?? ""}`);

  return (
    <div>
      <ErrorNote message={error} />
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" onClick={() => control("pause")}>Pause</button>
        <button className="btn" onClick={() => control("resume")}>Resume</button>
        {[1, 10, 50].map((speed) => (
          <button key={speed} className="btn" onClick={() => control("speed", speed)}>
            {speed}x
          </button>
        ))}
        <button className="btn" onClick={() => control("reset")}>Reset run</button>
        <span className="mx-1 h-5 w-px" style={{ background: "var(--line)" }} />
        <label htmlFor="scenario" className="text-[13px]">Scenario</label>
        <select
          id="scenario"
          className="input"
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
        >
          {scenarios?.map((s) => (
            <option key={s.scenario_id} value={s.scenario_id}>
              {s.scenario_id.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          onClick={() =>
            send(`/api/v1/scenarios/${selected}/start`, { params: {} }, `Started ${selected}`)
          }
        >
          Inject
        </button>
      </div>
      <p className="mt-2 text-[12px]" style={{ color: "var(--ink-3)" }}>
        {scenarios?.find((s) => s.scenario_id === selected)?.description}
        {message ? ` ${message}.` : ""}
      </p>
    </div>
  );
}
