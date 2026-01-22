param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000,
  [bool]$Reload = $true,
  [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
try {
  # import 안정화 (레포 루트 + src)
  $env:PYTHONPATH = "{0};{1}" -f $RepoRoot.Path, (Join-Path $RepoRoot "src")

  # python 선택: .venv > py -3.12 > python
  $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  $UsePy = $false
  $PythonExe = "python"

  if (Test-Path $VenvPython) {
    Write-Host "[serve] using venv python: $VenvPython"
    $PythonExe = $VenvPython
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host "[serve] using py -$PythonVersion"
    $UsePy = $true
  } else {
    Write-Host "[serve] using system python"
  }

  $UvicornArgs = @(
    "apps.api.main:app",
    "--host", $BindHost,
    "--port", "$Port"
  )
  if ($Reload) { $UvicornArgs += "--reload" }

  if ($UsePy) { & py "-$PythonVersion" -m uvicorn @UvicornArgs }
  else { & $PythonExe -m uvicorn @UvicornArgs }
}
finally {
  Pop-Location
}
