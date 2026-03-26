# harden.ps1 — Called by MSI custom action after install.
# Tightens ACLs on agent install dir and agent.env config file.
# Uses SilentlyContinue so failures never block the install.

$ErrorActionPreference = "SilentlyContinue"

# ── 1. Agent install directory ────────────────────────────────────────────────
$agentDir = "C:\Program Files\Detec\Agent"

$acl = Get-Acl -Path $agentDir
$acl.SetAccessRuleProtection($true, $false)   # disable inheritance, clear inherited rules

$inherit = [System.Security.AccessControl.InheritanceFlags]"ContainerInherit,ObjectInherit"
$none    = [System.Security.AccessControl.PropagationFlags]"None"
$allow   = [System.Security.AccessControl.AccessControlType]"Allow"

$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    "NT AUTHORITY\SYSTEM",
    [System.Security.AccessControl.FileSystemRights]"FullControl",
    $inherit, $none, $allow)))

$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    "BUILTIN\Administrators",
    [System.Security.AccessControl.FileSystemRights]"FullControl",
    $inherit, $none, $allow)))

$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    "BUILTIN\Users",
    [System.Security.AccessControl.FileSystemRights]"ReadAndExecute",
    $inherit, $none, $allow)))

Set-Acl -Path $agentDir -AclObject $acl

# ── 2. agent.env config file ──────────────────────────────────────────────────
$envFile = "C:\ProgramData\Detec\Agent\agent.env"

if (Test-Path $envFile) {
    $acl2 = Get-Acl -Path $envFile
    $acl2.SetAccessRuleProtection($true, $false)   # disable inheritance, clear inherited rules

    $noneInherit = [System.Security.AccessControl.InheritanceFlags]"None"

    $acl2.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
        "NT AUTHORITY\SYSTEM",
        [System.Security.AccessControl.FileSystemRights]"FullControl",
        $noneInherit, $none, $allow)))

    $acl2.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
        "BUILTIN\Administrators",
        [System.Security.AccessControl.FileSystemRights]"FullControl",
        $noneInherit, $none, $allow)))

    # No Users access — agent.env contains the API key.

    Set-Acl -Path $envFile -AclObject $acl2
}
