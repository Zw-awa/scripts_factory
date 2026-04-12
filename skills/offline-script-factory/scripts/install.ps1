[CmdletBinding()]
param(
    [string]$SkillsDir,
    [switch]$Force,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Usage {
    @'
Usage:
  .\install.ps1 [-SkillsDir <path>] [-Force] [-Help]

Installs the offline-script-factory skill into a skills directory.

Target skills directory resolution order:
  1. -SkillsDir
  2. OFFLINE_SCRIPT_FACTORY_SKILLS_DIR
  3. $CODEX_HOME\skills
  4. $HOME\.codex\skills
'@ | Write-Host
}

function Resolve-SkillsRoot {
    param([string]$CliValue)

    if ($CliValue) {
        return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CliValue)
    }

    if ($env:OFFLINE_SCRIPT_FACTORY_SKILLS_DIR) {
        return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath(
            $env:OFFLINE_SCRIPT_FACTORY_SKILLS_DIR
        )
    }

    if ($env:CODEX_HOME) {
        return Join-Path $env:CODEX_HOME "skills"
    }

    if ($env:USERPROFILE) {
        return Join-Path (Join-Path $env:USERPROFILE ".codex") "skills"
    }

    throw "Unable to determine a skills directory. Pass -SkillsDir explicitly."
}

if ($Help) {
    Show-Usage
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$skillName = Split-Path -Leaf $skillDir

$destRoot = Resolve-SkillsRoot -CliValue $SkillsDir
$destDir = Join-Path $destRoot $skillName

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null

if (Test-Path -LiteralPath $destDir) {
    if (-not $Force) {
        throw "Refusing to overwrite existing skill: $destDir`nUse -Force to reinstall."
    }

    Remove-Item -LiteralPath $destDir -Recurse -Force
}

Copy-Item -LiteralPath $skillDir -Destination $destRoot -Recurse

Write-Host "Installed skill to: $destDir"
Write-Host "Restart or reload your agent session if it does not detect the skill immediately."
