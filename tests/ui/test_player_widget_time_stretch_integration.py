"""
End-to-End Integration Tests for Time-Stretching Integration

Test Coverage:
- Full user workflows
- Toggle between normal and stretched playback
- Multiple loops processing
- State persistence
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt

from ui.widgets.player_widget import PlayerWidget


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def integration_test_audio_files():
    """Create test audio files for integration tests"""
    temp_dir = Path(tempfile.mkdtemp())

    sample_rate = 44100
    duration = 2.0  # 2 seconds
    samples = int(sample_rate * duration)

    # Create stems
    t = np.linspace(0, duration, samples)
    drums = np.sin(2 * np.pi * 220 * t)
    drums_stereo = np.column_stack([drums, drums])
    
    vocals = np.sin(2 * np.pi * 440 * t)
    vocals_stereo = np.column_stack([vocals, vocals])

    drums_file = temp_dir / "test_(Drums)_model.wav"
    vocals_file = temp_dir / "test_(Vocals)_model.wav"

    sf.write(str(drums_file), drums_stereo, sample_rate)
    sf.write(str(vocals_file), vocals_stereo, sample_rate)

    yield temp_dir, [drums_file, vocals_file]

    shutil.rmtree(temp_dir)


@pytest.fixture
def integration_widget(qtbot, integration_test_audio_files):
    """Create widget with stems and loops for integration tests"""
    with patch("core.player.AudioPlayer._import_rtmixer"):
        widget = PlayerWidget()
        qtbot.addWidget(widget)
        
        temp_dir, file_paths = integration_test_audio_files
        widget._load_stems(file_paths)
        
        # Simulate detected loops
        widget.detected_loop_segments = [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0)]
        widget.detected_intro_loops = []
        widget.detected_bpm = 120.0
        
        return widget


# ============================================================================
# End-to-End Integration Tests
# ============================================================================

@pytest.mark.integration
class TestTimeStretchIntegration:
    """End-to-end integration tests for time-stretching"""

    @patch("core.player.AudioPlayer._import_rtmixer")
    @patch("core.background_stretch_manager.BackgroundStretchManager")
    @patch("sounddevice.play")
    def test_full_workflow_enable_process_play(self, mock_sd_play, mock_manager_class, mock_rtmixer, qtbot, integration_widget):
        """Test full workflow: Enable → Set BPM → Process → Play stretched loop"""
        widget = integration_widget
        
        # Step 1: Enable time-stretching
        widget.time_stretch_checkbox.setChecked(True)
        widget._on_time_stretch_enabled_changed(True)
        assert widget.time_stretch_enabled is True
        
        # Step 2: Set target BPM
        widget.target_bpm_spin.setValue(140)
        widget._on_target_bpm_changed(140)
        assert widget.time_stretch_target_bpm == 140
        
        # Step 3: Start processing
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        widget._on_start_stretch_processing_clicked()
        assert widget.stretch_manager is not None
        mock_manager.start_batch.assert_called_once()
        
        # Step 4: Simulate processing completion
        widget.stretch_manager = mock_manager
        mock_audio = np.random.rand(22050, 2).astype(np.float32)
        mock_manager.get_stretched_loop.return_value = mock_audio
        
        # Step 5: Select loop and play
        widget.selected_loop_index = 0
        widget._on_play_loop_clicked()
        
        # Verify stretched playback was used
        mock_sd_play.assert_called_once()

    @patch("core.player.AudioPlayer._import_rtmixer")
    @patch("core.background_stretch_manager.BackgroundStretchManager")
    @patch("sounddevice.play")
    @patch("core.player.AudioPlayer.play_loop_segment")
    def test_toggle_workflow_normal_to_stretched(self, mock_normal_play, mock_sd_play, mock_manager_class, mock_rtmixer, qtbot, integration_widget):
        """Test toggle workflow: Enable → Process → Play stretched → Disable → Play normal"""
        widget = integration_widget
        widget.selected_loop_index = 0
        
        # Enable and process
        widget.time_stretch_enabled = True
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_audio = np.random.rand(22050, 2).astype(np.float32)
        mock_manager.get_stretched_loop.return_value = mock_audio
        widget.stretch_manager = mock_manager
        
        # Play stretched
        widget._on_play_loop_clicked()
        mock_sd_play.assert_called_once()
        mock_normal_play.assert_not_called()
        
        # Disable time-stretching
        widget.time_stretch_enabled = False
        
        # Play normal
        mock_sd_play.reset_mock()
        widget._on_play_loop_clicked()
        mock_normal_play.assert_called_once()
        mock_sd_play.assert_not_called()

    @patch("core.player.AudioPlayer._import_rtmixer")
    @patch("core.background_stretch_manager.BackgroundStretchManager")
    @patch("sounddevice.play")
    def test_multiple_loops_processing(self, mock_sd_play, mock_manager_class, mock_rtmixer, qtbot, integration_widget):
        """Test processing all loops and playing different loops"""
        widget = integration_widget
        widget.time_stretch_enabled = True
        
        # Process all loops
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        widget._on_start_stretch_processing_clicked()
        
        # Mock different audio for different loops
        mock_manager.get_stretched_loop = MagicMock(side_effect=lambda stem, idx, bpm: np.random.rand(22050, 2).astype(np.float32))
        widget.stretch_manager = mock_manager
        
        # Play different loops
        for loop_idx in range(len(widget.detected_loop_segments)):
            widget.selected_loop_index = loop_idx
            widget._on_play_loop_clicked()
        
        # Should have called sounddevice for each loop
        assert mock_sd_play.call_count == len(widget.detected_loop_segments)

    @patch("core.player.AudioPlayer._import_rtmixer")
    @patch("core.background_stretch_manager.BackgroundStretchManager")
    @patch("sounddevice.play")
    def test_repeat_mode_with_stretched_loops(self, mock_sd_play, mock_manager_class, mock_rtmixer, qtbot, integration_widget):
        """Test repeat mode with stretched loops"""
        widget = integration_widget
        widget.time_stretch_enabled = True
        widget.selected_loop_index = 0
        
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_audio = np.random.rand(22050, 2).astype(np.float32)
        mock_manager.get_stretched_loop.return_value = mock_audio
        widget.stretch_manager = mock_manager
        
        widget._on_play_loop_repeat_clicked()
        
        # Verify sounddevice was called
        mock_sd_play.assert_called_once()
        # Verify repeat mode (should have more samples)
        call_args = mock_sd_play.call_args
        audio_data = call_args[0][0]
        assert len(audio_data) > 22050  # Should be repeated

    @patch("core.player.AudioPlayer._import_rtmixer")
    def test_state_persistence_across_tab_switches(self, mock_rtmixer, qtbot, integration_widget):
        """Test that time-stretch state persists across tab switches"""
        widget = integration_widget
        
        # Enable time-stretching and set target BPM via UI
        widget.time_stretch_checkbox.setChecked(True)
        widget._on_time_stretch_enabled_changed(True)
        widget.target_bpm_spin.setValue(140)
        widget._on_target_bpm_changed(140)
        
        # Switch tabs
        widget.set_page(0)  # Stems
        widget.set_page(1)  # Playback
        widget.set_page(2)  # Looping
        
        # State should be preserved
        assert widget.time_stretch_enabled is True
        assert widget.time_stretch_target_bpm == 140
        assert widget.target_bpm_spin.value() == 140
