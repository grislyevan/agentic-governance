# Tamper Controls

This document defines Detec Agent tamper controls: how uninstall and service/process stop are restricted so that only administrators (or a defined override) can remove or stop the agent.

## Policy decisions

### 1. Scope: uninstall only, or also stop/kill?

- **Uninstall:** We explicitly restrict uninstall so that only an administrator (or an approved override) can remove the agent.
- **Stopping the service / killing the process:** We do **not** add custom logic to block stop or kill. We rely on the OS:
  - **Windows:** The Service Control Manager (SCM) already restricts stopping and deleting the DetecAgent service to administrators. Non-admin users cannot stop or remove the service via `sc stop` / `sc delete` or the Services GUI.
  - **macOS:** If the agent runs as a **LaunchDaemon** (root), only root can unload it (`launchctl bootout`). If it runs as a **LaunchAgent** (per-user), the user can unload their own agent; moving to LaunchDaemon (Phase 1.1.3) removes that ability for non-root users.

So we **block uninstall** at the installer/uninstaller level and **rely on the OS** for stop/delete (Windows SCM; macOS launchd when using LaunchDaemon).

### 2. Password vs MDM

We do **not** require a password at uninstall time. Rationale:

- **Windows:** Uninstall already requires elevation (UAC). Adding a password prompt would duplicate OS-level access control and complicate scripted/MDM uninstall.
- **macOS:** Uninstall requires root/sudo when using LaunchDaemon; we document that and optionally support an MDM-only or token-based override for scripted removal.

We **rely on MDM and OS access control:** deploy the agent via MDM with appropriate privileges; uninstall is then only possible by an admin (or by a script/task that has been approved and runs as root/SYSTEM). Optional **uninstall token** (Windows: file under ProgramData; macOS: document or implement per deployment) allows approved scripted uninstall without adding a password layer.

---

## Windows

### Admin requirement

- The Detec Agent installer is built with **PrivilegesRequired=admin**. Installing and uninstalling require elevation (UAC). Non-admin users cannot run the installer or the uninstaller from Add/Remove Programs.
- **Service Control Manager (SCM):** Stopping (`sc stop DetecAgent`) and deleting (`sc delete DetecAgent`) the service are restricted to administrators. Non-admin users get "Access is denied." No additional agent-side logic is required for stop/delete.

### Uninstall token (optional)

For scripted or MDM-driven uninstall, an **uninstall token** file can be used so that automated uninstall is explicitly allowed:

- **Path:** `C:\ProgramData\Detec\Agent\allow_uninstall.token`
- **Semantics:** If this file exists when the uninstaller runs, the uninstall is treated as approved (e.g. for silent or scripted removal). Only users who can write to `ProgramData\Detec\Agent` (typically admins or SYSTEM) can create the token. The token does not allow a non-admin to uninstall; it is for use when an admin or MDM runs the uninstaller and wants to avoid extra prompts or to signal "approved" removal.

Implementation (if desired): in the Inno Setup script, at uninstall start, require either the process to be elevated or the token file to exist; otherwise abort with a message. Current installer already runs uninstall with admin privileges when invoked from Add/Remove Programs.

---

## macOS

### Current: LaunchAgent

- The .pkg installs a **LaunchAgent** in `~/Library/LaunchAgents/com.detec.agent.plist`. The owning user can unload it (`launchctl bootout`) and can run the uninstall script if they have write access to the app and plist paths.
- Uninstall is documented to be run with **sudo** so that all components (app, LaunchAgent, config, logs, receipt) are removed cleanly. See [Uninstall script](#uninstall-script) below.

### Future: LaunchDaemon (Phase 1.1.3)

If the agent is switched to a **LaunchDaemon** (installed in `/Library/LaunchDaemons/`, running as root):

- Only root can unload the daemon (`sudo launchctl bootout system/com.detec.agent`). Non-root users cannot stop the agent.
- Uninstall **must** be run as root/sudo: remove the plist from `/Library/LaunchDaemons/`, unload the daemon, remove the app and config under `/Library/Application Support/Detec` (or the chosen daemon config path).
- Optionally, uninstall can be gated behind a token (e.g. a file in a root-only location that a script or MDM creates before running uninstall). Document or implement per policy.

### Uninstall script

- **Path:** `packaging/macos/uninstall.sh`
- **Usage:** Run with sudo for full removal:  
  `sudo bash /path/to/uninstall.sh`
- The script unloads the LaunchAgent, removes the app, config, logs, state, Keychain entry, and installer receipt. It resolves the real user via `SUDO_USER` when run with sudo.
- If using a LaunchDaemon, the script (or a separate daemon uninstall path) must unload from the system domain and remove system-level paths (see "Future: LaunchDaemon" above).

---

## Future: tamper event

A possible future enhancement is a **tamper signal** from the agent to the server when the agent detects an uninstall attempt or repeated kill (e.g. process repeatedly terminated). That would require:

- A new event type (or event subtype) in the wire protocol and API for "tamper" or "uninstall_attempt".
- The agent to detect uninstall (e.g. wrapper or installer callback) or repeated exits and send one last event before shutdown.
- API and dashboard support to store and display a tamper/uninstall alert per endpoint.

Not implemented in Phase 2.1; add when scope allows.
