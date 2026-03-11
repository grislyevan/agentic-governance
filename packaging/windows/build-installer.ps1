# Build the Detec Server installer (DetecServerSetup.exe)
#
# Runs the full pipeline:
#   1. Install Python build dependencies
#   2. Build the React dashboard
#   3. Build detec-server.exe via PyInstaller
#   4. Build detec-agent.exe (headless service) via PyInstaller
#   5. Build detec-agent-gui.exe (tray app) via PyInstaller
#   6. Generate installer branding assets
#   7. Compile the agent installer (DetecAgentSetup.exe) via Inno Setup
#   8. Bundle agent packages for server-side download
#   9. Compile the server installer (DetecServerSetup.exe) via Inno Setup
#
# Prerequisites:
#   - Python 3.11+ on PATH
#   - Node.js 20.19+ or 22+ on PATH
#   - Inno Setup 6 installed (iscc.exe on PATH or in default location)
#
# Optional:
#   Place a macOS .pkg in packaging/windows/dist/detec-server/dist/packages/
#   before running this script. Only buildable on macOS, so it must be copied
#   manually from a macOS build machine.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
#
# Output:
#   packaging\windows\dist\DetecServerSetup-<version>.exe
#   packaging\windows\dist\DetecAgentSetup-<version>.exe

$ErrorActionPreference = "Stop"

$RepoRoot     = (Resolve-Path "$PSScriptRoot\..\..").Path
$ApiDir       = "$RepoRoot\api"
$DashboardDir = "$RepoRoot\dashboard"
$PackagingDir = "$RepoRoot\packaging\windows"
$InstallerDir = "$PackagingDir\installer"
$DistDir      = "$PackagingDir\dist"

Write-Host ""
Write-Host "  Detec Server Installer Build" -ForegroundColor Cyan
Write-Host "  =============================" -ForegroundColor Cyan
Write-Host ""

# ── Locate Inno Setup compiler ───────────────────────────────────────────

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $defaultIscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultIscc) {
        $iscc = $defaultIscc
    } else {
        Write-Host "ERROR: Inno Setup 6 not found." -ForegroundColor Red
        Write-Host "  Install from https://jrsoftware.org/isdl.php" -ForegroundColor Red
        Write-Host "  or add iscc.exe to PATH." -ForegroundColor Red
        exit 1
    }
} else {
    $iscc = $iscc.Source
}
Write-Host "[0/9] Inno Setup found: $iscc" -ForegroundColor Green

# ── Step 1: Python dependencies ──────────────────────────────────────────

Write-Host "`n[1/9] Installing Python dependencies..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
pip install -r "$ApiDir\requirements.txt" 2>&1 | Out-Null
pip install pyinstaller pywin32 Pillow pystray 2>&1 | Out-Null
Push-Location $RepoRoot
pip install -e . 2>&1 | Out-Null
Pop-Location
$ErrorActionPreference = "Stop"
Write-Host "  Dependencies installed." -ForegroundColor Green

# ── Step 2: Dashboard build ──────────────────────────────────────────────

Write-Host "`n[2/9] Building dashboard..." -ForegroundColor Yellow
Push-Location $DashboardDir
$ErrorActionPreference = "Continue"
npm install --loglevel=error 2>&1 | Out-Null
npm run build 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
Pop-Location

if (-not (Test-Path "$DashboardDir\dist\index.html")) {
    Write-Host "  Dashboard build FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "  Dashboard built." -ForegroundColor Green

# ── Step 3: PyInstaller server bundle ────────────────────────────────────

Write-Host "`n[3/9] Building detec-server.exe (this takes a few minutes)..." -ForegroundColor Yellow
Push-Location $PackagingDir
$ErrorActionPreference = "Continue"
pyinstaller --clean --noconfirm detec-server.spec 2>&1 | ForEach-Object { "$_" } | Select-String -Pattern "(ERROR|completed)" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
$ErrorActionPreference = "Stop"
Pop-Location

$serverExe = "$DistDir\detec-server\detec-server.exe"
if (-not (Test-Path $serverExe)) {
    Write-Host "  PyInstaller build FAILED." -ForegroundColor Red
    exit 1
}
$sizeS = [math]::Round((Get-Item $serverExe).Length / 1MB, 1)
Write-Host "  detec-server.exe built ($sizeS MB)" -ForegroundColor Green

# ── Step 4: PyInstaller agent (headless service) ─────────────────────────

Write-Host "`n[4/9] Building detec-agent.exe..." -ForegroundColor Yellow
Push-Location $PackagingDir
$ErrorActionPreference = "Continue"
pyinstaller --clean --noconfirm detec-agent.spec 2>&1 | ForEach-Object { "$_" } | Select-String -Pattern "(ERROR|completed)" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
$ErrorActionPreference = "Stop"
Pop-Location

$agentDir = "$DistDir\detec-agent"
$agentExe = "$agentDir\detec-agent.exe"
if (-not (Test-Path $agentExe)) {
    Write-Host "  Agent build FAILED." -ForegroundColor Red
    exit 1
}
$sizeA = [math]::Round((Get-Item $agentExe).Length / 1MB, 1)
Write-Host "  detec-agent.exe built ($sizeA MB)" -ForegroundColor Green

# ── Step 5: PyInstaller agent GUI (tray app) ─────────────────────────────

Write-Host "`n[5/9] Building detec-agent-gui.exe..." -ForegroundColor Yellow
Push-Location $PackagingDir
$ErrorActionPreference = "Continue"
pyinstaller --clean --noconfirm detec-agent-gui.spec 2>&1 | ForEach-Object { "$_" } | Select-String -Pattern "(ERROR|completed)" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
$ErrorActionPreference = "Stop"
Pop-Location

$agentGuiDir = "$DistDir\detec-agent-gui"
$agentGuiExe = "$agentGuiDir\detec-agent-gui.exe"
if (-not (Test-Path $agentGuiExe)) {
    Write-Host "  Agent GUI build FAILED." -ForegroundColor Red
    exit 1
}
$sizeG = [math]::Round((Get-Item $agentGuiExe).Length / 1MB, 1)
Write-Host "  detec-agent-gui.exe built ($sizeG MB)" -ForegroundColor Green

# ── Step 6: Installer branding assets ────────────────────────────────────

Write-Host "`n[6/9] Generating installer branding assets..." -ForegroundColor Yellow
python "$InstallerDir\generate-assets.py"

if (-not (Test-Path "$InstallerDir\wizard-image.bmp") -or -not (Test-Path "$InstallerDir\wizard-small-image.bmp")) {
    Write-Host "  Asset generation FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "  Branding assets ready." -ForegroundColor Green

# ── Step 7: Agent installer (Inno Setup) ─────────────────────────────────

Write-Host "`n[7/9] Compiling agent installer..." -ForegroundColor Yellow
Get-ChildItem "$DistDir\DetecAgentSetup-*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
& $iscc "$InstallerDir\detec-agent-setup.iss"

$agentSetupExe = Get-ChildItem "$DistDir\DetecAgentSetup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $agentSetupExe) {
    Write-Host "  Agent installer compilation FAILED." -ForegroundColor Red
    exit 1
}
$sizeAI = [math]::Round($agentSetupExe.Length / 1MB, 1)
Write-Host "  DetecAgentSetup.exe built ($sizeAI MB)" -ForegroundColor Green

# ── Step 8: Bundle agent packages into server dist ───────────────────────

Write-Host "`n[8/9] Bundling agent packages and compiling server installer..." -ForegroundColor Yellow

$pkgDir = "$DistDir\detec-server\dist\packages"
New-Item -ItemType Directory -Force -Path $pkgDir | Out-Null

# Copy the agent installer EXE (preferred download for Windows)
Copy-Item $agentSetupExe.FullName "$pkgDir\DetecAgentSetup.exe"
Write-Host "  DetecAgentSetup.exe copied to server packages." -ForegroundColor Green

# Zip the headless agent for backward-compatible / scripted deployments
$agentZip = "$pkgDir\detec-agent.zip"
if (Test-Path $agentZip) { Remove-Item $agentZip -Force }
Compress-Archive -Path "$agentDir\*" -DestinationPath $agentZip -CompressionLevel Optimal
$sizeZ = [math]::Round((Get-Item $agentZip).Length / 1MB, 1)
Write-Host "  detec-agent.zip created ($sizeZ MB)" -ForegroundColor Green

# Check for macOS .pkg (must be built on macOS and placed here manually)
$macPkgSrc = @(
    "$RepoRoot\dist\DetecAgent-latest.pkg",
    "$RepoRoot\dist\DetecAgent.pkg"
)
$macPkgFound = $false
foreach ($src in $macPkgSrc) {
    if (Test-Path $src) {
        Copy-Item $src "$pkgDir\$(Split-Path $src -Leaf)"
        Write-Host "  macOS .pkg found and included: $(Split-Path $src -Leaf)" -ForegroundColor Green
        $macPkgFound = $true
        break
    }
}
if (-not $macPkgFound) {
    Write-Host "  macOS .pkg not found (optional; build on macOS and place in dist/)." -ForegroundColor Gray
}

# Compile the server installer
Get-ChildItem "$DistDir\DetecServerSetup-*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
& $iscc "$InstallerDir\detec-server-setup.iss"

$setupExe = Get-ChildItem "$DistDir\DetecServerSetup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setupExe) {
    Write-Host "  Server installer compilation FAILED." -ForegroundColor Red
    exit 1
}

# ── Step 9: Summary ─────────────────────────────────────────────────────

$sizeI = [math]::Round($setupExe.Length / 1MB, 1)
Write-Host ""
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Server installer: $($setupExe.FullName) ($sizeI MB)" -ForegroundColor White
Write-Host "  Agent installer:  $($agentSetupExe.FullName) ($sizeAI MB)" -ForegroundColor White
Write-Host ""
Write-Host "  Bundled agent packages (in server dist/packages/):" -ForegroundColor White
Write-Host "    Windows: DetecAgentSetup.exe ($sizeAI MB) + detec-agent.zip ($sizeZ MB)" -ForegroundColor White
if ($macPkgFound) {
    Write-Host "    macOS:   .pkg included" -ForegroundColor White
} else {
    Write-Host "    macOS:   not included (place .pkg in dist/ before building)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Ship DetecServerSetup.exe to clients. They double-click it," -ForegroundColor Gray
Write-Host "  follow the wizard, and the server is installed and running." -ForegroundColor Gray
Write-Host "  Agent installers are served from the dashboard automatically." -ForegroundColor Gray
Write-Host ""
