"""
Beat Detection - BeatNet integration for loop analysis

PURPOSE: Detect beats and downbeats in audio for loop segmentation
CONTEXT: Uses BeatNet beat-service (subprocess) with DeepRhythm/librosa fallback

Strategy:
1. Primary: BeatNet beat-service binary (full beat+downbeat grid)
2. Fallback: DeepRhythm/librosa (BPM only, synthetic beat grid)
"""
from pathlib import Path
from typing import Tuple, Optional, List, Callable, Dict
import numpy as np
import soundfile as sf

from utils.logger import get_logger
from utils.beat_service_client import (
    analyze_beats,
    is_beat_service_available,
    BeatServiceError,
    BeatServiceTimeout,
    BeatServiceNotFound,
)
from utils.audio_processing import detect_bpm
from utils.beatnet_warmup import wait_for_warmup_complete

logger = get_logger()


def is_beatnet_available() -> bool:
    """
    Check if BeatNet beat-service is available.

    Returns:
        True if beat-service binary exists and is executable
    """
    return is_beat_service_available()


# Type alias for progress callback: (phase: str, detail: str) -> None
ProgressCallback = Callable[[str, str], None]


def detect_beats_and_downbeats(
    audio_path: Path,
    bpm_hint: Optional[float] = None,
    bpm_audio_path: Optional[Path] = None,
    progress_callback: Optional[ProgressCallback] = None
) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """
    Detect beats and downbeats in audio file.

    Strategy:
    1. Try BeatNet beat-service (full beat+downbeat grid)
    2. Use DeepRhythm for BPM (optionally from drums stem for better accuracy)
    3. Fallback: DeepRhythm/librosa (BPM only, synthetic beat grid)

    Args:
        audio_path: Path to audio file for beat grid detection (typically mixed)
        bpm_hint: Optional BPM hint (used for fallback logging)
        bpm_audio_path: Optional separate audio path for BPM detection (e.g., drums stem).
                        If None, uses audio_path. Drums stem gives more accurate BPM.
        progress_callback: Optional callback for progress updates.
                          Called with (phase, detail) strings.

    Returns:
        Tuple of:
        - beat_times: Array of beat positions in seconds
        - downbeat_times: Array of downbeat positions in seconds
        - first_downbeat: Time of first downbeat in seconds
        - confidence_msg: Human-readable confidence/source message

    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If no beats detected and fallback also fails

    Example:
        >>> # Use drums for BPM, mixed for beat grid:
        >>> beats, downbeats, first_db, msg = detect_beats_and_downbeats(
        ...     audio_path=mixed_path, bpm_audio_path=drums_path
        ... )
    """
    def report_progress(phase: str, detail: str = ""):
        """Helper to report progress if callback is provided."""
        if progress_callback:
            progress_callback(phase, detail)
        logger.info(f"{phase}: {detail}" if detail else phase)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    report_progress("Initializing", f"Analyzing {audio_path.name}")

    if bpm_hint:
        logger.info(f"BPM hint: {bpm_hint:.1f}")

    # Strategy 1: Try BeatNet beat-service for beat grid + DeepRhythm for BPM
    if is_beat_service_available():
        try:
            # Wait for warm-up to complete before starting real analysis
            # WHY: Ensures XProtect scanning happens during warm-up, not here
            # Silent wait - warm-up runs in background, user shouldn't notice
            # Increased timeout for M1 and less performant Macs
            wait_for_warmup_complete(max_wait_seconds=120.0)
            
            # Calculate dynamic timeout based on audio duration
            # Base: 60s + ~1.0s per second of audio (increased for M1 and less performant Macs)
            # BeatNet processes ~2x realtime on MPS, but slower on M1/CPU
            try:
                info = sf.info(str(audio_path))
                audio_duration = info.duration
                timeout = max(120.0, 60.0 + audio_duration * 1.0)
                logger.debug(f"BeatNet timeout: {timeout:.0f}s for {audio_duration:.1f}s audio")
            except Exception:
                audio_duration = 0
                timeout = 180.0  # Safe default for unknown duration (increased for M1)

            report_progress("BeatNet", f"Analyzing beat grid ({audio_duration:.0f}s audio, timeout: {timeout:.0f}s)...")

            result = analyze_beats(
                audio_path,
                timeout_seconds=timeout,
                device="auto"
            )

            report_progress("BeatNet", f"Found {len(result.beats)} beats, processing...")

            beat_times = np.array([b.time for b in result.beats])
            downbeat_times = np.array([d.time for d in result.downbeats])

            if len(downbeat_times) == 0:
                logger.warning("BeatNet returned no downbeats, using first beat")
                first_downbeat = beat_times[0] if len(beat_times) > 0 else 0.0
                downbeat_times = np.array([first_downbeat])
            else:
                first_downbeat = downbeat_times[0]

            # Use DeepRhythm/librosa for more accurate BPM estimation
            # BeatNet provides the beat grid, DeepRhythm provides better tempo
            # Use bpm_audio_path (e.g., drums stem) if provided for better accuracy
            beatnet_tempo = result.tempo
            final_tempo = beatnet_tempo
            tempo_source = "BeatNet"
            grid_recalculated = False

            bpm_source_path = bpm_audio_path if bpm_audio_path and bpm_audio_path.exists() else audio_path
            bpm_source_name = "drums" if bpm_audio_path and bpm_audio_path.exists() else "mixed"

            report_progress("DeepRhythm", f"Refining BPM from {bpm_source_name} stem...")

            try:
                audio_data, sample_rate = sf.read(str(bpm_source_path), always_2d=False)
                if audio_data.ndim > 1:
                    audio_data = np.mean(audio_data, axis=1)

                audio_duration = len(audio_data) / sample_rate
                deeprhythm_tempo, dr_confidence = detect_bpm(audio_data, sample_rate)

                if deeprhythm_tempo > 0 and dr_confidence is not None:
                    # Use DeepRhythm tempo if confidence is good
                    final_tempo = deeprhythm_tempo
                    tempo_source = f"DeepRhythm ({dr_confidence:.0%})"
                    logger.info(
                        f"BPM refinement: BeatNet={beatnet_tempo:.1f}, "
                        f"DeepRhythm={deeprhythm_tempo:.1f} (using DeepRhythm)"
                    )
                elif deeprhythm_tempo > 0:
                    # librosa fallback (no confidence score)
                    final_tempo = deeprhythm_tempo
                    tempo_source = "librosa"
                    logger.info(
                        f"BPM refinement: BeatNet={beatnet_tempo:.1f}, "
                        f"librosa={deeprhythm_tempo:.1f} (using librosa)"
                    )

                # CRITICAL FIX: Recalculate beat grid if BPM differs significantly
                # WHY: BeatNet may detect wrong tempo (e.g., 141 vs 128 BPM), causing
                # beat positions to drift progressively. The displayed BPM comes from
                # DeepRhythm, but the grid was drawn from BeatNet's beat times.
                # This mismatch causes beats to not align with actual audio.
                bpm_diff_ratio = abs(final_tempo - beatnet_tempo) / beatnet_tempo
                BPM_RECALC_THRESHOLD = 0.05  # 5% difference triggers recalculation

                if bpm_diff_ratio > BPM_RECALC_THRESHOLD:
                    logger.warning(
                        f"BPM mismatch: BeatNet={beatnet_tempo:.1f}, "
                        f"DeepRhythm={final_tempo:.1f} ({bpm_diff_ratio:.1%} diff). "
                        f"Recalculating beat grid with DeepRhythm tempo."
                    )
                    report_progress("Grid Correction", f"Recalculating beat grid at {final_tempo:.1f} BPM...")

                    # Recalculate grid using DeepRhythm tempo, anchored to first downbeat
                    beat_times, downbeat_times, first_downbeat = recalculate_beat_grid_from_bpm(
                        current_beat_times=beat_times,
                        current_downbeat_times=downbeat_times,
                        new_bpm=final_tempo,
                        audio_duration=audio_duration,
                        first_downbeat_anchor=first_downbeat
                    )
                    grid_recalculated = True
                    logger.info(
                        f"Beat grid recalculated: {len(beat_times)} beats, "
                        f"{len(downbeat_times)} downbeats at {final_tempo:.1f} BPM"
                    )

            except Exception as e:
                logger.warning(f"DeepRhythm BPM detection failed, using BeatNet: {e}")

            grid_source = "recalculated" if grid_recalculated else "BeatNet"
            confidence_msg = (
                f"{tempo_source}: {final_tempo:.1f} BPM, "
                f"{len(downbeat_times)} downbeats (grid: {grid_source})"
            )

            logger.info(
                f"Beat analysis complete: {len(beat_times)} beats, "
                f"{len(downbeat_times)} downbeats, first at {first_downbeat:.2f}s"
            )

            return beat_times, downbeat_times, first_downbeat, confidence_msg

        except BeatServiceTimeout as e:
            logger.warning(f"BeatNet timeout: {e}, falling back to DeepRhythm")
        except BeatServiceNotFound as e:
            logger.info(f"BeatNet not available: {e}, using fallback")
        except BeatServiceError as e:
            logger.warning(f"BeatNet error: {e}, falling back to DeepRhythm")
    else:
        logger.info("BeatNet beat-service not available, using fallback")

    # Strategy 2: Fallback to DeepRhythm/librosa (BPM only)
    return _fallback_bpm_detection(audio_path)


def _fallback_bpm_detection(audio_path: Path) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """
    Fallback beat detection using DeepRhythm/librosa.

    WHY: When BeatNet is unavailable, we can still detect BPM and generate
    a synthetic beat grid. However, we cannot detect true downbeats.

    Returns:
        Same tuple format as detect_beats_and_downbeats()

    Note:
        - Downbeats are NOT accurate (just every 4th beat assumed)
        - Loop-export functionality should be limited in this mode
    """
    logger.info("Using fallback BPM detection (no true downbeats)")

    try:
        # Load audio for duration calculation
        audio_data, sample_rate = sf.read(str(audio_path), always_2d=False)
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)

        duration = len(audio_data) / sample_rate

        # Detect BPM using DeepRhythm (preferred) or librosa
        bpm, confidence = detect_bpm(audio_data, sample_rate)

        if bpm <= 0:
            bpm = 120.0
            logger.warning("BPM detection failed, using default 120 BPM")

        # Generate synthetic beat grid from BPM
        beat_interval = 60.0 / bpm
        beat_times = np.arange(0, duration, beat_interval)

        # Generate synthetic downbeats (every 4 beats, assuming 4/4)
        # WARNING: These are NOT true musical downbeats!
        downbeat_indices = np.arange(0, len(beat_times), 4)
        downbeat_times = beat_times[downbeat_indices]

        first_downbeat = 0.0  # Assume start

        # Build confidence message
        if confidence is not None:
            confidence_msg = f"Fallback: {bpm:.1f} BPM ({confidence:.0%}) - keine echten Downbeats"
        else:
            confidence_msg = f"Fallback: {bpm:.1f} BPM (librosa) - keine echten Downbeats"

        logger.info(
            f"Fallback detection: {bpm:.1f} BPM, {len(beat_times)} synthetic beats, "
            f"{len(downbeat_times)} assumed downbeats"
        )

        return beat_times, downbeat_times, first_downbeat, confidence_msg

    except Exception as e:
        logger.error(f"Fallback BPM detection failed: {e}", exc_info=True)
        raise ValueError(f"Could not detect beats: {e}")


def calculate_loops_from_downbeats(
    downbeat_times: np.ndarray,
    bars_per_loop: int,
    audio_duration: float,
    song_start_downbeat_index: Optional[int] = None,
    intro_handling: str = "pad"
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Calculate loop segments based on downbeat positions.

    Args:
        downbeat_times: Array of downbeat positions in seconds
        bars_per_loop: Number of bars per loop (typically 2, 4, or 8)
        audio_duration: Total audio duration in seconds
        song_start_downbeat_index: Optional index of downbeat marking song start.
                                   If provided, loops are calculated from this point.
        intro_handling: How to handle intro before song start marker:
                       "pad" - Create intro loops calculated BACKWARDS from song start,
                               aligned to song start, with padding only at audio start
                       "skip" - Skip intro in loop calculation

    Returns:
        Tuple of (loops, intro_loops):
        - loops: List of (start_time, end_time) tuples for main loop segments (forward from song start)
        - intro_loops: List of (start_time, end_time) for intro loops if song_start_downbeat_index is set
                      Calculated BACKWARDS from song start in bars_per_loop chunks
                      NOTE: First intro loop may have negative start_time (silence padding)
                      Each intro loop is exactly bars_per_loop length

    Raises:
        ValueError: If no downbeats provided or invalid bars_per_loop

    Example:
        >>> downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
        >>> # Without song start marker (backward compatible):
        >>> loops, intro_loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=12.0)
        >>> # loops = [(0.0, 8.0), (8.0, 12.0)], intro_loops = []
        >>>
        >>> # With song start at bar 3 (time 6.0s), 2 bars/loop:
        >>> # Backwards from 6.0s: [2.0-6.0] (2 bars), [0.0-2.0] (1 bar + 1 bar padding)
        >>> loops, intro_loops = calculate_loops_from_downbeats(
        ...     downbeats, bars_per_loop=2, audio_duration=12.0,
        ...     song_start_downbeat_index=3, intro_handling="pad"
        ... )
        >>> # intro_loops = [(-2.0, 2.0), (2.0, 6.0)]  # Backwards from song start
        >>> # First loop: 1 bar silence + 1 bar audio, Second loop: 2 bars audio
        >>> # loops = [(6.0, 10.0), (10.0, 12.0)]  # Forward from song start
    """
    if len(downbeat_times) == 0:
        raise ValueError("No downbeats provided")

    if bars_per_loop <= 0:
        raise ValueError(f"Invalid bars_per_loop: {bars_per_loop}")

    num_downbeats = len(downbeat_times)

    # Validate song_start_downbeat_index
    if song_start_downbeat_index is not None:
        if song_start_downbeat_index < 0 or song_start_downbeat_index >= num_downbeats:
            logger.warning(
                f"Invalid song_start_downbeat_index {song_start_downbeat_index}, "
                f"must be 0-{num_downbeats-1}. Ignoring marker."
            )
            song_start_downbeat_index = None

    intro_loops: List[Tuple[float, float]] = []
    loops = []

    # If song start marker is set, handle intro
    if song_start_downbeat_index is not None and song_start_downbeat_index > 0:
        intro_actual_start = 0.0
        intro_actual_end = downbeat_times[song_start_downbeat_index]
        intro_bars = song_start_downbeat_index

        if intro_handling == "pad":
            # Calculate loops BACKWARDS from song start in bars_per_loop chunks
            # WHY: Loops should align relative to song start (reference point),
            #      not audio start. This ensures musical alignment.
            # Example: Song start at bar 3, bars_per_loop=2
            #   → Loops: [bar 1-3], [bar 0-1 + padding]
            import math

            # Use average bar duration from all downbeats
            avg_bar_duration = np.mean(np.diff(downbeat_times))
            loop_duration = bars_per_loop * avg_bar_duration

            song_start_time = downbeat_times[song_start_downbeat_index]

            # Calculate loops backwards from song start
            current_end = song_start_time
            num_intro_loops = 0
            total_padding = 0.0

            while current_end > 0.0:
                current_start = current_end - loop_duration

                if current_start >= 0.0:
                    # Full loop within audio bounds
                    intro_loops.insert(0, (current_start, current_end))
                    current_end = current_start
                    num_intro_loops += 1
                else:
                    # Partial loop at audio start - add padding to make full length
                    actual_audio_duration = current_end  # from 0.0 to current_end
                    padding_duration = loop_duration - actual_audio_duration
                    intro_loops.insert(0, (-padding_duration, current_end))
                    total_padding = padding_duration
                    num_intro_loops += 1
                    break  # Reached audio start

            logger.info(
                f"Created {num_intro_loops} leading loops (backwards from song start): "
                f"{total_padding:.2f}s silence padding + {song_start_time:.2f}s intro "
                f"({num_intro_loops} loops × {bars_per_loop} bars each)"
            )
        elif intro_handling == "skip":
            # Skip intro - no intro loops created
            logger.info(f"Skipping intro ({intro_actual_start:.2f}s - {intro_actual_end:.2f}s)")

        # Start loop calculation from song start marker
        start_idx = song_start_downbeat_index
    else:
        # No song start marker - start from beginning (backward compatible)
        start_idx = 0

    # Calculate main loops
    idx = start_idx
    while idx < num_downbeats:
        start_time = downbeat_times[idx]

        # Calculate end index (start + bars_per_loop)
        end_idx = idx + bars_per_loop

        if end_idx < num_downbeats:
            # Normal loop - use next downbeat as end
            end_time = downbeat_times[end_idx]
        else:
            # Last loop - might be partial
            if idx + 1 < num_downbeats:
                # Calculate average bar duration
                avg_bar_duration = np.mean(np.diff(downbeat_times))
                end_time = min(audio_duration, start_time + (bars_per_loop * avg_bar_duration))
            else:
                end_time = audio_duration

        loops.append((start_time, end_time))
        idx += bars_per_loop

    if song_start_downbeat_index is not None:
        logger.info(
            f"Calculated {len(intro_loops)} leading loops + {len(loops)} main loops "
            f"({bars_per_loop} bars each) from song start marker (downbeat {song_start_downbeat_index})"
        )
    else:
        logger.info(f"Calculated {len(loops)} loops ({bars_per_loop} bars each)")

    return loops, intro_loops


def detect_transients(
    audio_data: np.ndarray,
    sample_rate: int,
    threshold: float = 0.3,
    min_distance: float = 0.03  # CHANGED: 30ms instead of 100ms for fast drums
) -> np.ndarray:
    """
    Detect transient peaks in audio signal with attack-phase focus.

    WHY: Snap-to-transient for manual downbeat placement improves accuracy.
    STRATEGY: Use attack-focused detection (spectral flux + energy derivative).

    Args:
        audio_data: Audio samples (mono)
        sample_rate: Sample rate in Hz
        threshold: Relative threshold for peak detection (0-1)
        min_distance: Minimum time between transients in seconds (default 30ms)

    Returns:
        Array of transient times in seconds

    Raises:
        ValueError: If audio_data is empty
    """
    if len(audio_data) == 0:
        raise ValueError("Audio data is empty")

    # Use new attack-focused detection
    transient_times = detect_transients_attack_focused(
        audio_data=audio_data,
        sample_rate=sample_rate,
        threshold=threshold,
        min_distance=min_distance,
        percussion_mode=False
    )

    logger.info(f"Detected {len(transient_times)} transients")
    return transient_times


def detect_transients_attack_focused(
    audio_data: np.ndarray,
    sample_rate: int,
    threshold: float = 0.3,
    min_distance: float = 0.03,  # 30ms - allows fast drum hits
    percussion_mode: bool = False
) -> np.ndarray:
    """
    Detect transient attack phases using combined spectral flux + energy derivative.

    WHY: Standard onset detection with backtrack is unreliable for manual placement.
         Energy-based fallback detects peak energy (sustain), not attack phase.
         This function focuses specifically on the ATTACK phase of transients.

    STRATEGY:
        1. Spectral flux - detects rapid frequency content changes
        2. Energy derivative - detects rapid amplitude increases (attack)
        3. Combine both signals to identify attack moments
        4. Optional percussion weighting for drums (2-8kHz snare/hi-hat, 50-150Hz kick)

    Args:
        audio_data: Audio samples (mono)
        sample_rate: Sample rate in Hz
        threshold: Relative threshold for detection (0-1, default 0.3)
        min_distance: Minimum time between transients in seconds (default 30ms)
        percussion_mode: If True, apply percussion-specific frequency weighting

    Returns:
        Array of transient times in seconds

    Raises:
        ValueError: If audio_data is empty
    """
    if len(audio_data) == 0:
        raise ValueError("Audio data is empty")

    try:
        import librosa

        # Convert min_distance to frames (hop_length=512 is librosa default)
        hop_length = 512
        min_frames = max(1, int(min_distance * sample_rate / hop_length))

        # Method 1: Spectral Flux (detects frequency content changes)
        spectral_onset_env = librosa.onset.onset_strength(
            y=audio_data,
            sr=sample_rate,
            hop_length=hop_length,
            aggregate=np.median  # More robust than mean
        )

        # Method 2: Energy Derivative (detects rapid amplitude increases)
        # Calculate short-term energy with small window for attack detection
        frame_length = hop_length * 2
        energy = np.array([
            np.sum(audio_data[i:i + frame_length] ** 2)
            for i in range(0, len(audio_data) - frame_length, hop_length)
        ])

        # Compute first derivative (rate of energy increase)
        energy_derivative = np.diff(energy, prepend=energy[0])
        # Only keep positive derivatives (rising energy = attack)
        energy_derivative = np.maximum(energy_derivative, 0)

        # Normalize both signals to 0-1 range
        if np.max(spectral_onset_env) > 0:
            spectral_onset_env = spectral_onset_env / np.max(spectral_onset_env)
        if np.max(energy_derivative) > 0:
            energy_derivative = energy_derivative / np.max(energy_derivative)

        # Align lengths (energy_derivative may be shorter)
        min_len = min(len(spectral_onset_env), len(energy_derivative))
        spectral_onset_env = spectral_onset_env[:min_len]
        energy_derivative = energy_derivative[:min_len]

        # Optional: Percussion-specific frequency weighting
        if percussion_mode:
            # Apply frequency weighting to emphasize percussion ranges
            # 50-150Hz (kick), 2-8kHz (snare/hi-hat)
            stft = librosa.stft(audio_data, hop_length=hop_length)
            freqs = librosa.fft_frequencies(sr=sample_rate)

            # Create weighting mask
            kick_mask = (freqs >= 50) & (freqs <= 150)
            snare_mask = (freqs >= 2000) & (freqs <= 8000)
            perc_mask = kick_mask | snare_mask

            # Weight spectral content
            weighted_stft = np.abs(stft) * perc_mask[:, np.newaxis]
            perc_energy = np.sum(weighted_stft, axis=0)

            # Normalize and align
            if np.max(perc_energy) > 0:
                perc_energy = perc_energy / np.max(perc_energy)
            perc_energy = perc_energy[:min_len]

            # Combine all three signals (weighted average)
            combined_onset = (
                0.4 * spectral_onset_env +
                0.3 * energy_derivative +
                0.3 * perc_energy
            )
        else:
            # Combine spectral flux and energy derivative (equal weight)
            combined_onset = 0.5 * spectral_onset_env + 0.5 * energy_derivative

        # Peak picking on combined onset function
        # Use librosa's peak picking with proper threshold
        onset_frames = librosa.util.peak_pick(
            combined_onset,
            pre_max=3,      # Frames before peak
            post_max=3,     # Frames after peak
            pre_avg=3,      # Frames for pre-average
            post_avg=5,     # Frames for post-average
            delta=threshold,  # Threshold for peak detection
            wait=min_frames   # Minimum frames between peaks
        )

        # Convert frames to time
        transient_times = librosa.frames_to_time(onset_frames, sr=sample_rate, hop_length=hop_length)

        logger.info(f"Detected {len(transient_times)} attack-focused transients (percussion_mode={percussion_mode})")
        return transient_times

    except ImportError:
        # Fallback: Enhanced energy-based detection with derivative
        logger.warning("librosa not available, using enhanced energy-based detection")

        hop_length = int(min_distance * sample_rate / 4)  # 4x smaller than min_distance
        frame_length = hop_length * 2

        # Calculate energy
        energy = []
        for i in range(0, len(audio_data) - frame_length, hop_length):
            frame = audio_data[i:i + frame_length]
            energy.append(np.sum(frame ** 2))

        energy = np.array(energy)

        # Calculate derivative (rate of change)
        energy_derivative = np.diff(energy, prepend=energy[0])

        # Find peaks in positive derivative (attack moments)
        threshold_value = np.mean(energy_derivative) + threshold * np.std(energy_derivative)

        peaks = []
        min_frames_fallback = max(1, int(min_distance * sample_rate / hop_length))

        for i in range(1, len(energy_derivative) - 1):
            # Peak in derivative AND positive (rising energy)
            if (energy_derivative[i] > threshold_value and
                energy_derivative[i] > energy_derivative[i-1] and
                energy_derivative[i] > energy_derivative[i+1] and
                energy_derivative[i] > 0):

                # Check minimum distance from last peak
                if not peaks or (i - peaks[-1]) >= min_frames_fallback:
                    peaks.append(i)

        transient_times = np.array([(i * hop_length) / sample_rate for i in peaks])
        logger.info(f"Detected {len(transient_times)} attack-focused transients (fallback method)")
        return transient_times


def detect_transients_per_stem(
    stem_waveforms: Dict[str, np.ndarray],
    sample_rate: int,
    threshold: float = 0.3,
    min_distance: float = 0.1
) -> Dict[str, np.ndarray]:
    """
    Detect transients for each stem independently.

    WHY: Enables stem-specific snap-to-transient for manual downbeat placement.
    STRATEGY: Call detect_transients() for each stem, return dict of results.

    Args:
        stem_waveforms: Dict mapping stem names to mono audio arrays
        sample_rate: Sample rate in Hz
        threshold: Relative threshold for peak detection (0-1)
        min_distance: Minimum time between transients in seconds

    Returns:
        Dict mapping stem names to transient time arrays

    Example:
        >>> transients = detect_transients_per_stem(
        ...     {"drums": drums_audio, "bass": bass_audio},
        ...     44100
        ... )
        >>> # transients = {"drums": array([0.1, 0.5, ...]), "bass": array([...]), ...}
    """
    transient_dict = {}

    for stem_name, audio_data in stem_waveforms.items():
        try:
            # Convert to mono if stereo
            if audio_data.ndim == 2:
                audio_data = np.mean(audio_data, axis=1)

            # Determine if this is a percussion stem for enhanced detection
            is_percussion = stem_name.lower() in ['drums', 'percussion', 'drum', 'perc']

            transients = detect_transients_attack_focused(
                audio_data=audio_data,
                sample_rate=sample_rate,
                threshold=threshold,
                min_distance=min_distance,
                percussion_mode=is_percussion  # Enable percussion weighting for drums
            )
            transient_dict[stem_name] = transients
            logger.debug(f"Stem '{stem_name}': {len(transients)} transients")

        except Exception as e:
            logger.warning(f"Transient detection failed for stem '{stem_name}': {e}")
            transient_dict[stem_name] = np.array([])

    return transient_dict


def recalculate_beat_grid_from_bpm(
    current_beat_times: np.ndarray,
    current_downbeat_times: np.ndarray,
    new_bpm: float,
    audio_duration: float,
    first_downbeat_anchor: Optional[float] = None
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Recalculate beat grid based on new BPM value.

    WHY: Allows manual BPM correction after automatic detection.
    STRATEGY: Uses first downbeat as anchor point to minimize grid shift.

    Args:
        current_beat_times: Existing beat positions (for reference)
        current_downbeat_times: Existing downbeat positions
        new_bpm: New BPM value
        audio_duration: Total audio duration in seconds
        first_downbeat_anchor: Optional anchor point (defaults to first downbeat)

    Returns:
        Tuple of (new_beat_times, new_downbeat_times, first_downbeat)

    Raises:
        ValueError: If new_bpm <= 0 or no downbeats available
    """
    if new_bpm <= 0:
        raise ValueError(f"Invalid BPM: {new_bpm}. BPM must be > 0")

    if len(current_downbeat_times) == 0:
        raise ValueError("No downbeats available for recalculation")

    # Use specified anchor or first downbeat
    anchor = first_downbeat_anchor if first_downbeat_anchor is not None else current_downbeat_times[0]

    # Calculate beat interval from BPM
    # WHY: Using exact division ensures precise beat spacing
    beat_interval = 60.0 / new_bpm

    logger.info(f"Recalculating beat grid: {new_bpm:.1f} BPM, anchor at {anchor:.6f}s, interval={beat_interval:.6f}s")

    # Generate beats using direct multiplication to avoid cumulative floating-point errors
    # WHY: Repeated addition (current_time += beat_interval) accumulates floating-point errors.
    #      Direct multiplication (anchor + n * beat_interval) is mathematically equivalent
    #      but more numerically stable, as each position is calculated independently.
    
    # Calculate number of beats forward from anchor to end of audio
    beats_forward_count = int((audio_duration - anchor) / beat_interval) + 1
    beats_forward = [anchor + n * beat_interval for n in range(beats_forward_count)
                     if anchor + n * beat_interval <= audio_duration]
    
    # Calculate number of beats backward from anchor to start of audio
    beats_backward_count = int(anchor / beat_interval)
    beats_backward = [anchor - n * beat_interval for n in range(1, beats_backward_count + 1)
                      if anchor - n * beat_interval >= 0]

    # Combine and sort
    all_beats = sorted(beats_backward + beats_forward)
    new_beat_times = np.array(all_beats, dtype=np.float64)  # Explicit high precision

    # Generate downbeats (every 4th beat, assuming 4/4 time)
    anchor_idx = np.argmin(np.abs(new_beat_times - anchor))

    # Align downbeats to start at anchor
    downbeat_indices = []
    # Backward from anchor
    idx = anchor_idx
    while idx >= 0:
        downbeat_indices.append(idx)
        idx -= 4
    # Forward from anchor
    idx = anchor_idx + 4
    while idx < len(new_beat_times):
        downbeat_indices.append(idx)
        idx += 4

    downbeat_indices = sorted(downbeat_indices)
    new_downbeat_times = new_beat_times[downbeat_indices]

    first_downbeat = new_downbeat_times[0] if len(new_downbeat_times) > 0 else anchor

    # Detailed debug logging for drift analysis
    # WHY: Helps diagnose timing issues by showing exact calculated positions
    if len(new_downbeat_times) >= 5:
        logger.debug(
            f"Beat grid verification (first 5 bars):\n"
            f"  Bar 1 (beat 1):  {new_downbeat_times[0]:.6f}s\n"
            f"  Bar 2 (beat 5):  {new_downbeat_times[1]:.6f}s (interval: {new_downbeat_times[1] - new_downbeat_times[0]:.6f}s)\n"
            f"  Bar 3 (beat 9):  {new_downbeat_times[2]:.6f}s (interval: {new_downbeat_times[2] - new_downbeat_times[1]:.6f}s)\n"
            f"  Bar 4 (beat 13): {new_downbeat_times[3]:.6f}s (interval: {new_downbeat_times[3] - new_downbeat_times[2]:.6f}s)\n"
            f"  Bar 5 (beat 17): {new_downbeat_times[4]:.6f}s (interval: {new_downbeat_times[4] - new_downbeat_times[3]:.6f}s)\n"
            f"  Expected bar duration at {new_bpm:.2f} BPM: {60.0 * 4 / new_bpm:.6f}s"
        )

    logger.info(
        f"Grid recalculated: {len(new_beat_times)} beats, "
        f"{len(new_downbeat_times)} downbeats"
    )

    return new_beat_times, new_downbeat_times, first_downbeat


def recalculate_beat_grid_from_manual_downbeats(
    manual_downbeat_times: np.ndarray,
    audio_duration: float
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """
    Recalculate beat grid based on manually placed downbeats.

    WHY: Allows users to define musical structure by clicking on transients.
    STRATEGY: Calculates average bar duration from downbeat intervals,
              derives BPM, and interpolates beats between downbeats.

    Args:
        manual_downbeat_times: User-placed downbeat positions in seconds
        audio_duration: Total audio duration in seconds

    Returns:
        Tuple of:
        - new_beat_times: Interpolated beat positions
        - new_downbeat_times: Manual downbeat positions (sorted)
        - calculated_bpm: BPM derived from downbeat intervals
        - first_downbeat: Position of first downbeat

    Raises:
        ValueError: If fewer than 2 downbeats provided
    """
    if len(manual_downbeat_times) < 2:
        raise ValueError("Need at least 2 downbeats to calculate beat grid")

    # Sort downbeats
    downbeat_times = np.sort(manual_downbeat_times)

    # Calculate average bar duration from downbeat intervals
    downbeat_intervals = np.diff(downbeat_times)
    median_bar_duration = float(np.median(downbeat_intervals))

    if median_bar_duration <= 0:
        raise ValueError("Invalid downbeat spacing (zero or negative interval)")

    # Calculate BPM (assuming 4/4 time: 4 beats per bar)
    calculated_bpm = (60.0 * 4) / median_bar_duration

    logger.info(f"Manual downbeats: {len(downbeat_times)} bars, "
                f"median bar duration: {median_bar_duration:.2f}s, "
                f"calculated BPM: {calculated_bpm:.1f}")

    # Generate beats between downbeats (interpolate 4 beats per bar)
    all_beats = []

    for i in range(len(downbeat_times)):
        # Add downbeat
        all_beats.append(downbeat_times[i])

        # Add 3 beats between this downbeat and next (if not last bar)
        if i < len(downbeat_times) - 1:
            bar_duration = downbeat_times[i + 1] - downbeat_times[i]
            beat_interval = bar_duration / 4

            for beat_num in range(1, 4):
                beat_time = downbeat_times[i] + (beat_num * beat_interval)
                all_beats.append(beat_time)

    # Extend beats beyond last downbeat to end of audio
    # WHY: Use direct multiplication to avoid cumulative floating-point errors
    if len(downbeat_times) > 0:
        last_downbeat = downbeat_times[-1]
        beat_interval = median_bar_duration / 4

        beats_after_count = int((audio_duration - last_downbeat) / beat_interval)
        for n in range(1, beats_after_count + 1):
            beat_time = last_downbeat + n * beat_interval
            if beat_time <= audio_duration:
                all_beats.append(beat_time)

    # Extend beats before first downbeat to start of audio
    # WHY: Use direct multiplication to avoid cumulative floating-point errors
    if len(downbeat_times) > 0:
        first_downbeat = downbeat_times[0]
        beat_interval = median_bar_duration / 4

        beats_before_count = int(first_downbeat / beat_interval)
        beats_before = []
        for n in range(1, beats_before_count + 1):
            beat_time = first_downbeat - n * beat_interval
            if beat_time >= 0:
                beats_before.append(beat_time)
        # Insert at beginning in correct order
        all_beats = sorted(beats_before) + all_beats

    new_beat_times = np.array(sorted(all_beats))
    first_downbeat = float(downbeat_times[0])

    logger.info(f"Generated {len(new_beat_times)} beats from manual downbeats")

    return new_beat_times, downbeat_times, calculated_bpm, first_downbeat
