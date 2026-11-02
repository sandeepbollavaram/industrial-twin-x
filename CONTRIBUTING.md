# Contributing

## Setup

Follow [the deployment guide](docs/architecture/deployment-guide.md). On Windows, run `. .\scripts\env.ps1` first in any shell where you use `uv`, so its cache stays on D:.

## Before you commit

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe
.\.venv\Scripts\python.exe -m pytest tests -m "not integration"
docker compose up -d --wait
.\.venv\Scripts\python.exe -m pytest tests -m integration
pnpm --filter @twinx/web lint
pnpm --filter @twinx/web typecheck
pnpm --filter @twinx/web build
```

## Rules

- Keep randomness seeded through `FactorySimulation`. A headless run must stay byte-identical for a given seed; `tests/simulation/test_engine.py` enforces this.
- Hidden simulator state (wear, leak, cooling) may be used for labels and evaluation only. It must never appear in telemetry or features.
- Split data by simulation run, never by window.
- Report measured results only, and call them simulated. If a proposed method loses to its baseline, say so.
- ML output must never reach an actuator except through `modules/recovery_engine/authorization.py`.
- Do not commit `.env`, generated datasets, model binaries or logs.
- Do not use AI co-author trailers in commit messages. Do not force-push.

Record significant decisions in [docs/design-decisions/](docs/design-decisions/).
