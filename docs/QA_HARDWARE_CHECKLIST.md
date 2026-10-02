# Manual Hardware / Cross-Platform Test Checklist (QA-03)

CI covers CPU-only inference on three OSes; it cannot prove anything about real
GPUs, audio hardware or system-audio capture. Work through this list on each
platform you ship, with the app built from `docs/PACKAGING.md`. Record the
observed numbers — a tick without an observation is not evidence.

App version / commit: ________________  Operator: ________  Date: ________

## 0. Both GPU checks (run before and after any torch/onnx pin change)

- [ ] `nvidia-smi` (Windows: `nvidia-smi` in PowerShell) reports the driver and at least one GPU.
- [ ] In the venv/build: `python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"` prints a CUDA build and the device name.
- [ ] App menu → Settings → Compute device: choose **CUDA GPU**, run a separation, and confirm the worker log contains
      `Device enforced: torch=cuda` (grep the log file printed at start-up by `main.py`).
- [ ] Choose **CPU** and repeat: log must contain `Device enforced: torch=cpu`.
      This is the check that the setting really drives the worker — the original
      defect accepted the device and ignored it.
- [ ] Unplug/disable the GPU (or set `CUDA_VISIBLE_DEVICES=""`) and request CUDA in Settings: the app must
      **fail visibly** — a message naming the device and the reason, plus the offered CPU retry —
      and must not quietly switch to CPU while reporting GPU.
      Expected helper text links to `docs/PACKAGING.md## CUDA Installation`.
- [ ] Timing sanity: same clip, same preset (`fast`), GPU vs CPU. GPU must be
      clearly faster. Reference measurement (Linux, 12 s clip, demucs_4s):
      CUDA 2.61 s, CPU 4.47 s. Record yours: GPU ______ s, CPU ______ s.
- [ ] ONNX models (MDX-Net / BS-RoFormer): with the CUDA build of ONNX Runtime
      installed, the log shows a CUDA execution provider; with the CPU wheel it
      shows `['CPUExecutionProvider']` and the UI still completes the job.

## 1. macOS (Apple Silicon and Intel if available)

- [ ] MPS device selectable and enforced (`Device enforced: torch=mps`).
- [ ] BlackHole card in Settings appears **only** here; install/verify buttons work.
- [ ] System-audio recording via BlackHole: meter moves, file has non-silent audio.
- [ ] ScreenCaptureKit path on the current macOS release (manual probe, see `docs/SCREENCAPTURE_INTEGRATION.md`).
- [ ] `.app` launches from a copy in `/Applications` with no Terminal involved; first run downloads nothing that was bundled.

## 2. Windows

- [ ] Installed build (Inno Setup) and portable onedir both start; no console window appears (that is why worker IPC is file-based).
- [ ] Settings → Output device: list shows the speakers **with their host API**; pick a non-default one, play, confirm sound comes from it, restart the app and confirm the choice persisted.
- [ ] Unplug the selected output device mid-session: playback must not pretend to run — expect a stopped transport and a visible message; the app recovers to the system default with a warning after a re-scan.
- [ ] WASAPI endpoint that rejects 44.1 kHz (common on consumer laptops): playback still works (candidate-rate probing + resample). Verify by listening, not by logs.
- [ ] System-audio recording: the `[System Audio]` entry appears without installing any driver; capture 10 s of music and confirm the waveform is non-silent.
- [ ] Microphone recording works with the input device chosen by name.
- [ ] Bundled `ffmpeg` is found (`packaging/vendor/windows/bin`, `ffmpeg-master-latest-win64-gpl` layout): MP3/M4A import succeeds on a machine without ffmpeg on PATH.
- [ ] Loop export with time stretching succeeds; `rubberband` CLI used when shipped, otherwise the fallback engine is named in the log.
- [ ] Beat analysis: `beatnet-service.exe` starts, returns a tempo for a click track, and `tasklist` shows no leftover process after the app exits or the analysis is cancelled.
- [ ] Kill the app from Task Manager while a separation runs, then restart: the single-instance lock is not stuck and no orphan worker survives.

## 3. Linux

- [ ] Starts on a stock desktop session (X11 **and** Wayland) without env tweaks; `QT_QPA_PLATFORM=offscreen` is only for headless checks.
- [ ] `libportaudio` is present (`ldconfig -p | grep portaudio`) or bundled via `packaging/vendor/linux`; otherwise sounddevice/recorder report the reason instead of failing silently.
- [ ] PipeWire and PulseAudio backend both exercised if available: system-audio list shows `Monitor of …` entries; capture 5 s and confirm peak > 0 (`soundfile` read of the WAV is enough).
- [ ] Output device picker shows ALSA + Pulse duplicates distinguished by host API; selection persists across restarts (`playback_device` in `user_settings.json`).
- [ ] `rubberband` CLI chosen when installed (`Engine used: rubberband-cli` in the log), librosa fallback when uninstalled — durations must be exact in both cases.
- [ ] CUDA and CPU device enforcement as in §0.
- [ ] Beat service source-mode fallback works when the frozen binary is absent; `pgrep -f beatnet` is empty after stop/timeout.
- [ ] Bundled ffmpeg/ffprobe found through `bundled_binary_dirs()` with nothing on `PATH`.

## 4. All platforms

- [ ] Read-only install location: model list must report bundled weights as available without downloading, and must refuse downloads into the read-only directory with an actionable message (see `ensure_writable_models_dir`).
- [ ] Copy `user_settings.json.example` to `user_settings.json` unchanged: the `~/Music/...` output path must land in the real home directory, and no literal `~` directory may appear next to the executable.
- [ ] Language switch (de/en) applies without an error dialog and survives restart.
- [ ] Quit with the platform shortcut; app writes its runtime report to the log.
- [ ] Long separation cancelled from the UI leaves no worker process and no stale IPC files in the temp dir.

## Sign-off

Flows verified: ______________  Deviations found (link issues): ______________
