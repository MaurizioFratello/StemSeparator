# Build Instructions for StemSeparator macOS Application

This guide will walk you through building a standalone macOS application bundle.

## Prerequisites

### Required Software

1. **macOS 10.15 (Catalina) or later**
2. **Python 3.11** (recommended)
   - Install via [python.org](https://www.python.org/downloads/macos/) or Homebrew
3. **Xcode Command Line Tools**
   ```bash
   xcode-select --install
   ```

### Required Packages

1. **Install runtime dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install build dependencies:**
   ```bash
   pip install -r requirements-build.txt
   ```

## Pre-Build Steps

### Step 1: Download All AI Models

**IMPORTANT:** Models must be downloaded BEFORE building. They will be bundled into the app.

```bash
python packaging/download_models.py
```

This will download ~800MB of AI models to `resources/models/`:
- mel-roformer (~100MB)
- bs-roformer (~300MB)
- demucs_6s (~240MB)
- demucs_4s (~160MB)

**Verify models are downloaded:**
```bash
ls -lh resources/models/
```

You should see:
- `model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt`
- `model_bs_roformer_ep_317_sdr_12.9755.ckpt`
- `htdemucs_6s.yaml` (+ related .th files)
- `htdemucs.yaml` (+ related .th files)

### Step 2: Create Application Icon (Optional)

If you have a custom icon:

1. Create a 1024x1024 PNG of your icon
2. Convert to .icns format (see `packaging/ICON_README.md`)
3. Save as `packaging/icon.icns`

If no icon is provided, the default Python icon will be used.

## Building

### Determine Your Architecture

Check your Mac's architecture:
```bash
uname -m
```

- `x86_64` = Intel Mac → Build Intel version
- `arm64` = Apple Silicon (M1/M2/M3) → Build ARM version

### Build for Intel (x86_64)

```bash
./packaging/build_intel.sh
```

**Output:** `dist/StemSeparator-intel.app` and `dist/StemSeparator-intel.dmg`

### Build for Apple Silicon (arm64)

```bash
./packaging/build_arm64.sh
```

**Output:** `dist/StemSeparator-arm64.app` and `dist/StemSeparator-arm64.dmg`

### Build Both Architectures

If you want to create both builds (requires appropriate hardware or cross-compilation):

```bash
./packaging/build_all.sh
```

## Build Process Details

Each build script performs these steps:

1. **Clean previous builds** (removes `build/` and `dist/`)
2. **Run PyInstaller** with architecture-specific settings
3. **Verify .app bundle** was created
4. **Create DMG installer** (compressed disk image)
5. **Show build summary** with file sizes

## Expected Output

### File Sizes

- **Application bundle (.app):** 1.2-1.5 GB
  - Includes Python, PyTorch, PySide6, audio libraries, all models
- **DMG installer (.dmg):** 600-800 MB (compressed)

### Directory Structure

```
dist/
├── StemSeparator-intel.app/        # Intel application bundle
│   └── Contents/
│       ├── MacOS/
│       │   └── StemSeparator      # Executable
│       ├── Resources/              # Bundled resources
│       │   ├── models/             # All 4 AI models
│       │   ├── translations/       # i18n files
│       │   └── ...
│       └── Info.plist              # App metadata
├── StemSeparator-intel.dmg         # Intel installer
├── StemSeparator-arm64.app/        # Apple Silicon bundle
└── StemSeparator-arm64.dmg         # Apple Silicon installer
```

## Testing the Build

### Basic Test

1. **Mount the DMG:**
   ```bash
   open dist/StemSeparator-intel.dmg  # or arm64
   ```

2. **Drag app to Applications** (or test directly)

3. **Launch the application:**
   ```bash
   open /Applications/StemSeparator.app
   ```

### Comprehensive Testing Checklist

- [ ] App launches without errors (no console/terminal window)
- [ ] UI renders correctly with theme
- [ ] Can select and upload audio file
- [ ] Can select model and quality preset
- [ ] Separation works (test with a short audio file)
- [ ] Output files are created in correct location
- [ ] Player tab works (can play separated stems)
- [ ] Settings dialog opens and saves preferences
- [ ] Language switching works (German/English)
- [ ] Queue tab shows active/completed tasks
- [ ] Recording tab detects missing BlackHole and offers installation

### Test on Clean System

**Most important:** Test on a Mac that doesn't have Python or development tools installed!

This ensures the app is truly standalone.

## Troubleshooting

### Build Fails: "ModuleNotFoundError"

- **Cause:** Missing dependency
- **Solution:** Add missing module to `hiddenimports` in the .spec file

### Build Fails: "command not found: pyinstaller"

- **Cause:** Build dependencies not installed
- **Solution:** `pip install -r requirements-build.txt`

### App Won't Launch: "damaged and can't be opened"

- **Cause:** macOS Gatekeeper blocking unsigned app
- **Solution:** Right-click app → "Open" → "Open" (confirm)
- **Alternative:** Disable Gatekeeper temporarily:
  ```bash
  sudo spctl --master-disable
  ```

### App Crashes on Launch

1. **Check Console logs:**
   - Open Console.app
   - Search for "StemSeparator"
   - Look for error messages

2. **Run from Terminal to see errors:**
   ```bash
   /Applications/StemSeparator.app/Contents/MacOS/StemSeparator
   ```

### Models Not Found After Build

- **Cause:** Models weren't downloaded before building
- **Solution:** Run `python packaging/download_models.py` and rebuild

### Huge File Size (>2GB)

- **Cause:** May include debugging symbols or unnecessary files
- **Solution:** Check `.spec` file `excludes` and `binaries` sections

## Distribution

### For Users

1. **Upload DMG to GitHub Releases:**
   ```bash
   # Tag a release
   git tag v1.0.0
   git push origin v1.0.0

   # Upload DMG files via GitHub web interface
   ```

2. **Provide installation instructions:**
   - Download appropriate DMG (Intel or Apple Silicon)
   - Open DMG
   - Drag StemSeparator to Applications folder
   - Right-click and "Open" first time (if unsigned)
   - For recording: Install BlackHole 2ch when prompted

### Optional: Code Signing & Notarization

For professional distribution without security warnings:

1. **Purchase Apple Developer account** ($99/year)
2. **Get Developer ID certificate**
3. **Sign the application:**
   ```bash
   codesign --deep --force --verify --verbose \
     --sign "Developer ID Application: Your Name" \
     --options runtime \
     dist/StemSeparator.app
   ```
4. **Notarize with Apple** (see Apple's documentation)

This is optional but recommended for wider distribution.

## Continuous Integration (Optional)

For automated builds on every release, see:
- `.github/workflows/build-macos.yml` (to be created)
- Use GitHub Actions with macOS runners
- Build and upload DMGs automatically

## Need Help?

- Check PyInstaller documentation: https://pyinstaller.org/
- Check PySide6 deployment guide: https://doc.qt.io/qtforpython/deployment.html
- Open an issue on GitHub
