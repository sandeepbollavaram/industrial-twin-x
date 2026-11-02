"use client";

import { formatNumber, Machine, machineSeverity } from "@/lib/api";
import { Status } from "./ui";

export function MachineTable({ machines }: { machines: Machine[] }) {
  return (
    <table className="data">
      <thead>
        <tr>
          <th>Machine</th>
          <th>Zone</th>
          <th>Gateway</th>
          <th>State</th>
          <th className="text-right">Speed</th>
          <th className="text-right">Power kW</th>
          <th className="text-right">Winding °C</th>
          <th className="text-right">Vibration mm/s</th>
        </tr>
      </thead>
      <tbody>
        {machines.map((machine) => {
          const state = machineSeverity(machine);
          const s = machine.signals;
          return (
            <tr key={machine.machine_id}>
              <td>
                <div className="font-medium">{machine.machine_id}</div>
                <div className="text-[12px]" style={{ color: "var(--ink-3)" }}>{machine.name}</div>
              </td>
              <td>{machine.zone_id}</td>
              <td>{machine.gateway_id}</td>
              <td><Status severity={state.severity} label={state.label} /></td>
              <td className="num text-right">{formatNumber(s.rpm, 0)}</td>
              <td className="num text-right">{formatNumber(s.power_kw)}</td>
              <td className="num text-right">{formatNumber(s.winding_temp_c)}</td>
              <td className="num text-right">{formatNumber(s.vibration_mm_s, 2)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
