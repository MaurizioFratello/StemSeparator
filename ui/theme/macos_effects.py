"""
macOS Visual Effects (Vibrancy, Blur, Translucency)

PURPOSE: Provides macOS-specific visual effects that create depth and hierarchy.
CONTEXT: Native macOS apps use translucent "frosted glass" backgrounds (Safari sidebar,
         Music, Finder, etc.). This module enables similar effects in Qt.
"""

from __future__ import annotations

import platform
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGraphicsBlurEffect, QGraphicsEffect


class MacOSEffects:
    """
    Apply macOS-specific visual effects

    WHY: Creates the signature macOS look with depth, translucency, and hierarchy.
         Makes Qt apps feel more native on macOS.
    """

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS"""
        return platform.system() == "Darwin"

    @staticmethod
    def apply_vibrancy(
        widget: QWidget, material: str = "dark", blend_mode: str = "behind-window"
    ) -> None:
        """
        Apply vibrancy/translucency effect to widget

        WHY: Creates the signature macOS "frosted glass" look that native apps use.
             This provides visual depth and makes the UI feel more premium.

        Args:
            widget: Widget to apply effect to
            material: "light" or "dark" material
            blend_mode: Blending mode (for future native implementation)

        Note:
            For true NSVisualEffectView vibrancy, we'd need PyObjC bindings.
            This implementation provides a close approximation using Qt.
        """
        if not MacOSEffects.is_macos():
            return  # macOS only

        try:
            # Enable translucent background
            widget.setAttribute(Qt.WA_TranslucentBackground, True)

            # Apply semi-transparent background to simulate vibrancy
            if material == "dark":
                alpha = 0.85
                bg_color = "rgba(30, 30, 30, {})".format(alpha)
            else:
                alpha = 0.90
                bg_color = "rgba(245, 245, 245, {})".format(alpha)

            # Apply stylesheet with transparency
            # Note: backdrop-filter is not supported in Qt, this is aspirational
            widget.setStyleSheet(
                f"""
                QWidget {{
                    background-color: {bg_color};
                }}
            """
            )

        except Exception:
            # Gracefully degrade if effect can't be applied
            pass

    @staticmethod
    def apply_sidebar_effect(widget: QWidget, dark: bool = True) -> None:
        """
        Apply sidebar vibrancy effect

        WHY: Replicates the translucent sidebar look from Finder, Music, etc.
             Provides visual separation while maintaining context awareness.

        Args:
            widget: Widget to apply sidebar effect to (typically sidebar/navigation)
            dark: Whether to use dark or light material
        """
        if not MacOSEffects.is_macos():
            return

        try:
            widget.setAttribute(Qt.WA_TranslucentBackground, True)

            if dark:
                bg_color = "rgba(40, 40, 40, 0.90)"
                border_color = "rgba(255, 255, 255, 0.05)"
            else:
                bg_color = "rgba(235, 235, 235, 0.92)"
                border_color = "rgba(0, 0, 0, 0.08)"

            widget.setStyleSheet(
                f"""
                QWidget {{
                    background-color: {bg_color};
                    border-right: 1px solid {border_color};
                }}
            """
            )

        except Exception:
            pass

    @staticmethod
    def apply_toolbar_effect(widget: QWidget, dark: bool = True) -> None:
        """
        Apply toolbar vibrancy effect

        WHY: Native macOS toolbars have subtle translucency and blend with window chrome.
             This makes the toolbar feel integrated with the title bar.

        Args:
            widget: Toolbar widget to apply effect to
            dark: Whether to use dark or light material
        """
        if not MacOSEffects.is_macos():
            return

        try:
            if dark:
                bg_color = "rgba(45, 45, 45, 0.95)"
                border_color = "rgba(255, 255, 255, 0.1)"
            else:
                bg_color = "rgba(250, 250, 250, 0.95)"
                border_color = "rgba(0, 0, 0, 0.1)"

            widget.setStyleSheet(
                f"""
                QWidget {{
                    background-color: {bg_color};
                    border-bottom: 0.5px solid {border_color};
                }}
            """
            )

        except Exception:
            pass

    @staticmethod
    def apply_blur_effect(
        widget: QWidget, blur_radius: float = 10.0
    ) -> Optional[QGraphicsEffect]:
        """
        Apply Gaussian blur effect

        WHY: Can be used for modal overlays, disabled states, or background content.
             Adds depth and focus to UI hierarchy.

        Args:
            widget: Widget to blur
            blur_radius: Blur radius in pixels (higher = more blur)

        Returns:
            The QGraphicsBlurEffect applied, or None if failed
        """
        try:
            blur_effect = QGraphicsBlurEffect()
            blur_effect.setBlurRadius(blur_radius)
            widget.setGraphicsEffect(blur_effect)
            return blur_effect
        except Exception:
            return None

    @staticmethod
    def remove_effects(widget: QWidget) -> None:
        """
        Remove all visual effects from widget

        WHY: Useful for cleanup or toggling effects on/off

        Args:
            widget: Widget to remove effects from
        """
        try:
            widget.setAttribute(Qt.WA_TranslucentBackground, False)
            widget.setGraphicsEffect(None)
            widget.setStyleSheet("")  # Clear custom styles
        except Exception:
            pass

    @staticmethod
    def apply_hover_lift(widget: QWidget, lift_amount: int = 2) -> None:
        """
        Apply subtle lift effect on hover (macOS Big Sur style)

        WHY: macOS Big Sur+ uses subtle elevation changes to indicate interactivity.
             Buttons and cards appear to "lift" slightly on hover.

        Args:
            widget: Widget to apply lift effect to
            lift_amount: Pixels to lift (typically 1-3px)

        Note:
            This would be better implemented with animations, but requires
            more complex integration. For now, this sets up the foundation.
        """
        # This would require animation support, left for future enhancement
        # Placeholder for documentation
        pass

    @staticmethod
    def set_corner_radius(widget: QWidget, radius: int = 8) -> None:
        """
        Set rounded corners on widget

        WHY: macOS design language uses rounded corners extensively (since Big Sur).
             Softer corners feel more approachable and modern.

        Args:
            widget: Widget to round corners of
            radius: Corner radius in pixels
        """
        try:
            widget.setStyleSheet(
                f"""
                QWidget {{
                    border-radius: {radius}px;
                }}
            """
            )
        except Exception:
            pass

    @staticmethod
    def apply_shadow(
        widget: QWidget,
        color: str = "rgba(0, 0, 0, 0.3)",
        offset_x: int = 0,
        offset_y: int = 2,
        blur_radius: int = 8,
    ) -> None:
        """
        Apply drop shadow to widget

        WHY: Shadows create depth and hierarchy in the UI, separating floating
             elements like popovers, tooltips, and elevated cards.

        Args:
            widget: Widget to add shadow to
            color: Shadow color (supports rgba)
            offset_x: Horizontal offset
            offset_y: Vertical offset
            blur_radius: Shadow blur radius

        Note:
            Qt's shadow support is limited. For production, consider using
            QGraphicsDropShadowEffect or custom painting.
        """
        # Note: This would require QGraphicsDropShadowEffect for true shadows
        # Leaving as placeholder for documentation and future implementation
        pass


def get_macos_effects() -> MacOSEffects:
    """Get MacOSEffects instance (for convenience)"""
    return MacOSEffects
