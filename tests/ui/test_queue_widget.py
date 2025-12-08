"""
Tests for QueueWidget

PURPOSE: Verify task queue management and batch processing.
CONTEXT: Tests queue widget with mocked separation tasks.
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from ui.widgets.queue_widget import QueueWidget, TaskStatus, QueueTask
from core.separator import SeparationResult


@pytest.mark.unit
def test_queue_widget_creation(qapp, reset_singletons):
    """Test that queue widget can be created"""
    widget = QueueWidget()

    assert widget is not None
    assert widget.queue_table is not None
    assert widget.btn_start is not None
    assert len(widget.tasks) == 0


@pytest.mark.unit
def test_queue_widget_add_task(qapp, reset_singletons, mock_audio_file):
    """Test adding task to queue"""
    widget = QueueWidget()

    # Add task
    widget.add_task(mock_audio_file, "demucs_4s")

    # Task should be added
    assert len(widget.tasks) == 1
    assert widget.tasks[0].file_path == mock_audio_file
    assert widget.tasks[0].model_id == "demucs_4s"
    assert widget.tasks[0].status == TaskStatus.PENDING

    # Table should have one row
    assert widget.queue_table.rowCount() == 1

    # Start button should be enabled
    assert widget.btn_start.isEnabled()


@pytest.mark.unit
def test_queue_widget_add_multiple_tasks(qapp, reset_singletons, tmp_path):
    """Test adding multiple tasks"""
    widget = QueueWidget()

    # Add multiple tasks
    for i in range(3):
        file_path = tmp_path / f"file_{i}.wav"
        file_path.touch()
        widget.add_task(file_path, "demucs_4s")

    assert len(widget.tasks) == 3
    assert widget.queue_table.rowCount() == 3


@pytest.mark.unit
def test_queue_widget_clear_queue(qapp, reset_singletons, mock_audio_file):
    """Test clearing the queue"""
    widget = QueueWidget()

    # Add tasks
    widget.add_task(mock_audio_file, "demucs_4s")
    assert len(widget.tasks) == 1

    # Clear with confirmation
    with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
        from PySide6.QtWidgets import QMessageBox

        mock_question.return_value = QMessageBox.Yes

        widget._on_clear_queue()

    # Queue should be empty
    assert len(widget.tasks) == 0
    assert widget.queue_table.rowCount() == 0


@pytest.mark.unit
def test_queue_widget_remove_task(qapp, reset_singletons, mock_audio_file):
    """Test removing a specific task"""
    widget = QueueWidget()

    # Add tasks
    widget.add_task(mock_audio_file, "demucs_4s")
    widget.add_task(mock_audio_file, "bs-roformer")
    assert len(widget.tasks) == 2

    # Select first task
    widget.queue_table.selectRow(0)

    # Remove it
    widget._on_remove_selected()

    # Should have one task left
    assert len(widget.tasks) == 1
    assert widget.queue_table.rowCount() == 1


@pytest.mark.unit
def test_queue_widget_task_progress(qapp, reset_singletons, mock_audio_file):
    """Test task progress updates"""
    widget = QueueWidget()

    # Add task
    widget.add_task(mock_audio_file, "demucs_4s")

    # Simulate progress update
    widget._on_task_progress(0, "Processing...", 50)

    # Task progress should be updated
    assert widget.tasks[0].progress == 50

    # Progress bar should show 50%
    progress_bar = widget.queue_table.cellWidget(0, 3)
    assert progress_bar.value() == 50


@pytest.mark.unit
def test_queue_widget_task_completed(qapp, reset_singletons, mock_audio_file, tmp_path):
    """Test task completion"""
    widget = QueueWidget()

    # Add task
    widget.add_task(mock_audio_file, "demucs_4s")

    # Create successful result
    result = SeparationResult(
        success=True,
        input_file=mock_audio_file,
        output_dir=tmp_path,
        stems={"vocals": tmp_path / "vocals.wav"},
        model_used="demucs_4s",
        device_used="cpu",
        duration_seconds=1.0,
    )

    # Simulate completion
    widget._on_task_finished(0, result)

    # Task should be completed
    assert widget.tasks[0].status == TaskStatus.COMPLETED
    assert widget.tasks[0].progress == 100
    assert widget.tasks[0].result == result


@pytest.mark.unit
def test_queue_widget_task_failed(qapp, reset_singletons, mock_audio_file):
    """Test task failure"""
    widget = QueueWidget()

    # Add task
    widget.add_task(mock_audio_file, "demucs_4s")

    # Simulate error
    widget._on_task_error(0, "Test error")

    # Task should be failed
    assert widget.tasks[0].status == TaskStatus.FAILED
    assert widget.tasks[0].error_message == "Test error"


@pytest.mark.unit
def test_queue_widget_update_status(qapp, reset_singletons, mock_audio_file):
    """Test status label updates"""
    widget = QueueWidget()

    # Empty queue
    widget._update_status()
    assert "empty" in widget.status_label.text().lower()

    # Add task
    widget.add_task(mock_audio_file, "demucs_4s")
    widget._update_status()

    # Status should show task count
    assert (
        "1 tasks" in widget.status_label.text()
        or "1 task" in widget.status_label.text()
    )


@pytest.mark.unit
@patch("ui.widgets.queue_widget.QueueWorker")
def test_queue_widget_start_processing(
    mock_worker_class, qapp, reset_singletons, mock_audio_file
):
    """Test starting queue processing"""
    mock_worker = Mock()
    mock_worker_class.return_value = mock_worker

    widget = QueueWidget()

    # Add tasks
    widget.add_task(mock_audio_file, "demucs_4s")

    # Start queue
    widget._on_start_queue()

    # Worker should have been created
    mock_worker_class.assert_called_once()

    # Processing flag should be set
    assert widget.is_processing
    assert not widget.btn_start.isEnabled()
    assert widget.btn_stop.isEnabled()
