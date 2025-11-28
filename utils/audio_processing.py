"""
Audio Processing Utilities

Utility functions for audio manipulation and processing.
"""
import numpy as np
from typing import Tuple
from utils.logger import get_logger

logger = get_logger()


def trim_leading_silence(
    audio_data: np.ndarray,
    sample_rate: int,
    threshold_db: float = -40.0,
    min_silence_duration: float = 0.5
) -> Tuple[np.ndarray, float]:
    """
    Remove silence from the beginning of an audio recording.

    This function is designed to remove the initial silence that occurs when
    starting a recording before the actual audio content begins (e.g., when
    switching to Spotify to start playback after starting the recording).

    The trimming is done at a zero-crossing point to prevent clicks and pops
    in the resulting audio.

    Args:
        audio_data: Audio array (samples x channels for stereo, or just samples for mono)
        sample_rate: Sample rate in Hz
        threshold_db: Threshold in dB below which audio is considered silence (default: -40 dB)
        min_silence_duration: Minimum duration of silence in seconds that must be present
                              to trigger trimming (default: 0.5s). This prevents trimming
                              when there's minimal silence.

    Returns:
        Tuple of (trimmed_audio_data, trimmed_duration_seconds)
        - trimmed_audio_data: Audio array with leading silence removed
        - trimmed_duration_seconds: Duration of silence that was removed (0.0 if no trimming)

    Example:
        >>> audio, sr = load_audio("recording.wav")
        >>> trimmed_audio, removed_duration = trim_leading_silence(audio, sr)
        >>> print(f"Removed {removed_duration:.2f}s of silence")
    """
    if len(audio_data) == 0:
        logger.warning("trim_leading_silence: Empty audio data")
        return audio_data, 0.0

    # 1. Convert threshold from dB to linear amplitude
    # Formula: amplitude = 10^(dB/20)
    # Example: -40 dB = 10^(-40/20) = 0.01 (1% of full scale)
    threshold_linear = 10 ** (threshold_db / 20.0)

    # 2. Find first sample above threshold
    # For stereo: take the maximum absolute value across both channels
    # This ensures we detect audio in either channel
    if audio_data.ndim > 1:
        # Stereo or multi-channel: shape is (samples, channels)
        audio_abs = np.max(np.abs(audio_data), axis=1)
    else:
        # Mono: shape is just (samples,)
        audio_abs = np.abs(audio_data)

    # 3. Find first sample that exceeds the threshold
    above_threshold = np.where(audio_abs > threshold_linear)[0]

    if len(above_threshold) == 0:
        # Entire audio is silence - don't trim
        logger.info("trim_leading_silence: Entire audio is below threshold, no trimming")
        return audio_data, 0.0

    first_sound_idx = above_threshold[0]

    # 4. Check if there's enough silence to justify trimming
    silence_duration = first_sound_idx / sample_rate

    if silence_duration < min_silence_duration:
        # Not enough silence to trim - this is likely intentional audio
        logger.debug(
            f"trim_leading_silence: Only {silence_duration:.2f}s silence "
            f"(min: {min_silence_duration}s), not trimming"
        )
        return audio_data, 0.0

    # 5. Find nearest zero-crossing before the first sound
    # This prevents clicks and pops by ensuring we cut at a point
    # where the waveform crosses zero amplitude

    trim_idx = first_sound_idx

    # Search backwards from first_sound_idx for a zero-crossing
    # Limit search to 10ms window (should be plenty for most audio)
    search_start = max(0, first_sound_idx - int(0.01 * sample_rate))

    if audio_data.ndim > 1:
        # Stereo: Look for zero-crossing in either channel
        # A zero-crossing occurs when the sign changes between consecutive samples
        for i in range(first_sound_idx - 1, search_start, -1):
            # Check if sign changes in any channel
            if np.any(np.sign(audio_data[i]) != np.sign(audio_data[i + 1])):
                trim_idx = i + 1
                break
    else:
        # Mono: Simple zero-crossing detection
        for i in range(first_sound_idx - 1, search_start, -1):
            if np.sign(audio_data[i]) != np.sign(audio_data[i + 1]):
                trim_idx = i + 1
                break

    # 6. Calculate how much silence we're removing
    trimmed_duration = trim_idx / sample_rate

    # 7. Trim the audio
    trimmed_audio = audio_data[trim_idx:]

    logger.info(
        f"trim_leading_silence: Removed {trimmed_duration:.2f}s of silence "
        f"(threshold: {threshold_db} dB, {len(audio_data) - len(trimmed_audio)} samples)"
    )

    return trimmed_audio, trimmed_duration
