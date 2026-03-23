# Create a scheduled task that runs Detec Agent at user logon.
# Requires: detec-agent on PATH (pip install -e . from repo root).
# Set AGENTIC_GOV_API_URL and AGENTIC_GOV_API_KEY as user or system environment variables,
# or run this script after setting them in the current session.
#
# Usage: powershell -ExecutionPolicy Bypass -File install-detec-agent-task.ps1

$TaskName = "Detec Agent"
$TaskDescription = "Detec Agent — endpoint governance for agentic AI tools"
$Executable = "detec-agent"
$Arguments = "--interval 300"

$Action = New-ScheduledTaskAction -Execute $Executable -Argument $Arguments -WorkingDirectory $env:USERPROFILE
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description $TaskDescription -Force

Write-Host "Scheduled task '$TaskName' installed. It will run at logon."
Write-Host "Ensure AGENTIC_GOV_API_URL and AGENTIC_GOV_API_KEY are set (user or system environment variables)."
Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName'"
