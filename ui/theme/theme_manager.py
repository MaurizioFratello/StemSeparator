"""
Theme Manager for StemSeparator GUI

PURPOSE: Centralized theme management and stylesheet loading.
CONTEXT: Provides a singleton for applying consistent theming across the application.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject

from .colors import ColorPalette
from .typography import Typography
from .spacing import Spacing


class ThemeManager(QObject):
    """
    Manages application theming and stylesheet loading

    WHY: Centralizes theme logic and makes it easy to switch themes or update styling
    """

    _instance: Optional[ThemeManager] = None

    def __init__(self):
        super().__init__()
        self.colors = ColorPalette
        self.typography = Typography
        self.spacing = Spacing
        self._current_stylesheet: str = ""

    @classmethod
    def instance(cls) -> ThemeManager:
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def load_stylesheet(self, stylesheet_path: Optional[Path] = None) -> str:
        """
        Load QSS stylesheet from file

        Args:
            stylesheet_path: Path to .qss file (defaults to built-in theme)

        Returns:
            Stylesheet content as string

        Raises:
            FileNotFoundError: If stylesheet file doesn't exist
        """
        if stylesheet_path is None:
            # Use default theme
            stylesheet_path = Path(__file__).parent / "stylesheet.qss"

        if not stylesheet_path.exists():
            raise FileNotFoundError(f"Stylesheet not found: {stylesheet_path}")

        with open(stylesheet_path, 'r', encoding='utf-8') as f:
            self._current_stylesheet = f.read()

        return self._current_stylesheet

    def apply_to_app(self, app: QApplication, stylesheet_path: Optional[Path] = None):
        """
        Apply theme to entire application

        Args:
            app: QApplication instance
            stylesheet_path: Optional custom stylesheet path
        """
        stylesheet = self.load_stylesheet(stylesheet_path)
        app.setStyleSheet(stylesheet)

    def get_current_stylesheet(self) -> str:
        """Get currently loaded stylesheet"""
        return self._current_stylesheet

    @staticmethod
    def set_widget_property(widget, property_name: str, value: str):
        """
        Set Qt property and force style refresh

        Args:
            widget: QWidget to modify
            property_name: Property name (e.g., "buttonStyle")
            value: Property value (e.g., "danger")

        Example:
            ThemeManager.set_widget_property(button, "buttonStyle", "danger")
        """
        widget.setProperty(property_name, value)
        # Force style refresh
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


# Convenience function for getting singleton instance
def get_theme_manager() -> ThemeManager:
    """Get ThemeManager singleton instance"""
    return ThemeManager.instance()
