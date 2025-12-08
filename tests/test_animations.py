"""
Unit tests for animation helpers

PURPOSE: Test animation utility functions for smooth transitions
CONTEXT: Ensures animations work correctly and don't cause crashes
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QSize
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect, QScrollArea, QScrollBar
from PySide6.QtCore import Qt

from ui.theme.animations import Animations


class TestAnimations:
    """Test suite for Animations functionality"""

    def test_duration_constants(self):
        """Test animation duration constants are reasonable"""
        assert Animations.DURATION_FAST > 0
        assert Animations.DURATION_NORMAL > Animations.DURATION_FAST
        assert Animations.DURATION_SLOW > Animations.DURATION_NORMAL

        # macOS standard timing
        assert Animations.DURATION_NORMAL == 250

    def test_easing_curve_constants(self):
        """Test easing curve constants are valid"""
        assert isinstance(Animations.EASING_DEFAULT, QEasingCurve.Type)
        assert isinstance(Animations.EASING_SHARP, QEasingCurve.Type)
        assert isinstance(Animations.EASING_SMOOTH, QEasingCurve.Type)

    def test_fade_in_creates_opacity_effect(self, qtbot):
        """Test fade in creates opacity effect if not present"""
        widget = QWidget()
        qtbot.addWidget(widget)

        animation = Animations.fade_in(widget, duration=100)

        # Should have opacity effect
        assert widget.graphicsEffect() is not None
        assert isinstance(widget.graphicsEffect(), QGraphicsOpacityEffect)

        # Animation should be running
        assert animation is not None

    def test_fade_in_uses_existing_opacity_effect(self, qtbot):
        """Test fade in reuses existing opacity effect"""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Add effect first
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        animation = Animations.fade_in(widget, duration=100)

        # Should reuse same effect
        assert widget.graphicsEffect() is effect

    def test_fade_in_animation_properties(self, qtbot):
        """Test fade in animation has correct properties"""
        widget = QWidget()
        qtbot.addWidget(widget)

        duration = 200
        animation = Animations.fade_in(widget, duration=duration)

        # Check animation properties (before it auto-deletes)
        assert animation.duration() == duration
        assert animation.startValue() == 0.0
        assert animation.endValue() == 1.0

    def test_fade_in_with_callback(self, qtbot):
        """Test fade in calls callback when finished"""
        widget = QWidget()
        qtbot.addWidget(widget)

        callback = Mock()
        animation = Animations.fade_in(widget, duration=50, on_finished=callback)

        # Wait for animation to complete
        qtbot.wait(100)

        # Callback should have been called
        callback.assert_called_once()

    def test_fade_out_creates_opacity_effect(self, qtbot):
        """Test fade out creates opacity effect if not present"""
        widget = QWidget()
        qtbot.addWidget(widget)

        animation = Animations.fade_out(widget, duration=100)

        # Should have opacity effect
        assert widget.graphicsEffect() is not None
        assert isinstance(widget.graphicsEffect(), QGraphicsOpacityEffect)

    def test_fade_out_hides_widget_when_done(self, qtbot):
        """Test fade out hides widget after animation"""
        widget = QWidget()
        widget.show()
        qtbot.addWidget(widget)

        Animations.fade_out(widget, duration=50, hide_when_done=True)

        # Wait for animation to complete
        qtbot.wait(100)

        # Widget should be hidden
        assert not widget.isVisible()

    def test_fade_out_doesnt_hide_if_disabled(self, qtbot):
        """Test fade out doesn't hide widget if hide_when_done=False"""
        widget = QWidget()
        widget.show()
        qtbot.addWidget(widget)

        Animations.fade_out(widget, duration=50, hide_when_done=False)

        # Wait for animation to complete
        qtbot.wait(100)

        # Widget should still be visible
        assert widget.isVisible()

    def test_slide_in_from_bottom(self, qtbot):
        """Test slide in from bottom"""
        widget = QWidget()
        qtbot.addWidget(widget)

        original_pos = QPoint(100, 100)
        widget.move(original_pos)

        animation = Animations.slide_in(
            widget, direction="bottom", distance=20, duration=100
        )

        # Animation should be created
        assert animation is not None

        # Wait for animation
        qtbot.wait(150)

        # Widget should be back at original position
        assert widget.pos() == original_pos

    def test_slide_in_from_top(self, qtbot):
        """Test slide in from top"""
        widget = QWidget()
        qtbot.addWidget(widget)

        original_pos = QPoint(100, 100)
        widget.move(original_pos)

        animation = Animations.slide_in(
            widget, direction="top", distance=20, duration=100
        )
        assert animation is not None

    def test_slide_in_from_left(self, qtbot):
        """Test slide in from left"""
        widget = QWidget()
        qtbot.addWidget(widget)

        animation = Animations.slide_in(
            widget, direction="left", distance=20, duration=100
        )
        assert animation is not None

    def test_slide_in_from_right(self, qtbot):
        """Test slide in from right"""
        widget = QWidget()
        qtbot.addWidget(widget)

        animation = Animations.slide_in(
            widget, direction="right", distance=20, duration=100
        )
        assert animation is not None

    def test_slide_out_to_bottom(self, qtbot):
        """Test slide out to bottom"""
        widget = QWidget()
        qtbot.addWidget(widget)

        animation = Animations.slide_out(
            widget, direction="bottom", distance=20, duration=100
        )
        assert animation is not None

    def test_slide_out_hides_when_done(self, qtbot):
        """Test slide out hides widget after animation"""
        widget = QWidget()
        widget.show()
        qtbot.addWidget(widget)

        Animations.slide_out(
            widget, direction="bottom", distance=20, duration=50, hide_when_done=True
        )

        # Wait for animation to complete
        qtbot.wait(100)

        # Widget should be hidden
        assert not widget.isVisible()

    def test_scale_in_animation(self, qtbot):
        """Test scale in animation"""
        widget = QWidget()
        widget.resize(100, 100)
        qtbot.addWidget(widget)

        animation = Animations.scale_in(widget, duration=100)

        # Animation should be created
        assert animation is not None

        # Wait for animation
        qtbot.wait(150)

        # Widget should be back to original size
        assert widget.size() == QSize(100, 100)

    def test_scale_in_with_callback(self, qtbot):
        """Test scale in calls callback when finished"""
        widget = QWidget()
        widget.resize(100, 100)
        qtbot.addWidget(widget)

        callback = Mock()
        Animations.scale_in(widget, duration=50, on_finished=callback)

        # Wait for animation
        qtbot.wait(100)

        # Callback should have been called
        callback.assert_called_once()

    def test_pulse_animation(self, qtbot):
        """Test pulse animation"""
        widget = QWidget()
        widget.resize(100, 100)
        qtbot.addWidget(widget)

        animation = Animations.pulse(widget, duration=50, scale_factor=1.1)

        # Animation should be created
        assert animation is not None

        # Wait for full pulse (up and down)
        qtbot.wait(150)

        # Widget should be back to original size
        assert widget.size() == QSize(100, 100)

    def test_pulse_with_callback(self, qtbot):
        """Test pulse calls callback when finished"""
        widget = QWidget()
        widget.resize(100, 100)
        qtbot.addWidget(widget)

        callback = Mock()
        Animations.pulse(widget, duration=30, on_finished=callback)

        # Wait for full pulse
        qtbot.wait(100)

        # Callback should have been called
        callback.assert_called_once()

    def test_smooth_scroll_vertical(self, qtbot):
        """Test smooth scroll on vertical scrollbar"""
        scroll_area = QScrollArea()
        qtbot.addWidget(scroll_area)

        # Add content to make scrollbar active
        content = QWidget()
        content.setMinimumSize(100, 1000)
        scroll_area.setWidget(content)

        animation = Animations.smooth_scroll(
            scroll_area, target_value=100, duration=100, orientation="vertical"
        )

        # Animation should be created
        assert animation is not None

    def test_smooth_scroll_horizontal(self, qtbot):
        """Test smooth scroll on horizontal scrollbar"""
        scroll_area = QScrollArea()
        qtbot.addWidget(scroll_area)

        # Add content to make scrollbar active
        content = QWidget()
        content.setMinimumSize(1000, 100)
        scroll_area.setWidget(content)

        animation = Animations.smooth_scroll(
            scroll_area, target_value=100, duration=100, orientation="horizontal"
        )

        # Animation should be created
        assert animation is not None

    def test_smooth_scroll_on_scrollbar_directly(self, qtbot):
        """Test smooth scroll on QScrollBar directly"""
        scrollbar = QScrollBar()
        scrollbar.setRange(0, 1000)
        qtbot.addWidget(scrollbar)

        animation = Animations.smooth_scroll(scrollbar, target_value=500, duration=100)

        # Animation should be created
        assert animation is not None

    def test_get_animations_returns_class(self):
        """Test convenience function returns Animations class"""
        from ui.theme.animations import get_animations

        result = get_animations()
        assert result is Animations

    def test_fade_in_default_duration(self, qtbot):
        """Test fade in uses default duration"""
        widget = QWidget()
        qtbot.addWidget(widget)

        animation = Animations.fade_in(widget)

        # Should use DURATION_NORMAL by default
        assert animation.duration() == Animations.DURATION_NORMAL

    def test_slide_in_invalid_direction(self, qtbot):
        """Test slide in with invalid direction doesn't crash"""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Should not crash with invalid direction
        animation = Animations.slide_in(widget, direction="invalid", duration=100)
        assert animation is not None
