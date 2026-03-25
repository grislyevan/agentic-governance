<#
.SYNOPSIS
    Build the Detec Agent MSI installer.

.DESCRIPTION
    Runs PyInstaller for both agent executables, then WiX to produce DetecAgent.msi.
    Optionally uploads the MSI to a Detec server.

.PARAMETER ServerUrl
    Detec server URL for uploading the built MSI.

.PARAMETER ApiKey
    Admin API key for the upload.

.PARAMETER Version
    Version string (e.g., "0.5.0"). Defaults to "dev".
#>
param(
    [string]$ServerUrl,
    [string]$ApiKey,
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"
$root = (Get-Item "$PSScriptRoot\..\..").FullName

Write-Host "=== Step 1: Install dependencies ===" -ForegroundColor Cyan
pip install -r "$root\collector\requirements.txt" pyinstaller pywin32 pystray Pillow windows-toasts

Write-Host "=== Step 2: Build detec-agent.exe ===" -ForegroundColor Cyan
pyinstaller "$root\installers\windows\detec-agent.spec" --distpath "$root\installers\windows\dist" --workpath "$root\installers\windows\build" -y

Write-Host "=== Step 3: Build detec-agent-gui.exe ===" -ForegroundColor Cyan
pyinstaller "$root\installers\windows\detec-agent-gui.spec" --distpath "$root\installers\windows\dist" --workpath "$root\installers\windows\build" -y

Write-Host "=== Step 4: Build MSI ===" -ForegroundColor Cyan
Push-Location "$root\installers\windows"
wix build DetecAgent.wxs -o "dist\DetecAgent.msi"
Pop-Location

$msiPath = "$root\installers\windows\dist\DetecAgent.msi"
if (-not (Test-Path $msiPath)) {
    Write-Error "MSI build failed - $msiPath not found"
    exit 1
}

Write-Host "MSI built: $msiPath" -ForegroundColor Green

if ($ServerUrl -and $ApiKey) {
    Write-Host "=== Step 5: Upload to server ===" -ForegroundColor Cyan
    curl.exe -X POST "$ServerUrl/api/agent-builds" `
        -H "X-Api-Key: $ApiKey" `
        -F "file=@$msiPath" `
        -F "version=$Version"
    Write-Host "Upload complete." -ForegroundColor Green
} else {
    Write-Host "Skipping upload (no -ServerUrl / -ApiKey provided)." -ForegroundColor Yellow
    Write-Host "To upload manually: curl -X POST <server>/api/agent-builds -H 'X-Api-Key: <key>' -F file=@$msiPath -F version=$Version"
}
