"""
Unit Tests für File Manager
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import numpy as np
import soundfile as sf

from utils.file_manager import FileManager, get_file_manager
from config import SUPPORTED_AUDIO_FORMATS


@pytest.fixture
def temp_audio_dir():
    """Erstellt temporäres Verzeichnis mit Test-Audio-Dateien"""
    temp_dir = Path(tempfile.mkdtemp())

    # Erstelle Test-Audio-Datei (1 Sekunde, 44100 Hz, Stereo)
    sample_rate = 44100
    duration = 1.0
    samples = int(sample_rate * duration)

    # Generiere Sinus-Ton
    t = np.linspace(0, duration, samples)
    audio_data = np.sin(2 * np.pi * 440 * t)  # 440 Hz = A4
    stereo_data = np.column_stack([audio_data, audio_data])  # Stereo

    # Speichere als WAV
    wav_file = temp_dir / "test.wav"
    sf.write(str(wav_file), stereo_data, sample_rate)

    # Erstelle weitere Test-Dateien
    (temp_dir / "test.mp3").touch()  # Leere MP3 (nur für Format-Tests)
    (temp_dir / "test.txt").touch()  # Nicht-Audio-Datei

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.unit
class TestFileManager:
    """Tests für File Manager"""

    def test_singleton(self):
        """Teste ob FileManager korrekt funktioniert"""
        fm1 = FileManager()
        fm2 = get_file_manager()
        assert fm1 is not fm2  # FileManager ist KEIN Singleton
        assert isinstance(fm2, FileManager)

    def test_is_supported_format(self, temp_audio_dir):
        """Teste Format-Erkennung"""
        fm = FileManager()

        # Unterstützte Formate
        assert fm.is_supported_format(Path("test.wav"))
        assert fm.is_supported_format(Path("test.mp3"))
        assert fm.is_supported_format(Path("test.flac"))
        assert fm.is_supported_format(Path("test.m4a"))

        # Nicht unterstützte Formate
        assert not fm.is_supported_format(Path("test.txt"))
        assert not fm.is_supported_format(Path("test.pdf"))

    def test_is_supported_format_case_insensitive(self):
        """Teste dass Format-Erkennung case-insensitive ist"""
        fm = FileManager()
        assert fm.is_supported_format(Path("test.WAV"))
        assert fm.is_supported_format(Path("test.Mp3"))

    def test_get_audio_info_valid_file(self, temp_audio_dir):
        """Teste Audio-Info Extraktion für gültige Datei"""
        fm = FileManager()
        wav_file = temp_audio_dir / "test.wav"

        info = fm.get_audio_info(wav_file)

        assert info is not None
        assert "duration" in info
        assert "sample_rate" in info
        assert "channels" in info
        assert info["sample_rate"] == 44100
        assert info["channels"] == 2
        assert 0.9 < info["duration"] < 1.1  # ~1 Sekunde

    def test_get_audio_info_invalid_file(self, temp_audio_dir):
        """Teste Audio-Info für ungültige Datei"""
        fm = FileManager()
        txt_file = temp_audio_dir / "test.txt"

        info = fm.get_audio_info(txt_file)
        assert info is None

    def test_get_audio_info_nonexistent_file(self):
        """Teste Audio-Info für nicht-existierende Datei"""
        fm = FileManager()

        info = fm.get_audio_info(Path("/nonexistent/file.wav"))
        assert info is None

    def test_get_file_size_mb(self, temp_audio_dir):
        """Teste Dateigröße-Berechnung"""
        fm = FileManager()
        wav_file = temp_audio_dir / "test.wav"

        size_mb = fm.get_file_size_mb(wav_file)
        assert size_mb > 0
        assert size_mb < 1  # Sollte kleiner als 1 MB sein

    def test_validate_audio_file_valid(self, temp_audio_dir):
        """Teste Validierung für gültige Audio-Datei"""
        fm = FileManager()
        wav_file = temp_audio_dir / "test.wav"

        is_valid, error = fm.validate_audio_file(wav_file)
        assert is_valid is True
        assert error is None

    def test_validate_audio_file_not_found(self):
        """Teste Validierung für nicht-existierende Datei"""
        fm = FileManager()

        is_valid, error = fm.validate_audio_file(Path("/nonexistent.wav"))
        assert is_valid is False
        assert "not found" in error.lower()

    def test_validate_audio_file_unsupported_format(self, temp_audio_dir):
        """Teste Validierung für nicht-unterstütztes Format"""
        fm = FileManager()
        txt_file = temp_audio_dir / "test.txt"

        is_valid, error = fm.validate_audio_file(txt_file)
        assert is_valid is False
        assert "unsupported format" in error.lower()

    def test_list_audio_files(self, temp_audio_dir):
        """Teste Auflistung von Audio-Dateien"""
        fm = FileManager()

        audio_files = fm.list_audio_files(temp_audio_dir)

        # Sollte WAV finden (MP3 ist leer und könnte Probleme machen)
        assert len(audio_files) >= 1
        assert any(f.suffix == ".wav" for f in audio_files)
        # Sollte keine .txt Dateien enthalten
        assert not any(f.suffix == ".txt" for f in audio_files)

    def test_list_audio_files_empty_dir(self):
        """Teste Auflistung in leerem Verzeichnis"""
        fm = FileManager()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            audio_files = fm.list_audio_files(temp_dir)
            assert len(audio_files) == 0
        finally:
            shutil.rmtree(temp_dir)

    def test_cleanup_temp_files(self):
        """Teste Aufräumen von temporären Dateien"""
        fm = FileManager()

        # Erstelle Test-Datei im temp-Verzeichnis
        fm.temp_dir.mkdir(parents=True, exist_ok=True)
        test_file = fm.temp_dir / "test.txt"
        test_file.write_text("test")

        assert test_file.exists()

        # Cleanup
        fm.cleanup_temp_files()

        # Temp-Dir sollte existieren aber leer sein
        assert fm.temp_dir.exists()
        assert not test_file.exists()

    def test_temp_dir_creation(self):
        """Teste dass temp_dir automatisch erstellt wird"""
        fm = FileManager()
        assert fm.temp_dir.exists()
        assert fm.temp_dir.is_dir()

    def test_validate_audio_file_corrupted(self, temp_audio_dir):
        """Teste Validierung mit korrupter Audio-Datei"""
        from unittest.mock import patch

        fm = get_file_manager()

        audio_file = temp_audio_dir / "test.wav"

        # Mock get_audio_info um None zurückzugeben (simuliert korrupte Datei)
        with patch.object(fm, "get_audio_info", return_value=None):
            is_valid, error_msg = fm.validate_audio_file(audio_file)
            assert is_valid is False
            assert error_msg == "Could not read audio file"

    def test_cleanup_temp_files_error_handling(self):
        """Teste Error Handling in cleanup_temp_files"""
        from unittest.mock import patch

        fm = get_file_manager()

        # Mock shutil.rmtree um einen Error zu werfen
        with patch("shutil.rmtree", side_effect=PermissionError("Access denied")):
            # Sollte nicht crashen, nur loggen
            fm.cleanup_temp_files()
            # Temp dir sollte noch existieren
            assert fm.temp_dir.exists()
