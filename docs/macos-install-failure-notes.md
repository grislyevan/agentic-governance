# macOS Install Failure Notes (Phase 1.1.1)

This document describes the current macOS installer behavior and failure modes on a clean Mac, based on the codebase and the agent_reliability_admin_control plan. It is used to justify and scope fixes in Phase 1.1.2 and 1.1.3.

## Current Install Flow

- **Artifact:** `.pkg` built by `packaging/macos/build-pkg.sh` installs `Detec Agent.app` to `/Applications`.
- **Scripts:** `packaging/macos/scripts/preinstall` and `postinstall` run as **root** during install.
- **Postinstall** writes a **LaunchAgent** plist to `~/Library/LaunchAgents/com.detec.agent.plist` and runs `launchctl bootstrap gui/$UID` (or `launchctl load`) to load it. It also creates `~/Library/Application Support/Detec`, `~/Library/Logs/DetecAgent`, and `~/.agentic-gov`, and copies any baked config from the .app into `~/Library/Application Support/Detec/`.

## Paths and Permissions

| Path | Purpose | Owner after postinstall |
|------|---------|-------------------------|
| `/Applications/Detec Agent.app` | App bundle (binary at `Contents/MacOS/detec-agent-gui`) | root (pkg default) |
| `~/Library/LaunchAgents/com.detec.agent.plist` | LaunchAgent plist | Real user (chown in postinstall) |
| `~/Library/Application Support/Detec/` | Config (agent.env, collector.json) | Real user |
| `~/Library/Logs/DetecAgent/` | Logs | Real user |
| `~/.agentic-gov` | State | Real user |

Binary and plist paths in `build-pkg.sh` and `postinstall` are consistent: install location is `/Applications/Detec Agent.app`, binary is `detec-agent-gui` inside the bundle.

## Who Is $HOME During Postinstall?

- **Interactive install (double-click .pkg):** The installer often runs postinstall with `$HOME` set to the **console user's** home (e.g. `/Users/jane`). Behavior is installer-dependent.
- **sudo installer -pkg ... -target /:** Typically `$HOME` is **root's** home (`/var/root`). Postinstall then creates `LaunchAgents` under `/var/root/Library/LaunchAgents` and assigns ownership to the user reported by `stat -f '%Su' "$HOME"` (i.e. `root`). The **console user** never gets a LaunchAgent; the agent does not start at their login.
- **MDM push:** Same as sudo install: scripts run as root; `$HOME` is usually `/var/root`. Result: LaunchAgent is installed for root, not for the logged-in user. Agent may not run in the intended user session.

So: **current behavior is undefined for non-interactive installs.** Manual QA is needed to confirm exact `$HOME` and console user detection for (1) double-click install, (2) `sudo installer -pkg ... -target /`, and (3) MDM deployment.

## LaunchAgent Loading

- Postinstall loads the plist with `launchctl bootstrap "gui/$REAL_UID" "$PLIST_PATH"`. For this to work, the plist must be in that user's LaunchAgents and owned by that user. When `$HOME` is `/var/root`, the plist is root's; the agent runs in root's GUI domain, which is not the logged-in user's session.
- **Manual QA:** After install (interactive and sudo), run `launchctl list | grep detec` and `launchctl print gui/$(id -u)` to confirm whether the LaunchAgent is loaded and in which domain.

## Behavior After Reboot

- LaunchAgents with **LimitLoadToSessionType = Aqua** run only in a **graphical (Aqua) login session**. They do **not** run at boot before any user logs in.
- So: **agent starts only at user login**, and only for the user whose LaunchAgents directory received the plist. After a reboot with no one logged in, the agent is not running. After reboot and login, it runs only if the plist was installed for that user.

## Known Packaging Gaps (Pre-1.1.2)

1. **license.html:** `distribution.xml` references `license file="license.html"`, but `build-pkg.sh` does **not** copy `license.html` into the pkg resources directory. Only `welcome.html` and `readme.html` are copied. Result: installer may fail or show a broken license step when the user must accept the license.
2. **No postuninstall:** Removing the .app (or the component package) does not unload the LaunchAgent or remove `~/Library/LaunchAgents/com.detec.agent.plist`. Leftover plist can cause launch errors or duplicate behavior after reinstall.
3. **No LaunchDaemon:** There is no system-wide, boot-time persistence. Only LaunchAgent (user session, login-time) exists.

## Phase 1.1.3 Choice: LaunchDaemon

Phase 1.1.3 implements option **(B) LaunchDaemon** for persistence across reboot without login. The .pkg postinstall now installs a LaunchDaemon to `/Library/LaunchDaemons/com.detec.agent.plist` and uses system config under `/Library/Application Support/Detec`. The agent runs as root at boot. The collector reads system config first on macOS (`config_loader._platform_config_paths`). See `packaging/macos/scripts/postinstall` and `packaging/macos/com.detec.agent.plist`.

## Manual QA Checklist (Not Executed in Phase 1.1)

The following should be validated manually (Phase 1.1.4 or later):

- [ ] Clean Mac: install .pkg by double-click; note `$HOME` in postinstall logs if possible; confirm LaunchDaemon loaded; reboot (without login), confirm agent process and heartbeats.
- [ ] Clean Mac: install with `sudo installer -pkg ... -target /`; confirm LaunchDaemon in /Library/LaunchDaemons; reboot with and without login, confirm agent behavior.
- [ ] MDM: push .pkg; confirm LaunchDaemon and behavior after reboot.
- [ ] Uninstall: run uninstall script; confirm LaunchDaemon unloaded and no leftover plists.

## References

- Plan: `.cursor/plans/agent_reliability_admin_control.plan.md`
- Postinstall: `packaging/macos/scripts/postinstall`
- Preinstall: `packaging/macos/scripts/preinstall`
- Build: `packaging/macos/build-pkg.sh`, `packaging/macos/distribution.xml`
- LaunchDaemon plist (source): `packaging/macos/com.detec.agent.plist`
- Deploy plist (manual installs only): `deploy/macos/com.detec.agent.plist`
