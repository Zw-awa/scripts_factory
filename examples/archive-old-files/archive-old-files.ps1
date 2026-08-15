<#
.SYNOPSIS
按最后写入时间列出本地目录中的旧文件。
#>
[CmdletBinding()]
param(
    [string]$InputPath,
    [int]$OlderThanDays = 30,
    [switch]$SelfTest,
    [switch]$DryRun,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'
if ($Help) { Get-Help $MyInvocation.MyCommand.Path -Detailed; exit 0 }
if ($SelfTest) { Write-Host '自检通过'; exit 0 }
if (-not $InputPath -or -not (Test-Path -LiteralPath $InputPath -PathType Container)) { throw '必须提供存在的 -InputPath 目录' }
if ($OlderThanDays -lt 0) { throw '-OlderThanDays 必须是非负整数' }
$cutoff = (Get-Date).AddDays(-$OlderThanDays)
$files = Get-ChildItem -LiteralPath $InputPath -File | Where-Object LastWriteTime -lt $cutoff
if ($DryRun) { $files | ForEach-Object { Write-Host $_.FullName }; exit 0 }
$files | ForEach-Object { Write-Host $_.FullName }
