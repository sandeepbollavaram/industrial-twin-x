# Environment Audit

Audit date: 2026-11-02. All values below were read from the machine with read-only commands.

## Detected configuration

| Item | Value |
| --- | --- |
| Machine | HP Victus 15-fa1xxx |
| OS | Windows 11 Home Single Language, 26H2, build 26300, 64-bit |
| CPU | Intel Core i5-13420H, 8 cores, 12 threads |
| RAM | 15.65 GB total, 3.08 GB free at audit time |
| GPU | NVIDIA GeForce RTX 2050, 4 GB VRAM, driver 592.27, CUDA 13.1 reported by `nvidia-smi`; Intel UHD integrated |
| Hypervisor | Present (WSL2 is functional) |

## Storage

| Drive | Size | Free | Use |
| --- | --- | --- | --- |
| C: | 291.9 GB | 15.6 GB | Avoid: low free space |
| D: | 562.3 GB | 220.7 GB | Project, caches, Docker data |
| S: | 97.7 GB | 59.0 GB | Not used |

## Installed software

| Tool | Version | Status |
| --- | --- | --- |
| VS Code | 1.144.0 | Reuse. Python, Pylance and Debugger extensions present |
| Python on PATH | 3.10.11 (Microsoft Store) | Not used by this project |
| Python launcher default | 3.12.10 | Not used by this project |
| uv | 0.13.1 | Reuse |
| Node.js / npm | 24.11.1 / 11.6.2 | Reuse |
| pnpm / Corepack | 10.4.1 / 0.34.2 | Reuse |
| Git | 2.52.0 | Reuse. Global name and email are set |
| GitHub CLI | 2.89.0 | Reuse. See the GitHub section below |
| Docker / Compose | 29.3.1 / v5.1.1 | Reuse |
| WSL | 2.4.13, kernel 5.15.167 | Reuse. Ubuntu and docker-desktop distributions, version 2 |
| PostgreSQL (native) | `postgresql-x64-18` service, running | Not touched. The project uses its own container |

## Missing software

| Tool | Decision |
| --- | --- |
| Python 3.13 | Install through uv into `D:\uv-python`. No administrator rights needed |
| DBeaver | Optional, not installed. Not required for any project function |
| VS Code extensions: Docker, GitLens, ESLint, Prettier, Tailwind, YAML, REST Client | Listed in `.vscode/extensions.json`, so VS Code offers them on open. Not force-installed, to save space on C: |

## Compatibility issues and how they are handled

1. **uv defaults point at C:.** `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR` are unset, although `D:\uv-cache` and `D:\uv-python` already exist. `scripts/env.ps1` sets both for the current process only. No user or system environment variable is changed.
2. **`python` on PATH is 3.10.** Always use `.venv` or `uv run`.
3. **Native PostgreSQL service exists.** The container publishes on `127.0.0.1:15432`, away from the native service and from the Windows reserved TCP range that covers 54738-55487 (first attempted port 55432 was refused for this reason).
4. **No `.wslconfig`.** WSL2 may use up to about half of RAM. This file is global, so it was left alone; containers carry their own memory limits in `docker-compose.yml` instead.
5. **Low free RAM at audit time (3.08 GB).** Other applications were using most memory. Close heavy applications before running the full stack and experiments.
6. **Two GitHub accounts are in the CLI.** `gh auth status` labels the active one `sandy001-kki`, but the token resolves to the login `sandeepbollavaram` (id 192683536); the label is stale. Publishing would go to `sandeepbollavaram`. The repository name `sandeepbollavaram/industrial-twin-x` was free at audit time.

## Reusable configuration

- Docker Desktop stores WSL data under `D:\DockerData\DockerDesktopWSL` (already on D:).
- pnpm store: `D:\caches\pnpm-store`. npm cache: `D:\npm-cache`.
- Ports 1883, 3000, 4840, 8000 and 9001 were free.

## Installation plan

No step requires administrator rights, Windows feature changes, firewall changes or system environment changes.

1. Install Python 3.13 with uv into `D:\uv-python`.
2. Create `D:\Industrial-Twin-X\.venv` and sync pinned dependencies.
3. Install frontend packages with pnpm using the existing D: store.
4. Pull `postgres` and `eclipse-mosquitto` images into the existing Docker data location on D:.

## Estimated resource requirements

These are planning estimates, not measurements.

| Resource | Estimate |
| --- | --- |
| Disk on D: | About 3 GB (Python environment, `node_modules`, images, datasets) |
| Disk on C: | Close to zero new usage |
| RAM, full stack | About 2 to 3 GB plus Docker Desktop overhead |
| GPU | Not required. All first-stage models run on CPU |
