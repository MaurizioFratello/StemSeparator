#!/usr/bin/env python3
"""
Comprehensive Synchronization Tests for Ensemble Separator

Tests for CRITICAL synchronization issues:
- Sample rate mismatches between models
- Length differences and padding
- Phase alignment
- Channel count mismatches
"""
import sys
from pathlib import Path
import numpy as np
import tempfile
import shutil
import soundfile as sf

# Add project to path
sys.path.insert(0, '/home/user/StemSeparator')

from core.ensemble_separator import EnsembleSeparator
from core.separator import SeparationResult


def create_test_audio_with_different_sample_rates():
    """
    Create test audio files with DIFFERENT sample rates
    This simulates what could happen when different models output different rates
    """
    temp_dir = Path(tempfile.mkdtemp())

    # Model 1: 44100 Hz
    sr1 = 44100
    duration = 2.0
    samples1 = int(sr1 * duration)
    t1 = np.linspace(0, duration, samples1)
    vocals1 = np.sin(2 * np.pi * 440 * t1) * 0.5
    vocals1_stereo = np.column_stack([vocals1, vocals1])

    # Model 2: 48000 Hz (DIFFERENT!)
    sr2 = 48000
    samples2 = int(sr2 * duration)
    t2 = np.linspace(0, duration, samples2)
    vocals2 = np.sin(2 * np.pi * 440 * t2) * 0.5
    vocals2_stereo = np.column_stack([vocals2, vocals2])

    # Create directories
    model1_dir = temp_dir / "model1"
    model2_dir = temp_dir / "model2"
    model1_dir.mkdir(parents=True)
    model2_dir.mkdir(parents=True)

    # Save with different sample rates
    sf.write(str(model1_dir / "test_(vocals)_m1.wav"), vocals1_stereo, sr1)
    sf.write(str(model2_dir / "test_(vocals)_m2.wav"), vocals2_stereo, sr2)

    return temp_dir, {
        'model1_dir': model1_dir,
        'model2_dir': model2_dir,
        'model1_file': model1_dir / "test_(vocals)_m1.wav",
        'model2_file': model2_dir / "test_(vocals)_m2.wav",
        'sr1': sr1,
        'sr2': sr2,
        'samples1': samples1,
        'samples2': samples2
    }


def create_test_audio_with_different_lengths():
    """
    Create test audio files with DIFFERENT lengths at same sample rate
    This simulates models that process audio differently
    """
    temp_dir = Path(tempfile.mkdtemp())
    sr = 44100

    # Model 1: 2.0 seconds
    duration1 = 2.0
    samples1 = int(sr * duration1)
    t1 = np.linspace(0, duration1, samples1)
    vocals1 = np.sin(2 * np.pi * 440 * t1) * 0.5
    vocals1_stereo = np.column_stack([vocals1, vocals1])

    # Model 2: 2.1 seconds (LONGER - simulates different border handling)
    duration2 = 2.1
    samples2 = int(sr * duration2)
    t2 = np.linspace(0, duration2, samples2)
    vocals2 = np.sin(2 * np.pi * 440 * t2) * 0.5
    vocals2_stereo = np.column_stack([vocals2, vocals2])

    # Create directories
    model1_dir = temp_dir / "model1"
    model2_dir = temp_dir / "model2"
    model1_dir.mkdir(parents=True)
    model2_dir.mkdir(parents=True)

    # Save with same sample rate but different lengths
    sf.write(str(model1_dir / "test_(vocals)_m1.wav"), vocals1_stereo, sr)
    sf.write(str(model2_dir / "test_(vocals)_m2.wav"), vocals2_stereo, sr)

    return temp_dir, {
        'model1_dir': model1_dir,
        'model2_dir': model2_dir,
        'model1_file': model1_dir / "test_(vocals)_m1.wav",
        'model2_file': model2_dir / "test_(vocals)_m2.wav",
        'sr': sr,
        'samples1': samples1,
        'samples2': samples2,
        'duration1': duration1,
        'duration2': duration2
    }


def create_test_audio_with_phase_shift():
    """
    Create test audio files with PHASE SHIFT
    This simulates models that introduce delays
    """
    temp_dir = Path(tempfile.mkdtemp())
    sr = 44100
    duration = 2.0
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples)

    # Model 1: Normal phase
    vocals1 = np.sin(2 * np.pi * 440 * t) * 0.5
    vocals1_stereo = np.column_stack([vocals1, vocals1])

    # Model 2: PHASE SHIFTED by 100 samples (~2.3ms at 44100 Hz)
    phase_shift = 100
    vocals2_shifted = np.zeros_like(vocals1)
    vocals2_shifted[phase_shift:] = vocals1[:-phase_shift]  # Delay
    vocals2_stereo = np.column_stack([vocals2_shifted, vocals2_shifted])

    # Create directories
    model1_dir = temp_dir / "model1"
    model2_dir = temp_dir / "model2"
    model1_dir.mkdir(parents=True)
    model2_dir.mkdir(parents=True)

    # Save
    sf.write(str(model1_dir / "test_(vocals)_m1.wav"), vocals1_stereo, sr)
    sf.write(str(model2_dir / "test_(vocals)_m2.wav"), vocals2_stereo, sr)

    return temp_dir, {
        'model1_dir': model1_dir,
        'model2_dir': model2_dir,
        'model1_file': model1_dir / "test_(vocals)_m1.wav",
        'model2_file': model2_dir / "test_(vocals)_m2.wav",
        'phase_shift': phase_shift,
        'sr': sr
    }


def create_test_audio_with_different_channels():
    """
    Create test audio files with DIFFERENT channel counts
    Model 1: Stereo, Model 2: Mono
    """
    temp_dir = Path(tempfile.mkdtemp())
    sr = 44100
    duration = 2.0
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples)

    # Model 1: Stereo (2 channels)
    vocals = np.sin(2 * np.pi * 440 * t) * 0.5
    vocals_stereo = np.column_stack([vocals, vocals])

    # Model 2: Mono (1 channel)
    vocals_mono = vocals

    # Create directories
    model1_dir = temp_dir / "model1"
    model2_dir = temp_dir / "model2"
    model1_dir.mkdir(parents=True)
    model2_dir.mkdir(parents=True)

    # Save
    sf.write(str(model1_dir / "test_(vocals)_m1.wav"), vocals_stereo, sr)
    sf.write(str(model2_dir / "test_(vocals)_m2.wav"), vocals_mono, sr)

    return temp_dir, {
        'model1_dir': model1_dir,
        'model2_dir': model2_dir,
        'model1_file': model1_dir / "test_(vocals)_m1.wav",
        'model2_file': model2_dir / "test_(vocals)_m2.wav",
        'sr': sr
    }


def test_sample_rate_mismatch():
    """
    CRITICAL TEST: Different sample rates

    Tests automatic resampling when models output different sample rates.
    Expected behavior: Detect mismatch, resample to common rate, log warning.
    """
    print("\n" + "="*70)
    print("TEST: Sample Rate Mismatch (44100 vs 48000)")
    print("="*70)

    temp_dir, test_files = create_test_audio_with_different_sample_rates()

    try:
        separator = EnsembleSeparator()

        # Create fake results with DIFFERENT sample rates
        result1 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model1_dir'],
            stems={'vocals': test_files['model1_file']},
            model_used="model1",
            device_used="cpu",
            duration_seconds=1.0
        )

        result2 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model2_dir'],
            stems={'vocals': test_files['model2_file']},
            model_used="model2",
            device_used="cpu",
            duration_seconds=1.0
        )

        # Attempt to combine
        weights = {'vocals': [0.5, 0.5]}

        print(f"  Model 1: {test_files['sr1']} Hz, {test_files['samples1']} samples")
        print(f"  Model 2: {test_files['sr2']} Hz, {test_files['samples2']} samples")
        print(f"  Difference: {abs(test_files['samples2'] - test_files['samples1'])} samples")

        combined = separator._combine_stems_weighted(
            [result1, result2],
            weights,
            ['model1', 'model2']
        )

        if 'vocals' in combined:
            print(f"\n  ✓ Successfully combined with automatic resampling!")
            print(f"  Combined shape: {combined['vocals'].shape}")
            print(f"  Peak: {np.max(np.abs(combined['vocals'])):.3f}")

            # Verify both stems were resampled to same length
            if combined['vocals'].shape[1] == test_files['samples1']:
                print(f"  ✓ Resampled to {test_files['sr1']} Hz ({test_files['samples1']} samples)")
                print(f"  ✓ PASS: Sample rate mismatch detected and corrected via resampling")
                return True
            else:
                print(f"  ❌ Unexpected length: {combined['vocals'].shape[1]}")
                return False

    except Exception as e:
        print(f"\n  ❌ Failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(temp_dir)

    return False


def test_length_mismatch():
    """
    TEST: Different lengths at same sample rate

    This should pad shorter audio, but WARN about significant differences
    """
    print("\n" + "="*70)
    print("TEST: Length Mismatch (Same Sample Rate)")
    print("="*70)

    temp_dir, test_files = create_test_audio_with_different_lengths()

    try:
        separator = EnsembleSeparator()

        result1 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model1_dir'],
            stems={'vocals': test_files['model1_file']},
            model_used="model1",
            device_used="cpu",
            duration_seconds=test_files['duration1']
        )

        result2 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model2_dir'],
            stems={'vocals': test_files['model2_file']},
            model_used="model2",
            device_used="cpu",
            duration_seconds=test_files['duration2']
        )

        weights = {'vocals': [0.5, 0.5]}

        print(f"  Model 1: {test_files['samples1']} samples ({test_files['duration1']}s)")
        print(f"  Model 2: {test_files['samples2']} samples ({test_files['duration2']}s)")
        print(f"  Difference: {abs(test_files['samples2'] - test_files['samples1'])} samples")

        combined = separator._combine_stems_weighted(
            [result1, result2],
            weights,
            ['model1', 'model2']
        )

        if 'vocals' in combined:
            print(f"\n  ✓ Successfully combined with padding")
            print(f"  Combined shape: {combined['vocals'].shape}")
            print(f"  Peak: {np.max(np.abs(combined['vocals'])):.3f}")

            # Check that combined length matches longest input
            if combined['vocals'].shape[1] == test_files['samples2']:
                print(f"  ✓ Length matches longest input: {test_files['samples2']} samples")
                return True
            else:
                print(f"  ❌ Length mismatch: expected {test_files['samples2']}, got {combined['vocals'].shape[1]}")
                return False

    except Exception as e:
        print(f"\n  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(temp_dir)

    return False


def test_phase_cancellation():
    """
    TEST: Phase shift detection

    When stems are phase-shifted, averaging can cause cancellation
    This test verifies if phase shifts are detected/handled
    """
    print("\n" + "="*70)
    print("TEST: Phase Shift Detection (Potential Cancellation)")
    print("="*70)

    temp_dir, test_files = create_test_audio_with_phase_shift()

    try:
        separator = EnsembleSeparator()

        result1 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model1_dir'],
            stems={'vocals': test_files['model1_file']},
            model_used="model1",
            device_used="cpu",
            duration_seconds=2.0
        )

        result2 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model2_dir'],
            stems={'vocals': test_files['model2_file']},
            model_used="model2",
            device_used="cpu",
            duration_seconds=2.0
        )

        weights = {'vocals': [0.5, 0.5]}

        # Read original signals
        audio1, _ = sf.read(str(test_files['model1_file']), always_2d=True)
        audio2, _ = sf.read(str(test_files['model2_file']), always_2d=True)

        peak1 = np.max(np.abs(audio1))
        peak2 = np.max(np.abs(audio2))

        print(f"  Model 1 peak: {peak1:.3f}")
        print(f"  Model 2 peak (shifted by {test_files['phase_shift']} samples): {peak2:.3f}")

        combined = separator._combine_stems_weighted(
            [result1, result2],
            weights,
            ['model1', 'model2']
        )

        if 'vocals' in combined:
            peak_combined = np.max(np.abs(combined['vocals']))
            print(f"\n  Combined peak: {peak_combined:.3f}")

            # Check for phase cancellation
            # If signals are in phase: peak ~= (peak1 + peak2) / 2 = ~0.5
            # If signals are out of phase: peak << 0.5
            expected_peak = (peak1 + peak2) / 2

            if peak_combined < expected_peak * 0.7:  # More than 30% reduction
                print(f"  ⚠️  WARNING: Potential phase cancellation detected!")
                print(f"  Expected peak: ~{expected_peak:.3f}, got: {peak_combined:.3f}")
                print(f"  ❌ CRITICAL: Phase alignment not verified!")
                return False
            else:
                print(f"  ℹ️  No significant cancellation (expected ~{expected_peak:.3f})")
                print(f"  ⚠️  NOTE: Current implementation does NOT check phase alignment")
                return True

    except Exception as e:
        print(f"\n  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        shutil.rmtree(temp_dir)

    return False


def test_channel_count_mismatch():
    """
    TEST: Different channel counts (stereo vs mono)

    Should handle gracefully by upmixing mono to stereo
    """
    print("\n" + "="*70)
    print("TEST: Channel Count Mismatch (Stereo vs Mono)")
    print("="*70)

    temp_dir, test_files = create_test_audio_with_different_channels()

    try:
        separator = EnsembleSeparator()

        result1 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model1_dir'],
            stems={'vocals': test_files['model1_file']},
            model_used="model1",
            device_used="cpu",
            duration_seconds=2.0
        )

        result2 = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=test_files['model2_dir'],
            stems={'vocals': test_files['model2_file']},
            model_used="model2",
            device_used="cpu",
            duration_seconds=2.0
        )

        weights = {'vocals': [0.5, 0.5]}

        # Read to check channel counts
        audio1, _ = sf.read(str(test_files['model1_file']), always_2d=True)
        audio2, _ = sf.read(str(test_files['model2_file']), always_2d=True)

        print(f"  Model 1: {audio1.shape[1]} channels (stereo)")
        print(f"  Model 2: {audio2.shape[1]} channels (mono)")

        combined = separator._combine_stems_weighted(
            [result1, result2],
            weights,
            ['model1', 'model2']
        )

        if 'vocals' in combined:
            print(f"\n  Combined shape: {combined['vocals'].shape}")

            # Should be stereo (2 channels)
            if combined['vocals'].shape[0] == 2:
                print(f"  ✓ Successfully converted to stereo")
                return True
            else:
                print(f"  ❌ Unexpected channel count: {combined['vocals'].shape[0]}")
                return False

    except Exception as e:
        print(f"\n  ⚠️  Error (possibly expected): {e}")
        print(f"  ❌ ISSUE: Cannot handle channel count mismatch")
        return False

    finally:
        shutil.rmtree(temp_dir)

    return False


def run_all_synchronization_tests():
    """Run all synchronization tests"""
    print("\n" + "="*70)
    print("COMPREHENSIVE SYNCHRONIZATION TESTS")
    print("Testing for CRITICAL audio alignment issues")
    print("="*70)

    tests = [
        ("Sample Rate Mismatch", test_sample_rate_mismatch),
        ("Length Mismatch", test_length_mismatch),
        ("Phase Cancellation", test_phase_cancellation),
        ("Channel Count Mismatch", test_channel_count_mismatch),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n  ❌ Test FAILED with exception: {name}")
            print(f"     Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("SYNCHRONIZATION TEST RESULTS")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed} passed, {failed} failed out of {len(results)}")

    if failed > 0:
        print("\n⚠️  CRITICAL ISSUES FOUND!")
        print("The ensemble separator needs fixes for synchronization:")
        print("  1. Sample rate verification and resampling")
        print("  2. Phase alignment detection/correction")
        print("  3. Channel count normalization")

    print("="*70)

    return failed == 0


if __name__ == '__main__':
    success = run_all_synchronization_tests()
    sys.exit(0 if success else 1)
