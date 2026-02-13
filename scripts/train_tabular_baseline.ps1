param(
  # (옵션) Dataset Spec(JSON)로 실행
  [string]$DatasetSpec = "",
  [string]$DatasetName = "",

  # (옵션) CSV 직접 지정
  [string]$CsvPath = "",
  [string]$TargetCol = "",

  # 공통 옵션
  [string]$Sep = ",",
  [switch]$NoOneHot,
  [switch]$NoDropna,

  [double]$TestSize = 0.2,
  [int]$Seed = 42,

  # 승격 방지(안전 실행)
  [switch]$NoAutoPromote
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# dataset-spec 우선
$UseDatasetSpec = -not [string]::IsNullOrWhiteSpace($DatasetSpec)

# 인자가 없으면 데모 CSV 자동 생성(단, dataset-spec 모드가 아닐 때만)
if (-not $UseDatasetSpec -and -not $CsvPath -and -not $TargetCol) {
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

if (-not $UseDatasetSpec) {
  if (-not ($CsvPath -and $TargetCol)) {
    throw "DatasetSpec 또는 (CsvPath + TargetCol)을 지정해야 합니다.`n예) .\scripts\train_tabular_baseline.ps1 -DatasetSpec .\examples\dataset_specs\finance_credit_demo.json -NoAutoPromote`n또는 .\scripts\train_tabular_baseline.ps1 -CsvPath .\data\toy.csv -TargetCol y"
  }
}

# ---- args 구성 ----
$CommonArgs = @(
  "--seed", $Seed,
  "--test-size", $TestSize
)

if ($NoAutoPromote) { $CommonArgs += "--no-auto-promote" }

if ($UseDatasetSpec) {
  $Args = @("--dataset-spec", $DatasetSpec) + $CommonArgs
  if (-not [string]::IsNullOrWhiteSpace($DatasetName)) {
    $Args += @("--dataset-name", $DatasetName)
  }
} else {
  $Args = @(
    "--csv-path", $CsvPath,
    "--target-col", $TargetCol,
    "--sep", $Sep
  ) + $CommonArgs

  if ($NoOneHot) { $Args += "--no-one-hot" }
  if ($NoDropna) { $Args += "--no-dropna" }
}

# ---- 실행기 선택: venv CLI exe > venv python -m > py > python ----
$CliExe = Join-Path $RepoRoot ".venv\Scripts\balanceops-train-tabular-baseline.exe"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path $CliExe) {
  Write-Host "[train_tabular_baseline] using CLI: $CliExe"
  & $CliExe @Args
} else {
  $PyArgs = @("-m", "balanceops.pipeline.train_tabular_baseline") + $Args

  if (Test-Path $VenvPython) {
    Write-Host "[train_tabular_baseline] using venv python: $VenvPython"
    & $VenvPython @PyArgs
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host "[train_tabular_baseline] using py launcher"
    & py -3.12 @PyArgs
  } else {
    Write-Host "[train_tabular_baseline] using system python"
    python @PyArgs
  }
}
