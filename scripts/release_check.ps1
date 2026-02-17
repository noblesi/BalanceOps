param(
  # 예: v0.1.1, v1.2.3
  [Parameter(Mandatory = $true)]
  [string]$Tag,

  [string]$Remote = "origin",
  [string]$Branch = "main",

  # 원격 fetch 생략(오프라인/권한 문제일 때)
  [switch]$LocalOnly,

  # 워킹트리 변경 있어도 통과(권장 X)
  [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

# 콘솔 출력 인코딩(한글 출력 안정화)
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

# 레포 루트로 이동
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Run_Git([string[]]$GitArgs) {
  $old = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $out = (& git @GitArgs 2>&1 | Out-String).TrimEnd()
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $old
  }
  return [pscustomobject]@{ Code = $code; Output = $out }
}

function Fail([string]$msg) {
  Write-Host ""
  Write-Host "[release_check] ERROR: $msg"
  exit 1
}

Write-Host "[release_check] repo: $($RepoRoot.Path)"
Write-Host "[release_check] tag:  $Tag"
Write-Host "[release_check] remote/branch: $Remote/$Branch"
Write-Host "[release_check] local_only: " + ($(if ($LocalOnly) { "1" } else { "0" }))

# 1) 워킹트리 깨끗한지 확인
$porcelain = Run_Git @("status","--porcelain")
if ($porcelain.Code -ne 0) { Fail "git status 실패" }

if (-not $AllowDirty -and $porcelain.Output) {
  Write-Host ""
  Write-Host $porcelain.Output
  Fail "워킹트리에 변경이 있습니다. 커밋/스태시 후 다시 시도하세요. (또는 -AllowDirty)"
}

# 2) HEAD commit
$head = Run_Git @("rev-parse","HEAD")
if ($head.Code -ne 0 -or -not $head.Output) { Fail "HEAD 해시를 읽지 못했습니다." }
$HeadSha = $head.Output.Trim()
Write-Host "[release_check] HEAD: $HeadSha"

# 3) 원격 fetch + ahead/behind (가능하면)
if (-not $LocalOnly) {
  $fetch = Run_Git @("fetch",$Remote,"--tags")
  if ($fetch.Code -ne 0) {
    Write-Host "[release_check] WARN: fetch 실패 -> 로컬 기준으로만 검사합니다."
    if ($fetch.Output) { Write-Host $fetch.Output }
  } else {
    $upstream = "$Remote/$Branch"
    $verify = Run_Git @("rev-parse","--verify",$upstream)
    if ($verify.Code -eq 0) {
      $ab = Run_Git @("rev-list","--left-right","--count","HEAD...$upstream")
      if ($ab.Code -eq 0 -and $ab.Output) {
        # 형식: "<left> <right>" where left=HEAD only(ahead), right=upstream only(behind)
        $parts = $ab.Output.Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
        if ($parts.Count -ge 2) {
          $ahead = [int]$parts[0]
          $behind = [int]$parts[1]
          Write-Host "[release_check] ahead/behind vs $upstream: $ahead/$behind"
          if ($behind -gt 0) {
            Fail "로컬이 원격보다 뒤쳐져 있습니다(behind=$behind). pull/rebase 후 태그를 찍으세요."
          }
        }
      }
    }
  }
}

# 4) 로컬 태그 존재 여부 + 태그 커밋이 HEAD인지 확인
$localTag = Run_Git @("rev-parse","-q","--verify","refs/tags/$Tag")
$localTagExists = ($localTag.Code -eq 0 -and $localTag.Output)

if ($localTagExists) {
  # annotated tag도 커밋으로 deref
  $tagCommit = Run_Git @("rev-list","-n","1",$Tag)
  if ($tagCommit.Code -ne 0 -or -not $tagCommit.Output) {
    Fail "로컬 태그는 있는데($Tag) 커밋을 해석하지 못했습니다."
  }

  $TagSha = $tagCommit.Output.Trim()
  Write-Host "[release_check] local tag exists: $Tag -> $TagSha"

  if ($TagSha -ne $HeadSha) {
    Write-Host ""
    Write-Host "태그가 HEAD에 찍혀있지 않습니다."
    Write-Host "  tag:  $TagSha"
    Write-Host "  HEAD: $HeadSha"
    Write-Host ""
    Write-Host "해결 옵션:"
    Write-Host "  (A) 태그를 HEAD로 다시 찍기(릴리스 전/팀 합의 필요):"
    Write-Host "      git tag -d $Tag"
    Write-Host "      git tag -a $Tag -m `"$Tag`""
    Write-Host "      git push -f $Remote $Tag"
    Write-Host "  (B) 다음 버전으로 새 태그 만들기(보수적):"
    Write-Host "      git tag -a vX.Y.(Z+1) -m `"vX.Y.(Z+1)`""
    Fail "태그/HEAD 불일치"
  }
} else {
  Write-Host "[release_check] local tag not found: $Tag (OK: 태그 생성 전 검사)"
}

# 5) 원격 태그 존재하면 HEAD와 일치하는지 확인(가능하면)
if (-not $LocalOnly) {
  $remoteTag = Run_Git @("ls-remote","--tags",$Remote,"refs/tags/$Tag")
  if ($remoteTag.Code -eq 0 -and $remoteTag.Output) {
    # 출력 예: "<sha>\trefs/tags/v0.1.0" 또는 annotated면 ^{}가 추가될 수 있음
    # 가장 마지막(=dereference ^{}) 우선
    $lines = $remoteTag.Output -split "\r?\n" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
    $sha = $null
    foreach ($ln in $lines) {
      if ($ln -match "^([0-9a-f]{7,40})\s+refs/tags/$([regex]::Escape($Tag))\^\{\}$") { $sha = $Matches[1] }
    }
    if (-not $sha) {
      foreach ($ln in $lines) {
        if ($ln -match "^([0-9a-f]{7,40})\s+refs/tags/$([regex]::Escape($Tag))$") { $sha = $Matches[1] }
      }
    }

    if ($sha) {
      Write-Host "[release_check] remote tag exists: $Tag -> $sha"
      if ($sha -ne $HeadSha -and -not $localTagExists) {
        Fail "원격에 이미 $Tag 태그가 있고(sha=$sha), 현재 HEAD와 다릅니다. 새 버전 태그를 사용하세요."
      }
    }
  }
}

Write-Host ""
Write-Host "[release_check] OK"
Write-Host "다음 단계(태그 생성/푸시):"
Write-Host "  git tag -a $Tag -m `"$Tag`""
Write-Host "  git push $Remote $Branch"
Write-Host "  git push $Remote $Tag"
