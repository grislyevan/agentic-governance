# Build script for Detec Agent (collector) Windows distribution.
#
# Prerequisites:
#   - Python 3.11+ with pip
#   - pyinstaller, pywin32 installed
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File packaging/windows/build-agent.ps1

param(
    [string]$ApiUrl = "",
    [string]$ApiKey = ""
)

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

# Step 3: Optionally bake in server config.
$DistDir = "$RepoRoot\packaging\windows\dist\detec-agent"
if ($ApiUrl -and $ApiKey) {
    Write-Host "`n[3/4] Embedding server config..." -ForegroundColor Yellow
    $ConfigDir = "$DistDir\config"
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    $collectorJson = @{
        api_url  = $ApiUrl
        api_key  = $ApiKey
        interval = 300
        protocol = "http"
    } | ConvertTo-Json
    Set-Content -Path "$ConfigDir\collector.json" -Value $collectorJson -Encoding UTF8
    Write-Host "  Config written to $ConfigDir\collector.json"
} else {
    Write-Host "`n[3/4] No -ApiUrl/-ApiKey provided; building generic package (manual setup required)." -ForegroundColor Yellow
}

# Step 4: Verify output.
$ExePath = "$DistDir\detec-agent.exe"
if (Test-Path $ExePath) {
    $size = (Get-Item $ExePath).Length / 1MB
    Write-Host "`n=== Build complete ===" -ForegroundColor Green
    Write-Host "Executable: $ExePath ($([math]::Round($size, 1)) MB)"
    Write-Host "`nTest it:"
    Write-Host "  cd $DistDir"
    Write-Host "  .\detec-agent.exe scan --verbose"
    if ($ApiUrl -and $ApiKey) {
        Write-Host "  Server config is pre-loaded. The agent will connect automatically."
    } else {
        Write-Host "  .\detec-agent.exe setup --api-url http://server:8000/api --api-key YOUR_KEY"
    }
} else {
    Write-Host "`nBuild FAILED: $ExePath not found" -ForegroundColor Red
    exit 1
}
