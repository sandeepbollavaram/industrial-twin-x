# Implementation

## 9.1 Development Environment

The project was developed on one laptop, whose configuration was audited before any installation (`docs/environment-audit.md`). @tab:env summarises it. No step required administrator rights. The Python interpreter, caches and Docker data were kept on drive D: because drive C: had little free space.

Table: Development environment {#tab:env}

| Item | Value |
| --- | --- |
| Machine | HP Victus 15-fa1xxx laptop |
| Operating system | Windows 11 Home Single Language, 26H2 |
| CPU | Intel Core i5-13420H, 8 cores, 12 threads |
| Memory | 15.65 GB |
| GPU | NVIDIA GeForce RTX 2050, 4 GB (not used; all models run on the CPU) |
| Containers | Docker Desktop with the WSL2 backend |
| Editor | Visual Studio Code |
| Python | 3.13.16, managed by uv in a project virtual environment |
| Node.js / pnpm | 24.11.1 / 10.4.1 |

## 9.2 Technology Stack

@tab:stack lists the main libraries and the versions installed when this report was prepared.

Table: Technology stack and installed versions {#tab:stack}

| Layer | Technology | Version |
| --- | --- | --- |
| Simulation | SimPy [@simpy] | 4.1.2 |
| Numerics | NumPy [@harris2020], SciPy, pandas | 2.5.4, 1.18.1, 3.1.0 |
| Machine learning | scikit-learn [@pedregosa2011] | 1.9.1 |
| Messaging | Eclipse Mosquitto [@light2017], Eclipse Paho [@paho] | 2.0 (image), 2.1.0 |
| API | FastAPI [@fastapi], Pydantic, Uvicorn | 0.162.0, 2.14.2 |
| Persistence | PostgreSQL [@postgres], SQLAlchemy, Alembic, psycopg 3 | 17 (image), 2.1.6 |
| Frontend | Next.js [@nextjs], React | 16.4.3, 19.3.1 |
| 3D | three.js, React Three Fiber [@r3f], drei | 0.187.0, 9.8.2, 10.7.9 |
| Charts | Recharts; Matplotlib for report figures [@hunter2007] | 3.10.1 |
| Styling | Tailwind CSS | 4.3.3 |
| Quality | pytest, Ruff, mypy, ESLint, TypeScript | TypeScript 6.0.3 |
| Infrastructure | Docker Compose [@compose] | Compose v5 |

TypeScript is held at version 6 because `typescript-eslint`, which `eslint-config-next` uses, refused to run with TypeScript 7.0 (ADR-009).

## 9.3 Repository Structure

The repository is a monorepo containing both Python packages and the web application (Appendix B gives the full tree). The total size of the hand-written source at the time of writing is shown in @tab:loc.

Table: Size of the hand-written source code {#tab:loc}

| Area | Files | Lines |
| --- | --- | --- |
| `simulation` | 16 | 1,438 |
| `modules` | 21 | 1,311 |
| `apps/api` | 5 | 800 |
| `apps/web/src` | 22 | 1,704 |
| `research` | 9 | 886 |
| `tests` | 6 | 865 |

## 9.4 Backend Implementation

The FastAPI application (`apps/api/twinx_api/main.py`) creates a `Runtime` in its lifespan handler and exposes 20 HTTP endpoints and one WebSocket (Appendix C). Request bodies are Pydantic models, so invalid input is rejected with HTTP 422 before any handler runs. The command endpoint shows how authorisation is enforced at the boundary:

```python
verdict = authorize(body.command, body.value, approved_by=body.approved_by)
if verdict.decision is Decision.DENY:
    raise HTTPException(422, verdict.reason)
if verdict.decision is Decision.NEEDS_APPROVAL:
    raise HTTPException(403, f"approval required: {verdict.reason}")
```

The WebSocket handler computes the overview snapshot in a worker thread (`asyncio.to_thread`), so the event loop is never blocked by the pipeline lock.

## 9.5 Simulation Engine Implementation

`FactorySimulation` (`simulation/engine/core.py`) builds the machines, sensors and gateways from the factory specification, registers the SimPy processes and schedules scenarios. Random streams are derived as follows:

```python
root = np.random.SeedSequence(seed)
machine_seeds, sensor_seeds, gateway_seeds, ambient_seed = root.spawn(4)
machine_rngs = machine_seeds.spawn(len(self.spec.machines))
sensor_rngs = iter(sensor_seeds.spawn(self.spec.sensor_count))
```

Machines are built in two passes, because the tank needs references to its pumps and the distribution units need references to the machines they supply. The physics process steps the ambient model, then the rotating machines, then the dependent assets (tank, power units, environment), so that each dependent asset sees its inputs from the same second.

The live runner (`simulation/run.py`) paces the engine against wall time. Every 100 ms it handles queued commands, then advances the engine by 0.1 s multiplied by the speed factor. If a step overruns, it does not try to catch up in a burst; instead it lets simulation time fall behind. During verification with the speed set to 50×, the observed telemetry rate was about 500 messages per second rather than the nominal 1,000. The simulator was therefore running at roughly 25× real time on this laptop with all services active.

## 9.6 MQTT Implementation

Both processes use Paho with the version 2 callback API, automatic reconnection with backoff from 1 to 15 seconds, and a bounded outgoing queue [@paho]. The API's `on_connect` callback re-subscribes on every reconnection, so subscriptions survive broker restarts. The simulator's publish callback selects QoS by message kind:

```python
qos = 0 if envelope.kind in ("telemetry", "network") else 1
result = self.client.publish(envelope.topic, json.dumps(envelope.payload), qos=qos)
if result.rc != mqtt.MQTT_ERR_SUCCESS:
    self.publish_failures += 1
```

## 9.7 Database Integration

The schema is defined with SQLAlchemy 2 declarative models (`apps/api/twinx_api/db.py`), and the initial Alembic migration (`0001`) was generated from them and applied to the containerised PostgreSQL. The `BatchWriter` thread inserts each batch with a single `INSERT` of many rows inside one transaction, and records the duration of each batch. The registry seed and the twin-state sync use PostgreSQL's `INSERT ... ON CONFLICT` through SQLAlchemy's dialect-specific `insert`, so restarts neither duplicate devices nor fail.

## 9.8 AI Model Integration

At startup, the `Runtime` loads the model bundle if it exists and wraps it in `TrainedAI`, which implements the same `assess()` interface as the rule-based fallback. The pipeline calls `assess()` for each machine at most once every 30 simulated seconds. Inference is single-row: all forests use `n_jobs=1`, because parallel prediction on one row costs more in thread overhead than it saves. Forest sizes were reduced during development (100 trees for the classifier, 60 for the risk model) after measuring that single-row inference time dominated the headless experiments.

## 9.9 Recovery Engine

The recovery engine is pure Python with no dependency on the API or MQTT. It receives two callables: one to send a command and one to verify recovery. This lets the same engine run in the API, in headless experiments, and in unit tests with stub functions. The transition table is a dictionary from each state to the set of allowed next states. Every change goes through one method, which checks the table, updates the state and appends to the audit trail:

```python
def _to(self, incident, state, now, actor, detail):
    if state not in TRANSITIONS[incident.state]:
        raise InvalidTransition(f"{incident.state} -> {state}")
    incident.state = state
    self._log(incident, now, "transition", actor, detail)
```

## 9.10 Frontend Implementation

The dashboard is a Next.js App Router application with twelve pages, listed in @tab:pages. All pages are client components that read either the shared WebSocket snapshot or REST endpoints. The visual design uses neutral surfaces, a single accent colour, no gradients and no emoji. Colour tokens are defined in CSS custom properties for light and dark themes. Every status shows a shape and a word as well as a colour, so it does not rely on colour alone. @fig:screenoverview, @fig:screentelemetry and @fig:screenrecovery show three pages from a live run; Appendix H contains more.

Table: Dashboard pages {#tab:pages}

| Page | Content |
| --- | --- |
| Overview | Key counts, latency, write statistics, simulation controls, machine table, recent alerts |
| 3D Factory | Zones and machines in 3D, fault labels, machine selection and inspection |
| Device Explorer | Reported and desired state and message counters for each device |
| Telemetry | One chart per signal for a selected machine (median of redundant sensors) |
| AI Intelligence | Live assessments and the held-out detector comparison |
| Predictive Maintenance | Machines ranked by risk score with recommendations |
| Network Monitoring | Gateway state, delivery ratio, losses, backlog and replay |
| Cybersecurity | Integrity findings, quarantined sensors, isolated devices, command log |
| Recovery Operations | Incidents, approval controls and audit trails |
| Experiments | Results table read from the experiment summary |
| Reports | Generated report files |
| System Settings | Service status, model version and factory configuration |

![Overview page during a live run with an overheating fault on MTR-A02 and a manipulated sensor on MTR-A01. Software simulation screenshot, 16 November 2026.](figures/screen-overview.png){#fig:screenoverview}

![Telemetry page for MTR-A02 after it was derated, showing medians of redundant simulated sensors. Software simulation screenshot.](figures/screen-telemetry.png){#fig:screentelemetry}

![Recovery Operations page: a recovered incident and a low-confidence incident awaiting approval, with its audit trail. Software simulation screenshot.](figures/screen-recovery.png){#fig:screenrecovery}

## 9.11 Three-Dimensional Factory Visualization

The 3D view (`apps/web/src/components/Factory3D.tsx`) uses React Three Fiber [@r3f] and helper components from drei. Each zone is a floor plane with a label, and each machine is a simple primitive placed at its layout position: a box sized by machine kind, or a cylinder for the tank. Machines are coloured by state. Faulted or selected machines carry an HTML label, and clicking a machine opens its readings in a side panel. The camera orbits, zooms and pans with OrbitControls, limited so it cannot go below the floor. The component reads the theme's colour tokens and updates when the theme changes. The page is loaded dynamically without server rendering, because WebGL requires a browser.

Two limitations were found during verification. In development mode, the Next.js error overlay reported a React warning ("Attempted to synchronously unmount a root while React was already rendering") originating in drei's `Html` labels; the view still worked, and production builds show no overlay. The 3D view was also designed for desktop browsers and was not tested on mobile devices.

![3D Factory page. Faulted machines are coloured and labelled. Software simulation screenshot.](figures/screen-factory3d.png){#fig:screen3d}

## 9.12 Docker Infrastructure

Docker Compose runs only the two infrastructure services, as shown in @tab:compose [@compose]. Both have health checks, memory limits and ports bound to 127.0.0.1. The database password comes from an untracked `.env` file; Compose refuses to start if it is missing. The Python processes and the dashboard run on the host, which keeps development iteration fast and avoids building images. Containerising them is possible future work.

Table: Docker Compose services {#tab:compose}

| Service | Image | Memory limit | Port (host) | Health check |
| --- | --- | --- | --- | --- |
| postgres | `postgres:17-alpine` | 512 MB | 127.0.0.1:15432 | `pg_isready` |
| mosquitto | `eclipse-mosquitto:2.0` | 128 MB | 127.0.0.1:1883 | Subscribe to `$SYS` |

PostgreSQL is published on port 15432 instead of the default 5432, for two reasons: a native PostgreSQL service was already installed on the machine, and Windows reserved the TCP range that includes the first port tried, 55432 (ADR-008).

## 9.13 Execution and Deployment Procedure

After one-time setup (Appendix A), the system starts with one command, `.\scripts\dev.ps1`. The script:

1. loads the D: cache settings;
2. checks that `.env` exists;
3. starts Compose and waits for the health checks;
4. syncs Python and Node dependencies;
5. applies database migrations;
6. opens the API, the simulator and the dashboard in separate PowerShell windows.

`.\scripts\dev.ps1 -Stop` stops the Compose services and keeps the database volume. This workflow was run end to end during post-publication verification. Afterwards, the API reported both the broker and the database connected, the dashboard returned HTTP 200, and all 100 devices were reporting.
