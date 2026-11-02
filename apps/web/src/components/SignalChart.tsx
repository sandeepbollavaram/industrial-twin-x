"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatSimTime, SIGNAL_LABELS } from "@/lib/api";

type Point = { t: number; v: number };

/** Readings from redundant sensors arrive staggered, so plot the median of each 5 s bin. */
function binned(points: Point[]): Point[] {
  const bins = new Map<number, number[]>();
  for (const point of points) {
    const key = Math.floor(point.t / 5) * 5;
    const bin = bins.get(key);
    if (bin) bin.push(point.v);
    else bins.set(key, [point.v]);
  }
  return [...bins.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([t, values]) => {
      values.sort((a, b) => a - b);
      return { t, v: values[Math.floor(values.length / 2)] };
    });
}

export function SignalChart({ signal, points }: { signal: string; points: Point[] }) {
  const data = useMemo(() => binned(points), [points]);
  const label = SIGNAL_LABELS[signal] ?? signal;
  return (
    <figure>
      <figcaption className="mb-1 text-[13px] font-semibold">{label}</figcaption>
      <div style={{ height: 170 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={formatSimTime}
              tick={{ fill: "var(--ink-3)", fontSize: 11 }}
              stroke="var(--line)"
              minTickGap={60}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: "var(--ink-3)", fontSize: 11 }}
              stroke="var(--line)"
              width={48}
            />
            <Tooltip
              isAnimationActive={false}
              labelFormatter={(value) => `Sim time ${formatSimTime(Number(value))}`}
              formatter={(value) => [Number(value).toFixed(2), label]}
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                borderRadius: 4,
                fontSize: 12,
                color: "var(--ink)",
              }}
            />
            <Line
              dataKey="v"
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
