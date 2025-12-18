# Time-Stretching Implementation Strategy

**Version:** 1.0  
**Date:** 2025-01-XX  
**Status:** Planning  
**Repository:** StemSeparator  
**Feature:** Stem-Specific Time-Stretching Integration

---

## 1. PRD Analysis & Improvements

### 1.1 Identified Improvements

**Missing Technical Details:**

- **Sample Rate Handling**: PRD doesn't specify how to handle the existing 44100 Hz requirement (all stems are at 44100 Hz per `TARGET_SAMPLE_RATE` in `core/separator.py`). Time-stretching should preserve this.
- **Chunking Integration**: PRD doesn't address how time-stretching works with the existing chunking system (`core/chunk_processor.py`). Long files are processed in chunks - time-stretching must handle this.
- **Memory Management**: No discussion of memory-efficient processing for large files, which is critical given the existing chunking infrastructure.
- **Error Recovery**: Missing fallback strategies when algorithms fail (beyond library availability).

**License Strategy Clarification:**

- PRD recommends Option B (optional Rubber Band), but needs explicit implementation:
  - Runtime detection with clear user warnings
  - Separate installation instructions for GPLv2 components
  - License acceptance dialog for GPLv2 libraries

**Integration Points Missing:**

- How time-stretching integrates with `SeparationResult` dataclass
- Integration with existing export widgets (`ui/widgets/export_mixed_widget.py`, `export_loops_widget.py`)
- Settings persistence via `ui/settings_manager.py`

**Performance Targets Too Vague:**

- "2x real-time" is ambiguous - needs specification: CPU-bound or I/O-bound?
- No discussion of parallel processing with existing separation subprocess pattern

### 1.2 Recommended PRD Enhancements

1. **Add Technical Constraints Section:**
   - Sample rate preservation (44100 Hz)
   - Chunking compatibility
   - Memory limits (<2x input size)

2. **Clarify License Strategy:**
   - Explicit opt-in flow for GPLv2 libraries
   - Installation script separation
   - License acceptance UI

3. **Define Integration Architecture:**
   - Extend `SeparationResult` with optional `stretched_stems` field
   - New processing step between separation and export
   - Settings schema for time-stretching preferences

## 2. Library Selection & Implementation Strategy

### 2.1 Primary Library: `audiotsm` (MIT License)

**Rationale:**

- MIT license compatible with existing project
- Supports WSOLA algorithm (optimal for drums per PRD)
- Pure Python implementation, easy integration
- Active maintenance, good documentation

**Implementation Pattern:**

```python
from audiotsm import wsola
from audiotsm.io.array import ArrayReader, ArrayWriter
import numpy as np
import soundfile as sf

# Load audio
audio_data, sr = sf.read("stem.wav", always_2d=True)
audio_data = audio_data.T  # (channels, samples) for audiotsm

# Time-stretch with WSOLA
reader = ArrayReader(audio_data, sr)
writer = ArrayWriter(reader.channels, reader.samplerate)
tsm = wsola(reader.channels, speed=1.05)  # 5% faster
tsm.run(reader, writer)

# Save result
stretched = writer.data.T  # Back to (samples, channels)
sf.write("stretched.wav", stretched, sr)
```

### 2.2 Optional Library: `rubberband` via `pylibrb` (GPLv2)

**Rationale:**

- Higher quality for vocals/bass (per PRD requirements)
- Must be optional with clear license warning
- Runtime detection pattern

**Implementation Pattern:**

```python
try:
    import pylibrb
    RUBBERBAND_AVAILABLE = True
except ImportError:
    RUBBERBAND_AVAILABLE = False
    # Fallback to audiotsm
```

**License Handling:**

- Show license acceptance dialog on first use
- Store acceptance in `user_settings.json`
- Separate installation instructions in docs

### 2.3 Fallback: `librosa.effects.time_stretch` (Phase Vocoder)

**Rationale:**

- Already in dependencies (`requirements.txt`)
- Acceptable quality for preview/fallback
- No additional dependencies

**Use Case:**

- Emergency fallback if audiotsm unavailable
- Real-time preview mode (lower quality acceptable)

## 3. Architecture Design

### 3.1 Component Structure

```
core/
  time_stretch/
    __init__.py
    processor.py          # Main TimeStretchProcessor class
    algorithms.py          # Algorithm implementations (WSOLA, RubberBand, PhaseVocoder)
    selector.py            # Stem → algorithm mapping
    config.py              # TimeStretchConfig dataclass
    exceptions.py          # Custom exceptions
```

### 3.2 Integration Points

**1. Extend `SeparationResult` (core/separator.py):**

```python
@dataclass
class SeparationResult:
    # ... existing fields ...
    stretched_stems: Optional[Dict[str, Path]] = None  # New optional field
```

**2. New Processing Step:**

- Time-stretching happens after separation, before export
- Optional step (user must enable)
- Integrates with existing progress callback pattern

**3. Settings Integration:**

- Add time-stretching settings to `ui/settings_manager.py`
- Persist presets and preferences in `user_settings.json`
- Default: disabled (opt-in)

**4. GUI Integration:**

- New widget: `ui/widgets/time_stretch_widget.py`
- Add to main window navigation (similar to `ExportMixedWidget`)
- Integrate with `PlayerWidget` for preview

### 3.3 Data Flow

```
Separation → SeparationResult → TimeStretchProcessor → Stretched Stems → Export
                (stems dict)         (optional step)      (new dict)      (existing)
```

## 4. Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Deliverables:**

- `core/time_stretch/` module structure
- `TimeStretchProcessor` class with basic WSOLA support
- Algorithm selector (stem → algorithm mapping)
- Unit tests for core functionality

**Files to Create:**

- `core/time_stretch/__init__.py`
- `core/time_stretch/processor.py`
- `core/time_stretch/algorithms.py`
- `core/time_stretch/selector.py`
- `core/time_stretch/config.py`
- `core/time_stretch/exceptions.py`

**Files to Modify:**

- `core/separator.py` - Add optional `stretched_stems` to `SeparationResult`
- `requirements.txt` - Add `audiotsm>=0.1.2`

### Phase 2: GUI Integration (Week 2-3)

**Deliverables:**

- `TimeStretchWidget` with controls (sliders, presets)
- Integration with main window navigation
- Settings persistence
- Preview functionality

**Files to Create:**

- `ui/widgets/time_stretch_widget.py`

**Files to Modify:**

- `ui/main_window.py` - Add time-stretch navigation button
- `ui/settings_manager.py` - Add time-stretching settings
- `user_settings.json.example` - Add time-stretching defaults

### Phase 3: Rubber Band Integration (Week 3-4)

**Deliverables:**

- Optional Rubber Band support with license handling
- License acceptance dialog
- Fallback to audiotsm when unavailable
- Algorithm selection based on stem type

**Files to Create:**

- `ui/dialogs/license_acceptance_dialog.py`
- `docs/TIME_STRETCHING_LICENSE.md`

**Files to Modify:**

- `core/time_stretch/algorithms.py` - Add Rubber Band implementation
- `core/time_stretch/selector.py` - Implement stem-specific selection
- `requirements.txt` - Add optional `pylibrb` with comment

### Phase 4: Export Integration (Week 4-5)

**Deliverables:**

- Integration with existing export widgets
- Naming convention for stretched stems
- Export options (format, bit depth, normalize)

**Files to Modify:**

- `ui/widgets/export_mixed_widget.py` - Add time-stretch option
- `ui/widgets/export_loops_widget.py` - Add time-stretch option
- `core/sampler_export.py` - Handle stretched stems if needed

### Phase 5: Testing & Optimization (Week 5-6)

**Deliverables:**

- Comprehensive unit tests (85%+ coverage)
- Integration tests
- Performance benchmarks
- Documentation

**Files to Create:**

- `tests/test_time_stretch_processor.py`
- `tests/test_time_stretch_algorithms.py`
- `tests/test_time_stretch_selector.py`
- `tests/ui/test_time_stretch_widget.py`
- `docs/TIME_STRETCHING_USER_GUIDE.md`

## 5. Key Implementation Details

### 5.1 Sample Rate Handling

**Critical Constraint:**

- All stems are at 44100 Hz (`TARGET_SAMPLE_RATE` in `core/separator.py`)
- Time-stretching must preserve sample rate
- No resampling needed (simplifies implementation)

**Implementation:**

```python
# In TimeStretchProcessor
def process_stem(self, stem_path: Path, speed: float) -> np.ndarray:
    audio_data, sr = sf.read(str(stem_path), always_2d=True)
    assert sr == 44100, "Stem must be at 44100 Hz"
    
    # Time-stretch (preserves sample rate)
    stretched = self._stretch_audio(audio_data, speed)
    
    return stretched  # Still 44100 Hz
```

### 5.2 Chunking Compatibility

**Challenge:**

- Long files are chunked during separation (`core/chunk_processor.py`)
- Time-stretching should work on final merged stems, not chunks
- No special handling needed (stems are already merged)

**Implementation:**

- Time-stretching operates on final stems from `SeparationResult.stems`
- No chunking-specific code required

### 5.3 Memory Management

**Strategy:**

- Process stems sequentially (not all at once)
- Use existing chunking if stems are very long (>5 minutes)
- Stream processing for large files (future enhancement)

**Implementation:**

```python
# Process one stem at a time
for stem_name, stem_path in stems.items():
    speed = config.get_stem_speed(stem_name)
    stretched = self.process_stem(stem_path, speed)
    # Save immediately, don't keep in memory
    output_path = self._save_stretched_stem(stem_name, stretched)
```

### 5.4 Progress Reporting

**Pattern:**

- Use existing `progress_callback(message, percent)` pattern
- Report per-stem progress
- Integrate with GUI progress bars

**Implementation:**

```python
total_stems = len(stems)
for i, (stem_name, stem_path) in enumerate(stems.items()):
    if progress_callback:
        progress_callback(f"Stretching {stem_name}...", 
                         int(100 * i / total_stems))
    # Process stem...
```

## 6. Testing Strategy

### 6.1 Unit Tests

**Coverage Targets:**

- `TimeStretchProcessor`: 90%+
- `AlgorithmSelector`: 100%
- Algorithm implementations: 85%+

**Test Cases:**

- Speed factor validation (0.5x - 2.0x)
- Sample rate preservation
- Error handling (missing libraries, invalid files)
- Algorithm selection logic
- Config validation

### 6.2 Integration Tests

**Test Scenarios:**

- Separation → Time-stretch → Export workflow
- GUI → Processing → Export workflow
- Settings persistence
- License acceptance flow

### 6.3 Audio Quality Tests

**Methodology:**

- Subjective listening tests (5+ testers)
- Objective metrics (SDR, spectral analysis)
- Sync verification (all stems remain synchronized)

**Test Files:**

- Short stems (<1 minute)
- Medium stems (3-5 minutes)
- Long stems (>10 minutes)
- Various content types (vocals, drums, bass, other)

## 7. License Compliance

### 7.1 MIT Libraries (Primary)

**audiotsm:**

- No special handling needed
- Include in main `requirements.txt`

### 7.2 GPLv2 Libraries (Optional)

**pylibrb/rubberband:**

- Separate installation instructions
- License acceptance dialog on first use
- Store acceptance in `user_settings.json`
- Clear documentation about GPLv2 implications

**Implementation:**

```python
# In TimeStretchProcessor.__init__
if RUBBERBAND_AVAILABLE:
    if not self._check_license_acceptance():
        # Show dialog, store acceptance
        self._request_license_acceptance()
```

## 8. Documentation Requirements

### 8.1 User Documentation

**Sections:**

1. Quick Start (preset usage)
2. Advanced Usage (per-stem control)
3. Algorithm Selection (WSOLA vs Rubber Band)
4. License Information (GPLv2 implications)
5. Troubleshooting

**File:** `docs/TIME_STRETCHING_USER_GUIDE.md`

### 8.2 Developer Documentation

**Sections:**

1. Architecture overview
2. Adding new algorithms
3. Integration with separation pipeline
4. Testing guidelines

**File:** `docs/TIME_STRETCHING_DEVELOPER_GUIDE.md`

## 9. Risk Mitigation

### 9.1 Technical Risks

| Risk | Mitigation |
|------|------------|
| Algorithm quality insufficient | Extensive testing, fallback algorithms |
| Performance too slow | Parallel processing, optimization |
| Memory issues with large files | Sequential processing, chunking support |

### 9.2 License Risks

| Risk | Mitigation |
|------|------------|
| GPLv2 incompatibility | Make optional, clear warnings, separate install |
| User confusion | Clear documentation, license acceptance dialog |

## 10. Success Metrics

### 10.1 Technical Metrics

- Processing time: <2x real-time for 3-minute stems
- Memory usage: <2x input file size
- Error rate: <2% processing failures
- Test coverage: 85%+ for core modules

### 10.2 User Metrics

- Adoption rate: 60% of active users within 3 months
- Quality satisfaction: 4.5/5.0 average rating
- Feature discovery: 40% find via UI exploration

## 11. GUI Workflow & User Experience

### 11.1 Navigation Structure

**Location in Sidebar:**

Time-stretching appears in the **"Export"** section of the sidebar, after "Export Mixed" and "Export Loops" buttons.

```
┌─────────────────────────┐
│  SIDEBAR                │
├─────────────────────────┤
│  Input                  │
│  [Upload] [Record]      │
├─────────────────────────┤
│  Processing             │
│  [Queue]                │
├─────────────────────────┤
│  Monitoring             │
│  [Stems] [Playback]     │
├─────────────────────────┤
│  Export                 │
│  [Export Mixed]         │
│  [Export Loops]         │
│  [Time-Stretch]  ← NEW  │
└─────────────────────────┘
```

**Implementation:**

- Add button in `ui/main_window.py` at line ~207 (after Export Loops)
- Widget added to `_content_stack` at index 6
- Follows same pattern as `ExportMixedWidget` and `ExportLoopsWidget`

### 11.2 Complete User Workflow

#### **Step 1: Separation (Existing)**

1. User uploads audio file → `UploadWidget`
2. File added to queue → `QueueWidget`
3. Separation runs → creates stems in `temp/separated/`
4. Stems loaded into `PlayerWidget` for playback

#### **Step 2: Access Time-Stretching**

1. User clicks **"Time-Stretch"** button in sidebar
2. `TimeStretchWidget` is displayed (index 6 in content stack)
3. Widget checks if stems are loaded:
   - **If stems loaded:** Shows controls, enables processing
   - **If no stems:** Shows message "Please load stems first" (similar to export widgets)

#### **Step 3: Configure Time-Stretching**

**Widget Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Time-Stretching                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Processing Mode:                                   │
│  ○ Offline (Best Quality)                          │
│  ● Real-time Preview (Fast)                        │
│                                                     │
│  Global Speed:                                      │
│  [========●========] 1.00x                         │
│  Apply to all stems                                │
│                                                     │
│  Per-Stem Override:                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ ☐ Vocals  [========●========] 1.00x [WSOLA]│   │
│  │ ☐ Drums   [========●========] 1.00x [WSOLA]│   │
│  │ ☐ Bass    [========●========] 1.00x [RB]   │   │
│  │ ☐ Other   [========●========] 1.00x [RB]   │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Presets:                                           │
│  [Faster +5%] [Slower -25%] [Half 0.5x] [Custom]  │
│                                                     │
│  Quality Options:                                   │
│  ☑ Auto-normalize (prevent clipping)                │
│                                                     │
│  Actions:                                           │
│  [Preview] [Process Stems] [Cancel]                 │
│                                                     │
│  Progress: [████████░░] 80% Processing...           │
└─────────────────────────────────────────────────────┘
```

**User Actions:**

1. **Select Processing Mode:**
   - Offline: Best quality, slower (for final export)
   - Real-time: Lower quality, faster (for preview)

2. **Set Speed:**
   - **Option A:** Use global speed slider (applies to all stems)
   - **Option B:** Enable per-stem override, adjust individual sliders
   - **Option C:** Click preset button (Faster, Slower, Half, Double)

3. **Configure Options:**
   - Enable/disable auto-normalize
   - View algorithm selection (read-only, auto-selected per stem)

#### **Step 4: Preview (Optional)**

1. User clicks **"Preview"** button
2. Widget loads original stems from `PlayerWidget.stem_files`
3. Applies time-stretching in real-time mode (fast, lower quality)
4. Plays stretched stems through existing `PlayerWidget` playback system
5. User can adjust settings and preview again

**Implementation:**

- `TimeStretchWidget` has reference to `PlayerWidget` (like `ExportMixedWidget`)
- Preview creates temporary stretched stems in `temp/time_stretch_preview/`
- Loads preview stems into player temporarily
- Restores original stems after preview ends

#### **Step 5: Process Stems**

1. User clicks **"Process Stems"** button
2. Widget validates settings:
   - Speed factors in range (0.5x - 2.0x)
   - At least one stem has non-1.0x speed
   - Stems are loaded

3. **Processing Flow:**
   ```
   User clicks "Process Stems"
   ↓
   Show progress dialog (modal or embedded)
   ↓
   For each stem:
     - Select algorithm (WSOLA for drums, Rubber Band for vocals/bass/other)
     - Load stem audio
     - Apply time-stretching
     - Save to temp/time_stretch/stem_name_1.05x.wav
     - Update progress (20%, 40%, 60%, 80%)
   ↓
   Store stretched stems in PlayerWidget.stretched_stems (new dict)
   ↓
   Show success message
   ↓
   Enable "Export Stretched" option in Export widgets
   ```

4. **Progress Reporting:**
   - Progress bar updates per stem
   - Status message: "Stretching Vocals... (1/4)"
   - Cancel button available (stops processing, cleans up)

5. **Result Storage:**
   - Stretched stems saved to `temp/time_stretch/`
   - Paths stored in `PlayerWidget.stretched_stems: Dict[str, Path]`
   - Original stems remain unchanged in `PlayerWidget.stem_files`

#### **Step 6: Export Stretched Stems**

1. User navigates to **"Export Mixed"** or **"Export Loops"**
2. Export widgets detect stretched stems available
3. Show checkbox: **"Use time-stretched stems"**
4. If checked, export uses `PlayerWidget.stretched_stems` instead of `PlayerWidget.stem_files`
5. Export proceeds normally with stretched stems

**Integration Points:**

- `ExportMixedWidget._update_export_button_state()` checks for stretched stems
- `ExportMixedWidget._execute_export()` uses stretched stems if option enabled
- Same pattern for `ExportLoopsWidget`

### 11.3 Widget State Management

**State Variables:**

```python
class TimeStretchWidget(QWidget):
    def __init__(self, player_widget=None, parent=None):
        # References
        self.player_widget = player_widget
        self.stems_loaded = False
        
        # Configuration
        self.processing_mode = "offline"  # "offline" or "realtime"
        self.global_speed = 1.0
        self.stem_speeds = {
            "vocals": 1.0,
            "drums": 1.0,
            "bass": 1.0,
            "other": 1.0
        }
        self.use_global = True
        self.auto_normalize = True
        
        # Processing state
        self.is_processing = False
        self.stretched_stems = {}  # Dict[str, Path]
```

**State Transitions:**

1. **Initial:** No stems loaded → Disabled controls, show message
2. **Stems Loaded:** Enable controls, show current speeds (1.0x)
3. **Processing:** Disable controls, show progress, allow cancel
4. **Complete:** Enable controls, show success, enable export option
5. **Error:** Show error message, restore controls, allow retry

### 11.4 Integration with PlayerWidget

**New Methods in PlayerWidget:**

```python
class PlayerWidget(QWidget):
    # Existing: self.stem_files: Dict[str, Path]
    
    # New: Stretched stems storage
    self.stretched_stems: Optional[Dict[str, Path]] = None
    
    def has_stretched_stems(self) -> bool:
        """Check if time-stretched stems are available"""
        return self.stretched_stems is not None and len(self.stretched_stems) > 0
    
    def get_stems_for_export(self, use_stretched: bool = False) -> Dict[str, Path]:
        """Get stems for export (original or stretched)"""
        if use_stretched and self.has_stretched_stems():
            return self.stretched_stems
        return self.stem_files
    
    def clear_stretched_stems(self):
        """Clear stretched stems (when new separation loaded)"""
        self.stretched_stems = None
```

**Signal Connections:**

- `TimeStretchWidget` connects to `PlayerWidget.stems_loaded_changed` signal
- When stems are cleared in PlayerWidget, TimeStretchWidget resets
- When new stems loaded, TimeStretchWidget enables controls

### 11.5 Export Widget Integration

**ExportMixedWidget Changes:**

```python
class ExportMixedWidget(QWidget):
    def _setup_ui(self):
        # ... existing UI ...
        
        # NEW: Time-stretch option
        self.use_stretched = QCheckBox("Use time-stretched stems")
        self.use_stretched.setEnabled(False)  # Enabled when stretched stems available
        self.use_stretched.setToolTip(
            "Export time-stretched stems instead of original stems"
        )
        # Add to UI layout
        
    def _update_export_button_state(self):
        # Check if stretched stems available
        has_stretched = (
            self.player_widget 
            and self.player_widget.has_stretched_stems()
        )
        self.use_stretched.setEnabled(has_stretched)
        
        # Update preview text to show which stems will be exported
        
    def _execute_export(self, output_path: Path, settings: ExportSettings):
        # Get stems (original or stretched)
        use_stretched = self.use_stretched.isChecked()
        stems = self.player_widget.get_stems_for_export(use_stretched)
        
        # Export proceeds with selected stems
        # ... existing export logic ...
```

### 11.6 Error Handling & User Feedback

**Error Scenarios:**

1. **No stems loaded:**
   - Show message: "Please load stems first. Go to Monitoring → Stems to load separated audio."
   - Disable all controls except info message

2. **Processing fails:**
   - Show error dialog with details
   - Allow retry with same settings
   - Clean up partial files

3. **Library unavailable:**
   - If Rubber Band requested but unavailable: Fallback to WSOLA, show warning
   - If audiotsm unavailable: Show error, suggest installation

4. **Invalid speed factor:**
   - Validate on slider change
   - Show tooltip/warning if out of range
   - Disable "Process" button if invalid

**Success Feedback:**

- Progress bar completes (100%)
- Success message: "Time-stretching complete! 4 stems processed."
- Export widgets automatically show "Use time-stretched stems" option
- Visual indicator in widget (green checkmark, success icon)

### 11.7 Settings Persistence

**Stored in user_settings.json:**

```json
{
  "time_stretching": {
    "default_mode": "offline",
    "default_speed": 1.0,
    "auto_normalize": true,
    "presets": {
      "faster": {"speed": 1.05, "description": "DJ mixing, +5% BPM"},
      "slower": {"speed": 0.75, "description": "Practice mode, -25% tempo"}
    },
    "rubberband_license_accepted": false
  }
}
```

**Load on widget init:**

- Load defaults from `SettingsManager`
- Restore last used speeds (optional, could be per-session only)
- Load preset definitions

**Save on changes:**

- Save preset customizations
- Save license acceptance
- Save default mode preference

## 12. Open Questions & Decisions

### 12.1 GUI Location

**Question:** Where should time-stretching controls appear?

**Recommendation:** New navigation button in main window sidebar (similar to "Export Mixed", "Export Loops")

**Rationale:**

- Clear separation of concerns
- Consistent with existing UI patterns
- Easy to discover

### 12.2 Default Behavior

**Question:** Opt-in or opt-out?

**Recommendation:** Opt-in (default disabled, speed = 1.0x)

**Rationale:**

- Backward compatibility
- User control
- Matches PRD recommendation

### 12.3 Preset System

**Question:** How many presets initially?

**Recommendation:** 5 presets (Faster +5%, Slower -25%, Half 0.5x, Double 2.0x, Custom)

**Rationale:**

- Covers common use cases
- Not overwhelming for users
- Extensible for future presets

---

**End of Document**

