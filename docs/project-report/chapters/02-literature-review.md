# Literature Review

## 2.1 Introduction

This chapter reviews the work on which Industrial Twin-X builds. It covers the IIoT, digital twin architectures, simulation of equipment, MQTT-based communication, predictive maintenance, anomaly detection, industrial cybersecurity, edge computing and fault detection and recovery. Every source cited here was opened and checked during preparation of this report. For each source the review states only what its abstract or text supports, and it relates the work to the design decisions in later chapters. Section 2.11 identifies the gaps this project addresses, and Section 2.12 compares the approaches.

## 2.2 Industrial Internet of Things

Xu, He and Li reviewed IoT research and its industrial applications, covering enabling technologies such as RFID, wireless sensor networks and service-oriented integration, together with research trends and open challenges [@xu2014]. Sisinni et al. clarified the relationship between the IoT, the IIoT and Industry 4.0. They identified requirements specific to industrial settings, including energy efficiency, real-time performance, coexistence, interoperability, and security and privacy [@sisinni2018]. Al-Fuqaha et al. gave a horizontal overview of the IoT, with emphasis on its enabling technologies, protocols and application issues [@alfuqaha2015].

Two architectural ideas from the cyber-physical systems literature shape this project. Lee, Bagheri and Kao proposed a five-level architecture in which information is monitored and synchronised between the physical factory floor and the cyber computational space [@lee2015]. Leitão, Colombo and Karnouskos reviewed industrial cyber-physical systems, their technologies and the challenges of implementing them, including the gap between prototypes and industrial readiness [@leitao2016]. Industrial Twin-X sits at the prototype end of this spectrum: it implements the connection, conversion and cyber layers in software, without the physical layer.

## 2.3 Digital Twin Architectures

The digital twin concept was developed by Grieves and Vickers across the product lifecycle [@grieves2017]. Tao et al. reviewed the key components, current development and major industrial applications of digital twins, in product design, production and prognostics and health management [@tao2019]. Kritzinger et al. separated the digital model, the digital shadow and the digital twin by the direction and automation of data flow between physical and virtual objects [@kritzinger2018]. This classification is useful for describing Industrial Twin-X precisely: its twin is updated automatically from telemetry and sends commands back automatically, so it has the data flows of a twin, but its physical counterpart is simulated.

Jones et al. analysed 92 publications and consolidated thirteen characteristics of the digital twin. These include the physical and virtual entities and environments, state, twinning and the twinning rate, and the physical-to-virtual and virtual-to-physical connections [@jones2020]. Industrial Twin-X implements several of these explicitly. Its state is the reported readings per device; its twinning rate is one message per device every 5 simulated seconds; and its virtual-to-physical connection is the command channel. Rasheed et al. emphasised that a twin's predictive value depends on combining physics-based models with data-driven models [@rasheed2020]. Fuller et al. surveyed enabling technologies and open problems, including data and model integration [@fuller2020]. Rosen et al. discussed autonomy and digital twins as technical questions for the future of manufacturing [@rosen2015].

Platform implementations have converged on a common state model. AWS IoT Device Shadow documents separate a *desired* state, written by applications, from a *reported* state, written by the device, and compute a *delta* containing desired values not yet matched by reported values [@awsshadow]. Eclipse Ditto represents devices as "Things" in the cloud and caches their last-known state, so applications can read it while the device is offline [@ditto]. Industrial Twin-X adopts the desired/reported/delta model inside its own twin engine rather than depending on either platform. This keeps the prototype self-contained and allows its ordering and reset rules to be tested directly (Chapter 6).

## 2.4 Physics-Based Equipment Simulation

Simulation is an established way to obtain data that real systems cannot safely or cheaply provide. Saxena et al. generated run-to-failure data for aircraft gas turbine engines by imposing exponentially growing flow and efficiency losses on a thermodynamic model, starting from randomly chosen initial deterioration, until a failure criterion was met [@saxena2008]. Two features of that approach carry over to this project: degradation grows faster as damage accumulates, and each trajectory has its own randomised parameters.

For electrical machines, Boglietti et al. surveyed thermal analysis methods, including lumped-parameter thermal networks, finite-element analysis and computational fluid dynamics [@boglietti2009]. A lumped-parameter network represents the machine as thermal resistances and capacitances, and a single-node version reduces to one first-order differential equation linking losses, heat transfer to the surroundings and thermal capacitance. Industrial Twin-X uses this simplest single-node form for winding temperature (Section 5.8). It is far coarser than the multi-node networks the survey describes, which is acceptable for testing software behaviour but not for predicting real motor temperatures.

Discrete-event simulation frameworks provide the time-keeping. SimPy describes itself as a process-based discrete-event simulation framework based on standard Python, in which processes are generator functions [@simpy]. Industrial Twin-X uses SimPy processes for physics, telemetry, networking, edge evaluation and scenario events, all advancing on a shared simulation clock.

## 2.5 MQTT-Based Industrial Communication

MQTT is a lightweight publish/subscribe messaging protocol standardised by OASIS. Version 3.1.1 defines three quality-of-service levels. Under QoS 0 ("at most once") message loss can occur; under QoS 1 ("at least once") duplicates can occur; and QoS 2 ("exactly once") assures single delivery [@mqtt311]. It also defines a keep-alive mechanism and a "Last Will" message that the broker publishes when a client disconnects unexpectedly [@mqtt311]. Version 5.0 retains this model and adds features for larger deployments [@mqtt5]. Hunkeler, Truong and Stanford-Clark described MQTT-S, an adaptation of MQTT for wireless sensor networks with low-end, battery-operated devices [@hunkeler2008]. Light described Eclipse Mosquitto, an open-source broker and client implementation of MQTT intended for lightweight messaging on constrained devices [@light2017].

Industrial Twin-X uses Mosquitto as its broker and the Eclipse Paho Python client, whose default protocol version is 3.1.1 [@paho]. The choice of QoS level per topic is a design decision examined in Section 6.5: high-rate telemetry uses QoS 0, accepting possible loss for lower overhead, while commands, status and alerts use QoS 1.

OPC UA is the other major industrial interoperability standard. The OPC Foundation describes it as a platform-independent, service-oriented architecture with built-in encryption, authentication and auditing [@opcua]. OPC UA was considered for this project but **has not been implemented**; it is listed as future work in Chapter 12.

## 2.6 Predictive Maintenance Approaches

Jardine, Lin and Banjevic reviewed diagnostics and prognostics for condition-based maintenance, with emphasis on models, algorithms and technologies for data processing and maintenance decision-making [@jardine2006]. Lei et al. reviewed machinery prognostics across the whole programme, from data acquisition to remaining useful life (RUL) prediction, and discussed current challenges and future trends [@lei2018]. Carvalho et al. systematically reviewed machine learning methods applied to predictive maintenance and observed that performance depends on choosing an appropriate method [@carvalho2019]. Zonta et al. catalogued predictive maintenance methods, standards and applications in Industry 4.0 [@zonta2020].

Two points from this literature constrain Industrial Twin-X. First, RUL prediction is a distinct task that requires validated degradation models and suitable data; this project does **not** claim RUL prediction. Second, a probability of failure is only meaningful if the model is calibrated. Niculescu-Mizil and Caruana showed that different learning algorithms distort predicted probabilities in characteristic ways and that Platt scaling and isotonic regression can correct this, given enough data [@niculescu2005]. The scikit-learn documentation notes that isotonic calibration is more flexible but more prone to overfitting on small datasets [@sklearn_calib]. Industrial Twin-X applies isotonic calibration but found residual miscalibration, so it reports a *risk score* rather than a probability (Section 7.9).

## 2.7 Machine Learning for Anomaly Detection

Chandola, Banerjee and Kumar grouped anomaly detection techniques into categories by their underlying approach, identified the key assumptions each category makes about normal and anomalous behaviour, and proposed using those assumptions to judge whether a technique suits a domain [@chandola2009]. The simplest statistical detectors flag points that lie far from the mean of normal data, measured in standard deviations; the baseline in Section 7.7 is of this kind.

Liu, Ting and Zhou proposed the Isolation Forest, which isolates anomalies by random recursive partitioning instead of profiling normal points. Anomalies need fewer partitions to isolate, so they have shorter average path lengths [@liu2008]. The authors reported favourable performance against ORCA, LOF and random forests in terms of AUC and processing time, especially on large datasets [@liu2008]. In scikit-learn, `score_samples` returns the negative of the paper's anomaly score, so lower values are more abnormal [@sklearn_iforest]. Breiman's random forests, which combine tree predictors grown on random feature subsets, are the basis of the fault classifier used here [@breiman2001]. Ge et al. reviewed unsupervised and supervised learning in the process industry and discussed its role in monitoring and fault diagnosis [@ge2017].

Evaluation methodology matters as much as the algorithm. Kaufman et al. described *leakage*: the introduction of information about the target that should not legitimately be available to the model [@kaufman2012]. Roberts et al. showed that ignoring temporal, spatial or hierarchical structure when cross-validating seriously underestimates predictive error, and recommended block cross-validation [@roberts2017]. Overlapping windows from one simulated trajectory are strongly dependent, so Industrial Twin-X splits its data by simulation run using scikit-learn's `GroupShuffleSplit`, which assigns whole groups to either training or test data [@sklearn_gss].

## 2.8 Industrial Cybersecurity

NIST SP 800-82 Rev. 3 covers the topologies, threats, vulnerabilities and countermeasures for operational technology [@nist80082]. The ISA/IEC 62443 series defines requirements and processes for electronically secure industrial automation and control systems across their lifecycle [@isa62443]. Humayed et al. systematised cyber-physical systems security along three axes: threats, vulnerabilities, attacks and controls; cyber, physical and cyber-physical components; and representative systems [@humayed2017].

For manipulated measurements, Liu, Ning and Reiter studied false data injection against power-grid state estimation, examining whether existing bad-measurement detection can defeat injected measurements [@liu2009]. Cárdenas et al. addressed risk assessment, detection and response for attacks against process control systems [@cardenas2011]. Langner's analysis of Stuxnet showed that an attack can aim at physical destruction [@langner2011].

Industrial Twin-X addresses a narrow part of this space. Its integrity checks compare each sensor with its redundant peers and detect frozen values, which catches manipulation of a single sensor but, as Section 8.8 explains, not coordinated manipulation of a majority of sensors. It does not implement the network-level controls these standards require, such as authentication and encryption. The broker and API are unauthenticated and are bound to localhost only (Section 12.5).

## 2.9 Edge Computing and Distributed Resilience

Shi et al. defined edge computing as processing data at the edge of the network, and identified response time, bandwidth, battery life, and data safety and privacy as motivations [@shi2016]. Satyanarayanan described edge computing's ability to provide responsive services close to devices and to *mask transient cloud outages* [@satya2017]. The second property motivates this project's edge design: protective logic runs on each gateway, keeps operating when the uplink to central services is lost, and buffers telemetry for later replay.

## 2.10 Fault Detection and Recovery

Isermann introduced model-based fault detection and diagnosis, with applications to an actuator, a passenger car and a combustion engine [@isermann2005]. Venkatasubramanian et al. classified process fault detection and diagnosis methods into three general categories and reviewed the quantitative model-based methods in the first part of their series [@venkat2003]. Industrial Twin-X combines detectors and classifiers learned from simulated history with simple checks based on physical knowledge: comparison of redundant sensors for integrity, and physically motivated verification conditions after mitigation.

Recovery requires more than detection. An automated system must decide which action to take, whether it may take it without a human, and how to confirm that the action worked. The industrial security guidance above stresses safety requirements in operational technology [@nist80082]. Industrial Twin-X makes these decisions explicit in an incident state machine, an authorisation policy and an audit trail (Sections 8.10 to 8.13).

## 2.11 Research Gaps

The literature reviewed here treats digital twins, predictive maintenance, anomaly detection, industrial security and edge computing in depth, and largely as separate subjects. The reviews of digital twins report that implementations integrating physical and virtual objects bidirectionally are less common than models and shadows [@kritzinger2018], and that enabling technologies and integration remain open research areas [@fuller2020]. The predictive maintenance reviews emphasise dependence on data and method choice [@carvalho2019; @zonta2020]. Evaluation-methodology work warns that dependent data and leakage can inflate reported performance [@kaufman2012; @roberts2017].

Within the scope of the sources reviewed, three gaps are relevant to this project. This review does not claim that no previous system has addressed them:

1. **Integrated, reproducible evaluation.** None of the reviewed sources describes a single testbed in which twin synchronisation, fault detection, edge protection, integrity checking and recovery are exercised together under seeded, repeatable conditions with known ground truth.
2. **Baselines under leakage-free conditions.** The evaluation-methodology literature shows that dependent data and leakage can inflate reported performance [@kaufman2012; @roberts2017]. A learned detector should therefore be compared against a simple baseline on data split by trajectory, rather than presented alone.
3. **Safe coupling of analytics to actuation.** The reviewed security guidance emphasises the safety requirements of operational technology [@nist80082], but the specific rules linking a model output to an actuator command are left to the system designer. These include confidence thresholds, impact classes, human approval and device-side limits.

Industrial Twin-X addresses these as a simulation-only prototype. It does not close them for real industrial systems, which would require validation on physical equipment and real data.

## 2.12 Comparative Analysis of Existing Approaches

@tab:litcompare summarises how representative approaches from the literature relate to the design of Industrial Twin-X. The right-hand column states what this project does, not a claim of superiority.

Table: Comparison of approaches from the literature with the Industrial Twin-X design {#tab:litcompare}

| Area | Approach in the literature | Strength | Limitation for this project | Industrial Twin-X design |
| --- | --- | --- | --- | --- |
| Twin state | Desired/reported shadow [@awsshadow]; cached Things [@ditto] | Mature, well-documented model | External platform dependency | Same state model implemented internally |
| Equipment data | Run-to-failure simulation [@saxena2008] | Known ground truth | Realism limited to the model | Seeded lumped-parameter models |
| Thermal model | Lumped networks, FEA, CFD [@boglietti2009] | Accurate with detailed parameters | Parameters unavailable without hardware | Single-node lumped model |
| Messaging | MQTT publish/subscribe [@mqtt311; @light2017] | Lightweight, broker-based | No built-in schema or ordering semantics | Versioned JSON schema, sequence numbers |
| Anomaly detection | Isolation Forest [@liu2008]; categories of techniques [@chandola2009] | Unsupervised, fast | Suitability depends on the domain assumptions | Both evaluated; baseline used live |
| Fault classification | Random forests [@breiman2001] | Robust, interpretable importances | Needs labelled faults | Trained on simulated labels |
| Probability estimates | Platt or isotonic calibration [@niculescu2005] | Corrects distorted probabilities | Needs data; can overfit | Isotonic, reported as a risk score |
| Evaluation | Block or grouped validation [@roberts2017] | Avoids optimistic error estimates | Fewer effective samples | Split by simulation run |
| Data integrity | Detection and response for process-control attacks [@cardenas2011] | Addresses the control system as a whole | Needs knowledge of the process | Redundant-sensor comparison, frozen-value check |
| Resilience | Edge computing masks outages [@satya2017] | Local response, less bandwidth | Edge resources and logic are limited | Gateway-local deterministic limits |
| Security controls | NIST SP 800-82, ISA/IEC 62443 [@nist80082; @isa62443] | Comprehensive guidance | Large implementation effort | Not implemented; documented gap |
