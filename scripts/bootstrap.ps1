param(
  [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# python 선택: .venv > py -3.12 > python
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
  Write-Host "[bootstrap] using venv python: $VenvPython"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  Write-Host "[bootstrap] creating venv with py -$PythonVersion"
  & py -$PythonVersion -m venv .venv
  $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
} else {
  Write-Host "[bootstrap] creating venv with system python"
  python -m venv .venv
  $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path $VenvPython)) {
  throw "venv python not found: $VenvPython"
}

# pip 업데이트
& $VenvPython -m pip install -U pip setuptools wheel

# 프로젝트 설치 (editable) + dev extras
& $VenvPython -m pip install -e ".[dev]"

Write-Host ""
Write-Host "[bootstrap] done."
Write-Host "Next:"
Write-Host "  .\scripts\run_once.ps1"
Write-Host "  .\scripts\dashboard.ps1"
