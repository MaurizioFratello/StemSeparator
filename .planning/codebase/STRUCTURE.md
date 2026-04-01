# Codebase Structure

**Analysis Date:** 2026-04-01

## Directory Layout

```
StemSeparator/
├── main.py                 # Application entry: GUI bootstrap, single-instance lock, separation CLI worker branch
├── config.py               # Paths, models, presets, retry config, app metadata
├── requirements.txt        # Python dependencies (pinned)
├── environment.yml         # Conda environment name / deps (if used)
├── core/                   # Domain logic: separation, playback, recording, models, devices
├── ui/                     # PySide6 GUI: main window, widgets, dialogs, theme, settings manager
├── utils/                  # Shared utilities: logging, i18n, files, errors, beat client, audio helpers
├── resources/              # Bundled assets: icons, translations, model files
│   ├── icons/
│   ├── translations/       # e.g. en.json, de.json
│   └── models/             # Downloaded / shipped weights (large; may be gitignored partially)
├── tests/                  # pytest + pytest-qt; unit and UI tests
│   ├── ui/
│   └── fixtures/
├── packaging/              # App packaging scripts, icon generation, beatnet_service, screencapture_tool
├── docs/                   # Project documentation (guides, PRDs — not runtime)
├── .github/                # CI workflows (e.g. tests.yml), issue templates
├── CONTRIBUTING.md
├── README.md
└── .planning/              # GSD / planning artifacts (e.g. codebase maps)
    └── codebase/
```

## Directory Purposes

**`core/`:**
- Purpose: Audio separation orchestration, ML-adjacent processing, playback, recording, subprocess worker.
- Contains: Python modules per concern (`separator.py`, `ensemble_separator.py`, `model_manager.py`, `device_manager.py`, `chunk_processor.py`, `player.py`, `recorder.py`, `separation_subprocess.py`, etc.).
- Key files: `core/separator.py`, `core/separation_subprocess.py`, `core/model_manager.py`, `core/player.py`, `core/recorder.py`

**`ui/`:**
- Purpose: All Qt UI code and runtime settings for the GUI.
- Contains: `main_window.py`, `splash_screen.py`, `app_context.py`, `settings_manager.py`, `widgets/`, `dialogs/`, `theme/`.
- Key files: `ui/main_window.py`, `ui/app_context.py`, `ui/settings_manager.py`

**`utils/`:**
- Purpose: Infrastructure used by core and UI without belonging to a single feature.
- Contains: `logger.py`, `i18n.py`, `file_manager.py`, `error_handler.py`, `beat_service_client.py`, `audio_processing.py`, platform helpers.
- Key files: `utils/logger.py`, `utils/error_handler.py`, `utils/file_manager.py`

**`resources/`:**
- Purpose: Static assets and large binary model data referenced via `config` (`RESOURCES_DIR`, `MODELS_DIR`, `TRANSLATIONS_DIR`, `ICONS_DIR`).
- Contains: Icons, locale JSON, ONNX/checkpoints/YAML for separation models.

**`tests/`:**
- Purpose: Automated tests mirroring package layout under `tests/` and `tests/ui/`.
- Contains: `conftest.py` for Qt fixtures, integration tests for separator/recorder/player, widget tests.

**`packaging/`:**
- Purpose: Build automation, auxiliary services, and platform-specific tools (not imported as a Python package by the main app in normal runs).
- Contains: `beatnet_service/` (isolated BeatNet worker), `screencapture_tool/` (Swift), helper scripts (`download_models.py`, icon generation).

**`docs/`:**
- Purpose: Human-readable design notes, user guides, migration docs.
- Contains: Markdown files; does not define runtime behavior.

## Key File Locations

**Entry Points:**
- `main.py`: Primary executable — GUI and separation worker dispatch.
- `core/separation_subprocess.py`: `__main__` block for JSON stdin/stdout worker when launched with `-m core.separation_subprocess`.

**Configuration:**
- `config.py`: Central constants; path helpers `get_base_dir()`, `get_user_dir()`, `get_default_output_dir()`.
- `ui/settings_manager.py`: Mutable user settings file `USER_DIR/user_settings.json`.

**Core Logic:**
- `core/separator.py`: Main separation API and subprocess orchestration.
- `core/ensemble_separator.py`: Multi-model ensemble pipeline.
- `core/chunk_processor.py`: Long-file chunking and merge.
- `core/model_manager.py`: Model discovery and downloads.
- `core/device_manager.py`: Torch device selection.
- `core/player.py`: Stem playback and mixing.
- `core/recorder.py`: System audio capture.

**Testing:**
- `tests/`: Root-level tests for core/utils.
- `tests/ui/`: Qt widget tests with `pytest-qt`.
- `tests/ui/conftest.py`: Shared Qt fixtures.

**CI:**
- `.github/workflows/tests.yml`: Workflow definition for automated tests.

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` throughout `core/`, `ui/`, `utils/` (e.g. `main_window.py`, `separation_subprocess.py`).
- Test files: `test_*.py` or `test_*` under `tests/` (e.g. `tests/test_separator.py`, `tests/ui/test_main_window.py`).

**Directories:**
- Package-style folders: short lowercase names (`core`, `ui`, `utils`, `widgets`, `dialogs`, `theme`).

**Symbols (prescriptive for new code):**
- Classes: `PascalCase` (`MainWindow`, `SeparationResult`, `AudioPlayer`).
- Functions and methods: `snake_case` (`get_separator`, `separate_ensemble`).
- Singleton accessors: prefix `get_` + module noun (`get_model_manager`, `get_app_context`).
- Private helpers: leading underscore on methods/attributes where the codebase already uses that pattern (e.g. `_setup_ui` in `MainWindow`).

## Where to Add New Code

**New Feature (e.g. a new processing step in the stem pipeline):**
- Primary logic: `core/` in a new module or extend `core/separator.py` / `core/chunk_processor.py` depending on scope.
- If the UI needs controls: new widget under `ui/widgets/` or dialog under `ui/dialogs/`; register in `ui/main_window.py` if it is a new view.
- Expose shared access via `AppContext` in `ui/app_context.py` if multiple widgets need the same backend service.
- Tests: `tests/test_<feature>.py` or `tests/ui/test_<widget>.py`; reuse `tests/ui/conftest.py` for Qt.

**New Component/Module:**
- Implementation: peer modules next to related code — `core/` for audio/ML orchestration, `ui/widgets/` for controls, `utils/` for generic helpers.
- Configuration defaults: add to `config.py`; user-tunable values: extend `SettingsManager` schema and defaults.

**Utilities:**
- Shared helpers: `utils/`; avoid circular imports — `core` should not depend on `ui` (exception: `chunk_processor.py` optionally reads settings via lazy import; follow that pattern sparingly).

**Translations:**
- Add keys to `resources/translations/en.json` and `resources/translations/de.json`; use `t()` / `AppContext.translate()`.

## Special Directories

**`resources/models/`:**
- Purpose: ONNX, checkpoints, YAML configs for `audio-separator`.
- Generated: Model files are downloaded or supplied by packaging scripts; not all may be committed.
- Committed: Repository policy varies; large binaries often excluded from git.

**`packaging/beatnet_service/`:**
- Purpose: Standalone BeatNet worker environment and binary build.
- Generated: Build artifacts from packaging; subprocess invoked by main app via `utils/beat_service_client.py`.

**`.planning/`:**
- Purpose: Planning and codebase documentation for GSD workflows.
- Generated: Manual / tool-written; safe to commit text artifacts.

---

*Structure analysis: 2026-04-01*
