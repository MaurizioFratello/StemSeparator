# Technology Stack

**Analysis Date:** 2026-04-01

## Languages

**Primary:**
- Python 3.10+ — Entire application (`main.py`, `core/`, `ui/`, `utils/`, `tests/`). CI validates 3.11 and 3.12 on `ubuntu-latest`, `macos-latest` and `windows-latest` (CPU-only torch wheels) per `.github/workflows/tests.yml`.

**Secondary:**
- Shell — Build scripts under `packaging/` (e.g. `packaging/build_arm64.sh`, `packaging/build_intel.sh`).
- YAML — Model configs referenced by Demucs (`config.py` `MODELS` entries such as `htdemucs.yaml`), PyYAML in `requirements.txt`.

## Runtime

**Environment:**
- CPython (version aligned with `requirements.txt` pins; README documents 3.10+ with 3.11 recommended for development).

**Package Manager:**
- pip — Dependencies declared in `requirements.txt` (pinned versions) and `requirements-build.txt` (packaging).
- Lockfile: not committed at repository root (no `poetry.lock` / `Pipfile.lock`).

## Frameworks

**Core:**
- PySide6 `6.10.0` — Desktop GUI (`main.py`, `ui/`).
- audio-separator `0.39.1` — Stem separation pipeline and model loading (`core/separator.py`, `core/separation_subprocess.py`, `core/model_manager.py`).
- PyTorch `2.9.0` + torchaudio `2.9.0` — ML inference and device selection (`core/device_manager.py`).
- onnxruntime `1.23.2` — ONNX-backed models (e.g. MDX-Net per `config.py`).

**Testing:**
- pytest `9.0.0` with pytest-qt, pytest-cov, pytest-mock — Config in `pytest.ini`.

**Build/Dev:**
- PyInstaller `>=6.0.0` — App bundles (`packaging/StemSeparator-arm64.spec`, `packaging/StemSeparator-intel.spec`).
- dmgbuild `>=1.6.0` — macOS DMG creation (`requirements-build.txt`, `packaging/dmg/`).
- black `25.9.0`, flake8 `7.3.0` — Formatting and lint (`requirements.txt`).

## Key Dependencies

**Critical:**
- audio-separator — Separation engine, model download trigger (`core/model_manager.py`, `packaging/download_models.py`).
- numpy `2.3.4`, scipy `1.16.3`, librosa `0.11.0`, soundfile `0.13.1`, resampy `0.4.3`, pydub `0.25.1` — Audio I/O and DSP (`utils/audio_processing.py`, `core/`).
- pyrubberband `0.4.0` — Time-stretch for loop export.
- deeprhythm `0.0.13` — Optional enhanced BPM (`utils/audio_processing.py`).
- soundcard `0.4.5`, sounddevice `0.5.3` — Capture and playback paths (`core/recorder.py`, player stack).
- colorlog `6.10.1` — Structured logging (`utils/logger.py`).
- PyYAML `6.0.3` — YAML model config parsing (`core/model_manager.py`).
- psutil `7.1.3` — Process/system utilities.
- tqdm `4.67.1` — Progress (where used by dependencies or UI flows).

**Infrastructure:**
- requests `2.32.5` — Listed in `requirements.txt`; no direct `import requests` in first-party `.py` files (likely used by dependencies such as audio-separator / model tooling).

**Isolated subprocess stack (BeatNet):**
- Separate Python 3.8-oriented environment documented in `packaging/beatnet_service/README.md` and `packaging/beatnet_service/requirements.txt` (BeatNet, madmom, numba constraints). Built as `beatnet-service` via PyInstaller (`packaging/beatnet_service/beatnet-service.spec`).

## Configuration

**Environment:**
- No `.env`-driven app config in `config.py`; paths derive from `sys.frozen`, platform, and `Path.home()`.
- Process flags: `STEMSEPARATOR_SUBPROCESS` and CLI `--separation-subprocess` for worker mode (`main.py`).
- `APPDATA` used on Windows for user dir when bundled (`config.py` `get_user_dir()`).
- `PATH` prepended with bundled `bin` for FFmpeg when frozen (`main.py`).

**Build:**
- PyInstaller `.spec` files: `packaging/StemSeparator-arm64.spec`, `packaging/StemSeparator-intel.spec`.
- Test and coverage: `pytest.ini` (coverage omit patterns, markers including `network`).

## Platform Requirements

**Development:**
- README targets macOS for the product; CI (`ubuntu-latest`, `macos-latest`, `windows-latest` × Python 3.11/3.12) runs the CPU-only test suite on all three platforms — Linux under `xvfb-run` with `libportaudio2`, Windows with `QT_QPA_PLATFORM=offscreen`, macOS against the runner's window server (no `xvfb-run`; that binary does not exist on macOS runners). The macOS suites (`test_blackhole*`, `test_macos_*`) are collected on the macOS jobs only; `test_screencapture*` are `sys.exit()` diagnostic scripts excluded on every OS; the CUDA/GPU paths are validated manually on real hardware, never in CI.

**Production:**
- Packaged macOS `.app` / `.dmg` per `packaging/README.md` and `docs/PACKAGING.md` (referenced from README). FFmpeg bundled into the app bundle for separation pipelines (`main.py`, `core/separator.py` PATH handling).

---

*Stack analysis: 2026-04-01*
