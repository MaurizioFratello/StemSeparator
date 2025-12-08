"""
Unit Tests für Error Handler
"""

import pytest
from utils.error_handler import (
    ErrorHandler,
    ErrorType,
    SeparationError,
    GPUMemoryError,
    CPUMemoryError,
    ModelLoadingError,
    retry_on_error,
)


@pytest.mark.unit
class TestErrorHandler:
    """Tests für Error Handler"""

    def test_error_handler_init(self):
        """Teste Initialisierung"""
        handler = ErrorHandler(max_retries=5)
        assert handler.max_retries == 5

    def test_classify_gpu_error(self):
        """Teste GPU Error Klassifizierung"""
        handler = ErrorHandler()
        error = RuntimeError("CUDA out of memory")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.GPU_MEMORY

    def test_classify_cpu_error(self):
        """Teste CPU Memory Error Klassifizierung"""
        handler = ErrorHandler()
        error = MemoryError("RAM allocation failed")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.CPU_MEMORY

    def test_safe_execute_success(self):
        """Teste safe_execute mit erfolgreicher Funktion"""
        handler = ErrorHandler()

        def successful_func():
            return "success"

        result = handler.safe_execute(successful_func)
        assert result == "success"

    def test_safe_execute_failure(self):
        """Teste safe_execute mit fehlschlagender Funktion"""
        handler = ErrorHandler()

        def failing_func():
            raise ValueError("Test error")

        result = handler.safe_execute(failing_func, default_return="default")
        assert result == "default"

    def test_retry_decorator_success(self):
        """Teste retry Decorator mit Erfolg"""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Temporary error")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 2

    def test_retry_decorator_failure(self):
        """Teste retry Decorator mit dauerhaftem Fehler"""

        @retry_on_error(max_retries=3, delay=0.1)
        def always_failing():
            raise ValueError("Permanent error")

        with pytest.raises(ValueError):
            always_failing()

    def test_separation_error(self):
        """Teste SeparationError Exception"""
        error = SeparationError(
            "Test error",
            error_type=ErrorType.AUDIO_PROCESSING,
            context={"file": "test.mp3"},
        )
        assert error.error_type == ErrorType.AUDIO_PROCESSING
        assert error.context["file"] == "test.mp3"

    def test_gpu_memory_error(self):
        """Teste GPUMemoryError"""
        error = GPUMemoryError("GPU OOM", context={"size": "4GB"})
        assert error.error_type == ErrorType.GPU_MEMORY

    def test_retry_with_fallback_success_first_try(self):
        """Teste retry_with_fallback mit Erfolg beim ersten Versuch"""
        handler = ErrorHandler()

        def successful_func(device="cpu", chunk_length=300):
            return f"success-{device}-{chunk_length}"

        result = handler.retry_with_fallback(successful_func)
        assert "success" in result

    def test_retry_with_fallback_success_second_try(self):
        """Teste retry_with_fallback mit Erfolg beim zweiten Versuch"""
        handler = ErrorHandler()
        call_count = 0

        def flaky_func(device="cpu", chunk_length=300):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First attempt failed")
            return "success"

        result = handler.retry_with_fallback(flaky_func)
        assert result == "success"
        assert call_count >= 2

    def test_retry_with_fallback_all_fail(self):
        """Teste retry_with_fallback wenn alle Versuche fehlschlagen"""
        handler = ErrorHandler(max_retries=2)

        def always_fail(device="cpu", chunk_length=300):
            raise ValueError("Always fails")

        strategies = [
            {"device": "gpu", "chunk_length": 300},
            {"device": "cpu", "chunk_length": 300},
        ]

        with pytest.raises(SeparationError):
            handler.retry_with_fallback(always_fail, strategies=strategies)

    def test_classify_model_loading_error(self):
        """Teste Model Loading Error Klassifizierung"""
        handler = ErrorHandler()
        error = RuntimeError("model checkpoint not found")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.MODEL_LOADING

    def test_classify_network_error(self):
        """Teste Network Error Klassifizierung"""
        handler = ErrorHandler()
        error = ConnectionError("network timeout")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.NETWORK

    def test_classify_file_io_error(self):
        """Teste File I/O Error Klassifizierung"""
        handler = ErrorHandler()
        error = FileNotFoundError("File not found")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.FILE_IO

    def test_classify_audio_processing_error(self):
        """Teste Audio Processing Error Klassifizierung"""
        handler = ErrorHandler()
        error = RuntimeError("audio decode failed")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.AUDIO_PROCESSING

    def test_classify_unknown_error(self):
        """Teste Unknown Error Klassifizierung"""
        handler = ErrorHandler()
        error = Exception("Some random error")
        error_type = handler._classify_error(error)
        assert error_type == ErrorType.UNKNOWN

    def test_log_error(self):
        """Teste log_error Methode"""
        handler = ErrorHandler()
        error = ValueError("Test error")

        # Sollte nicht crashen
        handler.log_error(error, context={"test": "context"})

    def test_log_error_without_context(self):
        """Teste log_error ohne Context"""
        handler = ErrorHandler()
        error = ValueError("Test error")

        handler.log_error(error)

    def test_safe_execute_with_args(self):
        """Teste safe_execute mit Argumenten"""
        handler = ErrorHandler()

        def func_with_args(a, b, c=10):
            return a + b + c

        result = handler.safe_execute(func_with_args, 1, 2, c=3)
        assert result == 6

    def test_safe_execute_no_logging(self):
        """Teste safe_execute ohne Logging"""
        handler = ErrorHandler()

        def failing_func():
            raise ValueError("Error")

        result = handler.safe_execute(failing_func, log_errors=False, default_return=42)
        assert result == 42

    def test_retry_decorator_custom_exceptions(self):
        """Teste retry Decorator mit spezifischen Exceptions"""
        call_count = 0

        @retry_on_error(max_retries=3, delay=0.05, exceptions=(ValueError,))
        def func_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "success"

        result = func_with_value_error()
        assert result == "success"

    def test_retry_decorator_wrong_exception_no_retry(self):
        """Teste retry Decorator mit nicht-gelisteter Exception"""

        @retry_on_error(max_retries=3, delay=0.05, exceptions=(ValueError,))
        def func_with_runtime_error():
            raise RuntimeError("Don't retry me")

        with pytest.raises(RuntimeError):
            func_with_runtime_error()

    def test_cpu_memory_error(self):
        """Teste CPUMemoryError Exception"""
        error = CPUMemoryError("Out of RAM", context={"available": "2GB"})
        assert error.error_type == ErrorType.CPU_MEMORY
        assert str(error) == "Out of RAM"
        assert error.context == {"available": "2GB"}

    def test_model_loading_error(self):
        """Teste ModelLoadingError Exception"""
        error = ModelLoadingError(
            "Failed to load model weights", context={"model": "demucs"}
        )
        assert error.error_type == ErrorType.MODEL_LOADING
        assert str(error) == "Failed to load model weights"
        assert error.context == {"model": "demucs"}
