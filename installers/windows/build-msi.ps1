<#
.SYNOPSIS
    Build the Detec Agent MSI installer.

.DESCRIPTION
    Runs PyInstaller for both agent executables, harvests the _internal
    directories into WiX fragments, then builds DetecAgent.msi.
    Optionally uploads the MSI to a Detec server.

.PARAMETER ServerUrl
    Detec server URL for uploading the built MSI.

.PARAMETER ApiKey
    Admin API key for the upload.

.PARAMETER Version
    Version string (e.g., "0.5.0"). Defaults to "dev".

.PARAMETER SkipPyInstaller
    Skip the PyInstaller build steps (use existing dist).
#>
param(
    [string]$ServerUrl,
    [string]$ApiKey,
    [string]$Version = "dev",
    [switch]$SkipPyInstaller
)

$ErrorActionPreference = "Stop"
$root = (Get-Item "$PSScriptRoot\..\..").FullName
$winDir = "$root\installers\windows"

if (-not $SkipPyInstaller) {
    Write-Host "=== Step 1: Install dependencies ===" -ForegroundColor Cyan
    pip install -r "$root\collector\requirements.txt" pyinstaller pywin32 pystray Pillow windows-toasts

    Write-Host "=== Step 2: Build detec-agent.exe ===" -ForegroundColor Cyan
    pyinstaller "$winDir\detec-agent.spec" --distpath "$winDir\dist" --workpath "$winDir\build" -y

    Write-Host "=== Step 3: Build detec-agent-gui.exe ===" -ForegroundColor Cyan
    pyinstaller "$winDir\detec-agent-gui.spec" --distpath "$winDir\dist" --workpath "$winDir\build" -y
} else {
    Write-Host "=== Skipping PyInstaller (using existing dist) ===" -ForegroundColor Yellow
}

Write-Host "=== Step 4: Harvest _internal directories ===" -ForegroundColor Cyan
Push-Location $winDir

# Harvest agent _internal (all DLLs, PYDs, data files PyInstaller bundles)
powershell -File harvest.ps1 `
    -SourceDir "dist\detec-agent\_internal" `
    -ComponentGroupId "AgentInternalFiles" `
    -DirectoryRefId "AGENTINTERNALDIR" `
    -SourceVar "AgentInternalDir" `
    -OutputFile "AgentInternal.wxs"

# Harvest GUI _internal
powershell -File harvest.ps1 `
    -SourceDir "dist\detec-agent-gui\_internal" `
    -ComponentGroupId "GuiInternalFiles" `
    -DirectoryRefId "GUIINTERNALDIR" `
    -SourceVar "GuiInternalDir" `
    -OutputFile "GuiInternal.wxs"

Write-Host "=== Step 5: Build MSI ===" -ForegroundColor Cyan
wix build DetecAgent.wxs AgentInternal.wxs GuiInternal.wxs `
    -arch x64 `
    -d AgentInternalDir="dist\detec-agent\_internal" `
    -d GuiInternalDir="dist\detec-agent-gui\_internal" `
    -o "dist\DetecAgent.msi"

Pop-Location

$msiPath = "$winDir\dist\DetecAgent.msi"
if (-not (Test-Path $msiPath)) {
    Write-Error "MSI build failed - $msiPath not found"
    exit 1
}

$size = [math]::Round((Get-Item $msiPath).Length / 1MB, 1)
Write-Host "MSI built: $msiPath ($size MB)" -ForegroundColor Green

if ($ServerUrl -and $ApiKey) {
    Write-Host "=== Step 6: Upload to server ===" -ForegroundColor Cyan
    curl.exe -X POST "$ServerUrl/api/agent-builds" `
        -H "X-Api-Key: $ApiKey" `
        -F "file=@$msiPath" `
        -F "version=$Version"
    Write-Host "Upload complete." -ForegroundColor Green
} else {
    Write-Host "Skipping upload (no -ServerUrl / -ApiKey provided)." -ForegroundColor Yellow
}
