param(
  [switch]$Global = $false
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$TemplatePath = Join-Path $RepoRoot ".gitmessage.txt"
if (-not (Test-Path $TemplatePath)) {
  throw "Commit template not found: $TemplatePath"
}

$scope = "--local"
if ($Global) { $scope = "--global" }

git config $scope commit.template $TemplatePath
git config $scope commit.cleanup strip | Out-Null

Write-Host "[commit-template] configured ($scope)"
Write-Host "  template: $TemplatePath"
Write-Host ""
Write-Host "Usage:"
Write-Host "  git commit   # template will appear in your editor"