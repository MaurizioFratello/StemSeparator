# Port State — Linux + Windows + CUDA (working notes, not a spec)

Resume point for the in-flight port. Requirements live in `.planning/REQUIREMENTS.md`,
phase plan in `.planning/ROADMAP.md`; this file records **what has actually been
executed** versus what still only exists as code.

- Branch / worktree: `feature/new-worktree` in `../StemSeparator-worktree` (base `main` @ `c4427fe`).
  All port work stays here; the primary clone is untouched.
- Interpreter for everything: `/home/mauriziofratello/.venvs/stemsep/bin/python`
  (CPython 3.11, PySide6 6.10, numpy 2.3.4, librosa 0.11, scipy 1.16.3, soundfile,
  sounddevice, soundcard 0.4.5, onnxruntime 1.23.2 **CPU-only**, audio-separator 0.39.1,
  torch 2.14.1+cu130, torchaudio 2.9.0+cpu, imageio-ffmpeg, pytest 9 + pytest-qt/mock/cov
  + pytest-timeout 2.4.0).
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

## Verified since (2026-10-02, executed)

| Area | Evidence |
| --- | --- |
| model_manager acceptance | `tests/test_model_manager.py` **26 passed hermetic (~75 s)**: external search-dir hit → `source_label == "external"`, 0 `Separator` instantiations; downloads target writable `MODELS_DIR`; read-only 0o500 dir survives init, `ensure_models_dir()` False, `download_model` False. Found+fixed 2 latent bugs (write-probe, `is_file()`+weight allowlist). Two test bugs fixed on the way: `test_download_all_models` ran the REAL Separator and hung in an HTTPS stream (needs the `stub_separator` fixture — it only ever "passed" on a warm cache), and the stub had to write a real Demucs bundle (YAML + ≥MIN `.th`) because `_demucs_bundle_is_complete` correctly rejects a pile of zeros named `.yaml`. |
| Recorder picker product bug | Refresh repopulated the combo without blocking Qt signals → `currentIndexChanged` persisted the first entry (a microphone on Linux/Windows), silently clobbering the saved `[System Audio]` source. Fixed with blockSignals + explicit `_on_device_changed(selected_index, persist=False)` dispatch after unblock; `_on_device_changed(index, persist=True)` gained the flag so a refresh can seed monitoring without ever writing settings (mirrors player_widget.py:811). |
| Monitoring lifecycle | Live scaffold proof with the REAL recorder: construction seeds `_last_selected_device`; `show()` → `showEvent` starts monitoring (`is_monitoring: True`, label `Monitoring...`) with no manual handler calls; refresh-while-visible re-monitors and leaves saved settings untouched; hide stops. 3 permanent tests in `tests/test_device_widgets.py` (**20 passed**). |
| BeatNet offline contracts | `tests/test_beat_service_client.py` **13 passed ×2 back-to-back in 0.05 s** (fake torch/Popen; real seams `platform_utils.popen_kwargs_for_console:378`, `numba_cuda_safe_env:418`): binary-name spelling, discovery precedence incl. `python -m src` fallback, availability, no-silent-CUDA-fallback, popen flags/env, group-kill + taskkill-fallback, pyaudio REALTIME/OFFLINE tiers. |
| platform_utils | `tests/test_platform_utils.py` **37 passed ×2 in 0.03 s** (XDG/APPDATA/HOME fakes, `~` never literal, bundled-beats-PATH binary order, popen kwargs). Also fixed a docstring lie: `is_linux()` claimed `emscripten`, code accepts only `linux*`/`freebsd*`. |
| CI hang guard | pytest-timeout + `timeout = 120`/`timeout_method = thread` (see `pytest.ini` WHY: the thread handler dumps stacks then `os._exit(1)` — aborts the WHOLE process, names the blocked test, does not yield a per-test failure line). It paid off immediately: located the HF-stream hang in 150 s that had silently killed two earlier suite runs. |
| Product bug: cancel freezes the app | `core/background_stretch_manager.py`: `cancel()` held the manager `QMutex` while `_cancel_all_workers()` did `QThread.terminate()` + **unbounded** `wait()` on GIL-holding Python DSP threads — the terminate blocks on the GIL while the caller holds GIL+mutex → process-wide deadlock (observed: suite stalled at `test_background_manager_cancel`, pytest-timeout's timer thread starved too; SIGKILL after 3600 s). Rewritten: snapshot+clear under the lock, `requestInterruption()` + bounded 5 s joins OUTSIDE the lock, `terminate()` only as last resort behind a bounded wait; `run()` got three interrupt checkpoints (before load, after load, before emit). Regression test `test_cancel_survives_a_worker_that_ignores_the_interrupt` (hostile worker → cancel still bounded; old code = infinite). File: **18 passed in 5.94 s** (was an infinite stall at test 11). |

## First full-suite census (2026-10-02)

Baseline: `45 failed, 175 passed, 1 skipped, 1 xfailed, 1 xpassed` across the
14 failing files (`/tmp/fail1.log` detail; whole-run map `/tmp/suite3.log`).

- Resolved (all re-run green): animations 5 — unparented QPropertyAnimation
  GC'd under offscreen, product fix parenting it to the widget
  (`ui/theme/animations.py:307`); blackhole 6 — macOS guards added to
  `check_blackhole_installed/check_blackhole_device/uninstall_blackhole`
  (uninstall could have run `brew uninstall` on a linuxbrew host!) plus
  Darwin-pinned mocks so the macOS branch runs on every CI; player 5 —
  PortAudio persistence + the volume test asserted `<=0.5` for coherent
  duplicates, rewritten to the real scaling/limiter contract; rms 1 (qtbot);
  sampler_export 5; improved_bpm 1 — file rewritten as real assertions, the
  librosa fallback halves a sparse 150 BPM click (74.9) inside the fold
  window, so strict assertions cover only {60,90,120,180} and 150/200 assert
  the octave family; export_loops_widget 7; time_stretcher 1 — restored the
  >2-D `ProcessingError` guard that the engine-chain rewrite had dropped
  (3-D input silently returned a corrupted array).
- Agents delivered and were VERIFIED by rerun + diff audit: separator 2 +
  chunk 1 + integration_separator 3 + ensemble 5 (`SepClusterFix`: 59 passed
  incl. product fix `core/chunk_processor.py` — `should_chunk` consulted the
  GLOBAL settings chunk length instead of the instance's own threshold, so a
  tighter per-instance threshold never entered the chunked path);
  integration_recording 3 (`RecIntegrations`: product fixes in
  `core/recorder.py` — pause no longer ingests an in-flight block; macOS
  default capture resolves strictly via BlackHole instead of any input; the
  no-device start path called `error_handler.handle_error`, which does not
  exist on `ErrorHandler` → latent AttributeError on every device-less start).
- **GUI hang — real root causes (the earlier "HF download via worker" guess
  was wrong, stack dumps decided):**
  1. Product bug, same family as the recorder-picker clobber:
     `UploadWidget._load_models()` repopulated `model_combo` WITHOUT blocking
     signals, and `_on_model_changed` answers an un-downloaded model with a
     MODAL "Model Not Downloaded" QMessageBox → the UI (and any offscreen
     test) was held hostage in a dialog at startup or after any download
     refresh just because the FIRST item happened to not be downloaded. Fixed
     like the recorder picker: blockSignals around repopulation (try/finally),
     selection preserved across refresh, `_update_button_states()` dispatched
     explicitly. The ⚠ item text is the intended non-blocking signal.
  2. Test-harness thread leak (advisory-confirmed, not psutil as the stack
     dumps suggested): `test_recording_to_file_workflow` started a REAL
     record loop, then mocked `Recorder.stop_recording` — bypassing
     `_stop_event.set()` + join — while its instant-return fake `record()`
     made the orphaned loop a GIL-hungry hot appender that starved every
     later test (the psutil `_ppid_map` frames in timeout dumps were the
     victim, not the blocker). `reset_singletons` only drops references.
     Fixed: conftest teardown now quiesces leaked `Recorder._record_loop`
     threads (set `_stop_event`, bounded join, force STOPPED) before clearing
     singletons, and the test uses a PACED fake stream (sleeps
     numframes/sr like a real device, 0.5-peak sine) through the REAL
     `stop_recording`, asserting the written WAV, IDLE state and zero leaked
     threads. A "throttle statusbar psutil scans" change made during this
     diagnosis was a misattribution and was REVERTED — GUI-thread psutil cost
     is a real concern but was NOT this hang's cause; do not resurrect it
     without a reproduction.

### Open findings (recorded, deliberately not acted on)

- `detect_bpm` librosa fallback: a sparse 150 BPM click track reads as 74.9 —
  half-tempo, and inside the 60-180 fold window so `_detect_bpm_librosa`'s
  octave correction cannot catch it. Measured candidate: `aggregate=None`
  (instead of `np.median`) reads 152.0 correctly and agrees with median on
  the only real-audio file available here (120.2 on `e2e_media/mix.wav`) —
  but that is click-track evidence; changing the validated median aggregate
  needs real-music verification (the median exists per its comment to be
  "robust to tempo variations"). DeepRhythm — the 95%-accuracy primary engine
  for these tempi — is currently blocked on this host by the installed
  torchaudio mismatch, so the fallback carries every local measurement.

## Suite status (2026-10-02, executed)

**Certified green run (2026-10-02): `942 passed, 1 skipped in 129.12 s`**
(bg_26, `/tmp/complete3.log`; collection 1010 items, 0 errors; the single skip is
the model-gated ensemble test). All 45 census failures, the `test_integration_gui`
hang (→10/10), and
the never-passing `tests/ui` graveyard resolved. The graveyard (player tabs,
upload, scroll-areas, user-behavior, styled, theme — ~100 red) had NEVER passed on
any OS: `_add_file`/`_language_actions`/`_queue_drawer`/`btn_export` exist in no
commit (git-proven for `_add_file`); tests referencing them were rewritten to the
current API or deleted per law (scroll suite deleted after a runtime probe proved
`UploadWidget.findChildren(QScrollArea)` is empty; the real `stems_scroll` contract
re-planted in `test_styled_components.TestPlayerStemScroll`).

1. **Marker honesty (DONE, verified by parent rerun):** both `xfail` markers in
   `tests/test_integration_recording.py` deleted with evidence — the E2E one
   concealed a stale mock signature (`_run_separation` gained the port's
   `quality_preset` positional; the TypeError failed all 3 retry attempts), the
   performance one was starved by the pre-rewrite fake capture.
   File: 15 passed isolated, 40 passed with the capture-device neighbor ×2.

2. **Windows runtime** — win32 branches proven against fakes + static spec checks
   only. A real 3-OS run (QA-01/02) needs the branch pushed to GitHub; user's call,
   asked, no answer yet.
3. **Commits landed** — tests+fixes `6a38215`, then the live-session fixes:
   `1e4fbc2` (vendor-dir discovery), `e817d99` (parent FFmpeg gate),
   `bd6f42b` (rescue-search deletion + queue→Player hand-off).

## Corrected premises (do not re-learn these the hard way)

- The mac specs do **not** exclude onnxruntime — the old handoff claim was FALSE. It sits in `hiddenimports` (`StemSeparator-arm64.spec:321`, `StemSeparator-intel.spec:256`); every `excludes` list holds pytest/black/flake8-style entries. Darwin specs untouched.
- Reproduce the Linux build with `python -m PyInstaller --noconfirm --clean packaging/linux/StemSeparator-linux.spec`; binary `dist/StemSeparator-linux/StemSeparator-linux` (65 MB exe, 7.3 G dist, ran frozen with `frozen: True`, bundled ffmpeg/ffprobe + bundled model verified). Vendor binaries come from `packaging/vendor/fetch_vendor.py` (`--check` verifies pinned SHA-256s); the dir is 474 MB and gitignored — `git add --dry-run -A` proves only specs/ico/iss/rthooks/generate_ico/README/fetch_vendor enter.
- `packaging/windows/StemSeparator-win.spec` builds every path from `SPECPATH`, degrades with an actionable note when vendored binaries are absent; `.ico` has 16→256 px via `generate_ico.py`; `requirements-cuda.txt` pins cu128 wheels whose existence on download.pytorch.org was checked same-day (cp311 win_amd64 + manylinux_2_28_x86_64).
- `tests/test_sample_rate_handling.py` aborted the WHOLE suite (imported a deleted constant); fixed by asserting the 44.1 kHz invariant instead of the dead name. Same class of blocker: any test importing a /tmp-only module is a CI-wide collection error — the two GUI scaffolds' `import pa_shim` must never reach a test file (the new widget tests inject fakes at `player._sounddevice_module`/`recorder._soundcard` instead).
- The dev venv's `user_settings.json` is throwaway state; scaffolds that mutated persisted settings (`sm.settings["use_gpu"]=…; mgr.save()`) were converted to monkeypatched seams — pytest must never touch it.
- `fetch_vendor.py` installs into `packaging/vendor/<platform>/bin` (linux/bin,
  windows/bin); the specs read those paths directly. `bundled_binary_dirs()`
  must probe the platform dir too (fixed `1e4fbc2`, pinned by
  `TestBundledBinaryDirs`) — probing only the flat `vendor/bin` silently broke
  source-mode separation on Linux.
- The worker's "empty list -> glob the output dir" rescue search is DELETED
  (`bd6f42b`). It laundered failures twice: adopted the INPUT recording as a
  bogus stem (queue renamed the user's take) and adopted a previous run's
  stale outputs, faking success and permanently deading the GPU-OOM -> CPU
  fallback chain. Never reintroduce it: empty result = failed attempt, the
  parent's retry chain handles strategy fallback.
- Live GPU->CPU proof (fresh temp out dir, sglang holding VRAM): attempt 1 CUDA
  fails, "Success on attempt 2" on CPU, 4 stems age<1 s, input intact. Replays
  MUST target a fresh empty output dir or stale stems invalidate the claim.
- Queue tab hands stems to the Player mixer via
  `QueueWidget.stems_load_requested` (double-click completed row, ordered by
  config `stem_names`) -> `MainWindow._on_queue_stems_load` ->
  `PlayerWidget.load_stem_files()`.
- PyInstaller with a `.spec`: `--collect-all`/`--specpath` are makespec-only
  flags and hard-fail; use `--noconfirm --distpath … --workpath …` only.
- `tests.yml` triggers now include `push: feature/**` and `workflow_dispatch`
  (before that, a feature-branch push ran NOTHING — CI claims were aspirational).

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
