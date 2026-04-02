# Parking Lot — Known Issues & Future Fixes

Items discovered during MSI installer sprint (2026-03-25). Not blocking, address when convenient.

## CI / Build

- [x] **build-agent-msi.yml workflow broken** — Fixed 2026-04-01: added WiX harvest step for
  `AgentInternal.wxs` / `GuiInternal.wxs` fragments and multi-file `wix build` invocation
  matching the instructions in `DetecAgent.wxs`.
- [x] **MSI uploads lost on API container rebuild** — Fixed 2026-04-01: added `detec-packages`
  Docker volume mount in docker-compose.yml (`/data/packages/`) so uploads persist across
  container rebuilds.

## Agent / Scanner

- [x] **ETW ctypes backend not bundled** — Fixed 2026-04-01: `collector/providers/_etw_ctypes.py`
  implemented (stdlib-only ctypes ETW backend); added to PyInstaller `hiddenimports` in
  `detec-agent.spec`; `_check_ctypes_etw()` false-positive fixed with `importlib.util.find_spec`
  guard.
- [x] **Linux commands called on Windows** — Fixed 2026-04-01: `pgrep`/`lsof` calls in
  `claude_cowork.py`, `cline.py`, `claude_code.py`, and `continue_ext.py` replaced with
  psutil-backed `find_processes()` / `get_connections()` compat layer. All four scanners are
  now cross-platform.
- [x] **PowerShell version queries timeout** — Fixed 2026-04-01: `get_app_version()` in
  `compat/identity.py` now caches results per path (process-lifetime); added `-NonInteractive`
  flag; tries `pwsh` (PowerShell 7, faster startup) before `powershell.exe`; timeout reduced
  from 10s to 5s per attempt.

## Server / API

- [x] **ECE calibration test failure** — `test_ece_below_lenient_max` no longer exists in the
  test suite; all 7 calibration tests pass as of 2026-04-01.
- [x] **DETEC_API_URL must be set for MSI stamping** — Fixed 2026-04-01: documented in
  .env.example and SERVER.md; added Host header fallback in api/routers/agent_download.py so
  DETEC_API_URL is optional.

## Installer

- [x] **Stale agent.env from previous installs** — Fixed 2026-04-01: `_agent_env_is_valid()`
  check in collector/agent_cli.py; if the existing key returns non-200, re-extracts from
  installer trailer.
- [x] **WiX Heat not available in WiX v6** — Resolved 2026-04-01: using
  `wix extension add WixToolset.Heat` in CI (added to build-agent-msi.yml). Monitoring for
  upstream WiX v5+ support.
- [ ] **MajorUpgrade version handling** — Partially addressed 2026-04-01: version bump
  automation added to release.yml (sed replaces version from git tag). Still requires operator
  to verify version in DetecAgent.wxs before each release.
