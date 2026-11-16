# Introduction

## 1.1 Introduction to Industrial IoT

The Industrial Internet of Things (IIoT) applies networked sensing, communication and computation to industrial equipment and processes. Sisinni et al. distinguish the IIoT from consumer IoT by its emphasis on reliability, determinism, energy efficiency, interoperability and security, and they place it within the broader Industry 4.0 programme [@sisinni2018]. Xu, He and Li surveyed IoT deployments in industry and identified the enabling technologies as identification, wireless and mobile sensing, and service-oriented integration of devices with information systems [@xu2014]. Al-Fuqaha et al. surveyed the enabling technologies of the IoT and the protocols that connect devices with applications and services [@alfuqaha2015].

In a typical industrial deployment, sensors measure physical quantities such as temperature, vibration, current, pressure and flow. Gateways collect these readings, perform local processing and forward them to central services, where they are stored, analysed and visualised. Operators and automated controllers then act on the results. Each stage introduces engineering concerns: measurement noise and drift at the sensor, intermittent connectivity at the gateway, data volume and ordering at the central services, and the risk that a wrong decision acts on a physical machine.

## 1.2 Evolution of Industrial Digital Twins

A digital twin is a virtual representation of a physical asset that is kept consistent with that asset through data. Grieves and Vickers developed the concept across the product lifecycle [@grieves2017]. Tao et al. reviewed industrial applications of digital twins in product design, production and prognostics and health management [@tao2019]. Kritzinger et al. classified implementations by their level of integration: a *digital model* has no automatic data exchange with the physical object, a *digital shadow* receives data automatically in one direction, and a *digital twin* exchanges data automatically in both directions [@kritzinger2018]. They reported that publications describing the full digital twin were scarce compared with those describing digital models and shadows.

Later reviews broadened the definition. Jones et al. consolidated thirteen characteristics of the digital twin, including the physical and virtual entities, their environments, state, twinning and the twinning rate [@jones2020]. Rasheed, San and Kvamsdal emphasised the role of physics-based simulators and data-driven models in giving a twin predictive value [@rasheed2020]. Fuller et al. reviewed enabling technologies and open research problems across manufacturing, healthcare and smart cities [@fuller2020]. Rosen et al. discussed the importance of autonomy and digital twins for the future of manufacturing [@rosen2015].

These classifications matter for this project. Industrial Twin-X maintains a twin of each virtual device that is updated automatically from telemetry and that issues commands back to the simulated equipment. Under the Kritzinger classification, the twin is bidirectional, but the "physical" side is itself a software simulation. The project therefore demonstrates the software architecture of a bidirectional twin; it does not demonstrate twinning of real equipment.

## 1.3 Importance of Predictive Maintenance

Maintenance strategies range from running equipment until it fails, through fixed-interval preventive maintenance, to condition-based and predictive maintenance that act on the measured state of the equipment. Jardine, Lin and Banjevic reviewed diagnostics and prognostics for condition-based maintenance, with emphasis on models, algorithms and technologies for data processing and maintenance decision-making [@jardine2006]. Lei et al. reviewed machinery prognostics from data acquisition to remaining useful life prediction [@lei2018]. Carvalho et al. and Zonta et al. reviewed the use of machine learning for predictive maintenance in Industry 4.0 settings, and both reported that performance depends heavily on the choice of method and on the available data [@carvalho2019; @zonta2020].

Predictive maintenance is attractive because unplanned failures stop production and can damage equipment, while premature maintenance wastes useful life. It is also hard to evaluate, because run-to-failure data from real machines is scarce and expensive to collect. Saxena et al. addressed this problem for aircraft engines by generating run-to-failure trajectories from a thermodynamic simulation model with imposed damage propagation [@saxena2008]. Industrial Twin-X follows the same general approach at a much smaller scale: it generates fault trajectories in simulation, where the true degradation state is known, so that detection and prediction methods can be evaluated against ground truth.

## 1.4 Challenges in Industrial Equipment Monitoring

Monitoring industrial equipment presents several recurring challenges:

- **Noisy and redundant measurements.** Sensors have calibration error, noise and limited resolution. Important quantities are often measured by more than one sensor, which provides redundancy but also requires a rule for combining disagreeing values.
- **Slowly developing faults.** Degradation such as bearing wear or a falling cooling capacity can develop over hours, and its early signature may be smaller than normal operational variation.
- **Operating-point changes.** A machine running at reduced speed produces different vibration, current and temperature from one at full speed, so a fixed threshold can mistake a deliberate change for a fault.
- **Intermittent connectivity.** Gateways lose their uplink, messages are delayed, lost or delivered out of order, and backlogs must be replayed without corrupting the current state.
- **Label scarcity.** Labelled fault data from real equipment is rare, which makes supervised learning and honest evaluation difficult.
- **Safety of automated actions.** An automated response to a false alarm can stop production or, worse, act unsafely on a machine.

## 1.5 Cybersecurity Challenges in IIoT

Industrial systems control physical processes, so a security failure can have physical consequences. NIST SP 800-82 Revision 3 provides guidance on securing operational technology while respecting its performance, reliability and safety requirements [@nist80082]. The ISA/IEC 62443 series defines requirements and processes for secure industrial automation and control systems [@isa62443]. Humayed et al. surveyed security threats, vulnerabilities, attacks and controls across cyber, physical and cyber-physical components [@humayed2017].

Manipulated sensor data is a particular concern. Liu, Ning and Reiter studied false data injection attacks against state estimation in electric power grids, questioning whether the bad-measurement detection techniques used there can defeat measurements injected by an attacker [@liu2009]. Cárdenas et al. studied risk assessment, detection and response for attacks against process control systems, motivated by attacks such as Stuxnet [@cardenas2011]. Langner's analysis of Stuxnet described malware whose goal was physical damage rather than information theft [@langner2011]. These works motivate a design in which decisions do not depend on any single sensor, and in which consequential commands require additional authorisation.

## 1.6 Motivation for Industrial Twin-X

The motivation for Industrial Twin-X is to build a controlled environment in which IIoT monitoring, digital twin synchronisation, fault detection, edge autonomy, sensor integrity checking and fault recovery can be designed and evaluated together. Each of these topics is well studied on its own, as Chapter 2 shows. Their interaction is harder to study, because doing so requires equipment that can be degraded, communication links that can be broken and sensors that can be manipulated, all repeatably.

Physical test rigs are costly, and deliberately damaging equipment or attacking an operational network is unsafe. A software simulation removes these constraints. It allows faults to be injected on demand, gives exact ground truth for evaluation, and makes every run reproducible from a random seed. The price is realism: a simulation contains only the physics its authors chose to model. This report therefore treats every result as a property of the simulation and the software, not as evidence about real industrial equipment.

## 1.7 Project Scope

The project is entirely software-based. No physical sensors, controllers, machines or IoT hardware were used. The scope comprises:

- a virtual factory with 3 production zones, 5 gateways, 10 machines, 100 devices and 300 sensors, built from simplified physical models;
- telemetry transport over MQTT using Eclipse Mosquitto;
- a digital twin with reported and desired state, persisted to PostgreSQL;
- anomaly detection, fault classification, degradation estimation and a short-horizon risk score, trained and evaluated on simulated data;
- edge protection that operates on the gateway without central services;
- sensor integrity checks and contained sensor-manipulation scenarios;
- an incident state machine with command authorisation and an audit trail;
- a web dashboard with a three-dimensional factory view;
- an experiment runner, automated tests and documentation.

Excluded from the scope are physical hardware, OPC UA integration, production-grade security (authentication and transport encryption), and validation against real industrial data. Section 3.9 and Chapter 12 discuss these limits.

## 1.8 Project Objectives

The objectives of the project are:

1. To simulate an industrial environment whose sensor readings follow physically motivated models, with reproducible fault injection.
2. To transport telemetry and commands through an industrial-style publish/subscribe architecture and to maintain a consistent digital twin.
3. To detect and classify equipment faults using statistical and machine-learning methods, and to evaluate them on held-out simulation runs.
4. To keep machines protected when central services are unreachable, using edge policies on the gateway.
5. To detect manipulated sensor readings and to prevent them from driving machine actions.
6. To manage faults through an auditable recovery process in which high-impact or low-confidence actions require human approval.
7. To measure the behaviour of the system under repeated, seeded experiments, and to report the results honestly, including unfavourable ones.

Section 12.2 assesses each objective against the evidence.

## 1.9 Contributions of the Project

The project's contributions are engineering and methodological rather than theoretical:

- **An integrated, reproducible testbed.** One shared simulation engine drives all virtual devices, and a headless run is byte-identical for a given seed. The same central processing code runs in live mode over MQTT and in headless experiments.
- **Evaluation against ground truth.** Hidden simulation state, such as bearing wear and leak fraction, labels the data, while features use only published telemetry. Data is split by simulation run to avoid leakage between overlapping windows.
- **A documented negative result.** The Isolation Forest, the planned primary anomaly detector, performed worse than a statistical baseline on the held-out runs. The live system therefore uses the baseline, and the report records why.
- **Safety-oriented decision design.** Edge limits act on the median of redundant sensors, ML output never reaches an actuator without passing an authorisation policy, and device-side limits apply regardless of the sender.
- **A measured resilience comparison.** Under central-service disconnection, an overheating motor failed in 5 of 5 runs without edge protection and in 0 of 5 runs with it.

## 1.10 Organization of the Report

Chapter 2 reviews literature on the IIoT, digital twins, simulation, MQTT, predictive maintenance, anomaly detection, industrial security, edge computing and fault recovery. Chapter 3 defines the problem, requirements and scope. Chapter 4 presents the architecture. Chapter 5 describes the simulated industrial environment and its models. Chapter 6 covers communication and the digital twin. Chapter 7 describes the AI and predictive maintenance work, and Chapter 8 covers edge computing, cybersecurity and fault recovery. Chapter 9 describes the implementation, Chapter 10 the testing, and Chapter 11 the experimental results. Chapter 12 concludes and lists future work. The appendices give setup instructions, the repository structure, interface summaries, the database schema, experiment configuration, test commands, additional figures and placeholders for team contributions.
