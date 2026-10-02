# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-01)

**Core value:** Reliable stem separation and playback in one desktop app — Windows users get CUDA when available and safe CPU fallback; recording and capture parity with macOS (scope B) where the OS allows.

**Current focus:** First-ever complete suite run (background, `/tmp/complete1.log`), then the tests+fixes commit and the CI push decision

## Current Position

Phase: **6** of **6** — code complete for Phases 1, 3, 4, 5, 6 and verified by execution on
this Linux host; Phase 2 (packaging) **committed** (`b5a22a9`)  
Plan: Phases 1/3/4/5/6 implemented; QA-01/02 CI runs outstanding (need user push decision)  
Status: **GREEN** — first-ever complete suite run: `942 passed, 1 skipped in 129 s`
(bg_26, `/tmp/complete3.log`; single skip = model-gated ensemble test)  
Last activity: **2026-10-02** — triage closed incl. the never-passing `tests/ui`
graveyard (rewritten to current APIs or deleted with runtime evidence) and the
last two xfail markers (real cause: stale `_run_separation` mock signatures)  
Progress: `[█████████]` ~90% (remaining: CI green run QA-01/02 — needs push decision)

## Performance Metrics

**Velocity:** (updated after plan execution)

- Total plans completed: 5 of 6 phases coded and verified (Windows clauses await a Windows runner)
- Reference measurements: separation of a 12 s clip, preset `fast` — CUDA 2.61 s, CPU 4.47 s;
  time stretch 12 s → 9.600 s @1.25× in 0.44 s (rubberband CLI) / 2.85 s (librosa fallback);
  live system-audio capture 3.00 s stereo, peak 0.96
- Full-suite execution on Linux: **942 passed, 1 skipped, 0 markers** (certification
  run 2026-10-02; collection 1010 items, 0 errors)

**By phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 Bootstrap/paths | done (verified) | — | — |
| 2 Packaging | in progress | — | — |
| 3 Inference | done (verified incl. real CUDA) | — | — |
| 4 Playback | done (verified) | — | — |
| 5 Recording | done (verified incl. live loopback) | — | — |
| 6 Services/QA | code done; CI run + packaging docs outstanding | — | — |

## Accumulated Context

### Decisions

- **One platform authority**: all OS branching lives in `utils/platform_utils.py` (`_platform_string()` is the test seam); no scattered `sys.platform` checks.
- **`spawn` everywhere**: forked children cannot reuse the parent CUDA context and Windows has no fork.
- **Worker IPC via files** (`--params-file` + result file), stdout as fallback: a `--noconsole` Windows build has no usable pipe.
- **No silent CPU fallback**: `set_device()` returns `False` + `last_error`; the CPU retry is the caller's visible decision.
- **Audio devices keyed by name**, not PortAudio index (indices shift when USB/Bluetooth devices attach); playback math stays 44.1 kHz and only the callback buffer is resampled.
- **`soundcard` remains the capture engine** on all three OSes with `all_microphones(include_loopback=True)`; no pyaudiowpatch/pulsectl dependency.
- **Time-stretch order CLI → pyrubberband → librosa** chosen by measurement, not taste.
- **Linux is in scope** by explicit user decision, overriding PLT-01's deferral.

### Pending Todos

- Complete-run triage: any residual failure in files the census never reached (suite3.log died at
  ~73%) — tracked in `.planning/PORT_STATE.md`
- Execute the CI matrix (jobs defined: 3 OS × Python 3.11/3.12, CPU torch, xvfb + libportaudio2 on
  Linux) and record a green run — BLOCKED on the user's push-to-GitHub decision
- ~~PKG-01..05~~ committed as `b5a22a9` (packaging); ~~first full pytest run~~ in flight bg_20

### Blockers/Concerns

- **No Windows host**: every `win32` branch is validated offline against fakes only; the Windows CI job is the substitute evidence and has not run yet.
- **Memory ceiling on this box**: the local inference endpoint holds ~24 GB; two jobs were OOM-killed. Torch/PyInstaller work must be serialised, one heavy process at a time.
- **`/tmp` prerequisites are volatile** (PortAudio lib + shim, rubberband CLI, test media): recreation commands in `.planning/PORT_STATE.md`.


## Session Continuity
Last session: 2026-10-02  
Stopped at: suite certified green (942/1-skip); both commits landing (packaging
`b5a22a9`, tests+fixes next); QA-01/02 CI awaits the user's push decision  
Resume file: `.planning/PORT_STATE.md` (commits `d845196`, `b165497`, `b36092e`, `b5a22a9`)
