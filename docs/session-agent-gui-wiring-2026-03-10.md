# Session: Agent GUI Wiring (2026-03-10)

## Objective

Wire up the macOS and Windows endpoint agents so they build, launch, and display correctly after download. Ensure the status window matches the design spec and the system tray icon appears.

## What Was Done

### 1. Centralized version constants

Previously, the version (`"0.3"`) and build number (`"0.3.0"`) were hardcoded independently in three places: `collector/gui/statuswindow.py` (macOS), `collector/gui/statuswindow_tk.py` (Windows), and `packaging/macos/detec-agent.spec` (Info.plist). A bump required editing all three and they could drift.

Created `collector/_version.py` as the single source of truth:

```python
__version__ = "0.3"
__build__ = "0.3.0"
```

All three consumers now import from this file. The macOS PyInstaller spec reads it at build time for `CFBundleVersion` and `CFBundleShortVersionString`.

**Files changed:** `collector/_version.py` (new), `collector/gui/statuswindow.py`, `collector/gui/statuswindow_tk.py`, `packaging/macos/detec-agent.spec`

### 2. Improved menu bar icon loading (macOS)

`get_menubar_icon_path()` in `collector/gui/assets.py` previously always generated the menu bar template icon at runtime via PyObjC rendering, even when pre-generated PNGs were bundled in the app. Updated to check the PyInstaller bundle (`sys._MEIPASS/icons/`) first, falling back to the cache (`~/.agentic-gov/icons/`), and only generating as a last resort.

**File changed:** `collector/gui/assets.py`

### 3. Fixed Windows agent import failures

Two classes of import resolution bugs prevented the Windows GUI agent (`detec-agent-gui.exe`) from launching:

**Problem A: `collector._version` not found**

`statuswindow_tk.py` imported `from collector._version import ...` (package-qualified), but:
- `collector._version` was not in the Windows PyInstaller specs' `hiddenimports`
- The Windows `tray.py` entry point adds `collector/` (not the project root) to `sys.path`, so the package-qualified import fails when running outside PyInstaller

Fix: Added `collector._version` to both Windows specs' hidden imports. Made the import in both status windows resilient with try/except (package-qualified first, bare fallback).

**Problem B: `agent._filelock` not found**

The import chain `tray.py` -> `daemon_bridge.py` -> `http_emitter.py` -> `buffer.py` crashed because `buffer.py` used a bare import (`from agent._filelock import file_lock`). In the PyInstaller bundle, the module was registered under its full package name (`collector.agent._filelock`), so the bare name was unresolvable.

The same issue affected `collector/agent/state.py`.

Fix: Made both imports resilient (package-qualified first, bare fallback). Added `collector.agent._filelock` to both Windows specs' hidden imports.

**Files changed:** `collector/gui/statuswindow.py`, `collector/gui/statuswindow_tk.py`, `collector/agent/buffer.py`, `collector/agent/state.py`, `packaging/windows/detec-agent-gui.spec`, `packaging/windows/detec-agent.spec`

### 4. Rebuilt and deployed both platforms

- **macOS**: Rebuilt via `build-app.sh`. Verified `Icon.icns`, menu bar template PNGs, and branding assets are bundled. `CFBundleVersion` reads `0.3.0` from `_version.py`.
- **Windows**: Rebuilt `detec-agent-gui.exe` on the Windows VM (`192.168.64.4`). Deployed to `C:\Program Files\Detec\Agent-GUI\`. Agent launches without errors (confirmed process running, PID 5780).

### 5. Updated documentation

- `CHANGELOG.md`: Added entries under `[Unreleased]` for version centralization and menu bar icon improvement.
- All existing docs referencing "Agent Status..." (ellipsis format) were already correct.

## Commits

| Hash | Message |
|------|---------|
| `f9562b0` | refactor: centralize version constants and improve menu bar icon loading |
| `e792c7d` | fix: Windows agent fails to import collector._version |
| `91c8a96` | fix: Windows agent crashes with 'No module named agent._filelock' |

All three commits are pushed to `origin/main`.

## Status Window Spec (confirmed in source)

- **Bottom left**: Current year in YYYY format (e.g., "2026")
- **Bottom right**: `Version 0.3 - Build no. 0.3.0`
- **Status text**: `Agent Status... Connected` (ellipsis, not colon)
- **Logo**: `branding/Icon.icns` (macOS) / `branding/Icon.png` (Windows)

## Known Future Work

- **Double-click-and-run**: ~~The server-generated ZIP puts `agent.env` alongside the `.pkg`/`.exe`, not inside it. For true zero-touch, the config needs to be baked into the installer itself.~~ **Resolved.** The macOS ZIP now includes `install.sh`, a wrapper script that copies `agent.env` and `collector.json` to `~/Library/Application Support/Detec/` before running the `.pkg`. Users run `bash install.sh` for a one-step install. The Windows `.exe` installer already embeds config directly.
- **Bare import cleanup**: The collector package mixes bare imports (`from config_loader import ...`) and package-qualified imports (`from collector.config_loader import ...`). The try/except pattern works but a full migration to package-qualified imports would eliminate the root cause.
