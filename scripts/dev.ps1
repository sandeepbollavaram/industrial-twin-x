# Starts infrastructure, applies migrations, then runs the API, simulator and dashboard.
# Usage: .\scripts\dev.ps1            start everything in separate windows
#        .\scripts\dev.ps1 -Stop      stop the Compose services (data volume is kept)
param([switch]$Stop)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
. .\scripts\env.ps1

if ($Stop) {
    docker compose stop
    return
}
if (-not (Test-Path .env)) {
    throw 'Missing .env. Copy .env.example to .env and set POSTGRES_PASSWORD.'
}
docker compose up -d --wait
uv sync
pnpm install
.\.venv\Scripts\alembic.exe upgrade head

$root = (Get-Location).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
Start-Process pwsh -ArgumentList '-NoExit', '-Command', "Set-Location '$root'; & '$python' -m uvicorn twinx_api.main:app --host 127.0.0.1 --port 8000"
Start-Process pwsh -ArgumentList '-NoExit', '-Command', "Set-Location '$root'; & '$python' -m simulation.run"
Start-Process pwsh -ArgumentList '-NoExit', '-Command', "Set-Location '$root\apps\web'; pnpm dev"
Write-Host 'Dashboard: http://127.0.0.1:3000   API docs: http://127.0.0.1:8000/docs'
