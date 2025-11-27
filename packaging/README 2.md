# StemSeparator Packaging

This directory contains all files needed to package StemSeparator as a standalone macOS application.

## Build Requirements

- macOS 10.15 (Catalina) or later
- Python 3.11 (recommended)
- All dependencies from `requirements.txt` and `requirements-build.txt`

## Architecture Builds

We create separate builds for:
- **Intel (x86_64)**: For Intel-based Macs
- **Apple Silicon (arm64)**: For M1/M2/M3 Macs

## Building

### Intel Build
```bash
./packaging/build_intel.sh
```

### Apple Silicon Build
```bash
./packaging/build_arm64.sh
```

### Build All
```bash
./packaging/build_all.sh
```

## Directory Structure

```
packaging/
├── README.md                    # This file
├── hooks/                       # PyInstaller custom hooks
├── dmg/                         # DMG installer resources
│   ├── background.png          # DMG background image
│   └── settings.py             # dmgbuild configuration
├── icon.icns                    # Application icon
├── StemSeparator-intel.spec    # PyInstaller spec for Intel
├── StemSeparator-arm64.spec    # PyInstaller spec for Apple Silicon
├── build_intel.sh              # Intel build script
├── build_arm64.sh              # Apple Silicon build script
└── build_all.sh                # Build both architectures
```

## Output

Built applications will be in:
- `dist/StemSeparator-intel.app` (Intel)
- `dist/StemSeparator-arm64.app` (Apple Silicon)
- `dist/StemSeparator-intel.dmg` (Intel installer)
- `dist/StemSeparator-arm64.dmg` (Apple Silicon installer)

## App Size

Expected sizes:
- Application bundle: ~1.2-1.5 GB (includes all models and PyTorch)
- DMG installer: ~600-800 MB (compressed)

## What's Bundled

- All Python dependencies (PySide6, PyTorch, audio-separator, etc.)
- All 4 AI models (~800MB):
  - mel-roformer (100MB)
  - bs-roformer (300MB)
  - demucs_6s (240MB)
  - demucs_4s (160MB)
- Translations (German, English)
- Theme files

## What's NOT Bundled

- **BlackHole 2ch audio driver**: Users must install separately for recording feature
  - App will prompt and assist with installation when needed
