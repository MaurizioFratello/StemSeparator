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
    USER_DIR,
    DEFAULT_QUALITY_PRESET,
    get_default_output_dir,
    DEFAULT_SEPARATED_DIR,
)
from utils.logger import get_logger
from utils.path_utils import resolve_output_path

logger = get_logger()


class SettingsManager:
    """
    Manages runtime user settings

    WHY: Separates mutable user preferences from immutable system defaults in config.py
    """

    def __init__(self):
        # Use USER_DIR for settings file (writable location)
        # WHY: In packaged apps, BASE_DIR is read-only (app bundle)
        #      USER_DIR is always writable (~/Library/Application Support/StemSeparator on macOS)
        self.settings_file = USER_DIR / "user_settings.json"
        self.settings: Dict[str, Any] = {}
        self._load_defaults()
        self._load_from_file()

        logger.info("SettingsManager initialized")

    def _load_defaults(self):
        """Load default settings from config.py"""
        # Use new default output directory: ~/Music/StemSeparator/separated
        default_output_dir = get_default_output_dir("separated")
        self.settings = {
            "language": DEFAULT_LANGUAGE,
            "default_model": DEFAULT_MODEL,
            "quality_preset": DEFAULT_QUALITY_PRESET,
            "use_gpu": USE_GPU,
            "chunk_length_seconds": CHUNK_LENGTH_SECONDS,
            "output_directory": str(default_output_dir),
            "recording_sample_rate": 44100,
            "recording_channels": 2,
            # WHY stored as names (not indices): PortAudio indices shift when
            # USB/Bluetooth devices attach, a device name stays stable across
            # those changes and across OS reboots.
            "playback_device": None,
            "recording_device": None,
        }

    def _load_from_file(self):
        """Load settings from user config file if it exists"""
        if not self.settings_file.exists():
            logger.debug("No user settings file found, using defaults")
            return

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                user_settings = json.load(f)

            # Migrate old default output directory to new default
            # WHY: Old default was TEMP_DIR/separated, new default is ~/Music/StemSeparator/separated
            needs_migration = False
            if "output_directory" in user_settings:
                old_path_str = user_settings["output_directory"]
                
                # Check if this matches the old default pattern
                old_default_pattern = TEMP_DIR / "separated"
                old_default_resolved = old_default_pattern.resolve()
                
                if old_path_str:
                    try:
                        old_path_resolved = Path(old_path_str).resolve()
                        # If saved path matches old default, migrate to new default
                        if old_path_resolved == old_default_resolved:
                            logger.info(
                                f"Migrating output directory from old default "
                                f"({old_path_resolved}) to new default ({DEFAULT_SEPARATED_DIR})"
                            )
                            user_settings["output_directory"] = str(DEFAULT_SEPARATED_DIR)
                            needs_migration = True
                    except (OSError, RuntimeError):
                        # Path resolution failed, might be relative or invalid
                        # Check if it's the old relative pattern
                        if "temp/separated" in old_path_str or "temp\\separated" in old_path_str:
                            logger.info(
                                f"Migrating relative output directory "
                                f"({old_path_str}) to new default ({DEFAULT_SEPARATED_DIR})"
                            )
                            user_settings["output_directory"] = str(DEFAULT_SEPARATED_DIR)
                            needs_migration = True

            # Update settings with user values
            self.settings.update(user_settings)
            
            # Save migrated settings if needed
            if needs_migration:
                self.save()
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

    def get_compute_device(self) -> str:
        """Pinned compute device: 'auto', 'cpu', 'cuda' or 'mps'."""
        value = self.settings.get("compute_device", "auto")
        return value if value in ("auto", "cpu", "cuda", "mps") else "auto"

    def set_compute_device(self, device: str):
        """Pin the compute device ('auto' restores automatic selection)."""
        if device not in ("auto", "cpu", "cuda", "mps"):
            device = "auto"
        self.settings["compute_device"] = device

    def get_playback_device(self) -> Optional[str]:
        """Name of the pinned audio output, or None for the system default."""
        return self.settings.get("playback_device")

    def set_playback_device(self, device: Optional[str]):
        """Pin an audio output by device name (None follows the system default)."""
        self.settings["playback_device"] = device

    def get_recording_device(self) -> Optional[str]:
        """Name of the pinned capture device (loopback or microphone), None = auto."""
        return self.settings.get("recording_device")

    def set_recording_device(self, device: Optional[str]):
        """Pin a capture device by name (None = platform system-audio device)."""
        self.settings["recording_device"] = device

    def get_chunk_length(self) -> int:
        """Get chunk length in seconds"""
        return self.settings.get("chunk_length_seconds", CHUNK_LENGTH_SECONDS)

    def set_chunk_length(self, seconds: int):
        """Set chunk length"""
        self.settings["chunk_length_seconds"] = seconds

    def get_output_directory(self) -> Path:
        """
        Get output directory, resolved to absolute path.

        WHY: Ensures path is absolute and directory exists, preventing issues
             with relative paths in packaged apps.
        """
        path_str = self.settings.get("output_directory", str(DEFAULT_SEPARATED_DIR))
        path = Path(path_str) if path_str else None

        # Resolve to absolute path, using default if path is invalid
        resolved = resolve_output_path(path, DEFAULT_SEPARATED_DIR)
        logger.debug(f"Output directory resolved to: {resolved}")
        return resolved

    def set_output_directory(self, path: Path):
        """
        Set output directory, ensuring it's resolved to absolute path.

        WHY: Saves absolute paths to prevent issues when loading settings later.
        """
        # Resolve to absolute before saving
        resolved = resolve_output_path(path, DEFAULT_SEPARATED_DIR)
        self.settings["output_directory"] = str(resolved)
        logger.debug(f"Output directory set to: {resolved}")

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
