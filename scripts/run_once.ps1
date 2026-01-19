param()

Set-Location (Split-Path $PSScriptRoot -Parent)

# 레포가 없으면 자동으로 git init (git 설치돼있다는 전제)
if (-not (Test-Path ".git")) {
  git init | Out-Null
  git branch -M main 2>$null
}

python -m balanceops.tracking.init_db
python -m balanceops.pipeline.demo_run
