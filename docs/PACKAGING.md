# StemSeparator - Packaging Guide

Complete guide to creating standalone macOS application bundles for StemSeparator.

## Quick Start

```bash
# 1. Install build dependencies
pip install -r requirements-build.txt

# 2. Download all AI models (~800MB)
python packaging/download_models.py

# 3. Build for your architecture
./packaging/build_intel.sh      # Intel Macs
./packaging/build_arm64.sh       # Apple Silicon (M1/M2/M3)
./packaging/build_all.sh         # Both architectures

# 4. Test the application
open dist/StemSeparator-*.app

# 5. Distribute the DMG
# dist/StemSeparator-intel.dmg or dist/StemSeparator-arm64.dmg
```

## What Gets Bundled

The packaged application is completely standalone and includes:

### Core Application
- Python 3.11 runtime
- All Python dependencies (PySide6, PyTorch, audio libraries)
- Application code (UI, core logic, utilities)

### AI Models (~800MB)
- **mel-roformer** (100MB) - 2 stems: Vocals, Instrumental
- **bs-roformer** (300MB) - 4 stems: Vocals, Drums, Bass, Other
- **demucs_6s** (240MB) - 6 stems: Vocals, Drums, Bass, Piano, Guitar, Other
- **demucs_4s** (160MB) - 4 stems: Vocals, Drums, Bass, Other

### Resources
- Translations (German, English)
- UI theme files
- Icons

### NOT Bundled
- **BlackHole 2ch** - System audio driver (must be installed separately)
  - Only needed for recording feature
  - App will prompt user to install when needed

## Prerequisites

### System Requirements
- macOS 10.15 (Catalina) or later
- For Intel build: Intel-based Mac or Rosetta 2
- For ARM build: Apple Silicon Mac (M1/M2/M3)

### Development Environment
- Python 3.11 (recommended)
- Xcode Command Line Tools: `xcode-select --install`
- All runtime dependencies: `pip install -r requirements.txt`
- All build dependencies: `pip install -r requirements-build.txt`

## Detailed Build Process

### Step 1: Prepare Models

Models must be downloaded before building:

```bash
python packaging/download_models.py
```

This downloads ~800MB of AI models. **This is required** - the build will fail if models are missing.

Verify models:
```bash
ls -lh resources/models/
```

You should see `.ckpt`, `.yaml`, and `.th` files.

### Step 2: (Optional) Create Custom Icon

Create a custom app icon:

1. Design a 1024x1024 PNG icon
2. Convert to `.icns` format (see `packaging/ICON_README.md`)
3. Save as `packaging/icon.icns`

If no icon is provided, the default Python icon will be used.

### Step 3: Build Application

Choose your build script based on target architecture:

#### Intel (x86_64)
```bash
./packaging/build_intel.sh
```

**Output:**
- `dist/StemSeparator-intel.app` (1.2-1.5GB)
- `dist/StemSeparator-intel.dmg` (600-800MB compressed)

#### Apple Silicon (arm64)
```bash
./packaging/build_arm64.sh
```

**Output:**
- `dist/StemSeparator-arm64.app` (1.2-1.5GB)
- `dist/StemSeparator-arm64.dmg` (600-800MB compressed)

#### Both Architectures
```bash
./packaging/build_all.sh
```

Builds both Intel and ARM versions sequentially.

### Step 4: Test Application

**Basic test:**
```bash
open dist/StemSeparator-*.app
```

**Test DMG installer:**
```bash
open dist/StemSeparator-*.dmg
# Drag app to Applications folder
open /Applications/StemSeparator.app
```

**IMPORTANT:** Test on a clean Mac without Python installed to ensure it's truly standalone!

## Testing Checklist

### Functional Tests
- [ ] Application launches without errors
- [ ] No console/terminal window appears
- [ ] UI renders with correct theme
- [ ] Can upload audio file via drag-and-drop
- [ ] Can select model and quality preset
- [ ] Separation completes successfully
- [ ] Output files created in correct location
- [ ] Can play separated stems in Player tab
- [ ] Settings dialog works
- [ ] Language switching works (German ↔ English)
- [ ] Queue shows active/completed tasks

### Recording Feature
- [ ] Recording tab detects missing BlackHole
- [ ] "Install BlackHole" button works
- [ ] After BlackHole install, can record system audio

### System Integration
- [ ] App survives force quit gracefully
- [ ] Settings persist after restart
- [ ] File associations work (if configured)
- [ ] macOS notifications work

### Clean System Test
**Most critical:** Test on a Mac that doesn't have:
- Python installed
- Development tools
- Conda/pip

This ensures the app is truly standalone.

## Build Configuration

### PyInstaller Spec Files

Two spec files define the build configuration:

- `packaging/StemSeparator-intel.spec` - Intel (x86_64)
- `packaging/StemSeparator-arm64.spec` - Apple Silicon (arm64)

**Key differences:**
- `target_arch`: `x86_64` vs `arm64`
- Minimum macOS version: 10.15 (Intel) vs 11.0 (ARM)
- ARM spec includes `torch.backends.mps` for Metal GPU support

**What they include:**
- All data files (models, translations, themes)
- Hidden imports (PyTorch, audio libraries, etc.)
- Excluded packages (tests, dev tools)
- macOS-specific metadata (bundle ID, version, permissions)

### Customizing the Build

Edit the spec files to customize:

**Bundle Identifier:**
```python
BUNDLE_ID = 'com.yourcompany.stemseparator'
```

**Version:**
```python
APP_VERSION = '1.0.0'
```

**Exclude more packages to reduce size:**
```python
excludes = [
    'matplotlib',
    'jupyter',
    # Add more here
]
```

**Add hidden imports if PyInstaller misses dependencies:**
```python
hiddenimports = [
    'your_module',
    # Add more here
]
```

## Troubleshooting

### Build Errors

**"ModuleNotFoundError" during build**
- Missing hidden import in spec file
- Add module to `hiddenimports` list

**"No models found" warning**
- Run `python packaging/download_models.py`
- Verify files exist in `resources/models/`

**"PyInstaller not found"**
- Install: `pip install -r requirements-build.txt`

### Runtime Errors

**App won't launch - "damaged and can't be opened"**
- Cause: macOS Gatekeeper blocking unsigned app
- Solution 1: Right-click app → "Open" → Confirm
- Solution 2: System Preferences → Security → "Open Anyway"
- Solution 3: Disable Gatekeeper temporarily:
  ```bash
  sudo spctl --master-disable
  # Re-enable after: sudo spctl --master-enable
  ```

**App crashes immediately**
- Check Console.app for error logs
- Run from Terminal to see errors:
  ```bash
  /Applications/StemSeparator.app/Contents/MacOS/StemSeparator
  ```

**"Models not found" error at runtime**
- Models weren't bundled properly
- Check `StemSeparator.app/Contents/Resources/resources/models/`
- Rebuild with models downloaded

**Subprocess errors**
- Check if `sys.executable` is correct in bundled environment
- Verify `core.separation_subprocess` module is bundled

### Size Issues

**App is too large (>2GB)**
- Check if debug symbols are included
- Review `excludes` in spec file
- Consider excluding some models (edit spec file)

**App is too small (<500MB)**
- Models probably weren't bundled
- Check build output for warnings
- Verify models exist before building

## Advanced: Code Signing & Notarization

For professional distribution without security warnings:

### Requirements
- Apple Developer account ($99/year)
- Developer ID Application certificate

### Steps

**1. Sign the application:**
```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  --options runtime \
  dist/StemSeparator-*.app
```

**2. Create signed DMG:**
```bash
hdiutil create -volname "Stem Separator" \
  -srcfolder dist/StemSeparator-*.app \
  -ov -format UDZO \
  dist/StemSeparator-signed.dmg

codesign --sign "Developer ID Application: Your Name (TEAM_ID)" \
  dist/StemSeparator-signed.dmg
```

**3. Notarize with Apple:**
```bash
# Submit for notarization
xcrun notarytool submit dist/StemSeparator-signed.dmg \
  --apple-id your@email.com \
  --password "app-specific-password" \
  --team-id TEAM_ID \
  --wait

# Staple notarization ticket
xcrun stapler staple dist/StemSeparator-signed.dmg
```

**4. Verify:**
```bash
spctl -a -vvv -t install dist/StemSeparator-signed.dmg
```

## Distribution

### GitHub Releases

1. **Create release tag:**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

2. **Upload DMG files:**
   - Go to GitHub → Releases → Draft new release
   - Attach `StemSeparator-intel.dmg`
   - Attach `StemSeparator-arm64.dmg`
   - Add release notes

### User Installation Instructions

Include these instructions with your release:

```markdown
## Installation

### Intel Macs
1. Download `StemSeparator-intel.dmg`
2. Open the DMG file
3. Drag "Stem Separator" to Applications folder
4. Right-click the app and select "Open" (first time only)

### Apple Silicon Macs (M1/M2/M3)
1. Download `StemSeparator-arm64.dmg`
2. Open the DMG file
3. Drag "Stem Separator" to Applications folder
4. Right-click the app and select "Open" (first time only)

### Using the Recording Feature
The recording feature requires BlackHole 2ch audio driver:
1. Open Stem Separator
2. Go to Recording tab
3. Click "Install BlackHole" and follow instructions
```

## Continuous Integration

For automated builds on GitHub Actions:

Create `.github/workflows/build-macos.yml`:

```yaml
name: Build macOS Applications

on:
  release:
    types: [created]
  workflow_dispatch:

jobs:
  build-intel:
    runs-on: macos-12  # Intel runner
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-build.txt
      - run: python packaging/download_models.py
      - run: ./packaging/build_intel.sh
      - uses: actions/upload-artifact@v3
        with:
          name: StemSeparator-intel
          path: dist/StemSeparator-intel.dmg

  build-arm64:
    runs-on: macos-14  # Apple Silicon runner
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-build.txt
      - run: python packaging/download_models.py
      - run: ./packaging/build_arm64.sh
      - uses: actions/upload-artifact@v3
        with:
          name: StemSeparator-arm64
          path: dist/StemSeparator-arm64.dmg
```

## File Structure

After building, your project will have:

```
StemSeparator/
├── dist/
│   ├── StemSeparator-intel.app/       # Intel application bundle
│   │   └── Contents/
│   │       ├── MacOS/
│   │       │   └── StemSeparator      # Executable
│   │       ├── Resources/
│   │       │   ├── resources/
│   │       │   │   ├── models/        # Bundled AI models
│   │       │   │   └── translations/  # i18n files
│   │       │   └── ui/theme/          # QSS stylesheet
│   │       ├── Frameworks/            # Bundled libraries
│   │       └── Info.plist             # App metadata
│   ├── StemSeparator-intel.dmg        # Intel installer
│   ├── StemSeparator-arm64.app/       # ARM application bundle
│   └── StemSeparator-arm64.dmg        # ARM installer
│
├── build/                              # Temporary build files (ignored)
└── packaging/
    ├── StemSeparator-intel.spec       # Intel build config
    ├── StemSeparator-arm64.spec       # ARM build config
    ├── build_intel.sh                 # Intel build script
    ├── build_arm64.sh                 # ARM build script
    └── download_models.py             # Model downloader
```

## User Data Location

When running the bundled app, user data is stored in:

**macOS:** `~/Library/Application Support/StemSeparator/`

This directory contains:
- `logs/` - Application logs
- `temp/` - Temporary processing files
- Settings (managed by Qt)

The bundled app resources (models, translations) remain in the read-only app bundle.

## Support

For build issues:
- Check [PyInstaller documentation](https://pyinstaller.org/)
- Check [PySide6 deployment guide](https://doc.qt.io/qtforpython/deployment.html)
- Open an issue on GitHub

---

**Happy packaging! 🎉**
