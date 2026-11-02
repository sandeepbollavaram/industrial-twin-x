# Design Decisions

## ADR-001: Python packages use underscores

The requested layout named folders such as `modules/digital-twin`. Python cannot import hyphenated names, so these became `modules/digital_twin` and so on. The boundaries are unchanged.

## ADR-002: Modular monolith with two processes

The simulator and the central API are separate processes connected only through MQTT. Everything else is modules inside them. Microservices would add operational load on a 16 GB laptop with no benefit for a single-node prototype. Redis, Kafka and Kubernetes are not used: a bounded in-process queue meets the measured load.

## ADR-003: Devices are data, not processes

One SimPy process advances all devices. Telemetry is staggered over the 5 s period. This is why 100 devices need no per-device container, and it keeps runs deterministic.

## ADR-004: Central logic does not depend on the broker

`CentralPipeline` takes plain dictionaries. Live mode feeds it from MQTT; experiments feed it directly. Experiments therefore exercise the same logic and are repeatable, but they do not measure broker latency. Network latency in experiments comes from the simulated network model.

## ADR-005: The statistical detector gates live alarms, not the Isolation Forest

On held-out simulated runs (dataset seed 1000, 20 runs per class, split seed 7):

| Detector | F1 | ROC-AUC | Overheating runs detected | Machines with a sustained false alarm |
| --- | --- | --- | --- | --- |
| Statistical baseline | 0.969 | 0.999 | 4 of 4 | 11 |
| Isolation Forest | 0.677 | 0.972 | 0 of 4 | 12 |
| Hybrid (either alarms) | 0.945 | 1.000 | 4 of 4 | 21 |

The Isolation Forest was the planned proposed method. It lost to the baseline, mainly because it missed slow thermal drift in a high-dimensional feature space. The hybrid added false alarms and almost no speed. The live system uses the statistical detector; the others remain implemented and are reported for comparison. A false alarm alone opens no incident: the fault classifier must also name a fault.

The comparison uses simulated data only, and this choice was made on that test split. The experiments use separate seeds.

## ADR-006: "Risk score", not "failure probability"

The handoff allows a failure probability only where properly calibrated. Isotonic calibration improved the Brier score over the prevalence baseline (0.0119 against 0.0218), but the reliability table under-predicts in the middle bins: predictions near 0.50 had an observed rate of 0.98. The interface therefore shows a risk score. No remaining useful life is predicted.

## ADR-007: Edge protection uses deterministic limits and sensor voting

Edge limits act on the median of redundant sensors and need at least two votes, so one manipulated sensor cannot trigger or suppress an action. No ML output reaches this path.

## ADR-008: PostgreSQL publishes on port 15432

Windows reserves TCP ranges including 54738-55487 on this machine, and a native PostgreSQL 18 service is installed. Port 15432 avoids both.

## ADR-009: TypeScript 6

`typescript-eslint`, used through `eslint-config-next`, refuses to run on TypeScript 7.0, so the frontend is on TypeScript 6.

## ADR-010: OPC UA is deferred

The handoff treats OPC UA as a separate advanced integration. It is not implemented yet, and `asyncua` is not a dependency. `infrastructure/opcua/` is reserved for it.
