# Industrial Communication and Digital Twin

## 6.1 Industrial Communication Requirements

The communication layer of Industrial Twin-X must:

1. carry periodic telemetry from 100 devices at a combined 20 messages per simulated second, and at a multiple of that in accelerated runs;
2. carry less frequent but more important messages (commands, command acknowledgements, alerts) with stronger delivery guarantees;
3. decouple producers from consumers, so the simulator and the API can start, stop and reconnect independently;
4. tolerate loss, delay, duplication and reordering without corrupting the twin;
5. make every message self-describing and versioned so it can be validated at the boundary.

## 6.2 MQTT Protocol

MQTT is a publish/subscribe protocol in which clients exchange messages through a broker. Clients publish to hierarchical *topics* and subscribe to topic filters, in which `+` matches exactly one topic level and `#` matches any number of levels [@mqtt311]. MQTT 3.1.1 defines three delivery guarantees: QoS 0, "at most once", where message loss can occur; QoS 1, "at least once", where duplicates can occur; and QoS 2, "exactly once" [@mqtt311]. A keep-alive interval lets the broker detect silent clients, and a Last Will message lets it announce an unexpected disconnection [@mqtt311]. The protocol suits constrained devices and low-bandwidth networks [@mqtt5; @hunkeler2008].

## 6.3 MQTT Broker Architecture

The broker is Eclipse Mosquitto 2.0 [@light2017], run as a container from the official image with a mounted configuration file (`infrastructure/mqtt/mosquitto.conf`). The configuration disables persistence, limits each client's queued messages to 5,000 and in-flight messages to 200, and logs only errors and warnings. Docker Compose publishes port 1883 on 127.0.0.1 only, so other machines cannot reach the broker. Anonymous access is enabled; this is acceptable only because of the localhost binding, and Section 8.10 discusses it further. Both Python processes use the Eclipse Paho client, which speaks MQTT 3.1.1 by default and runs its network loop in a background thread [@paho].

## 6.4 Topic Structure

@tab:topics lists the topics. All share the root `industrial-twin-x/factory/{factory_id}`.

Table: MQTT topics, publishers and QoS {#tab:topics}

| Topic (under the root) | Publisher | Subscriber | QoS | Content |
| --- | --- | --- | --- | --- |
| `zone/{zone}/device/{device}/telemetry` | Simulator | API | 0 | Readings from one device |
| `device/{device}/status` | Simulator | API | 1 | Command acknowledgement and machine status |
| `device/{device}/commands` | API | Simulator | 1 | Actuator command |
| `alerts` | Simulator | API | 1 | Edge actions and other alerts |
| `network` | Simulator | API | 0 | Gateway statistics every 5 s |
| `control` | API | Simulator | 1 | Pause, resume, speed, reset, scenario |

Putting the zone and device in the telemetry topic lets a consumer subscribe to one zone (`zone/A/device/+/telemetry`) or one device without parsing payloads. The API subscribes to all of them with `zone/+/device/+/telemetry`.

## 6.5 Message Publishing and Subscription

Each device publishes one JSON message every 5 simulated seconds containing its three readings. The telemetry schema, version 1.0, is defined with Pydantic in `modules/telemetry/schema.py` (@tab:schema). The model forbids unknown fields, rejects NaN and infinite values, and requires at least one reading.

Table: Telemetry message schema, version 1.0 {#tab:schema}

| Field | Type | Constraint | Purpose |
| --- | --- | --- | --- |
| `schema_version` | string | must equal "1.0" | Versioning |
| `factory_id`, `zone_id`, `machine_id`, `gateway_id`, `device_id` | string | required | Identity and routing |
| `timestamp` | float | finite, > 0 | Unix seconds at the source |
| `sim_time` | float | finite, ≥ 0 | Simulation clock |
| `sequence` | integer | ≥ 0 | Per-device ordering and gap detection |
| `scenario_id` | string | required | Active scenario label |
| `status` | string | required | Machine status (running, stopped, failed) |
| `readings` | map of string to float | finite, at least one entry | Sensor values |
| `replayed` | boolean | default false | Set when sent from a backlog |

Telemetry uses QoS 0. At this rate, the overhead of acknowledging every message under QoS 1 is not justified for data that is superseded 5 seconds later, and the sequence numbers detect any loss. Commands, status and alerts use QoS 1, because a lost command or a lost edge alert has lasting consequences, and duplicates are harmless: commands carry identifiers, and alerts are idempotent records. QoS 2 is not used.

The simulator subscribes to `device/+/commands` and `control`. Inbound messages are placed on a bounded queue of 1,000 by the Paho thread and executed by the main loop *between* engine steps, so a command never interleaves with a physics update.

## 6.6 Telemetry Processing

For every telemetry message, the central pipeline performs the following steps in order:

1. parse the JSON, counting a failure as an invalid message;
2. validate against the schema, counting a failure as invalid;
3. apply the twin's ordering rules (Section 6.8), which may drop the message;
4. publish the message to observers, which update the dashboard history and enqueue a database row;
5. if the message is not replayed: detect a simulator reset, update the latest simulation time, run the integrity checks, add non-quarantined readings to the machine's feature window, and possibly run an assessment;
6. advance time-based incident states.

Replayed messages are persisted and update counters, but they skip the live analytics in step 5, because their time has already passed.

## 6.7 Digital Twin Registry

The registry is built from the factory specification when the API starts: one `DeviceTwin` per device, keyed by device ID and holding the machine, zone, gateway and role. The same registry is written to the `devices` table at startup, ignoring rows that already exist. A message for a device that is not in the registry is rejected and counted. This prevents arbitrary publishers from creating new twins, although, as Section 8.10 notes, it does not stop a local publisher from impersonating a registered device.

## 6.8 State Synchronization

Each twin holds *reported* readings from the device and *desired* values set by commands, following the shadow model [@awsshadow]. A `set_speed` command, for example, sets the desired `speed_fraction`, and the *delta* lists desired values not yet matched by reported values. @fig:twinsync shows the ordering rules, and @tab:twinrules states them with their rationale.

Table: Twin ordering rules {#tab:twinrules}

| Condition | Action | Rationale |
| --- | --- | --- |
| Unknown device | Reject, count | Only registered devices have twins |
| Sequence 0 after a higher sequence | Clear readings and counters | The simulator was reset; old state belongs to another run |
| Same sequence as last | Ignore as duplicate | Possible under QoS 1 or replay |
| Lower sequence than last | Persist only; count as out of order | Late or replayed data must not overwrite newer state |
| Sequence jump | Count the gap, then apply | Measures loss without blocking progress |
| Next sequence | Apply | Normal case |

All twin operations hold a re-entrant lock, because the MQTT thread writes while API request threads read. Twin state is upserted to the `twin_state` table every 5 seconds, which provides a durable copy for inspection, though the live twin is rebuilt from telemetry after a restart.

The counter reset was added after an issue observed during post-publication verification. Before the fix, a simulator reset cleared the readings but left the gap and received counters from the previous run, so the network page reported misleading totals. The fix resets the counters with the readings, and a regression test (`test_twin_counters_restart_with_the_simulator`) covers it. At the time of writing, this fix is in the working tree but not yet committed (Section 10.10).

## 6.9 Persistence and Historical Data

The `BatchWriter` thread drains a bounded queue of 20,000 rows every second, in batches of up to 500, and inserts each batch in a single transaction. When the queue is full, or a batch fails because the database is unavailable, rows are dropped and counted rather than blocking ingestion. The overview page shows the dropped count and the mean batch write time. The twin's live behaviour therefore never depends on the database. The cost is that persisted history can have holes during a database outage, and the system reports them rather than hiding them.

Telemetry is stored with its source timestamp, simulation time, sequence number, scenario and the readings as JSONB. There is no retention policy: at 200 messages per wall second, the table grows quickly in long sessions, as `docs/architecture/database-design.md` notes.

## 6.10 Communication Failure Handling

The system distinguishes four classes of communication failure:

- **Gateway process failure** (`gateway_outage`). The gateway accepts no messages, so they are lost and counted as `lost_outage`. Its edge policy also stops, because it runs on the gateway.
- **Uplink failure** (`central_disconnection`, `telemetry_backlog`). The gateway keeps running its edge policy and buffers outgoing messages, up to 20,000. Overflow drops the oldest message and counts it.
- **Degraded link** (`network_degradation`). Messages incur extra latency and are dropped with a set probability, counted as `lost_network`.
- **Broker disconnection.** Both Paho clients reconnect automatically with exponential backoff between 1 and 15 seconds [@paho], and the API counts reconnections.

A command that arrives while a gateway's uplink is down is rejected by the simulator with the detail "unreachable" and recorded in the simulator's command log. The status message reporting the rejection is buffered like any other outbound message and reaches central services when the uplink returns. Until then, the command shows as issued but unacknowledged, never as applied.

During live verification at a speed setting of 50×, the API accepted 212,300 telemetry messages, the simulated gateways reported 212,401 delivered, and the twins recorded 80 sequence gaps, with no broker reconnections. The likeliest cause is QoS 0 delivery under high load between the simulator, the broker and the API. Some messages were also still in flight at the moment of measurement. This is a single observation (about 0.04% loss), not a controlled experiment, and the root cause was not investigated further.

## 6.11 Store-and-Forward Mechanism

When a gateway's uplink fails, `VirtualGateway.submit` appends each new message to a bounded FIFO buffer instead of transmitting it. While the buffer is non-empty, new messages are also appended to it, even after the link returns. This preserves per-device ordering. When the link returns, each one-second tick flushes up to 60 buffered messages, marks them as replayed, and transmits them through the same loss and latency model as live traffic. The flush rate is deliberately bounded, so that reconnection does not flood the broker.

The `telemetry_backlog` scenario and the automated test `test_link_loss_buffers_and_flushes_without_loss` verify this behaviour. After a 300-second link loss and recovery, every device's sequence numbers arrive as a complete, gap-free series, and the buffer drains to zero. In the experiments (Section 11.8), a 900-second link loss on one gateway gave a delivery ratio of 1.000, with a peak backlog of 3,584 messages.
