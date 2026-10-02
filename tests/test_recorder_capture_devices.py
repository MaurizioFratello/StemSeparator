"""
Capture-device discovery for the recorder (`core.recorder`).

WHY these tests exist: system-audio recording silently offered nothing outside
macOS because enumeration called `soundcard.all_microphones()` without
`include_loopback=True` — the call that hides exactly the Windows loopback
endpoints and the PulseAudio/PipeWire monitor sources. Auto-selection also
claimed the BlackHole backend on every platform that could import soundcard.
The whole module runs against a fake `soundcard`, so no audio hardware,
PipeWire or driver is involved and the matrix is deterministic per OS.
"""

import sys

import pytest

from core.recorder import RecordingBackend, Recorder

MICROPHONES = {
    "win32": [
        {"name": "Microphone (Realtek(R) Audio)"},
        {"name": "Speakers (Realtek(R) Audio)", "loopback": True},
        {"name": "Stereo Mix (Realtek High Definition Audio)"},
    ],
    "linux": [
        {"name": "Ryzen HD Audio Controller Analog Stereo"},
        {"name": "Monitor of GB202 HDMI", "dev_class": "monitor"},
        {"name": "Monitor of Ryzen IEC958", "dev_class": "monitor"},
    ],
    "darwin": [
        {"name": "MacBook Pro Microphone"},
        {"name": "BlackHole 2ch"},
    ],
}

DEFAULT_SPEAKER = {
    "win32": "Speakers (Realtek(R) Audio)",
    "linux": "GB202 HDMI",
    "darwin": "MacBook Pro Speakers",
}


class FakeMic:
    def __init__(self, name, loopback=False, dev_class=None):
        self.name = name
        self.isloopback = loopback
        self._info = {} if dev_class is None else {"device.class": dev_class}

    def _get_info(self):
        return dict(self._info)

    def __repr__(self):  # keeps assertion output readable
        return f"FakeMic({self.name!r})"


class FakeSoundcard:
    """Only the API surface the recorder is allowed to use."""

    def __init__(self, platform, speaker_raises=False, only_mics=None):
        self.platform = platform
        self.all_microphones_calls = []
        self._speaker_raises = speaker_raises
        self._only_mics = only_mics

    def all_microphones(self, include_loopback=False, **kwargs):
        self.all_microphones_calls.append(include_loopback)
        if self._only_mics is not None:
            return [FakeMic(**spec) for spec in self._only_mics]
        return [FakeMic(**spec) for spec in MICROPHONES[self.platform]]

    def all_speakers(self):
        return [FakeMic(DEFAULT_SPEAKER[self.platform])]

    def default_speaker(self):
        if self._speaker_raises:
            raise RuntimeError("no default output device")
        return FakeMic(DEFAULT_SPEAKER[self.platform])

    def __getattr__(self, item):
        # Dunder lookups have to fail normally, or importing/introspecting the
        # fake breaks. Anything else is an API the recorder must not touch:
        # `Recorder`/`Speaker` do not exist in the Linux soundcard build.
        if item.startswith("_"):
            raise AttributeError(item)
        raise AssertionError(f"recorder used unexpected soundcard API: {item}")


def install(monkeypatch, platform, fake):
    """Make `import soundcard` yield `fake` and the app believe it is `platform`."""
    import utils.platform_utils as platform_utils

    monkeypatch.setitem(sys.modules, "soundcard", fake)
    monkeypatch.setattr(platform_utils, "_platform_string", lambda: platform)
    monkeypatch.setattr(Recorder, "_import_screencapture", lambda self: False)
    return fake


@pytest.fixture
def recorder_for(monkeypatch):
    """Build a Recorder that believes it runs on the requested OS."""

    def build(platform, speaker_raises=False, only_mics=None):
        fake = FakeSoundcard(
            platform, speaker_raises=speaker_raises, only_mics=only_mics
        )
        install(monkeypatch, platform, fake)
        recorder = Recorder()
        recorder._fake = fake
        return recorder

    return build


class TestLoopbackEnumeration:
    def test_enumeration_requests_loopback_endpoints(self, recorder_for):
        """The regression itself: `include_loopback=True` must be passed."""
        recorder = recorder_for("linux")
        assert recorder._fake.all_microphones_calls, "all_microphones was never called"
        assert all(flag is True for flag in recorder._fake.all_microphones_calls), (
            "without include_loopback=True the Pulse/PipeWire monitor sources "
            "and Windows loopback endpoints are invisible"
        )

    def test_win32_and_darwin_also_request_loopback(self, recorder_for):
        for platform in ("win32", "darwin"):
            recorder = recorder_for(platform)
            assert all(f is True for f in recorder._fake.all_microphones_calls), platform


class TestSystemCaptureClassification:
    @pytest.mark.parametrize(
        "mic,expected",
        [
            (FakeMic("Speakers (Realtek)", loopback=True), True),
            (FakeMic("Monitor of GB202 HDMI", dev_class="monitor"), True),
            (FakeMic("Monitor of Whatever"), True),
            (FakeMic("Line Out [Loopback]"), True),
            (FakeMic("BlackHole 2ch"), True),
            (FakeMic("Ryzen HD Audio Controller Analog Stereo"), False),
            (FakeMic("USB Microphone", dev_class="audio"), False),
        ],
    )
    def test_classification(self, mic, expected):
        assert Recorder._is_system_capture_device(mic) is expected

    def test_split_between_input_and_system_devices(self, recorder_for):
        recorder = recorder_for("linux")
        assert [d.name for d in recorder.system_audio_devices()] == [
            "Monitor of GB202 HDMI",
            "Monitor of Ryzen IEC958",
        ]
        assert [d.name for d in recorder.all_input_devices()] == [
            "Ryzen HD Audio Controller Analog Stereo"
        ]

    def test_labels_decorate_only_system_devices(self, recorder_for):
        recorder = recorder_for("linux")
        assert recorder.label_for_device(
            FakeMic("Monitor of GB202 HDMI", dev_class="monitor")
        ) == "Monitor of GB202 HDMI [System Audio]"
        assert recorder.label_for_device(FakeMic("USB Mic")) == "USB Mic"

    def test_labels_round_trip_through_lookup(self, recorder_for):
        """Combo labels and raw driver names both resolve (settings persistence)."""
        recorder = recorder_for("linux")
        decorated = "Monitor of GB202 HDMI [System Audio]"
        assert recorder._find_device(decorated).name == "Monitor of GB202 HDMI"
        assert recorder._find_device("Monitor of GB202 HDMI").name == "Monitor of GB202 HDMI"
        assert recorder._find_device("Ryzen HD Audio Controller Analog Stereo") is not None

    def test_device_list_is_sorted_and_unique(self, recorder_for):
        recorder = recorder_for("linux")
        devices = recorder.get_available_devices()
        assert devices == sorted(devices)
        assert len(devices) == len(set(devices)) == 3


class TestPreferredSystemDevice:
    def test_prefers_monitor_of_the_current_default_output(self, recorder_for):
        """`default_speaker()` is GB202 HDMI, so its monitor must win."""
        recorder = recorder_for("linux")
        assert recorder._find_system_audio_device().name == "Monitor of GB202 HDMI"

    def test_survives_unqueryable_default_speaker(self, recorder_for):
        recorder = recorder_for("linux", speaker_raises=True)
        chosen = recorder._find_system_audio_device()
        assert chosen is not None, "a missing default output must not disable capture"
        assert Recorder._is_system_capture_device(chosen)

    def test_macos_prefers_blackhole(self, recorder_for):
        recorder = recorder_for("darwin")
        assert recorder._find_system_audio_device().name == "BlackHole 2ch"

    def test_none_when_no_loopback_exists(self, recorder_for):
        recorder = recorder_for("linux", only_mics=[{"name": "USB Microphone"}])
        assert recorder._find_system_audio_device() is None


class TestBackendSelection:
    @pytest.mark.parametrize(
        "platform,expected",
        [
            ("win32", RecordingBackend.WASAPI_LOOPBACK),
            ("linux", RecordingBackend.SYSTEM_LOOPBACK),
            ("darwin", RecordingBackend.BLACKHOLE),
        ],
    )
    def test_per_os_backend(self, recorder_for, platform, expected):
        recorder = recorder_for(platform)
        assert recorder.backend == RecordingBackend.AUTO
        assert recorder._selected_backend is expected, (
            "claiming a backend whose driver cannot exist on this OS produced the "
            "original cross-platform recording failure"
        )

    def test_falls_back_to_input_device_with_a_warning(self, recorder_for, caplog):
        """No loopback endpoint anywhere: microphone device, and say so loudly."""
        recorder = recorder_for("linux", only_mics=[{"name": "USB Microphone"}])
        assert recorder._selected_backend is RecordingBackend.INPUT_DEVICE

    def test_no_soundcard_means_no_backend_and_a_reason(self, monkeypatch):
        import utils.platform_utils as platform_utils

        def explode(self):
            self._soundcard = None
            self._soundcard_error = "OSError: libportaudio.so.2: cannot open"
            return False

        install(monkeypatch, "linux", FakeSoundcard("linux"))
        monkeypatch.setattr(Recorder, "_import_soundcard", explode)
        recorder = Recorder()

        assert recorder._selected_backend is None
        assert recorder.get_available_devices() == []
        assert recorder._soundcard_error.startswith("OSError")


class TestActionableErrors:
    def test_unknown_device_lists_what_exists(self, recorder_for):
        recorder = recorder_for("linux")
        assert recorder._find_device("Headset that does not exist") is None
        assert "not found" in recorder.last_error
        # the list must show the decorated names the user sees in the combo box
        assert "[System Audio]" in recorder.last_error

    def test_no_devices_explains_the_permission_angle(self, recorder_for):
        recorder = recorder_for("linux", only_mics=[])
        # `all_microphones` returns nothing at all -> permission guidance
        recorder._soundcard.all_microphones = lambda include_loopback=False, **kw: []
        assert recorder._find_device(None) is None
        assert "permission" in recorder.last_error.lower()

    def test_broken_enumeration_is_reported_not_raised(self, recorder_for):
        """A failing enumeration degrades to "no devices" and leaves a log line."""
        recorder = recorder_for("linux")

        class CollectingLogger:
            def __init__(self):
                self.messages = []

            def debug(self, message, *args, **kwargs):
                self.messages.append(message)

            def info(self, message, *args, **kwargs):
                self.messages.append(message)

            def warning(self, message, *args, **kwargs):
                self.messages.append(message)

            def error(self, message, *args, **kwargs):
                self.messages.append(message)

        recorder.logger = CollectingLogger()

        def boom(include_loopback=False, **kwargs):
            raise RuntimeError("pulse: connection refused")

        recorder._soundcard.all_microphones = boom
        assert recorder.all_capture_devices() == []
        assert any(
            "Could not enumerate capture devices" in message
            for message in recorder.logger.messages
        ), "the failure must leave a trace instead of an empty list alone"
