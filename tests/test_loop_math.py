"""
Tests for loop_math module - Musical calculations for sampler export
"""
import pytest
from utils.loop_math import (
    compute_bar_duration_seconds,
    compute_chunk_duration_seconds,
    compute_samples_per_chunk,
    is_valid_for_sampler,
    get_minimum_bpm,
    MIN_BPM_2_BARS,
    MIN_BPM_4_BARS,
    MIN_BPM_8_BARS
)


class TestComputeBarDuration:
    """Tests for compute_bar_duration_seconds"""

    def test_standard_120_bpm(self):
        """Test bar duration at 120 BPM (common tempo)"""
        # At 120 BPM, one beat = 0.5s, one bar (4 beats) = 2.0s
        assert compute_bar_duration_seconds(120) == 2.0

    def test_slow_60_bpm(self):
        """Test bar duration at 60 BPM (slow tempo)"""
        # At 60 BPM, one beat = 1.0s, one bar = 4.0s
        assert compute_bar_duration_seconds(60) == 4.0

    def test_fast_240_bpm(self):
        """Test bar duration at 240 BPM (fast tempo)"""
        # At 240 BPM, one beat = 0.25s, one bar = 1.0s
        assert compute_bar_duration_seconds(240) == 1.0

    def test_edge_case_1_bpm(self):
        """Test extremely slow 1 BPM"""
        # At 1 BPM, one beat = 60s, one bar = 240s
        assert compute_bar_duration_seconds(1) == 240.0

    def test_invalid_zero_bpm(self):
        """Test that zero BPM raises error"""
        with pytest.raises(ValueError):
            compute_bar_duration_seconds(0)

    def test_invalid_negative_bpm(self):
        """Test that negative BPM raises error"""
        with pytest.raises(ValueError):
            compute_bar_duration_seconds(-120)


class TestComputeChunkDuration:
    """Tests for compute_chunk_duration_seconds"""

    def test_2_bars_120_bpm(self):
        """Test 2 bars at 120 BPM"""
        # 2 bars at 120 BPM = 4.0s
        assert compute_chunk_duration_seconds(120, 2) == 4.0

    def test_4_bars_120_bpm(self):
        """Test 4 bars at 120 BPM"""
        # 4 bars at 120 BPM = 8.0s
        assert compute_chunk_duration_seconds(120, 4) == 8.0

    def test_8_bars_120_bpm(self):
        """Test 8 bars at 120 BPM"""
        # 8 bars at 120 BPM = 16.0s
        assert compute_chunk_duration_seconds(120, 8) == 16.0

    def test_4_bars_100_bpm(self):
        """Test 4 bars at 100 BPM"""
        # 4 bars at 100 BPM = 9.6s
        assert compute_chunk_duration_seconds(100, 4) == 9.6

    def test_invalid_zero_bars(self):
        """Test that zero bars raises error"""
        with pytest.raises(ValueError):
            compute_chunk_duration_seconds(120, 0)


class TestComputeSamplesPerChunk:
    """Tests for compute_samples_per_chunk"""

    def test_4_bars_120_bpm_44100(self):
        """Test 4 bars at 120 BPM, 44.1kHz"""
        # 4 bars at 120 BPM = 8.0s
        # 8.0s * 44100 Hz = 352800 samples
        assert compute_samples_per_chunk(120, 4, 44100) == 352800

    def test_4_bars_120_bpm_48000(self):
        """Test 4 bars at 120 BPM, 48kHz"""
        # 4 bars at 120 BPM = 8.0s
        # 8.0s * 48000 Hz = 384000 samples
        assert compute_samples_per_chunk(120, 4, 48000) == 384000

    def test_2_bars_90_bpm_44100(self):
        """Test 2 bars at 90 BPM, 44.1kHz"""
        # 2 bars at 90 BPM = 5.333... s
        # 5.333... * 44100 = 235200 samples
        expected = round(5.333333333333333 * 44100)
        assert compute_samples_per_chunk(90, 2, 44100) == expected

    def test_rounding(self):
        """Test that result is properly rounded to integer"""
        # Use odd BPM that doesn't divide evenly
        result = compute_samples_per_chunk(117, 3, 44100)
        assert isinstance(result, int)
        assert result > 0


class TestIsValidForSampler:
    """Tests for is_valid_for_sampler (20-second limit)"""

    def test_valid_4_bars_120_bpm(self):
        """Test valid combination: 4 bars at 120 BPM = 8s"""
        is_valid, msg = is_valid_for_sampler(120, 4)
        assert is_valid is True
        assert msg == ""

    def test_valid_8_bars_96_bpm(self):
        """Test edge case: 8 bars at 96 BPM = exactly 20s"""
        is_valid, msg = is_valid_for_sampler(96, 8)
        assert is_valid is True  # Exactly at limit should be valid
        assert msg == ""

    def test_invalid_8_bars_80_bpm(self):
        """Test invalid: 8 bars at 80 BPM = 24s (exceeds 20s)"""
        is_valid, msg = is_valid_for_sampler(80, 8)
        assert is_valid is False
        assert "24.00s" in msg
        assert "20.00s" in msg

    def test_invalid_2_bars_20_bpm(self):
        """Test invalid: 2 bars at 20 BPM = 24s"""
        is_valid, msg = is_valid_for_sampler(20, 2)
        assert is_valid is False
        assert "exceeding" in msg.lower()

    def test_edge_2_bars_minimum(self):
        """Test 2 bars at minimum BPM (24 BPM = exactly 20s)"""
        is_valid, msg = is_valid_for_sampler(24, 2)
        assert is_valid is True

    def test_edge_4_bars_minimum(self):
        """Test 4 bars at minimum BPM (48 BPM = exactly 20s)"""
        is_valid, msg = is_valid_for_sampler(48, 4)
        assert is_valid is True


class TestGetMinimumBPM:
    """Tests for get_minimum_bpm"""

    def test_2_bars(self):
        """Test minimum BPM for 2 bars (20s limit)"""
        # 2 bars * 4 beats * 60s / 20s = 24 BPM
        assert get_minimum_bpm(2, 20.0) == 24

    def test_4_bars(self):
        """Test minimum BPM for 4 bars"""
        # 4 bars * 4 beats * 60s / 20s = 48 BPM
        assert get_minimum_bpm(4, 20.0) == 48

    def test_8_bars(self):
        """Test minimum BPM for 8 bars"""
        # 8 bars * 4 beats * 60s / 20s = 96 BPM
        assert get_minimum_bpm(8, 20.0) == 96

    def test_constants_match(self):
        """Test that module constants match calculated values"""
        assert MIN_BPM_2_BARS == 24
        assert MIN_BPM_4_BARS == 48
        assert MIN_BPM_8_BARS == 96

    def test_custom_limit(self):
        """Test with custom time limit (10s instead of 20s)"""
        # 4 bars at 10s limit -> min BPM = 96
        assert get_minimum_bpm(4, 10.0) == 96

    def test_invalid_zero_bars(self):
        """Test that zero bars raises error"""
        with pytest.raises(ValueError):
            get_minimum_bpm(0, 20.0)

    def test_invalid_zero_seconds(self):
        """Test that zero seconds raises error"""
        with pytest.raises(ValueError):
            get_minimum_bpm(4, 0.0)


class TestIntegration:
    """Integration tests combining multiple functions"""

    def test_round_trip_calculation(self):
        """Test that calculations are consistent"""
        bpm = 128
        bars = 4
        sample_rate = 48000

        # Calculate duration
        duration = compute_chunk_duration_seconds(bpm, bars)
        # Calculate samples
        samples = compute_samples_per_chunk(bpm, bars, sample_rate)

        # Verify samples matches duration * sample_rate
        expected_samples = round(duration * sample_rate)
        assert samples == expected_samples

    def test_all_standard_combinations(self):
        """Test all standard bar lengths are valid at reasonable BPMs"""
        # Use BPMs that are safe for all bar lengths
        # 8 bars requires BPM >= 96, so start at 100
        standard_bpms = [100, 120, 140, 160, 180]
        standard_bars = [2, 4, 8]

        for bpm in standard_bpms:
            for bars in standard_bars:
                is_valid, msg = is_valid_for_sampler(bpm, bars)
                # All these combinations should be valid (well under 20s)
                assert is_valid, f"Expected valid: {bars} bars @ {bpm} BPM, but got: {msg}"
