# One-shot, idempotent project setup (Windows PowerShell).
# Creates .venv, installs pinned backend deps, copies .env, installs frontend deps.
$ErrorActionPreference = "Stop"
$env:PIP_REQUIRE_VIRTUALENV = "1"   # pip refuses to install outside a venv
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { py -3.14 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (Test-Path frontend\package.json) { Push-Location frontend; npm install; Pop-Location }

Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
