param(
  [string]$CsvPath = "",
  [string]$TargetCol = "",
  [double]$TestSize = 0.2,
  [int]$Seed = 42
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PyArgs = @("-m","balanceops.pipeline.train_tabular_baseline","--test-size",$TestSize,"--seed",$Seed)

if ($CsvPath -and $TargetCol) {
  $PyArgs += @("--csv-path",$CsvPath,"--target-col",$TargetCol)
}

if (Test-Path $VenvPython) {
  & $VenvPython @PyArgs
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3.12 @PyArgs
} else {
  python @PyArgs
}
