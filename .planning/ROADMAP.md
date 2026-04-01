# Roadmap: StemSeparator (Windows port milestone)

## Overview

This roadmap delivers a **Windows port** with **bootstrap and path correctness**, a **PyInstaller onedir artifact**, **CUDA inference with CPU fallback and clear device UX**, **playback baseline on Windows audio**, **recording and system-capture parity (scope B)** with a published parity matrix, then **BeatNet packaging plus cross-platform CI, documentation, and manual test matrices** — following research dependency order: foundation and packaging before GPU validation, playback before capture, auxiliary services and quality last.

**Granularity:** standard (from `config.json`)  
**Mode:** yolo

## Phases

- [ ] **Phase 1: Bootstrap & Windows paths** — Single-instance, APPDATA/temp/models/logs, FFmpeg discovery, frozen `_MEIPASS` paths
- [ ] **Phase 2: Windows PyInstaller artifact (onedir)** — Spec, Qt/torch bundling, import order, VCRedist notes, clean-VM smoke
- [ ] **Phase 3: CUDA inference & device UX on Windows** — CPU and CUDA separation, subprocess IPC, device selection and fallback visibility
- [ ] **Phase 4: Playback & Windows audio I/O baseline** — Stem playback and graceful device/sample-rate behavior
- [ ] **Phase 5: Recording parity (scope B)** — Mic/line-in, WASAPI loopback, enumeration, parity matrix vs macOS
- [ ] **Phase 6: BeatNet service, CI & quality** — Packaged beatnet service, macOS CI preserved, Windows GHA job, docs and manual matrices

## Phase Details

### Phase 1: Bootstrap & Windows paths
**Goal**: The app starts and resolves assets on Windows the same way users expect — no Unix-only crashes, correct data directories, FFmpeg found, PyInstaller runs work.
**Depends on**: Nothing (first phase)
**Requirements**: WIN-01, WIN-02, WIN-03, WIN-04
**Success Criteria** (what must be TRUE):
  1. User can launch the application on Windows without crashes from Unix-only APIs (e.g. single-instance behavior works without `fcntl`).
  2. User data, temp, downloaded models, and logs land under Windows-appropriate locations (e.g. local app data) and long paths do not break core flows.
  3. Separation and I/O find a working **FFmpeg** on Windows in both dev and frozen layouts.
  4. Running from a **PyInstaller** build resolves bundled resources via frozen paths (e.g. `_MEIPASS`) without macOS-only bundle assumptions on critical code paths.
**Plans**: TBD

### Phase 2: Windows PyInstaller artifact (onedir)
**Goal**: Installers and power users get a **maintainable onedir** Windows build with Qt, native deps, and torch/CUDA collection story documented — not onefile; smoke-validated on a clean VM.
**Depends on**: Phase 1
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05
**Success Criteria** (what must be TRUE):
  1. Maintainer can produce a **PyInstaller onedir** Windows artifact from a checked-in spec (not onefile for Qt/torch).
  2. On a clean Windows environment, the packaged app **starts the UI** without missing Qt plugins or obvious native dependency gaps.
  3. **torch/torchaudio** and CUDA-related pieces are collected or explicitly documented so both CUDA-capable and CPU-only installs are supportable.
  4. **Import/startup order** is documented and verified so Qt/torch DLL issues are avoided on Windows.
  5. End-user **VCRedist** / runtime prerequisites are documented.
**Plans**: TBD
**UI hint**: yes

### Phase 3: CUDA inference & device UX on Windows
**Goal**: Users run separation on **CPU or NVIDIA CUDA** on Windows with **visible device choice** and **subprocess separation** that behaves like the product intent — no unexplained silent fallback.
**Depends on**: Phase 2
**Requirements**: INF-01, INF-02, INF-03, INF-04, INF-05
**Success Criteria** (what must be TRUE):
  1. User can run stem separation on **CPU** when CUDA is absent or selected.
  2. User can run separation on **NVIDIA CUDA** when drivers and the pinned PyTorch CUDA line match the documented matrix.
  3. **Device selection** in settings (or equivalent) lists what is available; failures or fallbacks are visible, not silently ignored.
  4. The **separation worker subprocess** JSON protocol works on Windows (paths, no-console flags where appropriate, working directory).
  5. **Retry/fallback** behavior matches the intended product behavior (aligned with existing device/error patterns).
**Plans**: TBD
**UI hint**: yes

### Phase 4: Playback & Windows audio I/O baseline
**Goal**: Users **hear stems** through normal Windows audio paths with sensible device listing and recovery when devices or sample rates change.
**Depends on**: Phase 3
**Requirements**: PLY-01, PLY-02
**Success Criteria** (what must be TRUE):
  1. User can **play back** separated stems on Windows using supported backends (device list includes expected outputs, default device works).
  2. When the audio device or sample rate changes, the app **fails or recovers gracefully** with user-actionable feedback where feasible.
**Plans**: TBD
**UI hint**: yes

### Phase 5: Recording parity (scope B)
**Goal**: Users capture **mic/line-in** and **system/endpoint loopback** on Windows with **realistic device selection** and a **published parity matrix** vs macOS (including documented OS limits).
**Depends on**: Phase 4
**Requirements**: REC-01, REC-02, REC-03, REC-04
**Success Criteria** (what must be TRUE):
  1. User can record from **microphone or line-in** on Windows; if blocked by privacy/permissions, errors are clear and actionable.
  2. User can capture **system / “what you hear”** audio via a **WASAPI-appropriate** implementation behind the same recorder abstraction.
  3. User can **enumerate and choose** capture devices in a way that matches Windows reality (including documenting quirks such as Bluetooth where needed).
  4. A **parity matrix** is available (macOS vs Windows): what matches, what differs, and why (including DRM/OS limits).
**Plans**: TBD
**UI hint**: yes

### Phase 6: BeatNet service, CI & quality
**Goal**: Beat grid features work with a **packaged Windows beatnet service**, **macOS CI stays green**, **Windows CI** runs CPU-level checks, and **docs plus manual matrices** support CUDA and recording validation.
**Depends on**: Phase 5
**Requirements**: SRV-01, SRV-02, QA-01, QA-02, QA-03, QA-04
**Success Criteria** (what must be TRUE):
  1. **beatnet_service** is packaged and discoverable on Windows; the client **JSON IPC** works end-to-end.
  2. **Service start/stop** lifecycle behaves correctly on Windows (validated win32 paths).
  3. **macOS** CI continues to pass; no regressions to the existing shipping path without an explicit decision.
  4. **GitHub Actions** includes a **Windows** job that exercises imports/smoke tests with **CPU** torch (no GPU assumed on runners).
  5. A **manual test checklist** covers CUDA hardware validation and recording scenarios.
  6. **Documentation** is updated for Windows install, CUDA install lines, and troubleshooting.
**Plans**: TBD

## Progress

**Execution order:** 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Bootstrap & Windows paths | 0/TBD | Not started | - |
| 2. Windows PyInstaller (onedir) | 0/TBD | Not started | - |
| 3. CUDA inference & device UX | 0/TBD | Not started | - |
| 4. Playback & audio I/O baseline | 0/TBD | Not started | - |
| 5. Recording parity (scope B) | 0/TBD | Not started | - |
| 6. BeatNet service, CI & quality | 0/TBD | Not started | - |

---
*Roadmap created: 2026-04-01 — aligned with `.planning/research/SUMMARY.md` phase structure.*
