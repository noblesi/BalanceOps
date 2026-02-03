param(
  # e2e에서 사용할 포트 (기본 8010: 로컬 8000 서버와 충돌 방지)
  [int]$Port = 8010,

  # e2e는 시간이 좀 걸릴 수 있으니 필요시 스킵 옵션
  [switch]$SkipE2E = $false
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot

function Resolve-Tool {
  param(
    [Parameter(Mandatory = $true)][string]$VenvPath,
    [Parameter(Mandatory = $true)][string]$FallbackName
  )

  if (Test-Path $VenvPath) { return $VenvPath }

  $Cmd = Get-Command $FallbackName -ErrorAction SilentlyContinue
  if ($null -ne $Cmd) { return $FallbackName }

  return $null
}

try {
  # CI와 동일한 실행 경로로 고정 (로컬 data/, artifacts/ 오염 방지)
  $env:BALANCEOPS_DB = (Join-Path $RepoRoot ".ci/balanceops.db")
  $env:BALANCEOPS_ARTIFACTS = (Join-Path $RepoRoot ".ci/artifacts")
  $env:BALANCEOPS_CURRENT_MODEL = (Join-Path $RepoRoot ".ci/artifacts/models/current.joblib")
  $env:PYTHONUNBUFFERED = "1"

  New-Item -ItemType Directory -Force (Join-Path $RepoRoot ".ci") | Out-Null

  $RuffExe = Resolve-Tool -VenvPath (Join-Path $RepoRoot ".venv\Scripts\ruff.exe") -FallbackName "ruff"
  $PytestExe = Resolve-Tool -VenvPath (Join-Path $RepoRoot ".venv\Scripts\pytest.exe") -FallbackName "pytest"

  if ($null -eq $RuffExe) {
    throw "ruff를 찾을 수 없습니다. 먼저 'python -m pip install -e "".[dev]""' 를 실행하세요."
  }
  if ($null -eq $PytestExe) {
    throw "pytest를 찾을 수 없습니다. 먼저 'python -m pip install -e "".[dev]""' 를 실행하세요."
  }

  Write-Host "[ci_check] step 1/4: ruff format --check"
  & $RuffExe format --check .
  if ($LASTEXITCODE -ne 0) { throw "ruff format --check 실패 (exitcode=$LASTEXITCODE)" }

  Write-Host "[ci_check] step 2/4: ruff check"
  & $RuffExe check .
  if ($LASTEXITCODE -ne 0) { throw "ruff check 실패 (exitcode=$LASTEXITCODE)" }

  Write-Host "[ci_check] step 3/4: pytest"
  & $PytestExe -q
  if ($LASTEXITCODE -ne 0) { throw "pytest 실패 (exitcode=$LASTEXITCODE)" }

  if (-not $SkipE2E) {
    Write-Host "[ci_check] step 4/4: e2e"
    & (Join-Path $RepoRoot "scripts\e2e.ps1") -Port $Port
    if ($LASTEXITCODE -ne 0) { throw "e2e 실패 (exitcode=$LASTEXITCODE)" }
  } else {
    Write-Host "[ci_check] step 4/4: skip e2e"
  }

  Write-Host "[ci_check] OK"
}
finally {
  Pop-Location
}
