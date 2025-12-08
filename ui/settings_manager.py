"""
Settings Manager - Runtime configuration management

PURPOSE: Manage user preferences without mutating config.py.
CONTEXT: Provides in-memory settings that can be persisted to user config file.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import json

from config import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    USE_GPU,
    CHUNK_LENGTH_SECONDS,
    TEMP_DIR,
    BASE_DIR,
    DEFAULT_QUALITY_PRESET,
)
from utils.logger import get_logger

logger = get_logger()


class SettingsManager:
    """
    Manages runtime user settings

    WHY: Separates mutable user preferences from immutable system defaults in config.py
    """

    def __init__(self):
        self.settings_file = BASE_DIR / "user_settings.json"
        self.settings: Dict[str, Any] = {}
        self._load_defaults()
        self._load_from_file()

        logger.info("SettingsManager initialized")

    def _load_defaults(self):
        """Load default settings from config.py"""
        self.settings = {
            "language": DEFAULT_LANGUAGE,
            "default_model": DEFAULT_MODEL,
            "quality_preset": DEFAULT_QUALITY_PRESET,
            "use_gpu": USE_GPU,
            "chunk_length_seconds": CHUNK_LENGTH_SECONDS,
            "output_directory": str(TEMP_DIR / "separated"),
            "recording_sample_rate": 44100,
            "recording_channels": 2,
        }

    def _load_from_file(self):
        """Load settings from user config file if it exists"""
        if not self.settings_file.exists():
            logger.debug("No user settings file found, using defaults")
            return

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                user_settings = json.load(f)

            # Update settings with user values
            self.settings.update(user_settings)
            logger.info(f"Loaded user settings from {self.settings_file}")

        except Exception as e:
            logger.error(f"Error loading user settings: {e}", exc_info=True)

    def save(self) -> bool:
        """
        Save settings to file

        WHY: Persists user preferences across application restarts
        """
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)

            logger.info(f"Saved user settings to {self.settings_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving user settings: {e}", exc_info=True)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value"""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        """Set setting value"""
        self.settings[key] = value

    def get_language(self) -> str:
        """Get current language"""
        return self.settings.get("language", DEFAULT_LANGUAGE)

    def set_language(self, language: str):
        """Set language"""
        self.settings["language"] = language

    def get_default_model(self) -> str:
        """Get default model"""
        return self.settings.get("default_model", DEFAULT_MODEL)

    def set_default_model(self, model_id: str):
        """Set default model"""
        self.settings["default_model"] = model_id

    def get_use_gpu(self) -> bool:
        """Get GPU usage preference"""
        return self.settings.get("use_gpu", USE_GPU)

    def set_use_gpu(self, use_gpu: bool):
        """Set GPU usage preference"""
        self.settings["use_gpu"] = use_gpu

    def get_chunk_length(self) -> int:
        """Get chunk length in seconds"""
        return self.settings.get("chunk_length_seconds", CHUNK_LENGTH_SECONDS)

    def set_chunk_length(self, seconds: int):
        """Set chunk length"""
        self.settings["chunk_length_seconds"] = seconds

    def get_output_directory(self) -> Path:
        """Get output directory"""
        path_str = self.settings.get("output_directory", str(TEMP_DIR / "separated"))
        return Path(path_str)

    def set_output_directory(self, path: Path):
        """Set output directory"""
        self.settings["output_directory"] = str(path)

    def get_quality_preset(self) -> str:
        """Get quality preset"""
        return self.settings.get("quality_preset", DEFAULT_QUALITY_PRESET)

    def set_quality_preset(self, preset: str):
        """Set quality preset"""
        self.settings["quality_preset"] = preset


# Global instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
