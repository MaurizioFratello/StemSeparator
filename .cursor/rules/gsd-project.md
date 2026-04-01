<!-- gsd-project-start source:PROJECT.md -->
## Project

**StemSeparator**

**StemSeparator** is a desktop application for musicians and producers: it separates mixed audio into stems (vocals, drums, bass, etc.), previews and exports results, supports looping and time-stretch workflows, and records system or input audio on macOS using native integration. The codebase is a **Python** app with a **PySide6** UI, a **PyTorch** / **audio-separator** separation pipeline (including subprocess isolation for heavy work), and **macOS-focused packaging** (PyInstaller, DMG, bundled helpers such as BeatNet).

This planning cycle targets a **Windows port** that preserves **feature parity with macOS**, including **recording and system-audio capture** on Windows where technically feasible, while adding **CUDA GPU acceleration** for inference with a **CPU fallback**.

**Core Value:** **Reliable stem separation and playback in one desktop app** — users can go from a file or live capture to separated stems and usable exports without leaving the tool; on Windows, GPU acceleration should be used when available without blocking users on CPU-only systems.

### Constraints

- **Tech stack**: Python, PySide6, PyTorch, audio-separator — align CUDA/PyTorch builds with supported NVIDIA/CUDA matrix for Windows.
- **Dual platform**: No breaking macOS shipping path; use conditional platform code and CI for both targets where feasible.
- **Licensing**: Respect licenses of bundled binaries (FFmpeg, models, virtual audio drivers on Windows).
<!-- gsd-project-end -->

<!-- gsd-stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.10+ — Entire application (`main.py`, `core/`, `ui/`, `utils/`, `tests/`). CI validates 3.10, 3.11, 3.12 per `.github/workflows/tests.yml`.
- Shell — Build scripts under `packaging/` (e.g. `packaging/build_arm64.sh`, `packaging/build_intel.sh`).
- YAML — Model configs referenced by Demucs (`config.py` `MODELS` entries such as `htdemucs.yaml`), PyYAML in `requirements.txt`.
## Runtime
- CPython (version aligned with `requirements.txt` pins; README documents 3.10+ with 3.11 recommended for development).
- pip — Dependencies declared in `requirements.txt` (pinned versions) and `requirements-build.txt` (packaging).
- Lockfile: not committed at repository root (no `poetry.lock` / `Pipfile.lock`).
## Frameworks
- PySide6 `6.10.0` — Desktop GUI (`main.py`, `ui/`).
- audio-separator `0.39.1` — Stem separation pipeline and model loading (`core/separator.py`, `core/separation_subprocess.py`, `core/model_manager.py`).
- PyTorch `2.9.0` + torchaudio `2.9.0` — ML inference and device selection (`core/device_manager.py`).
- onnxruntime `1.23.2` — ONNX-backed models (e.g. MDX-Net per `config.py`).
- pytest `9.0.0` with pytest-qt, pytest-cov, pytest-mock — Config in `pytest.ini`.
- PyInstaller `>=6.0.0` — App bundles (`packaging/StemSeparator-arm64.spec`, `packaging/StemSeparator-intel.spec`).
- dmgbuild `>=1.6.0` — macOS DMG creation (`requirements-build.txt`, `packaging/dmg/`).
- black `25.9.0`, flake8 `7.3.0` — Formatting and lint (`requirements.txt`).
## Key Dependencies
- audio-separator — Separation engine, model download trigger (`core/model_manager.py`, `packaging/download_models.py`).
- numpy `2.3.4`, scipy `1.16.3`, librosa `0.11.0`, soundfile `0.13.1`, resampy `0.4.3`, pydub `0.25.1` — Audio I/O and DSP (`utils/audio_processing.py`, `core/`).
- pyrubberband `0.4.0` — Time-stretch for loop export.
- deeprhythm `0.0.13` — Optional enhanced BPM (`utils/audio_processing.py`).
- soundcard `0.4.5`, sounddevice `0.5.3` — Capture and playback paths (`core/recorder.py`, player stack).
- colorlog `6.10.1` — Structured logging (`utils/logger.py`).
- PyYAML `6.0.3` — YAML model config parsing (`core/model_manager.py`).
- psutil `7.1.3` — Process/system utilities.
- tqdm `4.67.1` — Progress (where used by dependencies or UI flows).
- requests `2.32.5` — Listed in `requirements.txt`; no direct `import requests` in first-party `.py` files (likely used by dependencies such as audio-separator / model tooling).
- Separate Python 3.8-oriented environment documented in `packaging/beatnet_service/README.md` and `packaging/beatnet_service/requirements.txt` (BeatNet, madmom, numba constraints). Built as `beatnet-service` via PyInstaller (`packaging/beatnet_service/beatnet-service.spec`).
## Configuration
- No `.env`-driven app config in `config.py`; paths derive from `sys.frozen`, platform, and `Path.home()`.
- Process flags: `STEMSEPARATOR_SUBPROCESS` and CLI `--separation-subprocess` for worker mode (`main.py`).
- `APPDATA` used on Windows for user dir when bundled (`config.py` `get_user_dir()`).
- `PATH` prepended with bundled `bin` for FFmpeg when frozen (`main.py`).
- PyInstaller `.spec` files: `packaging/StemSeparator-arm64.spec`, `packaging/StemSeparator-intel.spec`.
- Test and coverage: `pytest.ini` (coverage omit patterns, markers including `network`).
## Platform Requirements
- README targets macOS for the product; tests run on `macos-latest` in CI. Linux/WSL may run tests but full feature parity (ScreenCaptureKit, BlackHole, DMG) is macOS-centric.
- Packaged macOS `.app` / `.dmg` per `packaging/README.md` and `docs/PACKAGING.md` (referenced from README). FFmpeg bundled into the app bundle for separation pipelines (`main.py`, `core/separator.py` PATH handling).
<!-- gsd-stack-end -->

<!-- gsd-conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Python modules and packages use `snake_case`: `main_window.py`, `loop_math.py`, `beat_service_client.py`.
- Test files follow pytest discovery: `test_<module>.py` under `tests/` or `tests/ui/`.
- `snake_case` for functions and methods: `get_model_manager()`, `compute_bar_duration_seconds()`, `safe_execute()`.
- Module-level singleton accessors use `get_<name>()`: `get_logger()` in `utils/logger.py`, `get_model_manager()` in `core/model_manager.py`.
- `snake_case` for locals and instance attributes.
- “Private” UI and internal state often uses a leading underscore on attributes: e.g. `_content_stack`, `_btn_upload` in `ui/main_window.py`; module-level singleton holders like `_separator` in `core/separator.py`.
- `PascalCase` for classes: `Separator`, `MainWindow`, `ModelInfo`, `AppLogger`.
- Test classes use `Test*` prefix per `pytest.ini`: e.g. `TestErrorHandler`, `TestComputeBarDuration` in `tests/test_error_handler.py`, `tests/test_loop_math.py`.
- Enums use `PascalCase` members with string values: `ErrorType` in `utils/error_handler.py`.
## Code Style
- **Black** is the declared formatter (`requirements.txt`, `environment.yml`). No project-level `pyproject.toml` / `.black` overrides were found; use Black defaults (line length 88 unless you add config later).
- **Flake8** is listed for development (`requirements.txt`). No checked-in `.flake8` or `setup.cfg` flake8 section; treat Flake8 as the style gate when run manually or in CI if added.
## Import Organization
- `main.py` prepends the project root to `sys.path` so imports like `from core.model_manager import …` resolve when running from the repo root.
- No `src` layout or import aliases; imports are top-level package names (`core`, `ui`, `utils`, `config`) with project root on `PYTHONPATH` / cwd behavior from `main.py`.
## Error Handling
- Domain errors: hierarchy under `SeparationError` with `ErrorType` enum in `utils/error_handler.py` (`GPUMemoryError`, `ModelLoadingError`, etc.). Prefer raising these or standard exceptions where classification maps to retry/fallback behavior.
- Resilience: `ErrorHandler.retry_with_fallback()` and `safe_execute()` for controlled retries and optional default returns; `@retry_on_error` decorator for transient failures.
- User-facing flows: combine logging via `get_logger()` with exception context (`log_error_with_context` on `AppLogger` in `utils/logger.py`).
- Use for invariants sparingly; production paths favor explicit checks and logged errors.
## Logging
- Obtain the app logger with `get_logger()` from `utils/logger.py` (singleton `AppLogger`).
- Log levels: file handler captures DEBUG; console INFO and above. Use structured helpers where provided (`log_model_loading`, `log_chunk_progress`, etc.).
- Configuration constants (`LOG_FILE`, `LOG_LEVEL`, …) come from `config.py`.
## Comments
- Module docstrings describe purpose; many modules use German for descriptions (e.g. `utils/logger.py`, `config.py`).
- Inline **WHY** comments explain non-obvious behavior (e.g. `main.py` single-instance lock, PyInstaller `sys._MEIPASS` handling in `config.py`).
- UI and test files sometimes use English PURPOSE/CONTEXT headers (e.g. `tests/ui/conftest.py`, `tests/ui/test_main_window.py`).
- Public classes and methods often have short docstrings; type hints appear on signatures and dataclasses (`SeparationResult` in `core/separator.py`, `ModelInfo` in `core/model_manager.py`).
- Not all modules are fully typed; match surrounding style when adding code.
## Function Design
## Module Design
- Package `__init__.py` files are often minimal (e.g. `ui/widgets/__init__.py`).
- Several `core` modules expose `get_*()` and keep a private module-level instance (reset in `tests/ui/conftest.py` via `reset_singletons` for test isolation).
<!-- gsd-conventions-end -->

<!-- gsd-architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Single process for the GUI** with optional **worker modes** that reuse the same codebase (`main.py` separation CLI path; `core.separation_subprocess` module entry).
- **Singleton accessors** (`get_*`) in `core/` and `utils/` so the UI and orchestration code share one model cache, device selection, and recorder state.
- **Facade for the UI:** `ui/app_context.py` exposes backend services without widgets importing every module directly.
- **Bundled vs dev paths:** `config.py` resolves read-only resources (`BASE_DIR`, PyInstaller `sys._MEIPASS`) and writable user data (`USER_DIR`).
## Layers
- Purpose: Immutable defaults, model registry, quality presets, retry policies, and filesystem layout.
- Location: `config.py`
- Contains: `MODELS`, `QUALITY_PRESETS`, `ENSEMBLE_CONFIGS`, `RETRY_STRATEGIES`, `get_default_output_dir()`, path constants (`MODELS_DIR`, `TEMP_DIR`, etc.).
- Depends on: Standard library only (`os`, `pathlib`).
- Used by: All layers.
- Purpose: Stem separation, chunking, playback, recording, device selection, model download/verification, ensemble pipelines, time-stretch and export helpers.
- Location: `core/`
- Contains: `Separator`, `EnsembleSeparator`, `ModelManager`, `DeviceManager`, `ChunkProcessor`, `AudioPlayer`, `Recorder`, subprocess worker `run_separation_subprocess` in `core/separation_subprocess.py`, plus specialized modules (`background_stretch_manager.py`, `time_stretcher.py`, `screencapture_recorder.py`, `blackhole_installer.py`, `sampler_export.py`).
- Depends on: `config`, `utils` (logging, errors, file I/O helpers), third-party stacks (`audio-separator`, PyTorch, numpy, soundfile, librosa, sounddevice, etc.).
- Used by: `ui/` (via `AppContext` or direct `get_*` imports where historical), `main.py`, tests.
- Purpose: Logging, i18n, file validation, path helpers, beat-service client, macOS integration, BPM helpers, error handling with retries.
- Location: `utils/`
- Contains: `utils/logger.py`, `utils/i18n.py`, `utils/file_manager.py`, `utils/error_handler.py`, `utils/beat_service_client.py`, `utils/audio_processing.py`, and related modules.
- Depends on: `config` (sometimes indirectly), third-party libs as needed.
- Used by: `core/` and `ui/`.
- Purpose: Windows, widgets, dialogs, theming, settings persistence for the GUI.
- Location: `ui/`
- Contains: `ui/main_window.py`, `ui/widgets/*`, `ui/dialogs/*`, `ui/theme/*`, `ui/settings_manager.py`, `ui/splash_screen.py`, `ui/app_context.py`.
- Depends on: `core` and `utils` through `AppContext` and direct imports; `PySide6`.
- Used by: `main.py` only for bootstrap (then user events drive the rest).
- Purpose: Bundled icons, translation JSON, model weight files (when present).
- Location: `resources/icons/`, `resources/translations/`, `resources/models/`
- Depends on: Nothing; read via `config` paths.
- Purpose: macOS helpers and isolated Python environments for tools with conflicting dependencies.
- Location: `packaging/beatnet_service/`, `packaging/screencapture_tool/`, scripts under `packaging/`.
- Interacts with: `utils/beat_service_client.py`, `core/recorder.py` / macOS integration paths.
## Data Flow
- **Global singletons** back long-lived services (`get_separator()`, `get_model_manager()`, etc.).
- **User preferences** persist in `user_settings.json` via `SettingsManager`, not by editing `config.py`.
- **Qt widget state** lives in widget instances owned by `MainWindow` (`QStackedWidget` for main areas, nested pages in `PlayerWidget`).
## Key Abstractions
- Purpose: Structured outcome of a separation run (paths, model, device, timing, errors).
- Pattern: `@dataclass` return value from `Separator.separate()`.
- Purpose: Orchestrate validation, resampling, chunking, retries, and isolated ML execution.
- Examples: `core/separator.py`, `core/separation_subprocess.py`
- Pattern: Parent process uses `subprocess.Popen` with JSON IPC; worker imports `audio_separator.separator.Separator` only inside the child process.
- Purpose: Map logical model IDs in `config.MODELS` to files under `resources/models/`, download and verify weights (including YAML Demucs configs).
- Examples: `core/model_manager.py`
- Purpose: Split long inputs into overlapping segments and merge outputs; chunk length can follow `SettingsManager` when importable.
- Examples: `core/chunk_processor.py`
- Purpose: Lazy PyTorch import, probe MPS/CUDA/CPU, select and expose the active device string for separation.
- Examples: `core/device_manager.py`
- Purpose: Single entry for widgets to reach `Separator`, `Recorder`, `ChunkProcessor`, `ModelManager`, `DeviceManager`, `FileManager`, `SettingsManager`, `BlackHoleInstaller`, `ErrorHandler`, i18n, and paths.
- Examples: `ui/app_context.py`, `get_app_context()`
- Purpose: In-memory stem mixing and playback position; threading for non-blocking playback.
- Examples: `core/player.py`
## Entry Points
- Location: `main.py` → `main()`
- Triggers: `python main.py` or packaged app executable.
- Responsibilities: Lock file, dependency check, splash, `initialize_app()`, theme, `MainWindow`, `QApplication.exec()`.
- Location: `main.py` (early branch on `--separation-subprocess` or `STEMSEPARATOR_SUBPROCESS=1`) **or** `python -m core.separation_subprocess` (`core/separation_subprocess.py` `if __name__ == "__main__"`).
- Triggers: Parent process from `Separator._run_separation()`; must not initialize the GUI.
- Responsibilities: Parse params, call `run_separation_subprocess()`, print JSON result on stdout.
- Several `core/*.py` files expose `if __name__ == "__main__"` blocks for manual testing (e.g. `core/separator.py`); use only for development diagnostics.
## Error Handling
- Subprocess failures: non-zero exit, stderr logged, `SeparationError` raised in parent (`core/separator.py`).
- GPU/CPU OOM or transient issues: retry alternate strategies before surfacing to UI.
- GUI bootstrap: critical path wrapped in `main.py` with `QMessageBox` and log file path from `config.LOG_FILE`.
## Cross-Cutting Concerns
<!-- gsd-architecture-end -->

<!-- gsd-workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- gsd-workflow-end -->



<!-- gsd-profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- gsd-profile-end -->
