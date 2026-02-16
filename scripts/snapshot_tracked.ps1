param(
  # 출력 파일 기본명
  [string]$Name = "BalanceOps-tracked",

  # ZIP이 저장될 디렉토리(레포 루트 기준 상대경로 가능)
  [string]$OutDir = ".ci/snapshots",

  # untracked(새 파일)도 포함하지 않으려면 -NoUntracked
  [switch]$NoUntracked,

  # 최신 스냅샷을 ${Name}_latest.zip 으로도 복사하지 않으려면 -NoLatest
  [switch]$NoLatest
)

$ErrorActionPreference = "Stop"

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function GitOut {
  param(
    [string[]]$GitArgs
  )

  if (-not $GitArgs -or $GitArgs.Count -eq 0) {
    throw "git failed: no args provided"
  }

  $out = (& git @GitArgs 2>&1 | Out-String).TrimEnd()
  $code = $LASTEXITCODE

  if ($code -ne 0) {
    $msg = "git failed: git $($GitArgs -join ' ')"
    if ($out) { $msg += "`n$out" }
    throw $msg
  }

  return $out.Trim()
}


$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$sha = (GitOut @("rev-parse","--short=7","HEAD")).Trim()

$outDirPath = $OutDir
if (-not [System.IO.Path]::IsPathRooted($outDirPath)) {
  $outDirPath = Join-Path $RepoRoot $outDirPath
}
New-Item -ItemType Directory -Force $outDirPath | Out-Null

$zipPath = Join-Path $outDirPath ("{0}_{1}_{2}.zip" -f $Name, $ts, $sha)
$latestPath = Join-Path $outDirPath ("{0}_latest.zip" -f $Name)

if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

# 포함할 파일 목록 수집
$tracked = (GitOut @("ls-files")) -split "\r?\n" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
$files = New-Object System.Collections.Generic.List[string]
foreach ($f in $tracked) { [void]$files.Add($f) }

if (-not $NoUntracked) {
  $untracked = (GitOut @("ls-files","--others","--exclude-standard")) -split "\r?\n" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
  foreach ($f in $untracked) { [void]$files.Add($f) }
}

# 중복 제거 + 정렬
$relPaths = $files.ToArray() | Sort-Object -Unique

# ZIP 생성 (.NET)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  foreach ($rel in $relPaths) {
    $src = Join-Path $RepoRoot $rel
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { continue }

    # ZIP 내부 경로는 / 로 통일
    $entryName = ($rel -replace "\\","/")
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
      $zip,
      $src,
      $entryName,
      [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
  }
} finally {
  $zip.Dispose()
}

if (-not $NoLatest) {
  Copy-Item -Force $zipPath $latestPath
}

Write-Host "[snapshot] repo: $($RepoRoot.Path)"
Write-Host "[snapshot] head: $sha"
Write-Host "[snapshot] out:  $zipPath"
if (-not $NoLatest) { Write-Host "[snapshot] latest: $latestPath" }
