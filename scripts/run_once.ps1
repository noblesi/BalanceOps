param()

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# .venv 파이썬 우선 사용
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
  $Python = $VenvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $Python = "py -3.12"
} else {
  $Python = "python"
}

# 레포가 없으면 git init (git 설치 확인)
if (-not (Test-Path ".git")) {
  if (Get-Command git -ErrorAction SilentlyContinue) {
    git init | Out-Null
    git branch -M main 2>$null
  } else {
    Write-Warning "git이 설치되어 있지 않아 자동 git init을 건너뜁니다."
  }
}

# 파이프라인 실행 (venv/python으로 고정)
if ($Python -is [string] -and $Python.StartsWith("py ")) {
  & py -3.12 -m balanceops.tracking.init_db
  & py -3.12 -m balanceops.pipeline.demo_run
} else {
  & $Python -m balanceops.tracking.init_db
  & $Python -m balanceops.pipeline.demo_run
}
