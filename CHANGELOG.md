# Changelog

All notable changes to Stem Separator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Platform parity documentation (REC-04, QA-03)**
  - `docs/PLATFORM_PARITY.md` publishes which flows are identical across macOS,
    Windows and Linux, which use an OS-specific backend, and which differ because
    the OS forces it (BlackHole on macOS vs driver-free loopback elsewhere)
  - `docs/QA_HARDWARE_CHECKLIST.md` is the manual checklist CI cannot cover:
    real CUDA/MPS enforcement, timing comparison, output-device and loopback
    capture scenarios per platform
- `tests/test_path_utils.py` pins output-path resolution behaviour, including the
  `~` expansion cases that used to create a literal `~` directory
- **Cross-platform test coverage** — the behaviours the port had to prove are now
  permanent tests instead of throwaway scripts:
  `tests/test_player_output_devices.py` (device listing, sample-rate recovery, the
  playback failure modes), `tests/test_recorder_capture_devices.py` (loopback
  enumeration and the backend matrix for all three OSes),
  `tests/test_device_widgets.py` (both pickers, persistence, hot-unplug fallback),
  `tests/test_time_stretcher_engines.py` (engine chain, BPM math, the
  all-engines-missing error), `tests/test_device_manager_preferences.py`
  (`use_gpu`/`compute_device` translation and reload) and
  `tests/test_separation_device_enforcement.py` (worker device enforcement and the
  subprocess launch contract)
- `tests/test_sample_rate_handling.py` no longer aborts the entire suite: it
  imported `TARGET_SAMPLE_RATE`, a constant removed months ago, which turned every
  run into a collection error; the 44.1 kHz invariant is asserted directly now
- **Test-hang guard** — `pytest-timeout` plus `timeout = 120` and
  `timeout_method = thread` in `pytest.ini`: a test blocked on a device or
  subprocess that never answers aborts the run within minutes and dumps the
  stacks, naming the blocked test, instead of parking the CI job until the
  runner-level timeout hours later with no indication of which test hung
  (the thread method ends the whole process, so the offending test gets fixed
  or isolated rather than quietly skipped)
- **Linux and Windows packaging** — `packaging/linux/StemSeparator-linux.spec` and
  `packaging/windows/StemSeparator-win.spec` (onedir, torch/PySide6/onnxruntime
  collection, vendored FFmpeg), a multi-size `StemSeparator.ico`, an Inno Setup
  script, `packaging/vendor/fetch_vendor.py` for the pinned binaries that stay out
  of git, `requirements-cuda.txt` for the CUDA layer, and `docs/PACKAGING.md`
  sections for building on Linux and Windows (including `## CUDA Installation`)
- `.github/workflows/tests.yml` runs the suite on macOS, Windows and Linux across
  Python 3.11 and 3.12 with CPU-only torch, so the macOS path stays covered while
  the ported platforms are exercised

### Fixed
- **Model discovery, downloads and saved paths**
  - `ensure_writable_models_dir()` now proves writability with a real write probe:
    `mkdir(exist_ok=True)` succeeds on an existing read-only directory, so a
    read-only install reported "writable" and the download later failed with an
    opaque error
  - `_candidate_is_valid()` requires a regular file with a weight extension; it
    previously returned "valid" for directories and foreign files, letting an empty
    directory satisfy a model lookup
  - `packaging/download_models.py` crashed on every invocation (`MODELS` was used
    but never imported); `--help` started a multi-gigabyte download instead of
    printing usage, and unknown options were ignored silently
  - A `~/...` value in `user_settings.json` (as shipped in the example file) is now
    expanded for `Path` input as well; it used to be anchored to the working
    directory, writing stems into a stray `~` folder next to the executable
  - Language switching, the file-selection slot and the recorder's "no device"
    path raised `TypeError` because they passed printf-style arguments to a logger
    that only accepts a single message; the failure was silent in packaged builds
  - Model-manager tests no longer download weights from Hugging Face and no longer
    depend on which weights happen to exist in the developer's cache
- **Recording device picker overwrote the saved choice** — refreshing the device
  list (opening the tab, pressing Refresh, hot-plugging hardware) rebuilt the combo
  without blocking Qt signals, so the `currentIndexChanged` handler persisted the
  first entry that happened to be added. On Windows/Linux that is a microphone, so
  the saved system-audio source was silently replaced and the next recording
  captured the room. The repopulation now blocks signals, as the playback picker
  already did
- **The saved-device warning was unreachable on Linux** — the recorder only listed
  microphones it could open, so loopback endpoints were never enumerated and a
  pinned `[System Audio]` device resolved to nothing; enumeration now requests
  loopback devices explicitly on every platform
- **Auto-BPM / Beat Service - Linux and Windows**
  - The bundled BeatNet helper now runs on Linux and Windows, not only macOS: it is
    discovered as a binary (`.exe` on Windows), from the frozen bundle, from `PATH`,
    or executed from source with `python -m src`
  - Beat analysis now follows the app-wide device policy (`compute_device`,
    `use_gpu`): CUDA-preferred on Linux/Windows, MPS-preferred on macOS, CPU
    otherwise; a device that cannot be honoured is reported instead of silently
    downgrading to CPU
  - The helper no longer needs a working microphone: `src/pyaudio.py` uses real
    PyAudio when it loads and otherwise preloads PortAudio
    (override: `STEMSEPARATOR_PORTAUDIO_LIBRARY`) and installs an offline stub, so
    `pyaudio`-importing BeatNet still analyses files
  - Cancelling or timing out an analysis no longer orphans the helper's worker
    processes (and their GPU memory); the whole process group is drained
  - `detect_bpm` survives a broken DeepRhythm/torchaudio install - it used to raise
    out of the module import - and reports why it fell back to librosa

- **Upload screen opened a modal dialog by itself** — (re)building the model
  dropdown fired `currentIndexChanged` for every item, and the change handler
  answers a not-downloaded model with a modal "Model Not Downloaded" prompt:
  the app could hold the UI hostage in a download dialog for a model the user
  never picked (at startup, or after any model finished downloading). The
  ⚠ marker in the item text is the intended non-blocking signal; the prompt
  now fires only on user-initiated selection, and a refresh keeps the current
  selection instead of jumping back to the default

- **Stability fixes surfaced by the first full test-suite run**
  - Cancelling background time-stretching could freeze the entire application:
    `cancel()` force-terminated worker threads while holding the manager mutex,
    and terminating a Python thread blocks on the interpreter lock the canceller
    itself holds. Cancellation is now cooperative with bounded waits
  - Pausing a recording could still ingest one in-flight audio block, so the
    resumed file contained a chunk recorded "during" the pause
  - Starting a recording with no usable device raised `AttributeError`
    (called a method the error handler does not have) instead of showing the
    actionable failure
  - On macOS, leaving the capture device on auto could silently open any input
    the OS reports; the default now resolves strictly via BlackHole
  - The BlackHole check/uninstall entry points could run `brew` commands on
    Linux hosts (linuxbrew exists); they now refuse to act off-macOS
  - `ChunkProcessor.should_chunk()` consulted the global settings chunk length
    instead of the instance's own threshold, so callers that configure tighter
    chunking (constrained environments, tests) never entered the chunked path
  - Time-stretching no longer accepts >2-dimensional arrays and returns a
    silently corrupted result; it raises `ProcessingError` naming the shape
  - Widget back-animations that were only referenced from a local variable were
    garbage-collected mid-playback under some platforms (visible stutter);
    they are now parented to the widget they animate

### Planned
- Windows/Linux support for system audio recording
- Additional AI models (MDX-Net variations, VR Architecture)
- Batch export functionality
- Real-time preview during processing
- Custom model training interface
- VST/AU plugin version
- Cloud-based processing (optional)
- Mobile app (iOS/Android)

## [1.0.2] - 2025-12-19

### Fixed
- **Export Loops Widget - Time-Stretched Loops Export**
  - Fixed "Use Time-Stretched Loops" checkbox not working correctly
  - Export now correctly uses time-stretched loops when checkbox is enabled
  - Fixed loop segment inconsistency between Looping tab and Export Loops tab
  - Export now uses the same `valid_loops` (filtered to exclude intro loops with negative start times) that were used during time-stretching
  - Added stem name normalization (lowercase) for consistent cache access
  - Checkbox now only enables when all loops are ready (not just some)
  - Export aborts with warning if time-stretching is incomplete (no silent fallback to original loops)
  - Works correctly for both export modes (Mixed Audio and Individual Stems)
  - Properly handles intro loops (leading loops with padding are correctly filtered out)

## [1.0.1] - 2025-12-18

### Added
- **Comprehensive Documentation**
  - User Guide (English) - 800+ lines comprehensive guide
  - Benutzeranleitung (Deutsch) - 700+ lines German user guide
  - MODEL_LICENSES.md - Complete AI model licensing documentation
  - THIRD_PARTY_LICENSES.md - Full third-party dependency licenses
  - License compatibility tables and verification instructions
- **GitHub Community Files**
  - Issue templates for bug reports and feature requests
  - Pull request template
  - Security policy (SECURITY.md)
  - Code of Conduct

### Changed
- **Dependencies Pinned to Exact Versions**
  - requirements.txt updated with exact tested versions
  - PySide6: 6.10.0, PyTorch: 2.9.0, numpy: 2.3.4
  - Ensures reproducible builds and consistent behavior
- **Repository Cleanup**
  - Removed internal development files
  - Cleaned up temporary and build artifacts
  - Updated .gitignore for better exclusions
  - Removed debug print statements from production code

### Fixed
- **Test Suite Improvements**
  - Fixed test collection errors (2 → 1 remaining)
  - Renamed obsolete test files to prevent import errors
  - test_deeprhythm_integration.py → manual_deeprhythm_integration.py
  - test_beat_detection.py → obsolete_test_beat_detection.py
  - Removed tests for non-existent functions (_get_best_device, _get_beatnet_predictor)
- **Code Quality**
  - Removed 4 debug print statements from core/separation_subprocess.py
  - Fixed hardcoded paths in test files
  - Cleaned configuration placeholders

### Documentation
- Updated README.md and README.de.md with new documentation links
- Removed references to deleted internal documentation
- Added comprehensive attribution requirements for models
- Documented LGPL compliance for PySide6
- Added academic citations for all AI models

### Security
- Documented all third-party licenses for legal compliance
- Added license verification instructions
- Clarified commercial use permissions

## [1.0.0] - 2024-12-07

### Added
- **Ensemble Separation Feature**
  - Balanced Ensemble (BS-RoFormer + Demucs)
  - Quality Ensemble (Mel-RoFormer + BS-RoFormer + Demucs)
  - Vocals Focus (Mel-RoFormer + BS-RoFormer)
  - MDX + Demucs ensemble (mask blend)
- **Modern Dark Theme**
  - Purple-Blue accent colors
  - macOS native integration
  - Vibrancy effects and blur
- **Beat Detection & Looping**
  - Automatic beat detection with BeatNet
  - Manual beat adjustment
  - Loop export to sampler formats
  - Beat synchronization with audio
- **Native macOS Integration**
  - System menu bar
  - Native file dialogs
  - macOS keyboard shortcuts
  - Full-screen support
- **Comprehensive Testing**
  - 89% code coverage
  - 199+ unit and integration tests
  - GUI component tests
- **Complete Documentation**
  - Developer guides
  - API documentation
  - Packaging instructions
  - Troubleshooting guides

### Changed
- **Audio Player Migration**
  - Migrated from rtmixer to sounddevice
  - Improved stability and performance
  - Better thread safety
  - Fixed deadlocks on stop/pause
- **Error Handling**
  - Enhanced error messages
  - Automatic retry mechanisms
  - Better user feedback
  - Detailed logging system
- **UI/UX Improvements**
  - Sidebar navigation (replaced tabs)
  - Enhanced player controls
  - Better visual feedback
  - Improved layout and spacing

### Fixed
- Thread-safety issues in audio player
- Deadlocks during stop/pause operations
- Sample rate handling in ensemble mode
- Beat grid synchronization drift
- Manual downbeat placement bugs
- BlackHole installation threading issues
- Device prefix handling in recorder
- AppContext API inconsistencies

### Security
- Input validation for audio files
- Safe file handling
- Secure subprocess execution

## [1.0.0-rc1] - 2024-11-09

### Added
- Initial release candidate
- Core stem separation functionality
- System audio recording (macOS)
- Stem player with mixing controls
- Queue system for batch processing
- Multi-language support (German/English)
- GPU acceleration (MPS/CUDA)
- 4-stem and 6-stem modes
- Model management system
- Automatic chunking for long files

### Models Supported
- Mel-Band RoFormer (~100 MB)
- BS-RoFormer (~300 MB)
- MDX-Net Vocals/Inst (~110-120 MB)
- Demucs v4 6-stem (~240 MB)
- Demucs v4 4-stem (~160 MB)

## [0.9.0] - 2024-10-15 (Internal Beta)

### Added
- Basic GUI implementation
- File upload and processing
- Stem separation with Demucs
- Basic player functionality
- Settings dialog
- Logging system

### Changed
- Improved model loading performance
- Enhanced error messages

### Fixed
- Memory leaks in model manager
- GUI freezing during processing
- File path handling on macOS

## [0.5.0] - 2024-09-01 (Alpha)

### Added
- Command-line interface
- Basic stem separation
- Model download functionality
- Configuration system

## Versioning Notes

### Version 1.0.0
This is the first stable release of Stem Separator, ready for public use. All core features are implemented, tested, and documented.

### Breaking Changes
None - first major release.

### Migration Guide
Not applicable for first release.

---

## Legend

- `Added` - New features
- `Changed` - Changes in existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Security improvements

[Unreleased]: https://github.com/MaurizioFratello/StemSeparator/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/MaurizioFratello/StemSeparator/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/MaurizioFratello/StemSeparator/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v1.0.0
[1.0.0-rc1]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v1.0.0-rc1
[0.9.0]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v0.9.0
[0.5.0]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v0.5.0
