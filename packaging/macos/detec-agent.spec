# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Detec Agent macOS .app bundle.

Build:
    cd <project-root>
    pyinstaller packaging/macos/detec-agent.spec

The resulting .app bundle appears in dist/Detec Agent.app
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

# Read version from the single source of truth
sys.path.insert(0, PROJECT_ROOT)
from collector._version import __version__, __build__

block_cipher = None

# All scanner modules must be listed as hidden imports because they
# are discovered dynamically in main.py rather than via static import.
SCANNER_MODULES = [
    'collector.scanner.aider',
    'collector.scanner.claude_code',
    'collector.scanner.claude_cowork',
    'collector.scanner.cline',
    'collector.scanner.constants',
    'collector.scanner.continue_ext',
    'collector.scanner.copilot',
    'collector.scanner.cursor',
    'collector.scanner.gpt_pilot',
    'collector.scanner.lm_studio',
    'collector.scanner.ollama',
    'collector.scanner.open_interpreter',
    'collector.scanner.openclaw',
]

HIDDEN_IMPORTS = [
    'rumps',
    'msgpack',
    'collector.gui',
    'collector.gui.menubar',
    'collector.gui.statuswindow',
    'collector.gui.assets',
    'collector.gui.daemon_bridge',
    'collector._version',
    'collector.main',
    'collector.config_loader',
    'collector.agent.state',
    'collector.agent.buffer',
    'collector.agent.credentials',
    'collector.output.emitter',
    'collector.output.http_emitter',
    'collector.output.tcp_emitter',
    'collector.engine.confidence',
    'collector.engine.policy',
    'collector.engine.container',
    'collector.enforcement.enforcer',
    'collector.enforcement.network_block',
    'collector.enforcement.proxy_inject',
    'collector.compat.identity',
    'collector.compat.paths',
    'collector.compat.services',
    'collector.scanner.base',
    'collector.providers.esf_provider',
    'protocol',
    'protocol.wire',
    'protocol.messages',
    'protocol.connection',
    *SCANNER_MODULES,
]

# Data files to bundle inside the .app
datas = [
    (os.path.join(PROJECT_ROOT, 'collector', 'config'), 'collector/config'),
    (os.path.join(PROJECT_ROOT, 'schemas'), 'schemas'),
]

# ESF helper binary for native macOS telemetry (built separately via Makefile)
_esf_helper_path = os.path.join(
    PROJECT_ROOT, 'collector', 'providers', 'esf_helper', 'esf_helper',
)
binaries = []
if os.path.isfile(_esf_helper_path):
    binaries.append((_esf_helper_path, 'Resources'))
else:
    print(f"NOTE: ESF helper not found at {_esf_helper_path}. "
          f"Build it with: make -C collector/providers/esf_helper")

# Include generated icon assets if they exist
icons_dir = os.path.join(SPECPATH, 'icons')
if os.path.isdir(icons_dir):
    datas.append((icons_dir, 'icons'))

# Branding assets (Icon.icns loaded at runtime by statuswindow)
_branding_dir = os.path.join(PROJECT_ROOT, 'branding')
for _asset in ('Icon.icns', 'Icon.png'):
    _asset_path = os.path.join(_branding_dir, _asset)
    if os.path.exists(_asset_path):
        datas.append((_asset_path, 'branding'))

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'collector', 'gui', 'menubar.py')],
    pathex=[
        PROJECT_ROOT,
        os.path.join(PROJECT_ROOT, 'collector'),
    ],
    binaries=binaries,
    datas=datas,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'distutils',
    ],
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
    name='detec-agent-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=os.path.join(SPECPATH, 'entitlements.plist'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Detec Agent',
)

# Resolve .icns path: prefer branding master, fall back to generated, then None
icns_path = os.path.join(PROJECT_ROOT, 'branding', 'Icon.icns')
if not os.path.exists(icns_path):
    icns_path = os.path.join(SPECPATH, 'icons', 'DetecAgent.icns')
if not os.path.exists(icns_path):
    icns_path = None

app = BUNDLE(
    coll,
    name='Detec Agent.app',
    icon=icns_path,
    bundle_identifier='com.detec.agent',
    info_plist={
        'CFBundleName': 'Detec Agent',
        'CFBundleDisplayName': 'Detec Agent',
        'CFBundleIdentifier': 'com.detec.agent',
        'CFBundleVersion': __build__,
        'CFBundleShortVersionString': __version__,
        'LSMinimumSystemVersion': '13.0',
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSHumanReadableCopyright': 'Copyright 2026 Detec. All rights reserved.',
        'NSEndpointSecurityEarlyBoot': False,
        'NSSystemExtensionUsageDescription':
            'Detec Agent uses a System Extension to monitor process, '
            'file, and network activity for agentic AI tool detection.',
    },
)
