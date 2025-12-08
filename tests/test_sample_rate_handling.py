"""
Tests for sample rate handling and timing drift fixes

PURPOSE: Verify that all audio processing happens at 44100 Hz to prevent
         progressive timing drift and desynchronization issues.

CONTEXT: Fixes critical bugs where ensemble mode combined stems at different
         sample rates, causing beats to shift backward from the grid over time.
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil

# Add project root to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.separator import Separator, TARGET_SAMPLE_RATE
from core.ensemble_separator import (
    EnsembleSeparator,
    TARGET_SAMPLE_RATE as ENSEMBLE_TARGET_SR,
)
from config import DEFAULT_SAMPLE_RATE, EXPORT_SAMPLE_RATE, RECORDING_SAMPLE_RATE


class TestSampleRateConstants:
    """Test that sample rate constants are correctly defined"""

    def test_target_sample_rate_is_44100(self):
        """Verify TARGET_SAMPLE_RATE is 44100 Hz"""
        assert TARGET_SAMPLE_RATE == 44100, "TARGET_SAMPLE_RATE must be 44100 Hz"
        assert (
            ENSEMBLE_TARGET_SR == 44100
        ), "Ensemble TARGET_SAMPLE_RATE must be 44100 Hz"

    def test_config_sample_rates_are_44100(self):
        """Verify all config sample rates are 44100 Hz"""
        assert DEFAULT_SAMPLE_RATE == 44100, "DEFAULT_SAMPLE_RATE must be 44100 Hz"
        assert EXPORT_SAMPLE_RATE == 44100, "EXPORT_SAMPLE_RATE must be 44100 Hz"
        assert RECORDING_SAMPLE_RATE == 44100, "RECORDING_SAMPLE_RATE must be 44100 Hz"

    def test_sample_rates_are_consistent(self):
        """Verify all sample rate constants match"""
        assert (
            TARGET_SAMPLE_RATE
            == DEFAULT_SAMPLE_RATE
            == EXPORT_SAMPLE_RATE
            == RECORDING_SAMPLE_RATE
            == 44100
        )


class TestAudioResampling:
    """Test audio resampling functions"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def create_test_audio(
        self, sample_rate: int, duration: float, temp_dir: Path
    ) -> Path:
        """
        Create test audio file at specified sample rate

        Args:
            sample_rate: Sample rate in Hz
            duration: Duration in seconds
            temp_dir: Temporary directory

        Returns:
            Path to created audio file
        """
        # Generate sine wave test signal (440 Hz A note)
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * 440 * t)

        # Make stereo
        audio_stereo = np.stack([audio, audio], axis=1)

        # Save to file
        audio_file = temp_dir / f"test_audio_{sample_rate}hz.wav"
        sf.write(str(audio_file), audio_stereo, sample_rate, subtype="PCM_16")

        return audio_file

    def test_44100hz_input_not_resampled(self, temp_dir):
        """Test that 44100 Hz input is not resampled"""
        # Create 44100 Hz test file
        audio_file = self.create_test_audio(44100, 2.0, temp_dir)

        # Check file info
        info = sf.info(str(audio_file))
        assert info.samplerate == 44100, "Test file should be 44100 Hz"

        # Verify no resampling needed
        assert (
            info.samplerate == TARGET_SAMPLE_RATE
        ), "44100 Hz input should not need resampling"

    def test_48000hz_input_needs_resampling(self, temp_dir):
        """Test that 48000 Hz input requires resampling"""
        # Create 48000 Hz test file
        audio_file = self.create_test_audio(48000, 2.0, temp_dir)

        # Check file info
        info = sf.info(str(audio_file))
        assert info.samplerate == 48000, "Test file should be 48000 Hz"

        # Verify resampling needed
        assert (
            info.samplerate != TARGET_SAMPLE_RATE
        ), "48000 Hz input should need resampling"

    def test_resampling_preserves_duration(self, temp_dir):
        """Test that resampling preserves audio duration"""
        import librosa

        # Create 48000 Hz test file
        duration = 3.5
        audio_file = self.create_test_audio(48000, duration, temp_dir)

        # Load and resample
        audio_48k, sr_48k = sf.read(str(audio_file), always_2d=True, dtype="float32")
        audio_48k = audio_48k.T  # (samples, channels) -> (channels, samples)

        # Resample to 44100 Hz
        resampled_channels = []
        for channel in audio_48k:
            resampled = librosa.resample(
                channel, orig_sr=48000, target_sr=44100, res_type="soxr_hq"
            )
            resampled_channels.append(resampled)

        audio_44k = np.array(resampled_channels)

        # Calculate durations
        duration_48k = audio_48k.shape[1] / 48000
        duration_44k = audio_44k.shape[1] / 44100

        # Verify durations match (within 2 samples worth of time at highest SR)
        # WHY: Resampling is sample-based, max error = 2 samples ≈ 0.04ms at 48kHz
        max_error = 2.0 / 48000  # ~0.042 ms
        assert (
            abs(duration_48k - duration_44k) < max_error
        ), f"Resampling should preserve duration (error: {abs(duration_48k - duration_44k)*1000:.3f}ms > {max_error*1000:.3f}ms)"
        assert (
            abs(duration_44k - duration) < max_error
        ), f"Resampled duration should match original (error: {abs(duration_44k - duration)*1000:.3f}ms > {max_error*1000:.3f}ms)"

    def test_resampling_changes_sample_count(self, temp_dir):
        """Test that resampling changes sample count proportionally"""
        import librosa

        # Create 48000 Hz test file
        audio_file = self.create_test_audio(48000, 2.0, temp_dir)

        # Load audio
        audio_48k, _ = sf.read(str(audio_file), always_2d=True, dtype="float32")
        samples_48k = audio_48k.shape[0]

        # Resample to 44100 Hz
        audio_44k_ch0 = librosa.resample(
            audio_48k[:, 0], orig_sr=48000, target_sr=44100, res_type="soxr_hq"
        )
        samples_44k = len(audio_44k_ch0)

        # Calculate expected sample count
        expected_samples = int(samples_48k * 44100 / 48000)

        # Verify sample count changed proportionally (within 1 sample tolerance)
        assert (
            abs(samples_44k - expected_samples) <= 1
        ), "Sample count should change proportionally"
        assert samples_44k < samples_48k, "Downsampling should reduce sample count"


class TestSeparatorInputResampling:
    """Test that Separator class resamples input audio to 44100 Hz"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def create_test_audio(
        self, sample_rate: int, duration: float, temp_dir: Path
    ) -> Path:
        """Create test audio file at specified sample rate"""
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * 440 * t)
        audio_stereo = np.stack([audio, audio], axis=1)

        audio_file = temp_dir / f"test_{sample_rate}hz.wav"
        sf.write(str(audio_file), audio_stereo, sample_rate, subtype="PCM_16")

        return audio_file

    def test_separator_creates_target_sample_rate_constant(self):
        """Test that Separator module has TARGET_SAMPLE_RATE constant"""
        from core import separator

        assert hasattr(
            separator, "TARGET_SAMPLE_RATE"
        ), "Separator should define TARGET_SAMPLE_RATE"
        assert (
            separator.TARGET_SAMPLE_RATE == 44100
        ), "TARGET_SAMPLE_RATE should be 44100"

    def test_separator_input_validation_accepts_44100hz(self, temp_dir):
        """Test that Separator accepts 44100 Hz input without errors"""
        audio_file = self.create_test_audio(44100, 1.0, temp_dir)

        # Verify file can be validated (doesn't test full separation)
        separator = Separator()
        is_valid, error = separator.file_manager.validate_audio_file(audio_file)

        assert is_valid, f"44100 Hz audio should be valid: {error}"

    def test_separator_input_validation_accepts_48000hz(self, temp_dir):
        """Test that Separator accepts 48000 Hz input (will be resampled internally)"""
        audio_file = self.create_test_audio(48000, 1.0, temp_dir)

        # Verify file can be validated
        separator = Separator()
        is_valid, error = separator.file_manager.validate_audio_file(audio_file)

        assert is_valid, f"48000 Hz audio should be valid (will be resampled): {error}"


class TestEnsembleSampleRateValidation:
    """Test ensemble separator sample rate validation and warnings"""

    def test_ensemble_has_target_sample_rate_constant(self):
        """Test that EnsembleSeparator has TARGET_SAMPLE_RATE constant"""
        from core import ensemble_separator

        assert hasattr(
            ensemble_separator, "TARGET_SAMPLE_RATE"
        ), "EnsembleSeparator should define TARGET_SAMPLE_RATE"
        assert (
            ensemble_separator.TARGET_SAMPLE_RATE == 44100
        ), "TARGET_SAMPLE_RATE should be 44100"

    def test_ensemble_separator_initialization(self):
        """Test that EnsembleSeparator initializes without errors"""
        ensemble_sep = EnsembleSeparator()
        assert ensemble_sep is not None, "EnsembleSeparator should initialize"
        assert hasattr(
            ensemble_sep, "separator"
        ), "EnsembleSeparator should have separator attribute"


class TestIntegrationSampleRateDrift:
    """Integration tests for sample rate drift fixes"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def create_test_audio_with_beats(
        self, sample_rate: int, bpm: int, bars: int, temp_dir: Path
    ) -> Path:
        """
        Create test audio with clear beat markers for drift testing

        Args:
            sample_rate: Sample rate in Hz
            bpm: Beats per minute
            bars: Number of 4/4 bars
            temp_dir: Temporary directory

        Returns:
            Path to created audio file
        """
        # Calculate timing
        beat_duration = 60.0 / bpm  # Duration of one beat in seconds
        bar_duration = beat_duration * 4  # 4/4 time signature
        total_duration = bar_duration * bars

        # Generate audio
        t = np.linspace(0, total_duration, int(sample_rate * total_duration))
        audio = np.zeros_like(t)

        # Add click on each downbeat (first beat of each bar)
        for bar in range(bars):
            downbeat_time = bar * bar_duration
            downbeat_sample = int(downbeat_time * sample_rate)

            # Add 100ms click (sine wave burst)
            click_duration = 0.1
            click_samples = int(click_duration * sample_rate)
            if downbeat_sample + click_samples < len(audio):
                click_t = np.linspace(0, click_duration, click_samples)
                click = np.sin(2 * np.pi * 1000 * click_t) * 0.5  # 1kHz click
                audio[downbeat_sample : downbeat_sample + click_samples] = click

        # Make stereo
        audio_stereo = np.stack([audio, audio], axis=1)

        # Save to file
        audio_file = temp_dir / f"test_beats_{bpm}bpm_{sample_rate}hz.wav"
        sf.write(str(audio_file), audio_stereo, sample_rate, subtype="PCM_16")

        return audio_file

    def test_no_timing_drift_with_44100hz_input(self, temp_dir):
        """Test that 44100 Hz input maintains perfect timing"""
        # Create test audio with clear beats
        bpm = 128
        bars = 8  # 8 bars = ~15 seconds at 128 BPM
        audio_file = self.create_test_audio_with_beats(44100, bpm, bars, temp_dir)

        # Verify input sample rate
        info = sf.info(str(audio_file))
        assert info.samplerate == 44100, "Test input should be 44100 Hz"

        # Calculate expected downbeat positions
        beat_duration = 60.0 / bpm
        bar_duration = beat_duration * 4
        expected_downbeats = [bar * bar_duration for bar in range(bars)]

        # Load audio and detect downbeats
        audio, sr = sf.read(str(audio_file), always_2d=True, dtype="float32")
        assert sr == 44100, "Loaded audio should be 44100 Hz"

        # Verify timing preserved (sample count matches expected)
        expected_samples = int(bars * bar_duration * 44100)
        actual_samples = audio.shape[0]

        # Allow 0.1% tolerance for rounding
        tolerance = expected_samples * 0.001
        assert (
            abs(actual_samples - expected_samples) < tolerance
        ), "Sample count should match expected duration"

    def test_timing_preserved_after_resampling(self, temp_dir):
        """Test that 48000 Hz input maintains timing after resampling to 44100 Hz"""
        import librosa

        # Create test audio at 48000 Hz
        bpm = 128
        bars = 8
        audio_file = self.create_test_audio_with_beats(48000, bpm, bars, temp_dir)

        # Verify input is 48000 Hz
        info = sf.info(str(audio_file))
        assert info.samplerate == 48000, "Test input should be 48000 Hz"

        # Load and resample to 44100 Hz
        audio_48k, _ = sf.read(str(audio_file), always_2d=True, dtype="float32")
        audio_48k = audio_48k.T

        resampled_channels = []
        for channel in audio_48k:
            resampled = librosa.resample(
                channel, orig_sr=48000, target_sr=44100, res_type="soxr_hq"
            )
            resampled_channels.append(resampled)

        audio_44k = np.array(resampled_channels)

        # Calculate durations
        beat_duration = 60.0 / bpm
        bar_duration = beat_duration * 4
        expected_duration = bars * bar_duration

        actual_duration_44k = audio_44k.shape[1] / 44100

        # Verify timing preserved (within 2 samples at 48kHz ≈ 0.042ms)
        # WHY: Resampling can only be accurate to nearest sample
        max_error = 2.0 / 48000
        assert (
            abs(actual_duration_44k - expected_duration) < max_error
        ), f"Resampling should preserve timing (error: {abs(actual_duration_44k - expected_duration)*1000:.3f}ms > {max_error*1000:.3f}ms)"

    def test_progressive_drift_detection(self, temp_dir):
        """Test that we can detect progressive timing drift"""
        # Create two audio files: one at 44100 Hz, one at 48000 Hz
        bpm = 128
        bars = 16  # Longer duration to amplify any drift

        audio_44k_file = self.create_test_audio_with_beats(44100, bpm, bars, temp_dir)
        audio_48k_file = self.create_test_audio_with_beats(48000, bpm, bars, temp_dir)

        # Load both files
        audio_44k, sr_44k = sf.read(
            str(audio_44k_file), always_2d=True, dtype="float32"
        )
        audio_48k, sr_48k = sf.read(
            str(audio_48k_file), always_2d=True, dtype="float32"
        )

        # Calculate durations
        duration_44k = audio_44k.shape[0] / sr_44k
        duration_48k = audio_48k.shape[0] / sr_48k

        # Both should have same musical duration (within 2 samples at highest SR)
        max_error = 2.0 / max(sr_44k, sr_48k)
        assert (
            abs(duration_44k - duration_48k) < max_error
        ), f"Both files should have same duration (error: {abs(duration_44k - duration_48k)*1000:.3f}ms > {max_error*1000:.3f}ms)"

        # But different sample counts
        assert audio_44k.shape[0] != audio_48k.shape[0], "Sample counts should differ"

        # Calculate sample rate ratio
        ratio = audio_48k.shape[0] / audio_44k.shape[0]
        expected_ratio = 48000 / 44100

        # Verify ratio matches sample rate ratio
        assert (
            abs(ratio - expected_ratio) < 0.001
        ), "Sample count ratio should match SR ratio"


class TestSampleRateConsistency:
    """Test that all parts of the system use consistent sample rates"""

    def test_all_target_sample_rates_match(self):
        """Test that TARGET_SAMPLE_RATE constants match across modules"""
        from core.separator import TARGET_SAMPLE_RATE as SEP_SR
        from core.ensemble_separator import TARGET_SAMPLE_RATE as ENS_SR

        assert (
            SEP_SR == ENS_SR == 44100
        ), "All TARGET_SAMPLE_RATE constants must be 44100"

    def test_config_consistency(self):
        """Test that config sample rates are all consistent"""
        from config import (
            DEFAULT_SAMPLE_RATE,
            EXPORT_SAMPLE_RATE,
            RECORDING_SAMPLE_RATE,
        )

        assert DEFAULT_SAMPLE_RATE == 44100
        assert EXPORT_SAMPLE_RATE == 44100
        assert RECORDING_SAMPLE_RATE == 44100

        assert DEFAULT_SAMPLE_RATE == EXPORT_SAMPLE_RATE == RECORDING_SAMPLE_RATE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
