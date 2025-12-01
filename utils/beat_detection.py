"""
Beat Detection - BeatNet integration for loop analysis

PURPOSE: Detect beats and downbeats in audio for loop segmentation
CONTEXT: Used by Loop Preview system to identify musical boundaries
"""
from pathlib import Path
from typing import Tuple, Optional, List
import numpy as np
import soundfile as sf

from utils.logger import get_logger

logger = get_logger()

# Global predictor instance (lazy loaded)
_beatnet_predictor = None
_beatnet_available = None


def is_beatnet_available() -> bool:
    """
    Check if BeatNet is available.

    Returns:
        True if BeatNet can be imported, False otherwise
    """
    global _beatnet_available

    if _beatnet_available is not None:
        return _beatnet_available

    try:
        from BeatNet.BeatNet import BeatNet
        _beatnet_available = True
        logger.info("BeatNet is available")
    except ImportError as e:
        _beatnet_available = False
        logger.warning(f"BeatNet not available: {e}")

    return _beatnet_available


def _get_beatnet_predictor():
    """
    Get or create BeatNet predictor instance (singleton pattern).

    WHY: BeatNet model loading is expensive (~2-5s), so we cache it

    Returns:
        BeatNet predictor instance or None if unavailable
    """
    global _beatnet_predictor

    if not is_beatnet_available():
        return None

    if _beatnet_predictor is None:
        try:
            from BeatNet.BeatNet import BeatNet

            # Determine device (CUDA > MPS > CPU)
            device = _get_best_device()

            logger.info(f"Loading BeatNet model on {device}...")

            # Model 1, offline mode, DBN inference for best accuracy
            _beatnet_predictor = BeatNet(
                model=1,
                mode='offline',
                inference_model='DBN',
                plot=[],  # No visualization
                thread=False,
                device=device
            )

            logger.info(f"BeatNet model loaded successfully on {device}")

        except Exception as e:
            logger.error(f"Failed to load BeatNet: {e}", exc_info=True)
            _beatnet_predictor = None

    return _beatnet_predictor


def _get_best_device() -> str:
    """
    Determine best available device for PyTorch.

    Returns:
        'cuda', 'mps', or 'cpu'
    """
    try:
        import torch

        if torch.cuda.is_available():
            return 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mps'  # Apple Silicon
        else:
            return 'cpu'

    except ImportError:
        return 'cpu'


def detect_beats_and_downbeats(
    audio_path: Path,
    bpm_hint: Optional[float] = None
) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """
    Detect beats and downbeats in audio file.

    Args:
        audio_path: Path to audio file
        bpm_hint: Optional BPM hint (not used by BeatNet, for logging only)

    Returns:
        Tuple of:
        - beat_times: Array of beat positions in seconds
        - downbeat_times: Array of downbeat positions in seconds
        - first_downbeat: Time of first downbeat in seconds
        - confidence_msg: Human-readable confidence message

    Raises:
        RuntimeError: If BeatNet is not available
        ValueError: If no beats detected
        FileNotFoundError: If audio file doesn't exist

    Example:
        >>> beats, downbeats, first_db, msg = detect_beats_and_downbeats(audio_path)
        >>> print(f"Found {len(beats)} beats, {len(downbeats)} downbeats")
        >>> print(f"First downbeat at {first_db:.2f}s")
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    predictor = _get_beatnet_predictor()

    if predictor is None:
        raise RuntimeError("BeatNet not available")

    logger.info(f"Detecting beats in: {audio_path.name}")
    if bpm_hint:
        logger.info(f"BPM hint: {bpm_hint:.1f}")

    try:
        # BeatNet expects 22050 Hz audio
        audio_data, sr = sf.read(str(audio_path), always_2d=False)

        # Convert to mono if stereo
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Resample to 22050 Hz if needed
        if sr != 22050:
            from utils.audio_processing import resample_audio
            audio_data = resample_audio(audio_data, sr, 22050)
            logger.info(f"Resampled from {sr} Hz to 22050 Hz")

        # Process with BeatNet
        # Returns: numpy_array(num_beats, 2) where columns are [beat_time, is_downbeat]
        result = predictor.process(str(audio_path))

        if result is None or len(result) == 0:
            raise ValueError("No beats detected")

        # Extract beat times and downbeat flags
        beat_times = result[:, 0]  # First column: beat times
        downbeat_flags = result[:, 1]  # Second column: 1 for downbeat, 0 for regular beat

        # Extract downbeat positions
        downbeat_indices = np.where(downbeat_flags == 1)[0]
        downbeat_times = beat_times[downbeat_indices]

        if len(downbeat_times) == 0:
            logger.warning("No downbeats detected, using first beat as downbeat")
            first_downbeat = beat_times[0] if len(beat_times) > 0 else 0.0
            downbeat_times = np.array([first_downbeat])
        else:
            first_downbeat = downbeat_times[0]

        logger.info(
            f"Detected {len(beat_times)} beats, {len(downbeat_times)} downbeats. "
            f"First downbeat at {first_downbeat:.2f}s"
        )

        confidence_msg = f"BeatNet (offline): {len(downbeat_times)} downbeats detected"

        return beat_times, downbeat_times, first_downbeat, confidence_msg

    except Exception as e:
        logger.error(f"Beat detection failed: {e}", exc_info=True)
        raise


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
    # Example: 4 bars = 4 downbeats = indices [0, 1, 2, 3] → start at 0, end at 4
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
            # Use audio duration or last downbeat + average bar duration
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
