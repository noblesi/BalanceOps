param(
  [switch]$SkipE2E = $false,
  [switch]$IncludeTabularBaseline = $false,
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# import 안정화 (설치/엔트리포인트가 없더라도 -m 실행이 되게)
$SrcPath = Join-Path $RepoRoot "src"
if ($env:PYTHONPATH) {
  $env:PYTHONPATH = "{0};{1};{2}" -f $RepoRoot.Path, $SrcPath, $env:PYTHONPATH
} else {
  $env:PYTHONPATH = "{0};{1}" -f $RepoRoot.Path, $SrcPath
}

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

# args 구성 (python ci_check와 동일 계약)
$Args = @()
if ($SkipE2E) {
  $Args += "--skip-e2e"
} else {
  $Args += @("--port", $Port)
}
if ($IncludeTabularBaseline) {
  $Args += "--include-tabular-baseline"
}

# 1) console script 우선
$Cmd = Get-Command balanceops-ci-check -ErrorAction SilentlyContinue
if ($Cmd) {
  Write-Host "[ci_check.ps1] using console script: balanceops-ci-check"
  balanceops-ci-check @Args
  exit $LASTEXITCODE
}

# 2) python -m fallback: .venv > python
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonExe = "python"
if (Test-Path $VenvPython) {
  Write-Host "[ci_check.ps1] using venv python: $VenvPython"
  $PythonExe = $VenvPython
} else {
  Write-Host "[ci_check.ps1] using python on PATH"
}

& $PythonExe -m balanceops.tools.ci_check @Args
exit $LASTEXITCODE
