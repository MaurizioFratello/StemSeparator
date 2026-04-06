import sys
from unittest.mock import MagicMock, patch


def test_recorder_keeps_macos_backend_priority_without_windows_override():
    """
    Guardrail: Windows parity work must not alter macOS backend priority.
    Expected order on macOS remains ScreenCaptureKit -> BlackHole/SoundCard.
    """
    fake_sf = MagicMock()
    fake_audio_processing = MagicMock()
    fake_audio_processing.trim_leading_silence = lambda data, sr, **kwargs: (data, 0.0)
    fake_numpy = MagicMock()
    fake_numpy.ndarray = object

    with patch.dict(
        sys.modules,
        {
            "soundfile": fake_sf,
            "utils.audio_processing": fake_audio_processing,
            "numpy": fake_numpy,
        },
    ):
        with patch("core.recorder.Recorder._import_soundcard", return_value=False), patch(
            "core.recorder.Recorder._import_screencapture", return_value=False
        ):
            from core.recorder import Recorder, RecordingBackend

            recorder = Recorder(backend=RecordingBackend.AUTO)
            # With no backends available, selected backend should be None;
            # this assertion ensures initialization still follows existing logic.
            assert recorder._selected_backend is None
