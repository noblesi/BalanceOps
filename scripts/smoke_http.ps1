param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000,
  [int]$TimeoutSec = 10,

  # retry
  [int]$Retries = 0,
  [double]$RetryDelaySec = 0.5,

  # endpoints
  [string]$HealthPath = "/health",
  [string]$PredictPath = "/predict",

  # payload
  [double[]]$Features = @(0.1, 0.2, -0.3, 1.0, 0.5, 0.0, -0.2, 0.9),

  # behavior
  [switch]$SkipPredict = $false,
  [switch]$AllowPredictFailure = $false,
  [switch]$FailOnPredict404 = $false
)

$ErrorActionPreference = "Stop"

# PowerShell 버전에 따라 Invoke-WebRequest 옵션 지원 여부가 다름
$HasSkipHttpErrorCheck = $false
try {
  $HasSkipHttpErrorCheck = (Get-Command Invoke-WebRequest).Parameters.Keys -contains "SkipHttpErrorCheck"
} catch { }

function Get-HttpStatusCode {
  param([Parameter(Mandatory = $true)][object]$Exception)

  # PowerShell 7+: HttpResponseException
  if ($Exception.PSObject.Properties.Name -contains "Response") {
    try {
      $Resp = $Exception.Response
      if ($null -ne $Resp -and $Resp.PSObject.Properties.Name -contains "StatusCode") {
        $Code = $Resp.StatusCode
        if ($Code -is [int]) { return $Code }
        if ($Code.PSObject.Properties.Name -contains "value__") { return [int]$Code.value__ }
      }
    } catch { }
  }

  # Windows PowerShell: WebException -> HttpWebResponse
  if ($Exception.PSObject.Properties.Name -contains "Response") {
    try {
      $Resp2 = $Exception.Response
      if ($null -ne $Resp2 -and $Resp2.PSObject.Properties.Name -contains "StatusCode") {
        return [int]$Resp2.StatusCode
      }
    } catch { }
  }

  return $null
}

function Invoke-HttpJson {
  param(
    [Parameter(Mandatory = $true)][ValidateSet('GET','POST')][string]$Method,
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $false)][object]$Body = $null
  )

  $Common = @{
    Method      = $Method
    Uri         = $Url
    TimeoutSec  = $TimeoutSec
    ErrorAction = "Stop"
    Headers     = @{ "Accept" = "application/json" }
  }

  # Windows PowerShell(<=5.x)에서 필수
  if ($PSVersionTable.PSVersion.Major -lt 6) {
    $Common["UseBasicParsing"] = $true
  }

  if ($Method -eq "POST") {
    $Common["ContentType"] = "application/json"
    $Common["Body"] = ($Body | ConvertTo-Json -Compress)
  }

  if ($HasSkipHttpErrorCheck) {
    # PowerShell 7+에서 4xx/5xx도 예외 없이 StatusCode로 판단 가능
    $Common["SkipHttpErrorCheck"] = $true
  }

  try {
    $Resp = Invoke-WebRequest @Common
  } catch {
    $Code = Get-HttpStatusCode -Exception $_.Exception
    return [pscustomobject]@{
      Ok         = $false
      StatusCode = $Code
      Content    = $null
      Object     = $null
      Error      = $_.Exception.Message
    }
  }

  $Status = [int]$Resp.StatusCode
  $Obj = $null
  if ($null -ne $Resp.Content -and $Resp.Content.Trim().Length -gt 0) {
    try {
      $Obj = ($Resp.Content | ConvertFrom-Json)
    } catch {
      $Obj = $Resp.Content
    }
  }

  return [pscustomobject]@{
    Ok         = ($Status -ge 200 -and $Status -lt 300)
    StatusCode = $Status
    Content    = $Resp.Content
    Object     = $Obj
    Error      = $null
  }
}

function Invoke-WithRetry {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][scriptblock]$Action,
    [int[]]$NoRetryCodes = @()
  )

  $Max = [Math]::Max(1, ($Retries + 1))
  $Last = $null

  for ($Attempt = 1; $Attempt -le $Max; $Attempt++) {
    $Res = & $Action
    $Last = $Res

    if ($null -eq $Res) {
      $Res = [pscustomobject]@{ Ok = $false; StatusCode = $null; Content = $null; Object = $null; Error = "null response" }
      $Last = $Res
    }

    if ($Res.Ok) { return $Res }

    if (($NoRetryCodes -contains $Res.StatusCode) -or ($Attempt -ge $Max)) {
      return $Res
    }

    $CodeText = if ($null -ne $Res.StatusCode) { "HTTP $($Res.StatusCode)" } else { "no-status" }
    $ErrText = if ($null -ne $Res.Error) { $Res.Error } else { "request failed" }
    Write-Warning "[smoke] $Name attempt $Attempt/$Max failed ($CodeText): $ErrText. retry in ${RetryDelaySec}s"
    Start-Sleep -Seconds $RetryDelaySec
  }

  return $Last
}

$BaseUrl = "http://{0}:{1}" -f $BindHost, $Port
Write-Host "[smoke] base_url: $BaseUrl"
Write-Host "[smoke] timeout_sec: $TimeoutSec, retries: $Retries, retry_delay_sec: $RetryDelaySec"

# 1) /health
$Health = Invoke-WithRetry -Name "GET $HealthPath" -NoRetryCodes @(404) -Action {
  Invoke-HttpJson -Method GET -Url "$BaseUrl$HealthPath"
}

if (-not $Health.Ok) {
  $CodeText = if ($null -ne $Health.StatusCode) { "HTTP $($Health.StatusCode)" } else { "no-status" }
  $ErrText = if ($null -ne $Health.Error) { $Health.Error } else { "request failed" }
  Write-Error "[smoke] $HealthPath FAILED ($CodeText): $ErrText"
  exit 1
}

$HealthOut = if ($null -ne $Health.Object) { ($Health.Object | ConvertTo-Json -Compress) } else { $Health.Content }
Write-Host "[smoke] $HealthPath OK (HTTP $($Health.StatusCode)): $HealthOut"

if ($SkipPredict) {
  Write-Host "[smoke] skip predict."
  Write-Host "[smoke] done."
  exit 0
}

# 2) /predict
$Payload = @{ features = $Features }
$Pred = Invoke-WithRetry -Name "POST $PredictPath" -NoRetryCodes @(404) -Action {
  Invoke-HttpJson -Method POST -Url "$BaseUrl$PredictPath" -Body $Payload
}

if ($Pred.Ok) {
  $PredOut = if ($null -ne $Pred.Object) { ($Pred.Object | ConvertTo-Json -Compress) } else { $Pred.Content }
  Write-Host "[smoke] $PredictPath OK (HTTP $($Pred.StatusCode)): $PredOut"
  Write-Host "[smoke] done."
  exit 0
}

if ($Pred.StatusCode -eq 404) {
  $Msg = "[smoke] $PredictPath returned 404 (current model missing?)"
  if ($FailOnPredict404) {
    Write-Error $Msg
    exit 1
  }
  Write-Warning $Msg
  exit 0
}

$CodeText = if ($null -ne $Pred.StatusCode) { "HTTP $($Pred.StatusCode)" } else { "no-status" }
$ErrText = if ($null -ne $Pred.Error) { $Pred.Error } else { "request failed" }
$ErrMsg = "[smoke] $PredictPath FAILED ($CodeText): $ErrText"

if ($AllowPredictFailure) {
  Write-Warning $ErrMsg
  exit 0
}

Write-Error $ErrMsg
exit 1
