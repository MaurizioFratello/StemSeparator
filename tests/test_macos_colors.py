"""
Unit tests for macOS color integration

PURPOSE: Test macOS system color detection, dark mode detection, and adaptive colors
CONTEXT: Ensures color system works correctly on macOS and gracefully degrades elsewhere
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import platform

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

from ui.theme.macos_colors import MacOSColors


class TestMacOSColors:
    """Test suite for MacOSColors functionality"""

    def test_is_macos_on_darwin(self):
        """Test macOS detection returns True on Darwin"""
        with patch("platform.system", return_value="Darwin"):
            assert MacOSColors.is_macos() is True

    def test_is_macos_on_linux(self):
        """Test macOS detection returns False on Linux"""
        with patch("platform.system", return_value="Linux"):
            assert MacOSColors.is_macos() is False

    def test_is_macos_on_windows(self):
        """Test macOS detection returns False on Windows"""
        with patch("platform.system", return_value="Windows"):
            assert MacOSColors.is_macos() is False

    def test_is_dark_mode_no_app(self):
        """Test dark mode detection defaults to True when no QApplication"""
        with patch("platform.system", return_value="Darwin"):
            with patch("PySide6.QtWidgets.QApplication.instance", return_value=None):
                assert MacOSColors.is_dark_mode() is True

    def test_is_dark_mode_on_non_macos(self):
        """Test dark mode defaults to True on non-macOS systems"""
        with patch("platform.system", return_value="Linux"):
            assert MacOSColors.is_dark_mode() is True

    def test_is_dark_mode_dark_palette(self, qtbot):
        """Test dark mode detection with dark palette"""
        with patch("platform.system", return_value="Darwin"):
            # Create mock palette with dark colors
            mock_palette = Mock(spec=QPalette)
            mock_window_color = Mock(spec=QColor)
            mock_window_color.lightness.return_value = 30  # Dark background
            mock_text_color = Mock(spec=QColor)
            mock_text_color.lightness.return_value = 200  # Light text

            mock_palette.color.side_effect = lambda role: {
                QPalette.Window: mock_window_color,
                QPalette.WindowText: mock_text_color,
            }.get(role)

            mock_app = Mock(spec=QApplication)
            mock_app.palette.return_value = mock_palette

            with patch(
                "PySide6.QtWidgets.QApplication.instance", return_value=mock_app
            ):
                assert MacOSColors.is_dark_mode() is True

    def test_is_dark_mode_light_palette(self, qtbot):
        """Test dark mode detection with light palette"""
        with patch("platform.system", return_value="Darwin"):
            # Create mock palette with light colors
            mock_palette = Mock(spec=QPalette)
            mock_window_color = Mock(spec=QColor)
            mock_window_color.lightness.return_value = 240  # Light background
            mock_text_color = Mock(spec=QColor)
            mock_text_color.lightness.return_value = 20  # Dark text

            mock_palette.color.side_effect = lambda role: {
                QPalette.Window: mock_window_color,
                QPalette.WindowText: mock_text_color,
            }.get(role)

            mock_app = Mock(spec=QApplication)
            mock_app.palette.return_value = mock_palette

            with patch(
                "PySide6.QtWidgets.QApplication.instance", return_value=mock_app
            ):
                assert MacOSColors.is_dark_mode() is False

    def test_system_accent_color_with_app(self, qtbot):
        """Test system accent color retrieval"""
        mock_color = QColor("#007AFF")
        mock_palette = Mock(spec=QPalette)
        mock_palette.color.return_value = mock_color

        mock_app = Mock(spec=QApplication)
        mock_app.palette.return_value = mock_palette

        with patch("PySide6.QtWidgets.QApplication.instance", return_value=mock_app):
            color = MacOSColors.system_accent_color()
            assert isinstance(color, QColor)

    def test_system_accent_color_no_app(self):
        """Test system accent color fallback without QApplication"""
        with patch("PySide6.QtWidgets.QApplication.instance", return_value=None):
            color = MacOSColors.system_accent_color()
            assert isinstance(color, QColor)
            assert color.name() == "#667eea"  # Fallback color

    def test_system_accent_color_hex(self, qtbot):
        """Test system accent color as hex string"""
        mock_color = QColor("#007AFF")
        mock_palette = Mock(spec=QPalette)
        mock_palette.color.return_value = mock_color

        mock_app = Mock(spec=QApplication)
        mock_app.palette.return_value = mock_palette

        with patch("PySide6.QtWidgets.QApplication.instance", return_value=mock_app):
            hex_color = MacOSColors.system_accent_color_hex()
            assert isinstance(hex_color, str)
            assert hex_color.startswith("#")

    def test_window_background_returns_palette_string(self):
        """Test window background returns palette reference"""
        result = MacOSColors.window_background()
        assert result == "palette(window)"

    def test_control_background_returns_palette_string(self):
        """Test control background returns palette reference"""
        result = MacOSColors.control_background()
        assert result == "palette(button)"

    def test_text_color_returns_palette_string(self):
        """Test text color returns palette reference"""
        result = MacOSColors.text_color()
        assert result == "palette(window-text)"

    def test_secondary_text_color_returns_palette_string(self):
        """Test secondary text color returns palette reference"""
        result = MacOSColors.secondary_text_color()
        assert result == "palette(mid)"

    def test_accent_color_returns_palette_string(self):
        """Test accent color returns palette reference"""
        result = MacOSColors.accent_color()
        assert result == "palette(highlight)"

    def test_get_adaptive_background_on_macos(self):
        """Test adaptive background returns palette on macOS"""
        with patch("platform.system", return_value="Darwin"):
            result = MacOSColors.get_adaptive_background()
            assert result == "palette(window)"

    def test_get_adaptive_background_on_linux(self):
        """Test adaptive background returns fallback on Linux"""
        with patch("platform.system", return_value="Linux"):
            result = MacOSColors.get_adaptive_background(fallback="#custom")
            assert result == "#custom"

    def test_get_adaptive_text_on_macos(self):
        """Test adaptive text returns palette on macOS"""
        with patch("platform.system", return_value="Darwin"):
            result = MacOSColors.get_adaptive_text()
            assert result == "palette(window-text)"

    def test_get_adaptive_text_on_windows(self):
        """Test adaptive text returns fallback on Windows"""
        with patch("platform.system", return_value="Windows"):
            result = MacOSColors.get_adaptive_text(fallback="#custom")
            assert result == "#custom"

    def test_get_adaptive_accent_on_macos(self):
        """Test adaptive accent returns palette on macOS"""
        with patch("platform.system", return_value="Darwin"):
            result = MacOSColors.get_adaptive_accent()
            assert result == "palette(highlight)"

    def test_get_adaptive_accent_on_non_macos(self):
        """Test adaptive accent returns fallback on non-macOS"""
        with patch("platform.system", return_value="Linux"):
            result = MacOSColors.get_adaptive_accent(fallback="#custom")
            assert result == "#custom"

    def test_macos_color_constants_are_strings(self):
        """Test that all macOS color constants are valid hex strings"""
        colors = [
            MacOSColors.MACOS_BLUE,
            MacOSColors.MACOS_PURPLE,
            MacOSColors.MACOS_PINK,
            MacOSColors.MACOS_RED,
            MacOSColors.MACOS_ORANGE,
            MacOSColors.MACOS_YELLOW,
            MacOSColors.MACOS_GREEN,
            MacOSColors.MACOS_TEAL,
            MacOSColors.MACOS_INDIGO,
            MacOSColors.MACOS_GRAY,
        ]

        for color in colors:
            assert isinstance(color, str)
            assert color.startswith("#")
            assert len(color) == 7  # #RRGGBB format

    def test_macos_label_colors_exist(self):
        """Test that label colors are defined"""
        assert hasattr(MacOSColors, "MACOS_LABEL_PRIMARY")
        assert hasattr(MacOSColors, "MACOS_LABEL_PRIMARY_DARK")
        assert hasattr(MacOSColors, "MACOS_LABEL_SECONDARY")
        assert hasattr(MacOSColors, "MACOS_LABEL_SECONDARY_DARK")

    def test_get_macos_colors_returns_class(self):
        """Test convenience function returns MacOSColors class"""
        from ui.theme.macos_colors import get_macos_colors

        result = get_macos_colors()
        assert result is MacOSColors
