"""
Time Stretcher - Pitch-preserving time-stretching using Rubberband CLI

PURPOSE: Provide high-quality time-stretching for separated audio stems.
         Supports BPM-based stretching for DJ mixing, practice, and remixing.

CONTEXT: Integrated into the Loop Export workflow for processing loops
         from original BPM to target BPM while preserving pitch.

ALGORITHM: Uses Rubberband CLI directly (via subprocess)
           - Rubberband R3 phase vocoder engine
           - Pitch-preserving (independent time/pitch modification)
           - Transient detection and preservation
           - Adaptive stretch ratio
           - Phase lamination for reduced artifacts
           - Optimized for musical content

           Note: Uses CLI instead of pyrubberband library to avoid
                 stereo audio bug in pyrubberband v0.4.0

USAGE:
    >>> from core.time_stretcher import time_stretch_audio, calculate_stretch_factor
    >>>
    >>> # Calculate stretch factor from BPM
    >>> factor = calculate_stretch_factor(current_bpm=104, target_bpm=120)
    >>> # factor = 1.15 (15% faster)
    >>>
    >>> # Time-stretch audio (uses EXPORT quality by default)
    >>> stretched = time_stretch_audio(
    ...     audio=audio_array,
    ...     sample_rate=44100,
    ...     stretch_factor=factor
    ... )
"""

from typing import Optional, Tuple
import numpy as np
from pathlib import Path
import subprocess
import tempfile
import os

from utils.logger import get_logger

logger = get_logger()


# ============================================================================
# Quality Presets
# ============================================================================

class StretchQuality:
    """
    Quality presets for time-stretching.

    PREVIEW: Balanced quality and speed for background processing
             - Uses R2 engine with crispness level 5
             - Suitable for quick preview
             - ~1-2 seconds per 10-second loop

    EXPORT:  Maximum quality (default)
             - Uses R3 engine with long processing window
             - Best quality for all stem types
             - Slower processing (~2x compared to PREVIEW)
             - ~3-5 seconds per 10-second loop
             - Default choice for all time-stretching operations
    """
    PREVIEW = 'preview'
    EXPORT = 'export'


# ============================================================================
# Exceptions
# ============================================================================

class TimeStretchError(Exception):
    """Base exception for time-stretching errors"""
    pass


class InvalidStretchFactorError(TimeStretchError):
    """Stretch factor outside valid range"""
    pass


class ProcessingError(TimeStretchError):
    """Runtime processing failure"""
    pass


class LibraryNotFoundError(TimeStretchError):
    """PyRubberBand library not installed"""
    pass


# ============================================================================
# Utility Functions
# ============================================================================

def calculate_stretch_factor(current_bpm: float, target_bpm: float) -> float:
    """
    Calculate time-stretch factor from BPM change.

    Args:
        current_bpm: Original BPM (from detection or user input)
        target_bpm: Target BPM (user-specified)

    Returns:
        Stretch factor:
        - 1.0 = no change
        - >1.0 = faster (e.g., 1.15 = 15% faster)
        - <1.0 = slower (e.g., 0.85 = 15% slower)

    Example:
        >>> calculate_stretch_factor(104, 120)
        1.1538461538461537  # ~15.4% faster

        >>> calculate_stretch_factor(120, 90)
        0.75  # 25% slower
    """
    if current_bpm <= 0 or target_bpm <= 0:
        raise ValueError(f"BPM values must be positive: current={current_bpm}, target={target_bpm}")

    return target_bpm / current_bpm


def validate_stretch_factor(factor: float, min_factor: float = 0.5, max_factor: float = 2.0) -> bool:
    """
    Validate stretch factor is within safe range.

    Args:
        factor: Stretch factor to validate
        min_factor: Minimum allowed factor (default: 0.5 = half speed)
        max_factor: Maximum allowed factor (default: 2.0 = double speed)

    Returns:
        True if valid, raises InvalidStretchFactorError otherwise

    Raises:
        InvalidStretchFactorError: If factor is outside safe range

    Note:
        Safe range [0.5, 2.0] is recommended for musical content.
        Extreme factors may introduce audible artifacts.
    """
    if not min_factor <= factor <= max_factor:
        raise InvalidStretchFactorError(
            f"Stretch factor {factor:.2f} outside safe range [{min_factor}, {max_factor}]. "
            f"Extreme factors may degrade audio quality."
        )

    return True


def estimate_processing_time(
    audio_duration_seconds: float,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT
) -> float:
    """
    Estimate processing time for time-stretching.

    Args:
        audio_duration_seconds: Duration of input audio
        stretch_factor: Time-stretch factor
        quality_preset: Quality preset (PREVIEW or EXPORT)

    Returns:
        Estimated processing time in seconds

    Note:
        Estimates based on benchmarks (Intel i7, single core):
        - PREVIEW: ~0.15x real-time (10s audio → 1.5s processing)
        - EXPORT: ~0.30x real-time (10s audio → 3.0s processing)
    """

    # Base processing factor (seconds processing per second of audio)
    if quality_preset == StretchQuality.EXPORT:
        base_factor = 0.30
    else:
        base_factor = 0.15

    # Extreme stretch factors may increase processing time
    if stretch_factor < 0.7 or stretch_factor > 1.5:
        base_factor *= 1.3

    return audio_duration_seconds * base_factor


# ============================================================================
# Rubberband CLI Integration
# ============================================================================

def _time_stretch_with_rubberband_cli(
    audio: np.ndarray,
    sample_rate: int,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT
) -> np.ndarray:
    """
    Time-stretch audio using Rubberband CLI (bypasses pyrubberband bug).

    This implementation calls the `rubberband` binary directly via subprocess,
    which fixes the pyrubberband v0.4.0 bug with stereo audio temp files.

    Args:
        audio: Audio array (mono or stereo)
        sample_rate: Sample rate in Hz
        stretch_factor: Time-stretch factor
        quality_preset: Quality preset (PREVIEW or EXPORT)

    Returns:
        Time-stretched audio array

    Raises:
        LibraryNotFoundError: If rubberband binary not found
        ProcessingError: If processing fails
    """

    # Check if rubberband binary exists
    try:
        result = subprocess.run(
            ['rubberband', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            raise LibraryNotFoundError("rubberband binary not found or not working")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise LibraryNotFoundError(
            "Rubberband CLI not found. Please install it with: brew install rubberband"
        )

    # Create temporary files
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, 'input.wav')
    output_path = os.path.join(temp_dir, 'output.wav')

    try:
        import soundfile as sf

        # Write input to temp file
        sf.write(input_path, audio, sample_rate, subtype='FLOAT')

        # Build rubberband command
        cmd = ['rubberband']

        # Add quality options
        if quality_preset == StretchQuality.EXPORT:
            # Highest quality settings (use R3 engine)
            cmd.extend([
                '--fine',            # Use R3 (finer) engine
                '--window-long',     # Longer window for maximum quality
            ])
        else:  # PREVIEW
            # Balanced quality/speed (use R2 engine - default)
            cmd.extend([
                '-c5',               # Good transient preservation
            ])

        # Add tempo stretch factor
        # Use --tempo instead of --time because:
        # --tempo X = speed up by factor X (X > 1 = faster)
        # --time X = stretch to X times duration (X > 1 = longer/slower)
        # Our stretch_factor is target_bpm/original_bpm, so >1 means faster
        cmd.append(f'-T{stretch_factor}')

        # Add input/output paths
        cmd.extend([input_path, output_path])

        logger.debug(f"Rubberband CLI command: {' '.join(cmd)}")

        # Execute rubberband
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )

        if result.returncode != 0:
            raise ProcessingError(
                f"Rubberband CLI failed (exit code {result.returncode}): {result.stderr}"
            )

        # Read output
        stretched, _ = sf.read(output_path, always_2d=False)

        return stretched

    except Exception as e:
        if isinstance(e, (LibraryNotFoundError, ProcessingError)):
            raise
        else:
            raise ProcessingError(f"Rubberband CLI processing failed: {e}") from e

    finally:
        # Cleanup temp files
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up temp files: {e}")


# ============================================================================
# Core Time-Stretching Function
# ============================================================================

def time_stretch_audio(
    audio: np.ndarray,
    sample_rate: int,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT
) -> np.ndarray:
    """
    Time-stretch audio while preserving pitch using Rubberband CLI.

    Args:
        audio: Audio array
               - Mono: shape (samples,)
               - Stereo: shape (samples, 2)
        sample_rate: Sample rate in Hz (typically 44100 or 48000)
        stretch_factor: Time-stretch factor
                       - 1.0 = no change
                       - 1.15 = 15% faster (e.g., 104 BPM → 120 BPM)
                       - 0.75 = 25% slower (e.g., 120 BPM → 90 BPM)
        quality_preset: Quality preset (default: StretchQuality.EXPORT)
                       - StretchQuality.PREVIEW: Balanced quality/speed (R2 engine, crisp 5)
                       - StretchQuality.EXPORT: Maximum quality (R3 engine, long window)

    Returns:
        Time-stretched audio array (same format as input)

    Raises:
        InvalidStretchFactorError: If stretch_factor outside safe range [0.5, 2.0]
        LibraryNotFoundError: If rubberband binary not found
        ProcessingError: If time-stretching fails

    Example:
        >>> # Stretch drums loop from 104 BPM to 120 BPM
        >>> audio_data, sr = sf.read('drums_loop.wav')
        >>> stretch_factor = 120 / 104  # 1.15
        >>> stretched = time_stretch_audio(audio_data, sr, stretch_factor)
        >>> sf.write('drums_loop_120bpm.wav', stretched, sr)

    Performance:
        - 10-second stereo audio @ 44100 Hz:
          - PREVIEW quality: ~1.5 seconds processing
          - EXPORT quality: ~3.0 seconds processing

    Algorithm Details:
        Uses Rubberband R3 CLI engine:
        - Analyzes audio in frequency domain
        - Adjusts time scale without affecting pitch
        - Preserves transients with adaptive detection
        - Phase lamination reduces artifacts
        - Optimized for musical signals

    Implementation Note:
        Uses Rubberband CLI via subprocess instead of pyrubberband library
        to avoid stereo audio bug in pyrubberband v0.4.0
    """

    # Validate inputs
    validate_stretch_factor(stretch_factor)

    if audio.size == 0:
        raise ProcessingError("Input audio is empty")

    if sample_rate <= 0:
        raise ValueError(f"Invalid sample rate: {sample_rate}")

    # Log processing info
    duration_sec = len(audio) / sample_rate
    estimated_time = estimate_processing_time(duration_sec, stretch_factor, quality_preset)

    logger.debug(
        f"Time-stretching: {duration_sec:.2f}s audio, "
        f"factor={stretch_factor:.2f}, quality={quality_preset}, "
        f"estimated time={estimated_time:.1f}s"
    )

    try:
        # Use Rubberband CLI (bypasses pyrubberband stereo bug)
        stretched = _time_stretch_with_rubberband_cli(
            audio, sample_rate, stretch_factor, quality_preset
        )

        # Validate output
        if stretched.size == 0:
            raise ProcessingError("Time-stretching produced empty output")

        # Calculate actual output duration
        output_duration = len(stretched) / sample_rate
        expected_duration = duration_sec / stretch_factor

        logger.debug(
            f"Time-stretching complete: "
            f"output duration={output_duration:.2f}s "
            f"(expected {expected_duration:.2f}s)"
        )

        return stretched

    except Exception as e:
        if isinstance(e, TimeStretchError):
            raise
        else:
            raise ProcessingError(f"Time-stretching failed: {e}") from e


# ============================================================================
# Batch Processing Utilities
# ============================================================================

def time_stretch_file(
    input_path: Path,
    output_path: Path,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT
) -> bool:
    """
    Time-stretch an audio file.

    Convenience function for file-based processing.

    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        stretch_factor: Time-stretch factor
        quality_preset: Quality preset

    Returns:
        True if successful, False otherwise

    Example:
        >>> success = time_stretch_file(
        ...     Path('drums.wav'),
        ...     Path('drums_120bpm.wav'),
        ...     stretch_factor=1.15
        ... )
    """

    try:
        import soundfile as sf

        # Load audio
        audio, sr = sf.read(str(input_path), always_2d=False)

        logger.info(
            f"Loaded {input_path.name}: {len(audio)/sr:.2f}s, {sr} Hz, "
            f"{'stereo' if audio.ndim > 1 else 'mono'}"
        )

        # Time-stretch
        stretched = time_stretch_audio(audio, sr, stretch_factor, quality_preset)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), stretched, sr)

        logger.info(f"Saved time-stretched audio: {output_path.name}")

        return True

    except Exception as e:
        logger.error(f"Failed to time-stretch file {input_path.name}: {e}", exc_info=True)
        return False


def get_stretch_factor_description(stretch_factor: float) -> str:
    """
    Get human-readable description of stretch factor.

    Args:
        stretch_factor: Stretch factor

    Returns:
        Description string

    Example:
        >>> get_stretch_factor_description(1.15)
        '↑ +15.4% faster'

        >>> get_stretch_factor_description(0.75)
        '↓ -25.0% slower'
    """

    percent_change = (stretch_factor - 1.0) * 100

    if abs(percent_change) < 0.1:
        return "No change"

    direction = "↑" if stretch_factor > 1.0 else "↓"
    sign = "+" if percent_change > 0 else ""
    speed_desc = "faster" if stretch_factor > 1.0 else "slower"

    return f"{direction} {sign}{percent_change:.1f}% {speed_desc}"


# ============================================================================
# Quality Settings (for future enhancement)
# ============================================================================

# Future enhancement: Allow users to customize Rubber Band options
# Currently using default settings for simplicity
#
# Advanced options could include:
# - Transient detection mode (crisp/mixed/smooth)
# - Phase lamination
# - Formant preservation
# - Pitch shift (currently always 0 - pitch-preserving only)
#
# Example implementation:
# RUBBERBAND_OPTIONS = {
#     StretchQuality.PREVIEW: {
#         'transients': 'mixed',
#         'detector': 'compound',
#     },
#     StretchQuality.EXPORT: {
#         'transients': 'smooth',
#         'detector': 'compound',
#         'formant': True,
#     }
# }
