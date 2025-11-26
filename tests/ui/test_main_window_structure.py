"""
Test main window structure and sidebar configuration.
"""
import pytest
from PySide6.QtWidgets import QFrame, QPushButton, QLabel, QStackedWidget
from PySide6.QtCore import Qt

from ui.main_window import MainWindow

def test_sidebar_structure(qapp, reset_singletons):
    """Test sidebar contains correct headers and buttons in order"""
    window = MainWindow()
    
    # Find sidebar
    sidebar = window.findChild(QFrame, "sidebar")
    assert sidebar is not None
    assert sidebar.width() == 220
    
    # Get all children in layout order
    layout = sidebar.layout()
    assert layout is not None
    
    # Collect widgets in layout order
    widgets = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        if widget:
            widgets.append(widget)
            
    # Filter for relevant widgets
    relevant_widgets = [
        w for w in widgets 
        if (isinstance(w, QLabel) and w.objectName() == "sidebar_header") or
           (isinstance(w, QPushButton) and w.objectName() == "sidebar_button")
    ]
    
    # Expecting 3 headers + 4 buttons = 7 items
    assert len(relevant_widgets) == 7
    
    # 1. Input Header
    assert isinstance(relevant_widgets[0], QLabel)
    assert relevant_widgets[0].objectName() == "sidebar_header"
    # Note: Text might depend on locale, but fallback is usually English
    
    # 2. Upload Button
    assert isinstance(relevant_widgets[1], QPushButton)
    assert relevant_widgets[1].objectName() == "sidebar_button"
    
    # 3. Record Button
    assert isinstance(relevant_widgets[2], QPushButton)
    assert relevant_widgets[2].objectName() == "sidebar_button"
    
    # 4. Processing Header
    assert isinstance(relevant_widgets[3], QLabel)
    assert relevant_widgets[3].objectName() == "sidebar_header"
    
    # 5. Queue Button
    assert isinstance(relevant_widgets[4], QPushButton)
    assert relevant_widgets[4].objectName() == "sidebar_button"
    
    # 6. Monitoring Header
    assert isinstance(relevant_widgets[5], QLabel)
    assert relevant_widgets[5].objectName() == "sidebar_header"
    
    # 7. Player Button
    assert isinstance(relevant_widgets[6], QPushButton)
    assert relevant_widgets[6].objectName() == "sidebar_button"

def test_sidebar_styling_ids(qapp, reset_singletons):
    """Verify widgets have correct object IDs for styling"""
    window = MainWindow()
    sidebar = window.findChild(QFrame, "sidebar")
    
    headers = sidebar.findChildren(QLabel, "sidebar_header")
    assert len(headers) == 3
    
    buttons = sidebar.findChildren(QPushButton, "sidebar_button")
    assert len(buttons) == 4
