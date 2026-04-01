# Domain Pitfalls

**Domain:** PyTorch + PySide6 + audio on Windows (CUDA, DLLs, drivers) — porting from macOS Python audio apps  
**Researched:** 2026-04-01  
**Project context:** StemSeparator — Windows port with CUDA + CPU fallback, PyInstaller-style packaging, WASAPI/system capture (see `.planning/PROJECT.md`)

## Scope

This document focuses on mistakes teams commonly make when moving **macOS-first** Python desktop audio/ML apps to **Windows** with **NVIDIA CUDA** inference and a **Qt (PySide6)** UI. Confidence is **HIGH** where cited to official PyTorch/Qt docs or widely reproduced issue threads; **MEDIUM** for ecosystem patterns; **LOW** where only community reports exist.

---

## Critical Pitfalls

### Pitfall 1: Qt / PySide imported before PyTorch (DLL initialization order)

**What goes wrong:** On some Windows builds (reported with PyTorch 2.9+ and PyQt6/PySide-style stacks), importing the GUI toolkit **before** `torch` can trigger `WinError 1114` (“A dynamic link library (DLL) initialization routine failed”) or similar import failures. Root cause is load-order interaction between CRT/CUDA/Qt and bundled DLLs.

**Why it happens:** Windows resolves and initializes DLLs in import order; Qt and PyTorch both pull large native dependency chains.

**Consequences:** App fails at startup on Windows while identical code works on macOS; intermittent failures depending on entrypoint (frozen vs `python main.py`).

**Warning signs:**

- Failure only on Windows when launching the GUI entrypoint.
- Import succeeds in a REPL that imports `torch` first, but fails when the app imports widgets first.
- Stack trace mentions `DLL initialization` during `import torch` or right after UI imports.

**Prevention:**

- Establish a single startup module that **`import torch` (or a tiny shim that loads CUDA DLLs) before any PySide6/Qt** import, or document and enforce that order in `main.py` and PyInstaller boot paths.
- Smoke-test **frozen** Windows builds, not only dev installs.

**Suggested phase to address:** **Windows application build + CUDA inference path** — validate import order in the real packaged executable early; add an automated Windows smoke import test.

**Sources:** [PyTorch issue #166628](https://github.com/pytorch/pytorch/issues/166628) (PyQt6 + torch import order; same class of issue applies to Qt stacks on Windows). **Confidence:** MEDIUM (specific version matrix may vary; treat as mandatory validation on target PyTorch/Qt versions).

---

### Pitfall 2: Assuming PyInstaller “freezes” CUDA/cuDNN like Python files

**What goes wrong:** PyTorch loads many CUDA/cuDNN DLLs **dynamically**. PyInstaller’s static analysis often **does not** pull every runtime DLL into `dist/`, so the frozen app fails with missing DLL or load errors on machines that do not have matching CUDA/cuDNN on `PATH`.

**Why it happens:** Freezing tools trace Python imports, not every `LoadLibrary` path the CUDA stack uses at runtime.

**Consequences:** Dev machine works (CUDA in PATH); clean Windows VM fails; “works on my PC” reports.

**Warning signs:**

- `OSError`, `DLL load failed`, or missing `cudnn`, `cublas`, `cudart` when running the `.exe`.
- Same code runs with `python main.py` but not frozen.
- Differing behavior between conda env (many DLLs visible) and minimal venv.

**Prevention:**

- Treat CUDA runtime as an explicit **packaging** concern: use hooks such as `collect_dynamic_libs` for the active `torch`/CUDA env, **or** ship documented prerequisite (NVIDIA driver + matching PyTorch wheel index) and test without a full CUDA Toolkit install.
- Pin **one** PyTorch CUDA build (e.g. cu121 vs cu124) and test **GPU + CPU fallback** on a VM without developer toolchains.

**Suggested phase to address:** **Windows application build** (spec/hooks) and **CUDA inference path** (runtime matrix doc + CI or manual matrix).

**Sources:** PyInstaller discussions on bundling PyTorch/CUDA ([e.g. #8355, #8758](https://github.com/pyinstaller/pyinstaller/issues)); PyTorch Windows notes on runtime/DLL issues. **Confidence:** HIGH for “dynamic CUDA DLLs are easy to miss in freezes.”

---

### Pitfall 3: Mismatch between PyTorch wheel, driver, and optional system CUDA

**What goes wrong:** Teams install a **CUDA Toolkit** version or PATH order that **does not match** the PyTorch wheel’s bundled CUDA minor version, or users have an **old NVIDIA driver** that does not support the CUDA user-mode APIs the wheel expects.

**Why it happens:** On macOS, Metal/MPS path is different; on Windows, NVIDIA’s **driver** + **wheel** pairing is the real compatibility surface.

**Consequences:** `torch.cuda.is_available()` false though GPU present; cryptic kernel load errors; silent fallback to CPU that looks like “slow app.”

**Warning signs:**

- CUDA works in one venv but not another with “same” code.
- `nvidia-smi` shows GPU but PyTorch sees no CUDA.
- Errors mentioning unsupported PTX or driver version when launching inference.

**Prevention:**

- Publish a **single matrix**: supported Windows versions, **minimum NVIDIA driver**, and exact `pip` index URL / torch build used in releases.
- In-app: surface **device selection and last error** (from existing `DeviceManager` patterns) instead of silent CPU fallback.

**Suggested phase to address:** **CUDA inference path on Windows** — matrix + UX; **CPU fallback** — verify logging and tests when CUDA absent.

**Sources:** [PyTorch Get Started](https://pytorch.org/get-started/locally/) (wheel ↔ CUDA labels); NVIDIA driver/CUDA compatibility tables. **Confidence:** HIGH.

---

### Pitfall 4: Missing Visual C++ runtime / wrong NumPy BLAS on Windows

**What goes wrong:** PyTorch’s Windows FAQ calls out **missing VS redistributable** DLLs and **NumPy BLAS** mismatches (e.g. OpenBLAS vs MKL) causing import failures or subtle math/DLL conflicts.

**Why it happens:** Wheels do not bundle every MSVC runtime; scientific stacks stack multiple native linear algebra libraries.

**Consequences:** Import-time failures on clean machines; rare numerical or crash bugs.

**Warning signs:**

- Import errors referencing `VCRUNTIME`, `MSVCP140`, or similar on a fresh Windows install.
- Docs recommend `mkl`/`intel-openmp` stack for certain Windows setups.

**Prevention:**

- Installer or README: **Visual C++ Redistributable** prerequisite (version aligned with build toolchain).
- Pin NumPy/scipy stack in lockfiles; test **clean VM** installs.

**Suggested phase to address:** **Windows application build** (installer prerequisites); **Windows-focused testing** (clean VM checklist).

**Sources:** [PyTorch Windows notes — Import error / DLL](https://docs.pytorch.org/docs/stable/notes/windows.html) (Context7 excerpt from stable docs). **Confidence:** HIGH.

---

### Pitfall 5: PySide6 + PyInstaller without Qt plugin deployment on Windows

**What goes wrong:** Qt 6 often needs **platform plugins** (`platforms/`, image formats, etc.) beside the executable. PyInstaller may not copy everything; **onefile** mode is especially brittle for Qt.

**Why it happens:** Qt loads plugins by filesystem layout relative to `QCoreApplication` library paths; frozen layouts differ from `site-packages`.

**Consequences:** White window, “Could not find the Qt platform plugin windows”, missing icons, broken multimedia backends.

**Warning signs:**

- App runs from source, fails frozen.
- Logs mention `platforms/qwindows.dll` or plugin paths.
- Differences between `--onefile` and `--onedir` builds.

**Prevention:**

- Prefer **onedir** for Qt+heavy native deps; run **`windeployqt`** on the deployed Qt DLLs as [Qt for Python documents](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html), or equivalent explicit plugin copy in CI.
- Ensure PyInstaller uses the **venv’s** PySide6 (no shadowing system install — Qt doc warns picking wrong PySide6).

**Suggested phase to address:** **Windows application build** — repeatable plugin + DLL layout; document “no system PySide6” for release builds.

**Sources:** [Qt for Python & PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html). **Confidence:** HIGH for plugin/onefile caveats.

---

### Pitfall 6: Wrong DLL picked from `System32` vs bundle (“DLL search order”)

**What goes wrong:** Windows may load **OpenSSL**, **VC++**, or other DLLs from `System32` instead of the app folder, so the app uses **incompatible** versions.

**Why it happens:** Windows DLL search order and path hijacking differ from macOS `@rpath` behavior.

**Consequences:** Random SSL errors, Qt network failures, or crashes only on certain customer machines.

**Warning signs:**

- Issues referencing bundled vs system OpenSSL.
- PyInstaller issues about moving DLLs next to `.exe` to win load order.

**Prevention:**

- Pin known-good layouts; test on machines with aggressive security/AV and varied system DLLs.
- Follow bundler guidance for placing security-sensitive DLLs adjacent to the executable when required.

**Suggested phase to address:** **Windows application build** + **Windows-focused testing** (diverse consumer configs).

**Sources:** [PyInstaller #9381](https://github.com/pyinstaller/pyinstaller/issues/9381) (system vs bundled DLLs). **Confidence:** MEDIUM (case-dependent).

---

## Moderate Pitfalls

### Pitfall 7: Treating Windows audio like CoreAudio (device IDs, defaults, hotplug)

**What goes wrong:** macOS developers often rely on stable **CoreAudio** device semantics. On Windows, **WASAPI** device lists, **default sample rate**, and **exclusive/shared** modes differ; **PortAudio**/`sounddevice` device enumeration can be **stale** until reinit when devices change.

**Why it happens:** PortAudio abstracts WASAPI/WDM but exposes platform quirks; default rates may not update when the user changes Windows sound settings ([PortAudio discussion](https://github.com/PortAudio/portaudio/issues/682)).

**Consequences:** Wrong sample rate, open failure, or recording silence after USB interface reconnect.

**Warning signs:**

- Works once, fails after sleep/USB replug.
- `sounddevice.query_devices()` does not match Windows Sound control panel until restart.

**Prevention:**

- Re-query devices when opening streams; document **restart app** after device change if using PortAudio without hotplug refresh.
- Use [platform-specific `WasapiSettings`](https://python-sounddevice.readthedocs.io/en/latest/api/platform-specific-settings.html) when exclusive/shared behavior matters.

**Suggested phase to address:** **Feature parity (recording/playback)** — Windows audio QA; **Windows-focused testing**.

**Sources:** `python-sounddevice` platform-specific docs; PortAudio WASAPI issues. **Confidence:** MEDIUM–HIGH for “stale device list / sample rate surprises.”

---

### Pitfall 8: Expecting macOS-style “virtual cable” or ScreenCaptureKit parity

**What goes wrong:** macOS paths (BlackHole, ScreenCaptureKit) do not translate 1:1. Windows **system/loopback** capture usually involves **WASAPI loopback** (often exposed as special devices), **virtual audio drivers** (licensing/install UX), or third-party APIs — not the same code as CoreAudio taps.

**Why it happens:** Different OS security and audio driver models.

**Consequences:** Feature slips, support burden, “permission” confusion (also differs from macOS TCC).

**Warning signs:**

- Code still branches on macOS-only APIs (`fcntl`, ScreenCaptureKit helpers) without Windows implementation.
- Users expect loopback without installing anything — may be impossible without OS APIs or drivers.

**Prevention:**

- Explicit **Windows capture architecture** phase: choose WASAPI loopback vs virtual device vs documented limitation.
- Document **install steps** for any virtual audio driver (licensing, reboot, default device).

**Suggested phase to address:** **Feature parity (scope B)** — recording/system capture; **Out-of-scope** doc if a sub-mode is deferred.

**Sources:** Ecosystem patterns (PyAudioWPatch, `soundcard`, WASAPI docs). **Confidence:** MEDIUM for product-specific feasibility — validate in phase.

---

### Pitfall 9: Subprocess multiprocessing semantics (`spawn` vs `fork`)

**What goes wrong:** macOS/Linux developers may rely on **`fork`**-friendly patterns. Windows uses **`spawn`** for new interpreters — imports must be safe, guards (`if __name__ == "__main__"`) must be correct, and env inheritance differs.

**Why it happens:** StemSeparator already uses subprocess isolation for heavy work; Windows is stricter about pickling, cwd, and console.

**Consequences:** Hangs, double starts, or missing env vars in worker processes.

**Warning signs:**

- Separation subprocess works on macOS, fails on Windows with import or pickle errors.
- Workers missing `PATH` to find `ffmpeg` or CUDA.

**Prevention:**

- Audit all `multiprocessing` / `subprocess` entrypoints under Windows; pass explicit **env** and **paths** to children.
- CI: run critical subprocess tests on **Windows** runners where possible.

**Suggested phase to address:** **Cross-platform maintenance** — shared subprocess helpers; **Windows-focused testing**.

**Sources:** Python docs on `multiprocessing` start methods. **Confidence:** HIGH for general Windows vs Unix delta.

---

### Pitfall 10: Path assumptions (`/`, `os.path`, frozen `sys._MEIPASS`)

**What goes wrong:** macOS paths and PyInstaller `.app` layouts differ from Windows `Program Files`, spaces in paths, and `_MEIPASS` extraction.

**Why it happens:** Brownfield code with macOS-first `packaging/` assumptions.

**Consequences:** Model or FFmpeg not found, recorder helpers missing.

**Warning signs:**

- Hardcoded `/` or `Resources/` segments.
- Works unfrozen, fails under `_MEIPASS`.

**Prevention:**

- Centralize **resource resolution** (already partially in `config` / APPDATA patterns per PROJECT.md) and audit **all** asset loads for Windows + frozen.

**Suggested phase to address:** **Windows application build** — path audit; **Cross-platform maintenance**.

**Confidence:** HIGH for any PyInstaller app port.

---

## Minor Pitfalls

### Pitfall 11: FFmpeg binary name and console windows

**What goes wrong:** Subprocess calls to `ffmpeg` may spawn **console flashes** or fail if `ffmpeg.exe` is not on `PATH` or blocked by AV.

**Prevention:** Bundle FFmpeg next to app; use `CREATE_NO_WINDOW` flags on Windows subprocess where appropriate; test AV false positives.

**Suggested phase:** **Windows application build** / **Windows-focused testing**.

---

### Pitfall 12: Bluetooth / exclusive-mode latency surprises

**What goes wrong:** Bluetooth output devices on Windows add buffering; exclusive mode changes shared-mode mix behavior.

**Prevention:** Expose buffer size / device selection; document Bluetooth limitations.

**Suggested phase:** **Feature parity** — playback/recording UX.

---

## Phase-Specific Warnings (Roadmap Mapping)

| Topic | Likely pitfall | Mitigation | Suggested phase |
|-------|----------------|------------|-----------------|
| Packaged EXE | Missing CUDA/Qt/VC++ DLLs | Hooks, `windeployqt`, prereq installer | Windows application build |
| Startup | Qt before torch DLL init | Enforce import order; test frozen | CUDA inference + Windows build |
| GPU | Driver/wheel mismatch | Published matrix + in-app diagnostics | CUDA inference path |
| Clean install | MSVC runtime / NumPy BLAS | Prereqs + pinned deps | Windows build + testing |
| Recording | Loopback vs virtual device | Explicit Windows capture design | Feature parity (recording) |
| Audio I/O | WASAPI defaults / stale devices | Reinit, platform settings, QA | Feature parity + testing |
| Workers | `spawn` subprocess env | Audit isolation, PATH, cwd | Cross-platform + separation stack |

---

## Sources

- PyTorch Windows FAQ (import/DLL, MSVC, NumPy/MKL): https://docs.pytorch.org/docs/stable/notes/windows.html  
- Qt for Python — PyInstaller deployment (Qt 6 plugins, `windeployqt`, venv PySide6): https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html  
- python-sounddevice — platform-specific / WASAPI: https://python-sounddevice.readthedocs.io/en/latest/api/platform-specific-settings.html  
- PyTorch GitHub — PyQt6/torch DLL init (import order): https://github.com/pytorch/pytorch/issues/166628  
- PyInstaller — PyTorch/CUDA bundling discussions: https://github.com/pyinstaller/pyinstaller/issues/8355 , https://github.com/pyinstaller/pyinstaller/issues/8758  
- PortAudio — WASAPI default sample rate / device list: https://github.com/PortAudio/portaudio/issues/682  

---

## Gaps / LOW Confidence

- Exact **PySide6 version × PyTorch version × MSVC** combination for StemSeparator should be validated on hardware; do not rely on a single GitHub issue for all matrices.  
- **WASAPI loopback** implementation choice (stdlib vs PortAudio vs PyAudioWPatch vs native) needs phase-specific prototyping — ecosystem guidance varies by latency and license.
