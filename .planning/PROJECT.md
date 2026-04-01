# StemSeparator

## What This Is

**StemSeparator** is a desktop application for musicians and producers: it separates mixed audio into stems (vocals, drums, bass, etc.), previews and exports results, supports looping and time-stretch workflows, and records system or input audio on macOS using native integration. The codebase is a **Python** app with a **PySide6** UI, a **PyTorch** / **audio-separator** separation pipeline (including subprocess isolation for heavy work), and **macOS-focused packaging** (PyInstaller, DMG, bundled helpers such as BeatNet).

This planning cycle targets a **Windows port** that preserves **feature parity with macOS**, including **recording and system-audio capture** on Windows where technically feasible, while adding **CUDA GPU acceleration** for inference with a **CPU fallback**.

## Core Value

**Reliable stem separation and playback in one desktop app** — users can go from a file or live capture to separated stems and usable exports without leaving the tool; on Windows, GPU acceleration should be used when available without blocking users on CPU-only systems.

## Requirements

### Validated

- ✓ **Single-app stem separation** — Chunked and whole-file separation via `audio-separator`, ensemble paths, model registry and downloads (`core/separator.py`, `core/ensemble_separator.py`, `core/model_manager.py`) — existing
- ✓ **GPU/CPU device selection** — `DeviceManager` and retry/fallback strategies (`core/device_manager.py`, `config.RETRY_STRATEGIES`) — existing
- ✓ **PySide6 desktop UI** — Main window, queue, player, settings, themed UI (`ui/`, `main.py`) — existing
- ✓ **Playback and monitoring** — `AudioPlayer`, stem mixing, sounddevice-backed output (`core/player.py`, `ui/widgets/player_widget.py`) — existing
- ✓ **Time-stretch and loop export** — Rubber Band–based stretch, loop export flows (`core/time_stretcher.py`, export widgets) — existing
- ✓ **Internationalization** — JSON translations (`resources/translations/`, `utils/i18n.py`) — existing
- ✓ **macOS packaging** — PyInstaller specs, DMG, bundled FFmpeg and helpers (`packaging/`) — existing
- ✓ **macOS system audio recording** — Recorder stack with ScreenCaptureKit / BlackHole paths (`core/recorder.py`, related utils) — existing
- ✓ **Beat grid / BeatNet** — Isolated beatnet-service and client (`packaging/beatnet_service/`, `utils/beat_service_client.py`) — existing
- ✓ **Test suite** — pytest, pytest-qt, CI on macOS (`.github/workflows/tests.yml`) — existing

### Active

- [ ] **Windows application build** — Installable/runnable Windows artifact (e.g. PyInstaller or equivalent), documented prerequisites, FFmpeg and assets bundled or clearly provisioned.
- [ ] **CUDA inference path on Windows** — PyTorch/audio-separator stack runs on NVIDIA GPUs when drivers and CUDA-enabled wheels match; user-visible device selection consistent with macOS behavior.
- [ ] **CPU fallback** — When CUDA is unavailable or fails, separation and related ML paths complete on CPU without silent data loss; clear behavior in settings or logs.
- [ ] **Feature parity (scope B)** — Core GUI flows (upload, queue, separate, play, export, loops, time-stretch, settings) behave on Windows comparably to macOS; **recording and system-audio capture** are implemented on Windows using appropriate APIs/drivers (WASAPI loopback, virtual devices, or other chosen stack), with gaps documented if OS limits apply.
- [ ] **Cross-platform maintenance** — Changes preserve existing **macOS** builds and CI; shared code paths avoid platform regressions.
- [ ] **Windows-focused testing** — Automated or documented manual tests for separation, devices, and recording on Windows targets.

### Out of Scope

- **Linux as a primary release target** — Unless needed for CI only; not the product focus of this milestone.
- **Cloud / SaaS separation backend** — Local-first desktop scope remains.
- **Rewriting the separation engine** — Keep audio-separator / existing model stack unless a phase explicitly migrates.

## Context

- Brownfield codebase: see `.planning/codebase/` (STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, INTEGRATIONS, CONCERNS).
- `config.py` already considers Windows paths in places (e.g. `APPDATA` for user dir when frozen); full port requires auditing **all** macOS-only branches (`fcntl`, ScreenCaptureKit, BlackHole, dmg tooling, etc.).
- BeatNet and other **isolated subprocess** components may need Windows equivalents or repackaging.

## Constraints

- **Tech stack**: Python, PySide6, PyTorch, audio-separator — align CUDA/PyTorch builds with supported NVIDIA/CUDA matrix for Windows.
- **Dual platform**: No breaking macOS shipping path; use conditional platform code and CI for both targets where feasible.
- **Licensing**: Respect licenses of bundled binaries (FFmpeg, models, virtual audio drivers on Windows).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Windows port with **feature parity (B)** including recording/capture | User choice: match macOS breadth on Windows | — Pending |
| **CUDA + CPU fallback** for inference | Performance on NVIDIA hardware; accessibility without GPU | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):

1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):

1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after initialization (scope: Windows port, CUDA + CPU fallback, macOS feature parity including recording)*
