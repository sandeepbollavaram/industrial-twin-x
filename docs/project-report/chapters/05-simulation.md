# Industrial Environment Simulation

## 5.1 Simulation Methodology

The industrial environment is a discrete-time simulation advanced in steps of one simulated second by a SimPy environment [@simpy]. Four kinds of SimPy process share one clock:

1. a **physics process**, which steps the ambient model, then every machine, then the sensor attack state, once per second;
2. a **telemetry process**, which each second publishes the devices whose index falls in the current slot of a 5-second cycle, so that every device reports once every 5 seconds and the message rate stays even;
3. a **network process**, which advances each gateway, delivers due messages to a sink and emits a network report every 5 seconds;
4. an **edge process**, which evaluates the edge policy every 5 seconds, plus one **scenario process** per scheduled event.

The machine models are lumped-parameter approximations integrated with the explicit Euler method at Δt = 1 s. They were chosen to produce plausible, physically motivated behaviour: temperatures that rise with losses and fall with cooling, vibration that grows with wear and speed, and pressures that follow pump affinity laws. They are **not** calibrated against any specific real machine. Every value in this chapter is a model parameter set by the author, not a measured property of physical equipment.

The engine does not know about MQTT. Delivered messages are passed to a *sink* function. In live mode the sink publishes to the broker; in tests and experiments it feeds the central pipeline directly or records messages. This makes the same simulation code testable and repeatable.

## 5.2 Virtual Factory Design

@tab:machines lists the ten machines. The template is defined in `simulation/factory/layout.py`. Rated values are representative industrial magnitudes chosen for the simulation.

Table: Machines in the virtual factory (scale 1) {#tab:machines}

| ID | Name | Kind | Zone | Gateway | Rated speed (rpm) | Rated power (kW) |
| --- | --- | --- | --- | --- | --- | --- |
| MTR-A01 | Main Drive Motor 1 | motor | A | GW-A1 | 1480 | 15 |
| MTR-A02 | Main Drive Motor 2 | motor | A | GW-A1 | 1480 | 15 |
| CNV-A03 | Assembly Conveyor | conveyor | A | GW-A2 | 960 | 7.5 |
| ROB-A04 | Welding Robot Cell | robot | A | GW-A2 | 2800 | 5.5 |
| PMP-B01 | Feed Pump 1 | pump | B | GW-B1 | 2900 | 22 |
| PMP-B02 | Feed Pump 2 | pump | B | GW-B1 | 2900 | 22 |
| TNK-B03 | Process Water Tank | tank | B | GW-B1 | not applicable | not applicable |
| PDU-C01 | Distribution Unit Zone A | power | C | GW-C1 | not applicable | not applicable |
| PDU-C02 | Distribution Unit Zone B | power | C | GW-C1 | not applicable | not applicable |
| ENV-C03 | Environmental Station | environment | C | GW-C2 | not applicable | not applicable |

## 5.3 Factory Zones

**Zone A: Manufacturing.** Two 15 kW drive motors, a 7.5 kW assembly conveyor and a 5.5 kW welding robot cell. The motors carry a slowly varying load; the conveyor alternates between a loaded and a lighter state as product batches pass; the robot follows a 60-second duty cycle. Gateways GW-A1 and GW-A2 serve this zone.

**Zone B: Pumping and fluid systems.** Two 22 kW centrifugal feed pumps fill a process water tank whose outlet valve is controlled to hold the level. Gateway GW-B1 serves this zone.

**Zone C: Power and environmental monitoring.** Distribution unit PDU-C01 carries the electrical load of zone A, PDU-C02 that of zone B, and an environmental station reports hall temperature and humidity. Gateways GW-C1 and GW-C2 serve this zone.

## 5.4 Virtual Machines

Four machine classes are implemented in `simulation/devices/machines.py`:

- `RotatingMachine` (motors), with subclasses `Conveyor` and `RobotCell` that override the load profile, and `Pump`, which adds hydraulics;
- `Tank`, a mass balance with a level controller;
- `PowerUnit`, which aggregates downstream electrical load;
- `EnvironmentStation`, which reports the ambient model.

Each machine exposes `step(t, dt, ambient)` to advance its state, `signals()` to return its true physical values, `apply_command()` to act on commands, and `truth()` to return hidden state for evaluation.

## 5.5 Virtual IoT Devices

Each machine has ten devices, giving 100 devices at scale 1, and each device carries three sensors, giving 300 sensors. The signals measured depend on the machine kind (@tab:kindsignals). Signals are assigned to devices in rotation, so each signal is measured redundantly on several devices. A rotating machine with seven signals has 30 sensor slots, so each signal has four or five sensors.

Table: Signals measured for each machine kind {#tab:kindsignals}

| Machine kind | Signals |
| --- | --- |
| Motor, conveyor, robot | speed, current, power, winding temperature, bearing temperature, vibration, device health |
| Pump | the seven above, plus delivered flow, suction flow, discharge pressure |
| Tank | level, outlet flow, hydrostatic pressure, valve position, fluid temperature |
| Power unit | current, voltage, power, transformer temperature, device health |
| Environment | air temperature, humidity, fan current, fan power |

## 5.6 Sensor Models

A sensor reading r is produced from the true value x as shown in @eq:sensor:

$$ r = Q( clip( g·x + o + ε + b ) ),  ε ~ N(0, σ²) $$ {#eq:sensor}

where g is a per-sensor gain drawn once from N(1, 0.002²), o is a per-sensor offset drawn once from N(0, (0.3σ)²), ε is fresh Gaussian noise for each reading, b is an attack bias that is zero except in manipulation scenarios, clip limits the value to the instrument range, and Q rounds to the instrument resolution. @tab:signals gives the parameters per signal.

Table: Sensor model parameters per signal {#tab:signals}

| Signal | Unit | Noise σ | Resolution | Range |
| --- | --- | --- | --- | --- |
| Speed | rpm | 2.0 | 0.1 | 0 to 4000 |
| Current | A | 0.08 | 0.01 | 0 to 2000 |
| Power | kW | 0.05 | 0.01 | 0 to 2000 |
| Winding temperature | °C | 0.25 | 0.01 | −40 to 250 |
| Bearing temperature | °C | 0.25 | 0.01 | −40 to 250 |
| Vibration (RMS velocity) | mm/s | 0.05 | 0.001 | 0 to 60 |
| Device health | % | 0.3 | 0.1 | 0 to 100 |
| Flow (delivered, suction) | m³/h | 0.4 | 0.01 | 0 to 1000 |
| Pressure | bar | 0.02 | 0.001 | 0 to 25 |
| Tank level | % | 0.1 | 0.01 | 0 to 100 |
| Valve position | % | 0.1 | 0.1 | 0 to 100 |
| Fluid temperature | °C | 0.1 | 0.01 | −10 to 120 |
| Voltage | V | 0.4 | 0.1 | 0 to 500 |
| Transformer temperature | °C | 0.2 | 0.01 | −40 to 200 |
| Air temperature | °C | 0.1 | 0.01 | −40 to 80 |
| Humidity | % | 0.3 | 0.1 | 0 to 100 |

The **device health** signal deserves comment. A real drive often reports a self-diagnostic health figure computed from what it can measure. The simulated health is computed the same way, from observable vibration and temperature (@eq:health). It never reads the hidden wear state, which would leak the answer into the data.

$$ H = clip( 100 − 8·max(0, v − 2) − 1.2·max(0, T_w − 90), 0, 100 ) $$ {#eq:health}

Here v is vibration in mm/s and T_w is winding temperature in °C.

## 5.7 Actuator Models

Rotating machines accept `set_speed`, `start`, `stop` and `repair`. Speed follows the command through a first-order response with an 8-second time constant. The device-side function `validate_command` rejects unknown commands and any `set_speed` value that is not finite or lies outside 0.3 to 1.0 of rated speed. A failed machine rejects every command except `repair`. In the simulation, `repair` represents completed maintenance: it resets wear, cooling and leak to healthy values and restarts the machine. The commands `isolate` and `release` stop and resume a device's telemetry and act at the gateway, not on the machine.

## 5.8 Physics-Informed Simulation

### Electrical model

For a rotating machine with rated power P_r, speed fraction s and load fraction L, the shaft fraction is L·s·(1 + 0.2w), where w ∈ [0, 1] is bearing wear. For pumps, the affinity laws make shaft power scale with the cube of speed, so the shaft fraction is L·s³·(1 + 0.2w)(1 + 0.35λ), where λ is the leak fraction. Electrical input power and line current follow @eq:power, with efficiency η = 0.90, line voltage V = 400 V and power factor 0.86:

$$ P = P_r · shaft / η,   I = P / (√3 · V · pf) $$ {#eq:power}

### Thermal model

Winding temperature uses a single-node lumped thermal model, the simplest form of the lumped-parameter networks surveyed by Boglietti et al. [@boglietti2009]. The Euler update applied every step is @eq:thermal:

$$ T(t+Δt) = T(t) + Δt · ( P_loss − h·c·( T(t) − T_amb ) ) / C $$ {#eq:thermal}

where:

- T is the winding temperature (°C) and T_amb the ambient temperature (°C);
- Δt = 1 s is the time step;
- P_loss = 0.027·P_r·s + 0.085·P_r·shaft² (W) combines a speed-dependent fixed loss and a load-dependent copper loss;
- h = 30·(P_r / 15 kW) W/K is the heat-transfer coefficient, scaled with machine size;
- c ∈ (0, 1] is the cooling effectiveness, 1 when healthy and reduced by the overheating fault;
- C = 9000·(P_r / 15 kW) J/K is the thermal capacitance.

The assumptions are that the winding is a single isothermal body, heat leaves only by a linear transfer to ambient air, and losses depend only on speed and load. For a 15 kW motor at full speed and 70% load, these parameters give a steady-state winding temperature of roughly 35 to 40 K above ambient, with a time constant of about 300 seconds. When cooling falls to 0.28, the temperature rises towards about 120 K above ambient, which exceeds the simulated insulation failure threshold of 140 °C. These values were chosen to make the fault develop over minutes of simulated time; they do not describe any particular real motor.

### Bearing and vibration model

Bearing temperature relaxes towards T_amb + 18s + 45ws with a 400-second time constant. Vibration RMS velocity follows @eq:vibration:

$$ v = 0.9·min(4s, 1) + 0.7·s² + 8.5·w²·s $$ {#eq:vibration}

The first term is a baseline that falls to zero as the machine stops, the second grows with speed (imbalance), and the third grows with the square of wear and with speed. At full speed, a healthy machine (w ≈ 0.03) vibrates at about 1.6 mm/s, and a machine at w = 0.8 at about 7 mm/s.

### Pump and tank model

A pump with rated flow Q_r = 120 m³/h draws suction flow Q_s = Q_r·s·(1 + 0.5λ) and delivers Q_d = Q_s·(1 − λ). Its head is 6s² − 1.5(Q_s/Q_r)² bar before the leak, and the discharge pressure is multiplied by (1 − 0.9λ). A leak therefore lowers discharge pressure and delivered flow while raising suction flow and shaft power, a combination the leak-ratio feature captures (Section 7.4). The tank integrates the inflow from both pumps minus its outflow. A proportional controller sets the outlet valve to 0.5 + 0.04·(level − 60%), clipped to [0, 1], which holds the level near 60%.

### Power and environment

Each distribution unit sums a 3 kW base load with the electrical power of the machines it serves. Its bus voltage droops by 0.06 V per ampere, and its transformer temperature relaxes towards ambient plus a load-dependent rise with a 30-minute time constant.

## 5.9 Equipment Degradation

Bearing wear grows according to @eq:wear:

$$ dw/dt = ( 10⁻⁸ + r·(1 + 4w) ) · s² $$ {#eq:wear}

where r is the fault-driven wear rate (zero when healthy). The factor (1 + 4w) makes wear accelerate as damage accumulates, a qualitative feature shared with the exponential damage propagation used by Saxena et al. [@saxena2008]. The factor s² means a derated machine wears more slowly. When w reaches 1, the machine fails with a bearing seizure; when the winding reaches 140 °C, it fails with an insulation failure. A failed machine stops and accumulates downtime until it is repaired. Each machine starts with a small random wear drawn from U(0, 0.05).

## 5.10 Environmental Influences

The ambient model gives hall temperature as 25 + 4·sin(2π(t + t₀)/86400 − π/2) + d(t) °C. Here t₀ sets the time of day at the start of the run, and d(t) is a slow Ornstein–Uhlenbeck drift with a 30-minute time constant. Humidity falls by 1.5 percentage points per degree above 25 °C. Ambient temperature enters every thermal model, so the same machine runs hotter in the afternoon than in the morning. This is the reason the training dataset randomises the time of day (Section 7.2). Load variation is also stochastic: each rotating machine adds an Ornstein–Uhlenbeck noise term with a 120-second time constant to its base load profile.

## 5.11 Fault Injection

Faults are scripted as `Scenario` objects containing timed `ScenarioEvent`s (`simulation/scenarios/catalog.py`). @tab:scenarios lists the implemented scenarios with their default parameters. Each scenario also carries ground-truth metadata (fault label, target machine and onset time) that is used only for evaluation and is never published.

Table: Implemented scenarios and default parameters {#tab:scenarios}

| Scenario | Effect | Default target and timing |
| --- | --- | --- |
| `normal` | No fault | Not applicable |
| `bearing_degradation` | Wear rate r = 1.5×10⁻⁴ × severity | MTR-A01 at 600 s |
| `motor_overheating` | Cooling falls to 0.28 / severity over 300 s | MTR-A02 at 600 s |
| `pump_leakage` | Leak rises to 0.35 × severity over 600 s | PMP-B01 at 600 s |
| `gateway_outage` | Gateway process down: messages lost, edge stopped | GW-A1, 600 s for 300 s |
| `network_degradation` | +0.8 s latency, 10% packet loss | GW-B1, 600 s for 600 s |
| `sensor_manipulation` | Bias ramps to +60 at 0.2 per second on one sensor | MTR-A01-node-a winding temperature at 600 s |
| `sensor_replay` | One sensor freezes at its current value | MTR-A01-node-a winding temperature at 600 s |
| `central_disconnection` | All five uplinks down; edge runs; telemetry buffers | All gateways, 600 s for 600 s |
| `telemetry_backlog` | Long uplink loss, then a bounded-rate flush | GW-A1, 600 s for 900 s |

In live mode, a scenario started from the dashboard is scheduled relative to the current simulation time. All attacks are changes to simulator state: no network traffic is attacked, and no real system is affected.

## 5.12 Simulation Time and Random Seeds

Reproducibility comes from NumPy's `SeedSequence` [@harris2020]. The root seed is spawned into four independent child sequences: machines, sensors, gateways and the ambient model. These are spawned again per component, by stable index. Every machine, sensor and gateway therefore has its own random stream, and adding a consumer of randomness to one component cannot shift any other component's stream. Headless runs stamp messages with a fixed epoch plus simulation time instead of the wall clock. The automated test `test_same_seed_is_byte_identical` serialises all messages from two runs with the same seed and checks that they are identical, and a companion test checks that different seeds give different output.

Live runs are not byte-identical, for two reasons: messages carry wall-clock timestamps, and operator actions arrive at unpredictable simulation times. The live runner advances the engine in steps of 0.1 s of wall time multiplied by the speed factor (1× to 100×), and it executes inbound commands only between steps, so state changes stay atomic.

## 5.13 Data Generation and Storage

Simulated data reaches storage by two routes:

- **Live operation.** Telemetry flows through MQTT to the API, which writes every accepted message to the `telemetry` table in batches, upserts twin state every 5 seconds, and records alerts, commands, findings, status messages and audit entries. At 100 devices, the system produces 20 telemetry messages per simulated second, or 200 per wall second at the default 10× speed.
- **Headless research runs.** The dataset generator runs the engine without a broker or database and writes labelled feature windows to `research/datasets/generated/windows.csv.gz`. The experiment runner writes per-run results to `research/experiments/runs/raw_results.json` and aggregated results to `research/reports/experiments/summary.json`.

Generated datasets, model binaries and raw run results are excluded from version control because they can be regenerated from their seeds. The aggregated summaries and figures are versioned as evidence.
