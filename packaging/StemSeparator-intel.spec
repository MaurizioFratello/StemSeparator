# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for StemSeparator (Intel/x86_64)

Build command:
    pyinstaller packaging/StemSeparator-intel.spec

Output:
    dist/StemSeparator-intel.app
"""

import sys
from pathlib import Path

# Project paths
project_root = Path(SPECPATH).parent
resources_dir = project_root / 'resources'
ui_dir = project_root / 'ui'

# Application metadata
APP_NAME = 'Stem Separator'
APP_VERSION = '1.0.0'
BUNDLE_ID = 'com.mauriziofratello.stemseparator'

block_cipher = None


# Data files to bundle
# Build datas list dynamically to avoid errors with missing files
datas = []

# Translations
for json_file in (resources_dir / 'translations').glob('*.json'):
    datas.append((str(json_file), 'resources/translations'))

# AI Models - include all model files if they exist
for pattern in ['*.ckpt', '*.yaml', '*.th', '*.json', '*.txt', '*.onnx']:
    for model_file in (resources_dir / 'models').glob(pattern):
        datas.append((str(model_file), 'resources/models'))

# Theme files
theme_qss = ui_dir / 'theme' / 'stylesheet.qss'
if theme_qss.exists():
    datas.append((str(theme_qss), 'ui/theme'))

# Icons directory (if exists)
icons_dir = resources_dir / 'icons'
if icons_dir.exists() and any(icons_dir.iterdir()):
    datas.append((str(icons_dir), 'resources/icons'))

# ScreenCapture tool binary
# Try multiple possible build locations for the Swift binary
screencapture_tool_dir = project_root / 'packaging' / 'screencapture_tool'
binary_paths = [
    screencapture_tool_dir / '.build' / 'x86_64-apple-macosx' / 'release' / 'screencapture-recorder',
    screencapture_tool_dir / '.build' / 'release' / 'screencapture-recorder',
    screencapture_tool_dir / 'ScreenCaptureRecorder.app' / 'Contents' / 'MacOS' / 'screencapture-recorder',
]

screencapture_binary = None
for path in binary_paths:
    if path.exists() and path.is_file():
        screencapture_binary = path
        break

if screencapture_binary:
    # Bundle the binary to the root of sys._MEIPASS so it can be found
    datas.append((str(screencapture_binary), '.'))
    print(f"Bundling screencapture-recorder to app bundle root")
else:
    print("WARNING: screencapture-recorder binary not found. ScreenCaptureKit recording will not be available.")


# BeatNet Beat-Service binary
# WHY: Bundle the BeatNet beat detection service for loop analysis
# The binary is built separately with Python 3.8/3.9 (required for numba compatibility)
beatnet_service_dir = project_root / 'packaging' / 'beatnet_service'
beatnet_binary_paths = [
    # Primary: PyInstaller dist output
    beatnet_service_dir / 'dist' / 'beatnet-service',
    # Alternative: resources location
    project_root / 'resources' / 'beatnet' / 'beatnet-service',
]

beatnet_binary = None
for path in beatnet_binary_paths:
    if path.exists() and path.is_file():
        import os
        if os.access(path, os.X_OK):
            beatnet_binary = path
            print(f"Found beatnet-service binary: {path}")
            break
        else:
            # Try to make it executable
            try:
                os.chmod(path, 0o755)
                if os.access(path, os.X_OK):
                    beatnet_binary = path
                    print(f"Found and made executable: {path}")
                    break
            except Exception as e:
                print(f"Warning: Binary found but cannot make executable: {path} ({e})")

if beatnet_binary:
    # Bundle to app root for easy discovery by beat_service_client.py
    datas.append((str(beatnet_binary), '.'))
    print(f"Bundling beatnet-service to app bundle root")
else:
    print("WARNING: beatnet-service binary not found. BeatNet beat detection will use fallback.")
    print("  Build with: cd packaging/beatnet_service && ./build.sh")
    print("  Searched paths:")
    for path in beatnet_binary_paths:
        exists = "✓" if path.exists() else "✗"
        print(f"    {exists} {path}")

# LARS Service binary
# WHY: Bundle the LARS drum separation service for advanced drum processing
# The binary is built separately with Python 3.9/3.10 (required for LarsNet compatibility)
lars_service_dir = project_root / 'packaging' / 'lars_service'
lars_binary_paths = [
    # Primary: PyInstaller dist output
    lars_service_dir / 'dist' / 'lars-service',
    # Alternative: resources location
    project_root / 'resources' / 'lars' / 'lars-service',
]

lars_binary = None
for path in lars_binary_paths:
    if path.exists() and path.is_file():
        import os
        if os.access(path, os.X_OK):
            lars_binary = path
            print(f"Found lars-service binary: {path}")
            break
        else:
            # Try to make it executable
            try:
                os.chmod(path, 0o755)
                if os.access(path, os.X_OK):
                    lars_binary = path
                    print(f"Found and made executable: {path}")
                    break
            except Exception as e:
                print(f"Warning: Binary found but cannot make executable: {path} ({e})")

if lars_binary:
    # Bundle to app root for easy discovery by lars_service_client.py
    datas.append((str(lars_binary), '.'))
    print(f"Bundling lars-service to app bundle root")
else:
    print("WARNING: lars-service binary not found. LARS drum separation will not be available.")
    print("  Build with: cd packaging/lars_service && ./build.sh")
    print("  Searched paths:")
    for path in lars_binary_paths:
        exists = "✓" if path.exists() else "✗"
        print(f"    {exists} {path}")

# FFmpeg: Bundle in separate directory to avoid conflicts with PySide6
# Place in Resources/bin/ with proper library isolation
ffmpeg_binary = None
ffmpeg_search_paths = [
    Path('/usr/local/bin/ffmpeg'),     # Intel Homebrew
    Path('/opt/homebrew/bin/ffmpeg'),  # Apple Silicon Homebrew
    Path('/usr/bin/ffmpeg'),           # System
]

for path in ffmpeg_search_paths:
    if path.exists() and os.access(path, os.X_OK):
        ffmpeg_binary = path
        print(f"Found ffmpeg: {path}")
        break

if ffmpeg_binary:
    # Bundle to Resources/bin/ (isolated from Frameworks and PySide6)
    datas.append((str(ffmpeg_binary), 'bin'))
    print(f"Bundling ffmpeg to Resources/bin/")

    # Bundle FFmpeg dylibs from homebrew
    import subprocess
    try:
        # Get list of dylib dependencies
        otool_output = subprocess.check_output(['otool', '-L', str(ffmpeg_binary)], text=True)
        for line in otool_output.split('\n')[1:]:  # Skip first line (the binary itself)
            line = line.strip()
            if not line or line.startswith('/usr/lib/') or line.startswith('/System/'):
                continue  # Skip system libraries

            # Extract dylib path (before the first '(')
            dylib_path = line.split('(')[0].strip()
            if dylib_path and Path(dylib_path).exists():
                # Bundle FFmpeg's dylibs to same bin/ directory
                datas.append((dylib_path, 'bin'))
                print(f"  Bundling FFmpeg dylib: {Path(dylib_path).name}")
    except Exception as e:
        print(f"Warning: Could not bundle FFmpeg dylibs: {e}")
else:
    print("WARNING: ffmpeg not found. App will require users to install it.")
    print("  Install with: brew install ffmpeg")

# Bundle audio_separator resource files (e.g., models-scores.json)
# Use PyInstaller's collect_data_files to properly bundle package data
try:
    from PyInstaller.utils.hooks import collect_data_files
    audio_sep_datas = collect_data_files('audio_separator')
    if audio_sep_datas:
        datas.extend(audio_sep_datas)
        print(f"Bundled {len(audio_sep_datas)} audio_separator data file(s)")
    else:
        print("WARNING: No audio_separator data files found")
except Exception as e:
    print(f"WARNING: Could not collect audio_separator data files: {e}")


# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Audio separator
    'audio_separator',
    'audio_separator.separator',
    'audio_separator.separator.architectures',
    'audio_separator.separator.architectures.demucs_separator',
    'audio_separator.separator.architectures.mdx_separator',
    'audio_separator.separator.architectures.mdxc_separator',
    'audio_separator.separator.architectures.vr_separator',
    'audio_separator.separator.common_separator',

    # Audio libraries
    'soundcard',
    'soundfile',
    'sounddevice',
    'rtmixer',

    # PyTorch and related
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.cuda',              # Needed even for CPU-only builds (module-level refs)
    'torchaudio',
    'onnxruntime',

    # Audio processing
    'librosa',
    'librosa.core',
    'librosa.feature',
    'resampy',
    'pydub',
    'scipy',
    'scipy.signal',
    'scipy.ndimage',

    # PySide6 modules
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtMultimedia',

    # Utilities
    'numpy',
    'yaml',
    'requests',
    'tqdm',
    'colorlog',

    # Subprocess modules
    'multiprocessing',
    'subprocess',
]


# Binaries to exclude (reduce size)
excludes = [
    # Test frameworks
    'pytest',
    'pytest_qt',
    'pytest_cov',
    'pytest_mock',

    # Development tools
    'black',
    'flake8',
    'pylint',

    # Documentation
    'sphinx',
    'docutils',

    # Unnecessary GUI toolkits
    'tkinter',
    'matplotlib',
    'PyQt5',        # Exclude conflicting Qt binding (app uses PySide6)
    'PyQt6',        # Exclude conflicting Qt binding (app uses PySide6)
]


# Ensure build directory exists for PyInstaller
# WHY: PyInstaller needs this directory to create base_library.zip during analysis
build_dir = project_root / 'build' / 'StemSeparator-intel'
build_dir.mkdir(parents=True, exist_ok=True)
dist_dir = project_root / 'dist'
dist_dir.mkdir(parents=True, exist_ok=True)


a = Analysis(
    [str(project_root / 'main.py')],
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
    name='StemSeparator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',  # Intel
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StemSeparator',
)

app = BUNDLE(
    coll,
    name='StemSeparator-intel.app',
    icon=str(resources_dir / 'icons' / 'app_icon.icns') if (resources_dir / 'icons' / 'app_icon.icns').exists() else None,
    bundle_identifier=BUNDLE_ID,
    version=APP_VERSION,
    info_plist={
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleIdentifier': BUNDLE_ID,
        'NSHumanReadableCopyright': 'Copyright © 2024 Maurizio Fratello',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.15.0',  # macOS Catalina
        'NSRequiresAquaSystemAppearance': 'False',  # Support dark mode

        # Audio permissions
        'NSMicrophoneUsageDescription': 'StemSeparator needs access to record system audio for stem separation.',
        
        # Screen Recording permission (required for ScreenCaptureKit on macOS 13+)
        'NSScreenCaptureUsageDescription': 'StemSeparator needs screen recording access to capture system audio without requiring BlackHole driver installation.',

        # Document types
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Audio File',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': [
                    'public.audio',
                    'public.mp3',
                    'public.aac-audio',
                    'com.microsoft.waveform-audio',
                ],
            }
        ],

        # UTI exports
        'UTExportedTypeDeclarations': [],
    },
)
