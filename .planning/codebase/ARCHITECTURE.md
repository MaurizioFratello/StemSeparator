# Architecture

**Analysis Date:** 2026-04-01

## Pattern Overview

**Overall:** Layered desktop application with a PySide6 GUI, singleton-backed domain services, and subprocess isolation for heavy ML separation work.

**Key Characteristics:**
- **Single process for the GUI** with optional **worker modes** that reuse the same codebase (`main.py` separation CLI path; `core.separation_subprocess` module entry).
- **Singleton accessors** (`get_*`) in `core/` and `utils/` so the UI and orchestration code share one model cache, device selection, and recorder state.
- **Facade for the UI:** `ui/app_context.py` exposes backend services without widgets importing every module directly.
- **Bundled vs dev paths:** `config.py` resolves read-only resources (`BASE_DIR`, PyInstaller `sys._MEIPASS`) and writable user data (`USER_DIR`).

## Layers

**Configuration (constants and path resolution):**
- Purpose: Immutable defaults, model registry, quality presets, retry policies, and filesystem layout.
- Location: `config.py`
- Contains: `MODELS`, `QUALITY_PRESETS`, `ENSEMBLE_CONFIGS`, `RETRY_STRATEGIES`, `get_default_output_dir()`, path constants (`MODELS_DIR`, `TEMP_DIR`, etc.).
- Depends on: Standard library only (`os`, `pathlib`).
- Used by: All layers.

**Core domain (audio ML and orchestration):**
- Purpose: Stem separation, chunking, playback, recording, device selection, model download/verification, ensemble pipelines, time-stretch and export helpers.
- Location: `core/`
- Contains: `Separator`, `EnsembleSeparator`, `ModelManager`, `DeviceManager`, `ChunkProcessor`, `AudioPlayer`, `Recorder`, subprocess worker `run_separation_subprocess` in `core/separation_subprocess.py`, plus specialized modules (`background_stretch_manager.py`, `time_stretcher.py`, `screencapture_recorder.py`, `blackhole_installer.py`, `sampler_export.py`).
- Depends on: `config`, `utils` (logging, errors, file I/O helpers), third-party stacks (`audio-separator`, PyTorch, numpy, soundfile, librosa, sounddevice, etc.).
- Used by: `ui/` (via `AppContext` or direct `get_*` imports where historical), `main.py`, tests.

**Utilities (cross-cutting infrastructure):**
- Purpose: Logging, i18n, file validation, path helpers, beat-service client, macOS integration, BPM helpers, error handling with retries.
- Location: `utils/`
- Contains: `utils/logger.py`, `utils/i18n.py`, `utils/file_manager.py`, `utils/error_handler.py`, `utils/beat_service_client.py`, `utils/audio_processing.py`, and related modules.
- Depends on: `config` (sometimes indirectly), third-party libs as needed.
- Used by: `core/` and `ui/`.

**Presentation (PySide6):**
- Purpose: Windows, widgets, dialogs, theming, settings persistence for the GUI.
- Location: `ui/`
- Contains: `ui/main_window.py`, `ui/widgets/*`, `ui/dialogs/*`, `ui/theme/*`, `ui/settings_manager.py`, `ui/splash_screen.py`, `ui/app_context.py`.
- Depends on: `core` and `utils` through `AppContext` and direct imports; `PySide6`.
- Used by: `main.py` only for bootstrap (then user events drive the rest).

**Resources (data, not code):**
- Purpose: Bundled icons, translation JSON, model weight files (when present).
- Location: `resources/icons/`, `resources/translations/`, `resources/models/`
- Depends on: Nothing; read via `config` paths.

**Packaging and auxiliary binaries (out-of-tree workers):**
- Purpose: macOS helpers and isolated Python environments for tools with conflicting dependencies.
- Location: `packaging/beatnet_service/`, `packaging/screencapture_tool/`, scripts under `packaging/`.
- Interacts with: `utils/beat_service_client.py`, `core/recorder.py` / macOS integration paths.

## Data Flow

**Application startup:**

1. `main.py` acquires a single-instance file lock (`fcntl` on `USER_DIR/.stemseparator.lock`).
2. `QApplication` and `SplashScreen` are created; `check_dependencies()` validates imports (`PySide6`, `soundfile`, `numpy`).
3. `initialize_app()` calls `set_language()` and `get_model_manager()` to log model availability.
4. `ThemeManager.apply_to_app()` applies global Qt styling (`ui/theme/theme_manager.py`).
5. Optional background BeatNet warm-up (`utils/beatnet_warmup.py`).
6. `MainWindow()` constructs feature widgets (`ui/main_window.py`).

**Single-model stem separation:**

1. User selects a file and options in `UploadWidget` / queue; settings come from `SettingsManager` (`USER_DIR/user_settings.json`).
2. `Separator.separate()` in `core/separator.py` validates audio via `FileManager`, resamples to `DEFAULT_SAMPLE_RATE` (44100 Hz) when needed, and decides chunking via `ChunkProcessor`.
3. For each chunk or whole file, `_run_separation()` spawns a **subprocess** that runs `audio-separator` inside `core/separation_subprocess.py` (or the frozen equivalent with `--separation-subprocess`). Parameters are sent as JSON on stdin; results return as JSON on stdout.
4. `DeviceManager` supplies device strings (`cpu` / `mps` / `cuda`); `ErrorHandler.retry_with_fallback()` can retry with strategies from `config.RETRY_STRATEGIES`.
5. Stems are written under the chosen output directory; `ChunkProcessor` merges chunk outputs when applicable.

**Ensemble separation:**

1. `EnsembleSeparator.separate_ensemble()` in `core/ensemble_separator.py` orchestrates multiple passes through `Separator` / intermediate files, guided by `ENSEMBLE_CONFIGS` in `config.py`.
2. Uses shared temp/cache under `TEMP_DIR` (e.g. ensemble cache paths in the ensemble module).

**Playback and monitoring:**

1. `AudioPlayer` in `core/player.py` loads stem files, mixes per `StemSettings`, and plays via `sounddevice`.
2. Widgets such as `PlayerWidget` drive the player and reflect state through Qt signals/slots and callbacks.

**System audio recording (macOS-focused):**

1. `Recorder` in `core/recorder.py` selects backends (e.g. ScreenCaptureKit vs BlackHole) and captures audio to buffers/files.
2. `BlackHoleInstaller` and macOS-specific utilities support setup and discovery.

**Beat grid / loop features:**

1. `utils/beat_service_client.py` invokes the packaged **beatnet-service** binary with JSON I/O for beat/downbeat data, separate from the main Python env to satisfy BeatNet/numba constraints.

**State Management:**
- **Global singletons** back long-lived services (`get_separator()`, `get_model_manager()`, etc.).
- **User preferences** persist in `user_settings.json` via `SettingsManager`, not by editing `config.py`.
- **Qt widget state** lives in widget instances owned by `MainWindow` (`QStackedWidget` for main areas, nested pages in `PlayerWidget`).

## Key Abstractions

**`SeparationResult` (`core/separator.py`):**
- Purpose: Structured outcome of a separation run (paths, model, device, timing, errors).
- Pattern: `@dataclass` return value from `Separator.separate()`.

**`Separator` + subprocess worker:**
- Purpose: Orchestrate validation, resampling, chunking, retries, and isolated ML execution.
- Examples: `core/separator.py`, `core/separation_subprocess.py`
- Pattern: Parent process uses `subprocess.Popen` with JSON IPC; worker imports `audio_separator.separator.Separator` only inside the child process.

**`ModelManager` / `ModelInfo`:**
- Purpose: Map logical model IDs in `config.MODELS` to files under `resources/models/`, download and verify weights (including YAML Demucs configs).
- Examples: `core/model_manager.py`

**`ChunkProcessor` / `AudioChunk`:**
- Purpose: Split long inputs into overlapping segments and merge outputs; chunk length can follow `SettingsManager` when importable.
- Examples: `core/chunk_processor.py`

**`DeviceManager` / `DeviceInfo`:**
- Purpose: Lazy PyTorch import, probe MPS/CUDA/CPU, select and expose the active device string for separation.
- Examples: `core/device_manager.py`

**`AppContext`:**
- Purpose: Single entry for widgets to reach `Separator`, `Recorder`, `ChunkProcessor`, `ModelManager`, `DeviceManager`, `FileManager`, `SettingsManager`, `BlackHoleInstaller`, `ErrorHandler`, i18n, and paths.
- Examples: `ui/app_context.py`, `get_app_context()`

**`AudioPlayer` / `PlaybackState`:**
- Purpose: In-memory stem mixing and playback position; threading for non-blocking playback.
- Examples: `core/player.py`

## Entry Points

**GUI application:**
- Location: `main.py` → `main()`
- Triggers: `python main.py` or packaged app executable.
- Responsibilities: Lock file, dependency check, splash, `initialize_app()`, theme, `MainWindow`, `QApplication.exec()`.

**Separation subprocess (stdin JSON worker):**
- Location: `main.py` (early branch on `--separation-subprocess` or `STEMSEPARATOR_SUBPROCESS=1`) **or** `python -m core.separation_subprocess` (`core/separation_subprocess.py` `if __name__ == "__main__"`).
- Triggers: Parent process from `Separator._run_separation()`; must not initialize the GUI.
- Responsibilities: Parse params, call `run_separation_subprocess()`, print JSON result on stdout.

**Optional module CLIs:**
- Several `core/*.py` files expose `if __name__ == "__main__"` blocks for manual testing (e.g. `core/separator.py`); use only for development diagnostics.

## Error Handling

**Strategy:** Typed exceptions (`SeparationError` hierarchy in `utils/error_handler.py`), centralized logging (`utils/logger.py`), and **retry with device/chunk fallback** via `ErrorHandler.retry_with_fallback()` using `config.RETRY_STRATEGIES`.

**Patterns:**
- Subprocess failures: non-zero exit, stderr logged, `SeparationError` raised in parent (`core/separator.py`).
- GPU/CPU OOM or transient issues: retry alternate strategies before surfacing to UI.
- GUI bootstrap: critical path wrapped in `main.py` with `QMessageBox` and log file path from `config.LOG_FILE`.

## Cross-Cutting Concerns

**Logging:** `colorlog`-style app logger; log file under `LOGS_DIR` (`config.LOG_FILE`). Use `get_logger()` from `utils/logger.py`.

**Validation:** Audio files via `FileManager` (`utils/file_manager.py`); model files via `ModelManager._verify_model()`.

**Authentication:** Not applicable (local desktop app; no cloud auth in core paths).

**Internationalization:** JSON dictionaries in `resources/translations/`; `utils/i18n.py` with `t()` / `set_language()`.

---

*Architecture analysis: 2026-04-01*
