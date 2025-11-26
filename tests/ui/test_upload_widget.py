"""
Tests for UploadWidget

PURPOSE: Verify file upload, model selection, and separation triggering.
CONTEXT: Tests upload widget functionality with mocked separation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PySide6.QtCore import Qt

from ui.widgets.upload_widget import UploadWidget, SeparationWorker
from core.separator import SeparationResult


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
    
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        widget._add_file(invalid_file)
        
        # Should show warning
        mock_warning.assert_called_once()
    
    # File should not be added
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
    widget.file_queued.connect(lambda f, m, ue, ec: signal_emitted.append((f, m, ue, ec)))

    # Click queue button
    widget._on_queue_clicked()

    # Signal should have been emitted
    assert len(signal_emitted) == 1
    file_path, model_id, use_ensemble, ensemble_config = signal_emitted[0]
    assert file_path == mock_audio_file
    assert model_id is not None
    assert use_ensemble == False  # Default should be False
    assert ensemble_config == ''  # Default should be empty


@pytest.mark.unit
@patch('ui.widgets.upload_widget.SeparationWorker')
def test_upload_widget_start_separation(mock_worker_class, qapp, reset_singletons, mock_audio_file):
    """Test starting separation"""
    # Setup mock worker
    mock_worker = Mock()
    mock_worker_class.return_value = mock_worker
    
    widget = UploadWidget()
    
    # Add file and select it
    widget._add_file(mock_audio_file)
    widget.file_list.setCurrentRow(0)
    
    # Start separation
    widget._on_start_clicked()
    
    # Worker should have been created
    mock_worker_class.assert_called_once()
    
    # Start button should be disabled during processing
    assert not widget.btn_start.isEnabled()
    assert not widget.progress_bar.isHidden()


@pytest.mark.unit
def test_separation_worker_signals(qapp, reset_singletons, mock_audio_file):
    """Test that separation worker has proper signals"""
    worker = SeparationWorker(mock_audio_file, "demucs_4s")
    
    assert worker.signals is not None
    assert hasattr(worker.signals, 'progress')
    assert hasattr(worker.signals, 'finished')
    assert hasattr(worker.signals, 'error')


@pytest.mark.unit
def test_upload_widget_separation_progress(qapp, reset_singletons):
    """Test progress updates during separation"""
    widget = UploadWidget()
    
    # Simulate progress update
    widget._on_separation_progress("Processing...", 50)
    
    # Progress should be updated
    assert widget.progress_bar.value() == 50
    assert "Processing" in widget.status_label.text()


@pytest.mark.unit
def test_upload_widget_separation_success(qapp, reset_singletons, mock_audio_file, tmp_path):
    """Test successful separation completion"""
    widget = UploadWidget()
    
    # Create mock result
    result = SeparationResult(
        success=True,
        input_file=mock_audio_file,
        output_dir=tmp_path,
        stems={'vocals': tmp_path / 'vocals.wav'},
        model_used='demucs_4s',
        device_used='cpu',
        duration_seconds=1.0
    )
    
    with patch('PySide6.QtWidgets.QMessageBox.information') as mock_info:
        widget._on_separation_finished(result)
        
        # Should show success message
        mock_info.assert_called_once()
    
    # Controls should be re-enabled
    assert widget.btn_start.isEnabled()


@pytest.mark.unit
def test_upload_widget_separation_error(qapp, reset_singletons):
    """Test error handling during separation"""
    widget = UploadWidget()
    
    with patch('PySide6.QtWidgets.QMessageBox.critical') as mock_error:
        widget._on_separation_error("Test error message")
        
        # Should show error dialog
        mock_error.assert_called_once()
    
    # Controls should be re-enabled
    assert widget.btn_start.isEnabled()
    assert not widget.progress_bar.isVisible()

