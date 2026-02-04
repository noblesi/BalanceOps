param(
  [switch]$SkipE2E = $false,
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# .ci sandbox env (기본값이 없을 때만 설정)
if (-not $env:BALANCEOPS_DB) {
  $env:BALANCEOPS_DB = (Join-Path $RepoRoot ".ci\balanceops.db")
}
if (-not $env:BALANCEOPS_ARTIFACTS) {
  $env:BALANCEOPS_ARTIFACTS = (Join-Path $RepoRoot ".ci\artifacts")
}
if (-not $env:BALANCEOPS_CURRENT_MODEL) {
  $env:BALANCEOPS_CURRENT_MODEL = (Join-Path $RepoRoot ".ci\artifacts\models\current.joblib")
}
if (-not $env:PYTHONUNBUFFERED) {
  $env:PYTHONUNBUFFERED = "1"
}

# balanceops-ci-check 우선 사용, 없으면 python -m fallback
$Cmd = Get-Command balanceops-ci-check -ErrorAction SilentlyContinue

if ($Cmd) {
  Write-Host "[check] using console script: balanceops-ci-check"
  if ($SkipE2E) {
    balanceops-ci-check --skip-e2e
  } else {
    balanceops-ci-check --port $Port
  }
  exit $LASTEXITCODE
}

# python fallback: .venv > python
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonExe = "python"
if (Test-Path $VenvPython) {
  Write-Host "[check] using venv python: $VenvPython"
  $PythonExe = $VenvPython
} else {
  Write-Host "[check] using python on PATH"
}

if ($SkipE2E) {
  & $PythonExe -m balanceops.tools.ci_check --skip-e2e
} else {
  & $PythonExe -m balanceops.tools.ci_check --port $Port
}
exit $LASTEXITCODE
