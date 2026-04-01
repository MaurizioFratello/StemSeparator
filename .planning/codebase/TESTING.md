# Testing Patterns

**Analysis Date:** 2026-04-01

## Test Framework

**Runner:**
- **pytest** (`requirements.txt` pins pytest; `environment.yml` specifies `pytest>=7.4.0`).
- Config: `pytest.ini` at repository root.

**Assertion library:**
- Plain `assert` statements (pytest style).

**Plugins:**
- **pytest-cov** — coverage reports.
- **pytest-qt** — Qt widgets and `qtbot` fixture.
- **pytest-mock** — listed in `requirements.txt` / `environment.yml`; the `mocker` fixture is **not** used in the current test suite (no matches under `tests/`). Prefer **`unittest.mock`** (`patch`, `Mock`, `MagicMock`) and **`monkeypatch`** from pytest instead.

**Run Commands:**
```bash
pytest                              # All tests (uses addopts in pytest.ini)
pytest tests/test_loop_math.py      # Single file
pytest tests/ui/                    # UI tests only
pytest -m unit                      # Only tests marked @pytest.mark.unit
pytest --no-cov                     # Disable coverage (faster local runs)
```

CI (`.github/workflows/tests.yml`) runs:
```bash
pytest --cov --cov-report=xml --cov-report=term
```
Codecov uploads `coverage.xml`.

## Test File Organization

**Location:**
- **Core / utils:** `tests/test_<area>.py` (e.g. `tests/test_error_handler.py`, `tests/test_loop_math.py`).
- **UI:** `tests/ui/test_<component>.py` plus `tests/ui/conftest.py` for shared Qt fixtures.

**Naming:**
- Files: `test_*.py` (enforced by `python_files` in `pytest.ini`).
- Classes: `Test*` (optional; many tests are module-level functions).
- Functions: `test_*`.

**Structure:**
```
tests/
├── test_*.py              # Domain, core, utils, integration
├── manual_deeprhythm_integration.py   # Manual / special runs (not standard unit layout)
├── obsolete_test_beat_detection.py    # Legacy / obsolete
└── ui/
    ├── conftest.py
    └── test_*.py
```

## Test Structure

**Suite organization:**
- Group related tests in classes (`TestErrorHandler`, `TestComputeBarDuration`) or flat functions with descriptive names.
- Docstrings on tests describe behavior (often German in older tests, English in newer UI tests).

**Example (unit class + markers):**
```python
@pytest.mark.unit
class TestErrorHandler:
    def test_safe_execute_failure(self):
        handler = ErrorHandler()
        def failing_func():
            raise ValueError("Test error")
        result = handler.safe_execute(failing_func, default_return="default")
        assert result == "default"
```
Reference: `tests/test_error_handler.py`.

**Markers (`pytest.ini`):**
- `unit`, `integration`, `slow`, `gui`, `audio`, `network` — use `@pytest.mark.<name>`; `--strict-markers` requires registered markers only.
- Integration tests combine `@pytest.mark.integration` and sometimes `@pytest.mark.slow` or `@pytest.mark.xfail` (e.g. `tests/test_integration_recording.py`).

**Setup / teardown:**
- **Session-scoped `qapp`** in `tests/ui/conftest.py` creates a single `QApplication` for the process.
- **`reset_singletons`** fixture clears module-level singletons before/after each test to avoid state leakage.
- **`tmp_path` / `temp_output_dir` / `mock_audio_file`** for filesystem and minimal WAV fixtures.
- **`monkeypatch`** to redirect paths (e.g. `model_manager_with_temp_dir` in `tests/test_model_manager.py`).
- Integration fixtures like **`mock_blackhole_available`** in `tests/test_integration_recording.py` use `patch` as context-managed fixtures.

## Mocking

**Primary tools:**
- **`unittest.mock`:** `patch`, `Mock`, `MagicMock` — used heavily (e.g. `tests/test_separator.py` patches `audio_separator.separator.Separator`; `tests/test_main_window.py` patches `SettingsDialog`).
- **`pytest` `monkeypatch`:** patching attributes on modules for config paths (`tests/test_model_manager.py`).

**Qt:**
- **`qtbot`** from pytest-qt: `qtbot.addWidget(widget)` for proper widget lifecycle; `qtbot.wait(ms)` for short async delays (e.g. `tests/ui/test_player_widget_time_stretch.py`).

**What to mock:**
- External heavy deps: `audio_separator` in separator tests, dialogs for menu actions, platform APIs for macOS-specific theme tests (`tests/test_macos_colors.py`, `tests/test_macos_effects.py`).
- Hardware / drivers: BlackHole and recorder internals in integration recording tests.

**What not to mock (unless slow/flaky):**
- Pure logic under test (`utils/loop_math.py` tests use direct assertions only).

## Fixtures and Factories

**Test data:**
- **`mock_audio_file`** in `tests/ui/conftest.py` writes a minimal stereo WAV via `wave` + `numpy`.
- **`temp_models_dir`** + **`model_manager_with_temp_dir`** in `tests/test_model_manager.py` isolate model storage.
- Integration tests may build temp dirs with `tempfile` / `shutil` and real `numpy`/`soundfile` writes where needed.

## Coverage

**Requirements:**
- No enforced percentage in-repo; `pytest.ini` sets `--cov=.` with branch coverage and HTML + term-missing reports by default.

**Omit patterns (`pytest.ini` `[coverage:run]`):**
- `tests/*`, `*/site-packages/*`, `*/__pycache__/*`, `*/venv/*`

**View coverage locally:**
```bash
pytest                    # generates htmlcov/ when using default addopts
# open htmlcov/index.html
```

## Test Types

**Unit tests:**
- Fast, isolated logic (`tests/test_loop_math.py`, `tests/test_error_handler.py`); UI smoke tests with `qapp` + `reset_singletons` (`tests/ui/test_main_window.py`).

**Integration tests:**
- Multi-component workflows: `tests/test_integration_separator.py`, `tests/test_integration_recording.py`, `tests/test_integration_simple.py` — marked `integration`, often slower, may use real temp files and mocked device layers.

**Manual / exploratory:**
- `tests/test_player_manual.py`, `tests/manual_deeprhythm_integration.py` — not standard automated naming; treat as manual or special runs.

**E2E:**
- No separate Playwright/Selenium stack; “integration” + Qt tests approximate GUI coverage.

## Common Patterns

**Async / Qt timing:**
- Use `qtbot.wait(n)` for small delays; avoid long fixed sleeps in new tests where `waitSignal` or event-driven assertions would be more reliable.

**Error testing:**
```python
with pytest.raises(ValueError):
    compute_bar_duration_seconds(0)
```
Reference: `tests/test_loop_math.py`.

**xfail:**
- Use for known flaky or environment-specific cases with a reason string (see `tests/test_integration_recording.py`).

---

*Testing analysis: 2026-04-01*
