# LARS Build Integration Notes

## Overview

This directory contains code snippets showing how LarsNet was integrated into the StemSeparator build system. Use these as reference if you need to restore the feature.

## Integration Points

### 1. Build Scripts (`build_arm64.sh`, `build_intel.sh`)

**Location**: After BeatNet build section, before main app build

**Purpose**:
- Automatically create `lars-env` conda environment (Python 3.10)
- Build the LARS service standalone binary using PyInstaller
- Validate the binary is executable

**Key Details**:
- LARS requires Python 3.10 (LarsNet dependency requirements)
- Uses separate conda environment to avoid conflicts with main app (Python 3.11)
- Binary built to `packaging/lars_service/dist/lars-service`
- Gracefully continues if LARS build fails (non-blocking)

**Integration Position**:
- **arm64**: Lines 184-249 (original file)
- **intel**: Lines 159-224 (original file)

**Snippet Files**:
- `build_arm64_snippet.sh`
- `build_intel_snippet.sh`

### 2. PyInstaller Spec Files (`StemSeparator-arm64.spec`, `StemSeparator-intel.spec`)

**Location**: After BeatNet binary bundling, before FFmpeg bundling

**Purpose**:
- Search for pre-built lars-service binary in multiple locations
- Bundle binary into macOS app bundle at root level
- Make binary executable if needed

**Key Details**:
- Search paths:
  1. `packaging/lars_service/dist/lars-service` (primary)
  2. `resources/lars/lars-service` (alternative)
- Bundles to app root (`.`) for easy discovery
- Automatically sets executable permissions (chmod 0o755)
- Prints helpful warnings if binary not found

**Integration Position**:
- **Both specs**: Lines 139-178 (original files, identical code)

**Snippet File**:
- `spec_snippet.py` (applies to both arm64 and intel specs)

## Restoration Steps

If you need to restore LarsNet integration:

### Step 1: Restore Backend Files

Move from archive back to main codebase:
```bash
mv potential_features/lars_drum_separation/backend/lars_service packaging/
mv potential_features/lars_drum_separation/client/lars_service_client.py utils/
mv potential_features/lars_drum_separation/ui/drum_details_widget.py ui/widgets/
mv potential_features/lars_drum_separation/tests/*.py tests/
mv potential_features/lars_drum_separation/docs/LARS_PHASE1_PLAN.md .
```

### Step 2: Restore Build Script Integration

Edit `packaging/build_arm64.sh`:
- After BeatNet build section (around line 182), insert content from `build_arm64_snippet.sh`

Edit `packaging/build_intel.sh`:
- After BeatNet build section (around line 157), insert content from `build_intel_snippet.sh`

### Step 3: Restore PyInstaller Spec Integration

Edit `packaging/StemSeparator-arm64.spec`:
- After BeatNet binary section (around line 138), insert content from `spec_snippet.py`

Edit `packaging/StemSeparator-intel.spec`:
- After BeatNet binary section (around line 138), insert content from `spec_snippet.py`

### Step 4: Restore UI Integration

Edit `ui/main_window.py`:

Add import (line 38):
```python
from ui.widgets.drum_details_widget import DrumDetailsWidget
```

Add widget instantiation (around line 126):
```python
self._drum_details_widget = DrumDetailsWidget(self)
```

Add to content stack (around line 135):
```python
self._content_stack.addWidget(self._drum_details_widget)  # Index 4
```

Update export widget indices to 5 and 6 (currently 4 and 5):
```python
self._btn_export_mixed = self._create_export_page_button("export_mixed", 5)  # was 4
self._btn_export_loops = self._create_export_page_button("export_loops", 6)  # was 5
```

Add sidebar button (around line 188):
```python
self._btn_drum_details = self._create_nav_button("drum", 4)
sidebar_layout.addWidget(self._btn_drum_details)
```

Add translation (around line 476):
```python
self._btn_drum_details.setText(translator("tabs.drum_details", fallback="🥁 Drum Details"))
```

### Step 5: Build and Test

1. Build LARS service:
   ```bash
   cd packaging/lars_service
   ./build.sh
   cd ../..
   ```

2. Build main app:
   ```bash
   cd packaging
   ./build_arm64.sh  # or build_intel.sh
   ```

3. Test:
   - Launch app and verify Drum Details tab appears
   - Test drum separation functionality
   - Verify export continues to work

## Dependencies

Make sure these are available before restoring:

- Python 3.10 (for LARS service)
- Conda (for environment management)
- PyTorch 2.0+ (LARS dependency)
- LarsNet models (~565 MB .pth files)
- All dependencies in `packaging/lars_service/requirements.txt`

## Notes

- The LARS service runs as a separate subprocess with its own Python environment
- Communication is via JSON over stdin/stdout
- This architecture prevents dependency conflicts between main app (Python 3.11) and LARS (Python 3.10)
- Binary is ~700MB when built (includes PyTorch and models)
- Build time: ~2-3 minutes on modern hardware
