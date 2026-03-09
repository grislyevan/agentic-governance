# Detec - Windows Server Bootstrap Script
#
# Installs all prerequisites (Python, Node.js, Git) on a fresh Windows
# Server VM, then runs the full deployment. One script, zero manual steps.
#
# Usage (from an elevated PowerShell prompt):
#   Set-ExecutionPolicy Bypass -Scope Process
#   irm https://raw.githubusercontent.com/grislyevan/agentic-governance/main/packaging/windows/bootstrap.ps1 | iex
#
# Or if you already downloaded this file:
#   Set-ExecutionPolicy Bypass -Scope Process
#   .\bootstrap.ps1

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # speeds up Invoke-WebRequest

$PythonVersion  = "3.11.9"
$NodeVersion    = "22.14.0"
$GitVersion     = "2.47.1"
$DownloadDir    = "$env:TEMP\detec-bootstrap"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      Detec — Windows Server Bootstrap                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check we're running elevated
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> 'Run as administrator', then re-run." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $DownloadDir)) { New-Item -ItemType Directory -Path $DownloadDir -Force | Out-Null }

# ── Helper: refresh PATH without restarting the shell ─────────────────────
function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path    = "$machinePath;$userPath"
}

# ══════════════════════════════════════════════════════════════════════════
# 1. Python 3.11
# ══════════════════════════════════════════════════════════════════════════
Write-Host "[1/4] Python $PythonVersion" -ForegroundColor Yellow

if (Get-Command python -ErrorAction SilentlyContinue) {
    $existingPy = python --version 2>&1
    Write-Host "  Already installed: $existingPy" -ForegroundColor Green
} else {
    $pyUrl  = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
    $pyExe  = "$DownloadDir\python-$PythonVersion-amd64.exe"

    Write-Host "  Downloading Python $PythonVersion..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyExe -UseBasicParsing

    Write-Host "  Installing (silent, adds to PATH)..." -ForegroundColor Gray
    Start-Process -FilePath $pyExe -ArgumentList `
        "/quiet", "InstallAllUsers=1", "PrependPath=1", `
        "Include_pip=1", "Include_launcher=1" `
        -Wait -NoNewWindow

    Refresh-Path

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pyCheck = python --version 2>&1
        Write-Host "  Installed: $pyCheck" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: python not found on PATH after install." -ForegroundColor DarkYellow
        Write-Host "  You may need to close and re-open PowerShell, then re-run." -ForegroundColor DarkYellow
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 2. Node.js 20 LTS
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[2/4] Node.js $NodeVersion LTS" -ForegroundColor Yellow

if (Get-Command node -ErrorAction SilentlyContinue) {
    $existingNode = node --version 2>&1
    Write-Host "  Already installed: $existingNode" -ForegroundColor Green
} else {
    $nodeUrl = "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-x64.msi"
    $nodeMsi = "$DownloadDir\node-v$NodeVersion-x64.msi"

    Write-Host "  Downloading Node.js $NodeVersion..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeMsi -UseBasicParsing

    Write-Host "  Installing (silent)..." -ForegroundColor Gray
    Start-Process msiexec.exe -ArgumentList "/i", $nodeMsi, "/qn", "/norestart" -Wait -NoNewWindow

    Refresh-Path

    if (Get-Command node -ErrorAction SilentlyContinue) {
        $nodeCheck = node --version 2>&1
        Write-Host "  Installed: $nodeCheck" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: node not found on PATH after install." -ForegroundColor DarkYellow
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 3. Git
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[3/4] Git $GitVersion" -ForegroundColor Yellow

if (Get-Command git -ErrorAction SilentlyContinue) {
    $existingGit = git --version 2>&1
    Write-Host "  Already installed: $existingGit" -ForegroundColor Green
} else {
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v$GitVersion.windows.1/Git-$GitVersion-64-bit.exe"
    $gitExe = "$DownloadDir\Git-$GitVersion-64-bit.exe"

    Write-Host "  Downloading Git $GitVersion..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitExe -UseBasicParsing

    Write-Host "  Installing (silent)..." -ForegroundColor Gray
    Start-Process -FilePath $gitExe -ArgumentList `
        "/VERYSILENT", "/NORESTART", "/NOCANCEL", `
        "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS", `
        "/COMPONENTS=icons,ext\reg\shellhere,assoc,assoc_sh" `
        -Wait -NoNewWindow

    Refresh-Path

    # Git installs to a non-standard location; add it explicitly
    $gitPath = "C:\Program Files\Git\cmd"
    if ((Test-Path $gitPath) -and ($env:Path -notlike "*$gitPath*")) {
        $env:Path = "$env:Path;$gitPath"
    }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        $gitCheck = git --version 2>&1
        Write-Host "  Installed: $gitCheck" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: git not found on PATH after install." -ForegroundColor DarkYellow
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 4. Run the deployment script
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[4/4] Running Detec deployment..." -ForegroundColor Yellow

# Ensure pip is up to date
python -m pip install --upgrade pip 2>&1 | Out-Null

$InstallDir = "C:\Detec\src"

if (-not (Test-Path "$InstallDir\.git")) {
    Write-Host "  Cloning repository..." -ForegroundColor Gray
    $parentDir = Split-Path $InstallDir -Parent
    if (-not (Test-Path $parentDir)) { New-Item -ItemType Directory -Path $parentDir -Force | Out-Null }
    git clone https://github.com/grislyevan/agentic-governance.git $InstallDir
} else {
    Write-Host "  Repo exists, pulling latest..." -ForegroundColor Gray
    Push-Location $InstallDir
    git pull origin main
    Pop-Location
}

# Hand off to the main deploy script in a clean process
# (avoids iex parser quirks when bootstrap is run via irm | iex)
powershell.exe -ExecutionPolicy Bypass -File "$InstallDir\packaging\windows\deploy.ps1"
