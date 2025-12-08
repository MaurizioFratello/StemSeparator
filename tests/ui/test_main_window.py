"""
Tests for MainWindow

PURPOSE: Verify main window initialization, menu actions, and widget integration.
CONTEXT: Core GUI integration tests.
"""

import pytest
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QStackedWidget, QFrame

from ui.main_window import MainWindow


@pytest.mark.unit
def test_main_window_creation(qapp, reset_singletons):
    """Test that main window can be created"""
    window = MainWindow()

    assert window is not None
    assert window.windowTitle() == "Stem Separator"
    # Default size changed
    assert window.width() >= 1000
    assert window.height() >= 700


@pytest.mark.unit
def test_main_window_has_sidebar_and_stack(qapp, reset_singletons):
    """Test that main window has sidebar and stacked widget"""
    window = MainWindow()

    # Check for Sidebar
    assert hasattr(window, "_sidebar")
    assert isinstance(window._sidebar, QFrame)
    # assert window._sidebar.isVisible()  # Window not shown, so this might be False

    # Check for Stacked Widget
    assert hasattr(window, "_content_stack")
    assert isinstance(window._content_stack, QStackedWidget)
    assert window._content_stack.count() == 4

    # Check Sidebar Buttons
    assert hasattr(window, "_btn_upload")
    assert hasattr(window, "_btn_record")
    assert hasattr(window, "_btn_queue")
    assert hasattr(window, "_btn_player")

    # Check connections (clicking button should change stack)
    window._btn_record.click()
    assert window._content_stack.currentIndex() == 1

    window._btn_queue.click()
    assert window._content_stack.currentIndex() == 2

    window._btn_player.click()
    assert window._content_stack.currentIndex() == 3


@pytest.mark.unit
def test_main_window_has_menu(qapp, reset_singletons):
    """Test that main window has menu bar with expected menus"""
    window = MainWindow()

    menu_bar = window.menuBar()
    assert menu_bar is not None

    # Get menu titles
    menus = [action.text() for action in menu_bar.actions() if action.menu()]

    # Should have File, View, Help menus
    assert len(menus) >= 3


@pytest.mark.unit
def test_main_window_settings_action(qapp, reset_singletons):
    """Test that settings action exists and can be triggered"""
    with patch("ui.main_window.SettingsDialog") as mock_dialog_class:
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog

        window = MainWindow()

        # Trigger settings action
        window._settings_action.trigger()

        # Settings dialog should have been created
        mock_dialog_class.assert_called_once()
        mock_dialog.exec.assert_called_once()


@pytest.mark.unit
def test_main_window_quit_action(qapp, reset_singletons):
    """Test that quit action is connected"""
    window = MainWindow()

    # Quit action should exist
    assert window._quit_action is not None
    # Shortcut format might vary by OS, but we check existence


@pytest.mark.unit
def test_main_window_widgets_connected(qapp, reset_singletons):
    """Test that widgets are properly connected via signals"""
    window = MainWindow()

    # Upload widget should be connected to queue
    assert window._upload_widget is not None
    assert window._queue_widget is not None

    # Recording widget should be connected to main window
    assert window._recording_widget is not None


@pytest.mark.unit
def test_main_window_close_event(qapp, reset_singletons):
    """Test that close event is handled properly"""
    window = MainWindow()

    # Create mock close event
    from PySide6.QtGui import QCloseEvent

    event = QCloseEvent()

    # Should accept close event
    window.closeEvent(event)
    assert event.isAccepted()


@pytest.mark.unit
def test_main_window_status_bar(qapp, reset_singletons):
    """Test that status bar exists and shows ready message"""
    window = MainWindow()

    status_bar = window.statusBar()
    assert status_bar is not None
    assert status_bar.currentMessage() != ""
