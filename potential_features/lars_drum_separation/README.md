# LarsNet Drum Separation Feature (Archived)

## Overview

This directory contains the archived LarsNet drum separation feature that was removed from the main StemSeparator application to focus on core stem separation and loop export functionality.

## What Was This Feature?

The LarsNet integration provided advanced drum stem separation capabilities, splitting drum tracks into individual drum instruments:
- Kick drum
- Snare drum
- Toms
- Hi-hat
- Cymbals

It used the LarsNet neural network model from Politecnico di Milano, featuring 5 parallel U-Nets with Wiener filtering for high-quality separation.

## Why Was It Removed?

- **Focus on Core Functionality**: The team decided to focus on core stem separation and loop export features
- **Size Impact**: The LarsNet models and dependencies added ~6.3 GB to the repository
- **Complexity**: Required separate Python environment (3.10) and additional build steps
- **Scope**: Drum detail separation was considered an advanced feature beyond the app's primary use case

## Components Archived

### Backend Service (`backend/`)
- Complete LARS service binary implementation
- LarsNet neural network models (~565 MB .pth files)
- PyInstaller build scripts and configuration
- Python 3.10 isolated environment setup

### Python Client (`client/`)
- `lars_service_client.py`: Wrapper API for invoking LARS service
- Subprocess management, JSON I/O, timeout handling
- Binary discovery and error handling

### UI Widget (`ui/`)
- `drum_details_widget.py`: Complete GUI for drum separation
- Settings panel, progress tracking, export functionality
- Background worker threads for non-blocking processing

### Tests (`tests/`)
- Unit tests for LARS service client
- Integration tests with real audio processing

### Documentation (`docs/`)
- `LARS_PHASE1_PLAN.md`: Complete Phase 1 implementation plan
- Architecture documentation

### Build Integration (`build_integration/`)
- Code snippets showing how LARS was integrated into build scripts
- PyInstaller spec file additions
- Notes on restoring the integration

## How to Restore

If you want to restore this feature in the future:

1. **Checkout the Archive Branch**:
   ```bash
   git checkout archive/lars-integration
   ```

   This branch contains the complete working implementation before removal.

2. **Copy Components Back**:
   - Move files from this archive directory back to their original locations
   - Refer to `build_integration/` for build script integration

3. **Restore Build Integration**:
   - Add LARS build sections back to build scripts (see `build_integration/`)
   - Update PyInstaller specs to bundle LARS binary

4. **Restore UI Integration**:
   - Import `DrumDetailsWidget` in `ui/main_window.py`
   - Add widget to content stack and sidebar

## Dependencies

### Python Requirements
- Python 3.10 (LarsNet compatibility requirement)
- PyTorch 2.0+
- torchaudio
- soundfile
- librosa
- scipy
- numpy

### Models
- 5 pretrained U-Net models (~113 MB each)
- Total: ~565 MB
- Available from: Politecnico di Milano (check larsnet repository)

### System Requirements
- macOS 11+ (current implementation)
- Conda environment for Python 3.10
- ~7 GB disk space for full setup (including Git history)

## Archive Date

Removed: 2025-12-07

## References

- Archive Branch: `archive/lars-integration`
- Original LarsNet Repository: https://github.com/Ale-Dili/LarsNet (check larsnet/README for details)
- Phase 1 Implementation Plan: `docs/LARS_PHASE1_PLAN.md`

## Notes

- Large binary files (.pth models, larsnet/ repo) are excluded from Git tracking via .gitignore
- Code structure and integration examples remain available for reference
- The archive branch contains the complete working implementation with all binaries
