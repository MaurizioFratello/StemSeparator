"""
Unit tests for core.time_stretcher module

Tests cover:
- Stretch factor calculation
- Stretch factor validation
- Time-stretching audio (mono and stereo)
- Error handling
- File-based processing
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import soundfile as sf

from core.time_stretcher import (
    calculate_stretch_factor,
    validate_stretch_factor,
    time_stretch_audio,
    time_stretch_file,
    get_stretch_factor_description,
    estimate_processing_time,
    InvalidStretchFactorError,
    ProcessingError,
    LibraryNotFoundError,
    StretchQuality
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_audio_mono():
    """Generate sample mono audio (1 second, 44100 Hz)"""
    sample_rate = 44100
    duration = 1.0
    frequency = 440  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)

    return audio, sample_rate


@pytest.fixture
def sample_audio_stereo():
    """Generate sample stereo audio (1 second, 44100 Hz)"""
    sample_rate = 44100
    duration = 1.0
    frequency = 440  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration))
    mono = np.sin(2 * np.pi * frequency * t).astype(np.float32)

    # Create stereo (slightly different phase in right channel)
    left = mono
    right = np.sin(2 * np.pi * frequency * t + 0.1).astype(np.float32)

    stereo = np.stack([left, right], axis=1)

    return stereo, sample_rate


@pytest.fixture
def temp_audio_file(sample_audio_stereo):
    """Create temporary audio file"""
    audio, sr = sample_audio_stereo

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, sr)
        yield Path(f.name)

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


# ============================================================================
# Test: Stretch Factor Calculation
# ============================================================================

def test_calculate_stretch_factor_faster():
    """Test stretch factor calculation for faster tempo"""
    # 104 BPM → 120 BPM should be ~1.15x faster
    factor = calculate_stretch_factor(104, 120)
    assert abs(factor - 1.1538) < 0.001


def test_calculate_stretch_factor_slower():
    """Test stretch factor calculation for slower tempo"""
    # 120 BPM → 90 BPM should be 0.75x slower
    factor = calculate_stretch_factor(120, 90)
    assert factor == 0.75


def test_calculate_stretch_factor_no_change():
    """Test stretch factor when BPM is unchanged"""
    factor = calculate_stretch_factor(120, 120)
    assert factor == 1.0


def test_calculate_stretch_factor_invalid_bpm():
    """Test error handling for invalid BPM values"""
    with pytest.raises(ValueError):
        calculate_stretch_factor(0, 120)

    with pytest.raises(ValueError):
        calculate_stretch_factor(120, -10)


# ============================================================================
# Test: Stretch Factor Validation
# ============================================================================

def test_validate_stretch_factor_valid():
    """Test validation of valid stretch factors"""
    assert validate_stretch_factor(1.0) is True
    assert validate_stretch_factor(0.75) is True
    assert validate_stretch_factor(1.5) is True


def test_validate_stretch_factor_edge_cases():
    """Test validation at edge of range"""
    assert validate_stretch_factor(0.5) is True  # Minimum
    assert validate_stretch_factor(2.0) is True  # Maximum


def test_validate_stretch_factor_invalid():
    """Test validation of invalid stretch factors"""
    with pytest.raises(InvalidStretchFactorError):
        validate_stretch_factor(0.4)  # Too slow

    with pytest.raises(InvalidStretchFactorError):
        validate_stretch_factor(2.5)  # Too fast


# ============================================================================
# Test: Time-Stretching Mono Audio
# ============================================================================

def test_time_stretch_mono_faster(sample_audio_mono):
    """Test time-stretching mono audio to faster tempo"""
    audio, sr = sample_audio_mono
    stretch_factor = 1.5  # 50% faster

    stretched = time_stretch_audio(audio, sr, stretch_factor)

    # Check output is shorter (faster)
    expected_length = int(len(audio) / stretch_factor)
    assert abs(len(stretched) - expected_length) < sr * 0.01  # Within 10ms tolerance

    # Check output is still mono
    assert stretched.ndim == 1

    # Check output is not empty
    assert stretched.size > 0


def test_time_stretch_mono_slower(sample_audio_mono):
    """Test time-stretching mono audio to slower tempo"""
    audio, sr = sample_audio_mono
    stretch_factor = 0.75  # 25% slower

    stretched = time_stretch_audio(audio, sr, stretch_factor)

    # Check output is longer (slower)
    expected_length = int(len(audio) / stretch_factor)
    assert abs(len(stretched) - expected_length) < sr * 0.01  # Within 10ms tolerance

    # Check output is still mono
    assert stretched.ndim == 1


# ============================================================================
# Test: Time-Stretching Stereo Audio
# ============================================================================

def test_time_stretch_stereo_faster(sample_audio_stereo):
    """Test time-stretching stereo audio to faster tempo"""
    audio, sr = sample_audio_stereo
    stretch_factor = 1.2  # 20% faster

    stretched = time_stretch_audio(audio, sr, stretch_factor)

    # Check output is shorter
    expected_length = int(len(audio) / stretch_factor)
    assert abs(len(stretched) - expected_length) < sr * 0.01

    # Check output is still stereo with correct shape
    assert stretched.ndim == 2
    assert stretched.shape[1] == 2


def test_time_stretch_stereo_slower(sample_audio_stereo):
    """Test time-stretching stereo audio to slower tempo"""
    audio, sr = sample_audio_stereo
    stretch_factor = 0.8  # 20% slower

    stretched = time_stretch_audio(audio, sr, stretch_factor)

    # Check output is longer
    expected_length = int(len(audio) / stretch_factor)
    assert abs(len(stretched) - expected_length) < sr * 0.01

    # Check output is still stereo
    assert stretched.ndim == 2
    assert stretched.shape[1] == 2


# ============================================================================
# Test: Quality Presets
# ============================================================================

def test_time_stretch_preview_quality(sample_audio_mono):
    """Test time-stretching with preview quality preset"""
    audio, sr = sample_audio_mono

    stretched = time_stretch_audio(
        audio, sr, 1.15,
        quality_preset=StretchQuality.PREVIEW
    )

    assert stretched.size > 0


def test_time_stretch_export_quality(sample_audio_mono):
    """Test time-stretching with export quality preset"""
    audio, sr = sample_audio_mono

    stretched = time_stretch_audio(
        audio, sr, 1.15,
        quality_preset=StretchQuality.EXPORT
    )

    assert stretched.size > 0


# ============================================================================
# Test: Error Handling
# ============================================================================

def test_time_stretch_invalid_factor(sample_audio_mono):
    """Test error handling for invalid stretch factor"""
    audio, sr = sample_audio_mono

    with pytest.raises(InvalidStretchFactorError):
        time_stretch_audio(audio, sr, 3.0)  # Too extreme


def test_time_stretch_empty_audio():
    """Test error handling for empty audio"""
    empty_audio = np.array([])

    with pytest.raises(ProcessingError):
        time_stretch_audio(empty_audio, 44100, 1.5)


def test_time_stretch_invalid_sample_rate(sample_audio_mono):
    """Test error handling for invalid sample rate"""
    audio, _ = sample_audio_mono

    with pytest.raises(ValueError):
        time_stretch_audio(audio, -1, 1.5)


def test_time_stretch_unsupported_shape():
    """Test error handling for unsupported audio shape"""
    # 3D array (unsupported)
    audio = np.zeros((100, 2, 2))

    with pytest.raises(ProcessingError):
        time_stretch_audio(audio, 44100, 1.5)


# ============================================================================
# Test: File Processing
# ============================================================================

def test_time_stretch_file(temp_audio_file):
    """Test file-based time-stretching"""
    input_path = temp_audio_file

    with tempfile.NamedTemporaryFile(suffix='_stretched.wav', delete=False) as f:
        output_path = Path(f.name)

    try:
        # Time-stretch file
        success = time_stretch_file(
            input_path,
            output_path,
            stretch_factor=1.2
        )

        assert success is True
        assert output_path.exists()

        # Verify output file
        audio, sr = sf.read(str(output_path))
        assert audio.size > 0
        assert sr == 44100

    finally:
        output_path.unlink(missing_ok=True)


def test_time_stretch_file_nonexistent():
    """Test error handling for nonexistent input file"""
    input_path = Path('/nonexistent/file.wav')
    output_path = Path('/tmp/output.wav')

    success = time_stretch_file(input_path, output_path, 1.5)
    assert success is False


# ============================================================================
# Test: Utility Functions
# ============================================================================

def test_get_stretch_factor_description_faster():
    """Test description generation for faster tempo"""
    desc = get_stretch_factor_description(1.15)
    assert "faster" in desc.lower()
    assert "15" in desc  # 15%


def test_get_stretch_factor_description_slower():
    """Test description generation for slower tempo"""
    desc = get_stretch_factor_description(0.75)
    assert "slower" in desc.lower()
    assert "25" in desc  # 25%


def test_get_stretch_factor_description_no_change():
    """Test description for no change"""
    desc = get_stretch_factor_description(1.0)
    assert "no change" in desc.lower()


def test_estimate_processing_time():
    """Test processing time estimation"""
    # 10 second audio with preview quality
    time_preview = estimate_processing_time(10.0, 1.15, StretchQuality.PREVIEW)
    assert time_preview > 0
    assert time_preview < 10.0  # Should be faster than real-time

    # Export quality should be slower
    time_export = estimate_processing_time(10.0, 1.15, StretchQuality.EXPORT)
    assert time_export > time_preview


# ============================================================================
# Test: Integration
# ============================================================================

def test_full_workflow_bpm_to_stretched_audio(sample_audio_stereo):
    """Test complete workflow: BPM → stretch factor → stretched audio"""
    audio, sr = sample_audio_stereo

    # User wants to go from 104 BPM to 120 BPM
    current_bpm = 104
    target_bpm = 120

    # Calculate stretch factor
    stretch_factor = calculate_stretch_factor(current_bpm, target_bpm)
    assert abs(stretch_factor - 1.1538) < 0.001

    # Validate factor
    assert validate_stretch_factor(stretch_factor)

    # Time-stretch
    stretched = time_stretch_audio(audio, sr, stretch_factor)

    # Verify result
    assert stretched.size > 0
    assert stretched.ndim == 2  # Still stereo

    # Verify duration changed correctly
    original_duration = len(audio) / sr
    stretched_duration = len(stretched) / sr
    expected_duration = original_duration / stretch_factor

    assert abs(stretched_duration - expected_duration) < 0.01  # Within 10ms


# ============================================================================
# Skip Tests if PyRubberBand Not Installed
# ============================================================================

def test_library_availability():
    """Test that pyrubberband is installed"""
    try:
        import pyrubberband
        assert True
    except ImportError:
        pytest.skip("pyrubberband not installed")
