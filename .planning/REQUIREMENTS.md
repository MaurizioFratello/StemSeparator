# Requirements: StemSeparator (Windows port milestone)

**Defined:** 2026-04-01  
**Core Value:** Reliable stem separation and playback in one desktop app — Windows users get CUDA when available and safe CPU fallback; recording and capture parity with macOS (scope B) where the OS allows.

## v1 Requirements

### Windows bootstrap and paths

- [ ] **WIN-01**: Application starts on Windows without Unix-only APIs (`fcntl` single-instance replaced or equivalent; no crash on import).
- [ ] **WIN-02**: User data, temp, models, and logs resolve under Windows conventions (`APPDATA`/local app data, long paths handled).
- [ ] **WIN-03**: Bundled or configured **FFmpeg** is discovered on Windows for separation and I/O (consistent with frozen layout).
- [ ] **WIN-04**: Resource paths work under **PyInstaller** frozen runs (`sys._MEIPASS`, no hardcoded macOS bundle paths in critical paths).

### Packaging (Windows artifact)

- [ ] **PKG-01**: **PyInstaller** produces a maintainable **onedir** Windows build (spec checked in; not onefile for Qt/torch).
- [ ] **PKG-02**: Required **Qt plugins** and native deps deploy with the app; smoke test launches UI on a clean Windows VM.
- [ ] **PKG-03**: **torch/torchaudio** and CUDA-related DLLs are collected or documented such that CUDA and CPU-only installs are both supportable.
- [ ] **PKG-04**: **Import order** and startup path documented and verified (avoid Qt-before-torch DLL failures on Windows).
- [ ] **PKG-05**: **VCRedist** / runtime prerequisites documented for end users.

### Inference (CUDA and CPU)

- [ ] **INF-01**: User can run separation on **CPU** on Windows when CUDA is absent or selected.
- [ ] **INF-02**: User can run separation on **NVIDIA CUDA** when drivers and the pinned **PyTorch CUDA** wheel line match the published matrix.
- [ ] **INF-03**: **Device selection** in settings (or equivalent) reflects available devices; errors are visible (no silent perpetual fallback without explanation).
- [ ] **INF-04**: **Separation subprocess** JSON protocol works on Windows (paths, `CREATE_NO_WINDOW` or equivalent, working directory).
- [ ] **INF-05**: **Retry/fallback** behavior matches product intent (aligned with `DeviceManager` / `ErrorHandler` patterns).

### Playback and monitoring (Windows)

- [ ] **PLY-01**: Stem **playback** works on Windows through supported audio backends (device list, default device).
- [ ] **PLY-02**: Sample-rate / device changes fail gracefully with user-actionable behavior where feasible.

### Recording and capture (parity scope B)

- [ ] **REC-01**: User can capture **microphone or line-in** on Windows with clear privacy/permission errors when blocked.
- [ ] **REC-02**: User can capture **system / endpoint loopback** (“what you hear”) via **WASAPI**-appropriate implementation behind the `Recorder` abstraction.
- [ ] **REC-03**: **Device enumeration and selection** for capture matches Windows reality (multiple endpoints, Bluetooth quirks documented).
- [ ] **REC-04**: **Parity matrix** published (macOS vs Windows): which flows match, which differ, and why (OS limits, DRM, etc.).

### BeatNet and auxiliary services

- [ ] **SRV-01**: **beatnet_service** (or equivalent) is packaged and locatable on Windows; client JSON IPC works.
- [ ] **SRV-02**: Process lifecycle (start/stop) behaves on Windows (`win32` branches validated).

### Quality, CI, and maintenance

- [ ] **QA-01**: **macOS** CI still passes; no regressions to existing shipping path without explicit decision.
- [ ] **QA-02**: **GitHub Actions** includes a **Windows** job exercising imports/smoke tests with **CPU** torch (GPU not assumed on runners).
- [ ] **QA-03**: **Manual test checklist** documents CUDA hardware validation and recording scenarios.
- [ ] **QA-04**: **Documentation** updated for Windows install, CUDA install lines, and troubleshooting.

## v2 Requirements

### Audio / capture

- **CAP-01**: **Process-scoped loopback** (per-app audio capture) on supported Windows builds — deferred until endpoint loopback and core parity are solid.

### Platform

- **PLT-01**: **Linux** as a primary desktop target — out of this milestone’s core scope.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cloud-hosted separation API | Local-first desktop product |
| Replacing **audio-separator** / core model stack | Port milestone; migrations are separate decisions |
| DRM bypass or violating platform audio policies | Legal and policy compliance |

## Traceability

Which phases cover which requirements — filled when roadmap is created.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WIN-01 — WIN-04 | TBD | Pending |
| PKG-01 — PKG-05 | TBD | Pending |
| INF-01 — INF-05 | TBD | Pending |
| PLY-01 — PLY-02 | TBD | Pending |
| REC-01 — REC-04 | TBD | Pending |
| SRV-01 — SRV-02 | TBD | Pending |
| QA-01 — QA-04 | TBD | Pending |

**Coverage:**

- v1 requirements: **24** total  
- Mapped to phases: **pending roadmap**  
- Unmapped: **24** until roadmap step completes

---
*Requirements defined: 2026-04-01*  
*Last updated: 2026-04-01 after research synthesis*
