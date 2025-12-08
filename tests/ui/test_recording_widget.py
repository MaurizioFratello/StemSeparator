"""
Tests for RecordingWidget

PURPOSE: Verify recording controls, BlackHole status, and state management.
CONTEXT: Tests recording widget with mocked recorder.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from ui.widgets.recording_widget import RecordingWidget
from core.recorder import RecordingState, RecordingInfo
from core.blackhole_installer import BlackHoleStatus


@pytest.mark.unit
def test_recording_widget_creation(qapp, reset_singletons):
    """Test that recording widget can be created"""
    with patch("ui.widgets.recording_widget.RecordingWidget._refresh_devices"):
        widget = RecordingWidget()

        assert widget is not None
        assert widget.btn_start is not None
        assert widget.btn_pause is not None
        assert widget.btn_stop is not None


@pytest.mark.unit
def test_recording_widget_refresh_devices(qapp, reset_singletons):
    """Test device refresh functionality"""
    with patch("core.recorder.Recorder.get_available_devices") as mock_devices:
        mock_devices.return_value = ["Device 1", "Device 2", "BlackHole 2ch"]

        widget = RecordingWidget()
        widget._refresh_devices()

        # Combo should have devices
        assert widget.device_combo.count() == 3


@pytest.mark.unit
def test_recording_widget_start_recording(qapp, reset_singletons):
    """Test starting recording"""
    with patch("core.recorder.Recorder.start_recording") as mock_start:
        mock_start.return_value = True

        widget = RecordingWidget()
        widget.device_combo.addItem("Test Device", userData="test")
        widget.device_combo.setCurrentIndex(0)

        widget._on_start_clicked()

        # Start should have been called
        mock_start.assert_called_once()

        # Buttons should update
        assert not widget.btn_start.isEnabled()
        assert widget.btn_pause.isEnabled()
        assert widget.btn_stop.isEnabled()


@pytest.mark.unit
def test_recording_widget_pause_resume(qapp, reset_singletons):
    """Test pause and resume functionality"""
    with patch("core.recorder.Recorder.get_state") as mock_state:
        with patch("core.recorder.Recorder.pause_recording") as mock_pause:
            with patch("core.recorder.Recorder.resume_recording") as mock_resume:
                mock_pause.return_value = True
                mock_resume.return_value = True

                widget = RecordingWidget()

                # Simulate recording state
                mock_state.return_value = RecordingState.RECORDING
                widget._on_pause_clicked()
                mock_pause.assert_called_once()

                # Simulate paused state
                mock_state.return_value = RecordingState.PAUSED
                widget._on_pause_clicked()
                mock_resume.assert_called_once()


@pytest.mark.unit
def test_recording_widget_stop_recording(qapp, reset_singletons, tmp_path):
    """Test stopping and saving recording"""
    test_file = tmp_path / "recording.wav"

    recording_info = RecordingInfo(
        duration_seconds=5.0,
        sample_rate=44100,
        channels=2,
        file_path=test_file,
        peak_level=0.8,
    )

    with patch("core.recorder.Recorder.stop_recording") as mock_stop:
        mock_stop.return_value = recording_info

        widget = RecordingWidget()

        # Track signal emission
        signal_emitted = []
        widget.recording_saved.connect(lambda p: signal_emitted.append(p))

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            widget._on_stop_clicked()

        # Should have saved
        mock_stop.assert_called_once()

        # Signal should have been emitted
        assert len(signal_emitted) == 1
        assert signal_emitted[0] == test_file


@pytest.mark.unit
def test_recording_widget_cancel_recording(qapp, reset_singletons):
    """Test cancelling recording"""
    with patch("core.recorder.Recorder.cancel_recording") as mock_cancel:
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            from PySide6.QtWidgets import QMessageBox

            mock_question.return_value = QMessageBox.Yes

            widget = RecordingWidget()
            widget._on_cancel_clicked()

            # Cancel should have been called
            mock_cancel.assert_called_once()


@pytest.mark.unit
def test_recording_widget_level_update(qapp, reset_singletons):
    """Test audio level meter updates"""
    widget = RecordingWidget()

    # Simulate level update
    widget._on_level_update(0.5)

    # Level meter should update
    assert widget.level_meter.value() == 50


@pytest.mark.unit
def test_recording_widget_duration_update(qapp, reset_singletons):
    """Test duration display updates"""
    with patch("core.recorder.Recorder.get_recording_duration") as mock_duration:
        with patch("core.recorder.Recorder.get_state") as mock_state:
            mock_duration.return_value = 65.5  # 1 minute 5.5 seconds
            mock_state.return_value = RecordingState.RECORDING

            widget = RecordingWidget()
            widget._update_display()

            # Duration should be formatted
            assert "01:05.5" in widget.duration_label.text()


@pytest.mark.unit
def test_recording_widget_reset_controls(qapp, reset_singletons):
    """Test resetting controls after recording"""
    widget = RecordingWidget()

    widget._reset_controls()

    # Buttons should be in initial state
    assert widget.btn_start.isEnabled()
    assert not widget.btn_pause.isEnabled()
    assert not widget.btn_stop.isEnabled()
    assert not widget.btn_cancel.isEnabled()
    assert widget.level_meter.value() == 0
