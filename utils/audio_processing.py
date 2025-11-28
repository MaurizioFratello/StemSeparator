"""
Audio Processing Utilities

Utility functions for audio manipulation and processing.
"""
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Tuple, Optional, List
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


def find_nearest_zero_crossing(
    audio_data: np.ndarray,
    target_index: int,
    sample_rate: int,
    max_search_duration: float = 0.050
) -> Optional[int]:
    """
    Find the nearest zero-crossing point before a target index.

    This function searches backwards from a target sample index to find a point
    where the audio waveform crosses zero amplitude. This is used to create
    clean audio splits without clicks or pops.

    WHY: When splitting audio into chunks, cutting at arbitrary points can create
    audible clicks. Cutting at zero-crossings (where the waveform crosses 0)
    ensures clean, click-free splits.

    Args:
        audio_data: Audio array (samples x channels for stereo, or just samples for mono)
        target_index: The ideal split point (sample index)
        sample_rate: Sample rate in Hz
        max_search_duration: Maximum time to search backwards in seconds (default: 50ms)

    Returns:
        Sample index of nearest zero-crossing, or None if none found within search window

    Example:
        >>> # Find zero-crossing before sample 48000 (1 second at 48kHz)
        >>> zc_index = find_nearest_zero_crossing(audio, 48000, 48000)
        >>> if zc_index:
        >>>     chunk1 = audio[:zc_index]
        >>>     chunk2 = audio[zc_index:]
    """
    if len(audio_data) == 0 or target_index <= 0:
        return None

    # Calculate search window
    max_search_samples = int(max_search_duration * sample_rate)
    search_start = max(0, target_index - max_search_samples)

    # Handle stereo vs mono
    if audio_data.ndim > 1:
        # Stereo/multi-channel: Look for zero-crossing in ANY channel
        # This is conservative - ensures smooth transition in all channels
        for i in range(target_index - 1, search_start, -1):
            # Zero-crossing occurs when sign changes between consecutive samples
            # Check all channels
            current_signs = np.sign(audio_data[i])
            next_signs = np.sign(audio_data[i + 1])

            # If ANY channel has a sign change, it's a zero-crossing
            if np.any(current_signs != next_signs):
                # Return the sample AFTER the zero-crossing
                # (i.e., the first sample of the new sign)
                return i + 1
    else:
        # Mono: Simple zero-crossing detection
        for i in range(target_index - 1, search_start, -1):
            if np.sign(audio_data[i]) != np.sign(audio_data[i + 1]):
                return i + 1

    # No zero-crossing found in search window
    logger.debug(
        f"find_nearest_zero_crossing: No zero-crossing found within {max_search_duration*1000:.0f}ms "
        f"of target index {target_index}"
    )
    return None


def export_audio_chunks(
    audio_data: np.ndarray,
    sample_rate: int,
    output_path: Path,
    chunk_length_seconds: float,
    file_format: str = 'WAV',
    bit_depth: int = 24
) -> List[Path]:
    """
    Export audio data split into chunks at zero-crossings.

    This function splits audio into chunks of approximately the specified length,
    with splits occurring at zero-crossings to prevent clicks and pops.
    Each chunk starts exactly where the previous chunk ended (no gaps or overlaps).

    WHY: Samplers often have file size/length limits. This function creates
    sampler-compatible chunks while maintaining audio quality and continuity.

    Args:
        audio_data: Audio array (channels x samples) - NOTE: different from other functions!
        sample_rate: Sample rate in Hz
        output_path: Base output path (e.g., "/path/to/output.wav")
                    Chunks will be saved as "output_1.wav", "output_2.wav", etc.
        chunk_length_seconds: Target length of each chunk in seconds
        file_format: Audio format ('WAV' or 'FLAC')
        bit_depth: Bit depth (16, 24, or 32)

    Returns:
        List of Path objects for all created chunk files

    Behavior:
    - Chunks will be EXACTLY chunk_length_seconds or slightly shorter (never longer)
    - Splits occur at zero-crossings when possible (within 50ms search window)
    - Each chunk starts where the previous ended (no audio loss)
    - Last chunk may be shorter than chunk_length_seconds

    Example:
        >>> # Split 180s audio into ~20s chunks
        >>> chunks = export_audio_chunks(
        >>>     audio, 48000, Path("output.wav"), chunk_length_seconds=20.0
        >>> )
        >>> # Creates: output_1.wav, output_2.wav, ..., output_9.wav
        >>> print(f"Created {len(chunks)} chunks")
    """
    if len(audio_data) == 0:
        logger.error("export_audio_chunks: Empty audio data")
        return []

    # Transpose audio to (samples, channels) for soundfile
    # Input is (channels, samples), soundfile expects (samples, channels)
    if audio_data.ndim > 1:
        audio_transposed = audio_data.T
    else:
        audio_transposed = audio_data.reshape(-1, 1)  # Mono -> (samples, 1)

    total_samples = audio_transposed.shape[0]
    chunk_samples = int(chunk_length_seconds * sample_rate)

    # Prepare output path
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = output_path.stem  # Filename without extension
    extension = output_path.suffix if output_path.suffix else f".{file_format.lower()}"

    # Determine subtype for soundfile
    subtype_map = {
        16: 'PCM_16',
        24: 'PCM_24',
        32: 'PCM_32'
    }
    subtype = subtype_map.get(bit_depth, 'PCM_24')

    chunk_paths = []
    current_pos = 0
    chunk_num = 1

    logger.info(
        f"Splitting audio into chunks: {total_samples / sample_rate:.1f}s total, "
        f"{chunk_length_seconds}s per chunk, {file_format} {bit_depth}bit"
    )

    while current_pos < total_samples:
        # Calculate ideal end position for this chunk
        ideal_end = min(current_pos + chunk_samples, total_samples)

        # Find zero-crossing near ideal end (but not past it!)
        if ideal_end < total_samples:
            # Not the last chunk - try to find zero-crossing
            zc_end = find_nearest_zero_crossing(
                audio_transposed,
                ideal_end,
                sample_rate,
                max_search_duration=0.050  # 50ms search window
            )

            if zc_end and zc_end > current_pos:
                # Found a zero-crossing - use it
                actual_end = zc_end
                zc_offset_ms = (ideal_end - actual_end) / sample_rate * 1000
                logger.debug(
                    f"Chunk {chunk_num}: Using zero-crossing at {actual_end} "
                    f"({zc_offset_ms:+.1f}ms from ideal)"
                )
            else:
                # No zero-crossing found - use ideal position
                actual_end = ideal_end
                logger.debug(
                    f"Chunk {chunk_num}: No zero-crossing found, using ideal position"
                )
        else:
            # Last chunk - use remaining audio
            actual_end = total_samples

        # Extract chunk
        chunk_data = audio_transposed[current_pos:actual_end]
        chunk_duration = len(chunk_data) / sample_rate

        # Generate filename
        chunk_path = output_dir / f"{base_name}_{chunk_num}{extension}"

        # Save chunk
        try:
            sf.write(
                str(chunk_path),
                chunk_data,
                sample_rate,
                subtype=subtype,
                format=file_format
            )
            logger.info(
                f"Exported chunk {chunk_num}: {chunk_path.name} "
                f"({chunk_duration:.2f}s, {len(chunk_data)} samples)"
            )
            chunk_paths.append(chunk_path)
        except Exception as e:
            logger.error(f"Failed to export chunk {chunk_num}: {e}")
            # Continue with next chunk even if one fails

        # Move to next chunk (starts exactly where this one ended)
        current_pos = actual_end
        chunk_num += 1

    logger.info(f"Successfully exported {len(chunk_paths)} chunks")
    return chunk_paths
