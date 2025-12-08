"""
Color palette for StemSeparator GUI

PURPOSE: Centralized color definitions for consistent theming across the application.
CONTEXT: Modern dark theme with purple-blue accents, inspired by professional audio software.
         Integrates with macOS system colors for native appearance on Mac.
"""

from __future__ import annotations

from .macos_colors import MacOSColors


class ColorPalette:
    """Modern color palette for StemSeparator"""

    # Base colors (Dark theme)
    BACKGROUND_PRIMARY = "#1e1e1e"  # Main background
    BACKGROUND_SECONDARY = "#2d2d2d"  # Elevated surfaces (cards, groups)
    BACKGROUND_TERTIARY = "#3d3d3d"  # Inputs, buttons
    BACKGROUND_HOVER = "#4d4d4d"  # Hover state

    # Text colors
    TEXT_PRIMARY = "#e0e0e0"  # Main text
    TEXT_SECONDARY = "#b0b0b0"  # Secondary text
    TEXT_DISABLED = "#707070"  # Disabled state
    TEXT_INVERSE = "#ffffff"  # Text on colored backgrounds

    # Accent colors (Modern gradient-friendly)
    ACCENT_PRIMARY = "#667eea"  # Main brand color (purple-blue)
    ACCENT_PRIMARY_HOVER = "#7c8ef0"  # Hover state
    ACCENT_PRIMARY_PRESSED = "#5568d3"  # Pressed state
    ACCENT_SECONDARY = "#764ba2"  # Secondary accent (purple)
    ACCENT_SECONDARY_HOVER = "#8a5fb8"  # Hover state

    # Semantic colors
    SUCCESS = "#10b981"  # Green for success
    SUCCESS_HOVER = "#34d399"  # Hover state
    WARNING = "#f59e0b"  # Orange for warnings
    WARNING_HOVER = "#fbbf24"  # Hover state
    ERROR = "#ef4444"  # Red for errors
    ERROR_HOVER = "#f87171"  # Hover state
    INFO = "#3b82f6"  # Blue for info
    INFO_HOVER = "#60a5fa"  # Hover state

    # Functional colors
    BORDER_DEFAULT = "#404040"
    BORDER_FOCUS = "#667eea"
    HOVER_OVERLAY = "rgba(255, 255, 255, 0.05)"
    SELECTION_BG = "#667eea"
    SELECTION_TEXT = "#ffffff"

    # Audio-specific colors
    WAVEFORM_PRIMARY = "#667eea"
    WAVEFORM_SECONDARY = "#764ba2"
    WAVEFORM_BACKGROUND = "#1a1a1a"

    # Level meter colors (professional audio standards)
    LEVEL_SAFE = "#10b981"  # Green (-60 to -12 dB)
    LEVEL_CAUTION = "#f59e0b"  # Orange (-12 to -3 dB)
    LEVEL_DANGER = "#ef4444"  # Red (> -3 dB - risk of clipping)

    # macOS system color integration (NEW)
    # These adapt to system appearance (light/dark mode) on macOS
    SYSTEM_WINDOW_BG = MacOSColors.window_background()
    SYSTEM_CONTROL_BG = MacOSColors.control_background()
    SYSTEM_TEXT = MacOSColors.text_color()
    SYSTEM_ACCENT = MacOSColors.accent_color()

    # macOS native colors for semantic purposes
    MACOS_BLUE = MacOSColors.MACOS_BLUE  # System blue (for focus states)
    MACOS_GREEN = MacOSColors.MACOS_GREEN  # System green (success)
    MACOS_RED = MacOSColors.MACOS_RED  # System red (danger)
    MACOS_ORANGE = MacOSColors.MACOS_ORANGE  # System orange (warning)
    MACOS_GRAY = MacOSColors.MACOS_GRAY  # System gray (secondary)

    # Transparency helpers
    @staticmethod
    def with_alpha(color: str, alpha: float) -> str:
        """
        Convert hex color to rgba with specified alpha

        Args:
            color: Hex color string (e.g., "#667eea")
            alpha: Alpha value 0.0-1.0

        Returns:
            RGBA color string
        """
        color = color.lstrip("#")
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"

    @classmethod
    def gradient_primary(cls) -> str:
        """Primary gradient (vertical)"""
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {cls.ACCENT_PRIMARY}, stop:1 {cls.ACCENT_SECONDARY})"

    @classmethod
    def gradient_primary_horizontal(cls) -> str:
        """Primary gradient (horizontal)"""
        return f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {cls.ACCENT_PRIMARY}, stop:1 {cls.ACCENT_SECONDARY})"

    @classmethod
    def gradient_success(cls) -> str:
        """Success gradient"""
        return f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {cls.SUCCESS}, stop:1 #059669)"

    @classmethod
    def gradient_warning(cls) -> str:
        """Warning gradient"""
        return f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {cls.WARNING}, stop:1 #ea580c)"

    @classmethod
    def gradient_error(cls) -> str:
        """Error gradient"""
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {cls.ERROR}, stop:1 #dc2626)"

    # macOS-adaptive color methods (NEW)
    @classmethod
    def get_adaptive_background(cls, fallback: str = None) -> str:
        """
        Get background color that adapts to macOS appearance

        WHY: On macOS, uses system colors that change with light/dark mode.
             On other platforms, uses fallback or default.
        """
        if fallback is None:
            fallback = cls.BACKGROUND_PRIMARY
        return MacOSColors.get_adaptive_background(fallback)

    @classmethod
    def get_adaptive_text(cls, fallback: str = None) -> str:
        """Get text color that adapts to macOS appearance"""
        if fallback is None:
            fallback = cls.TEXT_PRIMARY
        return MacOSColors.get_adaptive_text(fallback)

    @classmethod
    def get_adaptive_accent(cls, fallback: str = None) -> str:
        """Get accent color that adapts to macOS system accent"""
        if fallback is None:
            fallback = cls.ACCENT_PRIMARY
        return MacOSColors.get_adaptive_accent(fallback)
