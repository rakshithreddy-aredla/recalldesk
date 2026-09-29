# Starts the Hindsight memory server locally on http://localhost:8888.
# Reads backend/.env and forwards every variable into the process environment,
# so HINDSIGHT_API_LLM_PROVIDER / HINDSIGHT_API_LLM_API_KEY / HINDSIGHT_API_LLM_MODEL
# from .env configure the server's internal LLM directly.

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot "backend\.env"
if (-not (Test-Path $envFile)) {
  Write-Error "backend\.env not found - copy backend\.env.example to backend\.env and add your keys first."
  exit 1
}

Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
    Set-Item -Path ("env:" + $Matches[1]) -Value $Matches[2]
  }
}

if (-not $env:HINDSIGHT_API_LLM_API_KEY) {
  Write-Warning "HINDSIGHT_API_LLM_API_KEY is empty - Hindsight's extractor needs an LLM key (see backend\.env.example)."
}

$scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"
$exe = Join-Path $scripts "hindsight-api.exe"
if (-not (Test-Path $exe)) { $exe = Join-Path $scripts "hindsight-api" }
if (-not (Test-Path $exe)) {
  Write-Error "hindsight-api not found - run: pip install hindsight-api"
  exit 1
}

Write-Host "Starting Hindsight API at http://localhost:8888 ..."
& $exe
