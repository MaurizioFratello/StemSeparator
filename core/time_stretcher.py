"""
Time Stretcher - Pitch-preserving time-stretching for separated audio stems.

PURPOSE: Provide high-quality time-stretching for separated audio stems.
         Supports BPM-based stretching for DJ mixing, practice, and remixing.

CONTEXT: Integrated into the Loop Export workflow for processing loops
         from original BPM to target BPM while preserving pitch.

ALGORITHM: Engines are tried in this order (see `_run_engine_chain`):
           1. `rubberband-cli`        - Rubberband R3, called directly
           2. `pyrubberband`          - same binary through the 0.4.0 wrapper
           3. `librosa-phase-vocoder` - pure-Python phase vocoder fallback

           WHY: The macOS-only releases hard-required `brew install rubberband`
                and could fail at import time. On Windows/Linux the binary is
                often absent, so the module now degrades to the librosa phase
                vocoder instead of dying, and every heavy third-party import
                (pyrubberband, librosa) happens inside the engine that needs it.
                Engine changes are never silent: the engine that ran is logged
                at INFO, every skipped one at WARNING with its failure reason.

           The direct CLI call stays first because pyrubberband v0.4.0 has a
           stereo temp-file bug; the pyrubberband engine therefore stretches
           channel by channel.

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

from typing import Callable, Dict, List, Optional, Tuple
import inspect
import numpy as np
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import os

from utils import platform_utils
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


# ============================================================================
# Engines
# ============================================================================

ENGINE_CLI = "rubberband-cli"
ENGINE_PYRUBBERBAND = "pyrubberband"
ENGINE_LIBROSA = "librosa-phase-vocoder"

# Priority order for `_run_engine_chain`.
# WHY this order: the R3 CLI is transparent on musical material, the Python
# wrapper shells out to the same binary (so it only helps if the CLI exists but a
# direct call was blocked), and the phase vocoder is audible on transients — it is
# the last resort that still makes the feature work on a bare Windows/Linux box.
ENGINE_ORDER = (ENGINE_CLI, ENGINE_PYRUBBERBAND, ENGINE_LIBROSA)

class LibraryNotFoundError(TimeStretchError):
    """No usable time-stretching engine is available on this system."""
    pass


# ============================================================================
# Engine discovery
# ============================================================================

def rubberband_binary() -> Optional[str]:
    """
    Absolute path to the `rubberband` CLI, or None when it is not installed.

    WHY via platform_utils: the bundled PyInstaller layout (`packaging/vendor/bin`,
    `Contents/Resources` inside a .app on macOS, `*.exe` on Windows) differs per OS,
    and the previous hard-coded `sys._MEIPASS/bin/rubberband` check could only ever
    find a macOS binary — so every Windows/Linux session fell straight through to a
    `brew install rubberband` message that is meaningless there.
    """
    found = platform_utils.find_binary("rubberband")
    if found is None:
        return None
    return str(found)


def _install_guidance() -> str:
    """Per-OS instructions for obtaining the highest-quality engine."""
    if platform_utils.is_windows():
        return (
            "Install the Rubberband CLI (e.g. `choco install rubberband`) or ship "
            "it in packaging/vendor/bin for the packaged build."
        )
    if platform_utils.is_macos():
        return "Install it with: brew install rubberband"
    return "Install it with: apt install rubberband-cli (or your distro's equivalent)"


def available_engines() -> List[str]:
    """
    Engines usable right now, in priority order.

    Used by the UI to tell the user up front whether loop export will use the
    high-quality R3 engine or the librosa fallback.
    """
    engines: List[str] = []
    if rubberband_binary() is not None:
        engines.append(ENGINE_CLI)
        engines.append(ENGINE_PYRUBBERBAND)
    engines.append(ENGINE_LIBROSA)
    return engines


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

    rubberband_path = rubberband_binary()
    if rubberband_path is None:
        raise LibraryNotFoundError("Rubberband CLI not found. " + _install_guidance())

    try:
        result = subprocess.run(
            [rubberband_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            **platform_utils.popen_kwargs(),
        )
        if result.returncode != 0:
            raise LibraryNotFoundError(
                f"Rubberband CLI at {rubberband_path} did not run cleanly: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise LibraryNotFoundError(
            f"Rubberband CLI at {rubberband_path} is not executable ({exc}). "
            + _install_guidance()
        )

    # Create temporary files
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, 'input.wav')
    output_path = os.path.join(temp_dir, 'output.wav')

    try:
        import soundfile as sf

        # Write input to temp file
        sf.write(input_path, audio, sample_rate, subtype='FLOAT')

        # Build rubberband command (use found path)
        cmd = [rubberband_path]

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

def _time_stretch_with_pyrubberband(
    audio: np.ndarray,
    sample_rate: int,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT,
) -> np.ndarray:
    """
    Stretch through the pyrubberband wrapper, one channel at a time.

    WHY per-channel: pyrubberband 0.4.0 corrupts stereo temp files (the reason the
    original code shelled out to the CLI itself). The import is lazy so a machine
    without the package still imports this module, and the binary path is injected
    so a vendored build is used instead of whatever is on PATH.
    """
    binary = rubberband_binary()
    if binary is None:
        raise LibraryNotFoundError(
            "pyrubberband needs the Rubberband CLI. " + _install_guidance()
        )

    try:
        from pyrubberband import pyrb as _pyrb_module
    except Exception as exc:
        raise LibraryNotFoundError(f"pyrubberband unavailable: {exc}") from exc

    if getattr(_pyrb_module, "RUBBERBAND_EXE", None) != binary:
        _pyrb_module.RUBBERBAND_EXE = binary

    import soundfile as sf

    two_d = audio.reshape(-1, 1) if audio.ndim == 1 else audio
    stretched_channels = []
    temp_dir = tempfile.mkdtemp()
    try:
        for channel in range(two_d.shape[1]):
            in_path = os.path.join(temp_dir, f"in_{channel}.wav")
            out_path = os.path.join(temp_dir, f"out_{channel}.wav")
            sf.write(in_path, two_d[:, channel], sample_rate, subtype="FLOAT")

            options = [] if quality_preset == StretchQuality.EXPORT else ["-c5"]
            _pyrb_module.time_stretch_file(
                in_path, out_path, float(stretch_factor), *options
            )
            data, _sr = sf.read(out_path, dtype="float32")
            stretched_channels.append(np.asarray(data, dtype=np.float32))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return _stack_channels(stretched_channels, audio)


def _time_stretch_with_librosa(
    audio: np.ndarray,
    sample_rate: int,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT,
) -> np.ndarray:
    """
    Stretch with librosa's phase vocoder — the binary-free fallback.

    WHY: Windows and Linux ship without the Rubberband CLI, and requiring a native
    binary there made loop export simply not work. The phase vocoder is audibly
    softer on transients, so it is only reached after both Rubberband engines fail,
    and the engine that ran is always logged.
    """
    try:
        import librosa  # lazy: heavy import, only needed for the fallback
    except Exception as exc:
        raise LibraryNotFoundError(f"librosa unavailable: {exc}") from exc

    two_d = audio.reshape(-1, 1) if audio.ndim == 1 else audio
    stretched_channels = []
    for channel in range(two_d.shape[1]):
        stretched_channels.append(
            np.asarray(
                librosa.effects.time_stretch(
                    np.asfortranarray(two_d[:, channel].astype(np.float32)),
                    rate=float(stretch_factor),
                ),
                dtype=np.float32,
            )
        )

    return _stack_channels(stretched_channels, audio)


def _stack_channels(channels: List[np.ndarray], reference: np.ndarray) -> np.ndarray:
    """Re-join stretched channels, preserving the input's mono/stereo shape."""
    if not channels:
        raise ProcessingError("Time-stretching produced no channels")

    length = min(channel.shape[0] for channel in channels)
    trimmed = [channel[:length] for channel in channels]

    if reference.ndim == 1 or len(trimmed) == 1:
        return trimmed[0].astype(np.float32)

    return np.stack(trimmed, axis=1).astype(np.float32)


def _run_engine_chain(
    audio: np.ndarray,
    sample_rate: int,
    stretch_factor: float,
    quality_preset: str = StretchQuality.EXPORT,
) -> np.ndarray:
    """
    Try every available engine in priority order and report which one ran.

    WHY: the previous code raised as soon as the CLI was missing, so a user without
    Rubberband got a brew instruction and no audio. Failures stay visible — each
    skipped engine is logged with its reason, and the engine that produced the
    result is logged at INFO.
    """
    engines = {
        ENGINE_CLI: _time_stretch_with_rubberband_cli,
        ENGINE_PYRUBBERBAND: _time_stretch_with_pyrubberband,
        ENGINE_LIBROSA: _time_stretch_with_librosa,
    }

    failures: List[str] = []
    for name in ENGINE_ORDER:
        engine = engines[name]
        try:
            result = engine(audio, sample_rate, stretch_factor, quality_preset)
        except TimeStretchError as exc:
            failures.append(f"{name}: {exc}")
            logger.warning(f"Time-stretch engine '{name}' unusable: {exc}")
            continue
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            logger.warning(f"Time-stretch engine '{name}' failed: {exc}")
            continue

        if result is None or getattr(result, "size", 0) == 0:
            failures.append(f"{name}: produced empty output")
            logger.warning(f"Time-stretch engine '{name}' produced empty output")
            continue

        logger.info(
            f"Time-stretched with engine '{name}' "
            f"(factor={stretch_factor:.3f}, quality={quality_preset})"
        )
        return result

    raise LibraryNotFoundError(
        "No time-stretching engine available. Attempted: "
        + "; ".join(failures)
        + ". "
        + _install_guidance()
    )


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

    # WHY an explicit ndim guard: every engine treats >2 dims meaninglessly
    # (the phase vocoder stretches the LAST axis — a (100, 2, 2) input quietly
    # emerged as a corrupted (100, 2, 1) array instead of failing). The
    # documented formats are (samples,) and (samples, channels); anything else
    # is a caller bug and must say so.
    if audio.ndim > 2:
        raise ProcessingError(
            f"Unsupported audio shape {audio.shape}: expected (samples,) for "
            "mono or (samples, channels) for stereo"
        )
    # Log processing info
    duration_sec = len(audio) / sample_rate
    estimated_time = estimate_processing_time(duration_sec, stretch_factor, quality_preset)

    logger.debug(
        f"Time-stretching: {duration_sec:.2f}s audio, "
        f"factor={stretch_factor:.2f}, quality={quality_preset}, "
        f"estimated time={estimated_time:.1f}s"
    )

    try:
        # Engines are tried in priority order; the one that ran is logged.
        stretched = _run_engine_chain(
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
