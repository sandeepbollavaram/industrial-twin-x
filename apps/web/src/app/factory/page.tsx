"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { SimulationControls } from "@/components/SimulationControls";
import { Empty, PageHeader, Panel, Status } from "@/components/ui";
import { formatNumber, machineSeverity, SIGNAL_LABELS } from "@/lib/api";
import { useLive } from "@/lib/live";

const Factory3D = dynamic(() => import("@/components/Factory3D"), {
  ssr: false,
  loading: () => <Empty>Loading the 3D view.</Empty>,
});

export default function FactoryPage() {
  const { overview } = useLive();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const machines = overview?.machines ?? [];
  const selected = machines.find((m) => m.machine_id === selectedId) ?? null;
  return (
    <>
      <PageHeader
        title="3D Factory"
        description="Drag to orbit, scroll to zoom, right-drag to pan. Select a machine to inspect it. Faulted machines are colored and labelled."
      />
      <div className="mb-4">
        <Panel title="Simulation controls"><SimulationControls /></Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <Panel flush>
          <div style={{ height: 600, background: "var(--bg)" }}>
            <Factory3D machines={machines} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </Panel>
        <Panel title={selected ? selected.machine_id : "Selection"}>
          {selected ? (
            <div className="text-[13px]">
              <div className="font-medium">{selected.name}</div>
              <div className="mb-2 mt-1">
                <Status {...machineSeverity(selected)} />
              </div>
              <div className="mb-3" style={{ color: "var(--ink-3)" }}>
                Zone {selected.zone_id}, {selected.gateway_id}
              </div>
              <dl>
                {Object.entries(selected.signals).map(([signal, value]) => (
                  <div key={signal} className="flex justify-between gap-3 border-t py-1" style={{ borderColor: "var(--line)" }}>
                    <dt style={{ color: "var(--ink-2)" }}>{SIGNAL_LABELS[signal] ?? signal}</dt>
                    <dd className="num">{formatNumber(value, 2)}</dd>
                  </div>
                ))}
              </dl>
              {selected.assessment && (
                <p className="mt-3" style={{ color: "var(--ink-2)" }}>
                  {selected.assessment.recommendation.action}
                </p>
              )}
            </div>
          ) : (
            <Empty>Select a machine in the 3D view.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}
