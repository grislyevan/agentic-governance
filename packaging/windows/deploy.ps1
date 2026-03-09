# Detec Server + Agent - Full Windows Deployment Script
#
# Clones (or pulls) the repo, builds both executables, runs setup,
# and installs as Windows Services.
#
# Prerequisites:
#   - Python 3.11+ on PATH
#   - Node.js 18+ on PATH (for dashboard build)
#   - Git on PATH
#   - Run from an elevated (Administrator) PowerShell prompt
#
# Usage:
#   Set-ExecutionPolicy Bypass -Scope Process
#   .\deploy.ps1
#
# Environment variables (optional):
#   $env:DETEC_ADMIN_EMAIL   - seed admin email (default: admin@yourorg.com)
#   $env:DETEC_REPO_URL      - git clone URL
#   $env:DETEC_BRANCH        - git branch to deploy (default: main)
#   $env:DETEC_INSTALL_DIR   - where to clone the repo (default: C:\Detec\src)
#   $env:DETEC_SERVER_PORT   - port for the API server (default: 8000)

$ErrorActionPreference = "Stop"

# ── Configuration ──────────────────────────────────────────────────────────
$RepoUrl      = if ($env:DETEC_REPO_URL)    { $env:DETEC_REPO_URL }    else { "https://github.com/grislyevan/agentic-governance.git" }
$Branch       = if ($env:DETEC_BRANCH)      { $env:DETEC_BRANCH }      else { "main" }
$InstallDir   = if ($env:DETEC_INSTALL_DIR) { $env:DETEC_INSTALL_DIR } else { "C:\Detec\src" }
$AdminEmail   = if ($env:DETEC_ADMIN_EMAIL) { $env:DETEC_ADMIN_EMAIL } else { "admin@yourorg.com" }
$ServerPort   = if ($env:DETEC_SERVER_PORT) { $env:DETEC_SERVER_PORT } else { "8000" }

$ServerDist   = "$InstallDir\packaging\windows\dist\detec-server"
$AgentDist    = "$InstallDir\packaging\windows\dist\detec-agent"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          Detec — Windows Deployment Script           ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 0: Check prerequisites ───────────────────────────────────────────
Write-Host "[0/8] Checking prerequisites..." -ForegroundColor Yellow

$missing = @()
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $missing += "Python 3.11+" }
if (-not (Get-Command node -ErrorAction SilentlyContinue))   { $missing += "Node.js 18+" }
if (-not (Get-Command git -ErrorAction SilentlyContinue))    { $missing += "Git" }

if ($missing.Count -gt 0) {
    Write-Host "  MISSING: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  Install them and re-run this script." -ForegroundColor Red
    exit 1
}

$pyVer = python --version 2>&1
$nodeVer = node --version 2>&1
$gitVer = git --version 2>&1
Write-Host "  Python:  $pyVer" -ForegroundColor Gray
Write-Host "  Node.js: $nodeVer" -ForegroundColor Gray
Write-Host "  Git:     $gitVer" -ForegroundColor Gray

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ""
    Write-Host "  WARNING: Not running as Administrator." -ForegroundColor DarkYellow
    Write-Host "  Service install/start steps will fail. Re-run elevated if needed." -ForegroundColor DarkYellow
    Write-Host ""
}

# ── Step 1: Clone or update the repo ──────────────────────────────────────
Write-Host "`n[1/8] Getting source code..." -ForegroundColor Yellow

if (Test-Path "$InstallDir\.git") {
    Write-Host "  Repo exists at $InstallDir, pulling latest..." -ForegroundColor Gray
    Push-Location $InstallDir
    git fetch origin
    git checkout $Branch
    git pull origin $Branch
    Pop-Location
} else {
    Write-Host "  Cloning $RepoUrl -> $InstallDir ..." -ForegroundColor Gray
    $parentDir = Split-Path $InstallDir -Parent
    if (-not (Test-Path $parentDir)) { New-Item -ItemType Directory -Path $parentDir -Force | Out-Null }
    git clone --branch $Branch $RepoUrl $InstallDir
}

# ── Step 2: Install Python dependencies (API) ────────────────────────────
Write-Host "`n[2/8] Installing API Python dependencies..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
pip install -r "$InstallDir\api\requirements.txt" 2>&1 | Out-Null
pip install pyinstaller pywin32 2>&1 | Out-Null
pip install psycopg2-binary 2>&1 | Out-Null
Write-Host "  Dependencies installed." -ForegroundColor Green
$ErrorActionPreference = "Stop"

# ── Step 3: Install collector as a package ────────────────────────────────
Write-Host "`n[3/8] Installing collector package..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
Push-Location $InstallDir
pip install -e . 2>&1 | Out-Null
Pop-Location
Write-Host "  Collector package installed." -ForegroundColor Green
$ErrorActionPreference = "Stop"

# ── Step 4: Build the React dashboard ─────────────────────────────────────
Write-Host "`n[4/8] Building dashboard..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
Push-Location "$InstallDir\dashboard"
npm install --loglevel=error 2>&1 | Out-Null
npm run build 2>&1 | Out-Null
Pop-Location

if (-not (Test-Path "$InstallDir\dashboard\dist\index.html")) {
    Write-Host "  Dashboard build FAILED." -ForegroundColor Red
    exit 1
}
Write-Host "  Dashboard built OK." -ForegroundColor Green

# ── Step 5: Build detec-server.exe ────────────────────────────────────────
Write-Host "`n[5/8] Building detec-server.exe (this takes a few minutes)..." -ForegroundColor Yellow
Push-Location "$InstallDir\packaging\windows"
$ErrorActionPreference = "Continue"
pyinstaller --clean --noconfirm detec-server.spec 2>&1 | ForEach-Object { "$_" } | Select-String -Pattern "(ERROR|completed)" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
$ErrorActionPreference = "Stop"
Pop-Location

if (-not (Test-Path "$ServerDist\detec-server.exe")) {
    Write-Host "  Server build FAILED." -ForegroundColor Red
    exit 1
}
$sizeS = [math]::Round((Get-Item "$ServerDist\detec-server.exe").Length / 1MB, 1)
Write-Host "  detec-server.exe built ($sizeS MB)" -ForegroundColor Green

# ── Step 6: Build detec-agent.exe ─────────────────────────────────────────
Write-Host "`n[6/8] Building detec-agent.exe..." -ForegroundColor Yellow
Push-Location "$InstallDir\packaging\windows"
$ErrorActionPreference = "Continue"
pyinstaller --clean --noconfirm detec-agent.spec 2>&1 | ForEach-Object { "$_" } | Select-String -Pattern "(ERROR|completed)" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
$ErrorActionPreference = "Stop"
Pop-Location

if (-not (Test-Path "$AgentDist\detec-agent.exe")) {
    Write-Host "  Agent build FAILED." -ForegroundColor Red
    exit 1
}
$sizeA = [math]::Round((Get-Item "$AgentDist\detec-agent.exe").Length / 1MB, 1)
Write-Host "  detec-agent.exe built ($sizeA MB)" -ForegroundColor Green

# ── Step 7: Server setup + install ────────────────────────────────────────
Write-Host "`n[7/8] Setting up Detec Server..." -ForegroundColor Yellow

# Run first-time setup (generates JWT secret, admin password, DB)
$ErrorActionPreference = "Continue"
& "$ServerDist\detec-server.exe" setup --admin-email $AdminEmail --port $ServerPort
Write-Host ""

if ($isAdmin) {
    Write-Host "  Installing Detec Server as a Windows Service..." -ForegroundColor Gray
    & "$ServerDist\detec-server.exe" install
    & "$ServerDist\detec-server.exe" start
    Write-Host "  Detec Server service started." -ForegroundColor Green
} else {
    Write-Host "  Skipping service install (not Administrator)." -ForegroundColor DarkYellow
    Write-Host "  To test, run: $ServerDist\detec-server.exe run" -ForegroundColor DarkYellow
}
$ErrorActionPreference = "Stop"

# ── Step 8: Firewall rule ─────────────────────────────────────────────────
Write-Host "`n[8/8] Configuring firewall..." -ForegroundColor Yellow

if ($isAdmin) {
    $existingRule = Get-NetFirewallRule -DisplayName "Detec Server" -ErrorAction SilentlyContinue
    if (-not $existingRule) {
        New-NetFirewallRule -DisplayName "Detec Server" -Direction Inbound -Protocol TCP -LocalPort $ServerPort -Action Allow | Out-Null
        Write-Host "  Firewall rule created (TCP $ServerPort inbound)." -ForegroundColor Green
    } else {
        Write-Host "  Firewall rule already exists." -ForegroundColor Gray
    }
} else {
    Write-Host "  Skipping firewall (not Administrator)." -ForegroundColor DarkYellow
}

# ── Done ──────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '  *** Deployment Complete ***' -ForegroundColor Green
Write-Host ''
Write-Host "  Server:     http://localhost:$ServerPort" -ForegroundColor White
Write-Host "  Dashboard:  http://localhost:$ServerPort" -ForegroundColor White
Write-Host "  API docs:   http://localhost:$ServerPort/docs" -ForegroundColor White
Write-Host '  Config:     C:\ProgramData\Detec\server.env' -ForegroundColor White
Write-Host '  Database:   C:\ProgramData\Detec\detec.db' -ForegroundColor White
Write-Host ''
Write-Host "  Server exe: $ServerDist\detec-server.exe" -ForegroundColor Gray
Write-Host "  Agent exe:  $AgentDist\detec-agent.exe" -ForegroundColor Gray
Write-Host ''
Write-Host '  Next steps:' -ForegroundColor Yellow
Write-Host "  1. Open http://localhost:$ServerPort in a browser" -ForegroundColor White
Write-Host '  2. Log in with the admin credentials shown above' -ForegroundColor White
Write-Host '  3. Copy the API key from the setup output' -ForegroundColor White
Write-Host '  4. On each endpoint, run:' -ForegroundColor White
Write-Host '     detec-agent.exe setup --api-url http://SERVER:8000/api --api-key KEY' -ForegroundColor White
Write-Host '     detec-agent.exe install' -ForegroundColor White
Write-Host '     detec-agent.exe start' -ForegroundColor White
Write-Host ''
