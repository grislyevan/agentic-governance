# Windows Agent Install: Current Behavior and Failure Notes

This document describes the current Windows agent install behavior and known failure modes, based on the codebase and the Agent reliability and admin control plan. It is intended to support Phase 1.2 (Windows persistence) and to clarify where manual QA is required.

## Install Path

- **Installer:** Inno Setup script at `packaging/windows/installer/detec-agent-setup.iss`.
- **Install target:** `{autopf}\Detec\Agent` (typically `C:\Program Files\Detec\Agent`).
- **Post-install:** The installer runs `detec-agent.exe install` then `detec-agent.exe start` from the app directory, with working directory set to the app directory (see packaging/windows/README.md).

## Service Registration

- **Implementation:** `collector/win_agent_service.py` (pywin32 `ServiceFramework`).
- **Service name:** `DetecAgent` (display name: "Detec Agent").
- **Start type:** `SERVICE_AUTO_START` (Automatic). The service is configured to start automatically at boot.
- **Binary:** The service runs the same executable that is used for `detec-agent install` / `start` (the PyInstaller-built `detec-agent.exe`), invoked by the SCM with the service entry point.

## Current Gaps (No Failure Recovery)

- **Failure recovery:** The service does **not** configure failure actions. There is no call to `ChangeServiceConfig2` with `SERVICE_CONFIG_FAILURE_ACTIONS`. If the service process exits (crash, unhandled exception, or missing config), the SCM does not restart it. The service remains stopped until an administrator starts it manually or the machine is rebooted (at which point it will auto-start once, and if it fails again, remain stopped).
- **Uninstall:** The uninstaller runs `detec-agent.exe stop` then `detec-agent.exe remove` (see `[UninstallRun]` in the .iss). Uninstall requires elevation (installer uses `PrivilegesRequired=admin`).

## Where Manual QA Is Needed

The following cannot be fully inferred from code and require validation on a clean Windows box (Phase 1.2.4):

1. **Clean install and reboot**
   - After a fresh install, does the "Detec Agent" service exist in Services (`services.msc`), with start type **Automatic**?
   - After reboot, does the service start without user logon, and do heartbeats reach the server?

2. **Failure behavior**
   - If the service is stopped (e.g. crash or `stop`), does it remain stopped until manually started or reboot? (Expected today: yes.)
   - After adding failure recovery (Phase 1.2.3), does the SCM restart the service after a failure (e.g. restart after 60 s)?

3. **Event Viewer and Services**
   - On failure, does the Windows Application log record an entry (source "DetecAgent" or the executable name)?
   - Are any failure reasons or error codes visible in the service Properties or Event Viewer that would explain a failure to start (e.g. missing `AGENTIC_GOV_API_URL` / `AGENTIC_GOV_API_KEY`, path issues, or permission errors)?

4. **Working directory and binary path**
   - Confirm that post-install runs `detec-agent.exe install` and `start` with working directory = `{app}` and binary path = `{app}\detec-agent.exe`, so the service is registered with the correct image path and can load config from `%PROGRAMDATA%\Detec\Agent\` (see README for verification details).

## References

- Plan: `.cursor/plans/agent_reliability_admin_control.plan.md` (Phase 1.2).
- Service code: `collector/win_agent_service.py`.
- Installer: `packaging/windows/installer/detec-agent-setup.iss`.
- Agent CLI (install/start/stop/remove/set-recovery): `collector/agent_cli.py`.

## Update (Phase 1.2.3)

Failure recovery is implemented in `collector/win_agent_service.py`: `set_service_failure_recovery()` configures `ChangeServiceConfig2` with `SERVICE_CONFIG_FAILURE_ACTIONS` (restart after 60 s). The installer runs `detec-agent.exe set-recovery` after start; the same can be run manually after `install`.
