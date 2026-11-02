# Deployment Guide

Local development on Windows. Needs Docker Desktop with WSL2, uv and Node.js with pnpm. No step needs administrator rights.

## Install

```powershell
git clone <repository-url> D:\Industrial-Twin-X
cd D:\Industrial-Twin-X
Copy-Item .env.example .env        # then set POSTGRES_PASSWORD
. .\scripts\env.ps1                # keeps uv's cache on D: for this shell
uv python install 3.13
uv sync
pnpm install
```

## Train models

Models and datasets are not in the repository. Without them the system runs on rule-based diagnosis.

```powershell
.\.venv\Scripts\python.exe -m research.datasets.generate --runs-per-class 20 --seed 1000
.\.venv\Scripts\python.exe -m research.experiments.train
```

## Start

```powershell
.\scripts\dev.ps1
```

This starts Compose, applies migrations and opens the API, simulator and dashboard in separate windows.

- Dashboard: http://127.0.0.1:3000
- API docs: http://127.0.0.1:8000/docs

## Stop

Close the three windows, then run `.\scripts\dev.ps1 -Stop`. The database volume is kept.

## Demonstration

1. On Overview, set speed to 50x and inject `motor_overheating`. MTR-A02 is the target.
2. Watch the 3D Factory and Telemetry pages as the temperature climbs.
3. On Recovery Operations, follow the automatic derate and its audit trail.
4. Reset the run. Inject `pump_leakage` and approve the stop as a named operator.
5. Reset the run. Inject `sensor_manipulation` and see the quarantine on Cybersecurity, with no machine action.

## Test

See [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Reproduce the experiments

```powershell
.\.venv\Scripts\python.exe -m research.experiments.run_experiments --seeds 5 --workers 4
```

Results go to `research/reports/experiments/`. Raw per-run results go to the untracked `research/experiments/runs/`.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ports are not available` on a Postgres port | Windows reserved the range. Check with `netsh interface ipv4 show excludedportrange protocol=tcp` and change `POSTGRES_PORT` in `.env` |
| Compose says to set `POSTGRES_PASSWORD` | `.env` is missing |
| `password authentication failed` after changing `.env` | The volume keeps the first password. Restore it, or delete the volume if the data is disposable |
| Dashboard says API offline | The API window has stopped, or the port is taken |
| MQTT offline | Run `docker compose ps`, and check that port 1883 is free |
| Mode says rule-based fallback | Train the models, then restart the API |
| `ModuleNotFoundError: twinx_api` | Run `uv sync --reinstall-package industrial-twin-x` |
| High memory | Other Compose projects may auto-start with Docker. Check `docker stats` |
