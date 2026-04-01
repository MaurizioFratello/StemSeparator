# Technology Stack — Windows + CUDA Port (StemSeparator)

**Project:** StemSeparator  
**Scope:** Subsequent milestone — add Windows builds and CUDA inference to an existing PySide6 / PyTorch / audio-separator desktop app (do **not** replace the whole stack).  
**Researched:** 2026-04-01  
**Overall confidence:** **MEDIUM–HIGH** for packaging and PyTorch patterns; **MEDIUM** for exact CUDA wheel tag to pin (verify against [Get Started](https://pytorch.org/get-started/locally/) at release time).

---

## Recommended Stack

### Core runtime (unchanged from product direction)

| Technology | Version (align with repo) | Purpose | Why |
|------------|---------------------------|---------|-----|
| **Python** | **3.10–3.14** (match CI and macOS) | Interpreter | PyTorch officially supports this band on Windows; keep one Python minor across platforms to reduce drift. |
| **PySide6** | **6.10.x** (see `requirements.txt`) | Desktop UI | Official Qt for Python bindings; same major/minor as macOS avoids behavioral and asset differences. |
| **PyTorch** | **2.9.x** + matching **torchaudio** | Inference | Already pinned; Windows CUDA builds use PyTorch’s **extra index**, not vanilla PyPI, for GPU wheels. |
| **audio-separator** | **0.39.x** | Separation pipeline | Project constraint; stays atop torch/torchaudio — pin versions identically across OS builds. |
| **ONNX Runtime** | **1.23.x** (`onnxruntime` vs GPU extras) | ONNX paths | If GPU EP is needed on Windows, evaluate **`onnxruntime-gpu`** / provider packages separately from CPU-only wheel; avoid installing conflicting packages in the same env without checking upstream guidance. |

### Windows GPU / CPU install mechanics

| Piece | Standard approach | Rationale |
|-------|-------------------|-----------|
| **CUDA-enabled PyTorch** | `pip install torch torchaudio ... --index-url https://download.pytorch.org/whl/<cuTAG>` | Official distribution path; `<cuTAG>` is selected from the [PyTorch Get Started](https://pytorch.org/get-started/locally/) matrix (e.g. **cu128**, **cu126**, **cu118** — offerings change by release). |
| **CPU-only PyTorch** | `pip install torch torchaudio` from **PyPI** (no GPU index) | Smaller install; use for CPU-only CI, dev machines without NVIDIA, or a **CPU-only** shipped artifact. |
| **NVIDIA driver** | Recent **Game Ready / Studio** driver on end-user machines | PyTorch Windows wheels ship CUDA **runtime** pieces compatible with the build; users do **not** need the full CUDA Toolkit for inference. |
| **CPU fallback** | Same codebase; `torch.cuda.is_available()` / device manager | Table stakes; match existing `DeviceManager` behavior — no second framework. |

### Packaging and native assets

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **PyInstaller** | **≥ 6.0** (see `requirements-build.txt`) | Freeze app | Current major line; well trodden for Qt + large dependency trees on Windows. Prefer **onedir** for PyTorch + Qt size and DLL load behavior. |
| **FFmpeg** | **Windows static or shared build** (e.g. community “essentials” / BtbN-style builds) | Encode/decode / mux | No Python package replaces a tested `ffmpeg.exe` + bundled deps; mirror macOS spec pattern (`datas` / `bin`) with Windows paths and MinGW/VC++ runtime considerations for chosen build. |
| **MSVC runtime** | Matches toolchain used by Python and native wheels | DLL loading | Ensure installer or docs cover **VCRedist** if any bundled binary requires it (often already satisfied on modern Windows). |

### CI

| Technology | Role | Notes |
|------------|------|--------|
| **GitHub Actions** `windows-latest` | Build + test | Standard 2025–2026 default for Windows CI. |
| **CPU torch** in CI | pytest / import smoke | **Hosted runners typically have no NVIDIA GPU** — do not assert `torch.cuda.is_available()` in default CI; gate GPU tests behind labels or self-hosted runners. |
| **macOS workflow** | Keep existing | Project constraint: dual-platform maintenance. |

---

## Versions (pinning strategy)

- **Single source of truth:** Keep **`requirements.txt`** pins for PySide6, `audio-separator`, `torch`, `torchaudio`, numpy/scipy stack, pytest, etc., aligned across macOS and Windows **source** builds.
- **Split only where required:** Maintain optional files or CI steps, e.g. `requirements-windows-cuda.txt` or documented `pip install` lines that **only** override the PyTorch index for Windows CUDA installers — avoid duplicating unrelated pins.
- **PyTorch CUDA tag:** Pin **`cu128`** / **`cu126`** / etc. to the matrix row that matches **torch 2.9.x** on the [previous versions / get started](https://pytorch.org/get-started/locally/) pages at build time — the tag is release-specific.

---

## Rationale

1. **PyTorch on Windows is index-driven.** GPU wheels live under `download.pytorch.org`; installing `torch` from PyPI and expecting CUDA, or mixing indexes without care, is the primary class of environment bugs. CPU fallback is cleanly handled by a **CPU-only** install path.
2. **audio-separator** remains the separation layer — no rewrite — but its Windows story is only as good as **torch/torchaudio** and binary deps (FFmpeg, libs) you bundle or document.
3. **PySide6** on Windows is mainstream; PyInstaller 6’s hook ecosystem expects Qt — still validate plugins (multimedia, etc.) and platform plugins under `PySide6/plugins`.
4. **PyInstaller + large DL stacks:** Prefer **onedir**, explicit **`collect_all`** / hooks for `torch` when imports miss CUDA DLLs, and thorough smoke tests on a clean VM — onefile is usually a poor fit for this class of app.
5. **FFmpeg** is not “just another pip package” for production: vendor a known **Windows build** with license compliance (GPL vs LGPL build variants matter for distribution).
6. **CI honesty:** Automated Windows tests should assume **CPU** unless you provide GPU runners; CUDA validation stays manual or specialized infrastructure.

---

## What to avoid

| Avoid | Why |
|-------|-----|
| **Replacing PyTorch / audio-separator** “for Windows” | Out of scope; reintroduces validation and model risk. |
| **Implicit CUDA in CI** on hosted runners | Flaky or skipped tests; wrong signal. |
| **PyInstaller onefile** for full PyTorch + Qt apps | Slow startup, AV friction, extraction issues; harder DLL debugging. |
| **Mixing pip indexes** for `torch` without a clear documented recipe | Leads to CPU torch accidentally installed alongside CUDA expectations. |
| **Bundling random FFmpeg** without license review | GPL builds impose obligations; pick a deliberate build and document it. |
| **Assuming users install CUDA Toolkit** | Inference uses driver + PyTorch wheels; Toolkit is for **building** CUDA extensions, not typical end users. |
| **Divergent PySide6 / torch minor versions** across macOS vs Windows | Subtle UI and model bugs; keep pins synchronized unless a platform-specific hotfix is unavoidable. |

---

## Alternatives considered

| Instead of | Alternative | Why not (for this milestone) |
|------------|-------------|------------------------------|
| PyInstaller | cx_Freeze / Nuitka | PyInstaller already in repo and macOS path; switching adds migration cost. |
| CUDA from conda | pip + index URL | Project is pip-centric; keep one packaging story. |
| Shipping only CPU | — | Conflicts with CUDA + CPU fallback product goal for Windows. |

---

## Installation (illustrative — verify URLs at build time)

```bash
# Windows CPU dev / CI (example)
pip install -r requirements.txt

# Windows CUDA (example pattern — replace <cuTAG> per official matrix, e.g. cu128)
pip install torch==2.9.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/<cuTAG>
# Then install the rest without overriding torch from PyPI, or use a two-step requirements split.
pip install -r requirements.txt --no-deps  # only if you split deps carefully; prefer dedicated cuda requirements file
```

Use the exact commands from [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/) for **Windows + Pip + your CUDA version** — do not rely on stale command strings.

---

## Sources

- [PyTorch — Get Started (local installs)](https://pytorch.org/get-started/locally/) — **HIGH**
- [PyTorch 2.9 release blog](https://pytorch.org/blog/pytorch-2-9/) — CUDA 13 / wheel variant context — **HIGH**
- [PyTorch Windows notes (TDR, drivers)](https://docs.pytorch.org/docs/stable/notes/windows.html) — **HIGH**
- [PyInstaller — hooks, `collect_all`, binaries](https://github.com/pyinstaller/pyinstaller) — **HIGH**
- Repository: `requirements.txt`, `requirements-build.txt`, `packaging/*.spec` — **HIGH** (current pins)
