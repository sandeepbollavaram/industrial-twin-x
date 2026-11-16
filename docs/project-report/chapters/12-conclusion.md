# Conclusion and Future Enhancements

## 12.1 Project Summary

Industrial Twin-X is a software-only Industrial IoT digital twin. A seeded simulation replaces the physical plant:

- 10 machines, 100 devices and 300 sensors in 3 zones;
- lumped-parameter physical models;
- injectable equipment, network and sensor faults.

On top of it, an industrial-style software stack transports telemetry over MQTT, maintains a digital twin with reported and desired state, persists data to PostgreSQL, detects and classifies faults, protects machines locally at the gateway, detects manipulated sensors, and manages incidents through an audited, approval-aware state machine. A dashboard with a 3D view presents the system, and an experiment runner measures its behaviour under repeated, paired conditions. The code is covered by 101 automated tests, all passing on 16 November 2026, four of them through the real broker and database.

## 12.2 Objectives Achieved

@tab:achieved assesses each objective from Section 1.8 against the evidence.

Table: Assessment of objectives {#tab:achieved}

| Objective | Status | Evidence |
| --- | --- | --- |
| O1 Simulated environment, reproducible | Achieved in simulation | Target counts reached; byte-identical runs per seed (tests) |
| O2 MQTT transport and consistent twin | Achieved | All devices through the broker; command round trip; ordering rules (tests) |
| O3 Fault detection and classification | Achieved on simulated data | Baseline F1 0.969 on held-out runs; classifier macro-F1 1.000 on clean simulated classes |
| O4 Protection without central services | Achieved in simulation | 0 of 5 failures with edge, 5 of 5 without, under disconnection |
| O5 Manipulation detection without machine actions | Achieved for single-sensor attacks | 10 of 10 attacks detected, 0 false quarantines, 0 actions |
| O6 Auditable, approval-aware recovery | Achieved | State machine, authorisation tests, audit table |
| O7 Honest measurement | Achieved | Negative results reported: Isolation Forest, output, bearing downtime |

"Achieved in simulation" is a deliberate qualification. None of these objectives has been demonstrated on physical equipment.

## 12.3 Technical Contributions

1. **A reproducible integrated testbed.** One engine drives all devices deterministically, and the same central code runs live and headless. This made a paired experimental design possible.
2. **Leakage-aware evaluation against ground truth.** Hidden state labels the data but never becomes a feature; the data is split by run; and windows in which a fault is not yet physically manifest are excluded from precision and recall.
3. **Defence in depth for actuation.** Median voting at the edge, a single authorisation policy with impact classes and confidence thresholds, and device-side limits.
4. **A documented negative result.** The Isolation Forest underperformed a statistical baseline on these faults, and the system was designed around the evidence rather than the plan.
5. **A measured demonstration of edge autonomy.** Under central disconnection, gateway-local protection prevented every simulated overheating failure.

## 12.4 Experimental Findings

- Edge protection prevented failures when central services were unreachable (0 of 5 against 5 of 5).
- With central services connected, central detection derated the overheating motor before the edge limit was reached, so the edge added nothing in that case.
- Both single-sensor attacks were quarantined in 47 to 58 seconds, with no false quarantines and no machine actions.
- Store-and-forward achieved a delivery ratio of 1.000 through a 900-second uplink loss. A gateway process outage lost 1.7% of messages.
- Protection *reduced* one-hour output, because the simulation does not count failure costs. This is not an economic result.
- Bearing protection gave similar average downtime to no protection. Its benefit depended on classifier confidence: a confident diagnosis was derated automatically, with no downtime, while a 0.72 to 0.74 confidence diagnosis waited for approval and the edge eventually stopped the machine.
- The statistical baseline outperformed the Isolation Forest (F1 0.969 against 0.677). The forest missed all four held-out overheating runs.

## 12.5 Limitations

- **Simulation only.** No result was obtained with physical hardware. The physical models are simplified and uncalibrated, so neither real-world safety nor hardware performance is established.
- **Synthetic data and clean faults.** The AI results, especially the perfect classification, reflect the simulation's construction.
- **Operating-point sensitivity.** The detectors flag deliberately derated machines as anomalous, which produced repeated low-confidence incidents.
- **Risk calibration.** The risk score under-predicts in the middle range and is not a probability. Remaining useful life is not predicted.
- **Security.** The broker and API have no authentication or TLS, messages are unsigned, the approver is a typed name, and the audit log is append-only only by convention. The deployment is safe only on localhost.
- **Integrity checks.** Coordinated manipulation of most of a signal's sensors, and slow biases within tolerance, are not detected.
- **Experiment size.** Five seeds, fixed severity and onset, one target machine per fault, and no broker or database in the experiment loop.
- **Scale.** The full stack was exercised at 100 devices. Only the engine was benchmarked at 500.
- **Frontend.** There are no automated frontend tests, and the 3D labels emit a development-mode React warning.
- **Uncommitted fixes.** Three fixes and two regression tests from post-publication verification are in the working tree but not yet committed to the repository.
- **OPC UA.** Not implemented.

## 12.6 Future Enhancements

The following are proposed improvements. **None of them is implemented.**

1. **OPC UA integration.** Expose machines through an OPC UA server, using the platform-independent, secured architecture described by the OPC Foundation [@opcua], alongside MQTT.
2. **TLS and authentication.** Add broker authentication with per-client access control and TLS; API authentication with roles for operators and approvers; signed messages; and a tamper-evident (hash-chained) audit log, following NIST SP 800-82 and ISA/IEC 62443 [@nist80082; @isa62443].
3. **Benchmarking at 500 devices.** Run the full live stack at scale 5, measuring broker throughput, pipeline latency, database write latency and memory, and tune batch sizes and window evaluation accordingly.
4. **Larger experiments.** Use more seeds, randomised fault severities and onsets, all target machines, and include the broker and database in the loop so that their behaviour is also measured.
5. **Damage and economic modelling.** Model repair cost, parts, downtime beyond the window and safety consequences, so protection policies can be compared on cost rather than one-hour output.
6. **Better AI generalisation.** Train across operating points or condition on commanded speed, evaluate with repeated grouped cross-validation, add model-based fault detection [@isermann2005], improve risk calibration, and detect unknown faults.
7. **Frontend automated tests.** Add component tests and browser end-to-end tests for the main operator workflows (approval, scenario injection, reset).
8. **Validation on real industrial data.** Evaluate the detectors and integrity checks on public or partner datasets with real faults, to measure the gap between simulated and real performance.
9. **Hardware-in-the-loop experiments.** Optionally connect a small physical rig, such as a motor with real temperature and vibration sensors, to the same pipeline. This would test the software against real measurements while keeping the simulation for faults that are unsafe to induce.
