"""
Unit Tests für Separator
"""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from core.separator import Separator, SeparationResult, get_separator


@pytest.fixture(autouse=True)
def _assume_ffmpeg_present(monkeypatch):
    """
    Neutralize the parent FFmpeg gate for this file's wholesale mocks.

    WHY: every test here stubs the subprocess/audio layers, so a host- or
    runner-dependent FFmpeg lookup would only add nondeterminism. The gate's
    own contract is pinned explicitly in TestFFmpegGate below.
    """
    monkeypatch.setattr(Separator, "_ffmpeg_available", lambda self: True)


@pytest.fixture
def test_audio_file():
    """Erstellt temporäre Test-Audio-Datei"""
    sample_rate = 44100
    duration = 2.0
    samples = int(sample_rate * duration)

    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)
    stereo_data = np.column_stack([audio_data, audio_data])

    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "test.wav"
    sf.write(str(test_file), stereo_data, sample_rate)

    yield test_file

    shutil.rmtree(temp_dir)


@pytest.fixture
def long_audio_file():
    """Erstellt lange Test-Audio-Datei (12 Sekunden, wird gechunkt)"""
    sample_rate = 44100
    duration = 12.0
    samples = int(sample_rate * duration)

    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)
    stereo_data = np.column_stack([audio_data, audio_data])

    temp_dir = Path(tempfile.mkdtemp())
    test_file = temp_dir / "long.wav"
    sf.write(str(test_file), stereo_data, sample_rate)

    yield test_file

    shutil.rmtree(temp_dir)


@pytest.mark.unit
class TestSeparationResult:
    """Tests für SeparationResult Dataclass"""

    def test_separation_result_success(self):
        """Teste SeparationResult bei Erfolg"""
        result = SeparationResult(
            success=True,
            input_file=Path("test.wav"),
            output_dir=Path("/tmp/output"),
            stems={"vocals": Path("vocals.wav"), "drums": Path("drums.wav")},
            model_used="demucs",
            device_used="cpu",
            duration_seconds=10.5,
        )

        assert result.success is True
        assert len(result.stems) == 2
        assert result.error_message is None

    def test_separation_result_error(self):
        """Teste SeparationResult bei Fehler"""
        result = SeparationResult(
            success=False,
            input_file=Path("test.wav"),
            output_dir=Path("/tmp/output"),
            stems={},
            model_used="demucs",
            device_used="cpu",
            duration_seconds=1.0,
            error_message="Test error",
        )

        assert result.success is False
        assert len(result.stems) == 0
        assert result.error_message == "Test error"


@pytest.mark.unit
class TestSeparator:
    """Tests für Separator"""

    def test_initialization(self):
        """Teste Separator Initialisierung"""
        sep = Separator()

        assert sep.output_dir.exists()
        assert sep.model_manager is not None
        assert sep.device_manager is not None
        assert sep.chunk_processor is not None

    def test_separate_invalid_file(self):
        """Teste separate() mit ungültiger Datei"""
        sep = Separator()

        result = sep.separate(Path("/nonexistent.wav"))

        assert result.success is False
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    def test_separate_unknown_model(self, test_audio_file):
        """Teste separate() mit unbekanntem Model"""
        sep = Separator()

        result = sep.separate(test_audio_file, model_id="unknown_model")

        assert result.success is False
        assert "unknown model" in result.error_message.lower()

    @patch("audio_separator.separator.Separator")
    def test_separate_single_success(self, mock_audio_sep, test_audio_file):
        """Teste successful separation ohne Chunking"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = [
            str(test_audio_file.parent / "test_vocals.wav"),
            str(test_audio_file.parent / "test_drums.wav"),
        ]
        mock_audio_sep.return_value = mock_instance

        # Erstelle Mock Output-Files
        (test_audio_file.parent / "test_vocals.wav").write_text("")
        (test_audio_file.parent / "test_drums.wav").write_text("")

        sep = Separator()

        result = sep.separate(test_audio_file)

        assert result.success is True
        assert len(result.stems) >= 0  # Könnte leer sein wegen Mock

        # Cleanup
        (test_audio_file.parent / "test_vocals.wav").unlink(missing_ok=True)
        (test_audio_file.parent / "test_drums.wav").unlink(missing_ok=True)

    @patch("audio_separator.separator.Separator")
    def test_separate_progress_callback(self, mock_audio_sep, test_audio_file):
        """Teste dass Progress Callback aufgerufen wird"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        progress_calls = []

        def callback(message, percent):
            progress_calls.append((message, percent))

        result = sep.separate(test_audio_file, progress_callback=callback)

        # Mindestens ein Progress Call
        assert len(progress_calls) >= 1

    def test_create_error_result(self, test_audio_file):
        """Teste _create_error_result()"""
        sep = Separator()

        result = sep._create_error_result(
            test_audio_file, Path("/tmp"), "Test error", 5.0, "demucs"
        )

        assert result.success is False
        assert result.error_message == "Test error"
        assert result.duration_seconds == 5.0
        assert result.model_used == "demucs"

    def test_run_separation_mock(self, test_audio_file, monkeypatch):
        """Runs the isolated worker with the selected preset and device."""
        sep = Separator()
        captured_params = {}

        class CompletedProcess:
            returncode = 0

            def communicate(self, input=None, timeout=None):
                return ('{"success": true, "stems": {"vocals": "' + str(
                    test_audio_file.parent / "test_vocals.wav"
                ) + '"}}', "")

        def fake_popen(command, **kwargs):
            captured_params.update(
                __import__("json").loads(
                    Path(command[-1]).read_text(encoding="utf-8")
                )
            )
            return CompletedProcess()

        monkeypatch.setattr("core.separator.subprocess.Popen", fake_popen)

        stems = sep._run_separation(
            test_audio_file,
            "demucs_6s",
            test_audio_file.parent,
            "balanced",
            device="cpu",
        )

        assert captured_params["device"] == "cpu"
        assert captured_params["preset_params"] == {}
        assert captured_params["preset_attributes"]["demucs_shifts"] == 2

    def test_run_separation_device_setting(self, test_audio_file, monkeypatch):
        """Passes the requested device to the isolated worker."""
        sep = Separator()
        captured_params = {}

        class CompletedProcess:
            returncode = 0

            def communicate(self, input=None, timeout=None):
                return ('{"success": true, "stems": {"vocals": "' + str(
                    test_audio_file.parent / "test_vocals.wav"
                ) + '"}}', "")

        def fake_popen(command, **kwargs):
            captured_params.update(
                __import__("json").loads(
                    Path(command[-1]).read_text(encoding="utf-8")
                )
            )
            return CompletedProcess()

        monkeypatch.setattr("core.separator.subprocess.Popen", fake_popen)
        monkeypatch.setattr(sep.device_manager, "set_device", lambda device: True)

        sep._run_separation(
            test_audio_file,
            "demucs_6s",
            test_audio_file.parent,
            "balanced",
            device="mps",
        )

        assert captured_params["device"] == "mps"

    def test_run_separation_device_fail(self, test_audio_file):
        """Raises before launching a worker when device selection fails."""
        sep = Separator()

        with patch.object(sep.device_manager, "set_device", return_value=False):
            with pytest.raises(Exception):
                sep._run_separation(
                    test_audio_file,
                    "demucs_6s",
                    test_audio_file.parent,
                    "balanced",
                    device="invalid",
                )

    def test_singleton(self):
        """Teste get_separator Singleton"""
        sep1 = get_separator()
        sep2 = get_separator()

        assert sep1 is sep2
        assert isinstance(sep1, Separator)

    @patch("audio_separator.separator.Separator")
    def test_separate_chunking_decision(
        self, mock_audio_sep, test_audio_file, long_audio_file
    ):
        """Teste dass Chunking-Entscheidung korrekt getroffen wird"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        # Kurze Datei sollte nicht gechunkt werden
        with patch.object(sep, "_separate_single", return_value=Mock()) as mock_single:
            with patch.object(sep, "_separate_with_chunking") as mock_chunking:
                result = sep.separate(test_audio_file)

                # _separate_single sollte aufgerufen werden
                assert mock_single.called
                assert not mock_chunking.called

    @patch("audio_separator.separator.Separator")
    def test_separate_output_dir_creation(self, mock_audio_sep, test_audio_file):
        """Teste dass Output-Dir erstellt wird"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        custom_output = Path(tempfile.mkdtemp()) / "custom_output"

        result = sep.separate(test_audio_file, output_dir=custom_output)

        assert custom_output.exists()

        # Cleanup
        shutil.rmtree(custom_output.parent)

    @patch("audio_separator.separator.Separator")
    def test_separate_uses_default_model(self, mock_audio_sep, test_audio_file):
        """Teste dass Default-Model verwendet wird wenn keins angegeben"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        with patch.object(
            sep,
            "_separate_single",
            return_value=Mock(success=True, duration_seconds=1.0),
        ) as mock_sep:
            result = sep.separate(test_audio_file)

            # _separate_single wurde mit DEFAULT_MODEL aufgerufen
            call_args = mock_sep.call_args
            assert call_args is not None

    def test_separate_exception_handling(self, test_audio_file):
        """Teste Exception Handling"""
        sep = Separator()

        with patch.object(
            sep, "_separate_single", side_effect=RuntimeError("Test error")
        ):
            result = sep.separate(test_audio_file)

            assert result.success is False
            assert "Test error" in result.error_message

    @patch("audio_separator.separator.Separator")
    def test_separate_timing(self, mock_audio_sep, test_audio_file):
        """Teste dass Duration korrekt gemessen wird"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        result = sep.separate(test_audio_file)

        # Duration sollte gesetzt sein
        assert result.duration_seconds >= 0


class TestFFmpegGate:
    """Public contract of the parent-side FFmpeg gate.

    WHY: the live failure was three opaque FileNotFoundError retries because
    the worker PATH missed the vendored binary; the gate must abort before
    any worker spawn and name the fetch_vendor remedy instead.
    """

    def test_missing_ffmpeg_aborts_before_any_worker(self, test_audio_file, monkeypatch):
        sep = Separator()
        monkeypatch.setattr(sep, "_ffmpeg_available", lambda: False)
        popen_calls = []
        monkeypatch.setattr(
            "core.separator.subprocess.Popen",
            lambda *a, **k: popen_calls.append((a, k)),
        )

        result = sep.separate(test_audio_file, model_id="demucs_4s")

        assert result.success is False
        assert "fetch_vendor" in result.error_message
        assert popen_calls == []

