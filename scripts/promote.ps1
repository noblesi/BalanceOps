param(
  [string]$RunId = "",
  [switch]$Latest = $false,
  [string]$Name = "balance_model",
  [string]$ModelPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $RepoRoot
try {
  $env:PYTHONPATH = "{0};{1}" -f $RepoRoot.Path, (Join-Path $RepoRoot "src")

  $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path $VenvPython) { $PythonExe = $VenvPython }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { $PythonExe = $null }
  else { $PythonExe = "python" }

  $Args = @("-m", "balanceops.registry.promote_cli")
  if ($Latest) { $Args += "--latest" }
  else { $Args += @("--run-id", $RunId) }

  if ($Name) { $Args += @("--name", $Name) }
  if ($ModelPath) { $Args += @("--model-path", $ModelPath) }

  if ($PythonExe -eq $null) { & py -3.12 @Args }
  else { & $PythonExe @Args }
}
finally {
  Pop-Location
}
