param(
  [string]$CsvPath = "",
  [string]$TargetCol = "",
  [double]$TestSize = 0.2,
  [int]$Seed = 42
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# 인자가 없으면 데모 CSV 자동 생성
if (-not $CsvPath -and -not $TargetCol) {
  $DemoDir = Join-Path $RepoRoot ".ci\datasets"
  New-Item -ItemType Directory -Force -Path $DemoDir | Out-Null

  $DemoPath = Join-Path $DemoDir "toy_binary.csv"
  $csv = @"
f1,f2,y
1,10,0
2,9,0
3,8,0
4,7,1
5,6,1
6,5,1
"@
  Set-Content -Path $DemoPath -Value $csv -Encoding utf8

  $CsvPath = $DemoPath
  $TargetCol = "y"

  Write-Host "[train_tabular_baseline] demo csv generated: $DemoPath"
}

if (-not ($CsvPath -and $TargetCol)) {
  throw "CsvPath와 TargetCol을 함께 지정해야 합니다. 예) .\scripts\train_tabular_baseline.ps1 -CsvPath .\data\toy.csv -TargetCol y"
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PyArgs = @(
  "-m","balanceops.pipeline.train_tabular_baseline",
  "--test-size",$TestSize,
  "--seed",$Seed,
  "--csv-path",$CsvPath,
  "--target-col",$TargetCol
)

if (Test-Path $VenvPython) {
  & $VenvPython @PyArgs
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3.12 @PyArgs
} else {
  python @PyArgs
}
