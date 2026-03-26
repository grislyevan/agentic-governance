<#
.SYNOPSIS
    Generate WiX v4 fragment files from a directory tree (replaces wix heat dir).

.DESCRIPTION
    Scans a directory recursively and emits a .wxs fragment with Directory,
    Component, and File elements for every file found. Used to include the
    full PyInstaller _internal directory in the MSI.

.PARAMETER SourceDir
    The directory to harvest.

.PARAMETER ComponentGroupId
    Name for the ComponentGroup (e.g., AgentInternalFiles).

.PARAMETER DirectoryRefId
    The WiX Directory Id to anchor files under (e.g., AGENTINTERNALDIR).

.PARAMETER SourceVar
    WiX preprocessor variable for the source path (e.g., var.AgentInternalDir).

.PARAMETER OutputFile
    Path to write the generated .wxs fragment.
#>
param(
    [Parameter(Mandatory)][string]$SourceDir,
    [Parameter(Mandatory)][string]$ComponentGroupId,
    [Parameter(Mandatory)][string]$DirectoryRefId,
    [Parameter(Mandatory)][string]$SourceVar,
    [Parameter(Mandatory)][string]$OutputFile
)

$ErrorActionPreference = "Stop"

$SourceDir = (Resolve-Path $SourceDir).Path

# Collect all files and directories
$allFiles = Get-ChildItem -Path $SourceDir -Recurse -File
$allDirs = Get-ChildItem -Path $SourceDir -Recurse -Directory

# Short prefix from ComponentGroupId to make IDs unique across fragments
$idPrefix = ($ComponentGroupId -replace '[^A-Za-z]','').Substring(0, [Math]::Min(4, $ComponentGroupId.Length)).ToLower()

# Create unique IDs from paths using hash to guarantee no collisions
$script:sha = [System.Security.Cryptography.SHA256]::Create()
function Get-WixId {
    param([string]$Prefix, [string]$RelPath)
    $hashBytes = $script:sha.ComputeHash(
        [System.Text.Encoding]::UTF8.GetBytes("${script:idPrefix}_${RelPath}")
    )
    $hash = [System.BitConverter]::ToString($hashBytes).Replace("-","").Substring(0,16)
    return "${Prefix}_${script:idPrefix}_${hash}"
}

# Build directory ID map
$dirIds = @{}
$dirIds[""] = $DirectoryRefId

foreach ($d in $allDirs) {
    $relPath = $d.FullName.Substring($SourceDir.Length).TrimStart('\','/')
    $dirIds[$relPath] = Get-WixId "dir" $relPath
}

# Start building XML
$xml = [System.Text.StringBuilder]::new()
[void]$xml.AppendLine('<?xml version="1.0" encoding="UTF-8"?>')
[void]$xml.AppendLine('<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">')
[void]$xml.AppendLine('  <Fragment>')

# Emit directory structure
if ($allDirs.Count -gt 0) {
    # Group directories by their parent
    $topDirs = $allDirs | Where-Object {
        $_.Parent.FullName -eq $SourceDir
    }

    function Write-DirTree {
        param([string]$ParentPath, [string]$Indent)
        $parentFull = if ($ParentPath) { Join-Path $SourceDir $ParentPath } else { $SourceDir }
        $children = $allDirs | Where-Object { $_.Parent.FullName -eq $parentFull }
        foreach ($child in $children) {
            $relPath = $child.FullName.Substring($SourceDir.Length).TrimStart('\','/')
            $dirId = $dirIds[$relPath]
            [void]$xml.AppendLine("$Indent<Directory Id=`"$dirId`" Name=`"$($child.Name)`">")
            Write-DirTree -ParentPath $relPath -Indent "$Indent  "
            [void]$xml.AppendLine("$Indent</Directory>")
        }
    }

    [void]$xml.AppendLine("    <DirectoryRef Id=`"$DirectoryRefId`">")
    Write-DirTree -ParentPath "" -Indent "      "
    [void]$xml.AppendLine("    </DirectoryRef>")
}

# Emit component group
[void]$xml.AppendLine("    <ComponentGroup Id=`"$ComponentGroupId`">")

foreach ($f in $allFiles) {
    $relPath = $f.FullName.Substring($SourceDir.Length).TrimStart('\','/')
    $relDir = [System.IO.Path]::GetDirectoryName($relPath)
    if (-not $relDir) { $relDir = "" }
    $dirId = $dirIds[$relDir]
    $compId = Get-WixId "cmp" $relPath
    $fileId = Get-WixId "fil" $relPath
    $sourcePath = "`$(`$SourceVar)\$relPath" -replace '/', '\'

    # Use the preprocessor variable reference
    $sourceAttr = "`$(var.$SourceVar)\$relPath" -replace '/', '\'

    [void]$xml.AppendLine("      <Component Id=`"$compId`" Directory=`"$dirId`" Guid=`"*`">")
    [void]$xml.AppendLine("        <File Id=`"$fileId`" Source=`"$sourceAttr`" KeyPath=`"yes`" />")
    [void]$xml.AppendLine("      </Component>")
}

[void]$xml.AppendLine("    </ComponentGroup>")
[void]$xml.AppendLine('  </Fragment>')
[void]$xml.AppendLine('</Wix>')

# Write output
Set-Content -Path $OutputFile -Value $xml.ToString() -Encoding UTF8
$fileCount = $allFiles.Count
$dirCount = $allDirs.Count
Write-Host "Harvested $fileCount files in $dirCount directories -> $OutputFile"
