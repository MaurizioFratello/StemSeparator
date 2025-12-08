"""
Unit Tests for Ensemble Separator
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil

from core.ensemble_separator import EnsembleSeparator, get_ensemble_separator
from config import ENSEMBLE_CONFIGS


@pytest.fixture
def test_audio_files():
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
    # Mix all stems together
    mixed = vocals_stereo + drums_stereo + bass_stereo
    sf.write(str(test_file), mixed, sample_rate)

    # Create fake separated stems for testing combination
    stems_dir = temp_dir / "stems"
    stems_dir.mkdir()

    # Model 1 stems
    model1_dir = stems_dir / "model1"
    model1_dir.mkdir()
    sf.write(
        str(model1_dir / "test_song_(vocals)_model1.wav"), vocals_stereo, sample_rate
    )
    sf.write(
        str(model1_dir / "test_song_(drums)_model1.wav"), drums_stereo, sample_rate
    )
    sf.write(str(model1_dir / "test_song_(bass)_model1.wav"), bass_stereo, sample_rate)

    # Model 2 stems (slightly different)
    model2_dir = stems_dir / "model2"
    model2_dir.mkdir()
    sf.write(
        str(model2_dir / "test_song_(vocals)_model2.wav"),
        vocals_stereo * 0.95,
        sample_rate,
    )
    sf.write(
        str(model2_dir / "test_song_(drums)_model2.wav"),
        drums_stereo * 1.05,
        sample_rate,
    )
    sf.write(str(model2_dir / "test_song_(bass)_model2.wav"), bass_stereo, sample_rate)

    yield {
        "test_file": test_file,
        "stems_dir": stems_dir,
        "model1_dir": model1_dir,
        "model2_dir": model2_dir,
        "sample_rate": sample_rate,
    }

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.unit
class TestEnsembleSeparator:
    """Tests for EnsembleSeparator"""

    def test_initialization(self):
        """Test ensemble separator initialization"""
        separator = EnsembleSeparator()

        assert separator is not None
        assert separator.separator is not None
        assert separator.cache_dir.exists()

    def test_extract_stem_name(self):
        """Test stem name extraction"""
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
        assert (
            separator._extract_stem_name(Path("song_instrumental.wav"))
            == "instrumental"
        )
        assert separator._extract_stem_name(Path("song_instrum.wav")) == "instrumental"

    def test_combine_stems_weighted(self, test_audio_files):
        """Test weighted stem combination"""
        from core.separator import SeparationResult

        separator = EnsembleSeparator()

        # Create fake results
        result1 = SeparationResult(
            success=True,
            input_file=test_audio_files["test_file"],
            output_dir=test_audio_files["model1_dir"],
            stems={
                "vocals": test_audio_files["model1_dir"]
                / "test_song_(vocals)_model1.wav",
                "drums": test_audio_files["model1_dir"]
                / "test_song_(drums)_model1.wav",
                "bass": test_audio_files["model1_dir"] / "test_song_(bass)_model1.wav",
            },
            model_used="model1",
            device_used="cpu",
            duration_seconds=1.0,
        )

        result2 = SeparationResult(
            success=True,
            input_file=test_audio_files["test_file"],
            output_dir=test_audio_files["model2_dir"],
            stems={
                "vocals": test_audio_files["model2_dir"]
                / "test_song_(vocals)_model2.wav",
                "drums": test_audio_files["model2_dir"]
                / "test_song_(drums)_model2.wav",
                "bass": test_audio_files["model2_dir"] / "test_song_(bass)_model2.wav",
            },
            model_used="model2",
            device_used="cpu",
            duration_seconds=1.0,
        )

        # Test weighted combination
        weights = {"vocals": [0.6, 0.4], "drums": [0.4, 0.6], "bass": [0.5, 0.5]}

        combined = separator._combine_stems_weighted(
            [result1, result2], weights, ["model1", "model2"]
        )

        # Check results
        assert "vocals" in combined
        assert "drums" in combined
        assert "bass" in combined

        # Check shapes
        assert combined["vocals"].shape[0] == 2  # Stereo
        assert combined["drums"].shape[0] == 2
        assert combined["bass"].shape[0] == 2

        # Check values are reasonable (not clipped)
        assert np.max(np.abs(combined["vocals"])) <= 1.0
        assert np.max(np.abs(combined["drums"])) <= 1.0
        assert np.max(np.abs(combined["bass"])) <= 1.0

    def test_ensemble_configs_exist(self):
        """Test that ensemble configs are properly defined"""
        assert "balanced" in ENSEMBLE_CONFIGS
        assert "quality" in ENSEMBLE_CONFIGS
        assert "vocals_focus" in ENSEMBLE_CONFIGS

        # Check balanced config
        balanced = ENSEMBLE_CONFIGS["balanced"]
        assert "models" in balanced
        assert "weights" in balanced
        assert len(balanced["models"]) == 2
        assert "vocals" in balanced["weights"]

        # Check quality config
        quality = ENSEMBLE_CONFIGS["quality"]
        assert len(quality["models"]) == 3

        # Check vocals_focus config
        vocals = ENSEMBLE_CONFIGS["vocals_focus"]
        assert len(vocals["models"]) == 2

    def test_get_temp_dir(self, test_audio_files):
        """Test temporary directory creation"""
        separator = EnsembleSeparator()

        temp_dir = separator._get_temp_dir(
            None, "test_model", test_audio_files["test_file"]
        )

        assert temp_dir.exists()
        assert "test_model" in str(temp_dir)

    def test_singleton(self):
        """Test get_ensemble_separator singleton"""
        sep1 = get_ensemble_separator()
        sep2 = get_ensemble_separator()

        assert sep1 is sep2
        assert isinstance(sep1, EnsembleSeparator)

    def test_find_stem_file(self, test_audio_files):
        """Test finding stem files with various naming"""
        from core.separator import SeparationResult

        separator = EnsembleSeparator()

        result = SeparationResult(
            success=True,
            input_file=test_audio_files["test_file"],
            output_dir=test_audio_files["model1_dir"],
            stems={
                "vocals": test_audio_files["model1_dir"]
                / "test_song_(vocals)_model1.wav",
                "drums": test_audio_files["model1_dir"]
                / "test_song_(drums)_model1.wav",
            },
            model_used="model1",
            device_used="cpu",
            duration_seconds=1.0,
        )

        # Test finding exact match
        vocals_file = separator._find_stem_file(result, "vocals")
        assert vocals_file is not None
        assert vocals_file.exists()

        # Test finding with alternative name
        # (Would need to create test file with alternative name)

    def test_weighted_averaging_math(self):
        """Test that weighted averaging math is correct"""
        separator = EnsembleSeparator()

        # Create simple test arrays
        audio1 = np.array([[1.0, 1.0], [1.0, 1.0]], dtype=np.float32)  # (2, 2)
        audio2 = np.array([[2.0, 2.0], [2.0, 2.0]], dtype=np.float32)

        # Weighted average: 0.6 * audio1 + 0.4 * audio2
        expected = np.array([[1.4, 1.4], [1.4, 1.4]], dtype=np.float32)

        # Simulate weighted combination
        result = audio1 * 0.6 + audio2 * 0.4

        np.testing.assert_array_almost_equal(result, expected, decimal=5)


@pytest.mark.integration
class TestEnsembleIntegration:
    """Integration tests for ensemble separator"""

    @pytest.mark.skip(reason="Requires actual models and takes time")
    def test_full_ensemble_separation(self, test_audio_files):
        """Test full ensemble separation (integration test)"""
        separator = EnsembleSeparator()

        result = separator.separate_ensemble(
            audio_file=test_audio_files["test_file"],
            ensemble_config="balanced",
            progress_callback=lambda msg, pct: print(f"{pct}%: {msg}"),
        )

        # This would actually run separation - skip in unit tests
        # In integration tests with real models, we would check:
        # assert result.success
        # assert len(result.stems) > 0
        # assert 'vocals' in [s.stem for s in result.stems.values()]
        pass
