# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for StemSeparator (Windows, onedir)

Build command (run on Windows from the repository root, in the same venv that
has requirements.txt + requirements-build.txt installed):

    pyinstaller --noconfirm packaging\\windows\\StemSeparator-win.spec

Output:
    dist\\StemSeparator\\StemSeparator.exe   (+ dist\\StemSeparator\\_internal\\)

Requirements this spec implements (`.planning/REQUIREMENTS.md`, Phase 2):
  PKG-01  onedir (never onefile: Qt + torch + onnxruntime need a stable
          `_internal` directory; onefile unpacks to a temp dir on every start,
          which breaks torch's DLL probing and multiplies cold-start time)
  PKG-02  Qt plugins and native deps deploy with the app
  PKG-03  torch/torchaudio + CUDA DLLs collected or documented
  PKG-04  import order enforced by a runtime hook (see `_pyi_rthook_windows.py`)
  PKG-05  VCRedist prerequisites are documented in docs/PACKAGING.md

WHY no `excludes=["onnxruntime"]`: onnxruntime is what executes MDX-Net and
BS-RoFormer ONNX graphs (`core/separation_subprocess.py` sets
`separator.onnx_execution_provider`). Excluding it produces a bundle that boots
and separates on the torch architectures only, while ONNX models fail at load
time. The macOS specs already ship onnxruntime as a hidden import, and the
bundled `pyinstaller-hooks-contrib` `hook-onnxruntime.py` collects the provider
DLLs from `onnxruntime/capi`; both are kept here unchanged.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# SPECPATH is this file's directory (packaging/windows), so the repository root
# is two levels up - unlike the macOS specs, which live directly in packaging/.
project_root = Path(SPECPATH).parents[1]
resources_dir = project_root / "resources"
ui_dir = project_root / "ui"
vendor_dir = project_root / "packaging" / "vendor" / "windows"

APP_NAME = "Stem Separator"
APP_VERSION = "1.0.3"

block_cipher = None

warnings = []


def note(message):
    print(f"[StemSeparator-win.spec] {message}")


def warn(message):
    warnings.append(message)
    print(f"[StemSeparator-win.spec] WARNING: {message}")


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = []

# Translations (utils/i18n.py loads resources/translations/*.json)
for json_file in sorted((resources_dir / "translations").glob("*.json")):
    datas.append((str(json_file), "resources/translations"))

# Icons (main.py sets the window icon from resources/icons/app_icon_1024.png)
icons_dir = resources_dir / "icons"
if icons_dir.exists() and any(icons_dir.iterdir()):
    datas.append((str(icons_dir), "resources/icons"))
else:
    warn(f"no icons in {icons_dir}; the app will start without a window icon")

# Theme stylesheet (ui/theme/theme_manager.py)
theme_qss = ui_dir / "theme" / "stylesheet.qss"
if theme_qss.exists():
    datas.append((str(theme_qss), "ui/theme"))
else:
    warn(f"theme stylesheet missing: {theme_qss}")

# Model weights.
# WHY optional: in a frozen build `config.MODELS_DIR` is the per-user cache and
# `MODEL_SEARCH_PATHS` still contains the bundle, so shipping weights here is a
# convenience (first run offline) and not a hard requirement. The build works
# without them; the model manager downloads on demand.
for pattern in ["*.ckpt", "*.yaml", "*.th", "*.json", "*.onnx"]:
    for model_file in sorted((resources_dir / "models").glob(pattern)):
        datas.append((str(model_file), "resources/models"))

# audio-separator ships model registries + architecture yaml files it opens
# through importlib.resources at runtime.
audio_sep_datas = collect_data_files("audio_separator")
if audio_sep_datas:
    datas.extend(audio_sep_datas)
    note(f"collected {len(audio_sep_datas)} audio_separator data file(s)")
else:
    warn("audio_separator data files not found; model lookup will fail")


# ---------------------------------------------------------------------------
# Bundled FFmpeg (Windows)
# ---------------------------------------------------------------------------
# Naming convention of the gyan.dev/BtbN "ffmpeg-master-latest-win64-gpl"
# release, mirrored by utils/platform_utils.py (FFMPEG_WINDOWS_DIRNAME). The
# vendor fetch step unpacks the archive into packaging/vendor/windows/ and
# stages the executables in packaging/vendor/windows/bin/.
FFMPEG_WINDOWS_DIRNAME = "ffmpeg-master-latest-win64-gpl"
ffmpeg_dest = "bin"  # -> _internal/bin, the first entry of bundled_binary_dirs()
ffmpeg_needed = ("ffmpeg.exe", "ffprobe.exe")
ffmpeg_candidates = [
    vendor_dir / "bin",
    vendor_dir / FFMPEG_WINDOWS_DIRNAME / "bin",
]

staged = []
for directory in ffmpeg_candidates:
    present = [name for name in ffmpeg_needed if (directory / name).is_file()]
    if len(present) == len(ffmpeg_needed):
        for name in present:
            datas.append((str(directory / name), ffmpeg_dest))
        staged.append(str(directory))
        note(f"bundling FFmpeg from {directory} -> {ffmpeg_dest}/")
        break

if not staged:
    warn(
        "FFmpeg not vendored (looked in "
        + ", ".join(str(c) for c in ffmpeg_candidates)
        + "). Run packaging/vendor/fetch_vendor.py --platform windows; "
        "separation will only work if the user installed FFmpeg themselves."
    )

# RubberBand CLI is optional: core/time_stretcher.py falls back to
# pyrubberband and then to a librosa phase vocoder, logging which engine ran.
rubberband_exe = vendor_dir / "bin" / "rubberband.exe"
if rubberband_exe.is_file():
    datas.append((str(rubberband_exe), ffmpeg_dest))
    note("bundling rubberband.exe -> bin/")
else:
    note("rubberband.exe not vendored; time stretching uses the pyrubberband/librosa chain")


# ---------------------------------------------------------------------------
# Native binaries
# ---------------------------------------------------------------------------
binaries = []

def collect_libs(module, patterns):
    """`collect_dynamic_libs` that warns instead of aborting the build.

    WHY: wheel layouts differ per distribution (a single-file module such as
    `sounddevice` has no package directory at all, and its PortAudio copy lives
    in `_sounddevice_data`). One library the helper cannot locate must not kill a
    release build; the warning names exactly what to go check in the bundle.
    """
    try:
        found = collect_dynamic_libs(module, search_patterns=patterns)
    except Exception as exc:
        warn(f"collect_dynamic_libs({module!r}) failed: {exc}")
        return []
    if not found:
        warn(f"no shared libraries collected for {module!r}; inspect the bundle")
    return found


# torch/lib (torch DLLs, the OpenMP runtime, the CUDA-enabled builds'
# c10_cuda/torch_cuda) and onnxruntime/capi (execution-provider plugins).
# The bundled hooks do the same collection; repeating it is cheap and keeps the
# bundle correct if a hooks-contrib version regresses.
binaries += collect_libs("torch", ["*.dll", "*.pyd"])
binaries += collect_libs("onnxruntime", ["*.dll", "*.pyd"])

# CUDA wheels from download.pytorch.org ship their runtime in the `nvidia_*`
# distributions, laid out as site-packages/nvidia/<component>/bin/*.dll. No hook
# collects them, so without this a "CUDA" build silently loses cuDNN/cuBLAS and
# torch falls back to CPU at model-load time.
def collect_nvidia_dlls():
    found = []
    try:
        import importlib.util

        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        spec = None
    if spec is None or not spec.submodule_search_locations:
        return found
    for location in spec.submodule_search_locations:
        root = Path(location)
        for dll in sorted(root.glob("*/bin/*.dll")):
            dest = str(dll.parent.relative_to(root.parent))
            found.append((str(dll), dest))
            # Mirror flat as well: torch adds every nvidia/*/bin to the DLL
            # directory and some loader paths resolve by file name only.
            found.append((str(dll), "."))
    return found


nvidia_dlls = collect_nvidia_dlls()
if nvidia_dlls:
    binaries += nvidia_dlls
    note(f"collected {len(set(d for _, d in nvidia_dlls))} NVIDIA runtime DLL reference(s)")
else:
    note(
        "no nvidia/* CUDA runtime DLLs in this environment -> this build will be "
        "CPU-only for the ONNX/torch GPU paths (see docs/PACKAGING.md#CUDA Installation)"
    )

# libsndfile for soundfile, PortAudio for sounddevice (Windows wheels bundle it
# in _sounddevice_data/portaudio-binaries; the contrib hook covers it, keep it
# explicit here so a hook regression cannot silently drop playback support).
binaries += collect_libs("soundfile", ["*.dll", "*.pyd"])
binaries += collect_libs("sounddevice", ["*.dll"])


# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    # PyTorch and ONNX Runtime - the models import these lazily, so the
    # dependency analyser never sees them.
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
    # audio-separator imports its architecture plugins by name at model load.
    "audio_separator",
    "audio_separator.separator",
    "audio_separator.separator.architectures",
    "audio_separator.separator.common_separator",
    "audio_separator.separator.roformer",
    "audio_separator.separator.uvr_lib_v5",
    # audio-separator's own lazy dependencies.
    "beartype",
    "einops",
    "julius",
    "ml_collections",
    "rotary_embedding_torch",
    "samplerate",
    # Audio stack
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
    # Qt bindings actually used by ui/ and utils/
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "shiboken6",
    # Utilities
    "yaml",
    "requests",
    "tqdm",
    "colorlog",
    "psutil",
    # The frozen worker (main.py imports it inside an argv branch) and the
    # spawn-mode helpers `multiprocessing` needs in a frozen Windows app.
    "core.separation_subprocess",
    "multiprocessing",
    "multiprocessing.pool",
    "multiprocessing.popen_spawn_win32",
]

# Dynamic sub-modules that are only reachable via importlib.
for package in ("audio_separator",):
    try:
        hiddenimports += collect_submodules(package)
    except Exception as exc:  # pragma: no cover - build-time only
        warn(f"could not enumerate submodules of {package}: {exc}")


# Dev/test tooling and the conflicting Qt bindings must not leak into the
# bundle. Deliberately NOT excluding onnxruntime (see the module docstring).
excludes = [
    "pytest",
    "pytest_qt",
    "pytest-qt",
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
build_dir = project_root / "build" / "StemSeparator-win"
build_dir.mkdir(parents=True, exist_ok=True)
(project_root / "dist").mkdir(parents=True, exist_ok=True)

icon_path = Path(SPECPATH) / "StemSeparator.ico"
if not icon_path.is_file():
    raise SystemExit(
        "[StemSeparator-win.spec] missing "
        f"{icon_path}\n"
        "Generate it once with: python packaging/windows/generate_ico.py"
    )

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    # PKG-03/PKG-04: register torch/CUDA DLL directories and the bundled FFmpeg
    # before any module import, so torch is importable in the separation worker
    # that main.py spawns (see the hook's own docstring for the full story).
    runtime_hooks=[str(Path(SPECPATH) / "_pyi_rthook_windows.py")],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StemSeparator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # PKG-04: no console window. The separation worker therefore talks through
    # the params/result files in config.TEMP_DIR, never through stdin/stdout
    # (core/separation_subprocess.py:_emit_result).
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="StemSeparator",
)

if warnings:
    note(f"{len(warnings)} warning(s) above - the build is not shippable until they are resolved")
