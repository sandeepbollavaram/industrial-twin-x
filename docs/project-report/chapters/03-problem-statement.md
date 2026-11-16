# Problem Statement and Objectives

## 3.1 Problem Definition

An industrial plant needs to know the condition of its equipment, detect developing faults early, and respond in a way that limits damage without causing unnecessary stoppages. It must do this using measurements that are noisy, sometimes missing, sometimes delayed, and occasionally manipulated, and it must keep protecting equipment when its network or central services fail.

The problem addressed by this project is to design, implement and evaluate a software system that:

1. maintains a consistent, queryable state of every monitored device from streamed telemetry;
2. detects and diagnoses equipment faults from that telemetry;
3. continues to protect equipment when central services are unreachable;
4. resists manipulation of individual sensors; and
5. responds to faults through an auditable process that cannot be driven by low-confidence analytics alone.

Because no industrial equipment was available, and because deliberately damaging equipment or attacking a network is unsafe, the problem is posed and solved entirely in software. The physical plant is replaced by a simulation whose behaviour is known exactly.

## 3.2 Existing System

There is no existing system at the institution that this project replaces. In this context, the "existing system" means the common practice that the literature in Chapter 2 describes, of which industrial monitoring is typically assembled from separate parts:

- equipment readings collected by a SCADA or historian system and inspected by operators or fixed alarm thresholds;
- maintenance planned on fixed intervals or after failure, with condition-based maintenance applied selectively [@jardine2006];
- analytics, where present, developed and evaluated separately from the operational system, often on historical data [@carvalho2019];
- security controls designed by following guidance such as NIST SP 800-82 and ISA/IEC 62443 [@nist80082; @isa62443], usually independently of the analytics.

For academic study, the practical alternative is a physical demonstrator built from microcontrollers and sensors, or the use of a public dataset. A physical demonstrator offers realism but has few machines and cannot be run to failure repeatedly. A public dataset offers real or realistic data but cannot be interacted with: no command can be sent and no network fault injected.

## 3.3 Limitations of Existing Approaches

For the purpose of studying integrated IIoT behaviour, these approaches have the following limitations:

- **No ground truth.** In real plants and most datasets, the true degradation state is unknown, so detection latency and prediction lead time cannot be measured exactly.
- **No repeatability.** A physical failure happens once; it cannot be replayed with a different protection policy.
- **No safe fault injection.** Overheating a motor, opening a leak or attacking a network is unsafe on real equipment.
- **Separated concerns.** Analytics evaluated offline do not show how a detector behaves once its output drives an incident process, nor how it interacts with edge protection or manipulated sensors.
- **Fixed thresholds without corroboration.** A single-sensor threshold alarm reacts to a single faulty or manipulated sensor in the same way as to a real fault.

## 3.4 Proposed System

Industrial Twin-X replaces the physical plant with a deterministic, seeded simulation, and builds an industrial-style software stack on top of it:

- a **virtual factory** of 10 machines and 100 devices with 300 sensors, whose readings follow simplified physical models and whose faults can be injected on demand;
- **MQTT transport** through Eclipse Mosquitto with versioned message schemas;
- a **digital twin** with reported and desired state, ordering rules and persistence;
- **analytics** for anomaly detection, fault classification, degradation estimation and risk scoring, evaluated on held-out simulation runs;
- **edge protection** that runs on each simulated gateway, independently of central services;
- **sensor integrity monitoring** using redundant sensors;
- a **recovery engine** with an explicit state machine, command authorisation and an audit trail;
- a **dashboard** with live views and a three-dimensional factory model;
- an **experiment runner** that compares protection policies under identical seeds.

A software-simulated environment suits controlled experimentation because it provides exact ground truth, unlimited safe fault injection and exact repeatability. However, software simulation **does not establish real-world industrial safety or hardware performance**. A detector that works on simulated faults may fail on real ones, and a protection policy that prevents simulated failures may not prevent real ones. The results of this project concern the software and its behaviour against the simulation.

## 3.5 Project Objectives

The objectives listed in Section 1.8 are restated here with measurable criteria in @tab:objectives.

Table: Project objectives and their evaluation criteria {#tab:objectives}

| No. | Objective | Evaluation criterion |
| --- | --- | --- |
| O1 | Simulate an industrial environment with physically motivated, reproducible behaviour | Target device counts reached; identical output for identical seed (automated test) |
| O2 | Transport telemetry and commands over MQTT and maintain a consistent twin | All 100 devices reporting through the broker; command round trip changes the simulated machine (integration tests) |
| O3 | Detect and classify faults | Precision, recall, F1, ROC-AUC and detection latency on held-out runs, compared with a baseline |
| O4 | Protect equipment without central services | Machine failures with and without edge protection under central disconnection |
| O5 | Detect manipulated sensors without causing machine actions | Detection rate, time to detect, false quarantines, machine actions caused |
| O6 | Manage faults through an auditable, approval-aware process | State machine and authorisation tests; recorded audit trail |
| O7 | Measure and report behaviour honestly | Seeded repeated experiments; unfavourable results reported |

## 3.6 Functional Requirements

@tab:fr lists the functional requirements and where each is implemented.

Table: Functional requirements {#tab:fr}

| ID | Requirement | Implementation |
| --- | --- | --- |
| FR1 | Simulate 3 zones, 5 gateways, 10 machines, 100 devices and 300 sensors, extensible to 500 devices | `simulation/factory/layout.py` |
| FR2 | Model temperature, vibration, pressure, flow, current, speed, power and device health | `simulation/devices/machines.py` |
| FR3 | Inject faults: bearing degradation, overheating, pump leak | `simulation/scenarios/catalog.py` |
| FR4 | Inject network faults: gateway outage, latency and loss, central disconnection, backlog | `simulation/scenarios/catalog.py`, `simulation/network/gateway.py` |
| FR5 | Inject sensor manipulation: bias and replay | `simulation/sensors/models.py` |
| FR6 | Publish telemetry, status and alerts on defined MQTT topics; receive commands | `modules/telemetry/topics.py`, `simulation/run.py` |
| FR7 | Validate messages against a versioned schema | `modules/telemetry/schema.py` |
| FR8 | Maintain reported and desired device state, with gap, duplicate and ordering accounting | `modules/digital_twin/engine.py` |
| FR9 | Persist telemetry, events, twin state and the recovery audit | `apps/api/twinx_api/db.py`, `runtime.py` |
| FR10 | Detect anomalies and classify faults | `modules/anomaly_detection`, `modules/fault_diagnosis` |
| FR11 | Estimate degradation and a maintenance risk score with a recommendation | `modules/predictive_maintenance/models.py` |
| FR12 | Protect machines locally on the gateway | `modules/edge_computing/policy.py` |
| FR13 | Detect and quarantine inconsistent or frozen sensors | `modules/cybersecurity/integrity.py` |
| FR14 | Manage incidents through a state machine with an audit trail | `modules/recovery_engine/manager.py` |
| FR15 | Require human approval for high-impact or low-confidence actions; enforce actuator limits | `modules/recovery_engine/authorization.py`, `simulation/actuators/limits.py` |
| FR16 | Provide a dashboard with live status, 3D view and controls | `apps/web` |
| FR17 | Run repeated, seeded experiments and generate figures from their output | `research/experiments/run_experiments.py` |

## 3.7 Non-Functional Requirements

Table: Non-functional requirements {#tab:nfr}

| ID | Category | Requirement | How it is met or checked |
| --- | --- | --- | --- |
| NFR1 | Reproducibility | A headless run must be byte-identical for a given seed | Per-component random streams; automated test |
| NFR2 | Resource use | Run on a 16 GB laptop alongside other software | One shared simulation process; container memory limits; bounded queues |
| NFR3 | Robustness | Database or broker outages must not stop the twin | Bounded write queue that drops and counts; MQTT reconnection |
| NFR4 | Safety | ML output must never reach an actuator without authorisation | Single authorisation path; device-side limit check |
| NFR5 | Integrity | One manipulated sensor must not drive a machine action | Median voting at the edge; integrity quarantine centrally |
| NFR6 | Honesty | Results must be reported as simulated, with failures included | Results documents, this report |
| NFR7 | Maintainability | Modular boundaries; typed, linted, tested code | Ruff, mypy, ESLint, TypeScript; 101 automated tests |
| NFR8 | Usability | Status shown with shape and label, not colour alone; dark and light themes | Dashboard design |
| NFR9 | Exposure | Development services reachable only from the local machine | Ports published on 127.0.0.1 |

## 3.8 Feasibility Analysis

**Technical feasibility.** All components use mature open-source software: Python with SimPy, NumPy, pandas and scikit-learn [@simpy; @harris2020; @pedregosa2011]; FastAPI [@fastapi]; PostgreSQL [@postgres]; Eclipse Mosquitto [@light2017]; and Next.js with React Three Fiber [@nextjs; @r3f]. The environment audit in `docs/environment-audit.md` confirmed that the development laptop had the required tools or could install them without administrator rights.

**Economic feasibility.** The project used no paid hardware or software. All dependencies are open source, and the only cost was developer time and an existing laptop.

**Operational feasibility.** The system starts with one script on Windows (`scripts/dev.ps1`) after a one-time setup, and runs within the memory available on a 16 GB laptop. The same code runs headless for experiments.

**Schedule feasibility.** The work was organised into incremental phases (environment audit, foundation, simulation, communication, twin, AI, fault scenarios, dashboard, testing and publication), each producing a working milestone.

## 3.9 Project Scope and Constraints

The following constraints bound the results:

- **Simulation only.** No physical hardware was used, and no result is a real-world measurement.
- **Simplified physics.** Models are lumped-parameter approximations, not calibrated against specific machines (Chapter 5).
- **Synthetic labels.** Fault classes are clean and separable by construction, which inflates classifier accuracy (Chapter 7).
- **Local deployment.** The broker and API have no authentication or transport encryption and must stay on the local machine (Section 8.10 and Chapter 12).
- **Scale.** The full stack was exercised at 100 devices. The layout scales to 500 devices, but only the engine was benchmarked at that size.
- **Not implemented.** OPC UA, remaining useful life prediction, economic cost modelling and automated frontend tests are outside the delivered scope.
