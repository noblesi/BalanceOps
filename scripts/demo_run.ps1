param(
  [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot
$env:PYTHONPATH = "{0};{1}" -f $RepoRoot.Path, (Join-Path $RepoRoot "src")
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) { & $VenvPython -m balanceops.pipeline.demo_run }
elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -$PythonVersion -m balanceops.pipeline.demo_run }
else { python -m balanceops.pipeline.demo_run }
