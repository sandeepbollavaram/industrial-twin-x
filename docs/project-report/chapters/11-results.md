# Experimental Results and Analysis

## 11.1 Experimental Objectives

The experiments ask six questions:

1. Does edge protection prevent failures when central services are unreachable?
2. How do edge and central protection compare when both are available?
3. Do the integrity checks detect single-sensor manipulation without causing machine actions or false quarantines?
4. How do outages, degraded links and long link losses affect message delivery?
5. What does protection cost in production output, as the simulation measures it?
6. How quickly are the faults detected when the full central pipeline runs?

All results are from software simulation. They describe how this software behaves against this simulation, not how a real plant would behave.

## 11.2 Experimental Environment

The experiments ran on the development laptop described in Section 9.1, with four worker processes in parallel. Each run executed the real `FactorySimulation` and, where a condition included central services, the real `CentralPipeline` with the trained model bundle (version `20261102T063522Z`). Messages were passed from the simulator to the pipeline in-process, without the MQTT broker or the database (ADR-004). Experiment latencies are therefore those of the simulated network model, and database write performance was not measured in these runs. @fig:exppipe shows how data generation, training and experiments relate.

![Data generation, training and experiment pipeline. Training and experiment seeds do not overlap.](diagrams/png/13-experiment-pipeline.png){#fig:exppipe}

## 11.3 Simulation Configuration

@tab:conditions lists the fifteen conditions. Each was run for 3,600 simulated seconds at 100 devices. Fault scenarios used their default parameters (Section 5.11): severity 1.0 and onset at 600 seconds. Commands from central services were delivered back into the simulator in-process, subject to the same gateway reachability check as live commands.

Table: Experiment conditions {#tab:conditions}

| Condition | Scenario(s) | Edge | Central |
| --- | --- | --- | --- |
| `normal_control` | None | On | On |
| `overheat_edge_central` | Overheating on MTR-A02 | On | On |
| `overheat_central_only` | Overheating on MTR-A02 | Off | On |
| `overheat_edge_only` | Overheating on MTR-A02 | On | Off |
| `overheat_unprotected` | Overheating on MTR-A02 | Off | Off |
| `overheat_disconnect_edge` | Overheating, plus all uplinks down from 500 s for 2,800 s | On | On |
| `overheat_disconnect_no_edge` | As above | Off | On |
| `bearing_edge_central` | Bearing degradation on MTR-A01 | On | On |
| `bearing_unprotected` | Bearing degradation on MTR-A01 | Off | Off |
| `leak_edge_central` | Pump leak on PMP-B01 | On | On |
| `gateway_outage` | GW-A1 process down, 600 s to 900 s | On | On |
| `network_degradation` | GW-B1 +0.8 s latency, 10% loss, 600 s to 1,200 s | On | On |
| `telemetry_backlog` | GW-A1 uplink down, 600 s to 1,500 s | On | On |
| `sensor_bias` | Rising bias on MTR-A01-node-a winding temperature | On | On |
| `sensor_replay` | Frozen MTR-A01-node-a winding temperature | On | On |

In the two disconnection conditions, the uplinks go down at 500 s, before the overheating fault begins at 600 s. An earlier version of the experiment started the disconnection at 900 s. Central services then detected and derated the motor at about 840 s, before the disconnection, so the condition never tested edge autonomy. This flaw was found by inspecting the results, corrected, and the experiments were rerun. Only the corrected results are reported.

## 11.4 Random Seed Methodology

Every condition was run with the same five seeds, 5000 to 5004. Within a seed, all conditions therefore share identical machine parameters, sensor errors, load noise and ambient drift; only the scenario and the protection settings differ. This is a paired design: differences between conditions for one seed are caused by the conditions, not by different random draws. The experiment seeds are disjoint from the dataset-generation seeds (1000 to 1079), so the models are never evaluated on trajectories they were trained on. Results are reported as the mean and sample standard deviation across the five seeds.

Several metrics have a standard deviation of zero. This happens because the fault onset and severity are fixed, and because alarms fall on the 30-second evaluation grid. Only the seed varies, which **understates** the variability that varied severities and onsets would produce.

## 11.5 Fault Injection Experiments

@tab:resilience summarises the fault conditions. Downtime and failures refer to the faulted machine. Detection is measured from fault onset to the first sustained central alarm or edge action after onset. Recovery is measured from incident opening to the passing of the verification check.

Table: Resilience results (mean ± SD over 5 seeds; simulated seconds) {#tab:resilience}

| Condition | Machine failures | Downtime (s) | Detection (s) | Recovery (s) |
| --- | --- | --- | --- | --- |
| Overheating, edge and central | 0 / 5 | 0 | 270 ± 0 | 300 ± 0 |
| Overheating, central only | 0 / 5 | 0 | 270 ± 0 | 300 ± 0 |
| Overheating, edge only | 0 / 5 | 0 | not measured (no central) | not measured |
| Overheating, no protection | 5 / 5 | 691 ± 369 | not applicable | not applicable |
| Overheating, central disconnected, edge on | 0 / 5 | 0 | 883 ± 35 | 1,914 ± 35 |
| Overheating, central disconnected, edge off | 5 / 5 | 691 ± 369 | 2,990 ± 0 | not reached |
| Bearing wear, edge and central | 0 / 5 | 504 ± 462 | 324 ± 115 | 1,419 ± 1,022 |
| Bearing wear, no protection | 5 / 5 | 478 ± 123 | not applicable | not applicable |
| Pump leak, edge and central | 0 / 5 | 0 | 60 ± 0 | pending approval |

![Runs in which the overheating motor failed, by protection condition. Source: summary.json.](figures/fig-overheat-failures.png){#fig:failures}

Without any protection, the overheating motor failed in every run, and the bearing seized in every run. With central services available, central detection 270 seconds after onset led to an automatic derate (classifier confidence above 0.8, low-impact command). The motor never failed, and the incident passed verification 300 seconds later. In all five of these runs, a *second*, low-confidence overheating incident was later opened on the same derated motor and waited for approval. This is the operating-point sensitivity described in Section 7.12: the detector, trained at full speed, treats the derated motor as anomalous.

The pump leak was detected 60 seconds after onset in every run. The playbook action for a leak is `stop`, a high-impact command, so the incident waited for approval. No operator acts during experiments, so these incidents remained in `awaiting_approval`. This is the designed behaviour, and the leak conditions report no recovery time for that reason.

## 11.6 Edge Protection Experiment

The disconnection conditions isolate the value of edge autonomy. All five uplinks were down from 500 seconds, before the fault began, until 3,300 seconds. With edge protection, the motor failed in **0 of 5** runs; without it, in **5 of 5** runs (@fig:failures and @fig:downtime).

![Downtime of the faulted motor in one simulated hour, by condition. Source: summary.json.](figures/fig-overheat-downtime.png){#fig:downtime}

In the edge-on runs, the edge derated the motor when its median winding temperature reached 105 °C, about 883 seconds after onset. The edge alert was buffered at the gateway, and central services recorded it only after the uplink returned. The 883-second figure is therefore the time the *edge* acted, not the time central services learned of it. The incident then passed verification at about 1,914 seconds after opening. In the edge-off runs, central services could not see the fault until the uplink returned at 3,300 seconds. By then the motor had already failed; the "detection" at 2,990 seconds after onset reflects data arriving after the failure, not useful warning.

With central services connected, adding the edge made no difference in the overheating test: central services derated the motor before the temperature reached the edge's limit, so the "edge and central" and "central only" rows are identical. The edge's value appears only when central services are unavailable.

## 11.7 Sensor Tampering Experiment

Two contained attacks targeted one of the four winding-temperature sensors on MTR-A01 at 600 seconds: a bias ramping at 0.2 °C per second to +60 °C, and a replay that froze the sensor's value (@tab:tamper, @fig:tamper).

Table: Sensor manipulation results (5 seeds each) {#tab:tamper}

| Attack | Detected | Time to quarantine (s) | False quarantines | Machine actions caused | Healthy-machine incidents |
| --- | --- | --- | --- | --- | --- |
| Rising bias | 5 / 5 | 47 ± 2 | 0 | 0 | 0 |
| Frozen replay | 5 / 5 | 58 ± 0 | 0 | 0 | 0 |

![Time from attack start to quarantine of the manipulated sensor. Source: summary.json.](figures/fig-tamper.png){#fig:tamper}

Both attacks were detected in every run. The bias needed to exceed the 4 °C tolerance for six consecutive samples, which took about 47 seconds at the ramp rate used. The frozen value needed 12 identical samples, taking 58 seconds at one reading per 5 seconds. No other sensor was quarantined, and the machine was never derated or stopped. The edge took the median of four sensors and ignored the outlier, and central analytics excluded the sensor after quarantine. A slower bias, below the 4 °C tolerance, would not be detected; Section 8.8 lists this limitation.

## 11.8 Network Disconnection Experiment

@tab:iot and @fig:delivery show delivery under network faults, measured at the simulated gateways.

Table: Message delivery under network conditions (mean of 5 seeds) {#tab:iot}

| Condition | Delivery ratio | Mean latency (s) | Peak backlog (messages) |
| --- | --- | --- | --- |
| Normal operation | 1.000 | 0.03 | 0 |
| Gateway outage, 300 s | 0.983 | 0.03 | 0 |
| Network degradation, 10% loss, +0.8 s, 600 s | 0.995 | 0.07 | 0 |
| Uplink loss, 900 s (backlog scenario) | 1.000 | 0.03 | 3,584 |
| All uplinks down, 2,800 s (disconnection) | 0.991 | 0.03 | 16,776 |

![Message delivery ratio by network condition. Source: summary.json.](figures/fig-delivery.png){#fig:delivery}

A gateway *process* outage lost 1.7% of all messages, those of its devices during the outage, because a failed gateway cannot buffer. An uplink outage of 900 seconds lost nothing: the gateway buffered 3,584 messages and replayed them after recovery, for a delivery ratio of 1.000. In the long disconnection, the ratio was 0.991 only because some backlog was still being flushed when the hour ended. The degraded link lost about 10% of one gateway's messages for 10 minutes, consistent with the injected loss rate. Mean latency excludes replayed messages, which is why the long outages do not raise it.

## 11.9 AI Model Comparison

Chapter 7 reports the held-out comparison in full. In summary, on 24 held-out simulated runs the statistical baseline reached F1 0.969 and the Isolation Forest 0.677. The Isolation Forest missed all four overheating runs, and the hybrid of the two doubled the sustained false alarms. The resilience experiments used the baseline as the live detector. They also confirm that it works inside the full pipeline on new seeds: every overheating, bearing and leak run was detected. In the 15 conditions, no incident was ever opened on a healthy machine.

One caution on false alarms. In the leak condition, the detector raised on average 0.4 sustained alarms on the target pump *before* the fault began. The classifier did not name a fault, so these opened no incident, but they show that the baseline is not free of false alarms in practice.

## 11.10 Production Output Analysis

The simulation counts each rotating machine's output as its speed fraction integrated over time while it is running. @fig:output shows total factory output in one simulated hour.

![Total factory output in one simulated hour (mean of 5 seeds). The axis does not start at zero. Source: summary.json.](figures/fig-output.png){#fig:output}

The result is counter-intuitive and must be stated plainly. **Protected runs produced less output than unprotected runs**: about 20,512 units with central protection and about 20,756 with edge protection only, against 20,909 with no protection. The fault-free control produced 21,600. Derating the motor to 60% costs output immediately and for the rest of the hour. The unprotected motor runs at full speed until it fails late in the hour, and the hour ends before its downtime costs more than the derate does.

This **is not an economic result**. The simulation does not count the cost of a failed motor: repair, replacement parts, the lost hours or days after the window ends, or the safety consequences of a winding failure. In a real plant, a failed motor would usually cost far more than an hour of derated running. The comparison only shows that a one-hour output count, taken alone, is the wrong metric for judging protection.

## 11.11 Bearing Protection Analysis

Averaged over the five seeds, bearing protection did **not** reduce downtime: 504 ± 462 seconds with protection, against 478 ± 123 seconds without. Without protection, the bearing seized (wear reached 1.0) in every run. The per-run results, and a replay of seeds 5000 and 5001 that traced each incident's audit trail, show two distinct outcomes behind the protected average:

- **Confident diagnosis (seeds 5001 and 5004).** The classifier named bearing wear with confidence 0.94, so the derate to 60% was authorised automatically about 540 seconds after onset. Slower running slowed the wear (it ended the hour at about 0.35), and the motor had **no downtime**.
- **Low-confidence diagnosis (seeds 5000, 5002 and 5003).** The classifier named bearing wear with confidence 0.72 to 0.74, below the 0.8 threshold, so the incident waited for an operator, and none acts in an unattended experiment. The motor kept running at full speed until its vibration reached the edge's 7.1 mm/s derate limit, about 2,150 seconds after onset. The edge derated it, and 5 seconds later stopped it: at a wear of about 0.8, vibration at 60% speed was still about 6.2 mm/s, above the 5.0 mm/s trip limit for derated machines. The motor then stood stopped for roughly 800 to 900 seconds, but its bearing did not seize.

Two lessons follow. First, the approval rule worked as designed: a 0.74-confidence diagnosis did not act automatically. But unattended, it meant the earliest protective action came from the edge, much later. In a staffed plant, an operator would see the waiting incident and decide much sooner. Second, for a badly worn bearing, the edge's derate step achieves nothing, because the derated trip limit is already exceeded. The edge effectively goes straight to a stop. The protected motor was always stopped deliberately with an intact bearing, rather than seizing, but whether protection also saved running time depended on the classifier's confidence.

As with output, the simulation does not price these differences. A controlled stop with a worn bearing generally means a planned bearing replacement, whereas a seizure can damage the shaft and housing, but this report makes no quantitative claim about that.



## 11.12 Discussion of Results

The experiments support four conclusions *about this simulation and software*:

1. **Edge autonomy prevented failures that central-only protection could not** when central services were unreachable from before the fault (0 of 5 failures against 5 of 5).
2. **Single-sensor manipulation was detected quickly and caused no machine actions**, because decisions rest on medians of redundant sensors, and suspect sensors are quarantined.
3. **Store-and-forward preserved telemetry through uplink losses** of up to 2,800 seconds without overflow, whereas a gateway process failure lost data.
4. **The simple statistical detector was the better choice** for these faults and features, and the safety rules worked as designed: high-impact and low-confidence actions waited for a human.

They do **not** show that the protection is economically beneficial, that the detectors would work on real equipment, or that the system is secure.

**Limitations of the experiments.**

- **Small experiment.** There were 15 conditions with five seeds each, a single target machine per fault, fixed severity and fixed onset.
- **Model and limits share one simulation.** The edge limits and the detector were designed with knowledge of the same simulation they were evaluated in, which favours them.
- **No broker or database in the loop.** The experiments did not measure broker latency, broker loss or database behaviour. Live-stack figures (about 0.04% QoS 0 loss at high speed, p95 latency of about 160 ms, batch writes of about 60 ms) are single observations, not repeated measurements.
- **No cost model.** Machine damage, repair and safety are not modelled, so output and downtime cannot be turned into costs.
- **Scale.** All experiments used 100 devices. The engine alone ran at about 375× real time with 500 devices, but the full pipeline was not benchmarked at that scale.

**Computational performance.** In headless runs with the central pipeline, each worker processed about 2,400 to 2,800 messages per wall-clock second while four workers shared the CPU, and each worker process used about 185 to 220 MB of memory. These figures come from `psutil` within the experiment runner and depend on the laptop's other load at the time.
