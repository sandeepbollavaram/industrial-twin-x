# Edge Computing, Cybersecurity and Fault Recovery

## 8.1 Edge Computing Architecture

In Industrial Twin-X, the gateway is more than a relay. Each of the five simulated gateways runs an `EdgePolicy` (`modules/edge_computing/policy.py`) inside the simulator process, next to the machines it serves. The policy sees the same readings the gateway forwards, but it does not depend on the broker, the API or the database. This placement follows the edge-computing argument that processing near the data source can mask outages of central services [@satya2017; @shi2016].

The edge policy is deliberately simple and deterministic. It uses fixed limits and has no learned components. Its purpose is protection, the last line of defence for a machine, not optimisation. Because no ML output enters this path, a misbehaving model cannot cause an edge action.

## 8.2 Central Service Disconnection

The `central_disconnection` scenario takes the uplink of all five gateways down at once, while the gateway processes keep running. During the outage:

- central services receive no telemetry, alerts or command acknowledgements;
- commands from central services are rejected at the gateway as "unreachable";
- every gateway buffers its outgoing messages, up to 20,000;
- every gateway's edge policy continues to evaluate its machines.

This differs from `gateway_outage`, in which the gateway process itself fails: its messages are lost and its edge policy stops. Comparing the two shows why protection logic must run where it can survive the failure it guards against.

## 8.3 Autonomous Local Protection

Every 5 simulated seconds, for each rotating machine whose gateway process is up, the policy evaluates the rules in @tab:edgerules in order.

Table: Edge protection rules {#tab:edgerules}

| Order | Condition (median of at least 2 sensors) | Action | Severity |
| --- | --- | --- | --- |
| 1 | Machine already tripped | None | Not applicable |
| 2 | Winding ≥ 130 °C, or vibration ≥ 9.0 mm/s (≥ 5.0 mm/s if already derated) | Stop | Critical |
| 3 | Not yet derated, and winding ≥ 105 °C or vibration ≥ 7.1 mm/s | Set speed to 0.6 | Warning |
| 4 | Otherwise | None | Not applicable |

Two design details matter. First, the trip limit for vibration falls from 9.0 to 5.0 mm/s once a machine has been derated, because vibration grows with speed. At 60% speed, a badly worn bearing never reaches 9.0 mm/s, and without the lower limit it would run on to seizure. This was found during development: an earlier version derated a worn motor but let it fail. Second, each machine is derated and tripped at most once, until a repair or restart clears the policy's memory, so the edge does not oscillate.

The limit values are model parameters chosen to sit between normal operation and simulated failure in this simulation. They are not taken from a machine standard.

## 8.4 Local Decision-Making

The edge policy decides from local evidence alone. For each signal, it collects the most recent reading from each of the machine's devices and takes the median. A signal is considered only if at least two sensors report it. With four or five redundant sensors per signal, a single manipulated or faulty sensor cannot move the median far enough to trigger or suppress an action. The sensor-manipulation experiments confirm this: a bias ramping to +60 °C on one winding-temperature sensor caused no edge action in any of five runs (Section 11.7).

When the edge acts, it applies the command to the machine through the same `apply_command` path, including the device-side limits. It records the action and submits an alert to the gateway. If the uplink is down, the alert waits in the buffer, and central services learn of the action when the link returns. Central services then record it as an incident that is already mitigating, with the edge as the actor (Section 8.12).

## 8.5 Telemetry Buffering

Each gateway buffers outbound messages in a bounded FIFO queue of 20,000 messages while its uplink is down. The busiest gateway, GW-B1, serves 30 devices and produces 6 telemetry messages per simulated second, so the buffer holds about 55 minutes of its traffic. When the buffer is full, the oldest message is dropped and counted as `lost_overflow`. No overflow occurred in any experiment. The longest outage tested, 2,800 seconds of central disconnection, produced a peak backlog of 16,776 messages, below the limit.

## 8.6 Store-and-Forward

When the uplink returns, each gateway flushes up to 60 buffered messages per simulated second, in their original order, marking them as replayed (Section 6.11). Replayed messages update the twin's counters and are persisted, but they skip live analytics and cannot overwrite newer state, because the twin applies its ordering rules. Under a 900-second link loss on one gateway, all messages were eventually delivered: the delivery ratio was 1.000 in all five runs.

## 8.7 Sensor Integrity Monitoring

The `IntegrityMonitor` (`modules/cybersecurity/integrity.py`) runs centrally on every accepted, non-replayed reading (@fig:integrity). It applies two checks:

- **Frozen value.** For speed, flow, temperature, vibration and pressure signals, a sensor that repeats exactly the same value for 12 consecutive samples while its machine is running is flagged as `sensor_frozen`. Real sensor noise makes 12 identical readings practically impossible at the configured resolutions. Readings of exactly zero, and readings from stopped machines, are exempt, because a stopped machine's sensors can legitimately sit at zero.
- **Peer disagreement.** For slow-changing signals (winding, bearing, fluid and transformer temperature, vibration and pressure), each reading is compared with the median of the latest readings from the *other* sensors on the same machine and signal, provided there are at least three peers. A sensor whose deviation exceeds the tolerance in @tab:tolerance for six consecutive samples is flagged as `sensor_disagreement`.


Table: Peer-disagreement tolerances {#tab:tolerance}

| Signal | Tolerance |
| --- | --- |
| Winding temperature, bearing temperature | 4.0 °C |
| Fluid temperature | 2.0 °C |
| Transformer temperature | 3.0 °C |
| Vibration | 0.6 mm/s |
| Pressure | 0.3 bar |

Fast-changing signals such as current and power are excluded from the disagreement check. Devices report at different offsets within the 5-second cycle, and on the robot cell, whose load swings over a 60-second cycle, readings a few seconds apart can legitimately differ by a quarter or more.

## 8.8 Tampering Detection

When either check fires, the monitor:

1. adds the sensor to the quarantine set;
2. raises a critical alert describing the evidence, for example "value 71.42 differs from peer median 61.92 by more than 4.0 for 6 samples";
3. excludes the sensor's readings from all later feature windows.

Quarantine is automatic because it is a data action, not an actuator action: it changes what the analytics trust, not what any machine does. It is cleared only when maintenance is recorded for the machine.

**Limits of the method.** The checks assume that most sensors on a signal are honest. They do not detect:

- coordinated manipulation of a majority of a signal's sensors;
- a slow bias that stays within the tolerance (below 4 °C on a temperature);
- manipulation of a fast signal that is excluded from the disagreement check;
- forged messages that impersonate a device with plausible values, since messages are not authenticated.

Detection that also compares readings with a model of the physical process would address some of these. Detection and response for attacks on process control systems is studied in the literature [@cardenas2011], and process-aware detection is listed as future work. The attacks themselves are simulator state changes inside a local software simulation. No network traffic is attacked, and no real system is involved.

## 8.9 Device Isolation

A device can be isolated with the `isolate` command, which makes the gateway stop forwarding its telemetry; `release` reverses it. The twin marks isolated devices, and the security page lists them. Isolation is classed as a high-impact command (Section 8.11), so it always requires a named operator. In the current version, a quarantine finding does not automatically propose isolation; the operator decides.

## 8.10 Safety Constraints

Three independent layers constrain actuator commands:

1. **Edge voting.** Edge actions require at least two concurring sensors (Section 8.4).
2. **Central authorisation.** Every command from the recovery engine or an operator passes `authorize()` (Section 8.11).
3. **Device-side limits.** The simulated device itself rejects unknown commands and speed settings outside 0.3 to 1.0, or non-finite values, regardless of the sender (Section 5.7).

The third layer means that even a bug in the authorisation code cannot drive a machine outside its limits.

**Deployment security is not production grade.** The Mosquitto broker allows anonymous connections without TLS, and the REST API has no authentication. Any process on the local machine could publish forged telemetry or commands, or call the approval endpoints. The "approver" in the recovery workflow is a typed name: it demonstrates the approval *policy* but does not prove the operator's *identity*. CORS restricts which web origins a browser allows, but it is not an access control. These risks are contained only by binding every service to 127.0.0.1. The current deployment must not be exposed on a network. Production use would need broker authentication and TLS, API authentication with role-based authorisation, and message signing, following guidance such as NIST SP 800-82 and ISA/IEC 62443 [@nist80082; @isa62443].

## 8.11 Human Approval

The authorisation policy (`modules/recovery_engine/authorization.py`) classifies each command by impact and decides as follows:

1. If the command violates a device limit, it is **denied** for everyone, including a human approver.
2. If a named approver is present, it is **allowed**: the human, not the model, owns the decision.
3. If the command is high impact, it **needs approval**.
4. If the model's confidence is missing or below 0.8, it **needs approval**.
5. Otherwise it is **allowed** automatically.

Only `set_speed` to 0.5 or more of rated speed is classed as low impact. Stop, start, repair, isolate, release and deeper speed cuts are high impact. Commands issued manually from the dashboard carry no model confidence, so even low-impact operator commands need a named approver. @tab:authz summarises the outcomes, each of which an automated test covers.

Table: Authorisation outcomes {#tab:authz}

| Command | Confidence | Approver | Decision |
| --- | --- | --- | --- |
| `set_speed 0.6` | 0.95 | None | Allowed automatically |
| `set_speed 0.6` | 0.5 | None | Needs approval |
| `set_speed 0.6` | None (operator) | None | Needs approval |
| `set_speed 0.35` | 0.99 | None | Needs approval (high impact) |
| `stop`, `repair`, `isolate` | 1.0 | None | Needs approval (high impact) |
| `set_speed 5.0` | Any | Named | Denied (device limit) |
| Any valid command | Any | Named | Allowed |

This implements the rule that a low-confidence ML prediction must never trigger an unsafe action directly. During live verification, the system opened a second overheating incident on a motor that was already derated, with a classifier confidence of 0.34. The incident correctly waited for approval instead of acting.

## 8.12 Fault Recovery Workflow

The `IncidentManager` (`modules/recovery_engine/manager.py`) keeps at most one open incident per machine and moves it through the states of @fig:recovery according to an explicit transition table; any other transition raises an error.


1. **Detection and diagnosis.** When the pipeline sees two consecutive anomalous windows and the classifier names a fault, the incident opens in `detected` and moves to `diagnosed`.
2. **Playbook.** A table maps faults to actions: bearing wear and overheating map to `set_speed 0.6`, and a pump leak maps to `stop`. A fault without a playbook entry escalates.
3. **Authorisation.** If `authorize()` allows the action, the engine sends it and moves to `mitigating`. Otherwise the incident waits in `awaiting_approval` until an operator approves or rejects it.
4. **Edge path.** If an edge alert arrives first, the incident is opened (or updated) directly in `mitigating`, with the edge as the actor and fault label `edge_protection`.
5. **Verification.** Thirty seconds after mitigation the incident moves to `verifying`. At 300 seconds, a verifier checks the twin's reported state. For overheating it requires winding temperature below 100 °C; for bearing wear, vibration below 7.1 mm/s; for a leak, pump speed below 100 rpm, meaning the pump is stopped; and for edge protection, both temperature and vibration below those limits. If the check passes, the incident moves to `recovered`; otherwise it moves to `escalated`.
6. **Maintenance.** An operator can record maintenance from any open state. This sends the high-impact `repair` command and closes the incident as `recovered`. Where the transition table has no direct path to `recovered`, the code routes the incident through `escalated` first.

A limitation of the current design: "recovered" means the verification condition held after mitigation, not that the underlying fault was repaired. A derated motor with a still-degraded cooling system passes the overheating verifier once its temperature falls. The fault remains, and only maintenance removes it.

## 8.13 Audit Trail

Every incident event (opening, each state transition, and each command sent by an operator or the edge) is appended to the incident's audit list. The same event is written to the `recovery_audit` table with the incident ID, machine, fault, simulation time, event type, actor, detail and resulting state. Actors are recorded as `ai`, `edge`, `recovery-engine` or the operator's typed name. The dashboard's Recovery Operations page shows each incident's audit trail.

The audit table is append-only by convention: the application only ever inserts into it. Neither database permissions nor hash chaining enforce this, so a user with database access could alter it. Incident state itself lives in memory and is not restored after an API restart; its history survives in the audit table.
