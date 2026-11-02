import { ReactNode } from "react";
import type { Severity } from "@/lib/api";

export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <header className="mb-4">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="mt-1 max-w-3xl text-[13px]" style={{ color: "var(--ink-2)" }}>
        {description}
      </p>
    </header>
  );
}

export function Panel({
  title,
  action,
  children,
  flush,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}) {
  return (
    <section
      className="rounded-md border"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      {title && (
        <div
          className="flex items-center justify-between gap-3 border-b px-3 py-2"
          style={{ borderColor: "var(--line)" }}
        >
          <h2 className="text-[13px] font-semibold">{title}</h2>
          {action}
        </div>
      )}
      <div className={flush ? "overflow-x-auto" : "p-3"}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div
      className="rounded-md border px-3 py-2.5"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      <div className="text-[12px]" style={{ color: "var(--ink-3)" }}>
        {label}
      </div>
      <div className="num mt-0.5 text-xl font-semibold">{value}</div>
      {note && (
        <div className="mt-0.5 text-[12px]" style={{ color: "var(--ink-3)" }}>
          {note}
        </div>
      )}
    </div>
  );
}

const SHAPE: Record<Severity, string> = {
  good: "rounded-full",
  warning: "rotate-45",
  critical: "",
  idle: "rounded-full opacity-60",
};

/** Status always pairs a shape and a word with its color, so it never relies on color alone. */
export function Status({ severity, label }: { severity: Severity; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap capitalize">
      <span
        aria-hidden
        className={`inline-block h-2 w-2 ${SHAPE[severity]}`}
        style={{ background: `var(--${severity})` }}
      />
      {label}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="px-3 py-6 text-center text-[13px]" style={{ color: "var(--ink-3)" }}>
      {children}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mb-3 text-[13px]" style={{ color: "var(--critical)" }}>
      {message}
    </p>
  );
}

export function severityOfAlert(severity: string): Severity {
  if (severity === "critical") return "critical";
  return severity === "warning" ? "warning" : "idle";
}

export function severityOfState(state: string): Severity {
  if (state === "recovered") return "good";
  if (state === "escalated") return "critical";
  return state === "rejected" ? "idle" : "warning";
}
