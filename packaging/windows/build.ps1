# Build script for Detec Server Windows distribution.
#
# Prerequisites:
#   - Python 3.11+ with pip
#   - Node.js 18+ with npm
#   - pyinstaller, pywin32 installed
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File packaging/windows/build.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path

Write-Host "=== Building Detec Server ===" -ForegroundColor Cyan

# Step 1: Install Python dependencies.
Write-Host "`n[1/4] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r "$RepoRoot\api\requirements.txt"
pip install pyinstaller pywin32

# Step 2: Build the React dashboard.
Write-Host "`n[2/4] Building dashboard..." -ForegroundColor Yellow
Push-Location "$RepoRoot\dashboard"
npm install
npm run build
Pop-Location

# Step 3: Run PyInstaller.
Write-Host "`n[3/4] Running PyInstaller..." -ForegroundColor Yellow
Push-Location "$RepoRoot\packaging\windows"
pyinstaller --clean --noconfirm detec-server.spec
Pop-Location

# Step 4: Verify output.
$ExePath = "$RepoRoot\packaging\windows\dist\detec-server\detec-server.exe"
if (Test-Path $ExePath) {
    $size = (Get-Item $ExePath).Length / 1MB
    Write-Host "`n=== Build complete ===" -ForegroundColor Green
    Write-Host "Executable: $ExePath ($([math]::Round($size, 1)) MB)"
    Write-Host "`nTest it:"
    Write-Host "  cd $RepoRoot\packaging\windows\dist\detec-server"
    Write-Host "  .\detec-server.exe setup"
    Write-Host "  .\detec-server.exe run"
} else {
    Write-Host "`nBuild FAILED: $ExePath not found" -ForegroundColor Red
    exit 1
}
