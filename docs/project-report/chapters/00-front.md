# University Certificate

Sri Chandrasekharendra Saraswathi Viswa Mahavidyalaya (SCSVMV), Kancheepuram

Department of Computer Science and Engineering

This is to certify that the project report entitled **"Industrial Twin-X: An Intelligent, Autonomous and Cyber-Resilient Industrial Internet of Things Digital Twin Using Software Simulation"** is a bonafide record of the work carried out by Bollavram Sandeep Kumar (11249A040), D. Gopala Krishna Rayudu (11249A078), K. Harish (11249A150) in partial fulfilment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering of Sri Chandrasekharendra Saraswathi Viswa Mahavidyalaya (SCSVMV), Kancheepuram during the academic year [ACADEMIC YEAR].

[PLACEHOLDER: Replace with the university's prescribed certificate wording if it differs. Signatures and seal are added on the printed copy; no approval is implied by this draft.]

| | |
| --- | --- |
| Ms. Hema Poorani J | [NAME OF HEAD OF DEPARTMENT] |
| Project Guide | Head of the Department |
| Signature: | Signature: |

# Department Certificate

Department of Computer Science and Engineering, Sri Chandrasekharendra Saraswathi Viswa Mahavidyalaya (SCSVMV), Kancheepuram

This is to certify that Bollavram Sandeep Kumar (11249A040), D. Gopala Krishna Rayudu (11249A078), K. Harish (11249A150) have completed the major project entitled "Industrial Twin-X" under the guidance of Ms. Hema Poorani J in the Department of Computer Science and Engineering during the academic year [ACADEMIC YEAR].

[PLACEHOLDER: Replace with the department's prescribed wording if it differs. Signatures are added on the printed copy; no approval is implied by this draft.]

Date: [DATE]

Place: [PLACE]

# Student Declaration

We hereby declare that the project report entitled "Industrial Twin-X: An Intelligent, Autonomous and Cyber-Resilient Industrial Internet of Things Digital Twin Using Software Simulation", submitted to Sri Chandrasekharendra Saraswathi Viswa Mahavidyalaya (SCSVMV), Kancheepuram in partial fulfilment of the requirements for the degree of Bachelor of Technology in Computer Science and Engineering, is a record of original work done by us under the guidance of Ms. Hema Poorani J. All sources used are acknowledged in the references. All experimental results reported here were obtained from software simulation, and no result is claimed as a measurement on physical hardware.

[PLACEHOLDER: Each student must read, confirm and sign this declaration personally.]

| Name | Roll number | Signature |
| --- | --- | --- |
| Bollavram Sandeep Kumar | 11249A040 | |
| D. Gopala Krishna Rayudu | 11249A078 | |
| K. Harish | 11249A150 | |

Date: [DATE]

# Acknowledgement

We thank our project guide, Ms. Hema Poorani J, for her guidance throughout this project, and the Department of Computer Science and Engineering, Sri Chandrasekharendra Saraswathi Viswa Mahavidyalaya (SCSVMV), Kancheepuram, for its support.

[PLACEHOLDER: The team should review this acknowledgement and add, in their own words, anyone else who helped, such as the Head of the Department.]

The project used open-source software maintained by many contributors, including Python, SimPy, NumPy, pandas, scikit-learn, FastAPI, SQLAlchemy, PostgreSQL, Eclipse Mosquitto, Eclipse Paho, Next.js, React, three.js and React Three Fiber.

# Abstract

Industrial equipment monitoring must detect developing faults from noisy, sometimes delayed and occasionally manipulated sensor data. It must keep protecting machines when networks or central services fail, and it must never let an uncertain analytic drive an unsafe action. Studying these problems together on physical equipment is costly, unsafe and unrepeatable. This project presents Industrial Twin-X, a software-only Industrial Internet of Things digital twin that replaces the plant with a seeded simulation and builds an industrial-style monitoring and recovery stack on top of it.

A shared SimPy engine simulates 10 machines, 100 devices and 300 sensors in three zones, using lumped-parameter thermal, vibration, wear and hydraulic models. It can inject bearing wear, overheating, pump leakage, gateway and network faults, and sensor manipulation, all reproducibly from a seed. Telemetry flows over MQTT through Eclipse Mosquitto into a digital twin with reported and desired state and explicit ordering rules, persisted to PostgreSQL. Analytics combine a statistical anomaly detector, a random-forest fault classifier, a degradation regressor and a short-horizon risk score. Gateway-local edge policies protect machines using medians of redundant sensors. Integrity checks quarantine disagreeing or frozen sensors, and an audited incident state machine requires a named human for high-impact or low-confidence actions.

On held-out simulated runs split by trajectory, the statistical detector reached an F1 score of 0.969. The planned Isolation Forest reached only 0.677 and missed every overheating run, so the system uses the simpler detector. In five-seed experiments with central services disconnected, an overheating motor failed in 0 of 5 runs with edge protection and in 5 of 5 without it. Both single-sensor attacks were detected in 47 to 58 seconds without false quarantines or machine actions. Store-and-forward preserved every message through a 900-second uplink loss. All 101 automated tests pass. The results describe the software's behaviour against its simulation. They do not establish real-world industrial safety, hardware performance or economic benefit.

**Keywords:** Industrial Internet of Things, digital twin, predictive maintenance, anomaly detection, edge computing, MQTT, sensor integrity, fault recovery, simulation.

# List of Abbreviations

| Abbreviation | Meaning |
| --- | --- |
| ADR | Architecture Decision Record |
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| AUC | Area Under the (ROC) Curve |
| CBM | Condition-Based Maintenance |
| CORS | Cross-Origin Resource Sharing |
| CPS | Cyber-Physical System |
| DT | Digital Twin |
| FIFO | First In, First Out |
| HTTP | Hypertext Transfer Protocol |
| IACS | Industrial Automation and Control Systems |
| IIoT | Industrial Internet of Things |
| IoT | Internet of Things |
| JSON | JavaScript Object Notation |
| JSONB | Binary JSON (PostgreSQL data type) |
| MAE | Mean Absolute Error |
| ML | Machine Learning |
| MQTT | MQ Telemetry Transport |
| NIST | National Institute of Standards and Technology |
| OASIS | Organization for the Advancement of Structured Information Standards |
| OPC UA | OPC Unified Architecture |
| OT | Operational Technology |
| QoS | Quality of Service |
| REST | Representational State Transfer |
| RMS | Root Mean Square |
| ROC | Receiver Operating Characteristic |
| RPM | Revolutions Per Minute |
| RUL | Remaining Useful Life |
| SCADA | Supervisory Control and Data Acquisition |
| SD | Standard Deviation |
| TLS | Transport Layer Security |
| WSL | Windows Subsystem for Linux |
