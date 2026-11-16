# Appendix A: Installation and Setup Instructions

Prerequisites: Windows 10 or 11, Docker Desktop with the WSL2 backend, uv, Node.js 24 or later, pnpm 10 or later, and Git. No administrator rights are needed for the project itself.

```text
git clone https://github.com/sandeepbollavaram/industrial-twin-x.git
cd industrial-twin-x
Copy-Item .env.example .env          # then set POSTGRES_PASSWORD in .env
. .\scripts\env.ps1                  # keep uv caches on D: for this shell
uv python install 3.13
uv sync
pnpm install

# Models are not versioned; without them the system uses rule-based diagnosis.
.\.venv\Scripts\python.exe -m research.datasets.generate --runs-per-class 20 --seed 1000
.\.venv\Scripts\python.exe -m research.experiments.train

.\scripts\dev.ps1                    # start everything
```

The dashboard is served at http://127.0.0.1:3000 and the API documentation at http://127.0.0.1:8000/docs. To stop, close the three application windows and run `.\scripts\dev.ps1 -Stop`.

# Appendix B: Project Directory Structure

```text
industrial-twin-x/
  apps/
    api/twinx_api/        FastAPI app: main, runtime, db, settings
    web/src/              Next.js pages, components, client libraries
  simulation/
    engine/               FactorySimulation (SimPy)
    factory/              layout and scaling
    devices/              machine physical models
    sensors/              measurement and tampering model
    actuators/            device-side command limits
    network/              VirtualGateway
    scenarios/            scenario catalogue
    run.py                live runner (MQTT)
  modules/
    telemetry/            topics, schemas, CentralPipeline
    digital_twin/         TwinEngine
    anomaly_detection/    features, detectors
    fault_diagnosis/      classifier, rules
    predictive_maintenance/ degradation, risk, recommendation
    edge_computing/       EdgePolicy
    cybersecurity/        IntegrityMonitor
    recovery_engine/      authorisation, IncidentManager
  infrastructure/
    mqtt/                 mosquitto.conf
    database/alembic/     migrations
  research/
    datasets/             generator (outputs not versioned)
    experiments/          training and experiment runners
    metrics/              metric helpers
    reports/              versioned result summaries and figures
  tests/                  unit, simulation, evaluation, integration
  docs/                   architecture, design decisions, audit, this report
  scripts/                env.ps1, dev.ps1
  docker-compose.yml, pyproject.toml, uv.lock, pnpm-workspace.yaml, pnpm-lock.yaml
```

# Appendix C: API Endpoint Summary

Table: REST and WebSocket endpoints {#tab:api}

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Broker, database and model status |
| GET | `/api/v1/overview` | Counts, machines, alerts, pipeline and infrastructure statistics |
| GET | `/api/v1/factory` | Zones, gateways and machine views |
| GET | `/api/v1/devices` | Twins, optionally filtered by `machine_id` |
| GET | `/api/v1/devices/{device_id}` | One twin with its delta |
| GET | `/api/v1/telemetry/{machine_id}` | Recent readings per signal (up to 720) |
| GET | `/api/v1/ai` | Live assessments and evaluation metrics |
| GET | `/api/v1/network` | Gateway statistics and twin counters |
| GET | `/api/v1/security` | Findings, quarantine, isolation, command log |
| GET | `/api/v1/recovery/incidents` | Incidents with audit trails |
| GET | `/api/v1/recovery/audit` | Persisted audit entries |
| POST | `/api/v1/recovery/incidents/{id}/approve` | Approve the proposed action (operator name required) |
| POST | `/api/v1/recovery/incidents/{id}/reject` | Reject the proposed action |
| POST | `/api/v1/recovery/incidents/{id}/repair` | Record maintenance; sends `repair` |
| POST | `/api/v1/commands` | Operator command, subject to authorisation |
| GET | `/api/v1/scenarios` | Scenario catalogue |
| POST | `/api/v1/scenarios/{id}/start` | Start a scenario now |
| POST | `/api/v1/simulation/control` | Pause, resume, speed or reset |
| GET | `/api/v1/reports` | Generated report files |
| GET | `/api/v1/experiments` | Experiment summary |
| WebSocket | `/ws/live` | Overview snapshot every second |

# Appendix D: MQTT Topic Structure

Root: `industrial-twin-x/factory/{factory_id}`, with `factory_id` `plant-01` by default.

Table: MQTT topic list {#tab:topicsapp}

| Topic | QoS | Example |
| --- | --- | --- |
| `zone/{zone}/device/{device}/telemetry` | 0 | `.../zone/A/device/MTR-A01-controller/telemetry` |
| `device/{device}/status` | 1 | `.../device/MTR-A01-controller/status` |
| `device/{device}/commands` | 1 | `.../device/MTR-A01-controller/commands` |
| `alerts` | 1 | `.../alerts` |
| `network` | 0 | `.../network` |
| `control` | 1 | `.../control` |

An example telemetry payload:

```json
{"schema_version": "1.0", "factory_id": "plant-01", "zone_id": "A",
 "machine_id": "MTR-A01", "gateway_id": "GW-A1", "device_id": "MTR-A01-controller",
 "timestamp": 1767225900.0, "sim_time": 300.0, "sequence": 60,
 "scenario_id": "normal", "status": "running",
 "readings": {"rpm": 1478.2, "power_kw": 12.81, "health_pct": 99.9},
 "replayed": false}
```

# Appendix E: Database Schema

Table: Database tables and columns {#tab:dbschema}

| Table | Column | Type | Notes |
| --- | --- | --- | --- |
| devices | device_id | varchar(64) | Primary key |
| devices | machine_id, zone_id, gateway_id, role | varchar | Indexed: machine_id |
| devices | sensors | jsonb | Signal names |
| telemetry | id | bigint | Primary key, auto-increment |
| telemetry | device_id, machine_id | varchar | Index (machine_id, sim_time) |
| telemetry | sim_time, source_timestamp | double | Simulation and source time |
| telemetry | sequence | bigint | Per-device sequence |
| telemetry | scenario_id, status | varchar | |
| telemetry | readings | jsonb | Sensor values |
| telemetry | replayed | boolean | From backlog |
| twin_state | device_id | varchar(64) | Primary key; upserted every 5 s |
| twin_state | reported, desired | jsonb | Twin state |
| twin_state | status, last_sequence, received, gaps, updated_at | mixed | Counters and time |
| events | id, kind, sim_time, payload, created_at | mixed | Alerts, commands, findings, status; indexed by kind |
| recovery_audit | id, incident_id, machine_id, fault, sim_time, event, actor, detail, state, created_at | mixed | Insert-only by convention; indexed by incident_id |

No foreign keys are declared, so the database does not enforce the logical relationships shown in @fig:er.

# Appendix F: Experiment Configuration

Table: Experiment configuration {#tab:expconfig}

| Parameter | Value |
| --- | --- |
| Dataset generation | 20 runs per class × 4 classes; seeds 1000 to 1079; 3,600 s each; edge off |
| Window / hop / bin | 120 s / 30 s / 5 s |
| Split | GroupShuffleSplit by run, 30% test, seed 7 |
| Detector threshold | 99.5th percentile of normal training scores, per machine kind |
| Alarm rule | 2 consecutive windows above 1.0, and a fault named by the classifier |
| Risk horizon | 900 s; functional failure = failed machine or leak ≥ 0.30 |
| Experiment seeds | 5000 to 5004 |
| Experiment duration | 3,600 s per run; 15 conditions; 4 parallel workers |
| Model bundle | Version 20261102T063522Z |
| Commands | `python -m research.datasets.generate --runs-per-class 20 --seed 1000`; `python -m research.experiments.train`; `python -m research.experiments.run_experiments --seeds 5 --workers 4` |

# Appendix G: Test Execution Commands

```text
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe
.\.venv\Scripts\python.exe -m pytest tests -m "not integration"
docker compose up -d --wait
.\.venv\Scripts\python.exe -m pytest tests -m integration
pnpm --filter @twinx/web lint
pnpm --filter @twinx/web typecheck
pnpm --filter @twinx/web build
```

# Appendix H: Additional Screenshots and Diagrams

All screenshots were captured from the running application with simulated data on 16 November 2026, in the light theme. The diagrams in Chapter 4 are generated from editable Mermaid sources in `docs/project-report/diagrams/`.

![AI Intelligence page: live assessments and the held-out detector comparison. Software simulation screenshot.](figures/screen-ai.png){#fig:screenai}

![Predictive Maintenance page: the derated motor with a diagnosed overheating fault is shown as high priority. Software simulation screenshot.](figures/screen-maintenance.png){#fig:screenmaint}

![Network Monitoring page: gateway statistics during normal operation at high simulation speed. Software simulation screenshot.](figures/screen-network.png){#fig:screennet}

![Cybersecurity page: a quarantined winding-temperature sensor and the actuator command log. Software simulation screenshot.](figures/screen-security.png){#fig:screensec}


# Appendix I: Team Contribution Placeholders

The team members are listed below. Individual contributions are not recorded in the repository and must be filled in by the team.

Table: Team contributions (to be completed) {#tab:team}

| Name | Roll number | Contributions |
| --- | --- | --- |
| Bollavram Sandeep Kumar | 11249A040 | [CONTRIBUTIONS] |
| D. Gopala Krishna Rayudu | 11249A078 | [CONTRIBUTIONS] |
| K. Harish | 11249A150 | [CONTRIBUTIONS] |
