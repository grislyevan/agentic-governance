# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for detec-agent-gui.exe (Windows tray application).

Produces a one-directory bundle containing the GUI tray agent with
tkinter status window, pystray tray icon, and all scanning components.

Build:
    cd packaging/windows
    pyinstaller detec-agent-gui.spec

Output: dist/detec-agent-gui/detec-agent-gui.exe

Prerequisites:
    pip install pyinstaller pywin32 pystray Pillow
    pip install -e .   # from repo root
"""

from pathlib import Path

block_cipher = None

_root = Path(SPECPATH).resolve().parent.parent
_collector = _root / "collector"

hiddenimports = [
    "pystray",
    "pystray._win32",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "psutil",
    "psutil._pswindows",
    "jsonschema",
    "watchdog",
    "msgpack",
    "win32timezone",
    "tkinter",
    "collector._version",
    "collector.gui",
    "collector.gui.tray",
    "collector.gui.statuswindow_tk",
    "collector.gui.daemon_bridge",
    "collector.gui.assets",
    "collector.main",
    "collector.config_loader",
    "collector.agent.state",
    "collector.agent.buffer",
    "collector.agent.credentials",
    "collector.output.emitter",
    "collector.output.http_emitter",
    "collector.output.tcp_emitter",
    "collector.engine.confidence",
    "collector.engine.policy",
    "collector.engine.container",
    "collector.enforcement.enforcer",
    "collector.enforcement.network_block",
    "collector.enforcement.proxy_inject",
    "collector.compat.identity",
    "collector.compat.paths",
    "collector.compat.services",
    "collector.scanner",
    "collector.scanner.aider",
    "collector.scanner.claude_code",
    "collector.scanner.claude_cowork",
    "collector.scanner.cline",
    "collector.scanner.continue_ext",
    "collector.scanner.copilot",
    "collector.scanner.cursor",
    "collector.scanner.gpt_pilot",
    "collector.scanner.lm_studio",
    "collector.scanner.ollama",
    "collector.scanner.open_interpreter",
    "collector.scanner.openclaw",
    "protocol",
    "protocol.wire",
    "protocol.messages",
    "protocol.connection",
]

datas = []
_schemas = _root / "schemas"
if _schemas.is_dir():
    datas.append((str(_schemas), "schemas"))

_branding = _root / "branding"
if _branding.is_dir():
    for fname in ("Icon.ico", "Icon.png"):
        fpath = _branding / fname
        if fpath.exists():
            datas.append((str(fpath), "branding"))

_config = _collector / "config"
if _config.is_dir():
    datas.append((str(_config), "collector/config"))

a = Analysis(
    [str(_collector / "gui" / "tray.py")],
    pathex=[str(_collector), str(_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "rumps"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_ico = _root / "branding" / "Icon.ico"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="detec-agent-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(_ico) if _ico.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="detec-agent-gui",
)
