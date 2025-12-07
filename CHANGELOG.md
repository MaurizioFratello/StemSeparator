# Changelog

All notable changes to Stem Separator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Windows/Linux support for system audio recording
- Additional AI models (MDX-Net variations, VR Architecture)
- Batch export functionality
- Real-time preview during processing
- Custom model training interface
- VST/AU plugin version
- Cloud-based processing (optional)
- Mobile app (iOS/Android)

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

[Unreleased]: https://github.com/MaurizioFratello/StemSeparator/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v1.0.0
[1.0.0-rc1]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v1.0.0-rc1
[0.9.0]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v0.9.0
[0.5.0]: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v0.5.0
