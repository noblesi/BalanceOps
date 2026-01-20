param()

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# .venv 파이썬을 우선 사용 (없으면 py -3.12 -> python 순)
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
  $Python = $VenvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $Python = "py -3.12"
} else {
  $Python = "python"
}

# $env:PYTHONPATH = $RepoRoot.Path

# Streamlit 실행
if ($Python -is [string] -and $Python.StartsWith("py ")) {
  & py -3.12 -m streamlit run "apps/dashboard/app.py"
} else {
  & $Python -m streamlit run "apps/dashboard/app.py"
}