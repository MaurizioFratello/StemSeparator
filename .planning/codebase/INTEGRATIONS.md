# External Integrations

**Analysis Date:** 2026-04-01

## APIs & External Services

**Model artifacts (HTTP/HTTPS):**
- Separation and Demucs/MDX/BS-RoFormer weights are fetched by the **audio-separator** library when `Separator.load_model()` runs (`core/model_manager.py`, `packaging/download_models.py`). Upstream download URLs and hosting are not hardcoded in this repository; they live inside the **audio-separator** dependency chain.

**CI and coverage:**
- **GitHub Actions** — `.github/workflows/tests.yml` runs on push/PR to `main` and `develop`, matrix Python 3.10–3.12 on `macos-latest`.
- **Codecov** — `codecov/codecov-action@v3` uploads `./coverage.xml` after pytest.

**Documentation / install references (user-facing links, not runtime SDKs):**
- Homebrew — Referenced for BlackHole and general install guidance (`core/blackhole_installer.py`, README).
- BlackHole wiki URL appears in user-facing strings (`core/blackhole_installer.py`).

## Data Storage

**Databases:**
- Not applicable — No SQL/NoSQL client or ORM in the codebase.

**File Storage:**
- Local filesystem only — Models under `resources/models` (see `config.py` `MODELS_DIR`), user outputs via `get_default_output_dir()` (e.g. `~/Music/StemSeparator/` on macOS), logs under `LOGS_DIR`, temp under `TEMP_DIR`.

**Caching:**
- Application-level caches (e.g. stretch cache in `core/stretch_cache.py`) on local disk; no external cache service.

## Authentication & Identity

**Auth Provider:**
- Not applicable — Desktop offline-first app; no OAuth, API keys, or cloud login in application code.

## Monitoring & Observability

**Error Tracking:**
- None integrated (e.g. no Sentry) — Logging via `utils/logger.py` to rotating log files under `LOGS_DIR` (`config.py` `LOG_FILE`, `LOG_MAX_BYTES`).

**Logs:**
- File-based application logs; optional console via colorlog.

## CI/CD & Deployment

**Hosting:**
- End users install the macOS app from GitHub Releases (per README); no server deployment in-repo.

**CI Pipeline:**
- GitHub Actions test job only (see `.github/workflows/tests.yml`); no automated release/deploy steps in the workflow file reviewed.

## Environment Configuration

**Required env vars:**
- None for normal GUI use. Optional/CLI: `STEMSEPARATOR_SUBPROCESS=1` to force separation worker mode (`main.py`). Bundled apps rely on `PATH` mutation for FFmpeg rather than env-based API keys.

**Secrets location:**
- Not applicable for runtime services. Repository may use GitHub secrets only for CI if extended later; not present in workflow snippet for tests beyond Codecov upload.

## Webhooks & Callbacks

**Incoming:**
- None — No HTTP server or webhook endpoints in this codebase.

**Outgoing:**
- None — No application-initiated webhooks. Network use is indirect (model downloads via libraries, CI to Codecov).

## Inter-process & local system integrations

**BeatNet beat-service:**
- **Local subprocess** — `utils/beat_service_client.py` launches the `beatnet-service` binary (JSON over stdin/stdout). Not a network service; communicates via process IPC only.

**Separation subprocess:**
- **Local subprocess** — `core/separator.py` spawns worker using `core/separation_subprocess.py` to isolate audio-separator resource usage; JSON over stdio (`main.py` worker path).

**macOS system audio:**
- **ScreenCaptureKit** / native capture paths in `core/screencapture_recorder.py` (platform-specific).
- **BlackHole** — Virtual audio device installed via Homebrew when needed (`core/blackhole_installer.py`).

**FFmpeg:**
- Expected on `PATH`; bundled under PyInstaller `bin/` for frozen builds (`main.py`, `core/separator.py`).

---

*Integration audit: 2026-04-01*
