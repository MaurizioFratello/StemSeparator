"""
App context utilities for the GUI layer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from config import LOG_FILE, TEMP_DIR
from core.blackhole_installer import get_blackhole_installer, BlackHoleInstaller
from core.chunk_processor import ChunkProcessor, get_chunk_processor
from core.device_manager import DeviceManager, get_device_manager
from core.model_manager import ModelManager, get_model_manager
from core.recorder import Recorder, get_recorder
from core.separator import Separator, get_separator
from ui.settings_manager import SettingsManager, get_settings_manager
from utils.error_handler import ErrorHandler, error_handler
from utils.file_manager import FileManager, get_file_manager
from utils.i18n import get_language, set_language, t
from utils.logger import AppLogger, get_logger


class AppContext:
    """
    PURPOSE: Provide a single access point for backend singletons required by the GUI.
    CONTEXT: The core layer already applies singletons; the UI must reuse them to maintain
             consistent state (models, devices, recordings) and avoid redundant heavyweight
             initialisations.
    """

    def __init__(self) -> None:
        self._logger = get_logger()
        # WHY: Store frequently accessed paths so widgets avoid re-importing config everywhere.
        self._log_file = LOG_FILE
        self._temp_dir = TEMP_DIR

    def logger(self) -> AppLogger:
        """
        PURPOSE: Expose the shared application logger to GUI widgets.
        CONTEXT: Ensures all UI operations report through the central logging pipeline.
        """

        return self._logger

    def separator(self) -> Separator:
        """
        PURPOSE: Provide access to the stem separator singleton.
        CONTEXT: Upload, queue, and player widgets must trigger separations without creating
                 additional separator instances that would reinitialise models.
        """

        return get_separator()

    def recorder(self) -> Recorder:
        """
        PURPOSE: Provide access to the recorder singleton.
        CONTEXT: Recording UI controls need to manipulate recording state and threads consistently.
        """

        return get_recorder()

    def chunk_processor(self) -> ChunkProcessor:
        """
        PURPOSE: Provide access to the chunk processor singleton.
        CONTEXT: Queue and separation progress views rely on chunking hints and cleanup logic.
        """

        return get_chunk_processor()

    def model_manager(self) -> ModelManager:
        """
        PURPOSE: Provide access to the model manager singleton.
        CONTEXT: Upload widget must surface model metadata and trigger downloads on demand.
        """

        return get_model_manager()

    def device_manager(self) -> DeviceManager:
        """
        PURPOSE: Provide access to the device manager singleton.
        CONTEXT: Recording widget needs live device availability and the ability to switch hardware.
        """

        return get_device_manager()

    def file_manager(self) -> FileManager:
        """
        PURPOSE: Provide access to the file manager singleton.
        CONTEXT: Upload and player widgets need audio validation and file operations.
        """

        return get_file_manager()

    def settings_manager(self) -> SettingsManager:
        """
        PURPOSE: Provide access to the settings manager singleton.
        CONTEXT: UI components need to read/write user preferences like quality preset and model selection.
        """

        return get_settings_manager()

    def blackhole_installer(self) -> BlackHoleInstaller:
        """
        PURPOSE: Provide access to the BlackHole installer helper.
        CONTEXT: Recording setup UI informs the user about installation state and remediation.
        """

        return get_blackhole_installer()

    def error_handler(self) -> ErrorHandler:
        """
        PURPOSE: Surface the shared error handler for retry-aware operations.
        CONTEXT: GUI-triggered long-running tasks should reuse the existing retry strategies.
        """

        return error_handler

    def translate(self, key: str, fallback: str | None = None, **kwargs) -> str:
        """
        PURPOSE: Translate UI strings using the existing i18n infrastructure.
        CONTEXT: Keeps GUI text consistent with `resources/translations`.
        """

        return t(key, fallback=fallback, **kwargs)

    def t(self, key: str, fallback: str | None = None, **kwargs) -> str:
        """Alias for translate."""
        return self.translate(key, fallback, **kwargs)

    def set_language(self, language: str) -> None:
        """
        PURPOSE: Update global language preference and log the change.
        CONTEXT: Triggers re-translation of UI elements while keeping configuration consistent.
        """

        set_language(language)
        self._logger.info("UI language switched to %s", language)

    def get_language(self) -> str:
        """
        PURPOSE: Query the currently active language.
        CONTEXT: Used by widgets to determine which labels to render or which menu item is checked.
        """

        return get_language()

    def log_file(self) -> Path:
        """
        PURPOSE: Provide the central log file path.
        CONTEXT: File menu action opens logs for diagnostics without duplicate config imports.
        """

        return self._log_file

    def temp_dir(self) -> Path:
        """
        PURPOSE: Provide the base temporary directory.
        CONTEXT: GUI components store intermediate files (e.g., exported recordings, previews).
        """

        return self._temp_dir


_APP_CONTEXT = AppContext()


def get_app_context() -> AppContext:
    """
    PURPOSE: Return the singleton app context.
    CONTEXT: GUI modules import this helper to keep backend access consistent.
    """

    return _APP_CONTEXT

