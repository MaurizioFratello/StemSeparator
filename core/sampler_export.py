"""
Sampler Export - Export audio as musically-timed loops for samplers

PURPOSE: Export audio files as precise musical loops (2/4/8 bars) optimized for samplers.
         Handles BPM detection, bar length calculation, chunking, and zero-crossing splits.

CONTEXT: Integrated into the Player widget's export functionality.
         Supports samplers with max 20-second sample length limitation.

FUTURE EXTENSION POINT: alignToTempoGrid()
    In the current implementation, export always starts at sample 0.
    A future enhancement could add automatic grid alignment:

    def alignToTempoGrid(audio, bpm, sample_rate, time_signature=(4, 4)):
        '''
        Align audio to musical tempo grid by detecting optimal start point.

        This function would:
        - Analyze onset strengths to find likely downbeats
        - Calculate offset from sample 0 to nearest musical grid point
        - Optionally trim or pad audio to align with grid

        Args:
            audio: Audio buffer
            bpm: Detected or specified BPM
            sample_rate: Sample rate
            time_signature: Tuple (beats, beat_value), default (4, 4)

        Returns:
            Tuple (aligned_audio, offset_samples, confidence_score)
        '''

    This would enable fully automatic loop extraction from arbitrary audio positions,
    but is intentionally omitted from v1 to keep scope manageable.
"""
from pathlib import Path
from typing import Optional, List, Callable, Tuple
from dataclasses import dataclass
import numpy as np
import soundfile as sf

from utils.logger import get_logger
from utils.loop_math import (
    compute_samples_per_chunk,
    compute_chunk_duration_seconds,
    is_valid_for_sampler,
    get_minimum_bpm
)
from utils.audio_processing import (
    detect_bpm,
    normalize_peak_to_dbfs,
    resample_audio,
    apply_tpdf_dither,
    stereo_to_mono,
    find_nearest_zero_crossing
)

logger = get_logger()


@dataclass
class ExportResult:
    """
    Result of sampler loop export operation.

    Attributes:
        success: True if export completed successfully
        error_message: Error description if success=False, None otherwise
        warning_messages: List of non-critical warnings (e.g., short last chunk)
        output_files: List of exported file paths
        chunk_count: Number of chunks exported
        samples_per_chunk: Target samples per chunk (may vary slightly due to zero-crossing)
        zero_crossing_shifts: List of zero-crossing adjustments per chunk (in samples)
        effective_durations_sec: Actual duration of each exported chunk (in seconds)
    """
    success: bool
    error_message: Optional[str] = None
    warning_messages: List[str] = None
    output_files: List[Path] = None
    chunk_count: int = 0
    samples_per_chunk: int = 0
    zero_crossing_shifts: List[int] = None
    effective_durations_sec: List[float] = None

    def __post_init__(self):
        """Initialize mutable default values"""
        if self.warning_messages is None:
            self.warning_messages = []
        if self.output_files is None:
            self.output_files = []
        if self.zero_crossing_shifts is None:
            self.zero_crossing_shifts = []
        if self.effective_durations_sec is None:
            self.effective_durations_sec = []


def export_sampler_loops(
    input_path: Path,
    output_dir: Path,
    bpm: int,
    bars: int,
    sample_rate: int = 44100,
    bit_depth: int = 24,
    channels: int = 2,
    file_format: str = 'WAV',
    max_duration_seconds: float = 20.0,
    progress_callback: Optional[Callable[[str, int], None]] = None
) -> ExportResult:
    """
    Export audio as musically-timed sampler loops.

    This function implements the complete sampler export pipeline:
    1. Load audio
    2. Detect or validate BPM
    3. Resample to target sample rate (if needed)
    4. Convert to mono/stereo as requested
    5. Normalize to -1.0 dBFS peak
    6. Calculate exact chunk length based on BPM and bars
    7. Split into chunks with zero-crossing optimization
    8. Apply dither (for 16-bit)
    9. Export chunks with descriptive filenames

    Args:
        input_path: Path to input audio file
        output_dir: Directory for exported files
        bpm: Beats per minute (integer, will be rounded if float)
        bars: Number of bars per chunk (2, 4, or 8 typically)
        sample_rate: Target sample rate (44100 or 48000 recommended)
        bit_depth: Target bit depth (16, 24, or 32)
        channels: Target channels (1=mono, 2=stereo)
        file_format: Export format ('WAV', 'AIFF', or 'FLAC')
        max_duration_seconds: Maximum chunk duration for sampler compatibility (default: 20.0)
        progress_callback: Optional callback(message: str, percent: int) for progress updates

    Returns:
        ExportResult with success status, files, warnings, and metadata

    File Naming Convention:
        Single chunk: "<basename>_<BPM>_<bars>t.<ext>"
        Multiple chunks: "<basename>_<BPM>_<bars>t_part<NN>.<ext>"

        Examples:
            "MyLoop_120_4t.wav"
            "Bassline_98_2t_part01.flac"
            "DrumBreak_140_8t_part02.wav"

    Behavior:
        - Export always starts at sample 0 (no automatic grid alignment in v1)
        - Chunks are cut at zero-crossings when possible (within ±5 samples)
        - If input is shorter than one chunk: exports single file with warning
        - If input is longer than one chunk: splits into multiple chunks
        - Last chunk may be shorter than requested length
        - No padding, no looping, no time-stretching
        - 20-second limit is enforced (returns error if BPM+bars exceeds limit)

    Example:
        >>> result = export_sampler_loops(
        ...     input_path=Path("beat.wav"),
        ...     output_dir=Path("export/"),
        ...     bpm=120,
        ...     bars=4,
        ...     sample_rate=48000,
        ...     bit_depth=16,
        ...     channels=2
        ... )
        >>> if result.success:
        ...     print(f"Exported {result.chunk_count} chunks")
        ...     for file in result.output_files:
        ...         print(f"  - {file.name}")
    """
    # Report progress helper
    def report_progress(message: str, percent: int):
        logger.debug(f"Export progress: {message} ({percent}%)")
        if progress_callback:
            progress_callback(message, percent)

    # Validate inputs
    if not input_path.exists():
        return ExportResult(
            success=False,
            error_message=f"Input file not found: {input_path}"
        )

    # Round BPM to integer (as specified in requirements)
    bpm = round(bpm)

    # Validate BPM + bars combination against sampler limit
    is_valid, validation_error = is_valid_for_sampler(
        bpm, bars, max_duration_seconds
    )
    if not is_valid:
        return ExportResult(
            success=False,
            error_message=f"Invalid BPM/bars combination: {validation_error}"
        )

    report_progress("Loading audio file", 5)

    try:
        # Load audio
        audio_data, original_sr = sf.read(str(input_path), always_2d=False)
        logger.info(
            f"Loaded: {input_path.name}, {original_sr} Hz, "
            f"{audio_data.shape}, dtype={audio_data.dtype}"
        )

    except Exception as e:
        return ExportResult(
            success=False,
            error_message=f"Failed to load audio: {e}"
        )

    report_progress("Processing audio (resample, normalize)", 15)

    try:
        # Signal processing pipeline
        # Step 1: Resample (if needed)
        if original_sr != sample_rate:
            audio_data = resample_audio(audio_data, original_sr, sample_rate)

        # Step 2: Channel conversion
        if channels == 1 and audio_data.ndim > 1:
            # Convert stereo to mono
            audio_data = stereo_to_mono(audio_data)
        elif channels == 2 and audio_data.ndim == 1:
            # Convert mono to stereo (duplicate channel)
            audio_data = np.stack([audio_data, audio_data], axis=1)

        # Step 3: Normalize
        audio_data = normalize_peak_to_dbfs(audio_data, target_dbfs=-1.0)

    except Exception as e:
        return ExportResult(
            success=False,
            error_message=f"Audio processing failed: {e}"
        )

    report_progress("Calculating chunk parameters", 25)

    # Calculate chunk parameters
    try:
        samples_per_chunk = compute_samples_per_chunk(bpm, bars, sample_rate)
        chunk_duration = compute_chunk_duration_seconds(bpm, bars)

        logger.info(
            f"Chunk parameters: {bars} bars at {bpm} BPM = "
            f"{chunk_duration:.3f}s = {samples_per_chunk} samples @ {sample_rate} Hz"
        )

    except Exception as e:
        return ExportResult(
            success=False,
            error_message=f"Chunk calculation failed: {e}"
        )

    # Prepare for chunking
    total_samples = len(audio_data)
    warnings = []
    output_files = []
    zero_crossing_shifts = []
    effective_durations = []

    # Check if audio is shorter than one chunk
    if total_samples < samples_per_chunk:
        warnings.append(
            f"Input audio shorter than requested bar length "
            f"({total_samples / sample_rate:.2f}s < {chunk_duration:.2f}s); "
            "exporting original length."
        )

    # Determine number of chunks
    num_chunks = max(1, int(np.ceil(total_samples / samples_per_chunk)))

    logger.info(
        f"Chunking: {total_samples} samples ({total_samples / sample_rate:.2f}s) "
        f"-> {num_chunks} chunk(s) of {samples_per_chunk} samples each"
    )

    # Setup output directory and file naming
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = input_path.stem  # Filename without extension
    extension = f".{file_format.lower()}"

    # Determine soundfile subtype
    subtype_map = {
        16: 'PCM_16',
        24: 'PCM_24',
        32: 'PCM_32'
    }
    subtype = subtype_map.get(bit_depth, 'PCM_24')

    report_progress(f"Exporting {num_chunks} chunk(s)", 35)

    # Export chunks
    current_pos = 0
    for chunk_idx in range(num_chunks):
        # Calculate progress (35% to 95%, leaving 5% for finalization)
        chunk_progress = 35 + int((chunk_idx / num_chunks) * 60)
        report_progress(
            f"Exporting chunk {chunk_idx + 1}/{num_chunks}",
            chunk_progress
        )

        # Calculate ideal chunk end
        ideal_end = min(current_pos + samples_per_chunk, total_samples)

        # Find zero-crossing near ideal end (but not for the very last sample)
        if ideal_end < total_samples:
            # Not the last chunk - try zero-crossing optimization
            zc_end = find_nearest_zero_crossing(
                audio_data,
                ideal_end,
                sample_rate,
                max_search_duration=0.050  # 50ms search window (spec allows ±5 samples)
            )

            # Validate zero-crossing is within acceptable range
            # Spec: ±5 samples tolerance
            if zc_end and abs(zc_end - ideal_end) <= 5:
                actual_end = zc_end
                zc_shift = ideal_end - actual_end
            else:
                # Zero-crossing out of range or not found - use ideal position
                actual_end = ideal_end
                zc_shift = 0
        else:
            # Last chunk - use remaining audio
            actual_end = total_samples
            zc_shift = 0

        # Additional safety check: ensure we don't exceed 20-second limit
        chunk_duration_sec = (actual_end - current_pos) / sample_rate
        if chunk_duration_sec > max_duration_seconds:
            # This should rarely happen due to earlier validation,
            # but safety-check prevents exceeding sampler limit
            logger.warning(
                f"Chunk {chunk_idx + 1} would exceed {max_duration_seconds}s limit, "
                "cutting at exact position"
            )
            actual_end = current_pos + samples_per_chunk
            zc_shift = 0
            chunk_duration_sec = (actual_end - current_pos) / sample_rate

        # Extract chunk
        chunk_data = audio_data[current_pos:actual_end]

        # Check if last chunk is shorter than requested
        if chunk_idx == num_chunks - 1 and len(chunk_data) < samples_per_chunk * 0.8:
            # Last chunk is significantly shorter (< 80% of target)
            warnings.append(
                f"Last chunk shorter than requested bar length "
                f"({len(chunk_data) / sample_rate:.2f}s vs {chunk_duration:.2f}s); "
                "exporting remaining audio."
            )

        # Apply dither (if 16-bit)
        if bit_depth == 16:
            chunk_data = apply_tpdf_dither(chunk_data, bit_depth)

        # Generate filename
        if num_chunks == 1:
            # Single chunk: <name>_<BPM>_<bars>t.<ext>
            filename = f"{base_name}_{bpm}_{bars}t{extension}"
        else:
            # Multiple chunks: <name>_<BPM>_<bars>t_part<NN>.<ext>
            filename = f"{base_name}_{bpm}_{bars}t_part{chunk_idx + 1:02d}{extension}"

        output_path = output_dir / filename

        # Export chunk
        try:
            sf.write(
                str(output_path),
                chunk_data,
                sample_rate,
                subtype=subtype,
                format=file_format
            )

            logger.info(
                f"Exported chunk {chunk_idx + 1}/{num_chunks}: {filename} "
                f"({chunk_duration_sec:.3f}s, {len(chunk_data)} samples, "
                f"ZC shift: {zc_shift:+d} samples)"
            )

            output_files.append(output_path)
            zero_crossing_shifts.append(zc_shift)
            effective_durations.append(chunk_duration_sec)

        except Exception as e:
            return ExportResult(
                success=False,
                error_message=f"Failed to export chunk {chunk_idx + 1}: {e}",
                warning_messages=warnings,
                output_files=output_files  # Return what we managed to export
            )

        # Move to next chunk (no gaps, no overlaps)
        current_pos = actual_end

    report_progress("Export complete", 100)

    logger.info(
        f"Export successful: {len(output_files)} file(s) exported to {output_dir}"
    )

    return ExportResult(
        success=True,
        warning_messages=warnings,
        output_files=output_files,
        chunk_count=len(output_files),
        samples_per_chunk=samples_per_chunk,
        zero_crossing_shifts=zero_crossing_shifts,
        effective_durations_sec=effective_durations
    )


def detect_audio_bpm(audio_path: Path) -> Tuple[float, str]:
    """
    Detect BPM of an audio file (convenience wrapper).

    Args:
        audio_path: Path to audio file

    Returns:
        Tuple of (detected_bpm, status_message)
        - detected_bpm: Detected BPM as float (or 120.0 as fallback)
        - status_message: Description of detection result

    Example:
        >>> bpm, message = detect_audio_bpm(Path("song.wav"))
        >>> print(f"BPM: {bpm:.1f} - {message}")
        BPM: 128.0 - Detected successfully
    """
    try:
        audio_data, sample_rate = sf.read(str(audio_path), always_2d=False)
        bpm = detect_bpm(audio_data, sample_rate)

        if bpm == 120.0:
            # Default fallback (detection may have failed)
            return bpm, "Detection failed, using default 120 BPM"
        else:
            return bpm, f"Detected successfully"

    except Exception as e:
        logger.error(f"BPM detection error for {audio_path}: {e}")
        return 120.0, f"Error: {e}, using default 120 BPM"
