"""
Animation helpers for smooth macOS-style transitions

PURPOSE: Provide reusable animation utilities for polished UI interactions
CONTEXT: macOS apps use subtle, fast animations (typically 250ms ease-in-out)
         This module standardizes animation behavior across the app
"""

from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import (
    QPropertyAnimation,
    QEasingCurve,
    QObject,
    QPoint,
    QRect,
    QSize,
    Property,
    Signal,
)
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PySide6.QtGui import QColor


class Animations:
    """
    Animation utility class for creating smooth transitions

    WHY: Consistent, subtle animations improve perceived performance
         macOS standard is 250ms ease-in-out for most transitions
    """

    # macOS animation timing standards
    DURATION_FAST = 150  # Quick feedback (button presses, hovers)
    DURATION_NORMAL = 250  # Standard transitions (most UI changes)
    DURATION_SLOW = 350  # Deliberate transitions (sheet appearances)

    # Easing curves (macOS uses ease-in-out for most animations)
    EASING_DEFAULT = QEasingCurve.InOutQuad  # Smooth start and end
    EASING_SHARP = QEasingCurve.InOutCubic  # More pronounced curve
    EASING_SMOOTH = QEasingCurve.InOutSine  # Very gentle

    @classmethod
    def fade_in(
        cls,
        widget: QWidget,
        duration: int = DURATION_NORMAL,
        on_finished: Optional[Callable] = None,
    ) -> QPropertyAnimation:
        """
        Fade in a widget from transparent to opaque

        Args:
            widget: Widget to fade in
            duration: Animation duration in milliseconds
            on_finished: Optional callback when animation finishes

        Returns:
            QPropertyAnimation instance (auto-starts)
        """
        # Create opacity effect if not present
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        # Create animation
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(cls.EASING_DEFAULT)

        if on_finished:
            animation.finished.connect(on_finished)

        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    @classmethod
    def fade_out(
        cls,
        widget: QWidget,
        duration: int = DURATION_NORMAL,
        on_finished: Optional[Callable] = None,
        hide_when_done: bool = True,
    ) -> QPropertyAnimation:
        """
        Fade out a widget from opaque to transparent

        Args:
            widget: Widget to fade out
            duration: Animation duration in milliseconds
            on_finished: Optional callback when animation finishes
            hide_when_done: If True, hide widget when animation completes

        Returns:
            QPropertyAnimation instance (auto-starts)
        """
        # Create opacity effect if not present
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        # Create animation
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(cls.EASING_DEFAULT)

        # Hide widget when done if requested
        if hide_when_done:
            animation.finished.connect(widget.hide)

        if on_finished:
            animation.finished.connect(on_finished)

        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    @classmethod
    def slide_in(
        cls,
        widget: QWidget,
        direction: str = "bottom",
        distance: int = 20,
        duration: int = DURATION_NORMAL,
        on_finished: Optional[Callable] = None,
    ) -> QPropertyAnimation:
        """
        Slide widget in from specified direction

        Args:
            widget: Widget to animate
            direction: Direction to slide from ("top", "bottom", "left", "right")
            distance: Distance to slide in pixels
            duration: Animation duration in milliseconds
            on_finished: Optional callback when animation finishes

        Returns:
            QPropertyAnimation instance (auto-starts)
        """
        # Calculate start and end positions
        current_pos = widget.pos()

        if direction == "bottom":
            start_pos = QPoint(current_pos.x(), current_pos.y() + distance)
        elif direction == "top":
            start_pos = QPoint(current_pos.x(), current_pos.y() - distance)
        elif direction == "right":
            start_pos = QPoint(current_pos.x() + distance, current_pos.y())
        elif direction == "left":
            start_pos = QPoint(current_pos.x() - distance, current_pos.y())
        else:
            start_pos = current_pos

        # Create animation
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(current_pos)
        animation.setEasingCurve(cls.EASING_DEFAULT)

        if on_finished:
            animation.finished.connect(on_finished)

        # Set initial position and start
        widget.move(start_pos)
        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    @classmethod
    def slide_out(
        cls,
        widget: QWidget,
        direction: str = "bottom",
        distance: int = 20,
        duration: int = DURATION_NORMAL,
        on_finished: Optional[Callable] = None,
        hide_when_done: bool = True,
    ) -> QPropertyAnimation:
        """
        Slide widget out in specified direction

        Args:
            widget: Widget to animate
            direction: Direction to slide to ("top", "bottom", "left", "right")
            distance: Distance to slide in pixels
            duration: Animation duration in milliseconds
            on_finished: Optional callback when animation finishes
            hide_when_done: If True, hide widget when animation completes

        Returns:
            QPropertyAnimation instance (auto-starts)
        """
        # Calculate start and end positions
        current_pos = widget.pos()

        if direction == "bottom":
            end_pos = QPoint(current_pos.x(), current_pos.y() + distance)
        elif direction == "top":
            end_pos = QPoint(current_pos.x(), current_pos.y() - distance)
        elif direction == "right":
            end_pos = QPoint(current_pos.x() + distance, current_pos.y())
        elif direction == "left":
            end_pos = QPoint(current_pos.x() - distance, current_pos.y())
        else:
            end_pos = current_pos

        # Create animation
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(current_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(cls.EASING_DEFAULT)

        # Hide widget when done if requested
        if hide_when_done:
            animation.finished.connect(widget.hide)

        if on_finished:
            animation.finished.connect(on_finished)

        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    @classmethod
    def scale_in(
        cls,
        widget: QWidget,
        duration: int = DURATION_FAST,
        on_finished: Optional[Callable] = None,
    ) -> QPropertyAnimation:
        """
        Scale widget in from 90% to 100% (subtle pop-in effect)

        Args:
            widget: Widget to animate
            duration: Animation duration in milliseconds
            on_finished: Optional callback when animation finishes

        Returns:
            QPropertyAnimation instance (auto-starts)

        WHY: Subtle scale adds polish to appearing elements (menus, tooltips)
        """
        current_size = widget.size()
        start_size = QSize(
            int(current_size.width() * 0.9), int(current_size.height() * 0.9)
        )

        animation = QPropertyAnimation(widget, b"size")
        animation.setDuration(duration)
        animation.setStartValue(start_size)
        animation.setEndValue(current_size)
        animation.setEasingCurve(cls.EASING_SHARP)

        if on_finished:
            animation.finished.connect(on_finished)

        widget.resize(start_size)
        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    @classmethod
    def pulse(
        cls,
        widget: QWidget,
        duration: int = DURATION_FAST,
        scale_factor: float = 1.05,
        on_finished: Optional[Callable] = None,
    ) -> QPropertyAnimation:
        """
        Pulse widget slightly larger and back (for button feedback)

        Args:
            widget: Widget to animate
            duration: Animation duration in milliseconds (for one direction)
            scale_factor: How much to scale up (1.05 = 5% larger)
            on_finished: Optional callback when animation finishes

        Returns:
            QPropertyAnimation instance (auto-starts)

        WHY: Subtle pulse provides tactile feedback for interactions
        """
        current_size = widget.size()
        scaled_size = QSize(
            int(current_size.width() * scale_factor),
            int(current_size.height() * scale_factor),
        )

        # Scale up
        animation = QPropertyAnimation(widget, b"size")
        animation.setDuration(duration)
        animation.setStartValue(current_size)
        animation.setEndValue(scaled_size)
        animation.setEasingCurve(QEasingCurve.OutQuad)

        # Scale back down
        def scale_back():
            back_animation = QPropertyAnimation(widget, b"size")
            back_animation.setDuration(duration)
            back_animation.setStartValue(scaled_size)
            back_animation.setEndValue(current_size)
            back_animation.setEasingCurve(QEasingCurve.InQuad)

            if on_finished:
                back_animation.finished.connect(on_finished)

            back_animation.start(QPropertyAnimation.DeleteWhenStopped)

        animation.finished.connect(scale_back)
        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    @classmethod
    def smooth_scroll(
        cls,
        scroll_widget,
        target_value: int,
        duration: int = DURATION_NORMAL,
        orientation: str = "vertical",
    ) -> QPropertyAnimation:
        """
        Smoothly animate scrollbar to target position

        Args:
            scroll_widget: QScrollBar or QScrollArea
            target_value: Target scroll position
            duration: Animation duration in milliseconds
            orientation: "vertical" or "horizontal"

        Returns:
            QPropertyAnimation instance (auto-starts)

        WHY: Smooth scrolling feels more natural than instant jumps
        """
        # Get the appropriate scroll bar
        if hasattr(scroll_widget, "verticalScrollBar"):
            scrollbar = (
                scroll_widget.verticalScrollBar()
                if orientation == "vertical"
                else scroll_widget.horizontalScrollBar()
            )
        else:
            scrollbar = scroll_widget

        animation = QPropertyAnimation(scrollbar, b"value")
        animation.setDuration(duration)
        animation.setStartValue(scrollbar.value())
        animation.setEndValue(target_value)
        animation.setEasingCurve(cls.EASING_DEFAULT)

        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation


def get_animations() -> type[Animations]:
    """
    Convenience function to get Animations class

    Returns:
        Animations class
    """
    return Animations
