"""
Tests for UploadWidget

PURPOSE: Verify file upload, model selection, and separation triggering.
CONTEXT: Tests upload widget functionality with mocked separation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PySide6.QtCore import Qt

from ui.widgets.upload_widget import UploadWidget


@pytest.mark.unit
def test_upload_widget_creation(qapp, reset_singletons):
    """Test that upload widget can be created"""
    widget = UploadWidget()

    assert widget is not None
    assert widget.file_list is not None
    assert widget.model_combo is not None
    assert widget.btn_start is not None


@pytest.mark.unit
def test_upload_widget_has_models(qapp, reset_singletons):
    """Test that model combo box is populated"""
    widget = UploadWidget()

    # Should have models from config
    assert widget.model_combo.count() > 0

    # Each item should have model_id as userData
    for i in range(widget.model_combo.count()):
        model_id = widget.model_combo.itemData(i)
        assert model_id is not None
        assert isinstance(model_id, str)


@pytest.mark.unit
def test_upload_widget_add_file(qapp, reset_singletons, mock_audio_file):
    """Test adding a file to the upload list"""
    widget = UploadWidget()

    # Initially no files
    assert widget.file_list.count() == 0

    # Add file
    widget._add_file(mock_audio_file)

    # File should be added
    assert widget.file_list.count() == 1

    # Button states should update
    assert widget.btn_clear.isEnabled()


@pytest.mark.unit
def test_upload_widget_add_invalid_file(qapp, reset_singletons, tmp_path):
    """Test adding an invalid file shows error"""
    widget = UploadWidget()

    # Create invalid file
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("not an audio file")

    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
        widget._add_file(invalid_file)

        # Should show warning
        mock_warning.assert_called_once()

    # File should be added (the mock is skipped so we rely on file_list count)
    # Actually, if warning is shown, file is not added
    assert widget.file_list.count() == 0


@pytest.mark.unit
def test_upload_widget_clear_files(qapp, reset_singletons, mock_audio_file):
    """Test clearing file list"""
    widget = UploadWidget()

    # Add file
    widget._add_file(mock_audio_file)
    assert widget.file_list.count() == 1

    # Clear
    widget._on_clear_clicked()

    # List should be empty
    assert widget.file_list.count() == 0


@pytest.mark.unit
def test_upload_widget_queue_signal(qapp, reset_singletons, mock_audio_file):
    """Test that queue button emits file_queued signal"""
    widget = UploadWidget()

    # Add file and select it
    widget._add_file(mock_audio_file)
    widget.file_list.setCurrentRow(0)

    # Connect signal spy
    signal_emitted = []
    widget.file_queued.connect(
        lambda f, m, ue, ec: signal_emitted.append((f, m, ue, ec))
    )

    # Click queue button
    widget._on_queue_clicked()

    # Signal should have been emitted
    assert len(signal_emitted) == 1
    file_path, model_id, use_ensemble, ensemble_config = signal_emitted[0]
    assert file_path == mock_audio_file
    assert model_id is not None
    assert use_ensemble == False  # Default should be False
    assert ensemble_config == ""  # Default should be empty


@pytest.mark.unit
def test_upload_widget_start_separation(qapp, reset_singletons, mock_audio_file):
    """Test starting separation via queue"""
    widget = UploadWidget()

    # Add file and select it
    widget._add_file(mock_audio_file)
    widget.file_list.setCurrentRow(0)

    # Connect signals
    queued_signal = []
    start_signal = []
    widget.file_queued.connect(
        lambda f, m, ue, ec: queued_signal.append((f, m, ue, ec))
    )
    widget.start_queue_requested.connect(lambda: start_signal.append(True))

    # Start separation
    widget._on_start_clicked()

    # Should queue file AND request start
    assert len(queued_signal) == 1
    assert len(start_signal) == 1
    assert queued_signal[0][0] == mock_audio_file
