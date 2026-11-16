# System Architecture and Design

## 4.1 Overall Architecture

Industrial Twin-X is a modular monolith built as two independent processes that communicate only through an MQTT broker (@fig:arch). The **simulator process** runs the virtual factory, the gateway network model and the edge policies. The **API process** runs the central pipeline (validation, digital twin, integrity checks, analytics and recovery), persists data to PostgreSQL, and serves a REST and WebSocket interface to the dashboard. PostgreSQL and Mosquitto run as containers under Docker Compose; the two Python processes and the Next.js dashboard run directly on the host.

![Overall architecture of Industrial Twin-X. Arrows show the direction of data flow; all components run on one development machine.](diagrams/png/01-overall-architecture.png){#fig:arch}

The split into two processes mirrors the separation between plant-floor equipment and central IT in a real deployment. The simulator knows nothing about the database or the analytics, and the API knows nothing about the simulator's internals: it sees only the messages that a real gateway would send. This boundary also lets the same central code run without a broker in experiments (Section 4.2).

## 4.2 Architectural Design Principles

The design follows these principles, recorded as architecture decision records in `docs/design-decisions/README.md`:

1. **Devices are data, not processes.** One SimPy process advances all 100 devices. No device has its own container or thread. This keeps resource use low and makes runs deterministic (ADR-003).
2. **Central logic is independent of transport.** `CentralPipeline` accepts plain dictionaries. Live mode feeds it from MQTT; experiments and tests feed it directly from the simulator. Experiments therefore exercise the same logic, though they do not measure broker latency (ADR-004).
3. **No hidden truth in telemetry.** Hidden simulator state, such as wear or leak fraction, is used only to label data and evaluate results. It is never published or used as a feature.
4. **Defence in depth for actuation.** Edge limits use median voting, the central path passes an authorisation policy, and the simulated device checks its own limits regardless of who sent the command.
5. **Bounded everything.** Gateway buffers, the database write queue, the MQTT client queue and the dashboard history all have fixed limits. Overflow is counted rather than allowed to exhaust memory.
6. **No unnecessary infrastructure.** Redis, Kafka and Kubernetes are not used; a bounded in-process queue meets the measured load on one node (ADR-002).

## 4.3 System Components

@fig:components shows the Python packages and their dependencies. @tab:components summarises their responsibilities.

![Component diagram of the Python packages. Arrows point from a component to the components it depends on.](diagrams/png/02-component-diagram.png){#fig:components}

Table: Main components and responsibilities {#tab:components}

| Component | Path | Responsibility |
| --- | --- | --- |
| Factory layout | `simulation/factory` | Zones, gateways, machines, devices and sensors; scaling to 500 devices |
| Machine models | `simulation/devices` | Lumped physical models of all assets |
| Sensors | `simulation/sensors` | Measurement error and contained tampering |
| Actuator limits | `simulation/actuators` | Device-side command validation |
| Network | `simulation/network` | Gateway uplink: outage, latency, loss, buffering |
| Scenarios | `simulation/scenarios` | Scripted fault and attack events |
| Engine | `simulation/engine` | Shared SimPy engine, independent of MQTT |
| Live runner | `simulation/run.py` | Paces the engine against wall time and bridges it to MQTT |
| Telemetry | `modules/telemetry` | Topics, schemas and the central pipeline |
| Digital twin | `modules/digital_twin` | Reported and desired state |
| Anomaly detection | `modules/anomaly_detection` | Window features and detectors |
| Fault diagnosis | `modules/fault_diagnosis` | Random forest and rule baseline |
| Predictive maintenance | `modules/predictive_maintenance` | Degradation, risk score, recommendation |
| Edge computing | `modules/edge_computing` | Gateway-local protection policy |
| Cybersecurity | `modules/cybersecurity` | Sensor integrity checks |
| Recovery engine | `modules/recovery_engine` | Incident state machine and authorisation |
| API | `apps/api/twinx_api` | FastAPI routes, MQTT bridge, persistence |
| Dashboard | `apps/web` | Next.js command centre and 3D view |
| Research | `research` | Dataset generation, training, experiments, metrics |

## 4.4 Virtual Factory Architecture

The factory has three zones, each served by one or two gateways (@fig:factory). Zone A (manufacturing) contains two drive motors, a conveyor and a robot cell. Zone B (fluid systems) contains two feed pumps and a process water tank. Zone C (power and environment) contains two power distribution units and an environmental station. Physical couplings link the zones: the pumps fill the tank, each distribution unit carries the electrical load of one zone's machines, and the ambient temperature model affects every machine's cooling.

![Virtual factory layout: zones, gateways, machines and physical couplings. Dashed lines show electrical load carried by the distribution units.](diagrams/png/03-virtual-factory.png){#fig:factory}

The layout is defined as data by `build_factory(scale)`. At scale 1 it produces 3 zones, 5 gateways, 10 machines, 100 devices and 300 sensors. At scale 5 it repeats the template to produce 500 devices on 25 gateways, which an automated test checks.

## 4.5 Virtual Device Architecture

Each machine has ten devices with fixed roles: controller, drive, meter, six sensor nodes and a monitor. Each device carries three sensors. The assignment of signals to devices rotates through the machine's signal list, so every signal is measured by several sensors on different devices. For a rotating machine with seven signals, each signal has about four redundant sensors. This redundancy is deliberate. It lets the edge policy vote on the median and lets the integrity monitor compare each sensor with its peers. A device is a plain data record (`DeviceSpec`); its behaviour comes from the engine, which reads the device's sensors and publishes one message containing its three readings.

## 4.6 Sensor and Actuator Architecture

A sensor converts a true physical value into a reading with calibration gain and offset error, Gaussian noise, clipping to the instrument range and quantisation to the instrument resolution (Section 5.6). Each sensor has its own random stream, so readings stay reproducible. The sensor model also holds the contained attack state used by the manipulation scenarios: a ramped bias, or a frozen value.

Actuation is represented by commands on a machine: `set_speed`, `start`, `stop` and `repair`, plus `isolate` and `release`, which act on a device's telemetry. The function `validate_command` enforces hard limits on the device side: only known commands are accepted, and `set_speed` must be a finite value between 0.3 and 1.0 of rated speed. It runs inside the simulated machine, so even a command that passes central authorisation in error is rejected if it violates a device limit.

## 4.7 Communication Architecture

Telemetry, status, alerts and network reports flow from the simulator to the API through Mosquitto. Commands and simulation control flow in the other direction (@fig:mqttseq). Each message is JSON with a schema version. Section 6.4 lists the topic structure.

![MQTT publish/subscribe sequence for telemetry and an operator-approved command.](diagrams/png/05-mqtt-sequence.png){#fig:mqttseq}

The gateway is modelled inside the simulator, upstream of the broker. When a gateway's process is down, its messages are lost. When only its uplink is down, its messages are buffered and later replayed at a bounded rate (@fig:dataflow). This separation lets the project distinguish a gateway failure from a central-service disconnection, which have different consequences for edge protection.

![End-to-end data flow from virtual sensor to persistence and dashboard.](diagrams/png/04-iiot-data-flow.png){#fig:dataflow}

## 4.8 Digital Twin State Management

The twin engine keeps one record per registered device, holding the reported readings, the desired values, the status, the last sequence number and message accounting counters (received, gaps, duplicates and out-of-order). @fig:twinsync shows the rules applied to each validated message. Unknown devices are rejected. A sequence number of zero after a higher number signals a simulator reset and clears the record. Duplicates are ignored. Older messages, such as replayed backlog, are persisted but do not overwrite newer state. Sequence jumps add to the gap count. The *delta* is the set of desired values not yet matched by reported values, following the device-shadow model [@awsshadow].

![Digital twin synchronisation rules for each validated telemetry message.](diagrams/png/06-twin-synchronization.png){#fig:twinsync}

## 4.9 Backend Architecture

The backend is a FastAPI application [@fastapi]. A `Runtime` object owns the long-lived services: the MQTT client, the `CentralPipeline`, a batch writer thread for PostgreSQL and a twin-synchronisation thread. The MQTT client's network loop runs in its own thread [@paho] and passes every message to the pipeline, which serialises processing with a lock. REST endpoints read pipeline state under that lock, and a WebSocket endpoint pushes an overview snapshot every second. Appendix C lists the endpoints.

## 4.10 Database Architecture

PostgreSQL stores five tables: `devices`, `telemetry`, `twin_state`, `events` and `recovery_audit` (@fig:er). Telemetry readings are stored as JSONB because different devices carry different signals. An index on `(machine_id, sim_time)` supports per-machine time queries. Rows are written in batches of up to 500 each second from a bounded queue of 20,000 rows. Twin state is upserted every 5 seconds. The relationships in @fig:er are logical: the schema does not declare foreign keys, so the database does not enforce them.

![Entity-relationship diagram of the database. Relationships are logical and are not enforced by foreign keys.](diagrams/png/11-er-diagram.png){#fig:er}

## 4.11 AI Integration

Analytics run inside the central pipeline. For each rotating machine, accepted, non-replayed readings from non-quarantined sensors enter a 120-second window that is evaluated every 30 simulated seconds (@fig:aipipe). The window is reduced to 31 features. A statistical detector produces an anomaly score; a random forest names the fault and gives a confidence; a gradient-boosting regressor estimates degradation; and a calibrated forest produces a short-horizon risk score. An incident opens only when the anomaly score exceeds its limit for two consecutive windows *and* the classifier names a fault. If no trained model bundle is present, the pipeline falls back to hand-written rules and the dashboard says so.

![Analytics pipeline from accepted telemetry to incident and maintenance recommendation.](diagrams/png/07-ai-pipeline.png){#fig:aipipe}

## 4.12 Edge Computing Architecture

Each gateway runs an `EdgePolicy` inside the simulator (@fig:edge). Every 5 simulated seconds, for each rotating machine whose gateway process is up, the policy computes the median of the latest reading from each device for every signal. It acts only on a signal measured by at least two sensors. It derates the machine to 60% speed when the winding temperature reaches 105 °C or vibration reaches 7.1 mm/s, and stops it at 130 °C, or at 9.0 mm/s (5.0 mm/s once derated). The edge acts locally and reports its action as an alert through the gateway, so the alert is buffered if central services are unreachable. No ML output enters this path.

![Edge autonomy workflow on each gateway.](diagrams/png/08-edge-autonomy.png){#fig:edge}

## 4.13 Fault Recovery Architecture

The recovery engine models each incident as a finite state machine with eight states and an explicit table of allowed transitions (@fig:recovery). Every transition is recorded in the incident's audit trail and written to the `recovery_audit` table. On opening an incident, the engine looks up a playbook action for the diagnosed fault and asks the authorisation policy whether it may execute automatically. If not, the incident waits for a named operator. After mitigation, the incident enters verification, and a fault-specific verifier based on the twin's reported state decides whether it has recovered or must escalate.

![Incident state machine of the recovery engine.](diagrams/png/10-recovery-states.png){#fig:recovery}

## 4.14 Cybersecurity Architecture

Security in this prototype has four layers. **Boundary validation** rejects malformed messages, non-finite values and unknown devices. **Integrity monitoring** quarantines sensors that disagree with their peers or repeat values implausibly (@fig:integrity). **Decision safety** combines median voting at the edge, the authorisation policy centrally and limits on the device. **Exposure control** publishes all services on 127.0.0.1 only and keeps secrets out of the repository. Authentication and transport encryption are **not** implemented; Section 8.10 and Chapter 12 discuss this gap.

![Sensor integrity workflow applied to each reading.](diagrams/png/09-integrity-workflow.png){#fig:integrity}

## 4.15 Frontend and Visualization Architecture

The dashboard is a Next.js application with React client components [@nextjs]. A shared provider opens a WebSocket to the API and receives an overview snapshot every second; pages that need more detail poll REST endpoints every two or three seconds. The 3D factory view uses React Three Fiber [@r3f] to draw zones and machines, colouring machines by state and labelling faulted or selected ones. The design uses a neutral palette without gradients, colour tokens for dark and light themes, and status indicators that pair colour with a shape and a word. Section 9.10 describes the twelve pages.

The deployment view in @fig:deploy shows where each part runs on the development machine.

![Deployment on the development machine. All ports are bound to 127.0.0.1.](diagrams/png/12-deployment.png){#fig:deploy}
