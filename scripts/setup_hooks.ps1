param()

$ErrorActionPreference = "Stop"

# 레포 루트로 이동 (scripts/ 기준)
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

# hooksPath를 레포 내부 .githooks로 설정 (로컬 git config)
git config core.hooksPath .githooks

Write-Host "[hooks] core.hooksPath set to .githooks"
Write-Host "[hooks] pre-push hook enabled."
Write-Host "[hooks] skip: git push --no-verify  OR  `$env:BALANCEOPS_SKIP_PRE_PUSH='1'; git push"
