#!/usr/bin/env python3
"""
Manual test script for Ensemble Separator
Run without pytest dependencies
"""
import sys
from pathlib import Path
import numpy as np
import tempfile
import shutil
import soundfile as sf

# Add project to path
sys.path.insert(0, '/home/user/StemSeparator')

from core.ensemble_separator import EnsembleSeparator, get_ensemble_separator
from config import ENSEMBLE_CONFIGS, MODELS


def create_test_audio():
    """Create temporary test audio files"""
    temp_dir = Path(tempfile.mkdtemp())

    # Create test audio (2 seconds, stereo, 44100 Hz)
    sample_rate = 44100
    duration = 2.0
    samples = int(sample_rate * duration)

    # Test vocals - 440 Hz sine
    t = np.linspace(0, duration, samples)
    vocals = np.sin(2 * np.pi * 440 * t) * 0.5
    vocals_stereo = np.column_stack([vocals, vocals])

    # Test drums - noise
    drums = np.random.randn(samples) * 0.3
    drums_stereo = np.column_stack([drums, drums])

    # Test bass - 110 Hz sine
    bass = np.sin(2 * np.pi * 110 * t) * 0.5
    bass_stereo = np.column_stack([bass, bass])

    # Save test file
    test_file = temp_dir / "test_song.wav"
    mixed = vocals_stereo + drums_stereo + bass_stereo
    sf.write(str(test_file), mixed, sample_rate)

    # Create fake separated stems for testing combination
    stems_dir = temp_dir / "stems"
    stems_dir.mkdir()

    # Model 1 stems
    model1_dir = stems_dir / "model1"
    model1_dir.mkdir()
    sf.write(str(model1_dir / "test_song_(vocals)_model1.wav"), vocals_stereo, sample_rate)
    sf.write(str(model1_dir / "test_song_(drums)_model1.wav"), drums_stereo, sample_rate)
    sf.write(str(model1_dir / "test_song_(bass)_model1.wav"), bass_stereo, sample_rate)

    # Model 2 stems (slightly different)
    model2_dir = stems_dir / "model2"
    model2_dir.mkdir()
    sf.write(str(model2_dir / "test_song_(vocals)_model2.wav"), vocals_stereo * 0.95, sample_rate)
    sf.write(str(model2_dir / "test_song_(drums)_model2.wav"), drums_stereo * 1.05, sample_rate)
    sf.write(str(model2_dir / "test_song_(bass)_model2.wav"), bass_stereo, sample_rate)

    return temp_dir, {
        'test_file': test_file,
        'stems_dir': stems_dir,
        'model1_dir': model1_dir,
        'model2_dir': model2_dir,
        'sample_rate': sample_rate
    }


def test_initialization():
    """Test ensemble separator initialization"""
    print("TEST: Initialization")
    separator = EnsembleSeparator()

    assert separator is not None
    assert separator.separator is not None
    assert separator.cache_dir.exists()

    print("  ✓ EnsembleSeparator initialized correctly")
    return True


def test_extract_stem_name():
    """Test stem name extraction"""
    print("TEST: Extract stem name")
    separator = EnsembleSeparator()

    # Test with parentheses
    assert separator._extract_stem_name(Path("song_(vocals)_model.wav")) == "vocals"
    assert separator._extract_stem_name(Path("song_(drums)_model.wav")) == "drums"

    # Test with keywords
    assert separator._extract_stem_name(Path("song_vocal_model.wav")) == "vocals"
    assert separator._extract_stem_name(Path("song_drum_model.wav")) == "drums"
    assert separator._extract_stem_name(Path("song_bass_model.wav")) == "bass"
    assert separator._extract_stem_name(Path("song_other_model.wav")) == "other"

    # Test instrumental
    assert separator._extract_stem_name(Path("song_instrumental.wav")) == "instrumental"
    assert separator._extract_stem_name(Path("song_instrum.wav")) == "instrumental"

    print("  ✓ Stem name extraction works correctly")
    return True


def test_combine_stems_weighted():
    """Test weighted stem combination"""
    print("TEST: Weighted stem combination")

    temp_dir, test_files = create_test_audio()

    try:
        from core.separator import SeparationResult

        separator = EnsembleSeparator()

        # Create fake results
        result1 = SeparationResult(
            success=True,
            input_file=test_files['test_file'],
            output_dir=test_files['model1_dir'],
            stems={
                'vocals': test_files['model1_dir'] / "test_song_(vocals)_model1.wav",
                'drums': test_files['model1_dir'] / "test_song_(drums)_model1.wav",
                'bass': test_files['model1_dir'] / "test_song_(bass)_model1.wav"
            },
            model_used="model1",
            device_used="cpu",
            duration_seconds=1.0
        )

        result2 = SeparationResult(
            success=True,
            input_file=test_files['test_file'],
            output_dir=test_files['model2_dir'],
            stems={
                'vocals': test_files['model2_dir'] / "test_song_(vocals)_model2.wav",
                'drums': test_files['model2_dir'] / "test_song_(drums)_model2.wav",
                'bass': test_files['model2_dir'] / "test_song_(bass)_model2.wav"
            },
            model_used="model2",
            device_used="cpu",
            duration_seconds=1.0
        )

        # Test weighted combination
        weights = {
            'vocals': [0.6, 0.4],
            'drums': [0.4, 0.6],
            'bass': [0.5, 0.5]
        }

        combined = separator._combine_stems_weighted(
            [result1, result2],
            weights,
            ['model1', 'model2']
        )

        # Check results
        assert 'vocals' in combined
        assert 'drums' in combined
        assert 'bass' in combined

        # Check shapes
        assert combined['vocals'].shape[0] == 2  # Stereo
        assert combined['drums'].shape[0] == 2
        assert combined['bass'].shape[0] == 2

        # Check values are reasonable (not clipped)
        assert np.max(np.abs(combined['vocals'])) <= 1.0
        assert np.max(np.abs(combined['drums'])) <= 1.0
        assert np.max(np.abs(combined['bass'])) <= 1.0

        print(f"  ✓ Combined 3 stems with weighted averaging")
        print(f"    - vocals: shape={combined['vocals'].shape}, peak={np.max(np.abs(combined['vocals'])):.3f}")
        print(f"    - drums:  shape={combined['drums'].shape}, peak={np.max(np.abs(combined['drums'])):.3f}")
        print(f"    - bass:   shape={combined['bass'].shape}, peak={np.max(np.abs(combined['bass'])):.3f}")

        return True

    finally:
        shutil.rmtree(temp_dir)


def test_ensemble_configs():
    """Test that ensemble configs are properly defined"""
    print("TEST: Ensemble configurations")

    assert 'balanced' in ENSEMBLE_CONFIGS
    assert 'quality' in ENSEMBLE_CONFIGS
    assert 'vocals_focus' in ENSEMBLE_CONFIGS

    # Check balanced config
    balanced = ENSEMBLE_CONFIGS['balanced']
    assert 'models' in balanced
    assert 'weights' in balanced
    assert len(balanced['models']) == 2
    assert 'vocals' in balanced['weights']

    print(f"  ✓ Balanced ensemble: {balanced['models']}")
    print(f"    Weights: vocals={balanced['weights']['vocals']}, drums={balanced['weights']['drums']}")

    # Check quality config
    quality = ENSEMBLE_CONFIGS['quality']
    assert len(quality['models']) == 3

    print(f"  ✓ Quality ensemble: {quality['models']}")
    print(f"    Weights: vocals={quality['weights']['vocals']}, drums={quality['weights']['drums']}")

    # Check vocals_focus config
    vocals = ENSEMBLE_CONFIGS['vocals_focus']
    assert len(vocals['models']) == 2

    print(f"  ✓ Vocals focus ensemble: {vocals['models']}")
    print(f"    Weights: vocals={vocals['weights']['vocals']}")

    return True


def test_models_config():
    """Test that new models are properly defined"""
    print("TEST: Model configurations")

    # Check mel-roformer was added
    assert 'mel-roformer' in MODELS

    mel = MODELS['mel-roformer']
    assert mel['name'] == 'Mel-Band RoFormer'
    assert mel['strength'] == 'vocals'
    assert mel['stems'] == 4

    print(f"  ✓ Mel-RoFormer added: {mel['description']}")

    # Check other models have strength attribute
    bs = MODELS['bs-roformer']
    assert 'strength' in bs
    print(f"  ✓ BS-RoFormer: strength={bs['strength']}")

    demucs4 = MODELS['demucs_4s']
    assert 'strength' in demucs4
    print(f"  ✓ Demucs 4s: strength={demucs4['strength']}")

    return True


def test_singleton():
    """Test get_ensemble_separator singleton"""
    print("TEST: Singleton pattern")

    sep1 = get_ensemble_separator()
    sep2 = get_ensemble_separator()

    assert sep1 is sep2
    assert isinstance(sep1, EnsembleSeparator)

    print("  ✓ Singleton pattern works correctly")
    return True


def test_weighted_averaging_math():
    """Test that weighted averaging math is correct"""
    print("TEST: Weighted averaging math")

    # Create simple test arrays
    audio1 = np.array([[1.0, 1.0], [1.0, 1.0]], dtype=np.float32)  # (2, 2)
    audio2 = np.array([[2.0, 2.0], [2.0, 2.0]], dtype=np.float32)

    # Weighted average: 0.6 * audio1 + 0.4 * audio2
    expected = np.array([[1.4, 1.4], [1.4, 1.4]], dtype=np.float32)

    # Simulate weighted combination
    result = audio1 * 0.6 + audio2 * 0.4

    np.testing.assert_array_almost_equal(result, expected, decimal=5)

    print(f"  ✓ Weighted average: 0.6*[1.0] + 0.4*[2.0] = [1.4]")
    return True


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("TESTING ENSEMBLE SEPARATOR")
    print("="*60)

    tests = [
        test_initialization,
        test_extract_stem_name,
        test_models_config,
        test_ensemble_configs,
        test_weighted_averaging_math,
        test_combine_stems_weighted,
        test_singleton,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ✗ Test failed: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  ✗ Test failed with exception: {test.__name__}")
            print(f"    Error: {e}")
            import traceback
            traceback.print_exc()

    print("="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
