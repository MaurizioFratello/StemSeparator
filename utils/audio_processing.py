"""
Audio Processing Utilities

Utility functions for audio manipulation and processing.
"""
import numpy as np
import soundfile as sf
import librosa
import resampy
from pathlib import Path
from typing import Tuple, Optional, List
from utils.logger import get_logger

logger = get_logger()

# Try to import DeepRhythm for enhanced BPM detection
try:
    from deeprhythm import DeepRhythmPredictor
    DEEPRHYTHM_AVAILABLE = True
    logger.info("DeepRhythm available for BPM detection")
except ImportError:
    DEEPRHYTHM_AVAILABLE = False
    logger.info("DeepRhythm not available, using librosa for BPM detection")

# Global DeepRhythm predictor (lazy loaded)
_deeprhythm_predictor = None


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
                    Chunks will be saved as "output_01.wav", "output_02.wav", etc.
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
        >>> # Creates: output_01.wav, output_02.wav, ..., output_09.wav
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

        # Generate filename with two-digit numbering
        # WHY: Consistent two-digit format (_01, _02, etc.) for better sorting and organization
        chunk_path = output_dir / f"{base_name}_{chunk_num:02d}{extension}"

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


def _get_deeprhythm_predictor():
    """
    Lazy-load the DeepRhythm predictor model.

    Returns:
        DeepRhythmPredictor instance or None if unavailable
    """
    global _deeprhythm_predictor

    if not DEEPRHYTHM_AVAILABLE:
        return None

    if _deeprhythm_predictor is None:
        try:
            # Try to use GPU acceleration if available
            # Priority: CUDA (NVIDIA) > MPS (Apple Silicon) > CPU
            try:
                import torch
                if torch.cuda.is_available():
                    device = 'cuda'
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    device = 'mps'  # Apple Silicon (M1/M2/M3)
                else:
                    device = 'cpu'
            except ImportError:
                device = 'cpu'

            _deeprhythm_predictor = DeepRhythmPredictor(device=device)
            logger.info(f"DeepRhythm model loaded on {device}")
        except Exception as e:
            logger.warning(f"Failed to load DeepRhythm model: {e}")
            return None

    return _deeprhythm_predictor


def _detect_bpm_deeprhythm(audio_data: np.ndarray, sample_rate: int) -> Tuple[float, float]:
    """
    Detect BPM using DeepRhythm CNN model (more accurate than librosa).

    Args:
        audio_data: Audio array (mono recommended)
        sample_rate: Sample rate in Hz

    Returns:
        Tuple of (bpm, confidence) where confidence is 0.0-1.0

    Raises:
        Exception: If detection fails
    """
    predictor = _get_deeprhythm_predictor()
    if predictor is None:
        raise Exception("DeepRhythm predictor not available")

    try:
        # DeepRhythm expects mono audio
        if audio_data.ndim > 1:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        # Predict BPM with confidence score
        bpm, confidence = predictor.predict_from_audio(
            audio_mono,
            sample_rate,
            include_confidence=True
        )

        return float(bpm), float(confidence)

    except Exception as e:
        logger.error(f"DeepRhythm detection failed: {e}")
        raise


def _detect_bpm_librosa(audio_data: np.ndarray, sample_rate: int) -> float:
    """
    Detect BPM using librosa's beat tracking (fallback method).

    Args:
        audio_data: Audio array (mono recommended)
        sample_rate: Sample rate in Hz

    Returns:
        Detected BPM as float

    Raises:
        Exception: If detection fails
    """
    # Use librosa's tempo estimation with improved parameters
    # onset_envelope: strength of note onsets over time
    # aggregate=np.median: robust to tempo variations
    # hop_length=512: Higher temporal resolution for better accuracy
    # start_bpm=120: Expected starting tempo (most common range)
    # std_bpm=1.0: Lower standard deviation = more precise estimation
    # ac_size=8.0: Auto-correlation window size (default, works well)
    # max_tempo=240: Prevents double-tempo detection errors

    # Use the newer API if available (librosa >= 0.10.0)
    try:
        from librosa.feature.rhythm import tempo as tempo_func
    except ImportError:
        # Fallback to old API for older librosa versions
        tempo_func = librosa.beat.tempo

    tempo = tempo_func(
        y=audio_data,
        sr=sample_rate,
        aggregate=np.median,
        hop_length=512,
        start_bpm=120.0,
        std_bpm=1.0,
        ac_size=8.0,
        max_tempo=240.0
    )

    # librosa.beat.tempo returns an array, extract the first value
    detected_bpm = float(tempo[0])

    # Additional validation: check for common tempo doubling/halving errors
    # If BPM is very high, it might be double-tempo
    if detected_bpm > 180:
        logger.info(f"Detected high BPM ({detected_bpm:.1f}), checking if half-tempo is more likely")
        half_tempo = detected_bpm / 2
        # Accept half-tempo if it falls in typical range (60-180 BPM)
        if 60 <= half_tempo <= 180:
            logger.info(f"Using half-tempo: {half_tempo:.1f} BPM")
            detected_bpm = half_tempo

    # If BPM is very low, it might be half-tempo
    elif detected_bpm < 60:
        logger.info(f"Detected low BPM ({detected_bpm:.1f}), checking if double-tempo is more likely")
        double_tempo = detected_bpm * 2
        # Accept double-tempo if it falls in typical range (60-180 BPM)
        if 60 <= double_tempo <= 180:
            logger.info(f"Using double-tempo: {double_tempo:.1f} BPM")
            detected_bpm = double_tempo

    return detected_bpm


def detect_bpm(audio_data: np.ndarray, sample_rate: int, method: str = 'auto') -> Tuple[float, Optional[float]]:
    """
    Detect BPM (tempo) of audio using the best available method.

    Automatically uses DeepRhythm (95%+ accuracy) if available, otherwise
    falls back to librosa (~75-85% accuracy). DeepRhythm is significantly
    faster and more accurate, especially for electronic music and drums.

    WHY: For sampler loop export, we need to know the BPM to calculate
    exact bar lengths. Auto-detection provides a starting point that users
    can adjust if needed.

    Args:
        audio_data: Audio array (samples,) for mono or (samples, channels) for stereo
        sample_rate: Sample rate in Hz
        method: Detection method - 'auto' (default), 'deeprhythm', or 'librosa'

    Returns:
        Tuple of (bpm, confidence) where:
        - bpm: Detected BPM as float
        - confidence: 0.0-1.0 for DeepRhythm, None for librosa

    Example:
        >>> audio, sr = load_audio("song.wav")
        >>> bpm, confidence = detect_bpm(audio, sr)
        >>> if confidence:
        >>>     print(f"Detected tempo: {bpm:.1f} BPM ({confidence:.0%} confident)")
        >>> else:
        >>>     print(f"Detected tempo: {bpm:.1f} BPM (librosa)")

    Notes:
        - For stereo audio, the function converts to mono for analysis
        - Detection works best on music with clear rhythmic elements
        - Electronic music and music with strong drums typically detect well
        - DeepRhythm provides confidence scores for better UX
        - The returned BPM should be treated as a suggestion for user review
    """
    if len(audio_data) == 0:
        logger.warning("detect_bpm: Empty audio data, returning default 120 BPM")
        return 120.0, None

    # Convert stereo to mono if needed
    if audio_data.ndim > 1:
        # Stereo: (samples, channels) -> (samples,)
        audio_mono = np.mean(audio_data, axis=1)
    else:
        audio_mono = audio_data

    # Method selection
    use_deeprhythm = (
        method == 'deeprhythm' or
        (method == 'auto' and DEEPRHYTHM_AVAILABLE)
    )

    # Try DeepRhythm first if requested/available
    if use_deeprhythm:
        try:
            bpm, confidence = _detect_bpm_deeprhythm(audio_mono, sample_rate)
            logger.info(f"DeepRhythm detected: {bpm:.1f} BPM ({confidence:.0%} confident)")
            return bpm, confidence
        except Exception as e:
            logger.warning(f"DeepRhythm failed: {e}, falling back to librosa")
            # Fall through to librosa

    # Librosa fallback or direct use
    try:
        bpm = _detect_bpm_librosa(audio_mono, sample_rate)
        logger.info(f"Librosa detected: {bpm:.1f} BPM")
        return bpm, None
    except Exception as e:
        logger.warning(f"BPM detection failed: {e}, returning default 120 BPM")
        return 120.0, None


def normalize_peak_to_dbfs(
    audio_data: np.ndarray,
    target_dbfs: float = -1.0
) -> np.ndarray:
    """
    Normalize audio to a target peak level in dBFS.

    This function scales the audio so that the loudest peak reaches the
    specified target level. Common targets:
    - -1.0 dBFS: Near maximum, leaves 1 dB headroom
    - -3.0 dBFS: Conservative, leaves 3 dB headroom
    - 0.0 dBFS: Absolute maximum (true peak normalization)

    WHY: Normalizing ensures consistent loudness across exported loops
    and maximizes the dynamic range without clipping.

    Args:
        audio_data: Audio array (samples,) for mono or (samples, channels) for stereo
        target_dbfs: Target peak level in dBFS (default: -1.0)

    Returns:
        Normalized audio array (same shape as input)

    Example:
        >>> audio, sr = load_audio("quiet_recording.wav")
        >>> normalized = normalize_peak_to_dbfs(audio, target_dbfs=-1.0)
        >>> # Peak is now at -1.0 dBFS

    Formula:
        1. Find current peak: max(abs(audio))
        2. Convert to dBFS: 20 * log10(peak)
        3. Calculate gain: 10^((target_dbfs - current_dbfs) / 20)
        4. Apply gain: audio * gain

    Notes:
        - If audio is already silent (peak == 0), returns original audio
        - If audio is already at or above target, scales down
        - Preserves the shape and number of channels
    """
    if len(audio_data) == 0:
        logger.warning("normalize_peak_to_dbfs: Empty audio data")
        return audio_data

    # Find absolute peak across all channels
    peak = np.abs(audio_data).max()

    if peak == 0:
        logger.warning("normalize_peak_to_dbfs: Audio is silent (peak = 0)")
        return audio_data

    # Convert peak to dBFS
    # Formula: dBFS = 20 * log10(amplitude)
    current_dbfs = 20 * np.log10(peak)

    # Calculate required gain
    # Formula: gain = 10^((target - current) / 20)
    gain_db = target_dbfs - current_dbfs
    gain_linear = 10 ** (gain_db / 20.0)

    # Apply gain
    normalized = audio_data * gain_linear

    logger.debug(
        f"Normalized: peak {current_dbfs:.2f} dBFS -> {target_dbfs:.2f} dBFS "
        f"(gain: {gain_db:+.2f} dB, factor: {gain_linear:.4f})"
    )

    return normalized


def resample_audio(
    audio_data: np.ndarray,
    original_sr: int,
    target_sr: int,
    quality: str = 'kaiser_best'
) -> np.ndarray:
    """
    Resample audio to a different sample rate using high-quality resampling.

    This function uses resampy's high-quality resampling algorithm to change
    the sample rate while preserving audio quality.

    WHY: Samplers may require specific sample rates (44.1kHz or 48kHz).
    High-quality resampling prevents aliasing and preserves frequency content.

    Args:
        audio_data: Audio array (samples,) for mono or (samples, channels) for stereo
        original_sr: Original sample rate in Hz
        target_sr: Target sample rate in Hz
        quality: Resampling quality ('kaiser_best', 'kaiser_fast', or 'scipy')
                 - 'kaiser_best': Highest quality, slower (default)
                 - 'kaiser_fast': Good quality, faster
                 - 'scipy': Fastest, lower quality

    Returns:
        Resampled audio array with new sample rate

    Example:
        >>> audio_44k, sr = load_audio("song_44100.wav")  # 44.1 kHz
        >>> audio_48k = resample_audio(audio_44k, 44100, 48000)
        >>> # Now at 48 kHz

    Notes:
        - If original_sr == target_sr, returns original audio unchanged
        - For stereo, resamples each channel independently
        - Uses resampy for high-quality resampling (better than scipy's default)
        - Processing order: Load → Resample → Normalize → Chunk → Export
    """
    if original_sr == target_sr:
        logger.debug(f"Resample skipped: already at {target_sr} Hz")
        return audio_data

    if len(audio_data) == 0:
        logger.warning("resample_audio: Empty audio data")
        return audio_data

    logger.info(f"Resampling: {original_sr} Hz -> {target_sr} Hz (quality: {quality})")

    try:
        # Handle stereo vs mono
        if audio_data.ndim > 1:
            # Stereo: (samples, channels)
            # Resample each channel independently
            resampled_channels = []
            for ch_idx in range(audio_data.shape[1]):
                channel = audio_data[:, ch_idx]
                resampled_ch = resampy.resample(
                    channel,
                    original_sr,
                    target_sr,
                    filter=quality
                )
                resampled_channels.append(resampled_ch)

            # Stack channels back together
            resampled = np.stack(resampled_channels, axis=1)
        else:
            # Mono: (samples,)
            resampled = resampy.resample(
                audio_data,
                original_sr,
                target_sr,
                filter=quality
            )

        logger.debug(
            f"Resampled: {len(audio_data)} samples -> {len(resampled)} samples "
            f"(ratio: {len(resampled) / len(audio_data):.4f})"
        )

        return resampled

    except Exception as e:
        logger.error(f"Resampling failed: {e}, returning original audio")
        return audio_data


def apply_tpdf_dither(
    audio_data: np.ndarray,
    bit_depth: int
) -> np.ndarray:
    """
    Apply TPDF (Triangular Probability Density Function) dither before quantization.

    Dithering adds very low-level noise to prevent quantization distortion when
    reducing bit depth. TPDF dither is considered the optimal choice for most
    audio applications as it:
    - Eliminates harmonic distortion from quantization
    - Creates a flat noise floor
    - Is perceptually transparent at proper levels

    WHY: When exporting to 16-bit, quantization can create audible distortion
    on low-level signals. Dither trades this distortion for a very quiet,
    uniform noise floor.

    Args:
        audio_data: Audio array (samples,) for mono or (samples, channels) for stereo
                   Values should be in range [-1.0, 1.0]
        bit_depth: Target bit depth (16, 24, or 32)

    Returns:
        Audio with dither applied (same shape as input)

    Example:
        >>> # Export to 16-bit with dither
        >>> audio_24bit = load_audio("source_24bit.wav")
        >>> audio_dithered = apply_tpdf_dither(audio_24bit, bit_depth=16)
        >>> save_audio(audio_dithered, "output_16bit.wav", bit_depth=16)

    Technical Details:
        - TPDF dither = sum of two uniform random distributions
        - Amplitude: ±1 LSB (least significant bit) at target bit depth
        - LSB at 16-bit: 1 / 32768 ≈ 0.000031
        - LSB at 24-bit: 1 / 8388608 ≈ 0.00000012

    Notes:
        - For 24-bit and 32-bit, dither is optional (quantization noise is very low)
        - For 16-bit, dither is highly recommended
        - Dither should be applied AFTER all DSP processing (last step before export)
        - The noise is typically inaudible but prevents low-level distortion
    """
    if bit_depth not in [16, 24, 32]:
        logger.warning(f"Unsupported bit depth {bit_depth}, skipping dither")
        return audio_data

    if len(audio_data) == 0:
        logger.warning("apply_tpdf_dither: Empty audio data")
        return audio_data

    # Calculate LSB (Least Significant Bit) amplitude for target bit depth
    # 16-bit: 2^15 = 32768 levels (signed)
    # 24-bit: 2^23 = 8388608 levels
    # 32-bit: 2^31 = 2147483648 levels (but for float, we use 24-bit equivalent)
    if bit_depth == 16:
        lsb = 1.0 / 32768.0
    elif bit_depth == 24:
        lsb = 1.0 / 8388608.0
    else:  # 32-bit
        # For 32-bit float, dither is typically unnecessary
        # But if requested, use 24-bit equivalent
        lsb = 1.0 / 8388608.0

    # Generate TPDF dither
    # TPDF = sum of two uniform random variables
    # This creates a triangular probability distribution
    # Range: [-lsb, +lsb]
    shape = audio_data.shape
    dither = np.random.uniform(-lsb, lsb, shape) + np.random.uniform(-lsb, lsb, shape)

    # Apply dither
    dithered = audio_data + dither

    # Clip to valid range (in case dither pushed a sample out of bounds)
    dithered = np.clip(dithered, -1.0, 1.0)

    logger.debug(
        f"Applied TPDF dither for {bit_depth}-bit: "
        f"LSB amplitude = {lsb:.8f}, noise RMS ≈ {lsb/np.sqrt(3):.8f}"
    )

    return dithered


def stereo_to_mono(audio_stereo: np.ndarray) -> np.ndarray:
    """
    Convert stereo audio to mono by averaging channels.

    WHY: Some samplers only support mono, or users may want mono loops
    to save memory and simplify playback.

    Args:
        audio_stereo: Stereo audio array (samples, 2)

    Returns:
        Mono audio array (samples,)

    Example:
        >>> stereo, sr = load_audio("stereo.wav")
        >>> mono = stereo_to_mono(stereo)
        >>> # Mono[n] = 0.5 * (Left[n] + Right[n])

    Formula:
        mono[n] = 0.5 * (left[n] + right[n])

    This is the standard mono mix formula that preserves perceived loudness
    and prevents clipping when channels are correlated.
    """
    if len(audio_stereo) == 0:
        logger.warning("stereo_to_mono: Empty audio data")
        return audio_stereo

    if audio_stereo.ndim == 1:
        logger.debug("stereo_to_mono: Audio is already mono")
        return audio_stereo

    if audio_stereo.shape[1] != 2:
        logger.warning(
            f"stereo_to_mono: Expected 2 channels, got {audio_stereo.shape[1]}, "
            "averaging all channels"
        )

    # Average all channels
    mono = np.mean(audio_stereo, axis=1)

    logger.debug(f"Converted to mono: {audio_stereo.shape} -> {mono.shape}")

    return mono
