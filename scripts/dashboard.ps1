param()

Set-Location (Split-Path $PSScriptRoot -Parent)

# 레포 루트를 import 경로에 추가
$env:PYTHONPATH = (Get-Location).Path

python -m streamlit run apps/dashboard/app.py
