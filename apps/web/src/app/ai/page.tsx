"use client";

import { Empty, PageHeader, Panel, Stat, Status } from "@/components/ui";
import { Assessment, formatNumber, usePoll } from "@/lib/api";

type Detection = {
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
  false_positive_rate: number | null;
  false_alarms: { per_machine_hour: number };
};
type Evaluation = {
  split: { train_runs: number; test_runs: number };
  anomaly_detection: Record<string, Detection>;
  fault_diagnosis: { random_forest: { macro_f1: number }; rule_baseline: { macro_f1: number } };
};
type AiData = {
  model_version: string | null;
  mode: string;
  assessments: Assessment[];
  evaluation: Evaluation | null;
};

export default function AiPage() {
  const { data } = usePoll<AiData>("/api/v1/ai");
  const evaluation = data?.evaluation;
  return (
    <>
      <PageHeader
        title="AI Intelligence"
        description="Live assessments and held-out evaluation. Metrics come from simulated runs split by run, and do not indicate performance on real equipment."
      />
      <div className="mb-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat label="Mode" value={<span className="text-base">{data?.mode ?? "n/a"}</span>} note={data?.model_version ?? undefined} />
        <Stat label="Held-out runs" value={evaluation?.split.test_runs ?? "n/a"} note={`${evaluation?.split.train_runs ?? "n/a"} training runs`} />
        <Stat label="Fault classifier macro F1" value={formatNumber(evaluation?.fault_diagnosis.random_forest.macro_f1, 3)} note="Simulated faults are cleanly separable" />
        <Stat label="Rule baseline macro F1" value={formatNumber(evaluation?.fault_diagnosis.rule_baseline.macro_f1, 3)} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Live assessment" flush>
          {data?.assessments.length ? (
            <table className="data">
              <thead><tr><th>Machine</th><th>State</th><th>Diagnosis</th><th className="text-right">Confidence</th><th className="text-right">Score</th></tr></thead>
              <tbody>
                {data.assessments.map((a) => (
                  <tr key={a.machine_id}>
                    <td className="font-medium">{a.machine_id}</td>
                    <td><Status severity={a.is_anomaly ? "warning" : "good"} label={a.is_anomaly ? "Anomaly" : "Normal"} /></td>
                    <td>{a.fault.replace(/_/g, " ")}</td>
                    <td className="num text-right">{formatNumber(a.confidence, 2)}</td>
                    <td className="num text-right">{formatNumber(a.anomaly_score, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty>No assessments yet. A window needs 60 simulated seconds of data.</Empty>
          )}
        </Panel>
        <Panel title="Anomaly detector comparison" flush>
          {evaluation ? (
            <table className="data">
              <thead><tr><th>Detector</th><th className="text-right">Precision</th><th className="text-right">Recall</th><th className="text-right">F1</th><th className="text-right">ROC-AUC</th><th className="text-right">FPR</th></tr></thead>
              <tbody>
                {Object.entries(evaluation.anomaly_detection).map(([name, m]) => (
                  <tr key={name}>
                    <td className="font-medium">{name.replace(/_/g, " ")}</td>
                    <td className="num text-right">{formatNumber(m.precision, 3)}</td>
                    <td className="num text-right">{formatNumber(m.recall, 3)}</td>
                    <td className="num text-right">{formatNumber(m.f1, 3)}</td>
                    <td className="num text-right">{formatNumber(m.roc_auc, 3)}</td>
                    <td className="num text-right">{formatNumber(m.false_positive_rate, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty>No evaluation report found. Run the training script.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}
