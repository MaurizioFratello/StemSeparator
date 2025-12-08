"""
Detailliertes Logging-System mit File Rotation und farbiger Konsolen-Ausgabe
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

try:
    import colorlog

    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False

from config import LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_LEVEL


class AppLogger:
    """Singleton Logger für die gesamte Anwendung"""

    _instance: Optional["AppLogger"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger is not None:
            return

        self._logger = logging.getLogger("StemSeparator")
        self._logger.setLevel(getattr(logging, LOG_LEVEL))

        # Verhindere doppelte Handler
        if self._logger.handlers:
            return

        # File Handler mit Rotation
        self._setup_file_handler()

        # Console Handler mit Farben
        self._setup_console_handler()

    def _setup_file_handler(self):
        """Erstelle rotating file handler für detaillierte Logs"""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # File bekommt alles

        # Detailliertes Format für File
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        self._logger.addHandler(file_handler)

    def _setup_console_handler(self):
        """Erstelle farbigen console handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)  # Console nur INFO und höher

        if COLORLOG_AVAILABLE:
            # Farbige Ausgabe mit colorlog
            console_formatter = colorlog.ColoredFormatter(
                "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
                datefmt="%H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
        else:
            # Einfaches Format ohne Farben
            console_formatter = logging.Formatter("%(levelname)-8s %(message)s")

        console_handler.setFormatter(console_formatter)
        self._logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        """Gibt den konfigurierten Logger zurück"""
        return self._logger

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, exc_info=False, **kwargs):
        """Log error message"""
        self._logger.error(message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info=True, **kwargs):
        """Log critical message"""
        self._logger.critical(message, exc_info=exc_info, **kwargs)

    def log_separator_task(self, file_name: str, model: str, stems: int):
        """Spezielles Logging für Separation Tasks"""
        self.info(f"Starting separation: {file_name} | Model: {model} | Stems: {stems}")

    def log_chunk_progress(self, chunk_num: int, total_chunks: int, file_name: str):
        """Logging für Chunk-Verarbeitung"""
        self.info(f"Processing chunk {chunk_num}/{total_chunks} for {file_name}")

    def log_model_loading(self, model_name: str, device: str):
        """Logging für Model Loading"""
        self.info(f"Loading model '{model_name}' on device '{device}'")

    def log_error_with_context(self, error: Exception, context: dict):
        """Detailliertes Error Logging mit Kontext"""
        self.error(f"Error: {str(error)}")
        self.error(f"Context: {context}", exc_info=True)

    def log_performance(self, operation: str, duration_seconds: float):
        """Performance Logging"""
        self.debug(f"Performance: {operation} took {duration_seconds:.2f}s")


# Singleton Instance
logger = AppLogger()


def get_logger() -> AppLogger:
    """Helper function to get logger instance"""
    return logger


# Convenience functions
def debug(message: str, **kwargs):
    logger.debug(message, **kwargs)


def info(message: str, **kwargs):
    logger.info(message, **kwargs)


def warning(message: str, **kwargs):
    logger.warning(message, **kwargs)


def error(message: str, exc_info=False, **kwargs):
    logger.error(message, exc_info=exc_info, **kwargs)


def critical(message: str, exc_info=True, **kwargs):
    logger.critical(message, exc_info=exc_info, **kwargs)


if __name__ == "__main__":
    # Test logging
    info("Logger initialized successfully")
    debug("This is a debug message")
    warning("This is a warning")
    error("This is an error")

    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.log_error_with_context(e, {"test": "context"})
