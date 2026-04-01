# Coding Conventions

**Analysis Date:** 2026-04-01

## Naming Patterns

**Files:**
- Python modules and packages use `snake_case`: `main_window.py`, `loop_math.py`, `beat_service_client.py`.
- Test files follow pytest discovery: `test_<module>.py` under `tests/` or `tests/ui/`.

**Functions:**
- `snake_case` for functions and methods: `get_model_manager()`, `compute_bar_duration_seconds()`, `safe_execute()`.
- Module-level singleton accessors use `get_<name>()`: `get_logger()` in `utils/logger.py`, `get_model_manager()` in `core/model_manager.py`.

**Variables:**
- `snake_case` for locals and instance attributes.
- “Private” UI and internal state often uses a leading underscore on attributes: e.g. `_content_stack`, `_btn_upload` in `ui/main_window.py`; module-level singleton holders like `_separator` in `core/separator.py`.

**Types:**
- `PascalCase` for classes: `Separator`, `MainWindow`, `ModelInfo`, `AppLogger`.
- Test classes use `Test*` prefix per `pytest.ini`: e.g. `TestErrorHandler`, `TestComputeBarDuration` in `tests/test_error_handler.py`, `tests/test_loop_math.py`.
- Enums use `PascalCase` members with string values: `ErrorType` in `utils/error_handler.py`.

## Code Style

**Formatting:**
- **Black** is the declared formatter (`requirements.txt`, `environment.yml`). No project-level `pyproject.toml` / `.black` overrides were found; use Black defaults (line length 88 unless you add config later).

**Linting:**
- **Flake8** is listed for development (`requirements.txt`). No checked-in `.flake8` or `setup.cfg` flake8 section; treat Flake8 as the style gate when run manually or in CI if added.

## Import Organization

**Order (observed pattern in `core/separator.py` and similar):**
1. Standard library (`pathlib`, `typing`, `threading`, …).
2. Third-party (`numpy`, `soundfile`, `librosa`, …).
3. First-party: `config` imports, then `core.*`, then `utils.*`.

**Path setup:**
- `main.py` prepends the project root to `sys.path` so imports like `from core.model_manager import …` resolve when running from the repo root.

**Path aliases:**
- No `src` layout or import aliases; imports are top-level package names (`core`, `ui`, `utils`, `config`) with project root on `PYTHONPATH` / cwd behavior from `main.py`.

## Error Handling

**Patterns:**
- Domain errors: hierarchy under `SeparationError` with `ErrorType` enum in `utils/error_handler.py` (`GPUMemoryError`, `ModelLoadingError`, etc.). Prefer raising these or standard exceptions where classification maps to retry/fallback behavior.
- Resilience: `ErrorHandler.retry_with_fallback()` and `safe_execute()` for controlled retries and optional default returns; `@retry_on_error` decorator for transient failures.
- User-facing flows: combine logging via `get_logger()` with exception context (`log_error_with_context` on `AppLogger` in `utils/logger.py`).

**Assertions in non-test code:**
- Use for invariants sparingly; production paths favor explicit checks and logged errors.

## Logging

**Framework:** Python `logging` with optional **colorlog** for console; file rotation via `RotatingFileHandler` in `utils/logger.py`.

**Patterns:**
- Obtain the app logger with `get_logger()` from `utils/logger.py` (singleton `AppLogger`).
- Log levels: file handler captures DEBUG; console INFO and above. Use structured helpers where provided (`log_model_loading`, `log_chunk_progress`, etc.).
- Configuration constants (`LOG_FILE`, `LOG_LEVEL`, …) come from `config.py`.

## Comments

**When to Comment:**
- Module docstrings describe purpose; many modules use German for descriptions (e.g. `utils/logger.py`, `config.py`).
- Inline **WHY** comments explain non-obvious behavior (e.g. `main.py` single-instance lock, PyInstaller `sys._MEIPASS` handling in `config.py`).
- UI and test files sometimes use English PURPOSE/CONTEXT headers (e.g. `tests/ui/conftest.py`, `tests/ui/test_main_window.py`).

**Docstrings / typing:**
- Public classes and methods often have short docstrings; type hints appear on signatures and dataclasses (`SeparationResult` in `core/separator.py`, `ModelInfo` in `core/model_manager.py`).
- Not all modules are fully typed; match surrounding style when adding code.

## Function Design

**Size:** Large modules exist (`core/separator.py`, `ui/main_window.py`); new code should still prefer focused functions and extracted helpers over growing monoliths further.

**Parameters:** Prefer explicit optional parameters with `Optional[...]` and defaults; callbacks typed as `Callable[..., ...]` where used (e.g. `progress_callback` in `Separator.separate` in `core/separator.py`).

**Return Values:** Dataclasses for structured results (`SeparationResult`); `Optional` or `None` for missing entities (`get_model_info` returning `None`).

## Module Design

**Exports:**
- Package `__init__.py` files are often minimal (e.g. `ui/widgets/__init__.py`).

**Singletons:**
- Several `core` modules expose `get_*()` and keep a private module-level instance (reset in `tests/ui/conftest.py` via `reset_singletons` for test isolation).

---

*Convention analysis: 2026-04-01*
