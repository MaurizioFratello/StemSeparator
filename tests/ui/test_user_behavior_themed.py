"""User-visible themed widget behavior."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from ui.widgets.player_widget import PlayerWidget, StemControl
from ui.widgets.queue_widget import QueueWidget
from ui.widgets.recording_widget import RecordingWidget
from ui.widgets.upload_widget import UploadWidget


@pytest.fixture
def main_window(qtbot, reset_singletons):
    with patch("ui.main_window.get_app_context") as get_context:
        context = MagicMock()
        context.translate.side_effect = lambda _key, fallback="", **_kwargs: fallback
        get_context.return_value = context
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_user_can_see_themed_window(main_window):
    assert main_window.width() >= 1400
    assert main_window.height() >= 900


def test_user_can_switch_sidebar_destinations(main_window, qtbot):
    destinations = (
        (main_window._btn_upload, 0),
        (main_window._btn_record, 1),
        (main_window._btn_queue, 2),
        (main_window._btn_stems, 3),
        (main_window._btn_playback, 3),
        (main_window._btn_looping, 3),
    )

    for button, stack_index in destinations:
        qtbot.mouseClick(button, Qt.LeftButton)
        assert main_window._content_stack.currentIndex() == stack_index
        assert button.isChecked()


def test_user_sees_styled_sidebar(main_window):
    assert main_window._sidebar.objectName() == "sidebar"
    assert main_window._sidebar.width() == 220


def test_user_can_access_menu_items(main_window):
    assert main_window.menuBar().actions()
    assert main_window._file_menu.isEnabled()


@pytest.fixture
def upload_widget(qtbot):
    with patch("ui.widgets.upload_widget.AppContext"):
        widget = UploadWidget()
        qtbot.addWidget(widget)
        return widget


def test_user_sees_styled_upload_buttons(upload_widget):
    assert upload_widget.btn_browse.property("buttonStyle") == "secondary"
    assert upload_widget.btn_clear.property("buttonStyle") == "secondary"
    assert upload_widget.btn_queue.property("buttonStyle") == "secondary"


def test_user_sees_disabled_start_button_initially(upload_widget):
    assert upload_widget.btn_start.isEnabled() is False


def test_user_can_enable_ensemble_mode(upload_widget):
    upload_widget.ensemble_checkbox.setChecked(True)

    assert upload_widget.ensemble_checkbox.isChecked() is True
    assert upload_widget.model_combo.isEnabled() is True

@pytest.fixture
def player_widget(qtbot, reset_singletons):
    widget = PlayerWidget()
    qtbot.addWidget(widget)
    return widget


def test_user_sees_styled_playback_buttons(player_widget):
    assert player_widget.btn_play.property("buttonStyle") == "success"
    assert player_widget.btn_pause.property("buttonStyle") == "secondary"
    assert player_widget.btn_stop.property("buttonStyle") == "danger"


def test_user_sees_load_buttons_with_icons(player_widget):
    assert "📁" in player_widget.btn_load_dir.text()
    assert "📄" in player_widget.btn_load_files.text()


def test_user_sees_monospace_time_display(player_widget):
    assert player_widget.current_time_label.property("labelStyle") == "mono"
    assert player_widget.duration_label.property("labelStyle") == "mono"


def test_stem_control_mute_and_solo_follow_clicks(qtbot):
    control = StemControl("vocals")
    qtbot.addWidget(control)

    qtbot.mouseClick(control.btn_mute, Qt.LeftButton)
    qtbot.mouseClick(control.btn_solo, Qt.LeftButton)

    assert control.is_muted is True
    assert control.is_solo is True


@pytest.fixture
def recording_widget(qtbot):
    with patch("ui.widgets.recording_widget.AppContext"):
        widget = RecordingWidget()
        qtbot.addWidget(widget)
        return widget


def test_user_sees_styled_recording_controls(recording_widget):
    assert recording_widget.btn_start.property("buttonStyle") == "success"
    assert recording_widget.btn_pause.property("buttonStyle") == "secondary"
    assert recording_widget.btn_cancel.property("buttonStyle") == "danger"


def test_user_sees_monospace_recording_duration(recording_widget):
    assert recording_widget.duration_label.property("labelStyle") == "mono"


@pytest.fixture
def queue_widget(qtbot):
    with patch("ui.widgets.queue_widget.AppContext"):
        widget = QueueWidget()
        qtbot.addWidget(widget)
        return widget


def test_user_sees_styled_queue_controls(queue_widget):
    assert queue_widget.btn_start.property("buttonStyle") == "success"
    assert queue_widget.btn_stop.property("buttonStyle") == "danger"
    assert queue_widget.btn_clear.property("buttonStyle") == "secondary"
    assert queue_widget.btn_remove.property("buttonStyle") == "secondary"


def test_user_sees_queue_rows_when_adding_task(queue_widget, tmp_path):
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")

    queue_widget.add_task(source, "demucs_4s")

    assert queue_widget.queue_table.rowCount() == 1
