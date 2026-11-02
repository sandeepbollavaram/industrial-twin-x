"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { formatSimTime } from "@/lib/api";
import { LiveProvider, useLive } from "@/lib/live";
import { Status } from "./ui";

const NAV = [
  ["/", "Overview"],
  ["/factory", "3D Factory"],
  ["/devices", "Device Explorer"],
  ["/telemetry", "Telemetry"],
  ["/ai", "AI Intelligence"],
  ["/maintenance", "Predictive Maintenance"],
  ["/network", "Network Monitoring"],
  ["/security", "Cybersecurity"],
  ["/recovery", "Recovery Operations"],
  ["/experiments", "Experiments"],
  ["/reports", "Reports"],
  ["/settings", "System Settings"],
] as const;

function ThemeToggle() {
  const [theme, setTheme] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("twinx-theme");
      if (saved) {
        document.documentElement.dataset.theme = saved;
        const timer = setTimeout(() => setTheme(saved), 0);
        return () => clearTimeout(timer);
      }
    } catch {
      // Storage may be blocked; the OS preference still applies.
    }
  }, []);

  const toggle = () => {
    const dark =
      theme === "dark" || (theme === null && matchMedia("(prefers-color-scheme: dark)").matches);
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      localStorage.setItem("twinx-theme", next);
    } catch {
      // Not persisted this session.
    }
  };

  return (
    <button className="btn w-full" onClick={toggle}>
      Switch theme
    </button>
  );
}

function TopBar() {
  const { overview, connected } = useLive();
  const infra = overview?.infrastructure;
  return (
    <div
      className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b px-5 py-2 text-[13px]"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      <span style={{ color: "var(--ink-2)" }}>Software simulation. No physical hardware.</span>
      <span className="num">
        Sim time {overview ? formatSimTime(overview.sim_time) : "--:--:--"}
      </span>
      <span>Scenario: {overview?.scenario_id ?? "n/a"}</span>
      <span className="ml-auto flex flex-wrap gap-4">
        <Status severity={connected ? "good" : "critical"} label={connected ? "API" : "API offline"} />
        <Status
          severity={infra?.mqtt_connected ? "good" : "critical"}
          label={infra?.mqtt_connected ? "MQTT" : "MQTT offline"}
        />
        <Status
          severity={infra?.database_connected ? "good" : "critical"}
          label={infra?.database_connected ? "Database" : "Database offline"}
        />
      </span>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <LiveProvider>
      <div className="flex min-h-screen">
        <aside
          className="sticky top-0 flex h-screen w-52 shrink-0 flex-col border-r"
          style={{ background: "var(--surface)", borderColor: "var(--line)" }}
        >
          <div className="px-4 py-3.5 text-[15px] font-semibold tracking-tight">
            Industrial Twin-X
          </div>
          <nav className="flex-1 overflow-y-auto px-2" aria-label="Main">
            {NAV.map(([href, label]) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className="mb-0.5 block rounded px-2.5 py-1.5 text-[13px]"
                  style={{
                    background: active ? "var(--surface-2)" : "transparent",
                    color: active ? "var(--ink)" : "var(--ink-2)",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="p-3">
            <ThemeToggle />
          </div>
        </aside>
        <div className="min-w-0 flex-1">
          <TopBar />
          <main className="mx-auto max-w-[1500px] p-5">{children}</main>
        </div>
      </div>
    </LiveProvider>
  );
}
