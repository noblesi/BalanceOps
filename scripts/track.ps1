param(
  [string]$Remote = "origin",
  [string]$Branch = "main",
  [switch]$LocalOnly,
  [switch]$NoReport
)

$ErrorActionPreference = "Stop"

# 기본은 리포트 저장 ON, -NoReport면 OFF
$WriteReport = -not $NoReport

# 콘솔 출력 인코딩(한글 출력 안정화)
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Run_Git([string[]]$GitArgs) {
  # PowerShell이 stderr를 "에러"로 취급해도 스크립트가 멈추지 않도록,
  # 이 함수 안에서만 ErrorActionPreference를 낮춥니다.
  $old = $ErrorActionPreference
  $ErrorActionPreference = "Continue"

  try {
    $out = (& git @GitArgs 2>&1 | Out-String).TrimEnd()
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $old
  }

  return [pscustomobject]@{
    Code   = $code
    Output = $out
  }
}

function Iso_Time {
  # 예: 2026-02-09T18:12:34+09:00
  (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportPath = Join-Path $RepoRoot ".ci/track/track_$ts.md"
$ReportLines = New-Object System.Collections.Generic.List[string]

function Emit([string]$line) {
  Write-Host $line
  if ($WriteReport) { [void]$ReportLines.Add($line) }
}

function Write-Section([string]$Title) {
  Emit ""
  Emit ("=" * 80)
  Emit $Title
  Emit ("=" * 80)
}

function EmitCmd([string]$title, [string[]]$gitArgs) {
  Emit ""
  Emit "## $title"
  Emit '```'
  $r = Run_Git $gitArgs
  if ($r.Output) { ($r.Output -split "\r?\n") | ForEach-Object { Emit $_ } }
  if ($r.Code -ne 0) { Emit "[exit=$($r.Code)]" }
  Emit '```'
  return $r.Code
}

Write-Section "BalanceOps Track"
Emit ("repo: " + $RepoRoot.Path)
Emit ("time: " + (Iso_Time))
Emit ("remote: " + $Remote)
Emit ("branch: " + $Branch)
Emit ("local_only: " + ($(if ($LocalOnly) { "1" } else { "0" })))
Emit ("write_report: " + ($(if ($WriteReport) { "1" } else { "0" })))

# 항상 로컬 변경부터 표시 (track.sh parity)
Write-Section "Local status"
EmitCmd "git status -sb" @("status","-sb") | Out-Null
EmitCmd "status porcelain (all changes)" @("status","--porcelain") | Out-Null
EmitCmd "staged diff (name-status)" @("diff","--cached","--name-status") | Out-Null
EmitCmd "unstaged diff (name-status)" @("diff","--name-status") | Out-Null
EmitCmd "added files staged only (A)" @("diff","--cached","--name-status","--diff-filter=A") | Out-Null
EmitCmd "untracked files only" @("ls-files","--others","--exclude-standard") | Out-Null
EmitCmd "recent commits (-n 10)" @("log","--oneline","--decorate","-n","10") | Out-Null

if ($LocalOnly) {
  Emit ""
  Emit "(LocalOnly 모드: 원격 fetch 생략)"
} else {
  Write-Section "Remote fetch"
  $fetch = Run_Git @("fetch", $Remote)
  if ($fetch.Code -ne 0) {
    Emit "원격 fetch 실패: $Remote"
    if ($fetch.Output) { ($fetch.Output -split "\r?\n") | ForEach-Object { Emit $_ } }
    Emit ""
    Emit "=> fallback: 로컬 변경/추가 파일 중심으로 추적합니다."
  } else {
    Emit "fetch ok: $Remote"
    $upstream = "$Remote/$Branch"

    # upstream 존재 확인
    $verify = Run_Git @("rev-parse","--verify",$upstream)
    if ($verify.Code -ne 0) {
      Emit "upstream ref가 없습니다: $upstream"
    } else {
      Write-Section "Upstream diff"
      EmitCmd "ahead/behind (HEAD...$upstream)" @("rev-list","--left-right","--count","HEAD..."+$upstream) | Out-Null
      EmitCmd "incoming commits (HEAD..$upstream)" @("log","--oneline","--decorate","--max-count","30","HEAD.."+$upstream) | Out-Null
      EmitCmd "changed files (name-status)" @("diff","--name-status","HEAD",$upstream) | Out-Null
      EmitCmd "added files only (A)" @("diff","--name-status","--diff-filter=A","HEAD",$upstream) | Out-Null
    }
  }
}

if ($WriteReport) {
  New-Item -ItemType Directory -Force (Split-Path -Parent $ReportPath) | Out-Null

  # UTF-8 with BOM(한글 깨짐 방지). 필요 없으면 $true -> $false로 바꿔도 됨.
  [System.IO.File]::WriteAllLines(
    $ReportPath,
    $ReportLines.ToArray(),
    (New-Object System.Text.UTF8Encoding($true))
  )

  Write-Host ""
  Write-Host "[track] report saved: $ReportPath"
}
