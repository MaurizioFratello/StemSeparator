"""
Integration Tests for PlayerWidget
"""
import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtCore import Qt

from ui.widgets.player_widget import PlayerWidget, StemControl
from core.player import PlaybackState


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

    # Save files
    vocals_file = temp_dir / "test_(Vocals)_model.wav"
    bass_file = temp_dir / "test_(Bass)_model.wav"

    sf.write(str(vocals_file), vocals_stereo, sample_rate)
    sf.write(str(bass_file), bass_stereo, sample_rate)

    yield temp_dir, [vocals_file, bass_file]

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.integration
class TestStemControl:
    """Integration tests for StemControl"""

    def test_stem_control_creation(self, qtbot):
        """Test stem control creation"""
        control = StemControl("vocals")
        qtbot.addWidget(control)

        assert control.stem_name == "vocals"
        assert control.is_muted is False
        assert control.is_solo is False
        assert control.volume_slider.value() == 75

    def test_stem_control_mute(self, qtbot):
        """Test mute button"""
        control = StemControl("vocals")
        qtbot.addWidget(control)

        # Track signal
        mute_signal = Mock()
        control.mute_changed.connect(mute_signal)

        # Click mute
        qtbot.mouseClick(control.btn_mute, Qt.LeftButton)

        assert control.is_muted is True
        mute_signal.assert_called_once_with("vocals", True)

    def test_stem_control_solo(self, qtbot):
        """Test solo button"""
        control = StemControl("vocals")
        qtbot.addWidget(control)

        # Track signal
        solo_signal = Mock()
        control.solo_changed.connect(solo_signal)

        # Click solo
        qtbot.mouseClick(control.btn_solo, Qt.LeftButton)

        assert control.is_solo is True
        solo_signal.assert_called_once_with("vocals", True)

    def test_stem_control_volume(self, qtbot):
        """Test volume slider"""
        control = StemControl("vocals")
        qtbot.addWidget(control)

        # Track signal
        volume_signal = Mock()
        control.volume_changed.connect(volume_signal)

        # Change volume
        control.volume_slider.setValue(50)

        volume_signal.assert_called_with("vocals", 50)
        assert control.volume_label.text() == "50%"


@pytest.mark.integration
class TestPlayerWidget:
    """Integration tests for PlayerWidget"""

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_player_widget_initialization(self, mock_soundcard, qtbot):
        """Test player widget initialization"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        assert widget.player is not None
        assert len(widget.stem_controls) == 0
        assert widget.btn_play.isEnabled() is False

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_load_stems_from_files(self, mock_soundcard, qtbot, test_audio_files):
        """Test loading stems from file list"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files

        # Load stems
        widget._load_stems(file_paths)

        # Check UI state
        assert len(widget.stem_controls) == 2
        assert 'Vocals' in widget.stem_controls or 'vocals' in widget.stem_controls
        assert 'Bass' in widget.stem_controls or 'bass' in widget.stem_controls
        assert widget.btn_play.isEnabled() is True
        assert widget.btn_export.isEnabled() is True
        assert widget.position_slider.isEnabled() is True

        # Check player has stems
        assert len(widget.player.stems) == 2

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_load_stems_from_directory(self, mock_soundcard, qtbot, test_audio_files, monkeypatch):
        """Test loading stems from directory"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files

        # Mock QFileDialog
        monkeypatch.setattr(
            'PySide6.QtWidgets.QFileDialog.getExistingDirectory',
            lambda *args, **kwargs: str(temp_dir)
        )

        # Trigger load
        widget._on_load_dir()

        # Check stems loaded
        assert len(widget.stem_controls) >= 2

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_stem_volume_control(self, mock_soundcard, qtbot, test_audio_files):
        """Test stem volume control"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Get first stem name
        stem_name = list(widget.stem_controls.keys())[0]
        control = widget.stem_controls[stem_name]

        # Change volume
        control.volume_slider.setValue(50)

        # Check player received update
        assert widget.player.stem_settings[stem_name].volume == 0.5

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_stem_mute_control(self, mock_soundcard, qtbot, test_audio_files):
        """Test stem mute control"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Get first stem
        stem_name = list(widget.stem_controls.keys())[0]
        control = widget.stem_controls[stem_name]

        # Mute
        qtbot.mouseClick(control.btn_mute, Qt.LeftButton)

        # Check player received update
        assert widget.player.stem_settings[stem_name].is_muted is True

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_stem_solo_control(self, mock_soundcard, qtbot, test_audio_files):
        """Test stem solo control"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Get first stem
        stem_name = list(widget.stem_controls.keys())[0]
        control = widget.stem_controls[stem_name]

        # Solo
        qtbot.mouseClick(control.btn_solo, Qt.LeftButton)

        # Check player received update
        assert widget.player.stem_settings[stem_name].is_solo is True

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_master_volume_control(self, mock_soundcard, qtbot, test_audio_files):
        """Test master volume control"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Change master volume
        widget.master_slider.setValue(70)

        # Check player received update
        assert widget.player.master_volume == 0.7
        assert widget.master_label.text() == "70%"

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_playback_controls_disabled_without_stems(self, mock_soundcard, qtbot):
        """Test playback controls disabled without stems"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        assert widget.btn_play.isEnabled() is False
        assert widget.btn_pause.isEnabled() is False
        assert widget.btn_stop.isEnabled() is False
        assert widget.btn_export.isEnabled() is False

    @patch('core.player.AudioPlayer._import_soundcard')
    @patch('core.player.AudioPlayer.play')
    def test_play_button(self, mock_play, mock_soundcard, qtbot, test_audio_files):
        """Test play button"""
        mock_play.return_value = True

        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Mock soundcard for player
        mock_sc = MagicMock()
        mock_speaker = MagicMock()
        mock_sc.default_speaker.return_value = mock_speaker
        widget.player._soundcard = mock_sc

        # Click play
        qtbot.mouseClick(widget.btn_play, Qt.LeftButton)

        mock_play.assert_called_once()

    @patch('core.player.AudioPlayer._import_soundcard')
    @patch('core.player.AudioPlayer.pause')
    def test_pause_button(self, mock_pause, mock_soundcard, qtbot, test_audio_files):
        """Test pause button"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Set playing state
        widget.player.state = PlaybackState.PLAYING
        widget._on_state_changed(PlaybackState.PLAYING)

        # Click pause
        qtbot.mouseClick(widget.btn_pause, Qt.LeftButton)

        mock_pause.assert_called_once()

    @patch('core.player.AudioPlayer._import_soundcard')
    @patch('core.player.AudioPlayer.stop')
    def test_stop_button(self, mock_stop, mock_soundcard, qtbot, test_audio_files):
        """Test stop button"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Set playing state
        widget.player.state = PlaybackState.PLAYING
        widget._on_state_changed(PlaybackState.PLAYING)

        # Click stop
        qtbot.mouseClick(widget.btn_stop, Qt.LeftButton)

        mock_stop.assert_called_once()
        assert widget.position_slider.value() == 0

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_state_changes_update_buttons(self, mock_soundcard, qtbot):
        """Test state changes update button states"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        # Load stems
        widget.player.duration_samples = 88200
        widget.player.stems = {'test': np.zeros((2, 88200))}
        widget.btn_play.setEnabled(True)

        # Playing state
        widget._on_state_changed(PlaybackState.PLAYING)
        assert widget.btn_play.isEnabled() is False
        assert widget.btn_pause.isEnabled() is True
        assert widget.btn_stop.isEnabled() is True

        # Paused state
        widget._on_state_changed(PlaybackState.PAUSED)
        assert widget.btn_play.isEnabled() is True
        assert widget.btn_pause.isEnabled() is False
        assert widget.btn_stop.isEnabled() is True

        # Stopped state
        widget._on_state_changed(PlaybackState.STOPPED)
        assert widget.btn_play.isEnabled() is True
        assert widget.btn_pause.isEnabled() is False
        assert widget.btn_stop.isEnabled() is False

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_position_slider_seek(self, mock_soundcard, qtbot, test_audio_files):
        """Test seeking with position slider"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Seek to 1 second (1000 ms)
        widget.position_slider.setValue(1000)
        widget._on_slider_released()

        # Check player position
        assert abs(widget.player.get_position() - 1.0) < 0.1

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_time_formatting(self, mock_soundcard, qtbot):
        """Test time formatting"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        assert widget._format_time(0) == "00:00"
        assert widget._format_time(59) == "00:59"
        assert widget._format_time(60) == "01:00"
        assert widget._format_time(125) == "02:05"

    @patch('core.player.AudioPlayer._import_soundcard')
    @patch('core.player.AudioPlayer.export_mix')
    def test_export_mix(self, mock_export, mock_soundcard, qtbot, test_audio_files, monkeypatch):
        """Test export mixed audio"""
        mock_export.return_value = True

        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Mock save dialog
        output_file = temp_dir / "mixed.wav"
        monkeypatch.setattr(
            'PySide6.QtWidgets.QFileDialog.getSaveFileName',
            lambda *args, **kwargs: (str(output_file), "WAV Files (*.wav)")
        )

        # Trigger export
        widget._on_export()

        # Check export was called
        mock_export.assert_called_once()

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_load_separation_result(self, mock_soundcard, qtbot, test_audio_files):
        """Test loading from separation result"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files

        # Create stems dict like separation result
        stems = {
            'Vocals': file_paths[0],
            'Bass': file_paths[1]
        }

        # Load
        widget.load_separation_result(stems)

        # Check loaded
        assert len(widget.stem_controls) == 2

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_cleanup_on_close(self, mock_soundcard, qtbot, test_audio_files):
        """Test cleanup when widget closes"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Mock stop
        with patch.object(widget.player, 'stop') as mock_stop:
            # Close widget
            widget.close()

            mock_stop.assert_called_once()

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_interactive_seeking(self, mock_soundcard, qtbot, test_audio_files):
        """Test interactive seeking with slider"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Simulate slider interaction
        # Press slider
        widget._on_slider_pressed()
        assert widget._user_seeking is True

        # Move slider
        widget.position_slider.setValue(1500)  # 1.5 seconds
        widget._on_slider_moved(1500)
        assert widget.current_time_label.text() == "00:01"

        # Release slider (perform seek)
        widget._on_slider_released()
        assert widget._user_seeking is False
        assert abs(widget.player.get_position() - 1.5) < 0.1

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_seeking_during_playback(self, mock_soundcard, qtbot, test_audio_files):
        """Test that seeking works during playback"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Set playing state
        widget.player.state = PlaybackState.PLAYING
        widget._on_state_changed(PlaybackState.PLAYING)

        # Seek while playing
        widget._on_slider_pressed()
        widget.position_slider.setValue(500)
        widget._on_slider_released()

        # Verify seek happened
        assert abs(widget.player.get_position() - 0.5) < 0.1

    @patch('core.player.AudioPlayer._import_soundcard')
    def test_position_updates_blocked_during_seeking(self, mock_soundcard, qtbot, test_audio_files):
        """Test that automatic position updates don't interfere with seeking"""
        widget = PlayerWidget()
        qtbot.addWidget(widget)

        temp_dir, file_paths = test_audio_files
        widget._load_stems(file_paths)

        # Start seeking
        widget._on_slider_pressed()

        # Simulate position update from timer (should be ignored)
        widget.player.position_samples = 88200  # 2 seconds
        widget._update_position()

        # Slider should not have been updated
        assert widget.position_slider.value() != 2000

        # Finish seeking
        widget._on_slider_released()

        # Now position updates should work
        widget._update_position()
        assert abs(widget.position_slider.value() - 2000) < 100
