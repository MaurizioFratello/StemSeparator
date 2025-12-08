"""
Theme system for StemSeparator GUI

Provides a modern, cohesive design system with:
- Color palette (dark theme with accent colors)
- Typography scale
- Spacing system
- Master QSS stylesheet
"""

from .colors import ColorPalette
from .typography import Typography
from .spacing import Spacing
from .theme_manager import ThemeManager

__all__ = ["ColorPalette", "Typography", "Spacing", "ThemeManager"]
