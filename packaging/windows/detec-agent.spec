# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for detec-agent.exe.

Produces a one-directory bundle containing the collector agent, all Python
dependencies (psutil, cryptography, etc.), and the compat layer.

Build:
    cd packaging/windows
    pyinstaller detec-agent.spec

Output: dist/detec-agent/detec-agent.exe

Prerequisites:
    pip install pyinstaller pywin32
    pip install -e .   # from repo root, installs collector package
"""

from pathlib import Path

block_cipher = None

_root = Path(SPECPATH).resolve().parent.parent
_collector = _root / "collector"

# Hidden imports that PyInstaller may miss.
hiddenimports = [
    "psutil",
    "psutil._pswindows",
    "jsonschema",
    "watchdog",
    "msgpack",
    "win32timezone",
    "servicemanager",
    "pywintypes",
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
    "collector.compat",
    "collector.compat.processes",
    "collector.compat.network",
    "collector.compat.services",
    "collector.compat.identity",
    "collector.compat.paths",
    "collector.output.tcp_emitter",
    "protocol",
    "protocol.wire",
    "protocol.messages",
    "protocol.connection",
]

# Data files: schemas for event validation.
datas = []
_schemas = _root / "schemas"
if _schemas.is_dir():
    datas.append((str(_schemas), "schemas"))

a = Analysis(
    [str(_collector / "agent_cli.py")],
    pathex=[str(_collector), str(_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "rumps"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="detec-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(_root / "branding" / "Icon.ico") if (_root / "branding" / "Icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="detec-agent",
)
