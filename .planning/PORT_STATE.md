# Port State — Linux + Windows + CUDA (working notes, not a spec)

Resume point for the in-flight port. Requirements live in `.planning/REQUIREMENTS.md`,
phase plan in `.planning/ROADMAP.md`; this file records **what has actually been
executed** versus what still only exists as code.

- Branch / worktree: `feature/new-worktree` in `../StemSeparator-worktree` (base `main` @ `c4427fe`).
  All port work stays here; the primary clone is untouched.
- Interpreter for everything: `/home/mauriziofratello/.venvs/stemsep/bin/python`
  (CPython 3.11, PySide6 6.10, numpy 2.3.4, librosa 0.11, scipy 1.16.3, soundfile,
  sounddevice, soundcard 0.4.5, onnxruntime 1.23.2 **CPU-only**, audio-separator 0.39.1,
  torch 2.14.1+cu130, torchaudio 2.9.0+cpu, imageio-ffmpeg, pytest 9 + pytest-qt/mock/cov).
  No `pip` in that venv → install with `uv pip install --python <that python> ...`.
- Host: Linux x64, **no sudo**, PipeWire running, two real CUDA GPUs
  (RTX 5090 + RTX PRO 6000 Blackwell, driver 595.91.07).

## Standing constraints (from the user)

1. **Max 3 subagents at once** on the pennyroyal endpoint (concurrency 4 counting the
   parent). A previous run with 5 agents OOM-killed the box: the local sglang endpoint
   holds ~14 GB and swap sits at 14/16 GB. Serialize torch/PyInstaller work; never let
   two heavy processes run simultaneously.
2. Keep the shipping macOS path intact — every new `win32`/`linux` branch must leave the
   `darwin` path behaving as before.
3. No stubs, no `TODO: implement`, no silent CPU fallback, no fake fallbacks. A docstring
   must never describe behaviour the code does not have.
4. GSD slash-command gate in `.cursor/rules/gsd-project.md` was bypassed by direct user
   request; keep `.planning/STATE.md` / `ROADMAP.md` checkboxes coherent instead.

## Done AND verified by running it

| Area | Evidence |
| --- | --- |
| Phase 1 startup/paths (WIN-01..04) | `utils/platform_utils.py` + rewired `config.py`/`main.py`; no `fcntl`; cross-process single-instance lock proven with two real processes (child holds → parent `acquire_lock()` False; after exit → True). |
| Phase 2 device policy (INF-01..05) | `core/device_manager.py` + `core/separation_subprocess.py` **enforce** the requested device (worker previously accepted `device` and ignored it). 11 device-selection scenarios + 13 `_enforce_device` cases on fake torch. Real GPU measured on a 12 s clip, preset `fast`: **CUDA 2.61 s vs CPU 4.47 s**. Settings picker drives it (`compute_device` in `ui/settings_manager.py`, `reload_device_manager()`); verified pin cpu stays cpu on a GPU box (`CUDA_VISIBLE_DEVICES=""`) with the worker logging `Device enforced: torch=cpu`. |
| Real end-to-end separation | demucs_4s on `/tmp/e2e/mix.wav` → 4 stems, `Parsed separation result from result file`. |
| Worker launch bug | Was `python -m core.separation_subprocess` with cwd=output dir → `ModuleNotFoundError: No module named 'core'` (also broken on macOS). Now absolute script path + file-based IPC (`--params-file`, result file) so `--noconsole` builds work. |
| Player (PLY-01/02) | `core/player.py`: `list_output_devices()`, `set_output_device()`, `get_output_device(_name)()`, `_candidate_rates()`, `_resample_to()`, `_play_array()`. Real playback: 16 outputs listed, play → state playing → position 1.00 s after 1 s, stop → stopped. Four failure modes proven: all-devices-fail → `play()` False + stopped + actionable `last_error`; `Invalid sample rate` → recovered by resampling 44100→48000; pinned broken device → falls back to system default; everything failing → False + stopped. Callers no longer set PLAYING on a failed stream (both auto-restart sites in `_position_update_loop` stop the clock). |
| Player device picker | `ui/widgets/player_widget.py` combo (name + host API + channels, "default" marker, Refresh) persisted via `playback_device`; verified headless offscreen: selects, persists to `user_settings.json`, stale saved device falls back to default **with a visible warning**. |
| Recorder (REC-01/02) on Linux | `core/recorder.py`: `RecordingBackend` gained `WASAPI_LOOPBACK`/`SYSTEM_LOOPBACK`/`INPUT_DEVICE`; enumeration uses `all_microphones(include_loopback=True)` (without it Linux hides monitors and Windows hides loopback — that was the whole bug). Captured **3.00 s of real system audio** (peak 0.9647, RMS 0.16, level meter fired 64×) from `Monitor of GB202 ... (HDMI 2)` while the player was outputting. |
| Recorder backend matrix | Fake-soundcard run for win32→`wasapi_loopback`, linux→`system_loopback`, darwin→`blackhole`, always passing `include_loopback=True`; label round-trip + bogus-device → actionable `last_error`. |
| Recording UI | Device combo lists `[System Audio]` entries, auto-selects the default speaker's monitor, persists choice via `recording_device`; `_recording_failure_help()` gives per-OS guidance (no more "grant Screen Recording permission" on Linux). |
| Settings dialog | BlackHole install card is macOS-only (verified `hasattr(d,"btn_install_blackhole") == False` on Linux); off-mac gets a "System Audio Capture" card showing the real detected endpoint. |
| UI neutrality | `QKeySequence.Quit` already role-based; native dialogs already enabled; `ui/theme/macos_effects.py` + `utils/macos_integration.py` already guard every entry point (handoff's `setBlurEnabled` claim was false — no such call exists); splash font fixed (`QFont.setFamily` never parsed the CSS-style fallback list). |
| i18n | `resources/translations/{en,de}.json`: mac-only `recording.blackhole_*` + `recording.feature_disabled` deleted (all unused), platform-neutral recording/playback keys added; both files parse, 133 keys each. |
| Time stretcher | `core/time_stretcher.py`: lazy pyrubberband/librosa imports, `rubberband_binary()` via `platform_utils.find_binary`, engine chain `rubberband-cli → pyrubberband → librosa-phase-vocoder` logging which ran. With CLI on PATH: 12 s → **9.600 s** at 1.25× in 0.44 s. Without CLI: librosa fallback, also exact, 2.85 s. All engines broken → `LibraryNotFoundError` naming every engine's reason. Module imports with pyrubberband **and** librosa blocked. |
| BeatNet/DeepRhythm | Agent-executed: service over the client returned **120.0 BPM** (confidence 0.96, backend `cuda`) on the 120 BPM click track, CPU path also 120.0 BPM, termination left no orphans, 33/33 fake-torch device-policy cases, win32 spawn/kill branches exercised offline. Files: `utils/beat_service_client.py`, `packaging/beatnet_service/src/{device,pyaudio,__main__}.py`, `utils/audio_processing.py`. |

## NOT verified — start here tomorrow

1. **`core/model_manager.py` + `packaging/download_models.py`.** A killed agent left
   ~750 lines claiming `MODEL_SEARCH_PATHS` lookup (writes to `MODELS_DIR`, per-file
   provenance, lazy `MODELS_DIR` read so `tests/test_model_manager.py:26` monkeypatch
   still works). `py_compile` passes; **none of its acceptance runs were ever executed**.
   Prove: (a) model present only in a second search dir → reported available, no download;
   (b) download destination is `MODELS_DIR` (stub `Separator`, no network);
   (c) read-only `MODELS_DIR` doesn't crash init. Trust nothing the docstring claims until run.
2. **Packaging (PKG-01..05) — effectively not started.** Previous job was OOM-killed after
   only creating `packaging/vendor/linux/{bin,native}` (static ffmpeg 79 MB, ffprobe,
   `libportaudio.so.2` — **gitignored, keep out of git**). Missing: Windows onedir spec,
   Linux spec, real `.ico` (repo has only `.icns`/PNG), Inno Setup script,
   `requirements.txt` CUDA-index split, `requirements-build.txt` `dmgbuild` marker,
   audit of the mac specs' `excludes=["onnxruntime"]` (breaks MDX-Net), and
   **`docs/PACKAGING.md` with a literal `## CUDA Installation` heading** — two error
   strings already reference that anchor (`core/device_manager._cuda_unavailable_description`
   and the worker's CUDA RuntimeError). Acceptance: build the Linux onedir here and run it.
3. **CI matrix (QA-01/02)** — agent `CIMatrix-2` was still running at pause; it had already
   written `.github/workflows/tests.yml`, `.planning/codebase/STACK.md`, `.planning/codebase/TESTING.md`.
   Read those files and validate the YAML before re-delegating anything.
4. **Phase 8 tests — `pytest` has NEVER been run in this port.** Expect: 4 pytest-collectible
   files importing PyObjC (`tests/manual_deeprhythm_integration.py`, `test_ensemble_realworld.py`,
   `obsolete_test_beat_detection.py`, `obsolete_test_audio_separation_lib.py`), ~15 files
   monkeypatching `sys.platform="darwin"`, and tautological tests to **delete rather than
   re-pin** (`test_macos_colors.py`, `test_macos_effects.py`, `test_screencapture_simple.py`).
   `test_device_manager.py` will fail on the old silent-CPU-fallback `set_device` contract —
   update it to the new one. Then add behavioral tests for platform_utils, device enforcement,
   recorder backends (fake soundcard — reuse `.port_checkpoints/rec_matrix.py`), player
   resolution/resample, worker IPC, stretcher chain.
5. Docs/cleanup: README platform badges + install sections, CHANGELOG parity matrix (REC-04),
   QA-03 manual CUDA checklist, then delete `packaging/vendor/bin/ffmpeg` symlink (throwaway),
   `temp/` recordings, `logs/`, `user_settings.json`, `.stemseparator.lock`,
   `.port_checkpoints/`, and update `.planning/STATE.md` + ROADMAP checkboxes.

## Recreating host prerequisites (they live in /tmp and may not survive a reboot)

```bash
PY=/home/mauriziofratello/.venvs/stemsep/bin/python
WS=/home/mauriziofratello/Documents/01_Projects/StemSeparator-worktree

# PortAudio (no sudo needed) — the runtime library sounddevice/ctypes looks up
cd /tmp && mkdir -p pa && cd pa && apt-get download libportaudio2 && dpkg -x *.deb root
# The ctypes shim is version-controlled in .port_checkpoints; copy it back to /tmp
# because the scripts import it as `sys.path.insert(0,'/tmp'); import pa_shim`.
cp $WS/.port_checkpoints/pa_shim.py /tmp/pa_shim.py

# Rubberband CLI (proves the preferred stretch engine; gitignored, not installed
# system-wide). `librubberband.so.3` is ALREADY present in /usr/lib/x86_64-linux-gnu
# on this host, so extracting the CLI deb and extending PATH is sufficient — verify
# with `ldconfig -p | grep rubberband` before chasing dependency packages. The CLI
# deb's own Depends are: libc6, libfftw3-double3, libgcc-s1, libsamplerate0,
# libsndfile1, libstdc++6 (check with `dpkg-deb -f <deb> Depends` on newer releases,
# which rename sonames, e.g. t64 variants).
cd /tmp && mkdir -p rb && cd rb && apt-get download rubberband-cli && dpkg -x *.deb root
export PATH=/tmp/rb/root/usr/bin:$PATH

# 12 s synthetic 120 BPM mix + separated stems (35 MB copy kept in .port_checkpoints/e2e_media)
cp -r $WS/.port_checkpoints/e2e_media /tmp/e2e
$PY $WS/.port_checkpoints/e2e_separate.py      # regenerate stems if missing

# ffmpeg for host runs (throwaway symlink; remove before finishing)
mkdir -p $WS/packaging/vendor/bin
ln -sf /home/mauriziofratello/.venvs/stemsep/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2 \
   $WS/packaging/vendor/bin/ffmpeg
```

## Verification commands (scripts preserved in `.port_checkpoints/`, gitignored)

These are scaffolding, to be converted into real tests in Phase 8.

```bash
cd $WS
QT_QPA_PLATFORM=offscreen $PY .port_checkpoints/player_check.py      # real playback + device listing
QT_QPA_PLATFORM=offscreen $PY .port_checkpoints/player_fail.py       # 4 playback failure modes
$PY .port_checkpoints/rec_check.py                                    # live PipeWire monitor capture
$PY .port_checkpoints/rec_matrix.py                                   # win/linux/mac backend matrix (fake soundcard)
QT_QPA_PLATFORM=offscreen $PY .port_checkpoints/gui_player_check.py   # player picker headless
QT_QPA_PLATFORM=offscreen $PY .port_checkpoints/gui_rec_check.py      # recording widget headless
QT_QPA_PLATFORM=offscreen $PY .port_checkpoints/gui_settings2.py      # settings dialog headless
$PY .port_checkpoints/stretch_check.py                                # fallback engines (no CLI)
PATH=/tmp/rb/root/usr/bin:$PATH $PY .port_checkpoints/stretch_cli.py  # preferred CLI engine
$PY .port_checkpoints/devcheck.py                                     # device-selection matrix
# compile gate
$PY -m py_compile main.py config.py core/*.py utils/*.py ui/*.py ui/widgets/*.py
# first-ever suite run (expect collection failures; see Phase 8 above)
cd $WS && PYTHONPATH=$WS/.port_checkpoints QT_QPA_PLATFORM=offscreen $PY -m pytest -q -p no:cacheprovider
```

## Gotchas that already bit once

- `soundcard/pulseaudio.py` `_infer_program_name()` reads `sys.argv[1]` when
  `sys.argv[0] == "-c"` → importing soundcard under `python -c` raises `IndexError`.
  Always run via a file and set `sys.argv = ["name.py"]` in harnesses.
- Never import `Recorder`/`Speaker` from soundcard by name: absent on Linux. Use
  `all_microphones(include_loopback=True)` / `default_microphone()` / `get_microphone(id, include_loopback=True)`.
- ONNX models (MDX-Net) need a CUDA-enabled onnxruntime; this venv has CPU-only
  onnxruntime, so the worker logs a warning — that is correct behaviour, not a bug to hide.
- Settings files land in the repo root in dev mode (`USER_DIR = Path(__file__).parent`),
  so always check `git status` before committing.
- `user_settings.json.example` still contains a macOS `~/Library/Application Support/...`
  value under a Windows-shaped `output_directory` key — fix during docs/cleanup.
