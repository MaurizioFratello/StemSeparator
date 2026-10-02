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
# Replace "Your Name (TEAM_ID)" with your actual Apple Developer ID
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

# Replace "Your Name (TEAM_ID)" with your actual Apple Developer ID
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

**Windows:** `%LOCALAPPDATA%\StemSeparator\` (falls back to `%APPDATA%`), with
downloaded model weights under `%LOCALAPPDATA%\StemSeparator\Cache\models\`.

**Linux:** `$XDG_DATA_HOME/StemSeparator/` (falls back to
`~/.local/share/StemSeparator/`), with downloaded model weights under
`~/.cache/StemSeparator/models/`.

Both come from `utils.platform_utils.user_data_dir()` /
`user_cache_dir()`; the values the frozen Linux build actually used are printed
in its runtime log (see the `Platform: {...}` line below).

## Building for Linux

The Linux build is a PyInstaller **onedir** bundle: `dist/StemSeparator-linux/`
holds the launcher and an `_internal/` directory with the interpreter, the
collected libraries and the bundled resources. Onedir is deliberate — the
alternative (onefile) unpacks ~7 GB of torch/onnxruntime into `/tmp` on every
launch.

```bash
# 0. From the repository root, with the interpreter you build with.
PY=/path/to/venv/bin/python            # CPython 3.11

# 1. Vendor the native inputs (gitignored; see packaging/vendor/README.md).
"$PY" packaging/vendor/fetch_vendor.py --platform linux
"$PY" packaging/vendor/fetch_vendor.py --check --platform linux

# 2. Application + build dependencies.
"$PY" -m pip install -r requirements.txt -r requirements-build.txt

# 3. Build. KMP_DUPLICATE_LIB_OK/OMP_NUM_THREADS mirror what
#    core/separator.py sets for its separation workers: torch ships its own
#    OpenMP runtime and a second one loaded by a dependency aborts the process.
export KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1
"$PY" -m PyInstaller --noconfirm --clean packaging/linux/StemSeparator-linux.spec

# 4. Smoke-test headless, then run it for real on a desktop session.
QT_QPA_PLATFORM=offscreen ./dist/StemSeparator-linux/StemSeparator-linux
```

The result of step 3 on this machine (7.3 GB, ~2 min):

```
[StemSeparator-linux.spec] collected 32 audio_separator data file(s)
[StemSeparator-linux.spec] bundling ffmpeg from .../packaging/vendor/linux/bin -> bin/
[StemSeparator-linux.spec] bundling ffprobe from .../packaging/vendor/linux/bin -> bin/
[StemSeparator-linux.spec] rubberband CLI not found; time stretching uses the pyrubberband/librosa chain
[StemSeparator-linux.spec] collected 36 NVIDIA CUDA library file(s)
128375 INFO: Build complete! The results are available in: .../dist
```

and the headless smoke test (step 4) logs — the same lines land in
`~/.local/share/StemSeparator/logs/app.log`:

```
INFO     Single-instance lock acquired: /home/.../.local/share/StemSeparator/.stemseparator.lock
INFO     Starting Stem Separator v1.0.3
INFO     Platform: {'os': 'Linux', 'platform': 'linux', 'frozen': True,
         'data_dir': '/home/.../.local/share/StemSeparator',
         'cache_dir': '/home/.../.cache/StemSeparator',
         'ffmpeg': '/home/.../dist/StemSeparator-linux/_internal/bin/ffmpeg',
         'ffprobe': '/home/.../dist/StemSeparator-linux/_internal/bin/ffprobe',
         'rubberband': None, 'multiprocessing': 'spawn'}
INFO     Model 'demucs_4s' found and verified (bundled: .../_internal/resources/models/htdemucs.yaml)
INFO     Initialization complete
```

`ffmpeg`/`ffprobe` resolving *inside* the bundle is the acceptance criterion for
the vendoring: those paths come from `utils.platform_utils.bundled_binary_dirs()`,
which probes `<sys._MEIPASS>/bin` first. The separation worker reaches the same
directory through `utils.platform_utils.ensure_binaries_on_path()` plus the
`PATH` that `core/separator.py` prepends for the child, so `audio-separator`'s
own probe reports the vendored build instead of a system one:

```
INFO - FFmpeg installed: ffmpeg version 7.0.2-static https://johnvansickle.com/ffmpeg/
```

Requirements for the target machine:

* **glibc >= 2.34.** PySide6 6.10 publishes only `manylinux_2_34` wheels
  (Ubuntu 22.04+, Debian 12+), so an older distro cannot install the
  dependencies at all.
* A working `xcb` (X11) or Wayland session for the GUI; the offscreen plugin
  (`_internal/PySide6/Qt/plugins/platforms/libqoffscreen.so`, bundled) is for
  headless runs only and is what CI uses.
* `libasound.so.2`, `libjack.so.0`, `libpulse.so.0` for the vendored PortAudio
  (see `packaging/vendor/README.md`).

## Building for Windows

Run this **on a Windows 10/11 x64 machine** — the spec, the Inno Setup script and
the vendor layout are complete and statically checked, but no Windows build was
produced from this Linux workstation.

```bat
REM 0. CPython 3.11 (the wheel set below is cp311), from the repository root.
py -3.11 -m venv .venv & .venv\Scripts\activate

REM 1. Vendor FFmpeg (gitignored; see packaging/vendor/README.md).
python packaging\vendor\fetch_vendor.py --platform windows
python packaging\vendor\fetch_vendor.py --check --platform windows

REM 2. The application icon is generated from the source PNG; commit the result.
python packaging\windows\generate_ico.py

REM 3. Dependencies. CPU-only installs plain requirements.txt; a GPU build adds
REM    requirements-cuda.txt (see "CUDA Installation" below).
pip install -r requirements.txt -r requirements-build.txt

REM 4. Build the onedir into dist\StemSeparator\
pyinstaller --noconfirm --clean packaging\windows\StemSeparator-win.spec

REM 5. Produce the installer (Inno Setup 6.3+, ISCC on PATH).
iscc packaging\windows\StemSeparator.iss
```

Outputs:

* `dist\StemSeparator\StemSeparator.exe` + `_internal\` — the onedir bundle.
  `_internal\bin\` holds the vendored `ffmpeg.exe`/`ffprobe.exe`,
  `_internal\torch\lib\` the torch DLLs, `_internal\nvidia\*\bin\` the CUDA
  runtime DLLs when a CUDA torch was installed.
* `dist\installer\StemSeparator-1.0.3-win64.exe` — the Inno Setup installer
  (`OutputDir`/`OutputBaseFilename` in the `.iss`). It installs per-user
  (`PrivilegesRequired=lowest`, with an admin override dialog) because every
  writable path is in `%LOCALAPPDATA%\StemSeparator`, never next to the
  binaries; `packaging\windows\StemSeparator.ico` is both the setup icon and the
  application icon.

Prerequisite the installer can only warn about: the **Microsoft Visual C++
Redistributable (x64)**. torch, PySide6 and the FFmpeg build all need
`VCRUNTIME140.dll` / `MSVCP140.dll`. Install
<https://aka.ms/vs/17/release/vc_redist.x64.exe> first on a clean machine; the
setup probes `{sys}\vcruntime140.dll` and shows a message pointing at that
download if it is absent, because the frozen app otherwise dies before it can
log anything.

## CUDA Installation

Stem Separator runs on the CPU everywhere. To separate on an NVIDIA GPU you need
a **CUDA-enabled PyTorch** — the plain `torch` wheel from PyPI is not it, and
worse, PyPI's default wheel is a *different build per operating system* (CPU on
Linux, CUDA on Windows), which is why `requirements.txt` does not try to express
the GPU case and `requirements-cuda.txt` exists instead.

Both files install the **matched** pair: a `torch`/`torchaudio` combination from
the same release (see the comment in `requirements.txt`). Mixing versions is the
classic `OSError: Could not load this library: .../libtorchaudio.so` — an ABI
mismatch, not a packaging bug.

Get the wheel for your platform from the PyTorch index instead of PyPI. cu126 and
cu128 both publish cp311 `win_amd64` and `manylinux_2_28_x86_64` wheels for
`torch==2.9.0`/`torchaudio==2.9.0` (verified against the index):

```bash
# Linux
python -m pip uninstall -y torch torchaudio onnxruntime
python -m pip install --index-url https://download.pytorch.org/whl/cu128 -r requirements-cuda.txt

# Windows (same commands, same file)
py -3.11 -m pip uninstall -y torch torchaudio onnxruntime
py -3.11 -m pip install --index-url https://download.pytorch.org/whl/cu128 -r requirements-cuda.txt
```

Notes that matter:

* **Driver:** `nvidia-smi` reports the highest CUDA version your driver
  supports; the wheel's CUDA version must be <= that. If it is not, pick the
  lower index (`/whl/cu126`).
* **`onnxruntime` and `onnxruntime-gpu` are mutually exclusive** — both install
  the same `onnxruntime` package, so uninstall the CPU one first.
  `audio-separator[gpu]` is the upstream way to pull the CUDA execution
  provider in; `requirements-cuda.txt` pins `onnxruntime-gpu` to the same
  release line the CPU build is pinned to.
* **Rebuild the bundle after changing the environment.** PyInstaller copies the
  libraries that exist in the interpreter at build time: build with a CUDA torch
  and the spec collects `torch/lib/*.so|dll` plus `nvidia/*/lib|bin/*` (the
  Linux spec prints `collected 36 NVIDIA CUDA library file(s)`, the Windows spec
  prints the matching note or warns `no nvidia/* CUDA runtime DLLs in this
  environment`).

### Verifying GPU access

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count(), torch.cuda.get_device_name(0))"
```

Then ask the application, which is what the user actually sees. Start it and
read `logs/app.log` in the user data directory above: the startup `Platform:
{...}` line comes from `utils.platform_utils.runtime_report()`, and
`core/device_manager.py` logs the classification it performed — `CUDA available:
<name> (torch build <cuda>)` (`:146`), then `Selected device: cuda (...)` or
`Selected device: CPU (no GPU available)` (`:242`, `:247`).

Observed on this machine from the frozen build's separation worker
(`--separation-subprocess`, stderr and the app log):

```
audio_separator.separator.separator - INFO - CUDA is available in Torch, setting Torch device to CUDA
StemSeparator.Subprocess - WARNING - ONNX models will run on CPU: CUDAExecutionProvider is not present in this onnxruntime build (available: ['AzureExecutionProvider', 'CPUExecutionProvider'])
StemSeparator.Subprocess - INFO - Device enforced: torch=cuda onnx=['CPUExecutionProvider']
```

and with the CPU policy (`device: "cpu"`, which sets `CUDA_VISIBLE_DEVICES=""`):

```
audio_separator.separator.separator - INFO - No hardware acceleration could be configured, running in CPU mode
StemSeparator.Subprocess - INFO - Device enforced: torch=cpu onnx=['CPUExecutionProvider']
```

The `onnx=[...]` list is the honest report of the ONNX execution providers:
`['CPUExecutionProvider']` means MDX-Net/BS-RoFormer models will run on the CPU
even though Demucs is on the GPU, which is exactly what this machine's
CPU-only `onnxruntime` does. `CUDAExecutionProvider` in that list is what a
working GPU ONNX path looks like.

### No GPU: what the user sees

There is no silent fallback. `core/device_manager.py` classifies the hardware and
applies the configured policy:

| Policy | GPU present | GPU absent |
| ------ | ----------- | ---------- |
| `auto` | CUDA | CPU, logged |
| `gpu_preferred` | CUDA | **visible warning**: CPU-only, no hardware acceleration |
| `gpu_required` | CUDA | **error dialog** pointing at this section (`docs/PACKAGING.md## CUDA Installation`), and the separation subprocess refuses to start rather than quietly using the CPU |
| `cpu_only` | CPU, GPU hidden from the driver | CPU |

`gpu_required` raises `RuntimeError` inside the worker
(`core/separation_subprocess.py`), whose message also links to this section —
keep the heading text `## CUDA Installation`, two error strings link to it.

## Import Order and Native Library Paths

The frozen build depends on native directories being registered *before* torch,
PySide6 or audio-separator are imported. `main.py` does it at the top of the
module (lines 18-38), and the specs install the same calls as a PyInstaller
**runtime hook**, so they also run for entry points that never reach `main.py`
(the separation worker):

1. `utils.platform_utils.configure_native_library_dirs(torch_library_dirs())` —
   `os.add_dll_directory()` on Windows, `LD_LIBRARY_PATH` on Linux, so
   `torch/lib` and `nvidia/*/lib|bin` are resolvable.
2. `utils.platform_utils.ensure_binaries_on_path()` — puts the bundled
   `_internal/bin` (FFmpeg/ffprobe/rubberband) on `PATH` for subprocesses.
3. `numba_cuda_safe_env()` — `NUMBA_DISABLE_CUDA=1`: numba initialising the CUDA
   driver before torch poisons the spawned worker's CUDA context.
4. `configure_multiprocessing()` — forces the `spawn` start method; the `fork`
   default combined with CUDA and Qt is unreliable (the runtime report shows
   `'multiprocessing': 'spawn'`).

The hooks are `packaging/windows/_pyi_rthook_windows.py` and
`packaging/linux/_pyi_rthook_linux.py`; the Linux one additionally patches
`ctypes.util.find_library` so `sounddevice` finds the vendored PortAudio (see
`packaging/vendor/README.md` for why nothing else works on POSIX). Both write a
failure report next to the bundle instead of dying silently, since a windowed
build has no stderr.

## Building on macOS

Everything above this line is the macOS recipe and stays authoritative for the
`.app`/`.dmg` build: `packaging/build_arm64.sh`,
`packaging/StemSeparator-arm64.spec`, the `DYLD_LIBRARY_PATH` export in the
build script and the `dmgbuild` DMG step. The macOS specs keep
`onnxruntime` as a *hidden import* and let the bundled hook collect
`onnxruntime/capi` — it is never in their `excludes` list, because excluding it
would break MDX-Net/BS-RoFormer support. The Linux and Windows specs follow the
same policy.


## Support

For build issues:
- Check [PyInstaller documentation](https://pyinstaller.org/)
- Check [PySide6 deployment guide](https://doc.qt.io/qtforpython/deployment.html)
- Open an issue on GitHub

---

**Happy packaging! 🎉**
