param()

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
  & $VenvPython -m balanceops.pipeline.train_dummy
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3.12 -m balanceops.pipeline.train_dummy
} else {
  python -m balanceops.pipeline.train_dummy
}
