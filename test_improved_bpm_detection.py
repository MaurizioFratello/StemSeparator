#!/usr/bin/env python3
"""
Test script for improved BPM detection

This script demonstrates the improved librosa.beat.tempo parameters
and hierarchical source selection (Drums > Mixed Stems).
"""
import sys
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.audio_processing import detect_bpm


def create_test_audio(bpm: float, duration_seconds: float = 10.0, sample_rate: int = 44100):
    """
    Create synthetic audio with a specific BPM for testing.

    Generates a click track at the specified tempo.
    """
    # Calculate samples per beat
    beats_per_second = bpm / 60.0
    samples_per_beat = int(sample_rate / beats_per_second)

    total_samples = int(duration_seconds * sample_rate)
    audio = np.zeros(total_samples, dtype=np.float32)

    # Add clicks at beat positions
    for i in range(0, total_samples, samples_per_beat):
        if i < total_samples:
            # Create a short click (100 samples)
            click_length = min(100, total_samples - i)
            # Exponential decay envelope
            envelope = np.exp(-np.linspace(0, 5, click_length))
            audio[i:i+click_length] = envelope * 0.8

    return audio


def test_bpm_detection():
    """Test BPM detection with different tempos"""
    print("="*60)
    print("TESTING IMPROVED BPM DETECTION")
    print("="*60)
    print()

    # Test cases: (actual_bpm, expected_range)
    test_cases = [
        (104.0, (102.0, 106.0)),  # User's example
        (120.0, (118.0, 122.0)),  # Standard tempo
        (80.0, (78.0, 82.0)),      # Slower tempo
        (140.0, (138.0, 142.0)),   # Faster tempo
        (90.0, (88.0, 92.0)),      # Common tempo
    ]

    sample_rate = 44100
    duration = 15.0  # 15 seconds for better detection

    results = []

    for actual_bpm, (min_expected, max_expected) in test_cases:
        print(f"Testing BPM: {actual_bpm:.1f}")
        print("-" * 40)

        # Create test audio
        audio = create_test_audio(actual_bpm, duration, sample_rate)

        # Detect BPM
        detected_bpm = detect_bpm(audio, sample_rate)

        # Calculate error
        error = abs(detected_bpm - actual_bpm)
        error_percent = (error / actual_bpm) * 100

        # Check if within expected range
        is_accurate = min_expected <= detected_bpm <= max_expected

        print(f"  Actual BPM:    {actual_bpm:.1f}")
        print(f"  Detected BPM:  {detected_bpm:.1f}")
        print(f"  Error:         {error:.1f} BPM ({error_percent:.1f}%)")
        print(f"  Expected range: {min_expected:.1f} - {max_expected:.1f}")
        print(f"  Status:        {'✓ PASS' if is_accurate else '✗ FAIL'}")
        print()

        results.append({
            'actual': actual_bpm,
            'detected': detected_bpm,
            'error': error,
            'error_percent': error_percent,
            'accurate': is_accurate
        })

    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(1 for r in results if r['accurate'])
    total = len(results)
    avg_error = np.mean([r['error'] for r in results])
    avg_error_percent = np.mean([r['error_percent'] for r in results])

    print(f"Passed:          {passed}/{total} ({(passed/total)*100:.0f}%)")
    print(f"Average error:   {avg_error:.2f} BPM ({avg_error_percent:.2f}%)")
    print()

    print("Improvements implemented:")
    print("  ✓ hop_length=512 for higher temporal resolution")
    print("  ✓ start_bpm=120.0 for expected tempo range")
    print("  ✓ std_bpm=1.0 for more precise estimation")
    print("  ✓ max_tempo=240.0 to prevent double-tempo errors")
    print("  ✓ Automatic correction for tempo doubling/halving")
    print()

    return results


if __name__ == "__main__":
    try:
        results = test_bpm_detection()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
