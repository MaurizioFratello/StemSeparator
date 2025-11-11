"""
Unit Tests for Audio Player
"""
import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from core.player import (
    AudioPlayer,
    PlaybackState,
    StemSettings,
    PlaybackInfo,
    get_player
)


@pytest.fixture
def test_audio_files():
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

    yield {
        'vocals': vocals_file,
        'bass': bass_file,
        'drums': drums_file
    }

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_soundcard():
    """Mock soundcard module"""
    with patch('core.player.logger') as mock_logger:
        player = AudioPlayer()
        # Mock soundcard
        mock_sc = MagicMock()
        mock_speaker = MagicMock()
        mock_sc.default_speaker.return_value = mock_speaker
        player._soundcard = mock_sc
        yield player, mock_speaker


@pytest.mark.unit
class TestStemSettings:
    """Tests for StemSettings dataclass"""

    def test_stem_settings_defaults(self):
        """Test default stem settings"""
        settings = StemSettings()

        assert settings.volume == 0.75
        assert settings.is_muted is False
        assert settings.is_solo is False

    def test_stem_settings_custom(self):
        """Test custom stem settings"""
        settings = StemSettings(volume=0.5, is_muted=True, is_solo=True)

        assert settings.volume == 0.5
        assert settings.is_muted is True
        assert settings.is_solo is True


@pytest.mark.unit
class TestAudioPlayer:
    """Tests for AudioPlayer"""

    def test_initialization(self):
        """Test player initialization"""
        player = AudioPlayer(sample_rate=48000)

        assert player.sample_rate == 48000
        assert player.state == PlaybackState.STOPPED
        assert player.position_samples == 0
        assert player.duration_samples == 0
        assert len(player.stems) == 0
        assert player.master_volume == 1.0

    def test_load_stems_success(self, test_audio_files):
        """Test successful stem loading"""
        player = AudioPlayer()
        success = player.load_stems(test_audio_files)

        assert success is True
        assert len(player.stems) == 3
        assert 'vocals' in player.stems
        assert 'bass' in player.stems
        assert 'drums' in player.stems

        # Check all stems have same length
        lengths = [audio.shape[1] for audio in player.stems.values()]
        assert len(set(lengths)) == 1  # All same length

        # Check duration
        assert player.get_duration() > 0
        assert abs(player.get_duration() - 2.0) < 0.1  # ~2 seconds

    def test_load_stems_empty(self):
        """Test loading empty stem dict"""
        player = AudioPlayer()
        success = player.load_stems({})

        assert success is False
        assert len(player.stems) == 0

    def test_load_stems_creates_settings(self, test_audio_files):
        """Test that loading stems creates settings"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        assert len(player.stem_settings) == 3
        assert all(isinstance(s, StemSettings) for s in player.stem_settings.values())

    def test_load_stems_padding(self, test_audio_files):
        """Test that stems are padded to same length"""
        # Create a shorter stem
        temp_dir = test_audio_files['vocals'].parent
        short_file = temp_dir / "short.wav"

        # Create 1 second file
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, duration, samples))
        stereo = np.column_stack([audio, audio])
        sf.write(str(short_file), stereo, sample_rate)

        # Load with other stems
        stems = test_audio_files.copy()
        stems['short'] = short_file

        player = AudioPlayer()
        player.load_stems(stems)

        # All should have same length
        lengths = [audio.shape[1] for audio in player.stems.values()]
        assert len(set(lengths)) == 1

    def test_get_position(self):
        """Test get position"""
        player = AudioPlayer(sample_rate=44100)
        player.duration_samples = 88200  # 2 seconds
        player.position_samples = 44100  # 1 second

        assert abs(player.get_position() - 1.0) < 0.01

    def test_set_position(self):
        """Test set position"""
        player = AudioPlayer(sample_rate=44100)
        player.duration_samples = 88200  # 2 seconds

        player.set_position(1.5)
        assert abs(player.get_position() - 1.5) < 0.01

        # Test clamping
        player.set_position(-1.0)
        assert player.get_position() == 0.0

        player.set_position(10.0)
        assert abs(player.get_position() - 2.0) < 0.01

    def test_set_stem_volume(self, test_audio_files):
        """Test set stem volume"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        player.set_stem_volume('vocals', 0.5)
        assert player.stem_settings['vocals'].volume == 0.5

        # Test clamping
        player.set_stem_volume('vocals', 1.5)
        assert player.stem_settings['vocals'].volume == 1.0

        player.set_stem_volume('vocals', -0.5)
        assert player.stem_settings['vocals'].volume == 0.0

    def test_set_stem_mute(self, test_audio_files):
        """Test set stem mute"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        player.set_stem_mute('vocals', True)
        assert player.stem_settings['vocals'].is_muted is True

        player.set_stem_mute('vocals', False)
        assert player.stem_settings['vocals'].is_muted is False

    def test_set_stem_solo(self, test_audio_files):
        """Test set stem solo"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        player.set_stem_solo('vocals', True)
        assert player.stem_settings['vocals'].is_solo is True

        player.set_stem_solo('vocals', False)
        assert player.stem_settings['vocals'].is_solo is False

    def test_set_master_volume(self):
        """Test set master volume"""
        player = AudioPlayer()

        player.set_master_volume(0.7)
        assert player.master_volume == 0.7

        # Test clamping
        player.set_master_volume(1.5)
        assert player.master_volume == 1.0

        player.set_master_volume(-0.5)
        assert player.master_volume == 0.0

    def test_mix_stems_basic(self, test_audio_files):
        """Test basic stem mixing"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        # Mix 1 second (44100 samples)
        mixed = player._mix_stems(0, 44100)

        assert mixed.shape == (2, 44100)  # stereo
        assert mixed.dtype == np.float32
        assert np.max(np.abs(mixed)) <= 1.0  # clipped

    def test_mix_stems_with_mute(self, test_audio_files):
        """Test mixing with muted stem"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        # Mute all but vocals
        player.set_stem_mute('bass', True)
        player.set_stem_mute('drums', True)

        mixed = player._mix_stems(0, 44100)

        # Should only contain vocals (scaled by volume)
        expected = player.stems['vocals'][:, :44100] * 0.75  # default volume
        np.testing.assert_array_almost_equal(mixed, expected, decimal=5)

    def test_mix_stems_with_solo(self, test_audio_files):
        """Test mixing with solo stem"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        # Solo vocals
        player.set_stem_solo('vocals', True)

        mixed = player._mix_stems(0, 44100)

        # Should only contain vocals
        expected = player.stems['vocals'][:, :44100] * 0.75  # default volume
        np.testing.assert_array_almost_equal(mixed, expected, decimal=5)

    def test_mix_stems_master_volume(self, test_audio_files):
        """Test mixing with master volume"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        player.set_master_volume(0.5)

        mixed = player._mix_stems(0, 44100)

        # Check that master volume is applied
        # (exact values depend on mixing, but should be scaled)
        assert np.max(np.abs(mixed)) <= 0.5

    def test_play_without_stems(self, mock_soundcard):
        """Test play without loaded stems"""
        player, _ = mock_soundcard
        success = player.play()

        assert success is False
        assert player.state == PlaybackState.STOPPED

    def test_play_with_stems(self, mock_soundcard, test_audio_files):
        """Test play with loaded stems"""
        player, mock_speaker = mock_soundcard
        player.load_stems(test_audio_files)

        success = player.play()

        assert success is True
        assert player.state == PlaybackState.PLAYING
        assert player.playback_thread is not None

        # Stop immediately
        player.stop()

    def test_pause(self, mock_soundcard, test_audio_files):
        """Test pause"""
        player, _ = mock_soundcard
        player.load_stems(test_audio_files)

        player.play()
        player.pause()

        assert player.state == PlaybackState.PAUSED

        player.stop()

    def test_stop(self, mock_soundcard, test_audio_files):
        """Test stop"""
        player, _ = mock_soundcard
        player.load_stems(test_audio_files)

        player.play()
        player.stop()

        assert player.state == PlaybackState.STOPPED
        assert player.position_samples == 0

    def test_resume_from_pause(self, mock_soundcard, test_audio_files):
        """Test resume from pause"""
        player, _ = mock_soundcard
        player.load_stems(test_audio_files)

        player.play()
        player.pause()
        success = player.play()

        assert success is True
        assert player.state == PlaybackState.PLAYING

        player.stop()

    def test_callbacks(self, mock_soundcard, test_audio_files):
        """Test position and state callbacks"""
        player, _ = mock_soundcard
        player.load_stems(test_audio_files)

        position_calls = []
        state_calls = []

        def position_cb(pos, dur):
            position_calls.append((pos, dur))

        def state_cb(state):
            state_calls.append(state)

        player.position_callback = position_cb
        player.state_callback = state_cb

        player.play()
        player.stop()

        # State callback should have been called
        assert len(state_calls) > 0
        assert PlaybackState.PLAYING in state_calls

    def test_export_mix(self, test_audio_files):
        """Test export mixed audio"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        # Export to temp file
        output_file = Path(tempfile.mktemp(suffix='.wav'))

        try:
            success = player.export_mix(output_file)

            assert success is True
            assert output_file.exists()

            # Verify exported file
            data, sr = sf.read(str(output_file))
            assert sr == player.sample_rate
            assert data.shape[1] == 2  # stereo
            assert abs(data.shape[0] / sr - 2.0) < 0.1  # ~2 seconds

        finally:
            if output_file.exists():
                output_file.unlink()

    def test_export_mix_without_stems(self):
        """Test export without loaded stems"""
        player = AudioPlayer()
        output_file = Path(tempfile.mktemp(suffix='.wav'))

        success = player.export_mix(output_file)

        assert success is False
        assert not output_file.exists()

    def test_cleanup(self, test_audio_files):
        """Test cleanup"""
        player = AudioPlayer()
        player.load_stems(test_audio_files)

        player.cleanup()

        assert len(player.stems) == 0
        assert len(player.stem_settings) == 0
        assert player.state == PlaybackState.STOPPED

    def test_singleton(self):
        """Test get_player singleton"""
        player1 = get_player()
        player2 = get_player()

        assert player1 is player2
        assert isinstance(player1, AudioPlayer)
