# Starts the RecallDesk API + UI on http://localhost:8000.
# Uses `python -m uvicorn` because uvicorn.exe is not on PATH on this machine.

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $repoRoot "backend")
Write-Host "Starting RecallDesk at http://localhost:8000 ..."
python -m uvicorn app.main:app --port 8000
