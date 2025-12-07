# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

# Find LarsNet directory and models
larsnet_dir = Path('larsnet')
larsnet_models_dir = larsnet_dir / 'pretrained_larsnet_models'

# Build datas list for LarsNet components
datas = []

# Include LarsNet Python files and config
if larsnet_dir.exists():
    # LarsNet source files
    larsnet_py_files = list(larsnet_dir.glob('*.py'))
    for py_file in larsnet_py_files:
        datas.append((str(py_file), 'larsnet'))

    # Config file
    config_file = larsnet_dir / 'config.yaml'
    if config_file.exists():
        datas.append((str(config_file), 'larsnet'))

    # Pretrained models (if they exist)
    if larsnet_models_dir.exists():
        # Include all .pth files
        model_files = list(larsnet_models_dir.rglob('*.pth'))
        for model_file in model_files:
            relative_path = model_file.relative_to(larsnet_dir)
            dest_dir = f'larsnet/{relative_path.parent}'
            datas.append((str(model_file), dest_dir))
        print(f"[SPEC] Bundling {len(model_files)} model files (~565 MB)")

        # Include LICENSE.txt if it exists
        license_file = larsnet_models_dir / 'LICENSE.txt'
        if license_file.exists():
            datas.append((str(license_file), 'larsnet/pretrained_larsnet_models'))
    else:
        print("[SPEC] WARNING: pretrained_larsnet_models directory not found!")
else:
    print("[SPEC] WARNING: larsnet directory not found!")

a = Analysis(
    ['src/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'torch',
        'torchaudio',
        'soundfile',
        'numpy',
        'scipy',
        'scipy.signal',
        'librosa',
        'device',
        'lars_processor',
        'lars_processor_demucs',
        'lars_processor_larsnet',
        'larsnet',
        'larsnet.larsnet',
        'larsnet.unet',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='lars-service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
