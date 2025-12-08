"""
File Manager für Audio-Datei Operationen
"""

import os
from pathlib import Path
from typing import Optional, List
import soundfile as sf

from config import SUPPORTED_AUDIO_FORMATS, TEMP_DIR
from utils.logger import get_logger

logger = get_logger()


class FileManager:
    """Verwaltet Audio-Datei Operationen"""

    def __init__(self):
        self.temp_dir = TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def is_supported_format(self, file_path: Path) -> bool:
        """Prüft ob Dateiformat unterstützt wird"""
        return file_path.suffix.lower() in SUPPORTED_AUDIO_FORMATS

    def get_audio_info(self, file_path: Path) -> Optional[dict]:
        """
        Gibt Informationen über eine Audio-Datei zurück

        Returns:
            Dict mit duration, sample_rate, channels, format
        """
        try:
            info = sf.info(str(file_path))
            return {
                "duration": info.duration,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype,
                "frames": info.frames,
            }
        except Exception as e:
            logger.error(f"Error reading audio info from {file_path}: {e}")
            return None

    def get_file_size_mb(self, file_path: Path) -> float:
        """Gibt Dateigröße in MB zurück"""
        return file_path.stat().st_size / (1024 * 1024)

    def validate_audio_file(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """
        Validiert eine Audio-Datei

        Returns:
            (is_valid, error_message)
        """
        if not file_path.exists():
            return False, "File not found"

        if not self.is_supported_format(file_path):
            return False, f"Unsupported format: {file_path.suffix}"

        info = self.get_audio_info(file_path)
        if info is None:
            return False, "Could not read audio file"

        return True, None

    def list_audio_files(self, directory: Path) -> List[Path]:
        """Listet alle Audio-Dateien in einem Verzeichnis"""
        audio_files = []
        for ext in SUPPORTED_AUDIO_FORMATS:
            audio_files.extend(directory.glob(f"*{ext}"))
        return sorted(audio_files)

    def cleanup_temp_files(self):
        """Löscht temporäre Dateien"""
        try:
            import shutil

            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Temporary files cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")


# Globale Instanz
_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    """Gibt die globale FileManager-Instanz zurück"""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
    return _file_manager
