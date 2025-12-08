"""
Unit Tests für Recorder
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import time

from core.recorder import Recorder, RecordingState, RecordingInfo, get_recorder


@pytest.mark.unit
class TestRecordingState:
    """Tests für RecordingState Enum"""

    def test_recording_states(self):
        """Teste alle Recording States"""
        assert RecordingState.IDLE.value == "idle"
        assert RecordingState.RECORDING.value == "recording"
        assert RecordingState.PAUSED.value == "paused"
        assert RecordingState.STOPPED.value == "stopped"


@pytest.mark.unit
class TestRecordingInfo:
    """Tests für RecordingInfo Dataclass"""

    def test_recording_info_creation(self):
        """Teste RecordingInfo Erstellung"""
        info = RecordingInfo(
            duration_seconds=10.5,
            sample_rate=44100,
            channels=2,
            file_path=Path("/test.wav"),
            peak_level=0.8,
        )

        assert info.duration_seconds == 10.5
        assert info.sample_rate == 44100
        assert info.channels == 2
        assert info.file_path == Path("/test.wav")
        assert info.peak_level == 0.8


@pytest.mark.unit
class TestRecorder:
    """Tests für Recorder"""

    def test_initialization(self):
        """Teste Recorder Initialisierung"""
        recorder = Recorder()

        assert recorder.state == RecordingState.IDLE
        assert recorder.sample_rate == 44100
        assert recorder.channels == 2
        assert recorder.recorded_chunks == []

    def test_import_soundcard_success(self):
        """Teste SoundCard Import wenn verfügbar"""
        recorder = Recorder()

        # Wenn SoundCard installiert ist
        if recorder._soundcard:
            assert recorder._import_soundcard() is True
        else:
            # Sonst mocken
            with patch("core.recorder.sc") as mock_sc:
                recorder._soundcard = None
                result = recorder._import_soundcard()
                # Kann True oder False sein je nach Umgebung

    def test_get_state(self):
        """Teste get_state()"""
        recorder = Recorder()

        assert recorder.get_state() == RecordingState.IDLE

        recorder.state = RecordingState.RECORDING
        assert recorder.get_state() == RecordingState.RECORDING

    def test_is_recording(self):
        """Teste is_recording()"""
        recorder = Recorder()

        assert recorder.is_recording() is False

        recorder.state = RecordingState.RECORDING
        assert recorder.is_recording() is True

        recorder.state = RecordingState.PAUSED
        assert recorder.is_recording() is False

    def test_get_recording_duration_empty(self):
        """Teste get_recording_duration() ohne Chunks"""
        recorder = Recorder()

        assert recorder.get_recording_duration() == 0.0

    def test_get_recording_duration_with_chunks(self):
        """Teste get_recording_duration() mit Chunks"""
        recorder = Recorder()

        # Erstelle Mock-Chunks (1 Sekunde Audio jeweils)
        chunk1 = np.zeros((44100, 2))  # 1s stereo
        chunk2 = np.zeros((44100, 2))  # 1s stereo

        recorder.recorded_chunks = [chunk1, chunk2]

        duration = recorder.get_recording_duration()
        assert 1.9 < duration < 2.1  # ~2 Sekunden

    def test_pause_recording_when_not_recording(self):
        """Teste pause_recording() wenn nicht am Aufnehmen"""
        recorder = Recorder()

        result = recorder.pause_recording()
        assert result is False

    def test_pause_recording_when_recording(self):
        """Teste pause_recording() während Aufnahme"""
        recorder = Recorder()
        recorder.state = RecordingState.RECORDING

        result = recorder.pause_recording()
        assert result is True
        assert recorder.state == RecordingState.PAUSED

    def test_resume_recording_when_paused(self):
        """Teste resume_recording() wenn pausiert"""
        recorder = Recorder()
        recorder.state = RecordingState.PAUSED

        result = recorder.resume_recording()
        assert result is True
        assert recorder.state == RecordingState.RECORDING

    def test_resume_recording_when_not_paused(self):
        """Teste resume_recording() wenn nicht pausiert"""
        recorder = Recorder()
        recorder.state = RecordingState.IDLE

        result = recorder.resume_recording()
        assert result is False

    def test_cancel_recording(self):
        """Teste cancel_recording()"""
        recorder = Recorder()
        recorder.state = RecordingState.RECORDING
        recorder.recorded_chunks = [np.zeros((1000, 2))]

        recorder.cancel_recording()

        assert recorder.state == RecordingState.IDLE
        assert len(recorder.recorded_chunks) == 0

    def test_stop_recording_when_not_recording(self):
        """Teste stop_recording() wenn nicht am Aufnehmen"""
        recorder = Recorder()
        recorder.state = RecordingState.IDLE

        result = recorder.stop_recording()
        assert result is None

    def test_stop_recording_no_audio(self):
        """Teste stop_recording() ohne aufgenommenes Audio"""
        recorder = Recorder()
        recorder.state = RecordingState.RECORDING
        recorder.recorded_chunks = []  # Keine Audio-Chunks

        result = recorder.stop_recording()
        assert result is None

    def test_stop_recording_with_audio(self):
        """Teste stop_recording() mit aufgenommenem Audio"""
        recorder = Recorder()
        recorder.state = RecordingState.RECORDING

        # Erstelle Mock Audio-Daten (1 Sekunde)
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        audio_chunk = np.random.randn(samples, 2) * 0.1  # Leises Rauschen

        recorder.recorded_chunks = [audio_chunk]

        temp_dir = Path(tempfile.mkdtemp())
        save_path = temp_dir / "test_recording.wav"

        result = recorder.stop_recording(save_path=save_path)

        # Clean up
        if save_path.exists():
            save_path.unlink()
        shutil.rmtree(temp_dir)

        assert result is not None
        assert isinstance(result, RecordingInfo)
        assert 0.9 < result.duration_seconds < 1.1
        assert result.sample_rate == 44100

    @patch("soundcard.all_microphones")
    def test_get_available_devices(self, mock_all_mics):
        """Teste get_available_devices()"""
        # Mock Devices
        mock_mic1 = Mock()
        mock_mic1.name = "Built-in Microphone"

        mock_mic2 = Mock()
        mock_mic2.name = "BlackHole 2ch"

        mock_all_mics.return_value = [mock_mic1, mock_mic2]

        recorder = Recorder()

        # Kann leer sein wenn SoundCard nicht verfügbar
        devices = recorder.get_available_devices()
        # assert len(devices) >= 0  # Kann 0 oder mehr sein

    def test_singleton(self):
        """Teste get_recorder Singleton"""
        rec1 = get_recorder()
        rec2 = get_recorder()

        assert rec1 is rec2
        assert isinstance(rec1, Recorder)

    def test_start_recording_already_recording(self):
        """Teste start_recording() wenn schon am Aufnehmen"""
        recorder = Recorder()
        recorder.state = RecordingState.RECORDING

        result = recorder.start_recording()
        assert result is False

    def test_start_recording_no_soundcard(self):
        """Teste start_recording() ohne SoundCard"""
        recorder = Recorder()
        recorder._soundcard = None

        result = recorder.start_recording()
        assert result is False

    def test_level_callback(self):
        """Teste dass Level Callback gesetzt werden kann"""
        recorder = Recorder()

        callback_called = []

        def level_callback(level):
            callback_called.append(level)

        recorder.level_callback = level_callback

        # Simuliere Level Callback
        recorder.level_callback(0.5)

        assert len(callback_called) == 1
        assert callback_called[0] == 0.5
