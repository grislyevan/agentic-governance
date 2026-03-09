# Build the Detec Server installer (DetecServerSetup.exe)
#
# Runs the full pipeline:
#   1. Install Python build dependencies
#   2. Build the React dashboard
#   3. Build detec-server.exe via PyInstaller
#   4. Generate installer branding assets
#   5. Compile the Inno Setup installer
#
# Prerequisites:
#   - Python 3.11+ on PATH
#   - Node.js 20.19+ or 22+ on PATH
#   - Inno Setup 6 installed (iscc.exe on PATH or in default location)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
#
# Output:
#   packaging\windows\dist\DetecServerSetup-<version>.exe

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
Write-Host "[0/5] Inno Setup found: $iscc" -ForegroundColor Green

# ── Step 1: Python dependencies ──────────────────────────────────────────

Write-Host "`n[1/5] Installing Python dependencies..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
pip install -r "$ApiDir\requirements.txt" 2>&1 | Out-Null
pip install pyinstaller pywin32 Pillow 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
Write-Host "  Dependencies installed." -ForegroundColor Green

# ── Step 2: Dashboard build ──────────────────────────────────────────────

Write-Host "`n[2/5] Building dashboard..." -ForegroundColor Yellow
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

# ── Step 3: PyInstaller bundle ───────────────────────────────────────────

Write-Host "`n[3/5] Building detec-server.exe (this takes a few minutes)..." -ForegroundColor Yellow
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

# ── Step 4: Installer branding assets ────────────────────────────────────

Write-Host "`n[4/5] Generating installer branding assets..." -ForegroundColor Yellow
python "$InstallerDir\generate-assets.py"

if (-not (Test-Path "$InstallerDir\wizard-image.bmp") -or -not (Test-Path "$InstallerDir\wizard-small-image.bmp")) {
    Write-Host "  Asset generation FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "  Branding assets ready." -ForegroundColor Green

# ── Step 5: Inno Setup compilation ──────────────────────────────────────

Write-Host "`n[5/5] Compiling installer..." -ForegroundColor Yellow
& $iscc "$InstallerDir\detec-server-setup.iss"

$setupExe = Get-ChildItem "$DistDir\DetecServerSetup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setupExe) {
    Write-Host "  Installer compilation FAILED." -ForegroundColor Red
    exit 1
}

$sizeI = [math]::Round($setupExe.Length / 1MB, 1)
Write-Host ""
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  Installer: $($setupExe.FullName) ($sizeI MB)" -ForegroundColor White
Write-Host ""
Write-Host "  Ship this single file to clients. They double-click it," -ForegroundColor Gray
Write-Host "  follow the wizard, and the server is installed and running." -ForegroundColor Gray
Write-Host ""
