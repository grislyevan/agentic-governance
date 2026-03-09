# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for detec-server.exe.

Produces a one-directory bundle containing the FastAPI server, all Python
dependencies, Alembic migrations, and the pre-built React dashboard.

Build:
    cd packaging/windows
    pyinstaller detec-server.spec

Output: dist/detec-server/detec-server.exe

Prerequisites:
    pip install pyinstaller pywin32
    cd dashboard && npm run build       # creates dashboard/dist/
"""

import os
from pathlib import Path

block_cipher = None

_root = Path(SPECPATH).resolve().parent.parent
_api = _root / "api"
_dashboard_dist = _root / "dashboard" / "dist"

# Verify dashboard has been built.
if not _dashboard_dist.is_dir():
    raise FileNotFoundError(
        f"Dashboard not built. Run 'cd dashboard && npm run build' first.\n"
        f"Expected: {_dashboard_dist}"
    )

# Collect data files: Alembic config, migrations, dashboard static files.
# Destinations are relative to sys._MEIPASS (_internal/ in onedir builds).
datas = [
    (str(_api / "alembic.ini"), "."),
    (str(_api / "alembic"), "alembic"),
    (str(_dashboard_dist), os.path.join("dashboard", "dist")),
]

# Hidden imports that PyInstaller may miss.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "passlib.handlers.bcrypt",
    "win32timezone",
    "servicemanager",
    "pywintypes",
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(
    [str(_api / "server_cli.py")],
    pathex=[str(_api)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL"],
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
    name="detec-server",
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
    name="detec-server",
)
