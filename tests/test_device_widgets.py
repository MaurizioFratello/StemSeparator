"""
Device pickers in the GUI (`ui/widgets/player_widget`, `ui/widgets/recording_widget`).

WHY these tests exist: the widget layer is where a wrong choice becomes a user
visible failure — an output picker that pins nothing, a recording list that
auto-selects a room microphone while the user believes they are capturing system
audio (the pre-port macOS default), or a saved device that vanished after
hot-unplug. The widget behaviour is asserted, not the engine's: `player` and
`recorder` are replaced by recording stubs, so no PortAudio, no hardware, and no
writing to the real `user_settings.json`.
"""

import copy

import pytest

from core.player import AudioDeviceInfo
from ui.settings_manager import get_settings_manager


@pytest.fixture
def isolated_settings(tmp_path):
    """The real SettingsManager, but pointed at a throwaway file."""
    manager = get_settings_manager()
    snapshot = copy.deepcopy(manager.settings)
    original_file = manager.settings_file
    manager.settings_file = tmp_path / "user_settings.json"
    manager.settings["playback_device"] = None
    manager.settings["recording_device"] = None
    try:
        yield manager
    finally:
        manager.settings = snapshot
        manager.settings_file = original_file


# ----------------------------------------------------------------------------- player


class StubPlayer:
    """`PlayerWidget` surface: records what the widget asked for."""

    class _State:
        STOPPED = "stopped"

    def __init__(self, devices, fail_for=()):
        self._devices = devices
        self._fail_for = set(fail_for)
        self.pinned = "unset"
        self.state = self._State.STOPPED
        self.last_message = ""

    def list_output_devices(self):
        return list(self._devices)

    def set_output_device(self, device):
        if device in self._fail_for:
            # A refusal must leave the engine on the device it actually uses.
            self.last_message = f"Output device {device!r} not found."
            return False, self.last_message
        self.pinned = device
        self.last_message = f"Using {device!r}" if device else "Using system default"
        return True, self.last_message

    def get_output_device(self):
        return 0 if self.pinned is None else 7

    def get_output_device_name(self):
        return self.pinned

    def stop(self):
        """`closeEvent` calls this; without it qtbot teardown errors."""
        pass

    def play(self):
        pass


def device(name, host_api="WASAPI", channels=2, rate=48000.0, default=False):
    return AudioDeviceInfo(
        index=0,
        name=name,
        host_api=host_api,
        max_channels=channels,
        default_sample_rate=rate,
        is_default=default,
    )


def make_player_widget(qtbot, stub, saved=None):
    from ui.widgets.player_widget import PlayerWidget

    widget = PlayerWidget()
    qtbot.addWidget(widget)
    if saved is not None:
        get_settings_manager().set_playback_device(saved)
    widget.player = stub
    widget._populate_output_devices()
    return widget


class TestOutputPicker:
    def test_default_entry_first_and_devices_show_host_api(self, qtbot, isolated_settings):
        stub = StubPlayer([device("Speakers", "WASAPI"), device("Speakers", "DirectSound")])
        widget = make_player_widget(qtbot, stub)
        combo = widget.device_combo

        assert combo.count() == 3
        assert combo.itemData(0) is None, "entry 0 must mean 'follow the system default'"
        texts = [combo.itemText(i) for i in range(1, combo.count())]
        assert any("WASAPI" in t for t in texts) and any("DirectSound" in t for t in texts), (
            f"the host API must disambiguate the duplicate names, got {texts}"
        )

    def test_default_device_gets_a_marker(self, qtbot, isolated_settings):
        stub = StubPlayer([device("HDMI", default=True), device("USB")])
        widget = make_player_widget(qtbot, stub)
        labels = [widget.device_combo.itemText(i) for i in range(widget.device_combo.count())]
        # Assert through the widget's own translation: the UI language is a
        # persisted, host-specific value, and the contract is "the default output
        # row is marked as such" — checked per row, because in German that suffix
        # ("Standard") is also a substring of the system-default entry's label.
        suffix = widget.ctx.translate("playback.default_output_suffix", "default")
        rows = {
            widget.device_combo.itemData(i): widget.device_combo.itemText(i)
            for i in range(1, widget.device_combo.count())
        }
        assert suffix in rows["HDMI"], rows
        assert suffix not in rows["USB"], rows

    def test_choosing_an_output_pins_it_and_persists(self, qtbot, isolated_settings):
        stub = StubPlayer([device("HDMI"), device("USB DAC")])
        widget = make_player_widget(qtbot, stub)
        index = widget.device_combo.findData("USB DAC")
        assert index > 0
        widget._on_output_device_selected(index)

        assert stub.pinned == "USB DAC", "the engine must be told immediately"
        assert get_settings_manager().get_playback_device() == "USB DAC", (
            "the choice must survive a restart"
        )
        assert widget.device_status_label.text(), "the picker must report the outcome"

    def test_choosing_the_default_entry_unpins_and_persists(
        self, qtbot, isolated_settings
    ):
        stub = StubPlayer([device("HDMI")])
        widget = make_player_widget(qtbot, stub, saved="HDMI")
        assert stub.pinned == "HDMI"
        widget._on_output_device_selected(0)
        assert stub.pinned is None
        assert get_settings_manager().get_playback_device() in (None, "")

    def test_saved_but_missing_device_falls_back_without_phantom_pin(
        self, qtbot, isolated_settings
    ):
        """
        A device saved before it was unplugged must not stay pinned.

        WHY: the combo used to restore the saved name blindly, so playback kept
        targeting a dead endpoint and stayed silent.
        """
        stub = StubPlayer([device("HDMI")])
        widget = make_player_widget(qtbot, stub, saved="Ghost USB DAC 9000")

        assert widget.device_combo.currentIndex() == 0, "combo shows the system default"
        assert stub.pinned is None, "no phantom pin to a device that is not present"

    def test_failed_selection_reverts_the_combo(self, qtbot, isolated_settings):
        """Engine refusal must not leave the UI claiming an impossible device."""
        stub = StubPlayer([device("HDMI"), device("Broken")], fail_for={"Broken"})
        widget = make_player_widget(qtbot, stub)
        widget._on_output_device_selected(widget.device_combo.findData("Broken"))

        assert widget.device_combo.currentData() != "Broken"
        assert "not found" in widget.device_status_label.text().lower()


# --------------------------------------------------------------------------- recorder


class StubRecorder:
    """`RecordingWidget` surface for enumeration and persistence."""

    def __init__(self, devices, backend_info):
        self._devices = devices
        self._info = dict(backend_info)
        self.monitor_calls = []
        self.monitoring = False
        self.stops = 0
        self.recording = False

    def get_available_devices(self):
        return list(self._devices)

    def get_backend_info(self):
        return dict(self._info)

    def is_recording(self):
        return self.recording

    def is_monitoring(self):
        return self.monitoring

    def start_monitoring(self, device_name=None, level_callback=None):
        self.monitor_calls.append(device_name)
        self.monitoring = True
        return True

    def stop_monitoring(self):
        self.monitoring = False
        self.stops += 1


def make_recording_widget(qtbot, devices, backend_info, saved=None):
    from ui.widgets.recording_widget import RecordingWidget

    widget = RecordingWidget()
    qtbot.addWidget(widget)
    if saved is not None:
        get_settings_manager().set_recording_device(saved)
    widget.recorder = StubRecorder(devices, backend_info)
    widget._is_visible = False  # a device change must never start real monitoring
    widget._refresh_devices()
    return widget


LINUX_INFO = {
    "platform": "Linux",
    "backend": "SYSTEM_LOOPBACK",
    "screencapture_available": False,
    "soundcard_available": True,
    "system_audio_device": "Monitor of HDMI [System Audio]",
}


class TestRecordingPicker:
    def test_system_audio_is_preferred_over_a_room_microphone(
        self, qtbot, isolated_settings
    ):
        """
        REC-02: the default must be the loopback endpoint, not an arbitrary mic.

        WHY: the macOS-era default selected BlackHole when present and otherwise
        whatever came first — on Windows/Linux that was a microphone, so users
        recorded the room believing it was system audio.
        """
        widget = make_recording_widget(
            qtbot,
            ["Microphone (Realtek)", "Monitor of HDMI [System Audio]"],
            LINUX_INFO,
        )
        assert "[System Audio]" in widget.device_combo.currentText()
        assert "Microphone" not in widget.device_combo.currentText()

    def test_saved_device_beats_the_platform_default(self, qtbot, isolated_settings):
        widget = make_recording_widget(
            qtbot,
            ["Microphone (Realtek)", "Monitor of HDMI [System Audio]"],
            LINUX_INFO,
            saved="Microphone (Realtek)",
        )
        assert widget.device_combo.currentText().startswith("Microphone")

    def test_refreshing_the_list_does_not_clobber_the_saved_device(
        self, qtbot, isolated_settings
    ):
        """
        REC-02 regression: repopulating fired `currentIndexChanged` and the
        handler persisted whichever entry landed first, so opening the tab or
        pressing refresh silently replaced the user's saved source with an
        arbitrary microphone.
        """
        manager = get_settings_manager()
        widget = make_recording_widget(
            qtbot,
            ["Microphone (Realtek)", "Monitor of HDMI [System Audio]"],
            LINUX_INFO,
        )
        assert widget.device_combo.currentIndex() == 1
        assert manager.get_recording_device() is None, (
            "a refresh must not invent a user preference"
        )

        widget._on_device_changed(1)  # the user actually picks system audio
        assert manager.get_recording_device() == "Monitor of HDMI [System Audio]"

        widget._refresh_devices()  # hot-plug / tab re-entry
        assert manager.get_recording_device() == "Monitor of HDMI [System Audio]"
        assert widget.device_combo.currentIndex() == 1, (
            "the persisted choice must be what the picker shows afterwards"
        )

    def test_a_never_touched_picker_still_monitors_once_the_tab_shows(
        self, qtbot, isolated_settings
    ):
        """
        Regression for the blockSignals fix: with repopulation silent, no signal
        ever seeded `_last_selected_device`, so `showEvent` had nothing to
        monitor and the level meter stayed dead until the user manually changed
        the combo. The refresh itself must seed it.
        """
        widget = make_recording_widget(
            qtbot,
            ["Microphone (Realtek)", "Monitor of HDMI [System Audio]"],
            LINUX_INFO,
        )
        assert widget._last_selected_device == "Monitor of HDMI [System Audio]"

        widget.recorder.monitor_calls.clear()
        widget.show()  # real showEvent flips _is_visible and starts monitoring
        try:
            assert widget._is_visible is True
            assert widget.recorder.monitor_calls == ["Monitor of HDMI [System Audio]"]
            assert widget.state_label.text() == "Monitoring..."
        finally:
            widget.hide()

    def test_choosing_via_the_combo_persists_and_remonitors(
        self, qtbot, isolated_settings
    ):
        """The live signal path (not a direct call): picking another entry
        persists the name and moves monitoring to it."""
        widget = make_recording_widget(
            qtbot,
            ["Microphone (Realtek)", "Monitor of HDMI [System Audio]"],
            LINUX_INFO,
        )
        widget._is_visible = True
        mic = next(
            i
            for i in range(widget.device_combo.count())
            if "[System Audio]" not in widget.device_combo.itemText(i)
        )
        widget.device_combo.setCurrentIndex(mic)  # fires currentIndexChanged
        assert get_settings_manager().get_recording_device() == "Microphone (Realtek)"
        assert widget.recorder.monitor_calls[-1] == "Microphone (Realtek)"

    def test_vanished_device_stops_monitoring_and_resets_status(
        self, qtbot, isolated_settings
    ):
        """
        Hot-unplug with the tab open: the refresh must tear down monitoring on
        the dead stream and reset the stale "Monitoring..." label — the old
        branch cleared only the marker, so the level meter kept reading a
        vanished device (the stateless stub hid this; the stub is stateful now).
        """
        widget = make_recording_widget(qtbot, ["Microphone (Realtek)"], LINUX_INFO)
        widget._is_visible = True
        widget._refresh_devices()
        assert widget.recorder.is_monitoring()
        assert widget.state_label.text() == "Monitoring..."

        widget.recorder._devices = []
        widget._refresh_devices()
        assert widget._last_selected_device is None
        assert widget.recorder.is_monitoring() is False
        assert widget.recorder.stops == 1
        assert widget.state_label.text() == "Ready"

    def test_vanished_device_never_interrupts_an_active_recording(
        self, qtbot, isolated_settings
    ):
        """Same branch, mirrored guard: an in-progress recording survives a
        refresh even when every device disappears (the take is on disk, not on
        the monitor stream)."""
        widget = make_recording_widget(qtbot, ["Microphone (Realtek)"], LINUX_INFO)
        widget._is_visible = True
        widget._refresh_devices()
        widget.recorder.recording = True
        widget.recorder._devices = []
        widget._refresh_devices()
        assert widget.recorder.stops == 0, "a recording must survive a refresh"
        assert widget.state_label.text() == "Monitoring..."

    def test_choosing_a_device_persists_its_name(self, qtbot, isolated_settings):
        widget = make_recording_widget(qtbot, ["Microphone (Realtek)"], LINUX_INFO)
        widget._on_device_changed(0)
        assert get_settings_manager().get_recording_device() == "Microphone (Realtek)"

    def test_empty_enumeration_shows_an_explicit_placeholder(
        self, qtbot, isolated_settings
    ):
        widget = make_recording_widget(
            qtbot, [], dict(LINUX_INFO, system_audio_device=None)
        )
        assert widget.device_combo.count() == 1
        assert widget.device_combo.itemText(0) == "No devices found"
        assert widget.device_combo.currentData() is None, (
            "a placeholder must never be handed to the recorder as a device"
        )

    def test_screencapture_entry_is_absent_off_macos(self, qtbot, isolated_settings):
        widget = make_recording_widget(qtbot, ["Microphone"], LINUX_INFO)
        datas = [
            widget.device_combo.itemData(i) for i in range(widget.device_combo.count())
        ]
        assert "__screencapture__" not in datas

    def test_screencapture_entry_is_first_when_available(self, qtbot, isolated_settings):
        widget = make_recording_widget(
            qtbot,
            ["BlackHole 2CH"],
            dict(
                LINUX_INFO,
                platform="macOS",
                screencapture_available=True,
                system_audio_device=None,
            ),
        )
        assert widget.device_combo.itemData(0) == "__screencapture__"
        assert widget.device_combo.currentIndex() == 0

    @pytest.mark.parametrize(
        "platform_name,expected_fragment",
        [
            ("Windows", "WASAPI"),
            ("Linux", "PipeWire"),
            ("macOS", "Screen Recording"),
        ],
    )
    def test_failure_help_names_the_mechanism_of_the_running_os(
        self, qtbot, isolated_settings, platform_name, expected_fragment
    ):
        """REC-03: guidance must match the OS, not assume BlackHole."""
        widget = make_recording_widget(qtbot, [], LINUX_INFO)
        widget.recorder._info = {
            "platform": platform_name,
            "backend": "x",
            "screencapture_available": False,
            "last_error": "device busy",
        }
        help_text = widget._recording_failure_help()
        assert "device busy" in help_text, "the actual reason must be quoted"
        assert expected_fragment in help_text, (
            f"{platform_name} users must hear about {expected_fragment!r}: "
            f"{help_text[:220]}"
        )


# ------------------------------------------------------------------------- settings UI


class TestSettingsDialogPlatformGating:
    def test_blackhole_installer_is_absent_off_macos(self, qtbot, isolated_settings):
        """
        The port promise: no macOS-only installer affordance leaks to the UI.

        WHY: the BlackHole button shelled out to `brew install`, which is
        meaningless and confusing on Windows/Linux.
        """
        import utils.platform_utils as platform_utils
        from ui.widgets.settings_dialog import SettingsDialog

        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert platform_utils.is_macos() is False, "this runs on the ported platforms"
        assert not hasattr(dialog, "btn_install_blackhole")
        assert not hasattr(dialog, "blackhole_status_label")
