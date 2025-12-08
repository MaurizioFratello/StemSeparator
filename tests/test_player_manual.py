#!/usr/bin/env python3
"""
Manual test script for AudioPlayer with rtmixer
Run without pytest-qt dependency
"""
import sys
import tempfile
import shutil
from pathlib import Path
import numpy as np
import soundfile as sf

# Add project to path
sys.path.insert(0, "/home/user/StemSeparator")

from core.player import AudioPlayer, PlaybackState, StemSettings, get_player


def create_test_audio_files():
    """Create temporary test audio files"""
    temp_dir = Path(tempfile.mkdtemp())

    # Create test stems (2 seconds each, stereo, 44100 Hz)
    sample_rate = 44100
    duration = 2.0
    samples = int(sample_rate * duration)

    # Vocals - 440 Hz sine wave
    t = np.linspace(0, duration, samples)
    vocals = np.sin(2 * np.pi * 440 * t)
    vocals_stereo = np.column_stack([vocals, vocals])

    # Bass - 110 Hz sine wave
    bass = np.sin(2 * np.pi * 110 * t)
    bass_stereo = np.column_stack([bass, bass])

    # Drums - noise
    drums = np.random.randn(samples) * 0.3
    drums_stereo = np.column_stack([drums, drums])

    # Save files
    vocals_file = temp_dir / "vocals.wav"
    bass_file = temp_dir / "bass.wav"
    drums_file = temp_dir / "drums.wav"

    sf.write(str(vocals_file), vocals_stereo, sample_rate)
    sf.write(str(bass_file), bass_stereo, sample_rate)
    sf.write(str(drums_file), drums_stereo, sample_rate)

    return temp_dir, {"vocals": vocals_file, "bass": bass_file, "drums": drums_file}


def test_initialization():
    """Test player initialization"""
    print("TEST: Initialization")
    player = AudioPlayer(sample_rate=48000)

    assert player.sample_rate == 48000, "Sample rate mismatch"
    assert player.state == PlaybackState.STOPPED, "Initial state should be STOPPED"
    assert player.position_samples == 0, "Initial position should be 0"
    assert player.duration_samples == 0, "Initial duration should be 0"
    assert len(player.stems) == 0, "No stems should be loaded"
    assert player.master_volume == 1.0, "Master volume should be 1.0"

    print("  ✓ Player initialized correctly")
    return True


def test_stem_settings():
    """Test StemSettings dataclass"""
    print("TEST: StemSettings")

    # Test defaults
    settings = StemSettings()
    assert settings.volume == 0.75, "Default volume should be 0.75"
    assert settings.is_muted is False, "Default muted should be False"
    assert settings.is_solo is False, "Default solo should be False"

    # Test custom
    settings = StemSettings(volume=0.5, is_muted=True, is_solo=True)
    assert settings.volume == 0.5
    assert settings.is_muted is True
    assert settings.is_solo is True

    print("  ✓ StemSettings work correctly")
    return True


def test_load_stems():
    """Test stem loading"""
    print("TEST: Load stems")
    temp_dir, test_files = create_test_audio_files()

    try:
        player = AudioPlayer()
        success = player.load_stems(test_files)

        assert success is True, "Loading should succeed"
        assert len(player.stems) == 3, "Should have 3 stems loaded"
        assert "vocals" in player.stems, "Vocals stem missing"
        assert "bass" in player.stems, "Bass stem missing"
        assert "drums" in player.stems, "Drums stem missing"

        # Check all stems have same length
        lengths = [audio.shape[1] for audio in player.stems.values()]
        assert len(set(lengths)) == 1, "All stems should have same length"

        # Check duration
        duration = player.get_duration()
        assert duration > 0, "Duration should be positive"
        assert abs(duration - 2.0) < 0.1, f"Duration should be ~2s, got {duration}s"

        # Check settings created
        assert len(player.stem_settings) == 3, "Should have settings for all stems"

        print(f"  ✓ Loaded {len(player.stems)} stems")
        print(f"  ✓ Duration: {duration:.2f}s")
        print(f"  ✓ Sample rate: {player.sample_rate} Hz")

        return True
    finally:
        shutil.rmtree(temp_dir)


def test_position_seeking():
    """Test position seeking"""
    print("TEST: Position seeking")

    player = AudioPlayer(sample_rate=44100)
    player.duration_samples = 88200  # 2 seconds

    # Test basic seeking
    player.set_position(1.5)
    pos = player.get_position()
    assert abs(pos - 1.5) < 0.01, f"Position should be 1.5s, got {pos}s"

    # Test clamping at start
    player.set_position(-1.0)
    pos = player.get_position()
    assert pos == 0.0, f"Position should be clamped to 0.0, got {pos}s"

    # Test clamping at end
    player.set_position(10.0)
    pos = player.get_position()
    assert abs(pos - 2.0) < 0.01, f"Position should be clamped to 2.0s, got {pos}s"

    print("  ✓ Position seeking works correctly")
    return True


def test_volume_controls():
    """Test volume controls"""
    print("TEST: Volume controls")
    temp_dir, test_files = create_test_audio_files()

    try:
        player = AudioPlayer()
        player.load_stems(test_files)

        # Test stem volume
        player.set_stem_volume("vocals", 0.5)
        assert player.stem_settings["vocals"].volume == 0.5, "Stem volume should be 0.5"

        # Test volume clamping
        player.set_stem_volume("vocals", 1.5)
        assert (
            player.stem_settings["vocals"].volume == 1.0
        ), "Volume should be clamped to 1.0"

        player.set_stem_volume("vocals", -0.5)
        assert (
            player.stem_settings["vocals"].volume == 0.0
        ), "Volume should be clamped to 0.0"

        # Test mute
        player.set_stem_mute("bass", True)
        assert player.stem_settings["bass"].is_muted is True, "Bass should be muted"

        # Test solo
        player.set_stem_solo("drums", True)
        assert player.stem_settings["drums"].is_solo is True, "Drums should be solo"

        # Test master volume
        player.set_master_volume(0.7)
        assert player.master_volume == 0.7, "Master volume should be 0.7"

        print("  ✓ Volume controls work correctly")
        return True
    finally:
        shutil.rmtree(temp_dir)


def test_mixing():
    """Test stem mixing"""
    print("TEST: Stem mixing")
    temp_dir, test_files = create_test_audio_files()

    try:
        player = AudioPlayer()
        player.load_stems(test_files)

        # Test basic mixing
        mixed = player._mix_stems(0, 44100)

        assert mixed.shape == (
            2,
            44100,
        ), f"Mixed shape should be (2, 44100), got {mixed.shape}"
        assert (
            mixed.dtype == np.float32
        ), f"Mixed dtype should be float32, got {mixed.dtype}"
        assert np.max(np.abs(mixed)) <= 1.0, "Mixed audio should be clipped to [-1, 1]"

        # Test mixing with mute
        player.set_stem_mute("bass", True)
        player.set_stem_mute("drums", True)
        mixed_muted = player._mix_stems(0, 44100)

        # Should only contain vocals
        expected = player.stems["vocals"][:, :44100] * 0.75  # default volume
        np.testing.assert_array_almost_equal(mixed_muted, expected, decimal=5)

        print("  ✓ Stem mixing works correctly")
        return True
    finally:
        shutil.rmtree(temp_dir)


def test_export():
    """Test audio export"""
    print("TEST: Audio export")
    temp_dir, test_files = create_test_audio_files()
    output_file = Path(tempfile.mktemp(suffix=".wav"))

    try:
        player = AudioPlayer()
        player.load_stems(test_files)

        # Export
        success = player.export_mix(output_file)

        assert success is True, "Export should succeed"
        assert output_file.exists(), "Output file should exist"

        # Verify exported file
        data, sr = sf.read(str(output_file))
        assert (
            sr == player.sample_rate
        ), f"Sample rate mismatch: {sr} vs {player.sample_rate}"
        assert data.shape[1] == 2, f"Should be stereo, got {data.shape[1]} channels"
        assert abs(data.shape[0] / sr - 2.0) < 0.1, "Duration should be ~2s"

        print("  ✓ Audio export works correctly")
        return True
    finally:
        shutil.rmtree(temp_dir)
        if output_file.exists():
            output_file.unlink()


def test_singleton():
    """Test get_player singleton"""
    print("TEST: Singleton pattern")

    player1 = get_player()
    player2 = get_player()

    assert player1 is player2, "get_player should return same instance"
    assert isinstance(player1, AudioPlayer), "Should return AudioPlayer instance"

    print("  ✓ Singleton pattern works correctly")
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("TESTING AUDIOPLAYER WITH RTMIXER")
    print("=" * 60)

    tests = [
        test_initialization,
        test_stem_settings,
        test_load_stems,
        test_position_seeking,
        test_volume_controls,
        test_mixing,
        test_export,
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

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
