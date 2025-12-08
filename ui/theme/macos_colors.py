"""
macOS System Color Integration

PURPOSE: Provides macOS system colors that automatically adapt to Light/Dark mode
         and respect user's accent color preferences.
CONTEXT: Enables the app to feel native by using system-defined colors instead of
         hardcoded values, matching macOS design language.
"""

from __future__ import annotations

from typing import Optional
import platform

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


class MacOSColors:
    """
    macOS system color integration

    WHY: Native macOS apps adapt to system appearance automatically.
         This class provides system colors and dark mode detection.
    """

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS"""
        return platform.system() == "Darwin"

    @staticmethod
    def is_dark_mode() -> bool:
        """
        Detect if macOS is in dark mode

        WHY: Allows us to adjust styling based on system appearance

        Returns:
            True if in dark mode, False if in light mode
        """
        if not MacOSColors.is_macos():
            return True  # Default to dark for non-Mac systems

        # Check system appearance via Qt palette
        app = QApplication.instance()
        if app:
            palette = app.palette()
            # Dark mode check: window background is darker than text
            bg = palette.color(QPalette.Window)
            text = palette.color(QPalette.WindowText)
            return bg.lightness() < text.lightness()

        return True  # Default to dark if can't detect

    @staticmethod
    def system_accent_color() -> QColor:
        """
        Get user's system accent color preference

        WHY: macOS users can customize their accent color in System Preferences.
             Respecting this choice makes the app feel more integrated.

        Returns:
            QColor representing the system accent color
        """
        app = QApplication.instance()
        if app:
            # Qt's Highlight color matches the system accent on macOS
            return app.palette().color(QPalette.Highlight)

        # Fallback to default blue
        return QColor("#667eea")

    @staticmethod
    def system_accent_color_hex() -> str:
        """Get system accent color as hex string"""
        color = MacOSColors.system_accent_color()
        return color.name()

    # System color palette strings (for use in QSS)
    @staticmethod
    def window_background() -> str:
        """
        Main window background color

        WHY: Uses Qt's palette system which Qt adapts to macOS appearance
        """
        return "palette(window)"

    @staticmethod
    def control_background() -> str:
        """Button/control background color"""
        return "palette(button)"

    @staticmethod
    def text_color() -> str:
        """Primary text color"""
        return "palette(window-text)"

    @staticmethod
    def secondary_text_color() -> str:
        """Secondary/dimmed text color"""
        return "palette(mid)"

    @staticmethod
    def accent_color() -> str:
        """System accent color for highlights and selections"""
        return "palette(highlight)"

    @staticmethod
    def get_adaptive_background(fallback: str = "#1e1e1e") -> str:
        """
        Get background color that adapts to light/dark mode

        Args:
            fallback: Hex color to use on non-macOS systems

        Returns:
            Color string (palette reference on macOS, hex on others)
        """
        if MacOSColors.is_macos():
            return MacOSColors.window_background()
        return fallback

    @staticmethod
    def get_adaptive_text(fallback: str = "#e0e0e0") -> str:
        """
        Get text color that adapts to light/dark mode

        Args:
            fallback: Hex color to use on non-macOS systems

        Returns:
            Color string (palette reference on macOS, hex on others)
        """
        if MacOSColors.is_macos():
            return MacOSColors.text_color()
        return fallback

    @staticmethod
    def get_adaptive_accent(fallback: str = "#667eea") -> str:
        """
        Get accent color that respects user's system preferences

        Args:
            fallback: Hex color to use on non-macOS systems

        Returns:
            Color string (palette reference on macOS, hex on others)
        """
        if MacOSColors.is_macos():
            return MacOSColors.accent_color()
        return fallback

    # macOS-specific color constants (Big Sur/Monterey/Ventura/Sonoma palette)
    # These match the official Apple Design Resources
    MACOS_BLUE = "#007AFF"  # macOS system blue
    MACOS_PURPLE = "#AF52DE"  # macOS system purple
    MACOS_PINK = "#FF2D55"  # macOS system pink
    MACOS_RED = "#FF3B30"  # macOS system red
    MACOS_ORANGE = "#FF9500"  # macOS system orange
    MACOS_YELLOW = "#FFCC00"  # macOS system yellow
    MACOS_GREEN = "#34C759"  # macOS system green
    MACOS_TEAL = "#5AC8FA"  # macOS system teal
    MACOS_INDIGO = "#5856D6"  # macOS system indigo

    # macOS label colors (text)
    MACOS_LABEL_PRIMARY = "#000000"  # Light mode primary
    MACOS_LABEL_PRIMARY_DARK = "#FFFFFF"  # Dark mode primary
    MACOS_LABEL_SECONDARY = "#3C3C43"  # Light mode secondary (60% opacity)
    MACOS_LABEL_SECONDARY_DARK = "#EBEBF5"  # Dark mode secondary (60% opacity)
    MACOS_LABEL_TERTIARY = "#3C3C43"  # Light mode tertiary (30% opacity)
    MACOS_LABEL_TERTIARY_DARK = "#EBEBF5"  # Dark mode tertiary (30% opacity)

    # macOS system gray colors
    MACOS_GRAY = "#8E8E93"  # Standard gray
    MACOS_GRAY_2 = "#AEAEB2"  # Lighter gray
    MACOS_GRAY_3 = "#C7C7CC"  # Even lighter
    MACOS_GRAY_4 = "#D1D1D6"  # Very light
    MACOS_GRAY_5 = "#E5E5EA"  # Nearly white (light mode)
    MACOS_GRAY_6 = "#F2F2F7"  # Grouped background (light mode)

    MACOS_GRAY_DARK = "#8E8E93"  # Standard gray (dark mode)
    MACOS_GRAY_2_DARK = "#636366"  # Darker gray
    MACOS_GRAY_3_DARK = "#48484A"  # Even darker
    MACOS_GRAY_4_DARK = "#3A3A3C"  # Very dark
    MACOS_GRAY_5_DARK = "#2C2C2E"  # Nearly black (dark mode)
    MACOS_GRAY_6_DARK = "#1C1C1E"  # Grouped background (dark mode)


def get_macos_colors() -> MacOSColors:
    """Get MacOSColors instance (for convenience)"""
    return MacOSColors
