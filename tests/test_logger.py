"""
Unit Tests für Logger
"""

import pytest
from pathlib import Path
from utils.logger import AppLogger, get_logger


@pytest.mark.unit
class TestLogger:
    """Tests für das Logger-System"""

    def test_logger_singleton(self):
        """Teste ob Logger ein Singleton ist"""
        logger1 = AppLogger()
        logger2 = AppLogger()
        assert logger1 is logger2

    def test_get_logger(self):
        """Teste get_logger() Funktion"""
        logger = get_logger()
        assert isinstance(logger, AppLogger)

    def test_logger_methods(self):
        """Teste ob alle Logger-Methoden existieren"""
        logger = get_logger()
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

    def test_log_separator_task(self):
        """Teste spezialisierte Log-Methode"""
        logger = get_logger()
        # Sollte keinen Error werfen
        logger.log_separator_task("test.mp3", "demucs", 4)

    def test_log_chunk_progress(self):
        """Teste Chunk Progress Logging"""
        logger = get_logger()
        logger.log_chunk_progress(1, 5, "test.mp3")

    def test_log_performance(self):
        """Teste Performance Logging"""
        logger = get_logger()
        logger.log_performance("test_operation", 1.234)

    def test_log_model_loading(self):
        """Teste Model Loading Logging"""
        logger = get_logger()
        logger.log_model_loading("test_model", "cpu")

    def test_log_error_with_context(self):
        """Teste Error Logging mit Context"""
        logger = get_logger()
        error = ValueError("Test error")
        context = {"file": "test.mp3", "chunk": 1}

        logger.log_error_with_context(error, context)

    def test_all_log_levels(self):
        """Teste alle Log-Level"""
        logger = get_logger()

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message", exc_info=False)
        logger.critical("Critical message", exc_info=False)

    def test_logger_get_logger_method(self):
        """Teste get_logger() Methode"""
        logger = get_logger()
        internal_logger = logger.get_logger()

        import logging

        assert isinstance(internal_logger, logging.Logger)

    def test_convenience_functions(self):
        """Teste Convenience-Funktionen"""
        from utils.logger import debug, info, warning, error, critical

        # Sollten alle nicht crashen
        debug("Debug test")
        info("Info test")
        warning("Warning test")
        error("Error test", exc_info=False)
        critical("Critical test", exc_info=False)
