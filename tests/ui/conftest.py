"""
Pytest fixtures for UI tests

PURPOSE: Provide shared fixtures for Qt-based GUI testing.
CONTEXT: Handles QApplication lifecycle and singleton resets.
"""

import pytest
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """
    Create QApplication instance for entire test session

    WHY: QApplication can only be created once per process
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Don't quit - other tests may need it


@pytest.fixture
def reset_singletons():
    """
    Reset all singleton instances before each test

    WHY: Prevents state leakage between tests
    """
    # Import here to avoid circular imports
    import core.separator
    import core.recorder
    import core.model_manager
    import core.device_manager
    import core.chunk_processor
    import core.blackhole_installer
    import ui.settings_manager

    # Clear all singleton instances
    core.separator._separator = None
    core.recorder._recorder = None
    core.model_manager._model_manager = None
    core.device_manager._device_manager = None
    core.chunk_processor._chunk_processor = None
    core.blackhole_installer._installer = None
    ui.settings_manager._settings_manager = None

    yield

    # Cleanup again after test
    core.separator._separator = None
    core.recorder._recorder = None
    core.model_manager._model_manager = None
    core.device_manager._device_manager = None
    core.chunk_processor._chunk_processor = None
    core.blackhole_installer._installer = None
    ui.settings_manager._settings_manager = None


@pytest.fixture
def temp_output_dir(tmp_path):
    """
    Provide temporary output directory for tests

    WHY: Isolates test file outputs from each other and from real data
    """
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    yield output_dir


@pytest.fixture
def mock_audio_file(tmp_path):
    """
    Create a mock audio file for testing

    WHY: Many tests need valid audio files without actually processing audio
    """
    audio_file = tmp_path / "test_audio.wav"

    # Create minimal valid WAV file
    import wave
    import numpy as np

    sample_rate = 44100
    duration = 1.0  # 1 second
    samples = int(sample_rate * duration)

    # Generate silence
    audio_data = np.zeros((samples, 2), dtype=np.int16)

    with wave.open(str(audio_file), "w") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    yield audio_file
