# Experiment Results

All values were measured in software simulation. Nothing here was validated on physical equipment.

Configuration: 5 seeds (5000 to 5004, separate from the training seeds), 3600 simulated seconds per run, 100 devices. Values are mean ± SD. Machine-level columns refer to the faulted machine.

Reproduce with `python -m research.experiments.run_experiments --seeds 5 --workers 4`. Full data is in [summary.json](summary.json). Figures: [downtime](overheating_downtime.png), [detection time](detection_time.png), [delivery ratio](delivery_ratio.png).

## Resilience

| Condition | Machine failures | Downtime s | Detection s | Recovery s |
| --- | --- | --- | --- | --- |
| Overheating, edge and central | 0 / 5 | 0 | 270 ± 0 | 300 ± 0 |
| Overheating, central only | 0 / 5 | 0 | 270 ± 0 | 300 ± 0 |
| Overheating, edge only | 0 / 5 | 0 | not measured | not measured |
| Overheating, no protection | 5 / 5 | 691 ± 369 | none | none |
| Overheating, central disconnected, edge on | 0 / 5 | 0 | 883 ± 35 | 1914 ± 35 |
| Overheating, central disconnected, edge off | 5 / 5 | 691 ± 369 | 2990 ± 0 | none |
| Bearing wear, edge and central | 0 / 5 | 504 ± 462 | 324 ± 115 | 1419 ± 1022 |
| Bearing wear, no protection | 5 / 5 | 478 ± 123 | none | none |
| Pump leak, edge and central | 0 / 5 | 0 | 60 ± 0 | pending approval |

### How to read this

- **The clearest result is edge autonomy.** With central unreachable from before the fault, the motor failed in 5 of 5 runs without the edge and 0 of 5 with it.
- **With central connected, the edge added nothing in this overheating test.** Central derated the motor before the edge limit was reached, so the two rows match.
- **Protection cost production in this one-hour window.** Total factory output was 20,512 to 20,756 units with protection on and 20,909 with none in the overheating runs, against 21,600 with no fault. Derating costs output at once, while failure comes late in the hour. The simulator does not cost machine damage or repair, so this comparison favours running to failure and should not be read as an economic result.
- **Bearing protection did not reduce downtime.** It replaced seizure with a controlled stop, at similar downtime.
- **A detection time of 883 s under disconnection is the time the edge acted.** Central only learned of it after reconnection.
- **SD values of 0** arise because alarms fall on a fixed 30 s evaluation grid and the fault onset is fixed in these runs.
- **Severity and fault onset were fixed here,** and only the seed varied, so this understates real variability.
- Recovery means the incident's verifier passed, not that the fault was repaired. No operator acts during experiments, so the leak waits for approval by design.

## IoT

| Condition | Delivery ratio | Mean latency s | Peak backlog |
| --- | --- | --- | --- |
| Normal | 1.000 | 0.03 | 0 |
| Gateway outage, 300 s | 0.983 | 0.03 | 0 |
| Network degradation, 10% loss, 0.8 s added, 600 s | 0.995 | 0.07 | 0 |
| Backlog, 900 s link loss | 1.000 | 0.03 | 3,584 |
| Central disconnected, 2800 s | 0.991 | 0.03 | 16,776 |

The disconnection ratio is below 1 because some backlog was still flushing when the hour ended. Latency comes from the simulated network model, not from Mosquitto.

## Security

| Attack | Detected | Time to detect s | False quarantines | Machine action caused |
| --- | --- | --- | --- | --- |
| Rising bias on one sensor | 5 / 5 | 47 ± 2 | 0 | None |
| Replayed frozen value on one sensor | 5 / 5 | 58 ± 0 | 0 | None |

## False alarms and performance

- In these runs no incident opened on a healthy machine, and no sensor was falsely quarantined. Short anomaly flags do still occur: the live demonstration showed one on CNV-A03, and the leak condition averaged 0.4 sustained alarms before onset.
- Headless processing with the central pipeline reached about 2,400 to 2,800 messages per wall second on the laptop, with 4 parallel workers competing for CPU, and each worker used about 190 to 215 MB.

Engine-only benchmark, 600 simulated seconds, no central pipeline or broker:

| Devices | Wall s | Real-time factor | RSS MB |
| --- | --- | --- | --- |
| 100 | 0.40 | 1483x | 40 |
| 500 | 1.60 | 375x | 43 |

This shows only that the engine scales. The full stack has not been benchmarked at 500 devices.

Observed once in the live stack at 50x speed (500 messages per second): pipeline latency p95 of about 180 to 200 ms, batch write of about 319 ms, and no rows dropped. These are single observations, not repeated experiments. Experiments do not include the database, so database write latency has no repeated measurement yet.
