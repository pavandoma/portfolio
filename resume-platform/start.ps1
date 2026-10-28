<#
  Starts the Resume Intelligence Platform on Windows and opens http://localhost:3000.

  From PowerShell, in this folder:
      powershell -ExecutionPolicy Bypass -File .\start.ps1

  Needs Python 3.11+ and Node.js 20+. The first run installs dependencies (a few minutes).
  Your data stays in .\data on this computer. Close the two server windows to stop the app.
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

function Invoke-Checked([string]$what, [scriptblock]$cmd) {
    Write-Host "==> $what"
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)." }
}

if (-not (Test-Path $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-Checked "Creating the Python environment" { py -3 -m venv (Join-Path $backend ".venv") }
    } else {
        Invoke-Checked "Creating the Python environment" { python -m venv (Join-Path $backend ".venv") }
    }
}
Invoke-Checked "Installing backend packages" {
    & $venvPython -m pip install --disable-pip-version-check -q -r (Join-Path $backend "requirements.txt")
}
Push-Location $backend
try { Invoke-Checked "Preparing the database" { & $venvPython -m alembic upgrade head } } finally { Pop-Location }

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Push-Location $frontend
    try { Invoke-Checked "Installing frontend packages" { npm ci --no-audit --no-fund } } finally { Pop-Location }
}

Write-Host "==> Starting the backend (port 8000) and the frontend (port 3000) in two new windows"
Start-Process powershell -WorkingDirectory $backend -ArgumentList "-NoExit", "-Command",
    "& '$venvPython' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-Process powershell -WorkingDirectory $frontend -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "==> Waiting for the app to answer"
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://localhost:3000/api/health" | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
Start-Process "http://localhost:3000"
Write-Host "==> Open http://localhost:3000 (close the two server windows to stop)."
