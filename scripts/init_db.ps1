param(
  [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot
$env:PYTHONPATH = "{0};{1}" -f $RepoRoot.Path, (Join-Path $RepoRoot "src")
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) { & $VenvPython -m balanceops.tracking.init_db }
elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -$PythonVersion -m balanceops.tracking.init_db }
else { python -m balanceops.tracking.init_db }
