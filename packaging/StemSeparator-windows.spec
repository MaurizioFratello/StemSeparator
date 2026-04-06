# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Windows onedir build.

WHY:
- Use onedir for maintainability and clearer dependency packaging on Windows.
- Keep Windows-specific build separate to avoid any risk to stable macOS specs.
"""

from pathlib import Path
import os


project_root = Path.cwd()
app_name = "StemSeparator"
main_script = project_root / "main.py"

# Bundle runtime resources (read-only assets).
datas = [
    (str(project_root / "resources"), "resources"),
    (str(project_root / "ui" / "theme" / "stylesheet.qss"), "ui/theme"),
]

hiddenimports = [
    # Qt/PySide
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Audio stack
    "soundfile",
    "sounddevice",
    "soundcard",
    # Separation subprocess
    "core.separation_subprocess",
    # Torch backends (CPU/CUDA support paths)
    "torch",
    "torchaudio",
]

excludes = [
    "tests",
    "matplotlib",
    "jupyter",
]

block_cipher = None


a = Analysis(
    [str(main_script)],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "resources" / "icons" / "app_icon_1024.png")
    if (project_root / "resources" / "icons" / "app_icon_1024.png").exists()
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=app_name,
)
