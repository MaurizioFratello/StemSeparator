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

    # CUDA (macOS doesn't use CUDA)
    'torch.cuda',
    'torch.cudnn',
]


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
    icon=str(Path(SPECPATH) / 'icon.icns') if (Path(SPECPATH) / 'icon.icns').exists() else None,
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
