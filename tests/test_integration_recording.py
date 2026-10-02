"""
Integration Tests: Recording → Separation Workflow

Testet den kompletten User-Workflow:
1. System Audio aufnehmen
2. Recording separieren
3. Stems validieren
"""

import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
import soundfile as sf

from core.recorder import Recorder, RecordingBackend, RecordingState, get_recorder
from core.separator import Separator
from core.blackhole_installer import get_blackhole_installer
from utils import platform_utils


class FakeCaptureStream:
    def __init__(self, audio_block):
        self.audio_block = audio_block
        self.record_started = threading.Event()
        self.allow_return = threading.Event()

    def record(self, numframes):
        self.record_started.set()
        self.allow_return.wait(timeout=1.0)
        return self.audio_block[:numframes].copy()


class FakeCaptureDevice:
    def __init__(self, name, stream):
        self.name = name
        self._stream = stream
        self.isloopback = True

    @contextmanager
    def recorder(self, **_kwargs):
        yield self._stream


class FakeSoundcard:
    def __init__(self, device):
        self.device = device
        self.all_microphones_calls = []

    def all_microphones(self, include_loopback=False):
        self.all_microphones_calls.append(include_loopback)
        return [self.device]

    def default_speaker(self):
        return SimpleNamespace(name="Test Speakers")


@pytest.fixture
def fake_system_capture(monkeypatch):
    """Deterministic loopback source; never accesses host audio hardware."""
    phase = np.arange(512, dtype=np.float32) * (2 * np.pi / 512)
    audio_block = np.column_stack((0.5 * np.sin(phase), 0.5 * np.sin(phase))).astype(
        np.float32
    )
    stream = FakeCaptureStream(audio_block)
    device = FakeCaptureDevice("Monitor of Test Speakers", stream)
    fake_soundcard = FakeSoundcard(device)

    monkeypatch.setattr(Recorder, "_import_screencapture", lambda self: False)
    monkeypatch.setattr(
        Recorder,
        "_import_soundcard",
        lambda self: setattr(self, "_soundcard", fake_soundcard) or True,
    )
    monkeypatch.setattr(platform_utils, "_platform_string", lambda: sys.platform)
    recorder = Recorder()
    recorder._selected_backend = (
        RecordingBackend.SYSTEM_LOOPBACK
        if sys.platform.startswith("linux")
        else RecordingBackend.WASAPI_LOOPBACK
    )
    yield recorder, stream, fake_soundcard


@pytest.fixture
def mock_blackhole_available(fake_system_capture):
    """Compatibility fixture backed by deterministic synthetic audio."""
    recorder, stream, _ = fake_system_capture
    with patch("core.recorder.get_recorder", return_value=recorder):
        stream.allow_return.set()
        yield recorder


@pytest.fixture(autouse=True)
def cleanup_recorder():
    """Reset Recorder vor UND nach jedem Test"""
    # Cleanup VOR Test (wichtig!)
    recorder = get_recorder()

    # Stoppe laufendes Recording komplett
    if recorder.get_state() in [RecordingState.RECORDING, RecordingState.PAUSED]:
        recorder._stop_event.set()
        recorder.state = RecordingState.IDLE

        # Warte auf Thread
        if recorder.recording_thread and recorder.recording_thread.is_alive():
            recorder.recording_thread.join(timeout=2.0)

    # Reset State
    recorder.recorded_chunks = []
    recorder._stop_event.clear()
    recorder.state = RecordingState.IDLE
    recorder.recording_thread = None

    yield

    # Cleanup nach Test (nochmal)
    if recorder.get_state() in [RecordingState.RECORDING, RecordingState.PAUSED]:
        recorder._stop_event.set()
        recorder.state = RecordingState.IDLE

        if recorder.recording_thread and recorder.recording_thread.is_alive():
            recorder.recording_thread.join(timeout=2.0)

    recorder.recorded_chunks = []
    recorder._stop_event.clear()
    recorder.state = RecordingState.IDLE
    recorder.recording_thread = None


@pytest.mark.integration
class TestRecordingToSeparationWorkflow:
    """Integration Tests für Recording → Separation"""

    def test_record_and_validate(self, mock_blackhole_available):
        """
        Testet Recording-Workflow:
        1. System Audio aufnehmen
        2. Recording validieren
        """
        #  1. Recording starten
        recorder = get_recorder()

        # Level Callback für Test
        level_callbacks = []

        def level_callback(level):
            level_callbacks.append(level)

        success = recorder.start_recording(level_callback=level_callback)
        assert success is True, "Recording sollte starten"
        assert recorder.is_recording() is True

        # 2. Kurz warten (simuliert Aufnahme)
        time.sleep(0.5)  # 500ms aufnehmen

        # Check dass Level Callbacks aufgerufen wurden
        assert len(level_callbacks) > 0, "Level Callbacks sollten aufgerufen werden"

        # 3. Recording stoppen und speichern
        temp_dir = Path(tempfile.mkdtemp())
        recording_path = temp_dir / "test_recording.wav"

        info = recorder.stop_recording(save_path=recording_path)

        assert info is not None, "Recording sollte Info zurückgeben"
        assert info.file_path.exists(), "Recording-Datei sollte existieren"
        assert (
            info.duration_seconds > 0.4
        ), f"Duration zu kurz: {info.duration_seconds}s"
        assert info.sample_rate == 44100
        assert info.channels == 2

        # 4. Lade Recording und validiere
        recorded_audio, sr = sf.read(str(info.file_path))
        assert len(recorded_audio) > 0, "Recording sollte Audio-Daten enthalten"
        assert sr == 44100

        # Cleanup
        shutil.rmtree(temp_dir)

        print(f"\n✓ Recording erfolgreich:")
        print(f"  - Duration: {info.duration_seconds:.2f}s")
        print(f"  - Sample Rate: {info.sample_rate}")
        print(f"  - Channels: {info.channels}")
        print(f"  - Peak Level: {info.peak_level:.3f}")
        print(f"  - Level Callbacks: {len(level_callbacks)}")

    def test_record_pause_resume(self, fake_system_capture):
        """Pause discards an in-flight backend block before it can be appended."""
        recorder, stream, _ = fake_system_capture

        assert recorder.start_recording() is True
        assert stream.record_started.wait(timeout=1.0)

        assert recorder.pause_recording() is True
        assert recorder.get_state() == RecordingState.PAUSED
        chunks_after_pause = len(recorder.recorded_chunks)
        stream.allow_return.set()
        time.sleep(0.15)
        assert len(recorder.recorded_chunks) == chunks_after_pause

        assert recorder.resume_recording() is True
        assert recorder.is_recording() is True
        time.sleep(0.15)
        assert len(recorder.recorded_chunks) > chunks_after_pause

        temp_dir = Path(tempfile.mkdtemp())
        try:
            info = recorder.stop_recording(save_path=temp_dir / "paused_recording.wav")
            assert info is not None
            assert info.duration_seconds > 0
        finally:
            shutil.rmtree(temp_dir)

    def test_record_cancel(self, mock_blackhole_available):
        """
        Testet Recording Cancel (ohne Separation)
        """
        recorder = get_recorder()

        # 1. Recording starten
        success = recorder.start_recording()
        assert success is True
        time.sleep(0.3)  # Etwas länger warten damit Chunks kommen

        # Check dass Chunks aufgenommen wurden (mindestens 1)
        chunks_before_cancel = len(recorder.recorded_chunks)
        assert (
            chunks_before_cancel > 0
        ), f"Sollte Chunks haben, hat aber {chunks_before_cancel}"

        # 2. Cancel
        recorder.cancel_recording()

        # 3. Validierung
        assert recorder.get_state() == RecordingState.IDLE
        assert len(recorder.recorded_chunks) == 0, "Chunks sollten gelöscht sein"

        print(f"\n✓ Cancel funktioniert:")
        print(f"  - Chunks vor Cancel: {chunks_before_cancel}")
        print(f"  - Chunks nach Cancel: 0")

    @pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
    def test_record_without_blackhole(self, monkeypatch, platform):
        """BlackHole is required only on macOS; other OSes use loopback capture."""
        phase = np.arange(512, dtype=np.float32) * (2 * np.pi / 512)
        stream = FakeCaptureStream(
            np.column_stack((0.5 * np.sin(phase), 0.5 * np.sin(phase))).astype(
                np.float32
            )
        )
        device = (
            FakeCaptureDevice("Test Microphone", stream)
            if platform == "darwin"
            else FakeCaptureDevice("Monitor of Test Speakers", stream)
        )
        fake_soundcard = FakeSoundcard(device)
        monkeypatch.setattr(platform_utils, "_platform_string", lambda: platform)
        monkeypatch.setattr(Recorder, "_import_screencapture", lambda self: False)
        monkeypatch.setattr(
            Recorder,
            "_import_soundcard",
            lambda self: setattr(self, "_soundcard", fake_soundcard) or True,
        )
        recorder = Recorder()
        stream.allow_return.set()

        if platform == "darwin":
            assert recorder._selected_backend is RecordingBackend.BLACKHOLE
            assert recorder.start_recording() is False
            assert "BlackHole" in recorder.last_error
        else:
            expected_backend = (
                RecordingBackend.SYSTEM_LOOPBACK
                if platform == "linux"
                else RecordingBackend.WASAPI_LOOPBACK
            )
            assert recorder._selected_backend is expected_backend
            assert recorder.start_recording() is True
            assert fake_soundcard.all_microphones_calls
            recorder.cancel_recording()

    def test_blackhole_installation_check(self):
        """
        Testet BlackHole Installation Status Check
        """
        installer = get_blackhole_installer()

        # Check Status (real - kann installiert sein oder nicht)
        status = installer.get_status()

        assert status is not None
        assert isinstance(status.installed, bool)
        assert isinstance(status.homebrew_available, bool)

        if status.installed:
            assert status.version is not None
            print(f"\n✓ BlackHole installiert: {status.version}")
        else:
            print(f"\n✓ BlackHole nicht installiert")
            if status.error_message:
                print(f"  - Grund: {status.error_message}")

    def test_record_has_reasonable_duration(self, mock_blackhole_available):
        """
        Testet dass Recording eine sinnvolle Duration hat

        HINWEIS: Genaue Duration-Tests sind schwierig mit Mock-Recorder,
        da der Mock in While-Loop kontinuierlich Audio generiert.
        Dieser Test prüft nur dass Recording grundsätzlich funktioniert.
        """
        recorder = get_recorder()

        # Starte Recording
        recorder.start_recording()

        # Nehme kurz auf
        time.sleep(0.3)

        # Stoppe
        temp_dir = Path(tempfile.mkdtemp())
        recording_path = temp_dir / "duration_test.wav"
        info = recorder.stop_recording(save_path=recording_path)

        # Validiere dass Recording stattfand
        assert info is not None
        assert info.duration_seconds > 0, "Duration sollte > 0 sein"
        assert info.file_path.exists(), "Recording-Datei sollte existieren"

        # Cleanup
        shutil.rmtree(temp_dir)

        print(f"\n✓ Recording hat Duration:")
        print(f"  - Duration: {info.duration_seconds:.2f}s")
        print(f"  - Sample Rate: {info.sample_rate}")
        print(f"  - Channels: {info.channels}")

    def test_record_peak_level_detection(self, fake_system_capture):
        """A known synthetic sine produces its known peak without host capture."""
        recorder, stream, _ = fake_system_capture
        stream.allow_return.set()

        assert recorder.start_recording() is True
        time.sleep(0.15)

        temp_dir = Path(tempfile.mkdtemp())
        try:
            info = recorder.stop_recording(save_path=temp_dir / "peak_test.wav")
            assert info is not None
            assert info.peak_level == pytest.approx(0.5, abs=1e-6)
        finally:
            shutil.rmtree(temp_dir)

    def test_multiple_recordings_sequential(self, mock_blackhole_available):
        """
        Testet mehrere Recordings nacheinander
        """
        recorder = get_recorder()
        temp_dir = Path(tempfile.mkdtemp())

        recordings = []

        # Nehme 3 Recordings auf
        for i in range(3):
            # Start
            success = recorder.start_recording()
            assert success is True

            # Record
            time.sleep(0.2)

            # Stop
            recording_path = temp_dir / f"recording_{i}.wav"
            info = recorder.stop_recording(save_path=recording_path)

            assert info is not None
            assert info.file_path.exists()
            recordings.append(info)

        # Validiere alle Recordings
        assert len(recordings) == 3

        for i, info in enumerate(recordings):
            assert info.duration_seconds > 0.1
            assert info.file_path.exists()
            print(f"  - Recording {i}: {info.duration_seconds:.2f}s")

        # Cleanup
        shutil.rmtree(temp_dir)

        print(f"\n✓ Multiple Sequential Recordings erfolgreich")

    def test_recording_already_recording(self, mock_blackhole_available):
        """
        Testet dass zweites start_recording() während Recording fehlschlägt
        """
        recorder = get_recorder()

        # Erstes Recording starten
        success1 = recorder.start_recording()
        assert success1 is True

        # Zweites Recording versuchen (sollte fehlschlagen)
        success2 = recorder.start_recording()
        assert success2 is False, "Zweites Recording sollte fehlschlagen"

        # Stop
        temp_dir = Path(tempfile.mkdtemp())
        recorder.stop_recording(save_path=temp_dir / "test.wav")
        shutil.rmtree(temp_dir)

        print("\n✓ Doppeltes Recording wird verhindert")

    def test_recording_state_transitions(self, mock_blackhole_available):
        """
        Testet State-Übergänge während Recording
        """
        recorder = get_recorder()

        # Initial: IDLE
        assert recorder.get_state() == RecordingState.IDLE

        # Start Recording
        recorder.start_recording()
        assert recorder.get_state() == RecordingState.RECORDING
        time.sleep(0.1)

        # Pause
        recorder.pause_recording()
        assert recorder.get_state() == RecordingState.PAUSED

        # Resume
        recorder.resume_recording()
        assert recorder.get_state() == RecordingState.RECORDING
        time.sleep(0.1)

        # Stop
        temp_dir = Path(tempfile.mkdtemp())
        recorder.stop_recording(save_path=temp_dir / "state_test.wav")
        assert recorder.get_state() == RecordingState.IDLE

        # Cleanup
        shutil.rmtree(temp_dir)

        print("\n✓ State Transitions funktionieren korrekt")


@pytest.mark.integration
@pytest.mark.slow
class TestRecordingToSeparationEndToEnd:
    """End-to-End Tests: Recording → Separation"""

    def test_record_and_separate_workflow(self, mock_blackhole_available):
        """
        End-to-End Test: Kompletter Workflow Recording → Separation

        Workflow:
        1. System Audio aufnehmen (Mock)
        2. Recording als WAV speichern
        3. WAV mit Separator verarbeiten
        4. Stems validieren
        """
        # 1. Recording starten
        recorder = get_recorder()
        success = recorder.start_recording()
        assert success is True

        # Nehme Audio auf
        time.sleep(1.0)  # 1 Sekunde

        # Stoppe Recording
        temp_dir = Path(tempfile.mkdtemp())
        recording_path = temp_dir / "test_recording.wav"
        info = recorder.stop_recording(save_path=recording_path)

        assert info is not None
        assert info.file_path.exists()
        assert info.duration_seconds > 0.5

        # 2. Separation durchführen
        separator = Separator()

        # Mock die eigentliche Separation
        def mock_run_separation(
            audio_file, model_id, output_dir, quality_preset, **kwargs
        ):
            """Mock für _run_separation - erstellt Dummy-Stems."""
            stems = {}
            for stem_name in ["vocals", "drums", "bass", "other"]:
                stem_file = output_dir / f"{audio_file.stem}_{stem_name}.wav"
                # Kopiere Original als Mock-Stem
                shutil.copy(str(audio_file), str(stem_file))
                stems[stem_name] = stem_file  # Return Path not str
            return stems

        with patch(
            "core.separator.Separator._run_separation", side_effect=mock_run_separation
        ):
            # Rufe Separation auf
            result = separator.separate(audio_file=info.file_path, model_id="demucs_4s")

            # 3. Validierung
            assert (
                result.success is True
            ), f"Separation fehlgeschlagen: {result.error_message}"
            assert len(result.stems) >= 4, f"Zu wenige Stems: {len(result.stems)}"

            # Prüfe dass alle Stems existieren
            for stem_name, stem_path in result.stems.items():
                assert stem_path.exists(), f"Stem {stem_name} nicht gefunden"

                # Lade Stem und prüfe Inhalt
                stem_audio, sr = sf.read(str(stem_path))
                assert len(stem_audio) > 0, f"Stem {stem_name} ist leer"

        # Cleanup
        shutil.rmtree(temp_dir)

        print(f"\n✓ End-to-End Workflow erfolgreich:")
        print(f"  - Recording: {info.duration_seconds:.2f}s")
        print(f"  - Stems: {len(result.stems)}")

    def test_record_and_separate_with_error(self, mock_blackhole_available):
        """
        Test Error Handling im End-to-End Workflow
        """
        # 1. Recording
        recorder = get_recorder()
        recorder.start_recording()
        time.sleep(0.5)

        temp_dir = Path(tempfile.mkdtemp())
        recording_path = temp_dir / "error_test.wav"
        info = recorder.stop_recording(save_path=recording_path)

        assert info is not None

        # 2. Separation mit Error
        separator = Separator()

        with patch("core.separator.Separator._run_separation") as mock_run_sep:
            # Mock wirft Error
            mock_run_sep.side_effect = RuntimeError("Simulated separation error")

            # Separator sollte Error graceful handhaben
            result = separator.separate(info.file_path)

            # Sollte als fehlgeschlagen markiert sein
            assert result.success is False
            assert result.error_message is not None
            assert (
                "failed" in result.error_message.lower()
                or "error" in result.error_message.lower()
            )

        # Cleanup
        shutil.rmtree(temp_dir)

        print(f"\n✓ Error Handling funktioniert:")
        print(f"  - Error: {result.error_message}")


@pytest.mark.integration
@pytest.mark.slow
class TestRecordingPerformance:
    """Performance-Tests für Recording"""

    def test_recording_memory_usage(self, mock_blackhole_available):
        """
        Testet dass Memory Usage während Recording kontrolliert bleibt

        HINWEIS: Nur für längere Recordings relevant
        """
        import psutil
        import os

        process = psutil.Process(os.getpid())

        recorder = get_recorder()

        # Memory vor Recording
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # Recording (länger)
        recorder.start_recording()
        time.sleep(2.0)  # 2 Sekunden

        # Memory während Recording
        mem_during = process.memory_info().rss / 1024 / 1024  # MB

        # Stop
        temp_dir = Path(tempfile.mkdtemp())
        info = recorder.stop_recording(save_path=temp_dir / "mem_test.wav")

        # Memory nach Recording
        mem_after = process.memory_info().rss / 1024 / 1024  # MB

        # Memory-Anstieg sollte moderat sein
        mem_increase = mem_during - mem_before

        # Bei 2s Recording @ 44.1kHz stereo: ~350KB Audio-Daten
        # Memory-Anstieg sollte < 50 MB sein
        assert mem_increase < 50, f"Memory-Anstieg zu hoch: {mem_increase:.1f} MB"

        # Cleanup
        shutil.rmtree(temp_dir)

        print(f"\n✓ Memory Usage:")
        print(f"  - Before: {mem_before:.1f} MB")
        print(f"  - During: {mem_during:.1f} MB")
        print(f"  - After:  {mem_after:.1f} MB")
        print(f"  - Increase: {mem_increase:.1f} MB")
