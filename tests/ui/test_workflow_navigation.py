"""Workflow navigation tests."""

from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


@pytest.fixture
def main_window(qtbot, reset_singletons):
    with patch("ui.main_window.get_app_context") as get_context:
        context = get_context.return_value
        context.translate.side_effect = lambda _key, fallback="", **_kwargs: fallback
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_navigation_upload_to_queue(main_window, qtbot):
    with patch.object(main_window._queue_widget, "start_processing") as start_processing:
        main_window._upload_widget.start_queue_requested.emit()

    assert main_window._content_stack.currentIndex() == 2
    assert main_window._btn_queue.isChecked()
    start_processing.assert_called_once()


def test_navigation_manual_clicks(main_window, qtbot):
    qtbot.mouseClick(main_window._btn_record, Qt.LeftButton)
    assert main_window._content_stack.currentIndex() == 1
    assert main_window._btn_record.isChecked()

    qtbot.mouseClick(main_window._btn_playback, Qt.LeftButton)
    assert main_window._content_stack.currentIndex() == 3
    assert main_window._btn_playback.isChecked()
    assert main_window._player_widget.get_current_page() == 1


def test_recording_saved_navigation(main_window, tmp_path):
    recording = tmp_path / "test_rec.wav"
    sf.write(recording, np.zeros((100, 2)), 44100)

    main_window._recording_widget.recording_saved.emit(recording)

    assert main_window._content_stack.currentIndex() == 0
    assert main_window._btn_upload.isChecked()
    selected_item = main_window._upload_widget.file_list.currentItem()
    assert selected_item.data(Qt.UserRole) == recording
