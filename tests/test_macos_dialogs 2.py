"""
Unit tests for macOS dialog styling

PURPOSE: Test macOS-styled message boxes and dialogs
CONTEXT: Ensures dialogs apply correct styling on macOS and gracefully degrade elsewhere
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from PySide6.QtWidgets import QMessageBox, QWidget
from PySide6.QtCore import Qt

from ui.theme.macos_dialogs import MacOSDialogs


class TestMacOSDialogs:
    """Test suite for MacOSDialogs functionality"""

    def test_is_macos_on_darwin(self):
        """Test macOS detection returns True on Darwin"""
        with patch('platform.system', return_value='Darwin'):
            assert MacOSDialogs.is_macos() is True

    def test_is_macos_on_linux(self):
        """Test macOS detection returns False on Linux"""
        with patch('platform.system', return_value='Linux'):
            assert MacOSDialogs.is_macos() is False

    def test_is_macos_on_windows(self):
        """Test macOS detection returns False on Windows"""
        with patch('platform.system', return_value='Windows'):
            assert MacOSDialogs.is_macos() is False

    def test_apply_dialog_style_on_non_macos(self, qtbot):
        """Test dialog styling does nothing on non-macOS systems"""
        dialog = QMessageBox()
        qtbot.addWidget(dialog)

        with patch('platform.system', return_value='Linux'):
            MacOSDialogs.apply_dialog_style(dialog)

        # Should not have modified dialog
        assert dialog.styleSheet() == ""

    def test_apply_dialog_style_on_macos(self, qtbot):
        """Test dialog styling applies on macOS"""
        dialog = QMessageBox()
        qtbot.addWidget(dialog)

        with patch('platform.system', return_value='Darwin'):
            MacOSDialogs.apply_dialog_style(dialog)

        # Should have stylesheet
        assert len(dialog.styleSheet()) > 0
        assert 'QMessageBox' in dialog.styleSheet()

    def test_apply_dialog_style_sets_window_flags(self, qtbot):
        """Test dialog styling sets appropriate window flags on macOS"""
        dialog = QMessageBox()
        qtbot.addWidget(dialog)

        with patch('platform.system', return_value='Darwin'):
            MacOSDialogs.apply_dialog_style(dialog)

        # Should have dialog flags
        flags = dialog.windowFlags()
        assert flags & Qt.Dialog
        assert flags & Qt.CustomizeWindowHint

    def test_apply_dialog_style_graceful_degradation(self, qtbot):
        """Test dialog styling degrades gracefully on error"""
        dialog = Mock(spec=QMessageBox)
        dialog.setStyleSheet.side_effect = Exception("Test error")

        # Should not raise exception
        with patch('platform.system', return_value='Darwin'):
            MacOSDialogs.apply_dialog_style(dialog)

    def test_information_dialog(self, qtbot):
        """Test creating information dialog"""
        parent = QWidget()
        qtbot.addWidget(parent)

        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
                result = MacOSDialogs.information(
                    parent,
                    "Test Title",
                    "Test message"
                )

        assert result == QMessageBox.Ok

    def test_warning_dialog(self, qtbot):
        """Test creating warning dialog"""
        parent = QWidget()
        qtbot.addWidget(parent)

        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
                result = MacOSDialogs.warning(
                    parent,
                    "Warning",
                    "This is a warning"
                )

        assert result == QMessageBox.Ok

    def test_question_dialog(self, qtbot):
        """Test creating question dialog"""
        parent = QWidget()
        qtbot.addWidget(parent)

        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Yes):
                result = MacOSDialogs.question(
                    parent,
                    "Question",
                    "Are you sure?"
                )

        assert result == QMessageBox.Yes

    def test_critical_dialog(self, qtbot):
        """Test creating critical error dialog"""
        parent = QWidget()
        qtbot.addWidget(parent)

        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
                result = MacOSDialogs.critical(
                    parent,
                    "Error",
                    "Critical error occurred"
                )

        assert result == QMessageBox.Ok

    def test_about_dialog(self, qtbot):
        """Test creating about dialog"""
        parent = QWidget()
        qtbot.addWidget(parent)

        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
                # Should not raise exception
                MacOSDialogs.about(
                    parent,
                    "About",
                    "Application info"
                )

    def test_question_dialog_with_custom_buttons(self, qtbot):
        """Test question dialog with custom button configuration"""
        parent = QWidget()
        qtbot.addWidget(parent)

        buttons = QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel

        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Cancel):
                result = MacOSDialogs.question(
                    parent,
                    "Question",
                    "Save changes?",
                    buttons=buttons,
                    default_button=QMessageBox.Yes
                )

        assert result == QMessageBox.Cancel

    def test_dialog_with_none_parent(self, qtbot):
        """Test creating dialog with None parent"""
        with patch('platform.system', return_value='Darwin'):
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
                # Should not raise exception
                result = MacOSDialogs.information(
                    None,
                    "Test",
                    "Test message"
                )

        assert result == QMessageBox.Ok

    def test_stylesheet_contains_macos_colors(self):
        """Test stylesheet uses macOS blue accent"""
        stylesheet = MacOSDialogs.DIALOG_STYLESHEET

        # Should use macOS blue (#007AFF)
        assert '0, 122, 255' in stylesheet or '#007AFF' in stylesheet.upper()

        # Should have proper styling elements
        assert 'border-radius' in stylesheet
        assert 'QMessageBox' in stylesheet
        assert 'QPushButton' in stylesheet

    def test_stylesheet_has_hover_states(self):
        """Test stylesheet includes hover and pressed states"""
        stylesheet = MacOSDialogs.DIALOG_STYLESHEET

        assert ':hover' in stylesheet
        assert ':pressed' in stylesheet

    def test_stylesheet_styles_cancel_button(self):
        """Test stylesheet has special styling for Cancel/No buttons"""
        stylesheet = MacOSDialogs.DIALOG_STYLESHEET

        assert 'Cancel' in stylesheet or 'No' in stylesheet

    def test_get_macos_dialogs_returns_class(self):
        """Test convenience function returns MacOSDialogs class"""
        from ui.theme.macos_dialogs import get_macos_dialogs
        result = get_macos_dialogs()
        assert result is MacOSDialogs
