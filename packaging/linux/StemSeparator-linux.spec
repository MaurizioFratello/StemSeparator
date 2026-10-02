# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for StemSeparator (Linux, onedir)

Build command (run on Linux from the repository root, in the venv that has
requirements.txt + requirements-build.txt installed):

    python packaging/vendor/fetch_vendor.py --platform linux   # once, see the README
    pyinstaller --noconfirm packaging/linux/StemSeparator-linux.spec

Output:
    dist/StemSeparator-linux/StemSeparator-linux        (launcher)
    dist/StemSeparator-linux/_internal/                 (everything else)

The launcher is the app's only entry point, in both modes:
`./StemSeparator-linux` starts the GUI and
`./StemSeparator-linux --separation-subprocess --params-file <file>` runs the
isolation worker (`main.py` branches on the flag before Qt is imported), which
is how `core/separator.py` spawns separations when frozen.

WHY `excludes` never lists onnxruntime: onnxruntime executes MDX-Net and
BS-RoFormer ONNX graphs and `core/separation_subprocess.py` configures its
execution providers; the macOS specs keep it as a hidden import and so does
this one. `hook-onnxruntime` (pyinstaller-hooks-contrib) collects the provider
plugins from `onnxruntime/capi`.
"""

import importlib.util
import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# SPECPATH is this file's directory (packaging/linux); the repository root is
# two levels up, unlike the macOS specs that live directly in packaging/.
project_root = Path(SPECPATH).parents[1]
resources_dir = project_root / "resources"
ui_dir = project_root / "ui"
vendor_dir = project_root / "packaging" / "vendor" / "linux"

APP_NAME = "Stem Separator"
APP_VERSION = "1.0.3"

block_cipher = None

warnings = []


def note(message):
    print(f"[StemSeparator-linux.spec] {message}")


def warn(message):
    warnings.append(message)
    print(f"[StemSeparator-linux.spec] WARNING: {message}")


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = []

for json_file in sorted((resources_dir / "translations").glob("*.json")):
    datas.append((str(json_file), "resources/translations"))

icons_dir = resources_dir / "icons"
if icons_dir.exists() and any(icons_dir.iterdir()):
    datas.append((str(icons_dir), "resources/icons"))
else:
    warn(f"no icons in {icons_dir}; the app will start without a window icon")

theme_qss = ui_dir / "theme" / "stylesheet.qss"
if theme_qss.exists():
    datas.append((str(theme_qss), "ui/theme"))
else:
    warn(f"theme stylesheet missing: {theme_qss}")

# Model weights are optional in the bundle: `config.MODEL_SEARCH_PATHS` contains
# both the bundle and the per-user cache, so an empty bundle only costs the
# first-run download.
for pattern in ["*.ckpt", "*.yaml", "*.th", "*.json", "*.onnx"]:
    for model_file in sorted((resources_dir / "models").glob(pattern)):
        datas.append((str(model_file), "resources/models"))

try:
    audio_sep_datas = collect_data_files("audio_separator")
except Exception as exc:
    audio_sep_datas = []
    warn(f"collect_data_files('audio_separator') failed: {exc}")
if audio_sep_datas:
    datas.extend(audio_sep_datas)
    note(f"collected {len(audio_sep_datas)} audio_separator data file(s)")
else:
    warn("audio_separator data files not found; model lookup will fail")


# ---------------------------------------------------------------------------
# Vendored static FFmpeg + PortAudio
# ---------------------------------------------------------------------------
# Destination `bin` lands in `_internal/bin`, the first directory that
# `utils.platform_utils.bundled_binary_dirs()` probes in a frozen run, and
# `ensure_binaries_on_path()` (main.py) prepends it to PATH for audio-separator,
# pydub and pyrubberband, which all shell out.
ffmpeg_dir = vendor_dir / "bin"
for name in ("ffmpeg", "ffprobe"):
    binary = ffmpeg_dir / name
    if binary.is_file() and os.access(binary, os.X_OK):
        datas.append((str(binary), "bin"))
        note(f"bundling {name} from {ffmpeg_dir} -> bin/")
    else:
        warn(
            f"{binary} missing - run packaging/vendor/fetch_vendor.py --platform linux "
            "(see packaging/vendor/README.md); separation needs it"
        )

if not (vendor_dir / "GPLv3.txt").is_file():
    note(f"GPLv3.txt missing next to the static FFmpeg build ({vendor_dir / 'GPLv3.txt'})")

# PortAudio: the PyPI sounddevice wheel has no bundled copy on Linux (it relies
# on the distro package) and this build host has no sudo, so the library is
# vendored. It is shipped as a *binary* in the content directory (next to the
# collected torch libraries) because that is the directory PyInstaller's
# bootloader adds to LD_LIBRARY_PATH; `_pyi_rthook_linux.py` additionally makes
# `ctypes.util.find_library('portaudio')` resolve to it, which neither
# LD_LIBRARY_PATH nor `ldconfig -p` does on a machine without the distro package.
portaudio_dir = vendor_dir / "native"
portaudio_candidates = [
    portaudio_dir / "libportaudio.so.2",
    portaudio_dir / "libportaudio.so.2.0.0",
]
portaudio_binary = next((p for p in portaudio_candidates if p.is_file()), None)
if portaudio_binary is None:
    warn(
        f"libportaudio missing in {portaudio_dir} - playback/recording will fail; "
        "run packaging/vendor/fetch_vendor.py --platform linux"
    )
portaudio_dest = "."

# RubberBand CLI is optional; core/time_stretcher.py logs which engine it used.
rubberband_binary = None
for directory in (ffmpeg_dir, Path("/usr/bin"), Path("/usr/local/bin")):
    candidate = directory / "rubberband"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        rubberband_binary = candidate
        break
if rubberband_binary:
    datas.append((str(rubberband_binary), "bin"))
    note(f"bundling rubberband from {rubberband_binary} -> bin/")
else:
    note("rubberband CLI not found; time stretching uses the pyrubberband/librosa chain")


# ---------------------------------------------------------------------------
# Native binaries
# ---------------------------------------------------------------------------
binaries = []

if portaudio_binary is not None:
    # Ship the SONAME name (what dlopen looks for) and the real file, so both
    # `ctypes.CDLL("libportaudio.so.2")` and the preload in the runtime hook work.
    binaries.append((str(portaudio_binary), "."))
    real_file = portaudio_dir / "libportaudio.so.2.0.0"
    if real_file.is_file() and real_file != portaudio_binary:
        binaries.append((str(real_file), "."))

def collect_libs(module):
    """`collect_dynamic_libs` that warns instead of aborting the build.

    WHY: distribution layouts differ per wheel (a single-file module such as
    `sounddevice` has no package directory at all). One unpickable library must
    not kill a release build; the warning names exactly what to go check.
    """
    patterns = ["*.so", "*.so.*", "*.pyd", "*.dll"]
    try:
        found = collect_dynamic_libs(module, search_patterns=patterns)
    except Exception as exc:
        warn(f"collect_dynamic_libs({module!r}) failed: {exc}")
        return []
    if not found:
        warn(f"no shared libraries collected for {module!r}; inspect the bundle")
    return found


# `soundfile` is deliberately absent: pyinstaller-hooks-contrib's
# hook-soundfile.py collects `libsndfile` into `_soundfile_data/`, verified in
# the built bundle (`_internal/_soundfile_data/libsndfile_x86_64.so`), and
# `soundfile` is a single-file module, so collect_dynamic_libs only warns.
for _module in ("torch", "onnxruntime"):
    binaries += collect_libs(_module)


def collect_nvidia_libs():
    """CUDA runtime libraries from the `nvidia-*` wheels (site-packages/nvidia/*/lib).

    WHY: `hook-torch` infers the hidden imports for a CUDA build of torch, but a
    CPU-only PyPI wheel declares none; collecting whatever is on disk keeps one
    spec valid for both installs (PKG-03) instead of silently shipping a build
    that loses cuDNN at runtime.
    """
    found = []
    try:
        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        spec = None
    if spec is None or not spec.submodule_search_locations:
        return found
    for location in spec.submodule_search_locations:
        root = Path(location)
        for library in sorted(root.glob("*/lib/lib*.so*")):
            found.append((str(library), str(library.parent.relative_to(root.parent))))
            found.append((str(library), "."))
    return found


nvidia_libs = collect_nvidia_libs()
if nvidia_libs:
    binaries += nvidia_libs
    note(f"collected {len(set(src for src, _ in nvidia_libs))} NVIDIA CUDA library file(s)")
else:
    note("no nvidia/* CUDA libraries in this environment: this build is CPU-only for ONNX/torch GPU paths")


# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "torch.nn.parallel",
    "torch.nn.parallel.distributed",
    "torch.utils",
    "torch.utils.data",
    "torch.cuda",  # referenced at module level even on CPU-only installs
    "torch.backends.mps",  # core/device_manager probes it on every OS
    "torchaudio",
    "onnxruntime",
    "onnx",
    "audio_separator",
    "audio_separator.separator",
    "audio_separator.separator.architectures",
    "audio_separator.separator.common_separator",
    "audio_separator.separator.roformer",
    "audio_separator.separator.uvr_lib_v5",
    "beartype",
    "einops",
    "julius",
    "ml_collections",
    "rotary_embedding_torch",
    "samplerate",
    "numpy",
    "scipy",
    "scipy.signal",
    "scipy.ndimage",
    "librosa",
    "librosa.core",
    "librosa.feature",
    "resampy",
    "pydub",
    "soundfile",
    "sounddevice",
    "soundcard",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "shiboken6",
    "yaml",
    "requests",
    "tqdm",
    "colorlog",
    "psutil",
    "core.separation_subprocess",
    "multiprocessing",
    "multiprocessing.pool",
    # Modules the audio stack reaches through ctypes/optional imports.
    "pyaudio",
    "pulsectl",
]

hiddenimports = [name for name in hiddenimports if has_module(name)]

for package in ("audio_separator",):
    try:
        hiddenimports += collect_submodules(package)
    except Exception as exc:  # pragma: no cover - build-time only
        warn(f"could not enumerate submodules of {package}: {exc}")

excludes = [
    "pytest",
    "pytest_qt",
    "pytest_cov",
    "pytest_mock",
    "black",
    "flake8",
    "pylint",
    "sphinx",
    "docutils",
    "tkinter",
    "matplotlib",
    "PyQt5",
    "PyQt6",
]


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
build_dir = project_root / "build" / "StemSeparator-linux"
build_dir.mkdir(parents=True, exist_ok=True)
(project_root / "dist").mkdir(parents=True, exist_ok=True)

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(Path(SPECPATH) / "_pyi_rthook_linux.py")],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StemSeparator-linux",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # A frozen POSIX build has no console to hide; the flag is kept for parity
    # with the macOS/Windows specs so the three stay diffable.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # WHY no icon: an ELF executable carries no icon resource. The window icon
    # comes from resources/icons/app_icon_1024.png (set in main.py) and the
    # desktop entry's Icon= key documented in docs/PACKAGING.md.
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="StemSeparator-linux",
)

if warnings:
    note(f"{len(warnings)} warning(s) above - resolve them before shipping this build")
