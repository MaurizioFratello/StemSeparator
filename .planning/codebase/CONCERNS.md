# Codebase Concerns

**Analysis Date:** 2026-04-01

## Tech Debt

**Monolithic UI modules:**
- Issue: Primary monitoring and playback UI live in a single very large module, which increases merge conflict risk, makes behavior hard to reason about, and complicates targeted testing.
- Files: `ui/widgets/player_widget.py` (~3950+ lines), `ui/widgets/loop_waveform_widget.py` (~1475 lines), `ui/widgets/export_loops_widget.py` (~1277 lines)
- Impact: Slower onboarding, higher regression risk when changing playback, time-stretch, or loop UX.
- Fix approach: Extract cohesive subcomponents (e.g. stretch playback, mixer state, file dialogs) into dedicated modules under `ui/widgets/` or `ui/` with narrow public APIs; keep `player_widget.py` as a thin coordinator.

**Third-party workarounds embedded in app code:**
- Issue: Separation runs in a dedicated subprocess to avoid resource leaks and crashes from the `audio-separator` stack; this adds IPC, timeout, and packaging complexity.
- Files: `core/separator.py`, `core/separation_subprocess.py` (see module docstring on multiprocessing/semaphore issues)
- Impact: More moving parts (stdin JSON, return codes, parse-multiple-JSON-lines); harder to debug failures across process boundaries.
- Fix approach: Treat as permanent architecture unless upstream fixes land; keep subprocess contract documented and add focused integration tests around JSON protocol edges.

**BeatNet isolated binary:**
- Issue: BPM/beat analysis uses a separate PyInstaller-built `beatnet-service` with its own Python/numba constraints, parallel to the main app environment.
- Files: `utils/beat_service_client.py`, `packaging/beatnet_service/`, `utils/beat_detection.py`, `utils/beatnet_warmup.py`
- Impact: Two release artifacts to build and version; discovery paths for the binary must stay in sync with packaging (`sys._MEIPASS`, `packaging/beatnet_service/dist/`).
- Fix approach: Document version matrix in release checklist; consider CI smoke test that locates binary and runs a minimal JSON round-trip.

**Declared but unused dependency:**
- Issue: `requests` is pinned in `requirements.txt` but no `import requests` appears in application Python sources (may be transitive-only or leftover).
- Files: `requirements.txt`
- Impact: Unnecessary install surface and audit noise; version drift without code-level usage.
- Fix approach: Remove if confirmed unused, or add a short comment if retained for a script/tool not in-repo.

**Mixed language and comments:**
- Issue: German module strings and comments coexist with English docstrings (e.g. `config.py`, `core/model_manager.py`, `pytest.ini`).
- Files: `config.py`, `core/model_manager.py`, `pytest.ini`, various `ui/` files
- Impact: Inconsistent docs for contributors; no functional bug.
- Fix approach: Gradually align on one language for public docstrings and user-facing strings per team convention.

**Obsolete / renamed test module:**
- Issue: Beat detection tests were renamed to avoid import/discovery problems but kept in-tree.
- Files: `tests/obsolete_test_beat_detection.py` (see `CHANGELOG.md`); content still exercises `utils.beat_detection` APIs
- Impact: Name suggests “do not use” while file may still be maintained; confusing for triage.
- Fix approach: Either merge into active tests or move to `tests/legacy/` with explicit pytest ignore, or delete if superseded.

**Hardcoded project paths in tests:**
- Issue: Several tests insert a fixed developer path into `sys.path`.
- Files: `tests/test_player_manual.py`, `tests/test_ensemble_manual.py`, `tests/test_ensemble_realworld.py`, `tests/test_synchronization.py` (pattern: `/home/user/StemSeparator`)
- Impact: Brittle on other machines; may mask missing package layout if another path happens to work.
- Fix approach: Remove inserts and rely on pytest rootdir / `conftest.py` path setup, or use `Path(__file__).resolve().parents[...]`.

**Incomplete navigation chrome:**
- Issue: Sidebar nav buttons are created without loading real icons yet.
- Files: `ui/main_window.py` (`_create_nav_button`, TODO ~line 252)
- Impact: Visual polish gap only.
- Fix approach: Wire `ICONS_DIR` resources when assets exist.

## Known Bugs

**Windows entry point likely broken at import time:**
- Symptoms: `import fcntl` in `main.py` fails on Windows (module does not exist), so the GUI entry point cannot start on Windows without modification.
- Files: `main.py` (lines 10, 60, 88)
- Trigger: Run `python main.py` on Windows with otherwise valid dependencies.
- Workaround: None in-repo; would require a Windows-compatible lock (e.g. `msvcrt`, `portalocker`, or skip lock on win32).

**Manual test scripts use pytest-discoverable names:**
- Symptoms: Files such as `tests/test_player_manual.py` define `test_*` functions and live under `tests/` with `python_files = test_*.py`, so they run in normal `pytest` invocations including CI, while docstrings describe “manual” usage and embed fragile `sys.path` hacks.
- Files: `tests/test_player_manual.py`, `tests/test_ensemble_manual.py`
- Trigger: `pytest` without exclusion.
- Workaround: Use markers (`@pytest.mark.manual`) + `pytest -m "not manual"` or rename files to `manual_*.py` outside default patterns.

## Security Considerations

**Subprocess and external binaries:**
- Risk: Separation, Rubberband CLI, BeatNet service, ScreenCapture recorder, and macOS `osascript`/`open` invocations expand the attack surface if any user-controlled path were ever passed unsafely to a shell.
- Files: `core/time_stretcher.py`, `core/separator.py`, `utils/beat_service_client.py`, `core/screencapture_recorder.py`, `utils/macos_integration.py`, `core/blackhole_installer.py`
- Current mitigation: Most subprocess calls use argument lists (not `shell=True`); separation uses structured JSON over stdin.
- Recommendations: Continue avoiding `shell=True`; validate and normalize all filesystem paths from UI before passing to subprocess helpers; audit `osascript` string builds if any user text is ever interpolated.

**Single-instance lock file:**
- Risk: Lock file path under user data directory (`config.py` / `main.py` `LOCK_FILE`) is predictable; low severity for a desktop app.
- Files: `main.py`, `config.py`
- Current mitigation: Exclusive non-blocking flock on Unix.
- Recommendations: On Windows, once `fcntl` is replaced, use the same path semantics for consistency.

## Performance Bottlenecks

**Heavy ML inference and I/O:**
- Problem: Stem separation and ensemble merging are CPU/GPU and disk intensive; long tracks use chunked processing (`config.py` chunk settings) and subprocess isolation adds overhead.
- Files: `core/separator.py`, `core/chunk_processor.py`, `core/ensemble_separator.py`, `config.py` (`CHUNK_LENGTH_SECONDS`, etc.)
- Cause: Model size, sample-rate constraints (`DEFAULT_SAMPLE_RATE`), and repeated disk writes for stems.
- Improvement path: User-facing quality presets already exist; further gains need profiling on target hardware, optional GPU paths, and avoiding redundant resampling.

**Time-stretch export:**
- Problem: Rubberband CLI invocation per operation is high quality but slower than lightweight preview algorithms.
- Files: `core/time_stretcher.py`
- Cause: Intentional quality tradeoff (see module docstring vs `pyrubberband`).
- Improvement path: Keep preview vs export quality split; batch or cache where `core/stretch_cache.py` already applies.

**GUI thread and blocking work:**
- Problem: Large widgets and many `except Exception` handlers can hide slow synchronous work on the UI thread.
- Files: `ui/widgets/player_widget.py`, `ui/main_window.py`
- Cause: Qt patterns and defensive catches.
- Improvement path: Profile with Qt tools; move long work to `QThread`/`QRunnable` consistently (already used in places like BPM workers—extend pattern where missing).

## Fragile Areas

**JSON protocol between main process and separation subprocess:**
- Files: `core/separator.py`, `core/separation_subprocess.py`
- Why fragile: Multiple JSON objects on stdout, retries, and strict success detection; parsing mistakes surface as generic separation failures.
- Safe modification: Add tests for stdout parsing edge cases; log raw stderr on failure (already partially done).
- Test coverage: Integration tests exist under `tests/test_integration_separator.py` and related; extend when changing protocol.

**Beat service timeouts and binary absence:**
- Files: `utils/beat_service_client.py`, `utils/beat_detection.py`
- Why fragile: Network-like failure modes (timeouts, malformed JSON) must degrade to librosa or user messaging without crashing.
- Safe modification: Preserve explicit exception types (`BeatServiceTimeout`, `BeatServiceNotFound`) and user-visible fallbacks.
- Test coverage: Mock-based tests in `tests/`; real binary tests environment-dependent.

**macOS-specific integrations:**
- Files: `utils/macos_integration.py`, `ui/theme/macos_dialogs.py`, `ui/theme/macos_effects.py`, `core/blackhole_installer.py`
- Why fragile: Behavior differs by OS version and permissions; CI is macOS-only so Linux devs do not get automated coverage for these paths.
- Safe modification: Guard all imports and calls with `sys.platform == "darwin"` (pattern already used in places).

## Scaling Limits

**Separation subprocess timeout:**
- Current capacity: Hard cap of 7200 seconds per separation job in `core/separator.py`.
- Limit: Extremely long files or pathological hangs still fail the job; true hangs may consume resources until timeout.
- Scaling path: Raise cap with user setting, or split file by chunk at UI level before separation.

**Memory and GPU:**
- Current capacity: Driven by `audio-separator`, PyTorch, and chunk parameters—not centrally quota-enforced in application code.
- Limit: OOM on large files or high polyphony ensemble configs.
- Scaling path: Document RAM/GPU guidance; rely on retry strategies in `utils/error_handler.py` and chunking.

## Dependencies at Risk

**`audio-separator` and underlying torch/onnx stack:**
- Risk: Version coupling to separation quality, subprocess workaround, and PyInstaller bundling.
- Impact: Upgrades may reintroduce multiprocessing issues or API changes in `Separator`.
- Migration plan: Pin versions deliberately; run full separation integration tests after bumps (`requirements.txt`, `tests/test_integration_separator.py`).

**`pyrubberband` vs Rubberband CLI (`core/time_stretcher.py`):**
- Risk: Comment notes stereo bug in `pyrubberband` 0.4.0; project still lists `pyrubberband==0.4.0` in `requirements.txt` while stretch path uses CLI.
- Impact: Confusion and possible removal candidate if CLI-only path is permanent.
- Migration plan: Verify whether `pyrubberband` is still required elsewhere; trim dependency if not.

## Missing Critical Features

**Cross-platform parity for core entry:**
- Problem: Documented user dirs for Windows exist in `config.py`, but `main.py` cannot run on Windows due to `fcntl`.
- Blocks: First-class Windows desktop support.

**Automated CI on Linux:**
- Problem: `.github/workflows/tests.yml` uses `macos-latest` only; Linux/WSL developers get no CI signal matching their OS.
- Blocks: Early detection of POSIX-only assumptions outside macOS-specific modules.

## Test Coverage Gaps

**Warning suppression in pytest defaults:**
- What's not tested: Deprecation and runtime warnings from dependencies may be invisible during routine runs.
- Files: `pytest.ini` (`-p no:warnings` in `addopts`)
- Risk: Missed dependency deprecations until upgrade breaks.
- Priority: Medium

**Headless/GUI split:**
- What's not tested: Full visual and native dialog behavior across OS versions; many tests use `pytest-qt` with mocked or headless constraints.
- Files: `tests/ui/`, `pytest.ini` markers `gui`
- Risk: macOS-only regressions in production.
- Priority: Medium for release branches; use manual QA checklist.

**Integration scripts not in default pytest focus:**
- What's not tested: `tests/manual_deeprhythm_integration.py` is a runnable script-style suite, not integrated into standard pytest discovery the same way as unit tests.
- Files: `tests/manual_deeprhythm_integration.py`
- Risk: DeepRhythm edge cases drift without CI.
- Priority: Low unless DeepRhythm becomes mandatory path.

---

*Concerns audit: 2026-04-01*
