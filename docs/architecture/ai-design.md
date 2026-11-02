# AI Design

Every metric here comes from simulated runs and says nothing about performance on real equipment. Because the simulated faults follow clean equations, these scores should be treated as an upper bound.

Current numbers: [research/reports/ai-evaluation/metrics.json](../../research/reports/ai-evaluation/metrics.json).

## Dataset

`python -m research.datasets.generate --runs-per-class 20 --seed 1000`

- 80 runs of 3600 simulated seconds: normal, bearing wear, overheating, pump leak.
- Each run draws its target machine, severity (0.7 to 1.3), onset (300 to 900 s) and time of day from its seed.
- Edge protection is off, so trajectories develop naturally.
- 120 s windows at a 30 s hop, per rotating machine. Each reading is first reduced to a 5 s median across redundant sensors.
- Windows after onset but before the fault is physically observable are labelled `pending` and excluded from precision and recall.
- Hidden state is used for labels only.

## Split

`GroupShuffleSplit` by `run_id`, 70/30. Overlapping windows of one trajectory can never appear on both sides, and the script raises an error if they do.

## Models

| Task | Model | Baseline | Used live |
| --- | --- | --- | --- |
| Anomaly detection | Isolation Forest per machine kind | z-score on window means | Statistical detector (see ADR-005) |
| Fault classification | Random forest | Hand-written rules | Random forest |
| Degradation | Gradient boosting on hidden wear | Linear on vibration; mean predictor | Gradient boosting |
| Short-horizon risk | Random forest with isotonic calibration on grouped folds | Prevalence | Shown as a risk score (see ADR-006) |

Without a trained bundle, the system falls back to rule-based diagnosis and says so in the interface.

## Results on held-out simulated runs

| Metric | Value |
| --- | --- |
| Held-out runs | 24 of 80 |
| Statistical detector F1 / ROC-AUC | 0.969 / 0.999 |
| Isolation Forest F1 / ROC-AUC | 0.677 / 0.972 |
| Random forest macro F1 | 1.000 |
| Rule baseline macro F1 | 0.927 |
| Degradation MAE (boosting / linear / mean) | 0.0089 / 0.0173 / 0.0387 |
| Risk ROC-AUC | 0.956 |
| Risk Brier (model / prevalence) | 0.0119 / 0.0218 |

A macro F1 of 1.000 reflects how separable the simulated faults are. It is not evidence the classifier would behave this way on real machines.

## Decision safety

An alarm needs two consecutive anomalous windows and a named fault. Then `authorize()` decides: speed changes down to 50% can run automatically at confidence of at least 0.8. Stops, repairs, isolation and deep speed cuts always need a named human. Commands outside device limits are refused for everyone, and the simulated device checks its limits again itself.
