param()

Set-Location (Split-Path $PSScriptRoot -Parent)

$env:PYTHONPATH = (Get-Location).Path

python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
