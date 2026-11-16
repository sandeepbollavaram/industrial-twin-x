"""Generate report figures from recorded experiment and evaluation outputs only.

Usage (from the repository root): .venv/Scripts/python.exe docs/project-report/build/make_figures.py
Inputs: research/reports/experiments/summary.json, research/reports/ai-evaluation/metrics.json
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "project-report" / "figures"
SUMMARY = json.loads((ROOT / "research/reports/experiments/summary.json").read_text())
METRICS = json.loads((ROOT / "research/reports/ai-evaluation/metrics.json").read_text())

# Reference palette: one hue for single-series magnitude, first three slots for categories.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#dddcd8"
plt.rcParams.update(
    {
        "font.family": "Arial",
        "font.size": 10,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)
LABELS = {
    "overheat_edge_central": "Edge and central",
    "overheat_central_only": "Central only",
    "overheat_edge_only": "Edge only",
    "overheat_unprotected": "No protection",
    "overheat_disconnect_edge": "Central disconnected,\nedge on",
    "overheat_disconnect_no_edge": "Central disconnected,\nedge off",
    "normal_control": "No fault (control)",
    "gateway_outage": "Gateway outage, 300 s",
    "network_degradation": "10% loss, +0.8 s, 600 s",
    "telemetry_backlog": "Link loss, 900 s",
    "sensor_bias": "Rising bias",
    "sensor_replay": "Frozen replay",
    "bearing_edge_central": "Bearing, protected",
    "bearing_unprotected": "Bearing, unprotected",
    "leak_edge_central": "Pump leak, protected",
}


def finish(fig, ax, name: str) -> None:
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)
    print("wrote", name)


def hbar(conditions, values, errors, xlabel, name, fmt, xmax=None, annotate=None):
    fig, ax = plt.subplots(figsize=(6.3, 0.48 * len(conditions) + 1.1))
    labels = [LABELS[c] for c in conditions]
    ax.barh(labels, values, xerr=errors, color=BLUE, height=0.55, error_kw={"ecolor": INK, "lw": 0.8, "capsize": 3})
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.tick_params(length=0)
    if xmax:
        ax.set_xlim(0, xmax)
    for i, v in enumerate(values):
        text = annotate[i] if annotate else fmt.format(v)
        ax.text(v + (xmax or max(values) or 1) * 0.01, i, text, va="center", color=INK, fontsize=9)
    finish(fig, ax, name)


def mean(cond, metric):
    m = SUMMARY["summary"][cond][metric]
    return m["mean"] or 0.0, m["std"] or 0.0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = SUMMARY["summary"]

    over = ["overheat_edge_central", "overheat_central_only", "overheat_edge_only", "overheat_unprotected",
            "overheat_disconnect_edge", "overheat_disconnect_no_edge"]
    fails = [s[c]["failures"] for c in over]
    hbar(over, fails, None, "Runs in which the overheating motor failed (of 5)", "fig-overheat-failures.png",
         "{}", xmax=5.6, annotate=[f"{f} of {s[c]['runs']}" for f, c in zip(fails, over)])

    down = [mean(c, "machine_downtime_s") for c in over]
    hbar(over, [d[0] for d in down], [d[1] for d in down], "Downtime of the faulted motor, simulated seconds (mean, 1 SD)",
         "fig-overheat-downtime.png", "{:.0f}")

    out_conds = ["normal_control"] + over
    outputs = [mean(c, "total_output_units") for c in out_conds]
    fig, ax = plt.subplots(figsize=(6.3, 0.48 * len(out_conds) + 1.1))
    # Dots, not bars: the axis does not start at zero, and bar length would exaggerate gaps.
    ys = list(range(len(out_conds)))
    ax.plot([o[0] for o in outputs], ys, linestyle="none", marker="o", ms=8, color=BLUE)
    ax.set_yticks(ys, [LABELS[c] for c in out_conds])
    ax.invert_yaxis()
    ax.set_xlim(20300, 21800)
    ax.set_xlabel("Total factory output in one simulated hour, units (mean of 5 seeds)")
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    for i, (v, _) in enumerate(outputs):
        ax.text(v + 25, i, f"{v:,.0f}", va="center", fontsize=9, color=INK)
    finish(fig, ax, "fig-output.png")

    net = ["normal_control", "gateway_outage", "network_degradation", "telemetry_backlog"]
    ratios = [mean(c, "delivery_ratio") for c in net]
    hbar(net, [r[0] for r in ratios], [r[1] for r in ratios], "Message delivery ratio (mean of 5 seeds)",
         "fig-delivery.png", "{:.3f}", xmax=1.12)

    sec = ["sensor_bias", "sensor_replay"]
    det = [mean(c, "detection_time_s") for c in sec]
    hbar(sec, [d[0] for d in det], [d[1] for d in det], "Time from attack start to quarantine, simulated seconds (mean, 1 SD)",
         "fig-tamper.png", "{:.0f} s", xmax=70)

    # Detector comparison: three metrics on the same 0-1 scale, three fixed category colours.
    ad = METRICS["anomaly_detection"]
    names = [("statistical_baseline", "Statistical baseline", BLUE), ("isolation_forest", "Isolation Forest", ORANGE),
             ("hybrid", "Hybrid (either alarms)", AQUA)]
    metrics = [("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]
    fig, ax = plt.subplots(figsize=(6.3, 3.2))
    width = 0.26
    for j, (key, label, colour) in enumerate(names):
        xs = [i + (j - 1) * width for i in range(len(metrics))]
        vals = [ad[key][m] for m, _ in metrics]
        ax.bar(xs, vals, width=width - 0.03, color=colour, label=label)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.015, f"{v:.3f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(len(metrics)), [m for _, m in metrics])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Score on held-out runs")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(OUT / "fig-detectors.png", dpi=200)
    plt.close(fig)
    print("wrote fig-detectors.png")

    # Detection latency by fault: baseline vs Isolation Forest; missed runs labelled, not plotted as zero.
    faults = [("bearing_wear", "Bearing wear"), ("overheating", "Overheating"), ("pump_leak", "Pump leak")]
    fig, ax = plt.subplots(figsize=(6.3, 3.0))
    for j, (key, label, colour) in enumerate(names[:2]):
        for i, (fault, _) in enumerate(faults):
            t = ad[key]["timing"][fault]
            y = i + (j - 0.5) * 0.36
            latency = t["detection_latency_s"]["mean"]
            if latency is None:
                ax.text(5, y, f"{label}: missed {t['missed_runs']} of {t['runs']} runs", va="center", fontsize=8.5, color=colour)
            else:
                ax.barh(y, latency, height=0.32, color=colour, label=label if i == 0 else None)
                ax.text(latency + 8, y, f"{latency:.0f} s ({t['runs']} runs)", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(faults)), [f for _, f in faults])
    ax.invert_yaxis()
    ax.set_xlabel("Mean detection latency after fault onset, simulated seconds")
    ax.set_xlim(0, 900)
    ax.tick_params(length=0)
    ax.legend(frameon=False, loc="lower right")
    finish(fig, ax, "fig-latency.png")

    # Reliability of the risk score.
    rel = METRICS["failure_risk"]["reliability"]
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls="--", label="Perfect calibration")
    xs = [b["mean_predicted"] for b in rel]
    ys = [b["observed_rate"] for b in rel]
    ax.plot(xs, ys, color=BLUE, lw=2, marker="o", ms=6, label="Risk model")
    for b in rel:
        ax.annotate(f"n={b['n']}", (b["mean_predicted"], b["observed_rate"]), textcoords="offset points",
                    xytext=(6, -10), fontsize=8, color=MUTED)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Mean predicted risk in bin")
    ax.set_ylabel("Observed failure rate within 900 s")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "fig-reliability.png", dpi=200)
    plt.close(fig)
    print("wrote fig-reliability.png")


if __name__ == "__main__":
    main()
