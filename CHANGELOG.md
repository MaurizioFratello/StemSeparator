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
