# Product Requirements Document: Stem-Specific Time-Stretching

**Version:** 1.0  
**Date:** 2025-01-XX  
**Status:** Draft  
**Author:** Technical Product Manager  
**Repository:** StemSeparator  
**Feature:** Time-Stretching Integration for Separated Audio Stems

---

## 1. Executive Summary

**What:** Integration of stem-specific time-stretching algorithms into the Stem Separator application, allowing users to independently adjust playback speed (0.5x–2.0x) for each separated stem (Vocals, Drums, Bass, Other) using algorithm-optimized processing methods.

**Why:** Enables DJs to match BPMs for mixing, music students to practice at slower tempos, and producers to experiment with tempo variations without pitch changes. Each stem type requires different time-stretching algorithms for optimal quality (e.g., WSOLA for percussive content, Rubber Band for harmonic content).

**For Whom:** Music producers, DJs, music students, remix artists, and audio engineers who need tempo control while maintaining audio quality and pitch accuracy.

---

## 2. Problem Statement

### Current Limitations

1. **No Tempo Control:** Users cannot adjust playback speed of separated stems, limiting use cases for DJ mixing, practice, and creative remixing.
2. **Pitch-Shift Coupling:** Traditional speed changes alter pitch, making stems unusable for professional mixing.
3. **One-Size-Fits-All:** Different audio content types (percussive vs. harmonic) require different algorithms for optimal quality, but current tools don't differentiate.

### User Pain Points

- **DJs:** Cannot match BPMs between tracks for seamless mixing
- **Music Students:** Cannot slow down complex passages for practice
- **Producers:** Cannot experiment with tempo variations without re-recording
- **Remix Artists:** Limited creative options for tempo manipulation

### Market Context

Competing tools (iZotope RX, Serato Pitch'n Time, Ableton Live) offer time-stretching but:
- Require expensive licenses
- Don't integrate with stem separation workflows
- Don't offer stem-specific algorithm selection
- Lack offline processing modes for maximum quality

---

## 3. Goals & Success Metrics

### Primary Goals

1. **Quality:** Achieve transparent time-stretching (±5% speed change) with <1% audible artifacts
2. **Usability:** 80% of users successfully apply time-stretching without reading documentation
3. **Performance:** Offline processing completes within 2x real-time duration for typical 3-minute stems
4. **Adoption:** 60% of active users utilize time-stretching within 3 months of release

### Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| User Adoption Rate | 60% of active users | Analytics tracking (opt-in) |
| Quality Satisfaction | 4.5/5.0 average rating | Post-processing survey |
| Processing Time | <2x real-time for 3min audio | Performance benchmarks |
| Error Rate | <2% processing failures | Error logging |
| Feature Discovery | 40% find via UI exploration | User testing |

### Definition of Done

- [ ] All stems support independent time-stretching (0.5x–2.0x)
- [ ] Algorithm selection automatic based on stem type
- [ ] GUI and CLI interfaces functional
- [ ] Preset system with 5+ common use cases
- [ ] Unit tests achieve 85%+ coverage
- [ ] Documentation complete (user guide + API docs)
- [ ] Performance benchmarks meet targets
- [ ] License compliance verified (GPLv2 compatibility)

---

## 4. User Stories

### User Story 1: DJ BPM Matching
**As a** DJ  
**I want to** time-stretch separated stems to match my DJ set's BPM (e.g., 128 BPM)  
**So that** I can seamlessly mix tracks without pitch artifacts or tempo mismatches.

**Acceptance Criteria:**
- Can set global speed factor (e.g., 1.05x for +5% BPM)
- All stems stretched proportionally
- Pitch remains unchanged
- Processing completes in <30 seconds for 3-minute track
- Exported stems maintain sync

**Priority:** Must Have

---

### User Story 2: Music Student Practice Mode
**As a** music student  
**I want to** slow down complex drum patterns to 0.75x speed  
**So that** I can learn intricate rhythms by practicing at a manageable tempo.

**Acceptance Criteria:**
- Can set drums stem to 0.75x independently
- Other stems remain at 1.0x (or can be adjusted separately)
- Audio quality remains clear at slower speeds
- No pitch artifacts or "warbling" sounds
- Can export slowed stems for practice

**Priority:** Must Have

---

### User Story 3: Producer Tempo Experimentation
**As a** music producer  
**I want to** experiment with different tempo variations per stem (vocals +5%, drums -3%)  
**So that** I can create unique remix variations and find optimal tempo combinations.

**Acceptance Criteria:**
- Independent speed control per stem (0.5x–2.0x range)
- Real-time preview before export
- A/B comparison mode (original vs. stretched)
- Export stretched stems with clear naming convention
- Preset system for common variations

**Priority:** Should Have

---

### User Story 4: Audio Engineer Quality Control
**As an** audio engineer  
**I want to** use high-quality offline processing with Rubber Band R3 engine  
**So that** I can achieve maximum quality for critical projects without real-time constraints.

**Acceptance Criteria:**
- Offline mode uses Rubber Band R3 engine (highest quality)
- Processing time acceptable for batch operations
- Quality metrics logged (clipping detection, distortion analysis)
- Auto-normalize option to prevent clipping
- Export quality reports

**Priority:** Should Have

---

### User Story 5: Casual User Quick Adjustment
**As a** casual user  
**I want to** quickly apply a "Faster" or "Slower" preset  
**So that** I can adjust tempo without understanding technical parameters.

**Acceptance Criteria:**
- One-click preset buttons ("Faster", "Slower", "Custom")
- Presets apply sensible defaults (e.g., +5% for "Faster")
- Clear visual feedback (slider updates, preview available)
- No technical jargon in UI
- Help tooltips explain presets

**Priority:** Could Have

---

## 5. Functional Requirements

### 5.1 Core Functionality

#### FR-1: Stem-Specific Algorithm Selection (Must Have)
**Description:** Automatically select optimal time-stretching algorithm based on stem type.

| Stem Type | Algorithm | Library | Rationale |
|-----------|-----------|---------|-----------|
| Drums | WSOLA | `audiotsm` | Preserves transient attacks, minimal artifacts on percussive content |
| Vocals | Rubber Band (OptionDetectorSoft/Compound) | `rubberband` | Maintains vocal clarity, handles formants correctly |
| Bass | Rubber Band R3 (OptionTransientsSmooth) | `rubberband` | Smooth harmonic content, preserves low-frequency integrity |
| Other | Rubber Band R3 (OptionTransientsSmooth) | `rubberband` | General harmonic content benefits from R3 engine |

**Implementation Notes:**
- Algorithm selection occurs automatically during processing
- User can override via advanced settings (Could Have)
- Fallback to WSOLA if Rubber Band unavailable (license issues)

**Priority:** Must Have

---

#### FR-2: Speed Range & Precision (Must Have)
**Description:** Support speed factors from 0.5x to 2.0x with 0.01x precision.

**Requirements:**
- Minimum speed: 0.5x (half speed)
- Maximum speed: 2.0x (double speed)
- Precision: 0.01x increments (e.g., 1.05x, 1.23x)
- Default: 1.0x (no stretching)

**Validation:**
- Input validation prevents values outside 0.5x–2.0x range
- Error message if invalid range entered
- Slider constraints enforce limits in GUI

**Priority:** Must Have

---

#### FR-3: Independent Per-Stem Control (Must Have)
**Description:** Each stem (Vocals, Drums, Bass, Other) can have independent speed factor.

**Requirements:**
- Separate speed control per stem
- Global speed option (all stems same factor)
- Per-stem override capability
- Visual indication of which stems are stretched

**UI Representation:**
```
┌─────────────────────────────────────┐
│ Time-Stretching Controls            │
├─────────────────────────────────────┤
│ [Global] Speed: [====●====] 1.00x  │
│                                     │
│ Per-Stem Override:                  │
│ ☐ Vocals:  [====●====] 1.00x       │
│ ☐ Drums:   [====●====] 1.00x       │
│ ☐ Bass:    [====●====] 1.00x       │
│ ☐ Other:   [====●====] 1.00x       │
└─────────────────────────────────────┘
```

**Priority:** Must Have

---

#### FR-4: Processing Modes (Must Have)
**Description:** Support offline (quality) and real-time preview (speed) modes.

| Mode | Algorithm | Quality | Use Case |
|------|-----------|---------|----------|
| Offline | Rubber Band R3 / WSOLA (full quality) | Maximum | Final export, critical projects |
| Real-time Preview | WSOLA/OLA (fast) | Reduced | Quick preview, experimentation |

**Requirements:**
- Offline mode: Default for export, uses full-quality algorithms
- Real-time mode: Optional preview, lower quality acceptable
- Mode selection in settings/UI
- Clear indication of current mode

**Priority:** Must Have

---

#### FR-5: Preset System (Should Have)
**Description:** Pre-configured speed presets for common use cases.

**Presets:**

| Preset Name | Speed Factor | Description |
|-------------|--------------|-------------|
| Faster | +5% (1.05x) | DJ mixing, upbeat remix |
| Slower | -25% (0.75x) | Practice mode, detailed analysis |
| Half Speed | 0.5x | Extreme slow-motion practice |
| Double Speed | 2.0x | Fast-forward, time-saving |
| Custom | User-defined | Manual adjustment |

**Requirements:**
- Presets apply to all stems (global) or selected stems
- Custom presets can be saved/loaded
- Preset descriptions explain use cases
- Preset buttons in GUI for quick access

**Priority:** Should Have

---

#### FR-6: Export Functionality (Must Have)
**Description:** Export time-stretched stems with clear naming and format options.

**Naming Convention:**
- Original: `Song_(Vocals).wav`
- Stretched: `Song_(Vocals)_1.05x.wav` or `Song_(Vocals)_stretched_1.05x.wav`

**Export Options:**
- Format: WAV (16/24/32-bit), FLAC
- Sample rate: 44100 Hz (default), 48000 Hz (optional)
- Normalize: Auto-normalize to prevent clipping (optional)
- A/B Export: Export both original and stretched versions

**Priority:** Must Have

---

#### FR-7: Quality Assurance Features (Should Have)
**Description:** Automatic detection and handling of audio quality issues.

**Features:**
- Clipping detection: Warn if output exceeds 0 dBFS
- Distortion analysis: Detect artifacts (optional, advanced)
- Auto-normalize: Automatically reduce gain to prevent clipping
- Quality report: Log processing parameters and detected issues

**Priority:** Should Have

---

#### FR-8: A/B Comparison Mode (Could Have)
**Description:** Side-by-side comparison of original vs. stretched audio.

**Requirements:**
- Play original and stretched versions simultaneously
- Switch between versions during playback
- Visual waveform comparison
- Export both versions for external comparison

**Priority:** Could Have

---

### 5.2 User Interface Requirements

#### FR-9: GUI Integration (Must Have)
**Description:** Time-stretching controls integrated into main application window.

**Location:** New tab or section in main window, accessible after separation.

**Components:**
- Speed sliders per stem (0.5x–2.0x range)
- Preset buttons (Faster, Slower, Custom)
- Processing mode selector (Offline/Real-time)
- Preview button (play stretched audio)
- Export button (save stretched stems)
- Progress indicator during processing

**Design Principles:**
- Consistent with existing dark theme
- Clear visual hierarchy
- Accessible (keyboard navigation, screen reader support)
- Responsive (handles long stem names, many stems)

**Priority:** Must Have

---

#### FR-10: CLI Interface (Should Have)
**Description:** Command-line interface for batch processing and automation.

**Command Examples:**
```bash
# Global time-stretch
python main.py --time-stretch 1.05 input.wav

# Per-stem time-stretch
python main.py --vocals-speed 1.05 --drums-speed 0.95 input.wav

# With preset
python main.py --preset faster input.wav

# Batch processing
python main.py --time-stretch 1.05 --batch-dir ./audio_files/
```

**Options:**
- `--time-stretch <factor>`: Global speed factor
- `--vocals-speed <factor>`, `--drums-speed <factor>`, etc.: Per-stem factors
- `--preset <name>`: Apply preset (faster, slower, custom)
- `--mode <offline|realtime>`: Processing mode
- `--output-dir <path>`: Custom output directory
- `--normalize`: Auto-normalize output

**Priority:** Should Have

---

### 5.3 Configuration & Settings

#### FR-11: Config File Support (Should Have)
**Description:** YAML/JSON configuration for presets and default settings.

**Config Structure:**
```yaml
time_stretching:
  default_mode: "offline"
  default_speed: 1.0
  presets:
    faster:
      speed: 1.05
      description: "DJ mixing, +5% BPM"
    slower:
      speed: 0.75
      description: "Practice mode, -25% tempo"
  algorithm_overrides:
    drums: "wsola"  # Optional: override auto-selection
    vocals: "rubberband"
  quality:
    auto_normalize: true
    clipping_threshold: 0.0  # dBFS
```

**Requirements:**
- Config file: `user_settings.json` (extends existing)
- Preset storage: User-defined presets saved to config
- Defaults: Sensible defaults for new users
- Validation: Config validation on load

**Priority:** Should Have

---

## 6. Technical Requirements

### 6.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Stem Separator                        │
│  ┌──────────────┐         ┌──────────────────────────┐ │
│  │  Separator   │────────▶│  Time-Stretch Processor   │ │
│  │  (Existing)  │         │  (New Component)          │ │
│  └──────────────┘         └──────────────────────────┘ │
│                                │                         │
│                                ▼                         │
│                    ┌───────────────────────┐              │
│                    │  Algorithm Selector  │              │
│                    │  (Stem → Algorithm)  │              │
│                    └───────────────────────┘              │
│                                │                         │
│        ┌───────────────────────┼───────────────────────┐ │
│        ▼                       ▼                       ▼ │
│  ┌──────────┐          ┌──────────────┐        ┌──────┐ │
│  │  WSOLA   │          │ Rubber Band  │        │ OLA  │ │
│  │ (audiotsm)│          │  (rubberband)│        │(fallback)│ │
│  └──────────┘          └──────────────┘        └──────┘ │
└─────────────────────────────────────────────────────────┘
```

**Component Responsibilities:**
- **Time-Stretch Processor:** Main orchestrator, handles stem processing pipeline
- **Algorithm Selector:** Maps stem types to optimal algorithms
- **Algorithm Implementations:** WSOLA (audiotsm), Rubber Band (rubberband), OLA (fallback)

---

### 6.2 Library Integration

#### TR-1: Dependency Management

**New Dependencies:**

| Library | Version | License | Purpose | Priority |
|---------|---------|---------|---------|----------|
| `audiotsm` | >=0.1.2 | MIT | WSOLA algorithm for drums | Must Have |
| `rubberband` | >=3.0.0 | GPLv2 | High-quality time-stretching | Must Have |
| `pylibrb` | >=0.1.0 | GPLv2 | Python bindings for Rubber Band | Must Have (alternative) |

**License Considerations:**
- **GPLv2 Compatibility:** Rubber Band is GPLv2, which requires derivative works to be GPLv2
- **Current License:** Stem Separator uses MIT license (per README)
- **Resolution Options:**
  1. **Option A:** Switch entire project to GPLv2 (requires approval)
  2. **Option B:** Use Rubber Band as optional dependency, fallback to MIT-licensed alternatives
  3. **Option C:** Use commercial Rubber Band license (paid, not feasible for open-source)
  4. **Option D:** Implement Rubber Band as separate GPLv2-licensed plugin/module

**Recommendation:** **Option B** - Make Rubber Band optional, use `audiotsm` (MIT) as primary, with clear documentation about license implications if Rubber Band is installed.

**Fallback Strategy:**
- Primary: `audiotsm` (MIT) for all stems (acceptable quality)
- Enhanced: `rubberband` (GPLv2) for vocals/bass/other (if installed, user accepts GPLv2)
- Detection: Check library availability at runtime, warn user about license if GPLv2 library used

**Priority:** Must Have (with license mitigation)

---

#### TR-2: API Design

**Core API:**
```python
from core.time_stretch import TimeStretchProcessor, TimeStretchConfig

# Initialize processor
processor = TimeStretchProcessor()

# Configure stretching
config = TimeStretchConfig(
    global_speed=1.05,  # Optional: apply to all stems
    stem_speeds={
        "vocals": 1.05,
        "drums": 0.95,
        "bass": 1.0,
        "other": 1.0
    },
    mode="offline",  # "offline" or "realtime"
    auto_normalize=True,
    algorithm_overrides={}  # Optional: override auto-selection
)

# Process stems
result = processor.process_stems(
    stems={
        "vocals": Path("song_(Vocals).wav"),
        "drums": Path("song_(Drums).wav"),
        "bass": Path("song_(Bass).wav"),
        "other": Path("song_(Other).wav")
    },
    output_dir=Path("output/"),
    config=config,
    progress_callback=lambda msg, pct: print(f"{pct}%: {msg}")
)

# Result contains paths to stretched stems
print(result.stretched_stems)  # Dict[str, Path]
```

**Error Handling:**
- `TimeStretchError`: Base exception for time-stretching failures
- `AlgorithmNotFoundError`: Required algorithm library missing
- `InvalidSpeedFactorError`: Speed factor outside valid range
- `ProcessingError`: Runtime processing failure

**Priority:** Must Have

---

#### TR-3: Integration Points

**Integration with Existing Components:**

1. **Separator Integration:**
   - Add optional time-stretch step after separation
   - Extend `SeparationResult` to include stretched stems (optional)
   - Maintain backward compatibility (time-stretching opt-in)

2. **Player Integration:**
   - Preview stretched stems in existing player widget
   - Load stretched stems alongside original stems
   - A/B comparison mode (if implemented)

3. **Export Integration:**
   - Extend export widgets to include time-stretch options
   - Add time-stretch controls to export dialogs
   - Maintain existing export functionality

4. **Settings Integration:**
   - Add time-stretch settings to `settings_manager.py`
   - Store presets in user settings
   - Config file support (YAML/JSON)

**Priority:** Must Have

---

#### TR-4: Performance Requirements

**Processing Time Targets:**

| Audio Length | Offline Mode | Real-time Mode |
|--------------|--------------|----------------|
| 1 minute | <2 minutes | <10 seconds |
| 3 minutes | <6 minutes | <30 seconds |
| 5 minutes | <10 minutes | <50 seconds |

**Resource Usage:**
- Memory: <2x input file size (temporary buffers)
- CPU: Multi-threaded processing (one thread per stem)
- Disk: Temporary files cleaned up after processing

**Optimization Strategies:**
- Parallel processing: Process stems concurrently (multiprocessing)
- Chunked processing: For very long files, process in chunks
- Caching: Cache algorithm instances (avoid re-initialization)

**Priority:** Should Have

---

#### TR-5: Backward Compatibility

**Requirements:**
- Time-stretching is **opt-in** (default: disabled, speed = 1.0x)
- Existing separation workflow unchanged
- No breaking changes to existing APIs
- Existing exports continue to work without time-stretching

**Migration Path:**
- Feature flag: `ENABLE_TIME_STRETCHING = True` in config
- Gradual rollout: Feature hidden behind advanced settings initially
- User opt-in: Clear UI indication that time-stretching is experimental (if needed)

**Priority:** Must Have

---

## 7. UI/UX Mockup Description

### 7.1 GUI Layout

**Location:** New "Time-Stretch" tab in main window, or section in existing "Export" tab.

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Stem Separator                    [Upload] [Player] [Export]│
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Time-Stretching Controls                                     │
│  ─────────────────────────────────────────────────────────  │
│                                                               │
│  Processing Mode:  ○ Offline (Best Quality)                 │
│                    ● Real-time Preview (Fast)                │
│                                                               │
│  Global Speed:     [========●========] 1.00x                 │
│                    Apply to all stems                        │
│                                                               │
│  Per-Stem Override:                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ ☐ Vocals  [========●========] 1.00x  [WSOLA]       │    │
│  │ ☐ Drums   [========●========] 1.00x  [WSOLA]       │    │
│  │ ☐ Bass    [========●========] 1.00x  [Rubber Band] │    │
│  │ ☐ Other   [========●========] 1.00x  [Rubber Band] │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Presets:  [Faster +5%] [Slower -25%] [Half 0.5x] [Custom]  │
│                                                               │
│  Quality Options:                                             │
│  ☑ Auto-normalize (prevent clipping)                         │
│  ☐ A/B Comparison Mode                                        │
│                                                               │
│  Actions:                                                     │
│  [Preview] [Export Stretched Stems] [Cancel]                 │
│                                                               │
│  Progress: [████████░░] 80% Processing...                   │
└─────────────────────────────────────────────────────────────┘
```

**Design Notes:**
- Dark theme consistent with existing UI
- Sliders with numeric input fields (dual control)
- Algorithm indicator shows selected algorithm per stem
- Preset buttons with clear labels
- Progress bar during processing
- Tooltips explain each control

---

### 7.2 CLI Command Examples

**Basic Usage:**
```bash
# Separate and time-stretch in one command
python main.py separate input.wav --time-stretch 1.05

# Separate first, then time-stretch separately
python main.py separate input.wav
python main.py time-stretch input_separated/ --global-speed 1.05

# Per-stem control
python main.py time-stretch input_separated/ \
    --vocals-speed 1.05 \
    --drums-speed 0.95 \
    --bass-speed 1.0 \
    --other-speed 1.0

# With preset
python main.py time-stretch input_separated/ --preset faster

# Batch processing
python main.py time-stretch --batch-dir ./separated_tracks/ --global-speed 1.05

# Export options
python main.py time-stretch input_separated/ --global-speed 1.05 \
    --output-dir ./stretched/ \
    --format wav \
    --bit-depth 24 \
    --normalize
```

**Help Output:**
```bash
$ python main.py time-stretch --help

Usage: python main.py time-stretch [OPTIONS] INPUT_DIR

Time-stretch separated audio stems.

Options:
  --global-speed FLOAT       Global speed factor (0.5-2.0, default: 1.0)
  --vocals-speed FLOAT       Vocals speed factor (overrides global)
  --drums-speed FLOAT        Drums speed factor (overrides global)
  --bass-speed FLOAT         Bass speed factor (overrides global)
  --other-speed FLOAT        Other speed factor (overrides global)
  --preset TEXT              Preset name (faster, slower, half, double, custom)
  --mode [offline|realtime]  Processing mode (default: offline)
  --output-dir PATH          Output directory (default: input_dir/stretched)
  --format [wav|flac]        Output format (default: wav)
  --bit-depth [16|24|32]     Bit depth (default: 16)
  --normalize                Auto-normalize to prevent clipping
  --batch-dir PATH           Process all stems in directory
  --help                     Show this message
```

---

## 8. Non-Functional Requirements

### 8.1 Performance

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Processing Speed | <2x real-time (offline) | Benchmark 3-minute stems |
| Memory Usage | <2x input file size | Memory profiling |
| CPU Utilization | Multi-threaded (parallel stems) | CPU monitoring |
| Startup Time | <100ms initialization | Performance profiling |

**Priority:** Should Have

---

### 8.2 Quality

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Artifact Level | <1% audible artifacts at ±5% | Subjective listening tests |
| Pitch Accuracy | 0% pitch change (by design) | Frequency analysis |
| Transient Preservation | >90% transient clarity (drums) | Transient detection algorithms |
| Harmonic Preservation | >95% harmonic content (vocals/bass) | Spectral analysis |

**Priority:** Must Have

---

### 8.3 Reliability

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Error Rate | <2% processing failures | Error logging |
| Crash Rate | <0.1% crashes per session | Crash reporting |
| Data Loss | 0% (all stems preserved) | File integrity checks |
| Recovery | Graceful degradation (fallback algorithms) | Error handling tests |

**Priority:** Must Have

---

### 8.4 Usability

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Learning Curve | <5 minutes to first use | User testing |
| Error Messages | Clear, actionable error messages | UX review |
| Accessibility | WCAG 2.1 AA compliance | Accessibility audit |
| Documentation | Complete user guide + API docs | Documentation review |

**Priority:** Should Have

---

### 8.5 Security & Privacy

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Data Privacy | No audio data transmitted externally | Code audit |
| License Compliance | GPLv2 compatibility verified | Legal review |
| Dependency Security | No known vulnerabilities | Security scanning |

**Priority:** Must Have

---

## 9. Dependencies & Risks

### 9.1 External Dependencies

**Critical Dependencies:**

| Dependency | Risk Level | Mitigation |
|------------|------------|------------|
| `audiotsm` (MIT) | Low | Well-maintained, MIT license compatible |
| `rubberband` (GPLv2) | **High** | License conflict with MIT project, make optional |
| `pylibrb` (GPLv2) | **High** | License conflict, use as optional alternative |
| NumPy, soundfile (existing) | Low | Already in dependencies |

**License Risk Mitigation:**
1. **Primary Path:** Use `audiotsm` (MIT) for all stems (acceptable quality)
2. **Enhanced Path:** Make Rubber Band optional, clear GPLv2 warning if installed
3. **Documentation:** Explain license implications in user guide
4. **Build System:** Separate GPLv2 components in optional install script

**Priority:** Must Have (risk mitigation)

---

### 9.2 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|------------|
| Algorithm quality insufficient | High | Medium | Extensive testing, fallback algorithms |
| Performance too slow | Medium | Low | Parallel processing, optimization |
| License incompatibility | High | High | Make GPLv2 optional, use MIT alternatives |
| User confusion (too many options) | Medium | Medium | Preset system, clear defaults |
| Integration complexity | Medium | Low | Phased rollout, extensive testing |

**Priority:** Must Have (risk assessment)

---

### 9.3 Known Algorithm Limitations

**WSOLA (audiotsm):**
- **Limitation:** Artifacts at extreme speeds (<0.7x or >1.5x)
- **Mitigation:** Warn user, suggest Rubber Band for extreme speeds
- **Use Case:** Best for drums, acceptable for other stems

**Rubber Band:**
- **Limitation:** Slower processing, GPLv2 license
- **Mitigation:** Optional dependency, offline mode only
- **Use Case:** Best for vocals, bass, harmonic content

**OLA (fallback):**
- **Limitation:** Lower quality, more artifacts
- **Mitigation:** Only used if other libraries unavailable
- **Use Case:** Emergency fallback

**Priority:** Should Have (documentation)

---

## 10. Implementation Plan

### Phase 1: MVP (4-6 weeks)

**Goal:** Basic time-stretching with single algorithm (WSOLA), global speed control.

**Deliverables:**
- [ ] Core `TimeStretchProcessor` class
- [ ] WSOLA integration (`audiotsm`)
- [ ] Global speed control (all stems same factor)
- [ ] Basic GUI integration (slider + export button)
- [ ] CLI interface (`--time-stretch` flag)
- [ ] Unit tests (70%+ coverage)
- [ ] Basic documentation

**Success Criteria:**
- Can time-stretch all stems with single speed factor
- Processing completes without errors
- Exported stems play correctly

**Priority:** Must Have

---

### Phase 2: Stem-Specific Algorithms (3-4 weeks)

**Goal:** Algorithm selection per stem, Rubber Band integration (optional).

**Deliverables:**
- [ ] Algorithm selector (stem type → algorithm mapping)
- [ ] Rubber Band integration (optional, GPLv2 warning)
- [ ] Per-stem speed control in GUI
- [ ] Algorithm indicators in UI
- [ ] Enhanced error handling
- [ ] Unit tests (85%+ coverage)

**Success Criteria:**
- Drums use WSOLA, vocals use Rubber Band (if available)
- Per-stem controls functional
- Fallback to WSOLA if Rubber Band unavailable

**Priority:** Must Have

---

### Phase 3: Presets & Quality Features (2-3 weeks)

**Goal:** Preset system, quality assurance, A/B comparison.

**Deliverables:**
- [ ] Preset system (5+ presets)
- [ ] Config file support (YAML/JSON)
- [ ] Clipping detection & auto-normalize
- [ ] A/B comparison mode (if time permits)
- [ ] Quality reports
- [ ] User documentation

**Success Criteria:**
- Presets work correctly
- Auto-normalize prevents clipping
- Config file loads/saves presets

**Priority:** Should Have

---

### Phase 4: Optimization & Polish (2-3 weeks)

**Goal:** Performance optimization, UI polish, comprehensive testing.

**Deliverables:**
- [ ] Parallel processing (multiprocessing)
- [ ] Performance benchmarks meet targets
- [ ] UI/UX improvements (tooltips, help text)
- [ ] Comprehensive integration tests
- [ ] Documentation complete (user guide + API)
- [ ] License compliance verification

**Success Criteria:**
- Processing time <2x real-time
- All tests pass (85%+ coverage)
- Documentation complete

**Priority:** Should Have

---

### Phase 5: Real-time Preview (Optional, 2-3 weeks)

**Goal:** Real-time preview mode for experimentation.

**Deliverables:**
- [ ] Real-time processing mode (lower quality, faster)
- [ ] Preview player integration
- [ ] UI controls for real-time mode
- [ ] Performance optimization for real-time

**Success Criteria:**
- Preview plays within 10 seconds for 3-minute track
- Quality acceptable for preview (not final export)

**Priority:** Could Have

---

## 11. Testing Strategy

### 11.1 Unit Tests

**Test Coverage Target:** 85%+

**Test Areas:**
- `TimeStretchProcessor`: Core processing logic
- `AlgorithmSelector`: Stem → algorithm mapping
- `WSOLAProcessor`: WSOLA implementation
- `RubberBandProcessor`: Rubber Band implementation (if available)
- `ConfigParser`: Config file loading/saving
- `PresetManager`: Preset application

**Test Cases:**
```python
def test_time_stretch_processor_global_speed():
    """Test global speed factor application"""
    processor = TimeStretchProcessor()
    config = TimeStretchConfig(global_speed=1.05)
    result = processor.process_stems(stems, output_dir, config)
    assert result.success
    assert len(result.stretched_stems) == 4

def test_algorithm_selector_drums_uses_wsola():
    """Test algorithm selection for drums"""
    selector = AlgorithmSelector()
    algorithm = selector.select_algorithm("drums")
    assert algorithm == "wsola"

def test_invalid_speed_factor_raises_error():
    """Test validation of speed factor range"""
    config = TimeStretchConfig(global_speed=3.0)  # Invalid
    with pytest.raises(InvalidSpeedFactorError):
        processor.process_stems(stems, output_dir, config)
```

**Priority:** Must Have

---

### 11.2 Integration Tests

**Test Areas:**
- Separation → Time-stretch workflow
- GUI → Processing pipeline
- CLI → Processing pipeline
- Export → File system

**Test Cases:**
```python
def test_separation_then_time_stretch_workflow():
    """Test complete workflow: separate → time-stretch → export"""
    separator = get_separator()
    result = separator.separate(audio_file)
    assert result.success
    
    processor = TimeStretchProcessor()
    stretch_result = processor.process_stems(result.stems, output_dir)
    assert stretch_result.success
    assert all(path.exists() for path in stretch_result.stretched_stems.values())
```

**Priority:** Must Have

---

### 11.3 Audio Quality Tests

**Test Methodology:**
- Subjective listening tests (5+ testers)
- Objective metrics (SDR, spectral analysis)
- Artifact detection algorithms

**Test Cases:**
- **Transparency Test:** ±5% speed change should be nearly transparent
- **Extreme Speed Test:** 0.5x and 2.0x should have acceptable quality
- **Stem-Specific Test:** Drums preserve transients, vocals preserve formants
- **Sync Test:** All stems remain synchronized after stretching

**Priority:** Should Have

---

### 11.4 Performance Tests

**Benchmark Targets:**
- 1-minute stem: <2 minutes processing (offline)
- 3-minute stem: <6 minutes processing (offline)
- Memory usage: <2x input file size
- CPU utilization: Multi-threaded (parallel stems)

**Test Methodology:**
- Automated benchmarks on standardized test files
- Performance profiling (cProfile, memory_profiler)
- Comparison with baseline (no time-stretching)

**Priority:** Should Have

---

### 11.5 Edge Cases

**Test Cases:**
- Very short stems (<10 seconds)
- Very long stems (>30 minutes)
- Mono vs. stereo stems
- Different sample rates (44100 Hz, 48000 Hz)
- Missing algorithm libraries (fallback behavior)
- Invalid speed factors (validation)
- Corrupted input files (error handling)

**Priority:** Should Have

---

## 12. Documentation Requirements

### 12.1 User Documentation

**User Guide Sections:**
1. **Introduction:** What is time-stretching, why use it
2. **Quick Start:** Basic usage (preset application)
3. **Advanced Usage:** Per-stem control, custom presets
4. **Algorithm Selection:** Explanation of WSOLA vs. Rubber Band
5. **Quality Tips:** Best practices for optimal results
6. **Troubleshooting:** Common issues and solutions
7. **License Information:** GPLv2 implications (if Rubber Band used)

**Format:** Markdown, integrated into existing docs structure.

**Priority:** Must Have

---

### 12.2 API Documentation

**API Docs Sections:**
1. **TimeStretchProcessor:** Class reference
2. **TimeStretchConfig:** Configuration options
3. **Algorithm Selection:** Algorithm mapping logic
4. **Error Handling:** Exception types and handling
5. **Examples:** Code examples for common use cases

**Format:** Docstrings (Google/NumPy style) + Sphinx-generated docs.

**Priority:** Should Have

---

### 12.3 Preset Documentation

**Preset Descriptions:**
- **Faster (+5%):** Use case, expected results, when to use
- **Slower (-25%):** Use case, expected results, when to use
- **Half Speed (0.5x):** Use case, limitations, when to use
- **Double Speed (2.0x):** Use case, limitations, when to use
- **Custom:** How to create and save custom presets

**Format:** In-app tooltips + user guide section.

**Priority:** Should Have

---

### 12.4 Developer Documentation

**Developer Docs Sections:**
1. **Architecture:** Component overview, data flow
2. **Adding Algorithms:** How to integrate new time-stretching algorithms
3. **Testing:** How to run tests, add new tests
4. **License Considerations:** GPLv2 compatibility guide

**Format:** Markdown in `docs/` directory.

**Priority:** Could Have

---

## 13. Open Questions & Decisions Needed

### 13.1 License Compatibility

**Question:** How to handle GPLv2 license conflict with Rubber Band?

**Options:**
1. Make Rubber Band optional, use MIT-licensed `audiotsm` as primary
2. Switch entire project to GPLv2 (requires approval)
3. Implement Rubber Band as separate GPLv2 module

**Recommendation:** Option 1 (make optional, clear documentation).

**Decision Needed:** Product/legal approval.

---

### 13.2 GUI Integration Location

**Question:** Where should time-stretching controls appear?

**Options:**
1. New "Time-Stretch" tab in main window
2. Section in existing "Export" tab
3. Modal dialog (separate window)

**Recommendation:** Option 1 (new tab) for clarity and discoverability.

**Decision Needed:** UX/design approval.

---

### 13.3 Default Behavior

**Question:** Should time-stretching be enabled by default or opt-in?

**Options:**
1. Opt-in (default speed = 1.0x, user must enable)
2. Opt-out (default enabled, user can disable)

**Recommendation:** Option 1 (opt-in) for backward compatibility and user control.

**Decision Needed:** Product approval.

---

## 14. Appendix

### 14.1 Glossary

- **Time-Stretching:** Changing audio playback speed without changing pitch
- **WSOLA:** Waveform Similarity Overlap-Add (algorithm for time-stretching)
- **Rubber Band:** High-quality time-stretching library (GPLv2)
- **OLA:** Overlap-Add (basic time-stretching algorithm)
- **SDR:** Signal-to-Distortion Ratio (audio quality metric)
- **BPM:** Beats Per Minute (tempo measurement)

---

### 14.2 References

- **audiotsm Documentation:** https://github.com/gregorias/audiotsm
- **Rubber Band Library:** https://breakfastquay.com/rubberband/
- **GPLv2 License:** https://www.gnu.org/licenses/gpl-2.0.html
- **Time-Stretching Algorithms:** Academic papers on WSOLA, PSOLA, Phase Vocoder

---

### 14.3 Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-01-XX | Initial PRD draft | TPM |

---

**End of Document**

