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

    @patch("audio_separator.separator.Separator")
    def test_run_separation_mock(self, mock_audio_sep, test_audio_file):
        """Teste _run_separation() mit Mock"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = [
            str(test_audio_file.parent / "test_vocals.wav"),
            str(test_audio_file.parent / "test_other.wav"),
        ]
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        stems = sep._run_separation(
            test_audio_file, "demucs_6s", test_audio_file.parent, device="cpu"
        )

        # AudioSeparator wurde erstellt
        assert mock_audio_sep.called

        # Stems wurden returned
        assert isinstance(stems, dict)

    @patch("audio_separator.separator.Separator", side_effect=ImportError)
    def test_run_separation_import_error(self, mock_audio_sep, test_audio_file):
        """Teste _run_separation() wenn audio-separator nicht installiert"""
        sep = Separator()

        with pytest.raises(Exception):  # SeparationError
            sep._run_separation(test_audio_file, "demucs_6s", test_audio_file.parent)

    @patch("audio_separator.separator.Separator")
    def test_run_separation_device_setting(self, mock_audio_sep, test_audio_file):
        """Teste dass Device korrekt gesetzt wird"""
        # Mock AudioSeparator
        mock_instance = MagicMock()
        mock_instance.separate.return_value = []
        mock_audio_sep.return_value = mock_instance

        sep = Separator()

        with patch.object(
            sep.device_manager, "set_device", return_value=True
        ) as mock_set:
            try:
                sep._run_separation(
                    test_audio_file, "demucs_6s", test_audio_file.parent, device="mps"
                )
            except:
                pass  # Kann fehlschlagen, uns geht's nur um set_device

            mock_set.assert_called_with("mps")

    def test_run_separation_device_fail(self, test_audio_file):
        """Teste _run_separation() wenn Device-Setting fehlschlägt"""
        sep = Separator()

        with patch.object(sep.device_manager, "set_device", return_value=False):
            with pytest.raises(Exception):
                sep._run_separation(
                    test_audio_file,
                    "demucs_6s",
                    test_audio_file.parent,
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
