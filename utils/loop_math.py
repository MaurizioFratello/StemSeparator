"""
Loop Math - Musical calculations for loop-based sampler export

PURPOSE: Provide core mathematical functions for calculating loop lengths,
         validating BPM/bar combinations, and ensuring sampler compatibility.

CONTEXT: Used by sampler_export to compute exact sample counts for musical loops.
"""
from typing import Tuple


def compute_bar_duration_seconds(bpm: int, time_signature_beats: int = 4) -> float:
    """
    Compute the duration of one bar in seconds.

    Args:
        bpm: Beats per minute (integer)
        time_signature_beats: Number of beats per bar (default: 4 for 4/4 time)

    Returns:
        Duration of one bar in seconds

    Example:
        >>> compute_bar_duration_seconds(120)  # 120 BPM, 4/4 time
        2.0  # One bar = 2 seconds

        >>> compute_bar_duration_seconds(90)
        2.666...  # One bar = ~2.67 seconds

    Formula:
        - Beat duration: 60 / BPM seconds
        - Bar duration: (time_signature_beats * 60) / BPM seconds
    """
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")

    return (time_signature_beats * 60.0) / bpm


def compute_chunk_duration_seconds(
    bpm: int,
    bars: int,
    time_signature_beats: int = 4
) -> float:
    """
    Compute the duration of N bars in seconds.

    Args:
        bpm: Beats per minute (integer)
        bars: Number of bars (2, 4, or 8 typically)
        time_signature_beats: Number of beats per bar (default: 4 for 4/4 time)

    Returns:
        Duration of N bars in seconds

    Example:
        >>> compute_chunk_duration_seconds(120, 4)  # 4 bars at 120 BPM
        8.0  # 4 bars = 8 seconds

        >>> compute_chunk_duration_seconds(100, 2)  # 2 bars at 100 BPM
        4.8  # 2 bars = 4.8 seconds

    Formula:
        Duration = (bars * time_signature_beats * 60) / BPM
    """
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")
    if bars <= 0:
        raise ValueError(f"Bars must be positive, got {bars}")

    return (bars * time_signature_beats * 60.0) / bpm


def compute_samples_per_chunk(
    bpm: int,
    bars: int,
    sample_rate: int,
    time_signature_beats: int = 4
) -> int:
    """
    Compute the number of samples for N bars at given BPM and sample rate.

    Args:
        bpm: Beats per minute (integer)
        bars: Number of bars
        sample_rate: Sample rate in Hz (e.g., 44100 or 48000)
        time_signature_beats: Number of beats per bar (default: 4 for 4/4 time)

    Returns:
        Number of samples (integer, rounded)

    Example:
        >>> compute_samples_per_chunk(120, 4, 44100)  # 4 bars at 120 BPM, 44.1kHz
        352800  # samples

        >>> compute_samples_per_chunk(120, 4, 48000)  # Same but 48kHz
        384000  # samples

    Formula:
        1. Duration in seconds: (bars * time_signature_beats * 60) / BPM
        2. Samples: duration * sample_rate (rounded to nearest integer)
    """
    if sample_rate <= 0:
        raise ValueError(f"Sample rate must be positive, got {sample_rate}")

    duration_seconds = compute_chunk_duration_seconds(bpm, bars, time_signature_beats)
    return round(duration_seconds * sample_rate)


def is_valid_for_sampler(
    bpm: int,
    bars: int,
    max_seconds: float = 20.0,
    time_signature_beats: int = 4
) -> Tuple[bool, str]:
    """
    Check if BPM + bars combination fits within sampler's maximum duration.

    Args:
        bpm: Beats per minute (integer)
        bars: Number of bars
        max_seconds: Maximum duration allowed by sampler (default: 20.0)
        time_signature_beats: Number of beats per bar (default: 4 for 4/4 time)

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if combination is valid, False otherwise
        - error_message: Empty string if valid, error description if invalid

    Example:
        >>> is_valid_for_sampler(120, 4)  # 4 bars at 120 BPM
        (True, '')  # 8 seconds < 20 seconds ✓

        >>> is_valid_for_sampler(50, 8)  # 8 bars at 50 BPM
        (False, 'Duration would be 38.40s, exceeding 20.00s limit')

    Minimum BPMs for standard combinations (20s limit):
        - 2 bars: BPM >= 24
        - 4 bars: BPM >= 48
        - 8 bars: BPM >= 96
    """
    try:
        duration = compute_chunk_duration_seconds(bpm, bars, time_signature_beats)
    except ValueError as e:
        return False, str(e)

    if duration > max_seconds:
        return False, (
            f"Duration would be {duration:.2f}s, exceeding {max_seconds:.2f}s limit. "
            f"Minimum BPM for {bars} bars: {int((bars * time_signature_beats * 60) / max_seconds) + 1}"
        )

    return True, ""


def get_minimum_bpm(
    bars: int,
    max_seconds: float = 20.0,
    time_signature_beats: int = 4
) -> int:
    """
    Calculate the minimum BPM required for N bars to fit within max_seconds.

    Args:
        bars: Number of bars
        max_seconds: Maximum duration allowed (default: 20.0)
        time_signature_beats: Number of beats per bar (default: 4 for 4/4 time)

    Returns:
        Minimum BPM (rounded up to nearest integer)

    Example:
        >>> get_minimum_bpm(2)  # 2 bars, 20s limit
        24  # At 24 BPM, 2 bars = exactly 20s

        >>> get_minimum_bpm(4)  # 4 bars, 20s limit
        48  # At 48 BPM, 4 bars = exactly 20s

        >>> get_minimum_bpm(8)  # 8 bars, 20s limit
        96  # At 96 BPM, 8 bars = exactly 20s

    Formula:
        min_BPM = (bars * time_signature_beats * 60) / max_seconds
    """
    if bars <= 0:
        raise ValueError(f"Bars must be positive, got {bars}")
    if max_seconds <= 0:
        raise ValueError(f"Max seconds must be positive, got {max_seconds}")

    min_bpm_float = (bars * time_signature_beats * 60.0) / max_seconds
    return int(min_bpm_float) + (1 if min_bpm_float % 1 > 0 else 0)


# Constants for 4/4 time signature with 20s sampler limit
MIN_BPM_2_BARS = get_minimum_bpm(2)  # 24
MIN_BPM_4_BARS = get_minimum_bpm(4)  # 48
MIN_BPM_8_BARS = get_minimum_bpm(8)  # 96
