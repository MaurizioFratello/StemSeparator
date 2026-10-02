"""
Output-device handling for the stem player (`core.player`).

WHY these tests exist: `sounddevice.play()` used to sit in a bare `except` that
logged and returned while callers still set the state to PLAYING, so the UI
showed a running transport with no sound. On Windows/Linux the same speakers are
exposed through several host APIs and a WASAPI shared endpoint can reject
44.1 kHz while reporting `default_samplerate == 44100`, so device choice and
rate recovery are user-visible behaviour, not details.

Everything runs against a fake `sounddevice`: no PortAudio, no hardware, no
assumption that the machine running the suite has any audio at all.
"""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from core.player import AudioPlayer

DEVICES = [
    # index 0: capture-only
    {"name": "Ryzen Mic", "max_output_channels": 0, "max_input_channels": 2,
     "hostapi": 0, "default_samplerate": 44100.0},
    # index 1: HDMI output (the pinned default on the reference host)
    {"name": "GB202 HDMI", "max_output_channels": 2, "max_input_channels": 0,
     "hostapi": 0, "default_samplerate": 48000.0},
    # index 2: the same speakers through another host API
    {"name": "GB202 HDMI", "max_output_channels": 2, "max_input_channels": 0,
     "hostapi": 1, "default_samplerate": 44100.0},
    # index 3: USB speakers
    {"name": "PiKVM V4 Mini", "max_output_channels": 2, "max_input_channels": 0,
     "hostapi": 0, "default_samplerate": 44100.0},
]

HOST_APIS = {0: {"name": "ALSA"}, 1: {"name": "PulseAudio"}}


class FakeSounddevice:
    """`sounddevice` surface used by AudioPlayer, with scriptable failures."""

    def __init__(self, play_rules=None, query_raises=False, rates=None):
        self.default = SimpleNamespace(device=[0, 1])  # [input, output]
        self.play_calls = []
        self._play_rules = play_rules or {}
        self._query_raises = query_raises
        self._rates = rates

    def query_devices(self, index=None):
        if self._query_raises:
            raise RuntimeError("PortAudio not initialised")
        if index is None:
            return list(DEVICES)
        return dict(DEVICES[index])

    def query_hostapis(self, index):
        return HOST_APIS[index]

    def available_sample_rates(self, device):
        if self._rates is None:
            raise RuntimeError("unsupported by host API")
        return self._rates

    def play(self, audio, samplerate=44100, device=None, blocking=True, **kwargs):
        self.play_calls.append({"samplerate": float(samplerate), "device": device})
        failure = self._play_rules.get((device, float(samplerate)))
        if failure is None:
            failure = self._play_rules.get("always")
        if isinstance(failure, Exception):
            raise failure
        if isinstance(failure, dict):  # rate-dependent script
            failure = failure.get(float(samplerate))
            if isinstance(failure, Exception):
                raise failure
        return None


def make_player(monkeypatch, fake):
    """An AudioPlayer whose sounddevice import yields `fake`."""
    monkeypatch.setitem(sys.modules, "sounddevice", fake)

    def install(self):
        self._sounddevice_module = fake
        return True

    monkeypatch.setattr(AudioPlayer, "_import_sounddevice", install)
    return AudioPlayer()


@pytest.fixture
def player(monkeypatch):
    return make_player(monkeypatch, FakeSounddevice())


class TestListing:
    def test_only_outputs_are_listed_with_their_host_api(self, player):
        devices = player.list_output_devices()
        assert [d.name for d in devices] == [
            "GB202 HDMI",
            "GB202 HDMI",
            "PiKVM V4 Mini",
        ], "input-only devices must not be offered for playback"
        assert [d.host_api for d in devices] == ["ALSA", "PulseAudio", "ALSA"], (
            "the host API must be visible: Windows/Linux expose the same "
            "endpoint through several APIs and picking blind means no sound"
        )

    def test_default_flag_marks_the_system_output(self, player):
        devices = player.list_output_devices()
        assert [d.is_default for d in devices] == [True, False, False]

    def test_label_is_human_readable(self, player):
        label = player.list_output_devices()[0].label
        assert "GB202 HDMI" in label and "ALSA" in label

    def test_query_failure_yields_empty_list_and_a_reason(self, monkeypatch):
        player = make_player(monkeypatch, FakeSounddevice(query_raises=True))
        assert player.list_output_devices() == []
        assert "Could not query audio devices" in player.last_error

    def test_missing_sounddevice_yields_empty_list(self, player):
        player._sounddevice_module = None
        assert player.list_output_devices() == []


class TestSelection:
    def test_none_follows_the_system_default_without_pinning(self, player):
        ok, message = player.set_output_device(None)
        assert ok is True
        assert "GB202 HDMI" in message and "ALSA" in message
        assert player.get_output_device() is None

    def test_index_selection_pins_the_device(self, player):
        ok, message = player.set_output_device(3)
        assert ok is True and "PiKVM V4 Mini" in message
        assert player.get_output_device() == 3
        assert player.get_output_device_name() == "PiKVM V4 Mini"

    def test_name_match_is_case_insensitive_substring(self, player):
        ok, _ = player.set_output_device("pikvm")
        assert ok is True
        assert player.get_output_device() == 3

    def test_unknown_device_reports_the_available_list(self, player):
        ok, message = player.set_output_device("Bluetooth Buds")
        assert ok is False
        assert "not found" in message
        assert "ALSA" in message and "PulseAudio" in message, (
            "the message must show what exists, host API included"
        )
        assert player.last_error == message
        assert player.get_output_device() is None, "a failed pick must not pin anything"

    def test_no_portaudio_is_reported_not_swallowed(self, player):
        player._sounddevice_module = None
        ok, message = player.set_output_device(1)
        assert ok is False
        assert "PortAudio unavailable" in message

    def test_stale_saved_device_falls_back_visibly(self, player):
        """A device saved in settings that has since been unplugged."""
        player.set_output_device("pikvm")
        assert player.get_output_device() == 3
        ok, message = player.set_output_device("PiKVM V4 Mini (disconnected)")
        assert ok is False
        assert "not found" in message


class TestRateRecovery:
    def test_candidate_rates_order_and_dedup(self, monkeypatch):
        fake = FakeSounddevice(rates=(44100.0, 48000.0))
        player = make_player(monkeypatch, fake)
        # device 1 reports 48k natively; the rendered rate is 44.1k
        assert player._candidate_rates(1) == [48000.0, 32000.0], (
            "order is device-native, PortAudio's suggested pair, then common "
            "rates — de-duplicated, and never the rate just rejected"
        )

    def test_candidate_rates_survive_unsupported_query(self, player):
        """Host APIs that cannot report a rate range still get the fallbacks."""
        rates = player._candidate_rates(1)
        assert rates == [48000.0, 32000.0]
        assert float(player.sample_rate) not in rates

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("Invalid sample rate", True),
            ("Full-Duplex Stream: Sample rate mismatch", True),
            ("Unanticipated host error", False),
            ("device busy", False),
            ("", False),
            (None, False),
        ],
    )
    def test_rate_error_detection(self, player, message, expected):
        assert AudioPlayer._is_sample_rate_error(message) is expected

    def test_resample_changes_length_and_dtype_only_for_the_buffer(self, player):
        audio = np.zeros(44100, dtype=np.float32)
        out = player._resample_to(audio, 48000.0)
        assert out.dtype == np.float32
        assert len(out) == pytest.approx(48000, abs=2), "44100 samples @44.1k == 1 s"
        assert player.sample_rate == 44100, (
            "only the buffer handed to PortAudio may change rate; position and "
            "mixing math stay at the rendered rate"
        )

    @pytest.mark.parametrize("target", [44100.0, 0.0, -1.0])
    def test_resample_is_a_noop_when_pointless(self, player, target):
        audio = np.ones(128, dtype=np.float32)
        assert player._resample_to(audio, target) is audio

    def test_empty_buffer_is_returned_unchanged(self, player):
        audio = np.zeros(0, dtype=np.float32)
        assert player._resample_to(audio, 48000.0).size == 0


class TestPlayArray:
    def test_success_reports_the_device_and_rate(self, player):
        fake = player._sounddevice_module
        audio = np.zeros(1024, dtype=np.float32)
        assert player._play_array(audio, context="Stem") is True
        assert fake.play_calls == [{"samplerate": 44100.0, "device": 1}]
        assert player.last_error is None

    def test_wasapi_rate_rejection_recovers_by_resampling(self, monkeypatch):
        """
        Endpoint refuses 44.1 kHz -> retry at the device rate, and say so.

        WHY: this is the classic shared-mode WASAPI case; before recovery existed
        the player entered PLAYING with no sound.
        """
        fake = FakeSounddevice(
            play_rules={(1, 44100.0): RuntimeError("Invalid sample rate")},
            rates=(44100.0, 48000.0),
        )
        player = make_player(monkeypatch, fake)
        player._output_device = 1

        assert player._play_array(np.zeros(4410, dtype=np.float32), context="Stem") is True
        rates = [call["samplerate"] for call in fake.play_calls]
        assert rates[0] == 44100.0, "the requested rate is tried first"
        assert 48000.0 in rates, "recovery must retry at a plausible device rate"
        assert player.last_error is None

    def test_pinned_broken_device_falls_back_to_system_default(self, monkeypatch):
        fake = FakeSounddevice(
            play_rules={(3, 44100.0): RuntimeError("device is exclusively held")}
        )
        player = make_player(monkeypatch, fake)
        player._output_device = 3

        assert player._play_array(np.zeros(256, dtype=np.float32)) is True
        assert [c["device"] for c in fake.play_calls] == [3, 1], (
            "pinned device first, then the system default"
        )

    def test_every_failure_returns_false_with_an_actionable_error(self, player):
        fake = player._sounddevice_module
        fake._play_rules = {"always": RuntimeError("no device available")}

        assert player._play_array(np.zeros(256, dtype=np.float32)) is False
        assert "No output device could play audio" in player.last_error
        assert "no device available" in player.last_error, "must quote the cause"
        assert "WASAPI" in player.last_error or "exclusive" in player.last_error.lower()

    def test_missing_portaudio_returns_false(self, player):
        player._sounddevice_module = None
        assert player._play_array(np.zeros(8, dtype=np.float32)) is False
        assert "PortAudio unavailable" in player.last_error
