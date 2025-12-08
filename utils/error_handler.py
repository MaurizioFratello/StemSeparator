"""
Intelligenter Error Handler mit Retry-Logik und Fallback-Strategien
"""

import time
import traceback
from enum import Enum
from typing import Callable, Any, Optional, Dict
from functools import wraps

from config import MAX_RETRIES, RETRY_STRATEGIES
from utils.logger import get_logger

logger = get_logger()


class ErrorType(Enum):
    """Kategorisierung von Fehlern"""

    GPU_MEMORY = "gpu_memory"
    CPU_MEMORY = "cpu_memory"
    MODEL_LOADING = "model_loading"
    AUDIO_PROCESSING = "audio_processing"
    FILE_IO = "file_io"
    NETWORK = "network"
    UNKNOWN = "unknown"


class SeparationError(Exception):
    """Basis-Exception für Separation-Fehler"""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        context: dict = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.context = context or {}


class GPUMemoryError(SeparationError):
    """GPU Memory erschöpft"""

    def __init__(self, message: str, context: dict = None):
        super().__init__(message, ErrorType.GPU_MEMORY, context)


class CPUMemoryError(SeparationError):
    """CPU Memory erschöpft"""

    def __init__(self, message: str, context: dict = None):
        super().__init__(message, ErrorType.CPU_MEMORY, context)


class ModelLoadingError(SeparationError):
    """Fehler beim Model Loading"""

    def __init__(self, message: str, context: dict = None):
        super().__init__(message, ErrorType.MODEL_LOADING, context)


class ErrorHandler:
    """Intelligenter Error Handler mit Fallback-Strategien"""

    def __init__(self, max_retries: int = MAX_RETRIES):
        self.max_retries = max_retries
        self.logger = logger

    def retry_with_fallback(
        self, func: Callable, *args, strategies: Optional[list] = None, **kwargs
    ) -> Any:
        """
        Führt Funktion mit Retry-Strategien aus

        Retry-Strategie:
        1. Versuch: GPU (MPS) mit normaler Chunk-Länge
        2. Versuch: CPU mit normaler Chunk-Länge
        3. Versuch: CPU mit halber Chunk-Länge

        Args:
            func: Auszuführende Funktion
            strategies: Liste von Strategien (device, chunk_length)
            *args, **kwargs: Argumente für die Funktion

        Returns:
            Ergebnis der Funktion

        Raises:
            SeparationError: Wenn alle Strategien fehlschlagen
        """
        strategies = strategies or RETRY_STRATEGIES
        last_error = None

        for attempt, strategy in enumerate(strategies, 1):
            try:
                self.logger.info(
                    f"Attempt {attempt}/{len(strategies)} with strategy: {strategy}"
                )

                # Update kwargs mit aktueller Strategie
                kwargs.update(strategy)

                # Führe Funktion aus
                result = func(*args, **kwargs)

                self.logger.info(f"Success on attempt {attempt}")
                return result

            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)

                self.logger.warning(
                    f"Attempt {attempt} failed: {error_type.value} - {str(e)}"
                )

                # Log detaillierte Infos
                self.logger.debug(f"Strategy was: {strategy}")
                self.logger.debug(f"Error traceback: {traceback.format_exc()}")

                # Wenn es der letzte Versuch war, raise
                if attempt >= len(strategies):
                    self.logger.error(
                        f"All {len(strategies)} retry attempts failed", exc_info=True
                    )
                    raise SeparationError(
                        f"Processing failed after {len(strategies)} attempts",
                        error_type=error_type,
                        context={
                            "last_error": str(last_error),
                            "attempted_strategies": strategies,
                        },
                    ) from last_error

                # Kurze Pause vor nächstem Versuch
                time.sleep(1)

        # Sollte nie erreicht werden, aber zur Sicherheit
        raise SeparationError(
            "Unexpected error in retry logic", context={"last_error": str(last_error)}
        )

    def _classify_error(self, error: Exception) -> ErrorType:
        """Klassifiziert Error nach Typ"""
        error_str = str(error).lower()
        error_type_str = type(error).__name__.lower()

        # GPU Memory Errors
        if any(
            keyword in error_str for keyword in ["cuda", "gpu", "mps", "out of memory"]
        ):
            return ErrorType.GPU_MEMORY

        # CPU Memory Errors
        if any(
            keyword in error_str for keyword in ["memoryerror", "ram", "allocation"]
        ):
            return ErrorType.CPU_MEMORY

        # Model Loading Errors
        if any(keyword in error_str for keyword in ["model", "checkpoint", "weight"]):
            return ErrorType.MODEL_LOADING

        # Network Errors
        if any(
            keyword in error_str
            for keyword in ["connection", "network", "download", "timeout"]
        ):
            return ErrorType.NETWORK

        # File I/O Errors
        if any(
            keyword in error_type_str
            for keyword in ["ioerror", "filenotfound", "permission"]
        ):
            return ErrorType.FILE_IO

        # Audio Processing Errors
        if any(
            keyword in error_str
            for keyword in ["audio", "sample", "waveform", "decode"]
        ):
            return ErrorType.AUDIO_PROCESSING

        return ErrorType.UNKNOWN

    def log_error(self, error: Exception, context: Optional[Dict] = None):
        """Detailliertes Error Logging"""
        error_type = self._classify_error(error)

        self.logger.error(
            f"Error Type: {error_type.value} | {str(error)}", exc_info=True
        )

        if context:
            self.logger.error(f"Error Context: {context}")

    def safe_execute(
        self,
        func: Callable,
        *args,
        default_return: Any = None,
        log_errors: bool = True,
        **kwargs,
    ) -> Any:
        """
        Führt Funktion sicher aus und gibt default_return bei Fehler zurück

        Args:
            func: Auszuführende Funktion
            default_return: Rückgabewert bei Fehler
            log_errors: Ob Fehler geloggt werden sollen

        Returns:
            Ergebnis der Funktion oder default_return
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if log_errors:
                self.log_error(
                    e,
                    context={
                        "function": func.__name__,
                        "args": str(args)[:100],  # Limitiere für Readability
                        "kwargs": str(kwargs)[:100],
                    },
                )
            return default_return


def retry_on_error(
    max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)
):
    """
    Decorator für automatische Retries

    Usage:
        @retry_on_error(max_retries=3, delay=1.0)
        def my_function():
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler(max_retries=max_retries)
            last_error = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_retries}): {str(e)}"
                    )

                    if attempt < max_retries:
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts",
                            exc_info=True,
                        )
                        raise last_error

            return None  # Should never reach here

        return wrapper

    return decorator


# Globale Error Handler Instanz
error_handler = ErrorHandler()


if __name__ == "__main__":
    # Test Error Handler
    def test_function(device="cpu", chunk_length=300, fail=True):
        logger.info(f"Test function called with device={device}, chunk={chunk_length}")
        if fail:
            raise RuntimeError("Simulated GPU memory error")
        return "Success"

    try:
        result = error_handler.retry_with_fallback(test_function, fail=True)
    except SeparationError as e:
        logger.error(f"Final error: {e}")
        logger.error(f"Error type: {e.error_type}")
        logger.error(f"Context: {e.context}")
