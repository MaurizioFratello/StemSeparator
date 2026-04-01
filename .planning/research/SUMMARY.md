# Project Research Summary

**Project:** StemSeparator  
**Domain:** Cross-platform desktop stem separation (Python / PySide6 / PyTorch / audio-separator) — **Windows port** with CUDA inference, CPU fallback, and macOS feature parity (including recording).  
**Researched:** 2026-04-01  
**Confidence:** **MEDIUM–HIGH** (stack and pitfalls well sourced; Windows capture implementation choice needs phase-level validation)

## Executive Summary

StemSeparator is a **brownfield PySide6 desktop app** that already ships on macOS with chunked separation via **audio-separator**, subprocess-isolated inference, playback, time-stretch, i18n, and macOS recording (ScreenCaptureKit / BlackHole). Experts extend this class of product by **keeping one stack** (Python pins, PyTorch index discipline, PyInstaller onedir) and adding **platform shims** behind the same abstractions (`DeviceManager`, `Separator` + JSON IPC worker, `Recorder` backends) rather than forking core logic.

The recommended approach for this milestone is: **(1)** fix Windows-only bootstrap (single-instance lock replacing `fcntl`, frozen resource paths), **(2)** ship a **PyInstaller onedir** artifact with explicit CUDA/Qt/VC++ handling and **torch-before-Qt** import order, **(3)** validate **CUDA wheels from PyTorch’s extra index** plus documented driver matrix and in-app device clarity, **(4)** implement **WASAPI-oriented recording** (endpoint loopback + input) behind the existing `Recorder` API, and **(5)** package **BeatNet** and expand CI with honest **CPU-only** automation plus documented GPU/manual matrices.

Key risks are **DLL load order** (Qt vs torch), **incomplete freezing of dynamic CUDA DLLs**, **driver/wheel mismatch**, and **audio API mismatch** (CoreAudio assumptions vs WASAPI). Mitigations: enforce import order and smoke-test frozen builds early; treat CUDA as an explicit packaging concern with `collect_dynamic_libs`/hooks and clean-VM tests; publish a single support matrix; implement recording in dedicated backends with a documented parity scope matrix and defer process-scoped loopback until baseline loopback is solid.

## Key Findings

### Recommended Stack

Keep the existing product stack; **do not** replace PyTorch or audio-separator. On Windows, **CUDA-enabled PyTorch** must be installed via **`pip` + `https://download.pytorch.org/whl/<cuTAG>`** (tag pinned at release from the official matrix — e.g. cu128/cu126 — matching torch 2.9.x). **CPU-only** installs use vanilla PyPI for torch/torchaudio. **PyInstaller ≥ 6**, **onedir** (not onefile) for Qt + large native trees. Bundle a **known Windows FFmpeg** build with license clarity (GPL vs LGPL). **GitHub Actions `windows-latest`** for CI; assume **CPU torch** on hosted runners — gate GPU tests. Align **PySide6 6.10.x**, **torch/torchaudio 2.9.x**, and **audio-separator 0.39.x** across macOS and Windows source builds; split only a minimal `requirements-windows-cuda.txt` (or documented install lines) for the torch index override.

**Core technologies:**
- **Python 3.10–3.14** (match CI) — single minor across platforms reduces drift.
- **PyTorch 2.9.x + torchaudio** — inference; Windows GPU via PyTorch extra index, not mixed-index accidents.
- **audio-separator 0.39.x** — separation pipeline; unchanged layer.
- **PyInstaller ≥ 6 (onedir)** — frozen app; hooks/collect for torch/CUDA and Qt plugins.
- **FFmpeg (Windows build)** — encode/decode; vendor beside app like macOS `datas`/`bin` pattern.
- **ONNX Runtime 1.23.x** — only if ONNX paths need GPU EP on Windows; avoid conflicting CPU/GPU wheel installs without upstream guidance.

### Expected Features

**Must have (table stakes):**
- **WASAPI shared-mode playback and capture** — default Windows audio path; exclusive mode incompatible with classic loopback per Microsoft.
- **Endpoint loopback (“system mix”)** — `AUDCLNT_STREAMFLAGS_LOOPBACK` on the render endpoint; device selection so loopback matches what the user hears.
- **Microphone / line-in capture** — distinct from loopback; standard musician workflow.
- **Device enumeration and user selection** — multiple outputs are normal on Windows.
- **Format / sample-rate handling** — avoid silent pitch/speed errors or failed opens.
- **Windows privacy UX for microphone** — actionable errors and links to Settings.
- **Separation with CUDA when available and stable CPU fallback** — no corrupt output; aligned with `DeviceManager` / retry patterns.
- **Export and preview of stems** — core product promise.

**Should have (competitive):**
- **High-quality separation and CUDA + graceful CPU fallback** — speed vs accessibility.
- **Time-stretch, loops, beat workflows** — macOS-validated depth.
- **Polished PySide6 UI and i18n** — professional desktop bar.
- **Application / process-scoped loopback** (optional tier) — stronger when it works (Windows 10 build **20348+**); not the same as endpoint loopback; narrower OS floor.

**Defer (v2+ or stretch):**
- **Process-scoped loopback** as launch blocker — defer until endpoint loopback and device/format UX are solid; roadmap may promote if prioritized.

### Architecture Approach

**Do not** duplicate `Separator` or subprocess protocol for Windows. Keep **AppContext → core services**: `DeviceManager` (**CUDA > CPU** on Windows; MPS absent), **Separator** + **stdin/stdout JSON** worker with same `cwd`/IPC, **Recorder** with **new Windows backends** (WASAPI loopback, optional virtual-cable path) behind the same public API. Replace **Unix-only single-instance** (`fcntl`) in `main.py` with a Windows implementation (`QLocalServer` / named mutex / lock file). Package **beatnet_service** as **`beatnet_service.exe`** with path resolution parallel to macOS; `_terminate_process` already branches for win32. Centralize resource resolution for **`sys._MEIPASS`**, `%TEMP%`, and long paths.

**Major components:**
1. **`DeviceManager`** — PyTorch device probe/selection; same class, platform-aware priority.
2. **`Separator` + separation subprocess** — identical JSON IPC; OS-specific process flags only (`CREATE_NO_WINDOW`, no Dock env).
3. **`Recorder`** — strategy/backends for WASAPI loopback + input; optional virtual device installer UX (mirror BlackHole pattern).
4. **Bootstrap (`main.py`)** — Windows single-instance + FFmpeg PATH + frozen layout.
5. **Packaging** — PyInstaller spec, `bin/`, models, BeatNet binary; no ScreenCaptureKit on Windows.

### Critical Pitfalls

1. **Qt/PySide imported before PyTorch** — can cause `WinError 1114` / DLL init failures on Windows; **load torch (or a thin shim) before any Qt import** in `main.py` and frozen entry; smoke-test packaged EXE.
2. **PyInstaller missing dynamic CUDA/cuDNN DLLs** — use hooks / `collect_dynamic_libs`, test on clean VMs without dev CUDA on PATH; pin one CUDA wheel line and document prerequisites.
3. **PyTorch wheel vs NVIDIA driver mismatch** — publish minimum driver + exact pip index; surface device choice and errors in-app, not silent slow CPU.
4. **Missing VC++ runtime / NumPy BLAS conflicts** — document VCRedist; pin numpy/scipy; test clean installs.
5. **Qt plugins not deployed with PyInstaller** — prefer onedir; `windeployqt` or explicit plugin copy; ensure venv PySide6 is what gets bundled.
6. **WASAPI vs CoreAudio assumptions** — re-query devices; stale PortAudio lists after hotplug; document Bluetooth/exclusive-mode limits.
7. **Windows `spawn` and subprocess env** — audit PATH, `cwd`, and guards for workers vs macOS `fork` habits.
8. **Path and `_MEIPASS` assumptions** — audit hardcoded `/` and `Resources/`; centralize resolution.

## Implications for Roadmap

Suggested phase structure follows dependency order: **bootstrap and packaging before GPU validation before recording polish**.

### Phase 1: Bootstrap & Windows paths
**Rationale:** Unblocks a reliable single instance and correct asset resolution on Windows before heavy feature work.  
**Delivers:** Windows single-instance lock; audited `USER_DIR` / frozen paths; FFmpeg discovery consistent with packaging.  
**Addresses:** Cross-platform maintenance; foundation for scope B.  
**Avoids:** Pitfall 10 (paths), partial macOS-only locks.

### Phase 2: Windows PyInstaller artifact (onedir)
**Rationale:** Proves frozen layout for workers, Qt, and bundled `bin/`; core packaging risk container.  
**Delivers:** Windows `.spec`, onedir output, bundled FFmpeg and assets mirroring macOS patterns; plugin/DLL layout; optional VCRedist notes.  
**Uses:** PyInstaller ≥ 6, FFmpeg Windows build choice with license review.  
**Avoids:** Pitfalls 2, 5, 6 (CUDA/Qt DLLs, plugins, DLL search); onefile anti-pattern from STACK.

### Phase 3: CUDA inference path & device UX on Windows
**Rationale:** Product goal is NVIDIA acceleration with CPU fallback; matrix and UX must be explicit.  
**Delivers:** Documented `cuTAG` + install lines; `DeviceManager` validation on real hardware; separation subprocess E2E on Windows (CUDA + CPU); logging when falling back.  
**Addresses:** Table stakes separation + CUDA/CPU; PROJECT.md active requirements.  
**Avoids:** Pitfalls 1 (import order — validate in this phase with frozen smoke), 3, 4.

### Phase 4: Playback & Windows audio I/O baseline
**Rationale:** Table-stakes monitoring before complex capture.  
**Delivers:** Confirmed `sounddevice`/PortAudio playback paths on Windows; buffer/device UX; reinit on device change where feasible.  
**Avoids:** Pitfall 7 (stale devices, sample rates).

### Phase 5: Recording parity (scope B)
**Rationale:** PROJECT.md requires recording/system capture on Windows with documented gaps.  
**Delivers:** WASAPI endpoint loopback + input capture behind `Recorder`; device selection; privacy UX; optional virtual-cable fallback with installer/detect pattern; **parity matrix** (what matches macOS, what degrades).  
**Addresses:** FEATURES table stakes and MVP priorities; defer process-scoped loopback unless roadmap pulls it in.  
**Avoids:** Pitfall 8 (assuming macOS APIs); Stereo Mix–only paths; DRM circumvention marketing.

### Phase 6: BeatNet service, CI, and test matrix
**Rationale:** Beat grid features depend on packaged service; quality depends on Windows CI and documented manual GPU/recording tests.  
**Delivers:** `beatnet_service.exe` packaging; `beat_service_client` resolution; GHA Windows job for import/smoke/subprocess tests (CPU torch); manual checklist for CUDA/recording.  
**Avoids:** Pitfall 9 (subprocess on Windows); implicit GPU in default CI (STACK).

### Phase Ordering Rationale

- **Packaging and inference** before **full recording parity** reduces rework when DLLs or import order fail in the frozen EXE.  
- **Recording** depends on stable playback/device enumeration patterns.  
- **BeatNet** and **CI** close the loop on isolated binaries and cross-platform maintenance without blocking core separation deliverables.

### Research Flags

Phases likely needing deeper research during planning:
- **Recording parity (Phase 5):** WASAPI implementation choice (stdlib vs PortAudio vs specialized libraries) — ecosystem and latency/license tradeoffs; Microsoft process-loopback sample if pursuing stretch tier.
- **CUDA packaging (Phase 2–3):** Exact PyInstaller hooks for the pinned torch/CUDA line — validate on clean VMs.

Phases with standard patterns (lighter research):
- **Bootstrap/path audit (Phase 1):** Well-trodden porting patterns; map to existing `config`/APP DATA usage.
- **DeviceManager priority (Phase 3):** Code already encodes MPS > CUDA > CPU; Windows is mostly validation and UX.
- **Subprocess JSON separation:** Contract already OS-agnostic; Windows-specific flags only.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM–HIGH | PyTorch/Qt/PyInstaller docs and repo pins; **cuTAG** must be verified at release from get-started matrix. |
| Features | MEDIUM–HIGH | Microsoft Learn for loopback; market table stakes partly synthesized. |
| Architecture | HIGH | Aligns with `.planning/codebase/ARCHITECTURE.md` and cited core modules. |
| Pitfalls | MEDIUM–HIGH | Official docs + common PyInstaller/CUDA issues; import-order issue version-specific — validate on target stack. |

**Overall confidence:** **MEDIUM–HIGH**

### Gaps to Address

- **Exact PySide6 × PyTorch × MSVC matrix** — validate on target hardware; do not rely on a single GitHub issue for all combinations.
- **WASAPI loopback implementation library** — prototype in a dedicated planning/implementation slice; sounddevice alone is insufficient for “system audio” without explicit backend design.
- **Process-scoped loopback** — OS build floor (20348+) and app compatibility; treat as optional until baseline is shipped.

## Sources

### Primary (HIGH confidence)
- [PyTorch — Get Started (local installs)](https://pytorch.org/get-started/locally/) — Windows pip + CUDA index, wheel tags.
- [PyTorch — Windows notes](https://docs.pytorch.org/docs/stable/notes/windows.html) — DLL import, VCRedist, drivers.
- [Qt for Python — PyInstaller deployment](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html) — plugins, `windeployqt`, venv PySide6.
- [Microsoft Learn — Loopback Recording (WASAPI)](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording) — loopback flags, shared mode, DRM note.
- Repository: `requirements.txt`, `requirements-build.txt`, `packaging/*.spec` — current pins and packaging ground truth.
- `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` — full research detail.
- `.planning/PROJECT.md` — scope, active requirements, constraints.

### Secondary (MEDIUM confidence)
- [PyInstaller — PyTorch/CUDA bundling discussions](https://github.com/pyinstaller/pyinstaller/issues) — dynamic library collection patterns.
- [PyTorch issue #166628](https://github.com/pytorch/pytorch/issues/166628) — Qt/torch import order on Windows (validate for PySide6 stack).
- PortAudio / python-sounddevice — WASAPI device list and sample-rate quirks.

### Tertiary (LOW confidence / validate in phase)
- Per-machine AV and DLL search-order edge cases — test diverse consumer configs.

---
*Research completed: 2026-04-01*  
*Ready for roadmap: yes*
