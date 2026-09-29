param([switch]$InstallNSIS)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $PSScriptRoot 'CodeBridge.nsi'
$Desktop = [Environment]::GetFolderPath('Desktop')
$Output = Join-Path $PSScriptRoot 'dist\CodeBridge-Setup.exe'
$HashOutput = Join-Path $PSScriptRoot 'dist\CodeBridge-Setup.sha256'
$PayloadTools = Join-Path $PSScriptRoot 'payload\tools'
$VersionFile = Join-Path $Root 'version.json'
$VersionInclude = Join-Path $PSScriptRoot 'version.nsh'

if (-not (Test-Path $VersionFile)) {
    throw "version.json nao encontrado: $VersionFile"
}
$VersionData = Get-Content -Raw -LiteralPath $VersionFile | ConvertFrom-Json
$AppVersion = [string]$VersionData.version
$FileVersion = [string]$VersionData.windows_file_version
if ([string]::IsNullOrWhiteSpace($AppVersion) -or [string]::IsNullOrWhiteSpace($FileVersion)) {
    throw 'version.json invalido'
}
$VersionNsh = @(
    "!define APP_VERSION `"$AppVersion`""
    "!define APP_FILE_VERSION `"$FileVersion`""
) -join [Environment]::NewLine
[IO.File]::WriteAllText(
    $VersionInclude,
    $VersionNsh + [Environment]::NewLine,
    (New-Object Text.UTF8Encoding($false))
)

$RegistryProgramFiles = $null
$RegistryProgramFilesX86 = $null
try {
    $ProgramFilesReg = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion'
    $RegistryProgramFiles = [string]$ProgramFilesReg.ProgramFilesDir
    $RegistryProgramFilesX86 = [string]$ProgramFilesReg.'ProgramFilesDir (x86)'
}
catch {
}

$Candidates = @(
    "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
    "$env:ProgramFiles\NSIS\makensis.exe",
    "$RegistryProgramFilesX86\NSIS\makensis.exe",
    "$RegistryProgramFiles\NSIS\makensis.exe",
    "$env:LOCALAPPDATA\Programs\NSIS\makensis.exe"
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
$MakeNSIS = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $MakeNSIS -and $InstallNSIS) {
    winget install --id NSIS.NSIS -e --source winget --accept-package-agreements --accept-source-agreements
    $MakeNSIS = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $MakeNSIS) {
    throw 'NSIS nao encontrado. Execute novamente com -InstallNSIS.'
}

$LocalTools = Join-Path $env:LOCALAPPDATA 'CodeBridge-MCP-Bridge\tools'
$TunnelClient = Join-Path $LocalTools 'tunnel-client.exe'
$Cloudflared = Join-Path $LocalTools 'cloudflared.exe'
if (-not (Test-Path $TunnelClient)) { throw "tunnel-client.exe nao encontrado: $TunnelClient" }
if (-not (Test-Path $Cloudflared)) { throw "cloudflared.exe nao encontrado: $Cloudflared" }

New-Item -ItemType Directory -Force -Path $PayloadTools | Out-Null
Copy-Item $TunnelClient (Join-Path $PayloadTools 'tunnel-client.exe') -Force
Copy-Item $Cloudflared (Join-Path $PayloadTools 'cloudflared.exe') -Force
New-Item -ItemType Directory -Force -Path (Split-Path $Output -Parent) | Out-Null

Push-Location $PSScriptRoot
try {
    & $MakeNSIS /V3 /INPUTCHARSET UTF8 $Script
    if ($LASTEXITCODE -ne 0) { throw "makensis falhou com exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

if (-not (Test-Path $Output)) { throw "Instalador nao foi criado em $Output" }

$Hash = Get-FileHash $Output -Algorithm SHA256
$HashLine = "$($Hash.Hash.ToLowerInvariant())  CodeBridge-Setup.exe"
[IO.File]::WriteAllText($HashOutput, $HashLine + [Environment]::NewLine, [Text.Encoding]::ASCII)

$DesktopOutput = Join-Path $Desktop 'CodeBridge-Setup.exe'
Copy-Item $Output $DesktopOutput -Force

Write-Host 'INSTALADOR_OK'
Write-Host "Repo: $Output"
Write-Host "Hash file: $HashOutput"
Write-Host "Desktop: $DesktopOutput"
Write-Host "SHA256: $($Hash.Hash)"
