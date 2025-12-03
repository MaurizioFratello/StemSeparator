# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for StemSeparator (Apple Silicon/arm64)

Build command:
    pyinstaller packaging/StemSeparator-arm64.spec

Output:
    dist/StemSeparator-arm64.app
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
for pattern in ['*.ckpt', '*.yaml', '*.th', '*.json', '*.txt']:
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
# WHY: Bundle the Swift ScreenCaptureKit binary for native macOS 13+ audio recording
# The binary is searched in multiple locations to support different build configurations
screencapture_tool_dir = project_root / 'packaging' / 'screencapture_tool'
binary_paths = [
    # Primary: Architecture-specific build (arm64 on Apple Silicon)
    screencapture_tool_dir / '.build' / 'arm64-apple-macosx' / 'release' / 'screencapture-recorder',
    # Fallback: Generic release build
    screencapture_tool_dir / '.build' / 'release' / 'screencapture-recorder',
    # Alternative: App bundle location (if built as app)
    screencapture_tool_dir / 'ScreenCaptureRecorder.app' / 'Contents' / 'MacOS' / 'screencapture-recorder',
]

screencapture_binary = None
for path in binary_paths:
    if path.exists() and path.is_file():
        # Verify binary is executable
        import os
        if os.access(path, os.X_OK):
            screencapture_binary = path
            print(f"Found screencapture-recorder binary: {path}")
            break
        else:
            # Try to make it executable
            try:
                os.chmod(path, 0o755)
                if os.access(path, os.X_OK):
        screencapture_binary = path
                    print(f"Found and made executable: {path}")
        break
            except Exception as e:
                print(f"Warning: Binary found but cannot make executable: {path} ({e})")

if screencapture_binary:
    # Bundle the binary to the root of sys._MEIPASS so it can be found
    # WHY: Python code searches sys._MEIPASS root first, then Frameworks/
    # Placing it at root ensures it's found immediately
    datas.append((str(screencapture_binary), '.'))
    print(f"Bundling screencapture-recorder to app bundle root")
else:
    print("WARNING: screencapture-recorder binary not found. ScreenCaptureKit recording will not be available.")
    print("  Searched paths:")
    for path in binary_paths:
        exists = "✓" if path.exists() else "✗"
        print(f"    {exists} {path}")


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


# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Audio separator
    'audio_separator',
    'audio_separator.separator',

    # Audio libraries
    'soundcard',
    'soundfile',
    'sounddevice',
    'rtmixer',

    # PyTorch and related (with MPS support for Apple Silicon)
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.backends.mps',  # Apple Metal Performance Shaders
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

    # CUDA (macOS doesn't use CUDA)
    'torch.cuda',
    'torch.cudnn',
]


# Ensure build directory exists for PyInstaller
# WHY: PyInstaller needs this directory to create base_library.zip during analysis
# CRITICAL: This must exist before Analysis() is called, otherwise PyInstaller fails
build_dir = project_root / 'build' / 'StemSeparator-arm64'
try:
build_dir.mkdir(parents=True, exist_ok=True)
    # Verify directory was actually created and is writable
    if not build_dir.exists():
        raise RuntimeError(f"Failed to create build directory: {build_dir}")
    # Test write access by creating a temporary file
    test_file = build_dir / '.write_test'
    try:
        test_file.write_text('test')
        test_file.unlink()
    except Exception as e:
        raise RuntimeError(f"Build directory is not writable: {build_dir} ({e})")
except Exception as e:
    import sys
    print(f"ERROR: Cannot create build directory: {build_dir}")
    print(f"  Error: {e}")
    sys.exit(1)

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
    target_arch='arm64',  # Apple Silicon
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
    name='StemSeparator-arm64.app',
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
        'LSMinimumSystemVersion': '11.0.0',  # macOS Big Sur (first to support Apple Silicon)
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
