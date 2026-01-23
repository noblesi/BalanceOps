param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000,
  [int]$TimeoutSec = 10,
  [switch]$FailOnPredict404 = $false
)

$ErrorActionPreference = "Stop"

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

function Invoke-Json {
  param(
    [Parameter(Mandatory = $true)][ValidateSet('GET','POST')][string]$Method,
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $false)][object]$Body = $null
  )

  $Common = @{
    Method     = $Method
    Uri        = $Url
    TimeoutSec = $TimeoutSec
    Headers    = @{ "Accept" = "application/json" }
  }

  if ($Method -eq "POST") {
    $Common["ContentType"] = "application/json"
    $Common["Body"] = ($Body | ConvertTo-Json -Compress)
  }

  return Invoke-RestMethod @Common
}

$BaseUrl = "http://{0}:{1}" -f $BindHost, $Port
Write-Host "[smoke] base_url: $BaseUrl"

# 1) /health
try {
  $Health = Invoke-Json -Method GET -Url "$BaseUrl/health"
  $HealthJson = ($Health | ConvertTo-Json -Compress)
  Write-Host "[smoke] /health OK: $HealthJson"
} catch {
  $Code = Get-HttpStatusCode -Exception $_.Exception
  if ($null -ne $Code) { Write-Error "[smoke] /health FAILED (HTTP $Code): $($_.Exception.Message)" }
  else { Write-Error "[smoke] /health FAILED: $($_.Exception.Message)" }
  exit 1
}

# 2) /predict
$Payload = @{ features = @(0.1, 0.2, -0.3, 1.0, 0.5, 0.0, -0.2, 0.9) }
try {
  $Pred = Invoke-Json -Method POST -Url "$BaseUrl/predict" -Body $Payload
  $PredJson = ($Pred | ConvertTo-Json -Compress)
  Write-Host "[smoke] /predict OK: $PredJson"
} catch {
  $Code = Get-HttpStatusCode -Exception $_.Exception

  if ($Code -eq 404) {
    $Msg = "[smoke] /predict returned 404 (current model missing?)"
    if ($FailOnPredict404) {
      Write-Error $Msg
      exit 1
    } else {
      Write-Warning $Msg
      exit 0
    }
  }

  if ($null -ne $Code) { Write-Error "[smoke] /predict FAILED (HTTP $Code): $($_.Exception.Message)" }
  else { Write-Error "[smoke] /predict FAILED: $($_.Exception.Message)" }
  exit 1
}

Write-Host "[smoke] done."
