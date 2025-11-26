"""
Test workflow navigation between tabs.
"""
import pytest
from PySide6.QtWidgets import QStackedWidget, QPushButton
from PySide6.QtCore import Qt
from ui.main_window import MainWindow

def test_navigation_upload_to_queue(qapp, reset_singletons, qtbot):
    """Test start queue requested signal switches to queue tab"""
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Initial state: Upload tab (index 0)
    assert window._content_stack.currentIndex() == 0
    assert window._btn_upload.isChecked()
    
    # Trigger signal manually to simulate "Start Queue" button click in UploadWidget
    window._upload_widget.start_queue_requested.emit()
    
    # Check state: Queue tab (index 2)
    assert window._content_stack.currentIndex() == 2
    assert window._btn_queue.isChecked()

def test_navigation_manual_clicks(qapp, reset_singletons, qtbot):
    """Test clicking sidebar buttons switches tabs"""
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Click Record (Index 1)
    qtbot.mouseClick(window._btn_record, Qt.LeftButton)
    assert window._content_stack.currentIndex() == 1
    assert window._btn_record.isChecked()
    
    # Click Player (Index 3)
    qtbot.mouseClick(window._btn_player, Qt.LeftButton)
    assert window._content_stack.currentIndex() == 3
    assert window._btn_player.isChecked()

def test_recording_saved_navigation(qapp, reset_singletons, qtbot, tmp_path):
    """Test that saving a recording switches to Upload tab"""
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Switch to Recording tab first
    window._content_stack.setCurrentIndex(1)
    
    # Simulate recording saved
    dummy_path = tmp_path / "test_rec.wav"
    
    # Ensure the dummy file exists so valid checks pass (though UploadWidget might check)
    # UploadWidget.add_file does checks, so we need a valid file or we mock add_file
    # Creating a valid tiny wav
    import soundfile as sf
    import numpy as np
    sf.write(dummy_path, np.zeros((100, 2)), 44100)
    
    window._recording_widget.recording_saved.emit(dummy_path)
    
    # Should switch to Upload tab (index 0)
    assert window._content_stack.currentIndex() == 0
    assert window._btn_upload.isChecked()
