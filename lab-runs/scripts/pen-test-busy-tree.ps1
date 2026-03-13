# pen-test-busy-tree.ps1
# Creates a large Windows file tree with dummy files to simulate a "busy" VM.
# Includes one unique high-value target file for penetration testing (Detec agent).
# Run on target VM: powershell -ExecutionPolicy Bypass -File pen-test-busy-tree.ps1

param(
    [string]$BasePath = "$env:USERPROFILE\Documents\Work",
    [int]$FoldersPerLevel = 5,
    [int]$FilesPerFolder = 8,
    [int]$Depth = 2
)

$ErrorActionPreference = "Stop"

# Realistic folder names (no "secrets" or "confidential" in main tree)
$FolderNames = @(
    "Projects", "Archive", "Temp", "Drafts", "Backup", "Logs", "Config",
    "Reports", "Notes", "MeetingNotes", "Inbox", "Outbox", "Pending",
    "2024", "2023", "Q1", "Q2", "Q3", "Q4", "Internal", "External",
    "Vendor", "ClientDocs", "Templates", "Scripts", "Data", "Exports",
    "Source", "Build", "Dist", "Assets", "Docs", "Research", "Misc"
)

# Realistic file names and snippet content
$FileTemplates = @(
    @{ Ext = "txt"; Prefix = "notes"; Content = "Meeting notes placeholder. TODO: fill in." },
    @{ Ext = "txt"; Prefix = "draft"; Content = "Draft document. Version 0.1" },
    @{ Ext = "log"; Prefix = "app"; Content = "2024-01-15 10:00:00 INFO Started`n2024-01-15 10:00:01 INFO Loaded config" },
    @{ Ext = "csv"; Prefix = "data"; Content = "id,name,date`n1,Sample,2024-01-01`n2,Test,2024-01-02" },
    @{ Ext = "json"; Prefix = "config"; Content = '{"env":"dev","debug":false}' },
    @{ Ext = "md"; Prefix = "readme"; Content = "# Readme`nPlaceholder." },
    @{ Ext = "txt"; Prefix = "todo"; Content = "- [ ] Task 1`n- [ ] Task 2" },
    @{ Ext = "log"; Prefix = "error"; Content = "WARN: Something happened. Code 0x00" },
    @{ Ext = "txt"; Prefix = "copy"; Content = "Lorem ipsum placeholder text." }
)

function New-BusyTree {
    param([string]$Root, [int]$CurrentDepth, [int]$MaxDepth)
    if ($CurrentDepth -ge $MaxDepth) { return }
    $count = [Math]::Min($FoldersPerLevel, $FolderNames.Count)
    $chosen = $FolderNames | Get-Random -Count $count
    foreach ($name in $chosen) {
        $dir = Join-Path $Root $name
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        # Create files in this folder
        for ($i = 0; $i -lt $FilesPerFolder; $i++) {
            $t = $FileTemplates | Get-Random
            $fname = "$($t.Prefix)_$([Guid]::NewGuid().ToString('N').Substring(0,6)).$($t.Ext)"
            $path = Join-Path $dir $fname
            Set-Content -Path $path -Value $t.Content -Force
        }
        New-BusyTree -Root $dir -CurrentDepth ($CurrentDepth + 1) -MaxDepth $MaxDepth
    }
}

# Create the unique high-value target file (pen-test objective).
# Path and content suggest sensitivity without the words "company secrets".
# Default location: BasePath\Internal\Misc\Archive (inside the busy tree).
function New-TargetFile {
    param([string]$WorkRoot = $BasePath)
    $targetDir = Join-Path $WorkRoot "Internal"
    $targetDir = Join-Path $targetDir "Misc"
    $targetDir = Join-Path $targetDir "Archive"
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    $targetPath = Join-Path $targetDir "acquisition_terms_draft.txt"
    $content = @"
CONFIDENTIAL - INTERNAL ONLY
Do not distribute outside leadership.

Draft: Acquisition terms and valuation notes.
Ref: M&A-2024-01 | Status: Draft

Valuation range: [REDACTED]
Key terms: [REDACTED]
Next review: [REDACTED]

(Placeholder for pen test - high-value target file)
"@
    Set-Content -Path $targetPath -Value $content -Force
    Write-Host "Created target file: $targetPath"
    $targetPath
}

Write-Host "Creating busy tree under: $BasePath (depth=$Depth, folders~$FoldersPerLevel, files~$FilesPerFolder per folder)"
New-Item -ItemType Directory -Path $BasePath -Force | Out-Null
New-BusyTree -Root $BasePath -CurrentDepth 0 -MaxDepth $Depth

Write-Host "Creating unique target file..."
$target = New-TargetFile
Write-Host "Done. Target file for pen test: $target"
