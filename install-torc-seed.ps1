[CmdletBinding()]
param(
    [string]$LugosRoot = 'C:\Users\Matt\Desktop\MyDocs\lugos',
    [string]$RepoUrl = 'https://github.com/mdn87/torc.git',
    [string]$TargetName = 'torc'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$seedRoot = Join-Path $packageRoot 'repo'
$target = Join-Path $LugosRoot $TargetName

if (-not (Test-Path -LiteralPath $seedRoot -PathType Container)) {
    throw "Seed directory not found: $seedRoot"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git is not available on PATH.'
}

if (-not (Test-Path -LiteralPath $LugosRoot -PathType Container)) {
    throw "Lugos root does not exist: $LugosRoot"
}

if (-not (Test-Path -LiteralPath $target)) {
    Write-Host "Cloning $RepoUrl into $target"
    & git clone $RepoUrl $target
    if ($LASTEXITCODE -ne 0) {
        throw "git clone failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $target '.git'))) {
    throw "Target exists but is not a Git repository: $target"
}

$tracked = @(& git -C $target ls-files)
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect tracked files in the target repository.'
}

$working = @(& git -C $target status --porcelain)
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect target repository status.'
}

if ($tracked.Count -gt 0 -or $working.Count -gt 0) {
    throw "Target repository is already populated or dirty. Seed copy was not attempted: $target"
}

Get-ChildItem -LiteralPath $seedRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force
}

Write-Host ''
Write-Host 'TORC seed copied successfully.'
Write-Host "Repository: $target"
Write-Host ''
Write-Host 'Next:'
Write-Host "  Set-Location '$target'"
Write-Host '  git status'
Write-Host '  Open Codex in this repository.'
Write-Host '  Paste docs/prompts/CODEX_BOOTSTRAP_PROMPT.md as the task.'
Write-Host ''
Write-Host 'The installer did not commit, push, or edit the parent Lugos repository.'
