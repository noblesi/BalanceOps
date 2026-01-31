param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000,
  [string]$PythonVersion = "3.12",

  # smoke settings
  [int]$TimeoutSec = 8,
  [int]$Retries = 30,
  [double]$RetryDelaySec = 0.5,

  # behavior
  [switch]$SkipTrain = $false,
  [switch]$SkipServe = $false
)

$ErrorActionPreference = "Stop"

function Resolve-PythonInvocation {
  param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$PythonVersion
  )

  $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path $VenvPython) {
    return [pscustomobject]@{ Kind = "venv"; FilePath = $VenvPython; PrefixArgs = @() }
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    return [pscustomobject]@{ Kind = "py"; FilePath = "py"; PrefixArgs = @("-$PythonVersion") }
  }

  return [pscustomobject]@{ Kind = "python"; FilePath = "python"; PrefixArgs = @() }
}

function Get-CurrentModelPath {
  param(
    [Parameter(Mandatory = $true)][psobject]$Py,
    [Parameter(Mandatory = $true)][string]$RepoRoot
  )

  $Code = "from balanceops.common.config import get_settings; print(get_settings().current_model_path)"
  $Args = @()
  $Args += $Py.PrefixArgs
  $Args += @("-c", $Code)

  $Out = & $Py.FilePath @Args
  if ($LASTEXITCODE -ne 0) {
    throw "failed to read Settings via python (exitcode=$LASTEXITCODE)"
  }

  $Line = ($Out | Select-Object -First 1)
  if ($null -eq $Line) { throw "failed to read current_model_path (empty output)" }

  $Path = $Line.ToString().Trim()
  if ([string]::IsNullOrWhiteSpace($Path)) { throw "failed to read current_model_path (blank)" }

  if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }
  return (Join-Path $RepoRoot $Path)
}

function Ensure-CurrentModel {
  param(
    [Parameter(Mandatory = $true)][psobject]$Py,
    [Parameter(Mandatory = $true)][string]$RepoRoot
  )

  $CurPath = Get-CurrentModelPath -Py $Py -RepoRoot $RepoRoot
  if (Test-Path $CurPath) { return $true }

  Write-Warning "[e2e] current model not found: $CurPath"
  Write-Host "[e2e] trying manual promote of latest run..."
  & (Join-Path $RepoRoot "scripts\promote.ps1") -Latest

  return (Test-Path $CurPath)
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
$ServerProc = $null

try {
  # import 안정화 (레포 루트 + src)
  $env:PYTHONPATH = "{0};{1}" -f $RepoRoot.Path, (Join-Path $RepoRoot "src")

  Write-Host "[e2e] repo_root: $($RepoRoot.Path)"
  Write-Host "[e2e] host: $BindHost  port: $Port"

  # 1) init_db
  Write-Host "[e2e] step 1/4: init_db"
  & (Join-Path $RepoRoot "scripts\init_db.ps1") -PythonVersion $PythonVersion

  # 2) train_dummy (optional)
  if (-not $SkipTrain) {
    Write-Host "[e2e] step 2/4: train_dummy (auto-promote)"
    & (Join-Path $RepoRoot "scripts\train_dummy.ps1")
  } else {
    Write-Host "[e2e] step 2/4: skip train_dummy"
  }

  # 3) ensure current exists
  Write-Host "[e2e] step 3/4: ensure current model"
  $Py = Resolve-PythonInvocation -RepoRoot $RepoRoot.Path -PythonVersion $PythonVersion
  if (-not (Ensure-CurrentModel -Py $Py -RepoRoot $RepoRoot.Path)) {
    throw "current model still missing. Run .\scripts\train_dummy.ps1 or .\scripts\promote.ps1 -Latest"
  }
  $CurPath = Get-CurrentModelPath -Py $Py -RepoRoot $RepoRoot.Path
  Write-Host "[e2e] current model OK: $CurPath"

  if ($SkipServe) {
    Write-Host "[e2e] step 4/4: skip serve+smoke"
    Write-Host "[e2e] done."
    exit 0
  }

  # 4) serve (background) + smoke_http
  Write-Host "[e2e] step 4/4: serve (background) + smoke_http"

  $UvicornArgs = @()
  $UvicornArgs += $Py.PrefixArgs
  $UvicornArgs += @(
    "-m", "uvicorn",
    "apps.api.main:app",
    "--host", $BindHost,
    "--port", "$Port"
  )

  Write-Host "[e2e] starting api: $($Py.FilePath) $($UvicornArgs -join ' ')"
  $ServerProc = Start-Process -FilePath $Py.FilePath -ArgumentList $UvicornArgs -WorkingDirectory $RepoRoot.Path -PassThru -NoNewWindow

  Start-Sleep -Milliseconds 200
  if ($ServerProc.HasExited) {
    throw "api server exited immediately (exitcode=$($ServerProc.ExitCode)). Is the port in use?"
  }

  # smoke_http.ps1 내부의 exit가 부모 스크립트를 종료시키지 않도록 별도 프로세스로 실행
  $ShellExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
  $SmokeScript = Join-Path $RepoRoot "scripts\smoke_http.ps1"

  $SmokeArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $SmokeScript,
    "-BindHost", $BindHost,
    "-Port", "$Port",
    "-TimeoutSec", "$TimeoutSec",
    "-Retries", "$Retries",
    "-RetryDelaySec", "$RetryDelaySec",
    "-FailOnPredict404"
  )

  & $ShellExe @SmokeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "smoke_http failed (exitcode=$LASTEXITCODE)"
  }

  Write-Host "[e2e] OK"
}
finally {
  if ($null -ne $ServerProc) {
    try {
      if (-not $ServerProc.HasExited) {
        Write-Host "[e2e] stopping api server (pid=$($ServerProc.Id))"
        Stop-Process -Id $ServerProc.Id -Force
      }
    } catch {
      Write-Warning "[e2e] failed to stop api server: $($_.Exception.Message)"
    }
  }
  Pop-Location
}
