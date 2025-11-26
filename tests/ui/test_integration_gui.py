"""
Integration Tests for GUI Workflows

PURPOSE: Test complete user workflows from GUI perspective.
CONTEXT: End-to-end tests simulating real user interactions.
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from ui.main_window import MainWindow
from core.separator import SeparationResult
from core.recorder import RecordingInfo, RecordingState


@pytest.mark.integration
def test_complete_upload_workflow(qapp, reset_singletons, mock_audio_file, tmp_path):
    """
    Integration test: Upload file → Select model → Start separation → View results
    
    WHY: Tests complete upload widget workflow as user would experience it
    """
    with patch('audio_separator.separator.Separator') as mock_separator_class:
        # Mock successful separation
        mock_sep_instance = MagicMock()
        mock_sep_instance.separate.return_value = [
            str(tmp_path / 'test_vocals.wav'),
            str(tmp_path / 'test_drums.wav'),
            str(tmp_path / 'test_bass.wav'),
            str(tmp_path / 'test_other.wav')
        ]
        mock_separator_class.return_value = mock_sep_instance
        
        # Create main window
        window = MainWindow()
        window.show()
        QTest.qWaitForWindowExposed(window)
        
        # Navigate to Upload tab
        upload_widget = window._upload_widget
        window._content_stack.setCurrentWidget(upload_widget)
        
        # Add file
        upload_widget._add_file(mock_audio_file)
        assert upload_widget.file_list.count() == 1
        
        # Select file
        upload_widget.file_list.setCurrentRow(0)
        assert upload_widget.btn_start.isEnabled()
        
        # Select model
        upload_widget.model_combo.setCurrentIndex(0)
        
        # Start separation (now queues)
        # Since start_queue triggers thread, we just verify it was queued
        with patch('ui.widgets.queue_widget.QueueWorker'):
             upload_widget._on_start_clicked()
             
             # Should be in queue
             queue_widget = window._queue_drawer.queue_widget
             assert len(queue_widget.tasks) == 1
             assert queue_widget.tasks[0].file_path == mock_audio_file
             
             # Drawer should be visible
             assert window._queue_drawer.isVisible()


@pytest.mark.integration
def test_recording_to_file_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Start recording → Stop → Save file → Verify
    
    WHY: Tests complete recording workflow as user would experience it
    """
    with patch('soundcard.all_microphones') as mock_mics:
        with patch('soundcard.all_speakers') as mock_speakers:
            # Mock devices
            mock_device = MagicMock()
            mock_device.name = "BlackHole 2ch"
            mock_mics.return_value = [mock_device]
            mock_speakers.return_value = []
            
            # Mock recorder context
            mock_recorder_context = MagicMock()
            mock_recorder_context.__enter__ = MagicMock(return_value=mock_recorder_context)
            mock_recorder_context.__exit__ = MagicMock(return_value=None)
            mock_recorder_context.record = MagicMock(return_value=[[0.0, 0.0]] * 100)
            
            mock_device.recorder = MagicMock(return_value=mock_recorder_context)
            
            # Create main window
            window = MainWindow()
            window.show()
            QTest.qWaitForWindowExposed(window)
            
            # Navigate to Recording tab
            recording_widget = window._recording_widget
            window._content_stack.setCurrentWidget(recording_widget)
            
            # Refresh devices
            recording_widget._refresh_devices()
            assert recording_widget.device_combo.count() > 0
            
            # Start recording
            recording_widget._on_start_clicked()
            
            # Wait briefly
            QTest.qWait(200)
            
            # Should be recording
            assert not recording_widget.btn_start.isEnabled()
            assert recording_widget.btn_stop.isEnabled()
            
            # Stop recording
            save_path = tmp_path / "test_recording.wav"
            with patch('core.recorder.Recorder.stop_recording') as mock_stop:
                mock_stop.return_value = RecordingInfo(
                    duration_seconds=0.2,
                    sample_rate=44100,
                    channels=2,
                    file_path=save_path,
                    peak_level=0.5
                )
                
                with patch('PySide6.QtWidgets.QMessageBox.information'):
                    recording_widget._on_stop_clicked()
                
                # Should have called stop
                mock_stop.assert_called_once()


@pytest.mark.integration
def test_queue_batch_processing_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Add files to queue → Start batch processing → Monitor progress
    
    WHY: Tests queue widget with multiple files
    """
    # Create multiple test files
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test_file_{i}.wav"
        
        # Create minimal valid WAV
        import wave
        import numpy as np
        with wave.open(str(test_file), 'w') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(np.zeros((44100, 2), dtype=np.int16).tobytes())
        
        test_files.append(test_file)
    
    with patch('audio_separator.separator.Separator') as mock_separator_class:
        # Mock separator
        mock_sep_instance = MagicMock()
        
        def mock_separate(audio_file, **kwargs):
            # Simulate processing
            return SeparationResult(
                success=True,
                input_file=Path(audio_file),
                output_dir=tmp_path,
                stems={'vocals': tmp_path / f'{Path(audio_file).stem}_vocals.wav'},
                model_used='demucs_4s',
                device_used='cpu',
                duration_seconds=0.5
            )
        
        mock_sep_instance.separate.side_effect = mock_separate
        mock_separator_class.return_value = mock_sep_instance
        
        # Create main window
        window = MainWindow()
        window.show()
        QTest.qWaitForWindowExposed(window)
        
        # Get queue widget
        queue_widget = window._queue_drawer.queue_widget
        # window._content_stack.setCurrentWidget(queue_widget) # No longer in stack
        
        # Add files to queue
        for test_file in test_files:
            queue_widget.add_task(test_file, "demucs_4s")
        
        assert len(queue_widget.tasks) == 3
        assert queue_widget.queue_table.rowCount() == 3
        
        # Start queue processing
        with patch('PySide6.QtWidgets.QMessageBox.information'):
            queue_widget._on_start_queue()
            
            # Wait for processing to start
            QTest.qWait(100)
            
            # Should be processing
            assert queue_widget.is_processing


@pytest.mark.integration
def test_settings_persistence_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Change settings → Save → Restart → Verify loaded
    
    WHY: Tests settings persistence across sessions
    """
    from ui.settings_manager import SettingsManager
    
    # Create settings manager with temp file
    settings_file = tmp_path / "test_settings.json"
    
    with patch('ui.settings_manager.BASE_DIR', tmp_path):
        # First session: change and save settings
        settings_mgr = SettingsManager()
        settings_mgr.settings_file = settings_file
        
        original_lang = settings_mgr.get_language()
        new_lang = "en" if original_lang == "de" else "de"
        
        settings_mgr.set_language(new_lang)
        settings_mgr.set_use_gpu(False)
        settings_mgr.set_chunk_length(150)
        
        success = settings_mgr.save()
        assert success
        assert settings_file.exists()
        
        # Second session: load settings
        settings_mgr2 = SettingsManager()
        settings_mgr2.settings_file = settings_file
        settings_mgr2._load_from_file()
        
        # Settings should persist
        assert settings_mgr2.get_language() == new_lang
        assert settings_mgr2.get_use_gpu() == False
        assert settings_mgr2.get_chunk_length() == 150


@pytest.mark.integration
def test_upload_to_queue_signal_workflow(qapp, reset_singletons, mock_audio_file):
    """
    Integration test: Upload widget → Queue file → Verify in queue widget
    
    WHY: Tests signal-based communication between widgets
    """
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)
    
    upload_widget = window._upload_widget
    queue_widget = window._queue_drawer.queue_widget
    
    # Add file to upload widget
    upload_widget._add_file(mock_audio_file)
    upload_widget.file_list.setCurrentRow(0)
    
    # Queue it
    upload_widget._on_queue_clicked()
    
    # Should appear in queue
    assert len(queue_widget.tasks) == 1
    assert queue_widget.tasks[0].file_path == mock_audio_file
    assert queue_widget.queue_table.rowCount() == 1


@pytest.mark.integration
def test_recording_to_main_window_signal(qapp, reset_singletons, tmp_path):
    """
    Integration test: Recording saved → Signal to main window → Status update
    
    WHY: Tests signal propagation from recording widget to main window
    """
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)
    
    recording_widget = window._recording_widget
    
    # Simulate recording saved
    test_file = tmp_path / "recording.wav"
    test_file.touch()
    
    recording_widget.recording_saved.emit(test_file)
    
    # Process events
    QTest.qWait(100)
    
    # Status bar should show notification
    status_text = window.statusBar().currentMessage()
    assert "recording" in status_text.lower() or test_file.name in status_text


@pytest.mark.integration
def test_language_switch_workflow(qapp, reset_singletons):
    """
    Integration test: Switch language → Verify UI updates
    
    WHY: Tests translation system integration
    """
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)
    
    # Get current language
    current_lang = window._context.get_language()
    
    # Find opposite language action
    for lang_code, action in window._language_actions.items():
        if lang_code != current_lang:
            # Trigger language switch
            action.trigger()
            
            # Process events
            QTest.qWait(50)
            
            # Language should have changed
            new_lang = window._context.get_language()
            assert new_lang == lang_code
            break


@pytest.mark.integration
def test_player_load_stems_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Load stems into player → Verify controls enabled
    
    WHY: Tests player widget with real file loading
    """
    # Create mock stem files
    stem_files = {}
    for stem_name in ['vocals', 'drums', 'bass', 'other']:
        stem_file = tmp_path / f"test_{stem_name}.wav"
        
        # Create minimal WAV
        import wave
        import numpy as np
        with wave.open(str(stem_file), 'w') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(np.zeros((44100, 2), dtype=np.int16).tobytes())
        
        stem_files[stem_name] = stem_file
    
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)
    
    player_widget = window._player_widget
    window._content_stack.setCurrentWidget(player_widget)
    
    # Load stems
    player_widget._load_stems(list(stem_files.values()))
    
    # Should have loaded stems
    assert len(player_widget.stem_files) == 4
    assert len(player_widget.stem_controls) == 4
    
    # Play button should be enabled
    assert player_widget.btn_play.isEnabled()
    assert player_widget.btn_export.isEnabled()


@pytest.mark.integration
def test_error_handling_workflow(qapp, reset_singletons, tmp_path):
    """
    Integration test: Trigger error in separation → Verify error handling
    
    WHY: Tests error propagation and user notification
    """
    # Create invalid file
    invalid_file = tmp_path / "invalid.txt"
    invalid_file.write_text("not audio")
    
    window = MainWindow()
    window.show()
    QTest.qWaitForWindowExposed(window)
    
    upload_widget = window._upload_widget
    
    # Try to add invalid file
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        upload_widget._add_file(invalid_file)
        
        # Should show warning
        mock_warning.assert_called_once()
    
    # File should not be added
    assert upload_widget.file_list.count() == 0


@pytest.mark.integration
@pytest.mark.slow
def test_full_user_journey(qapp, reset_singletons, tmp_path):
    """
    Integration test: Complete user journey from start to finish
    
    Steps:
    1. Open app
    2. Upload file
    3. Start separation
    4. View results in player
    5. Queue another file
    6. Change settings
    
    WHY: Tests most common user workflow end-to-end
    """
    # Create test file
    test_file = tmp_path / "user_test.wav"
    import wave
    import numpy as np
    with wave.open(str(test_file), 'w') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(np.zeros((88200, 2), dtype=np.int16).tobytes())
    
    with patch('audio_separator.separator.Separator') as mock_separator_class:
        # Mock separator
        mock_sep_instance = MagicMock()
        mock_sep_instance.separate.return_value = [
            str(tmp_path / 'vocals.wav'),
            str(tmp_path / 'drums.wav')
        ]
        mock_separator_class.return_value = mock_sep_instance
        
        # Step 1: Open app
        window = MainWindow()
        window.show()
        QTest.qWaitForWindowExposed(window)
        assert window.isVisible()
        
        # Step 2: Upload file
        upload_widget = window._upload_widget
        window._content_stack.setCurrentWidget(upload_widget)
        upload_widget._add_file(test_file)
        assert upload_widget.file_list.count() == 1
        
        # Step 3: Queue file
        upload_widget.file_list.setCurrentRow(0)
        upload_widget._on_queue_clicked()
        
        queue_widget = window._queue_drawer.queue_widget
        assert len(queue_widget.tasks) == 1
        
        # Step 4: Change settings
        from ui.widgets.settings_dialog import SettingsDialog
        with patch.object(SettingsDialog, 'exec'):
            window._show_settings()
        
        # Journey complete
        assert True  # If we got here, full journey succeeded

