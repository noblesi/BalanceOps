param()

Set-Location (Split-Path $PSScriptRoot -Parent)

python -m balanceops.tracking.init_db
python -m balanceops.pipeline.demo_run
