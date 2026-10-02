"""PlayerWidget interaction tests."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import Qt
from unittest.mock import Mock, patch

from core.player import PlaybackState
from ui.widgets.player_widget import PlayerWidget, StemControl


@pytest.fixture
def test_audio_files(tmp_path):
    sample_rate = 44100
    samples = sample_rate
    time = np.linspace(0, 1, samples, endpoint=False)
    paths = []
    for name, frequency in (("Vocals", 440), ("Bass", 110)):
        audio = np.sin(2 * np.pi * frequency * time)
        path = tmp_path / f"test_({name})_model.wav"
        sf.write(path, np.column_stack([audio, audio]), sample_rate)
        paths.append(path)
    return paths


@pytest.fixture
def player_widget(qtbot, reset_singletons):
    widget = PlayerWidget()
    qtbot.addWidget(widget)
    return widget


def load_stems(qtbot, widget, paths):
    widget._load_stems(paths)
    qtbot.waitUntil(lambda: widget.btn_play.isEnabled(), timeout=15000)


class TestStemControl:
    def test_stem_control_creation(self, qtbot):
        control = StemControl("vocals")
        qtbot.addWidget(control)

        assert control.stem_name == "vocals"
        assert control.volume_slider.value() == 75

    def test_stem_control_mute_emits_state(self, qtbot):
        control = StemControl("vocals")
        qtbot.addWidget(control)
        signal = Mock()
        control.mute_changed.connect(signal)

        qtbot.mouseClick(control.btn_mute, Qt.LeftButton)

        assert control.is_muted is True
        signal.assert_called_once_with("vocals", True)

    def test_stem_control_solo_emits_state(self, qtbot):
        control = StemControl("vocals")
        qtbot.addWidget(control)
        signal = Mock()
        control.solo_changed.connect(signal)

        qtbot.mouseClick(control.btn_solo, Qt.LeftButton)

        assert control.is_solo is True
        signal.assert_called_once_with("vocals", True)

    def test_stem_control_volume_emits_value(self, qtbot):
        control = StemControl("vocals")
        qtbot.addWidget(control)
        signal = Mock()
        control.volume_changed.connect(signal)

        control.volume_slider.setValue(50)

        signal.assert_called_with("vocals", 50)
        assert control.volume_label.text() == "50%"


class TestPlayerWidget:
    def test_initial_playback_controls_are_disabled(self, player_widget):
        assert player_widget.player is not None
        assert player_widget.stem_controls == {}
        assert player_widget.btn_play.isEnabled() is False
        assert player_widget.btn_pause.isEnabled() is False
        assert player_widget.btn_stop.isEnabled() is False

    def test_loading_stems_enables_playback_and_populates_player(
        self, player_widget, qtbot, test_audio_files
    ):
        load_stems(qtbot, player_widget, test_audio_files)

        assert set(player_widget.stem_controls) == {"Vocals", "Bass"}
        assert set(player_widget.player.stems) == {"Vocals", "Bass"}
        assert player_widget.position_slider.isEnabled() is True

    def test_stem_controls_update_player_settings(
        self, player_widget, qtbot, test_audio_files
    ):
        load_stems(qtbot, player_widget, test_audio_files)
        stem_name = "Vocals"
        control = player_widget.stem_controls[stem_name]

        control.volume_slider.setValue(50)
        qtbot.mouseClick(control.btn_mute, Qt.LeftButton)
        qtbot.mouseClick(control.btn_solo, Qt.LeftButton)

        settings = player_widget.player.stem_settings[stem_name]
        assert settings.volume == 0.5
        assert settings.is_muted is True
        assert settings.is_solo is True

    def test_master_volume_updates_player(self, player_widget, qtbot, test_audio_files):
        load_stems(qtbot, player_widget, test_audio_files)

        player_widget.master_slider.setValue(70)

        assert player_widget.player.master_volume == 0.7
        assert player_widget.master_label.text() == "70%"

    def test_state_changes_update_transport_controls(self, player_widget):
        player_widget.player.duration_samples = 88200
        player_widget.player.stems = {"test": np.zeros((2, 88200))}
        player_widget.btn_play.setEnabled(True)

        player_widget._on_state_changed(PlaybackState.PLAYING)
        assert player_widget.btn_play.isEnabled() is False
        assert player_widget.btn_pause.isEnabled() is True
        assert player_widget.btn_stop.isEnabled() is True

        player_widget._on_state_changed(PlaybackState.PAUSED)
        assert player_widget.btn_play.isEnabled() is True
        assert player_widget.btn_pause.isEnabled() is False

    def test_position_slider_seeks_loaded_audio(
        self, player_widget, qtbot, test_audio_files
    ):
        load_stems(qtbot, player_widget, test_audio_files)

        player_widget.position_slider.setValue(500)
        player_widget._on_slider_released()

        assert abs(player_widget.player.get_position() - 0.5) < 0.1

    def test_time_formatting(self, player_widget):
        assert player_widget._format_time(0) == "00:00"
        assert player_widget._format_time(59) == "00:59"
        assert player_widget._format_time(60) == "01:00"
        assert player_widget._format_time(125) == "02:05"

    def test_load_separation_result_populates_controls(
        self, player_widget, qtbot, test_audio_files
    ):
        player_widget.load_separation_result(
            {"Vocals": test_audio_files[0], "Bass": test_audio_files[1]}
        )
        qtbot.waitUntil(lambda: player_widget.btn_play.isEnabled(), timeout=15000)

        assert set(player_widget.stem_controls) == {"Vocals", "Bass"}

    def test_position_updates_pause_while_user_seeks(
        self, player_widget, qtbot, test_audio_files
    ):
        load_stems(qtbot, player_widget, test_audio_files)
        player_widget._on_slider_pressed()
        player_widget.player.position_samples = 22050

        player_widget._update_position()

        assert player_widget.position_slider.value() != 500
