"""
Beat Detection - BeatNet integration for loop analysis

PURPOSE: Detect beats and downbeats in audio for loop segmentation
CONTEXT: Uses BeatNet beat-service (subprocess) with DeepRhythm/librosa fallback

Strategy:
1. Primary: BeatNet beat-service binary (full beat+downbeat grid)
2. Fallback: DeepRhythm/librosa (BPM only, synthetic beat grid)
"""
from pathlib import Path
from typing import Tuple, Optional, List, Callable
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
            # Calculate dynamic timeout based on audio duration
            # Base: 30s + ~0.5s per second of audio (BeatNet processes ~2x realtime on MPS)
            try:
                info = sf.info(str(audio_path))
                audio_duration = info.duration
                timeout = max(60.0, 30.0 + audio_duration * 0.5)
                logger.debug(f"BeatNet timeout: {timeout:.0f}s for {audio_duration:.1f}s audio")
            except Exception:
                audio_duration = 0
                timeout = 120.0  # Safe default for unknown duration

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

            bpm_source_path = bpm_audio_path if bpm_audio_path and bpm_audio_path.exists() else audio_path
            bpm_source_name = "drums" if bpm_audio_path and bpm_audio_path.exists() else "mixed"

            report_progress("DeepRhythm", f"Refining BPM from {bpm_source_name} stem...")

            try:
                audio_data, sample_rate = sf.read(str(bpm_source_path), always_2d=False)
                if audio_data.ndim > 1:
                    audio_data = np.mean(audio_data, axis=1)

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

            except Exception as e:
                logger.warning(f"DeepRhythm BPM detection failed, using BeatNet: {e}")

            confidence_msg = (
                f"{tempo_source}: {final_tempo:.1f} BPM, "
                f"{len(downbeat_times)} downbeats (grid: BeatNet)"
            )

            logger.info(
                f"BeatNet analysis: {len(beat_times)} beats, "
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
    audio_duration: float
) -> List[Tuple[float, float]]:
    """
    Calculate loop segments based on downbeat positions.

    Args:
        downbeat_times: Array of downbeat positions in seconds
        bars_per_loop: Number of bars per loop (typically 2, 4, or 8)
        audio_duration: Total audio duration in seconds

    Returns:
        List of (start_time, end_time) tuples for each loop segment

    Raises:
        ValueError: If no downbeats provided or invalid bars_per_loop

    Example:
        >>> downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0])  # Every 2 seconds
        >>> loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=10.0)
        >>> # Returns [(0.0, 8.0)] - one 4-bar loop
    """
    if len(downbeat_times) == 0:
        raise ValueError("No downbeats provided")

    if bars_per_loop <= 0:
        raise ValueError(f"Invalid bars_per_loop: {bars_per_loop}")

    loops = []

    # Each loop spans bars_per_loop downbeats
    num_downbeats = len(downbeat_times)

    idx = 0
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

    logger.info(f"Calculated {len(loops)} loops ({bars_per_loop} bars each)")

    return loops
