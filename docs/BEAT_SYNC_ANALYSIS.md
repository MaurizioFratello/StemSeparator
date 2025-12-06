# Beat Synchronization Drift Analysis

## Problem Description

BeatNet correctly detects BPMs and beat positions, but the visually drawn beats in the looping tab drift apart over time. Initially, loops are nearly perfect and the "1" of each bar aligns, but later the loop start points (detected "1") no longer match the actual "1" in the audio file. The audio file is always slightly behind.

## FIXED: BPM Mismatch Between Display and Grid (2024-12)

**Root Cause Identified**: BeatNet detected tempo (e.g., 141 BPM) differed from DeepRhythm's more accurate tempo (e.g., 128 BPM). The display showed DeepRhythm's tempo, but the beat grid was drawn using BeatNet's beat positions.

**Impact**: At 128 BPM vs 141 BPM (10% difference), after 33 bars:
- Grid (141 BPM): Bar 33 at ~56 seconds
- Audio (128 BPM): Bar 33 at ~62 seconds
- Drift: ~6 seconds by bar 33

**Fix Applied**: When DeepRhythm's BPM differs >5% from BeatNet's, the beat grid is now recalculated using DeepRhythm's tempo, anchored to the first detected downbeat.

**Code**: `utils/beat_detection.py` - `detect_beats_and_downbeats()` now calls `recalculate_beat_grid_from_bpm()` when BPM mismatch exceeds threshold.

## Remaining Potential Issues

### Issue: Anchor Point Not Exactly on First Beat

**Symptom**: Even with correct BPM, there's drift from the start.

**Cause**: The user places the downbeat at 0.0 seconds (audio start), but the actual first beat/transient in the audio is slightly after 0.0s (e.g., 30-60ms into the audio).

**Solution**: 
- Use Shift+Click to disable transient snapping and place downbeat exactly at 0.0s
- OR use transient snapping to place downbeat on the actual first drum hit
- Compare first downbeat position in StemSeparator with beat 1 position in Logic Pro

### Issue: BPM Spinbox is Integer-Only

**Symptom**: Slight tempo mismatch when actual tempo is not an integer (e.g., 127.8 BPM).

**Impact**: At 127.8 BPM vs 128 BPM:
- After 4 bars: 0.2% drift = ~15ms
- After 33 bars: ~125ms drift

**Workaround**: Don't change BPM in spinbox; use the auto-detected float BPM value.

### Issue: Cumulative Floating-Point Errors (FIXED)

**Fix Applied**: Beat positions now calculated using direct multiplication `anchor + n * beat_interval` instead of cumulative addition `current_time += beat_interval`.

### Debug Logging

Enable DEBUG level logging to see exact beat positions:
```
Beat grid verification (first 5 bars):
  Bar 1 (beat 1):  0.000000s
  Bar 2 (beat 5):  1.875000s (interval: 1.875000s)
  Bar 3 (beat 9):  3.750000s (interval: 1.875000s)
  ...
```

Compare these values with Logic Pro's beat positions to identify the source of drift.

## Root Cause Analysis

### 1. Sample Rate Mismatch Between Waveform Rendering and Audio Playback

**Location**: `ui/widgets/player_widget.py` and `core/player.py`

**Problem**:
- **Waveform rendering** (`_mix_stems_to_array()`): Reads audio files directly using `sf.read()`, uses the file's native sample rate
- **Audio playback** (`player.load_stems()`): Loads stems and may resample them to a common sample rate
- **Duration calculation mismatch**: 
  - Waveform: `duration = len(audio_data) / sample_rate` (from file)
  - Player: `duration_samples = max_length` (after potential resampling)

**Impact**: If waveform uses 44100 Hz but player resamples to 48000 Hz (or vice versa), the duration calculations differ:
- Waveform duration: `N_samples / 44100`
- Player duration: `N_samples_resampled / 48000`
- Beat positions in seconds are correct, but pixel positions drift because `_time_to_x()` uses waveform duration

**Code References**:
```python
# ui/widgets/player_widget.py:1764
def _mix_stems_to_array(self) -> Tuple[np.ndarray, int]:
    # Uses file's native sample rate
    audio_data, sr = sf.read(stem_path, dtype='float32')
    sample_rate = sr  # File's sample rate

# core/player.py:134
def load_stems(self, stem_files: Dict[str, Path]) -> bool:
    # May resample to detected_sample_rate
    if file_sr != detected_sample_rate:
        audio_data = librosa.resample(...)  # Resampled!
    self.sample_rate = detected_sample_rate  # May differ from file
```

### 2. Position Tracking Based on System Time (Cumulative Error)

**Location**: `core/player.py:_position_update_loop()`

**Problem**:
- Position is calculated as: `expected_position = start_position + int(elapsed * self.sample_rate)`
- Uses `time.time()` which has limited precision and can drift
- Integer truncation accumulates errors: `int(elapsed * sample_rate)` loses fractional samples
- No feedback from actual audio hardware position

**Impact**: Over time, the calculated position drifts from actual audio playback position. For a 5-minute song at 44100 Hz:
- 1ms timing error = 44.1 samples error
- Over 5 minutes, small errors accumulate

**Code Reference**:
```python
# core/player.py:496
def _position_update_loop(self):
    elapsed = time.time() - start_time
    elapsed_samples = int(elapsed * self.sample_rate)  # Truncation!
    expected_position = start_position + elapsed_samples
```

### 3. BPM Rounding for Display (Minor Issue)

**Location**: `ui/widgets/player_widget.py:1137`

**Problem**:
- BPM is rounded to integer for display: `int(calculated_bpm)`
- Beat grid recalculation uses float BPM, but display shows rounded value
- This causes confusion but shouldn't cause drift (beat times are calculated from float BPM)

**Impact**: User sees "120 BPM" but actual BPM might be 120.3, causing slight misalignment perception

**Code Reference**:
```python
# ui/widgets/player_widget.py:1137
bpm_prefix = f"{int(calculated_bpm)} BPM{confidence_str}"  # Rounded!
```

### 4. Time-to-Pixel Conversion Assumes Fixed Duration

**Location**: `ui/widgets/loop_waveform_widget.py:167`

**Problem**:
- `_time_to_x()` uses `self.duration` which is set once when waveform is loaded
- If sample rate mismatch exists, duration is wrong, causing all beat positions to be misaligned
- Formula: `x = (time_sec / duration) * width`
- If `duration` is wrong, all beat markers shift proportionally

**Code Reference**:
```python
# ui/widgets/loop_waveform_widget.py:167
def _time_to_x(self, time_sec: float) -> int:
    return int((time_sec / self.duration) * self._content_width)
    # If self.duration is wrong, all positions are wrong
```

## Solution Approaches

### Solution 1: Ensure Sample Rate Consistency (HIGH PRIORITY)

**Strategy**: Use the same sample rate for waveform rendering and audio playback.

**Implementation**:
1. When loading stems for playback, store the actual sample rate used
2. When rendering waveform, use the player's sample rate (not file's native rate)
3. Ensure waveform audio data matches player's audio data (same resampling)

**Changes Required**:
```python
# ui/widgets/player_widget.py
def _mix_stems_to_array(self) -> Tuple[np.ndarray, int]:
    # Use player's sample rate instead of file's native rate
    player_sample_rate = self.player.sample_rate
    
    # Resample all stems to player's sample rate before mixing
    for stem_name, stem_path in self.stem_files.items():
        audio_data, file_sr = sf.read(stem_path, dtype='float32')
        if file_sr != player_sample_rate:
            audio_data = librosa.resample(audio_data, orig_sr=file_sr, 
                                        target_sr=player_sample_rate)
        # ... mix ...
    
    return mixed_audio, player_sample_rate  # Use player's rate
```

**Benefits**:
- Eliminates sample rate mismatch
- Waveform duration matches playback duration exactly
- Beat positions align correctly

**Risks**:
- Requires resampling for waveform (slight performance cost)
- Must ensure player sample rate is set before waveform rendering

### Solution 2: Improve Position Tracking Accuracy (MEDIUM PRIORITY)

**Strategy**: Use sample-accurate position tracking instead of time-based estimation.

**Implementation Options**:

**Option 2A: Use sounddevice's position callback** (if available)
- Query actual playback position from sounddevice
- More accurate but may not be available on all platforms

**Option 2B: Use higher precision timing with sample-accurate calculation**
- Use `time.perf_counter()` instead of `time.time()` (higher precision)
- Calculate position as float, round only for display
- Add periodic correction based on actual audio buffer consumption

**Option 2C: Track position based on audio buffer consumption**
- When `sounddevice.play()` completes a buffer, update position
- More accurate but requires callback mechanism

**Changes Required** (Option 2B):
```python
# core/player.py
import time

def _position_update_loop(self):
    start_time = time.perf_counter()  # Higher precision
    start_position = self.position_samples
    
    while not self._stop_update.is_set():
        elapsed = time.perf_counter() - start_time
        # Use float calculation, round only at end
        elapsed_samples_float = elapsed * self.sample_rate
        expected_position = int(start_position + elapsed_samples_float)
        # ... rest of logic ...
```

**Benefits**:
- Reduces timing drift
- More accurate position tracking

**Risks**:
- Still relies on system time (not hardware position)
- May not fully eliminate drift

### Solution 3: Use Actual Audio Duration from Player (HIGH PRIORITY)

**Strategy**: Calculate waveform duration from player's actual duration, not from mixed audio.

**Implementation**:
```python
# ui/widgets/player_widget.py
def _on_beat_analysis_finished(self, ...):
    # Use player's duration instead of waveform duration
    player_duration = self.player.get_duration()  # In seconds
    
    # Set waveform with correct duration
    self.loop_waveform_widget.set_combined_waveform(
        mixed_audio, 
        sample_rate,
        duration=player_duration  # Override calculated duration
    )
```

**Changes Required**:
```python
# ui/widgets/loop_waveform_widget.py
def set_combined_waveform(self, audio_data: np.ndarray, sample_rate: int, 
                         duration: Optional[float] = None):
    self.waveform_data = audio_data
    self.sample_rate = sample_rate
    # Use provided duration or calculate from data
    if duration is not None:
        self.duration = duration
    else:
        self.duration = len(audio_data) / sample_rate
```

**Benefits**:
- Ensures waveform duration matches playback duration
- Simple fix with minimal code changes
- Works even if sample rates differ (as long as durations match)

### Solution 4: Display Actual BPM (Not Rounded) (LOW PRIORITY)

**Strategy**: Show float BPM with one decimal place for accuracy.

**Implementation**:
```python
# ui/widgets/player_widget.py:1137
if calculated_bpm:
    bpm_prefix = f"{calculated_bpm:.1f} BPM{confidence_str}"  # One decimal
```

**Benefits**:
- User sees accurate BPM
- Reduces confusion about alignment

## Recommended Implementation Order

1. **Solution 3** (Use player's duration) - Quick fix, high impact
2. **Solution 1** (Sample rate consistency) - Comprehensive fix
3. **Solution 2** (Position tracking) - Fine-tuning
4. **Solution 4** (BPM display) - Polish

## Testing Strategy

1. **Test with different sample rates**: Load stems at 44100 Hz and 48000 Hz
2. **Test long songs**: 5+ minute songs to observe drift accumulation
3. **Test beat alignment**: Verify beat markers align with actual audio beats throughout song
4. **Test loop playback**: Verify loop start/end points align correctly

## Expected Outcomes

After implementing Solutions 1 and 3:
- Beat markers align correctly throughout entire song
- Loop start points match actual audio "1" beats
- No progressive drift over time
- Waveform duration matches playback duration exactly

