# Platform Parity Matrix (REC-04)

Which user-visible flows are identical across macOS, Windows and Linux, which
differ, and the OS reason for each difference. Linux is in scope by explicit
decision (`.planning/PORT_STATE.md`), beyond the macOS/Windows pair in
`REQUIREMENTS.md`.

Legend: **same** = identical code path and behaviour · **adapter** = same
feature, OS-specific backend behind `utils/platform_utils.py` · **manual** =
needs a user step that the OS forces.

## Separation and inference

| Flow | macOS | Windows | Linux | Notes |
|---|---|---|---|---|
| Demucs v4 (4s/6s) | same | same | same | Verified end to end on Linux: `demucs_4s` produced 4 stems. |
| MDX-Net / VR arch models (ONNX) | same | same | same | Needs the ONNX Runtime build with the intended execution provider; a CPU-only `onnxruntime` wheel reports the CPU provider and the worker says so instead of pretending. |
| Mel-Band / BS-RoFormer | same | same | same | Same ONNX caveat. |
| Ensemble (staged) | same | same | same | `ENSEMBLE_CONFIGS` is platform-independent. |
| CUDA inference | n/a | adapter | adapter | NVIDIA only; MPS on macOS. Both CUDA paths verified on real hardware here (12 s clip, preset `fast`: **2.61 s CUDA vs 4.47 s CPU**). |
| Apple Silicon MPS | adapter | n/a | n/a | macOS only, no Linux/Windows equivalent. |
| Visible CPU fallback | same | same | same | `set_device()` returns **False** plus `last_error` when the requested device is unavailable; the CPU retry is surfaced in the UI. There is no silent fallback. |
| Worker isolation | same | same | same | Separation runs in a child process with `spawn` start method on every OS, IPC via params/result JSON files (a `--noconsole` Windows build has no usable stdout pipe); stdout remains as fallback. |

## Playback (PLY-01/02)

| Flow | macOS | Windows | Linux | Notes |
|---|---|---|---|---|
| Stem playback, per-stem volume, loop | same | same | same | Mixing/position math stays at 44.1 kHz on all platforms. |
| Output device selection | adapter | adapter | adapter | PortAudio device **name** is persisted (`playback_device`), not the index: indices shift when USB/Bluetooth devices attach. Windows/Linux show the host API because the same speakers appear several times (16 outputs on the verification host). |
| Sample-rate mismatch | adapter | adapter | adapter | Endpoint may reject 44.1 kHz while reporting `default_samplerate == 44100` (typical WASAPI endpoint). The player probes candidate rates, resamples the buffer handed to PortAudio, and keeps 44.1 kHz internally. |
| Stale saved device | same | same | same | Falls back to the system default **with a visible warning**, never silently. |
| Transport state honesty | same | same | same | If the audio callback cannot start, `play()` raises/stops instead of entering PLAYING; the position clock does not advance on a dead stream. |

## Recording (REC-01..03)

| Flow | macOS | Windows | Linux | Notes |
|---|---|---|---|---|
| Microphone capture | same | same | same | `soundcard` on all three OSes. |
| System-audio loopback | **manual** | adapter | adapter | macOS needs a virtual device (BlackHole) — an OS limitation, no public API to tap another app's output; the installer card and helper live in the macOS-only branch of the settings dialog. Windows uses WASAPI loopback; Linux uses the PulseAudio/PipeWire `Monitor of …` sources, both without extra drivers, surfaced as `[System Audio]` entries. |
| Loopback discovery | same | same | same | Root cause of the original Linux/Windows gap: enumeration must pass `all_microphones(include_loopback=True)`; the default call hides exactly the devices system capture needs. |
| Backend selection | adapter | adapter | adapter | darwin → `blackhole`, win32 → `wasapi_loopback`, linux → `system_loopback`, chosen per OS with `INPUT_DEVICE` fallback; verified offline against a fake `soundcard`. |
| Failure guidance | adapter | adapter | adapter | `_recording_failure_help()` prints per-OS steps, including why `soundcard` failed to import when it does. |
| Metering | same | same | same | Verified with live capture on Linux: 3.00 s stereo from a PipeWire monitor, peak 0.96, level callback fired 64×. |

## Beat analysis (SRV-01/02)

| Flow | macOS | Windows | Linux | Notes |
|---|---|---|---|---|
| BeatNet service launch | adapter | adapter | adapter | Frozen binary or source-mode fallback; `.exe` suffix and `creationflags` handled in `utils/beat_service_client.py`. |
| Device policy | adapter | adapter | adapter | The client resolves the device through `core.device_manager` and passes an explicit `--device`; `mps` on a Linux/Windows box exits 1 with a `DeviceError` JSON instead of silently using CPU. |
| Termination | adapter | adapter | adapter | Process-group drain on POSIX, `taskkill` tree fallback on Windows; verified no orphans after client timeout and explicit stop. |
| Realtime microphone in the service | same | same | same | The `pyaudio` shim re-exports real PyAudio when the C extension loads and otherwise raises a named `RuntimeError` on `open()`; offline analysis is unaffected (`REALTIME_SUPPORTED=False`, reason recorded). Verified both tiers. |
| DeepRhythm BPM | same | same | same | Falls back to librosa with a loud warning when `deeprhythm`/`torchaudio` cannot load; measured 120.2 BPM on a 120 BPM click track. |

## Application shell and packaging

| Flow | macOS | Windows | Linux | Notes |
|---|---|---|---|---|
| Single-instance lock | same | same | same | `fcntl` on POSIX, `msvcrt.locking` on Windows; proven with two real processes. |
| User data / cache / music dirs | adapter | adapter | adapter | `platform_utils.user_data_dir()` / `user_cache_dir()` / `music_dir()`; writable `MODELS_DIR` with `MODEL_SEARCH_PATHS` for bundled + cache reads (writes always go to `MODELS_DIR`). |
| Bundled binaries (ffmpeg, PortAudio, rubberband) | adapter | adapter | adapter | `bundled_binary_dirs()` + `find_binary()`; Windows uses the `ffmpeg-master-latest-win64-gpl` directory layout. |
| Quit shortcut, file dialogs | adapter | adapter | adapter | `QKeySequence.Quit` role (not a hardcoded Cmd+Q); dialogs use `DontUseNativeDialog` consistently, so no OS-specific surprise. |
| macOS visual effects | adapter | n/a | n/a | Every entry in `ui/theme/macos_*` is gated by `is_macos()`; off-macOS builds get the flat theme, never a blurred/vibrant window. |
| Installer | `.app`/`.dmg` | Inno Setup `.exe` | onedir build | See `docs/PACKAGING.md`. |
| CUDA installation help | same | same | same | Both error strings link to `docs/PACKAGING.md## CUDA Installation`. |

## Deliberately not equal

- **BlackHole installer UI**: macOS only. Windows/Linux reach system audio without a driver, so showing that card elsewhere would be a lie; the settings dialog renders a "System Audio Capture" status card instead.
- **MPS**: macOS only. There is no MPS on other platforms, and no CPU fallback is hidden behind it.
- **Time-stretch engine order** is the same (CLI → pyrubberband → librosa) but which engines exist differs per OS; the module imports and degrades even when both optional libraries are missing, and the chosen engine is logged at INFO with every skip at WARNING.
- **Packaging artefacts** differ by OS by nature; the specs live side by side under `packaging/`.
