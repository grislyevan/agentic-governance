# Build script for Detec Agent (collector) Windows distribution.
#
# Prerequisites:
#   - Python 3.11+ with pip
#   - pyinstaller, pywin32 installed
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File packaging/windows/build-agent.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path

Write-Host "=== Building Detec Agent ===" -ForegroundColor Cyan

# Step 1: Install Python dependencies.
Write-Host "`n[1/3] Installing Python dependencies..." -ForegroundColor Yellow
Push-Location $RepoRoot
pip install -e .
pip install pyinstaller pywin32
Pop-Location

# Step 2: Run PyInstaller.
Write-Host "`n[2/3] Running PyInstaller..." -ForegroundColor Yellow
Push-Location "$RepoRoot\packaging\windows"
pyinstaller --clean --noconfirm detec-agent.spec
Pop-Location

# Step 3: Verify output.
$ExePath = "$RepoRoot\packaging\windows\dist\detec-agent\detec-agent.exe"
if (Test-Path $ExePath) {
    $size = (Get-Item $ExePath).Length / 1MB
    Write-Host "`n=== Build complete ===" -ForegroundColor Green
    Write-Host "Executable: $ExePath ($([math]::Round($size, 1)) MB)"
    Write-Host "`nTest it:"
    Write-Host "  cd $RepoRoot\packaging\windows\dist\detec-agent"
    Write-Host "  .\detec-agent.exe scan --verbose"
    Write-Host "  .\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY"
} else {
    Write-Host "`nBuild FAILED: $ExePath not found" -ForegroundColor Red
    exit 1
}
