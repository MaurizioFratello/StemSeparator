"""
Tests for sampler_export module - Loop export functionality
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
from core.sampler_export import export_sampler_loops, detect_audio_bpm, ExportResult


@pytest.fixture
def temp_audio_file(tmp_path):
    """
    Create a temporary test audio file.

    Creates a 10-second sine wave at 440 Hz, 44.1 kHz, stereo.
    """
    sample_rate = 44100
    duration = 10.0  # seconds
    frequency = 440.0  # Hz (A4 note)

    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # Generate stereo sine wave
    # Left channel: pure 440 Hz
    # Right channel: 440 Hz with slight phase offset
    left = np.sin(2 * np.pi * frequency * t)
    right = np.sin(2 * np.pi * frequency * t + 0.1)

    # Stack into stereo
    audio = np.stack([left, right], axis=1).astype(np.float32)

    # Save to file
    audio_path = tmp_path / "test_audio.wav"
    sf.write(str(audio_path), audio, sample_rate, subtype="PCM_24")

    return audio_path


@pytest.fixture
def temp_short_audio_file(tmp_path):
    """
    Create a short audio file (2 seconds) for testing short input.
    """
    sample_rate = 44100
    duration = 2.0  # seconds
    frequency = 440.0

    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)

    audio_path = tmp_path / "test_short_audio.wav"
    sf.write(str(audio_path), audio, sample_rate, subtype="PCM_16")

    return audio_path


class TestExportBasicFunctionality:
    """Basic export functionality tests"""

    def test_export_single_chunk(self, temp_audio_file, tmp_path):
        """Test exporting audio that fits in a single chunk"""
        output_dir = tmp_path / "output"

        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=output_dir,
            bpm=120,
            bars=4,  # 4 bars at 120 BPM = 8s, so 10s audio -> 2 chunks
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True
        assert result.error_message is None
        assert len(result.output_files) == 2  # 10s / 8s per chunk = 2 chunks
        assert result.chunk_count == 2

        # Check that files were created
        for file_path in result.output_files:
            assert file_path.exists()
            assert file_path.suffix == ".wav"

    def test_export_filename_format_single(self, temp_short_audio_file, tmp_path):
        """Test filename format for single chunk export"""
        output_dir = tmp_path / "output"

        result = export_sampler_loops(
            input_path=temp_short_audio_file,
            output_dir=output_dir,
            bpm=120,
            bars=4,  # 4 bars = 8s > 2s file -> single chunk
            sample_rate=44100,
            bit_depth=16,
            channels=1,
        )

        assert result.success is True
        assert len(result.output_files) == 1

        # Check filename format: <name>_<bpm>_<bars>t.wav
        filename = result.output_files[0].name
        assert "test_short_audio" in filename
        assert "_120_" in filename
        assert "_4t.wav" in filename

    def test_export_filename_format_multiple(self, temp_audio_file, tmp_path):
        """Test filename format for multiple chunk export"""
        output_dir = tmp_path / "output"

        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=output_dir,
            bpm=150,
            bars=2,  # 2 bars at 150 BPM = 3.2s -> 4 chunks from 10s
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True
        assert len(result.output_files) >= 3

        # Check filename format: <name>_<bpm>_<bars>t_part<NN>.wav
        for idx, file_path in enumerate(result.output_files):
            filename = file_path.name
            assert "test_audio" in filename
            assert "_150_" in filename
            assert "_2t_part" in filename
            assert f"{idx + 1:02d}" in filename

    def test_export_creates_output_dir(self, temp_audio_file, tmp_path):
        """Test that export creates output directory if it doesn't exist"""
        output_dir = tmp_path / "new_dir" / "nested" / "output"
        assert not output_dir.exists()

        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=output_dir,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True
        assert output_dir.exists()


class TestExportValidation:
    """Tests for input validation and error handling"""

    def test_invalid_file_path(self, tmp_path):
        """Test export with non-existent input file"""
        result = export_sampler_loops(
            input_path=Path("/nonexistent/file.wav"),
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_invalid_bpm_bars_combination(self, temp_audio_file, tmp_path):
        """Test export with BPM+bars combination that exceeds 20s limit"""
        # 8 bars at 80 BPM = 24s (exceeds 20s limit)
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=80,
            bars=8,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is False
        assert (
            "invalid" in result.error_message.lower()
            or "exceed" in result.error_message.lower()
        )

    def test_bpm_rounding(self, temp_audio_file, tmp_path):
        """Test that float BPM is rounded to integer"""
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=128.7,  # Should round to 129
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True
        # Check filename contains rounded BPM
        filename = result.output_files[0].name
        assert "_129_" in filename


class TestExportAudioFormats:
    """Tests for different audio format configurations"""

    def test_export_mono(self, temp_audio_file, tmp_path):
        """Test export with mono conversion"""
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=1,  # Mono
        )

        assert result.success is True

        # Load exported file and check it's mono
        exported_audio, sr = sf.read(str(result.output_files[0]))
        assert exported_audio.ndim == 1  # Mono = 1D array

    def test_export_stereo(self, temp_short_audio_file, tmp_path):
        """Test export maintaining stereo (from mono source)"""
        result = export_sampler_loops(
            input_path=temp_short_audio_file,  # Mono source
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,  # Convert to stereo
        )

        assert result.success is True

        # Load exported file and check it's stereo
        exported_audio, sr = sf.read(str(result.output_files[0]))
        assert exported_audio.ndim == 2  # Stereo = 2D array
        assert exported_audio.shape[1] == 2

    def test_export_16bit(self, temp_audio_file, tmp_path):
        """Test export with 16-bit depth (should apply dither)"""
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=16,
            channels=2,
        )

        assert result.success is True

        # Verify file was created with correct bit depth
        info = sf.info(str(result.output_files[0]))
        assert info.subtype == "PCM_16"

    def test_export_48khz(self, temp_audio_file, tmp_path):
        """Test export with resampling to 48kHz"""
        result = export_sampler_loops(
            input_path=temp_audio_file,  # 44.1kHz source
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=48000,  # Resample to 48kHz
            bit_depth=24,
            channels=2,
        )

        assert result.success is True

        # Verify file was resampled
        info = sf.info(str(result.output_files[0]))
        assert info.samplerate == 48000

    def test_export_flac_format(self, temp_audio_file, tmp_path):
        """Test export to FLAC format"""
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
            file_format="FLAC",
        )

        assert result.success is True
        assert result.output_files[0].suffix == ".flac"


class TestExportMetadata:
    """Tests for export metadata and result information"""

    def test_result_contains_metadata(self, temp_audio_file, tmp_path):
        """Test that ExportResult contains all expected metadata"""
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True
        assert result.chunk_count > 0
        assert result.samples_per_chunk > 0
        assert len(result.effective_durations_sec) == result.chunk_count
        assert len(result.zero_crossing_shifts) == result.chunk_count
        assert len(result.output_files) == result.chunk_count

    def test_zero_crossing_shifts_within_tolerance(self, temp_audio_file, tmp_path):
        """Test that zero-crossing shifts are within ±5 samples"""
        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True

        # All zero-crossing shifts should be within ±5 samples
        for shift in result.zero_crossing_shifts:
            assert abs(shift) <= 5

    def test_short_input_warning(self, temp_short_audio_file, tmp_path):
        """Test that warning is issued when input is shorter than chunk length"""
        result = export_sampler_loops(
            input_path=temp_short_audio_file,  # 2s
            output_dir=tmp_path,
            bpm=120,
            bars=4,  # 4 bars = 8s
            sample_rate=44100,
            bit_depth=24,
            channels=2,
        )

        assert result.success is True
        assert len(result.warning_messages) > 0
        assert any("shorter" in msg.lower() for msg in result.warning_messages)


class TestProgressCallback:
    """Tests for progress callback functionality"""

    def test_progress_callback_called(self, temp_audio_file, tmp_path):
        """Test that progress callback is called during export"""
        progress_updates = []

        def progress_callback(message: str, percent: int):
            progress_updates.append((message, percent))

        result = export_sampler_loops(
            input_path=temp_audio_file,
            output_dir=tmp_path,
            bpm=120,
            bars=4,
            sample_rate=44100,
            bit_depth=24,
            channels=2,
            progress_callback=progress_callback,
        )

        assert result.success is True
        # Should have received multiple progress updates
        assert len(progress_updates) >= 3
        # Final update should be 100%
        assert progress_updates[-1][1] == 100


class TestBPMDetection:
    """Tests for BPM detection helper function"""

    def test_detect_bpm_returns_valid(self, temp_audio_file):
        """Test BPM detection on test file"""
        bpm, message = detect_audio_bpm(temp_audio_file)

        # Should return a positive BPM value
        assert bpm > 0
        assert isinstance(bpm, float)
        assert message != ""

    def test_detect_bpm_nonexistent_file(self):
        """Test BPM detection on non-existent file"""
        bpm, message = detect_audio_bpm(Path("/nonexistent/file.wav"))

        # Should fallback to 120 BPM
        assert bpm == 120.0
        assert "error" in message.lower() or "default" in message.lower()
