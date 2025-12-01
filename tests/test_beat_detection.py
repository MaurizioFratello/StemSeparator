"""
Unit tests for beat detection module

Test Coverage:
- Device detection
- BeatNet availability checking
- Loop calculation logic
- Error handling
- Edge cases
"""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from utils.beat_detection import (
    is_beatnet_available,
    detect_beats_and_downbeats,
    calculate_loops_from_downbeats,
    _get_best_device,
    _get_beatnet_predictor
)


# ============================================================================
# Device Detection Tests
# ============================================================================

def test_get_best_device_cuda():
    """Test device detection when CUDA is available"""
    with patch('torch.cuda.is_available', return_value=True):
        device = _get_best_device()
        assert device == 'cuda'


def test_get_best_device_mps():
    """Test device detection when MPS is available (Apple Silicon)"""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = True

    with patch.dict('sys.modules', {'torch': mock_torch}):
        device = _get_best_device()
        assert device == 'mps'


def test_get_best_device_cpu():
    """Test device detection fallback to CPU"""
    with patch('torch.cuda.is_available', return_value=False):
        with patch('torch.backends.mps.is_available', return_value=False):
            device = _get_best_device()
            assert device == 'cpu'


def test_get_best_device_no_torch():
    """Test device detection when PyTorch not installed"""
    with patch.dict('sys.modules', {'torch': None}):
        with patch('builtins.__import__', side_effect=ImportError):
            device = _get_best_device()
            assert device == 'cpu'


# ============================================================================
# BeatNet Availability Tests
# ============================================================================

def test_is_beatnet_available_true():
    """Test BeatNet availability when installed"""
    # Reset global cache
    import utils.beat_detection
    utils.beat_detection._beatnet_available = None

    with patch('builtins.__import__') as mock_import:
        # Simulate successful import
        mock_import.return_value = MagicMock()
        result = is_beatnet_available()
        assert result is True


def test_is_beatnet_available_false():
    """Test BeatNet availability when not installed"""
    # Reset global cache
    import utils.beat_detection
    utils.beat_detection._beatnet_available = None

    with patch('builtins.__import__', side_effect=ImportError("No module named 'BeatNet'")):
        result = is_beatnet_available()
        assert result is False


def test_is_beatnet_available_caching():
    """Test that availability check is cached"""
    import utils.beat_detection

    # Set cache
    utils.beat_detection._beatnet_available = True

    # Should return cached value without import attempt
    result = is_beatnet_available()
    assert result is True


# ============================================================================
# Loop Calculation Tests
# ============================================================================

def test_calculate_loops_basic():
    """Test loop calculation with evenly spaced downbeats"""
    downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=2, audio_duration=12.0)

    assert len(loops) == 3
    assert loops[0] == (0.0, 4.0)  # Downbeats 0-2
    assert loops[1] == (4.0, 8.0)  # Downbeats 2-4
    assert loops[2] == (8.0, 12.0)  # Downbeats 4-6


def test_calculate_loops_four_bars():
    """Test 4-bar loop calculation"""
    downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=16.0)

    assert len(loops) == 2
    assert loops[0] == (0.0, 8.0)  # 4 bars
    assert loops[1] == (8.0, 16.0)  # 4 bars


def test_calculate_loops_partial_last():
    """Test loop calculation with partial last loop"""
    downbeats = np.array([0.0, 2.0, 4.0, 6.0])  # Only 4 downbeats
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=10.0)

    assert len(loops) == 1
    assert loops[0][0] == 0.0
    # End time should be extrapolated or use audio duration
    assert 8.0 <= loops[0][1] <= 10.0


def test_calculate_loops_single_bar():
    """Test single bar loops"""
    downbeats = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=1, audio_duration=5.0)

    assert len(loops) == 5
    assert loops[0] == (0.0, 1.0)
    assert loops[1] == (1.0, 2.0)
    assert loops[4] == (4.0, 5.0)


def test_calculate_loops_eight_bars():
    """Test 8-bar loop calculation"""
    downbeats = np.linspace(0, 16, 17)  # 17 downbeats (0-16s, every 1s)
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=8, audio_duration=20.0)

    assert len(loops) == 3  # 2 complete + 1 partial
    assert loops[0] == (0.0, 8.0)
    assert loops[1] == (8.0, 16.0)


def test_calculate_loops_uneven_spacing():
    """Test with unevenly spaced downbeats"""
    downbeats = np.array([0.0, 1.5, 3.5, 5.0, 7.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=2, audio_duration=10.0)

    assert len(loops) == 3
    assert loops[0] == (0.0, 3.5)
    assert loops[1] == (3.5, 7.0)
    # Last loop uses extrapolation


def test_calculate_loops_empty_downbeats():
    """Test error handling for empty downbeats"""
    with pytest.raises(ValueError, match="No downbeats"):
        calculate_loops_from_downbeats(np.array([]), bars_per_loop=4, audio_duration=10.0)


def test_calculate_loops_invalid_bars():
    """Test error handling for invalid bars_per_loop"""
    downbeats = np.array([0.0, 2.0, 4.0])

    with pytest.raises(ValueError, match="Invalid bars_per_loop"):
        calculate_loops_from_downbeats(downbeats, bars_per_loop=0, audio_duration=10.0)

    with pytest.raises(ValueError, match="Invalid bars_per_loop"):
        calculate_loops_from_downbeats(downbeats, bars_per_loop=-1, audio_duration=10.0)


def test_calculate_loops_single_downbeat():
    """Test with only one downbeat"""
    downbeats = np.array([2.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=10.0)

    assert len(loops) == 1
    assert loops[0][0] == 2.0
    assert loops[0][1] == 10.0  # Should use audio duration


def test_calculate_loops_last_partial_uses_duration():
    """Test that partial last loop respects audio duration"""
    downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=12.0)

    assert len(loops) == 2
    assert loops[0] == (0.0, 8.0)
    # Last loop should not exceed audio duration
    assert loops[1][1] <= 12.0


# ============================================================================
# Beat Detection Integration Tests (Mocked)
# ============================================================================

def test_detect_beats_file_not_found():
    """Test error handling when audio file doesn't exist"""
    fake_path = Path("/nonexistent/file.wav")

    with pytest.raises(FileNotFoundError, match="Audio file not found"):
        detect_beats_and_downbeats(fake_path)


@patch('pathlib.Path.exists')
def test_detect_beats_beatnet_unavailable(mock_exists):
    """Test error handling when BeatNet is not available"""
    mock_exists.return_value = True  # File exists

    import utils.beat_detection
    utils.beat_detection._beatnet_available = False
    utils.beat_detection._beatnet_predictor = None

    with pytest.raises(RuntimeError, match="BeatNet not available"):
        detect_beats_and_downbeats(Path("dummy.wav"))


@patch('utils.beat_detection._get_beatnet_predictor')
@patch('soundfile.read')
@patch('pathlib.Path.exists')
def test_detect_beats_no_beats_detected(mock_exists, mock_sf_read, mock_predictor):
    """Test error handling when no beats detected"""
    mock_exists.return_value = True
    mock_sf_read.return_value = (np.random.randn(44100), 44100)

    # Mock predictor returning None
    mock_pred_instance = Mock()
    mock_pred_instance.process.return_value = None
    mock_predictor.return_value = mock_pred_instance

    with pytest.raises(ValueError, match="No beats detected"):
        detect_beats_and_downbeats(Path("dummy.wav"))


@patch('utils.beat_detection._get_beatnet_predictor')
@patch('soundfile.read')
@patch('pathlib.Path.exists')
def test_detect_beats_successful(mock_exists, mock_sf_read, mock_predictor):
    """Test successful beat detection"""
    mock_exists.return_value = True
    mock_sf_read.return_value = (np.random.randn(44100), 22050)  # Already 22050 Hz

    # Mock BeatNet result
    # Format: [[beat_time, is_downbeat], ...]
    mock_result = np.array([
        [0.0, 1],   # Downbeat
        [0.5, 0],   # Regular beat
        [1.0, 0],
        [1.5, 0],
        [2.0, 1],   # Downbeat
        [2.5, 0],
        [3.0, 0],
        [3.5, 0],
        [4.0, 1],   # Downbeat
    ])

    mock_pred_instance = Mock()
    mock_pred_instance.process.return_value = mock_result
    mock_predictor.return_value = mock_pred_instance

    beats, downbeats, first_db, msg = detect_beats_and_downbeats(Path("dummy.wav"))

    assert len(beats) == 9
    assert len(downbeats) == 3
    assert first_db == 0.0
    assert "BeatNet" in msg
    assert beats[0] == 0.0
    assert beats[4] == 2.0
    assert np.array_equal(downbeats, np.array([0.0, 2.0, 4.0]))


@patch('utils.beat_detection._get_beatnet_predictor')
@patch('soundfile.read')
@patch('pathlib.Path.exists')
def test_detect_beats_no_downbeats_fallback(mock_exists, mock_sf_read, mock_predictor):
    """Test fallback when no downbeats detected"""
    mock_exists.return_value = True
    mock_sf_read.return_value = (np.random.randn(44100), 22050)

    # Mock result with no downbeats (all zeros in second column)
    mock_result = np.array([
        [0.0, 0],
        [0.5, 0],
        [1.0, 0],
        [1.5, 0],
    ])

    mock_pred_instance = Mock()
    mock_pred_instance.process.return_value = mock_result
    mock_predictor.return_value = mock_pred_instance

    beats, downbeats, first_db, msg = detect_beats_and_downbeats(Path("dummy.wav"))

    # Should use first beat as downbeat
    assert len(downbeats) == 1
    assert first_db == 0.0
    assert downbeats[0] == 0.0


@patch('utils.beat_detection._get_beatnet_predictor')
@patch('soundfile.read')
@patch('utils.audio_processing.resample_audio')
@patch('pathlib.Path.exists')
def test_detect_beats_resampling(mock_exists, mock_resample, mock_sf_read, mock_predictor):
    """Test that audio is resampled to 22050 Hz"""
    mock_exists.return_value = True
    mock_sf_read.return_value = (np.random.randn(44100), 44100)  # 44100 Hz audio
    mock_resample.return_value = np.random.randn(22050)  # Resampled to 22050

    mock_result = np.array([[0.0, 1], [1.0, 1]])
    mock_pred_instance = Mock()
    mock_pred_instance.process.return_value = mock_result
    mock_predictor.return_value = mock_pred_instance

    detect_beats_and_downbeats(Path("dummy.wav"))

    # Verify resample was called
    mock_resample.assert_called_once()
    args = mock_resample.call_args[0]
    assert args[1] == 44100  # Original SR
    assert args[2] == 22050  # Target SR


@patch('utils.beat_detection._get_beatnet_predictor')
@patch('soundfile.read')
@patch('pathlib.Path.exists')
def test_detect_beats_stereo_to_mono(mock_exists, mock_sf_read, mock_predictor):
    """Test that stereo audio is converted to mono"""
    mock_exists.return_value = True
    # Stereo audio (samples, channels)
    stereo_audio = np.random.randn(22050, 2)
    mock_sf_read.return_value = (stereo_audio, 22050)

    mock_result = np.array([[0.0, 1], [1.0, 1]])
    mock_pred_instance = Mock()
    mock_pred_instance.process.return_value = mock_result
    mock_predictor.return_value = mock_pred_instance

    beats, downbeats, first_db, msg = detect_beats_and_downbeats(Path("dummy.wav"))

    # Should complete without error (conversion happens internally)
    assert len(beats) > 0


@patch('utils.beat_detection._get_beatnet_predictor')
@patch('soundfile.read')
@patch('pathlib.Path.exists')
def test_detect_beats_with_bpm_hint(mock_exists, mock_sf_read, mock_predictor):
    """Test beat detection with BPM hint (should be logged but not used by BeatNet)"""
    mock_exists.return_value = True
    mock_sf_read.return_value = (np.random.randn(22050), 22050)

    mock_result = np.array([[0.0, 1], [1.0, 1]])
    mock_pred_instance = Mock()
    mock_pred_instance.process.return_value = mock_result
    mock_predictor.return_value = mock_pred_instance

    beats, downbeats, first_db, msg = detect_beats_and_downbeats(
        Path("dummy.wav"),
        bpm_hint=120.0
    )

    # Should complete successfully
    assert len(beats) == 2


# ============================================================================
# Edge Cases and Robustness Tests
# ============================================================================

def test_calculate_loops_very_short_audio():
    """Test with very short audio (less than one loop)"""
    downbeats = np.array([0.0, 0.5])  # Only 0.5s between downbeats
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=1.0)

    assert len(loops) == 1
    assert loops[0][0] == 0.0


def test_calculate_loops_exact_fit():
    """Test when loops fit exactly into audio duration"""
    # 5 downbeats, 4 bars per loop = 1 complete loop + 1 partial
    # Loop 1: downbeats[0:4] = 0.0 to 8.0
    # Loop 2: downbeats[4] = 8.0 to audio_duration (8.0) - partial/empty
    downbeats = np.array([0.0, 2.0, 4.0, 6.0, 8.0])
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=4, audio_duration=8.0)

    # Expected: 2 loops (1 complete + 1 starting at 8.0)
    assert len(loops) == 2
    assert loops[0] == (0.0, 8.0)
    # Second loop starts at 8.0 and ends at audio duration
    assert loops[1][0] == 8.0


def test_calculate_loops_many_small_loops():
    """Test with many small loops (1 bar each)"""
    downbeats = np.linspace(0, 10, 21)  # 21 downbeats, 0.5s apart
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=1, audio_duration=10.0)

    assert len(loops) == 21
    # Check spacing
    for i in range(len(loops) - 1):
        duration = loops[i][1] - loops[i][0]
        assert 0.4 <= duration <= 0.6  # ~0.5s per loop


def test_calculate_loops_large_bars_per_loop():
    """Test with very large bars_per_loop (16 bars)"""
    downbeats = np.linspace(0, 32, 33)  # 33 downbeats
    loops = calculate_loops_from_downbeats(downbeats, bars_per_loop=16, audio_duration=35.0)

    assert len(loops) == 3  # 2 complete 16-bar loops + 1 partial
    assert loops[0] == (0.0, 16.0)
    assert loops[1] == (16.0, 32.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=utils.beat_detection", "--cov-report=term-missing"])
