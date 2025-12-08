"""
Unit tests for macOS visual effects

PURPOSE: Test macOS vibrancy, blur, and translucency effects
CONTEXT: Ensures effects apply correctly on macOS and gracefully degrade elsewhere
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor

from ui.theme.macos_effects import MacOSEffects


class TestMacOSEffects:
    """Test suite for MacOSEffects functionality"""

    def test_is_macos_on_darwin(self):
        """Test macOS detection returns True on Darwin"""
        with patch("platform.system", return_value="Darwin"):
            assert MacOSEffects.is_macos() is True

    def test_is_macos_on_linux(self):
        """Test macOS detection returns False on Linux"""
        with patch("platform.system", return_value="Linux"):
            assert MacOSEffects.is_macos() is False

    def test_apply_vibrancy_on_non_macos(self, qtbot):
        """Test vibrancy does nothing on non-macOS systems"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Linux"):
            # Should not raise exception
            MacOSEffects.apply_vibrancy(widget)

        # Should not have modified widget
        assert not widget.testAttribute(Qt.WA_TranslucentBackground)

    def test_apply_vibrancy_dark_material(self, qtbot):
        """Test applying dark vibrancy material"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_vibrancy(widget, material="dark")

        # Should enable translucency
        assert widget.testAttribute(Qt.WA_TranslucentBackground)

        # Should have stylesheet with dark background
        stylesheet = widget.styleSheet()
        assert "rgba" in stylesheet.lower()

    def test_apply_vibrancy_light_material(self, qtbot):
        """Test applying light vibrancy material"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_vibrancy(widget, material="light")

        # Should enable translucency
        assert widget.testAttribute(Qt.WA_TranslucentBackground)

        # Should have stylesheet
        stylesheet = widget.styleSheet()
        assert "rgba" in stylesheet.lower()

    def test_apply_sidebar_effect_on_non_macos(self, qtbot):
        """Test sidebar effect does nothing on non-macOS"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Windows"):
            MacOSEffects.apply_sidebar_effect(widget)

        # Should not modify widget
        assert not widget.testAttribute(Qt.WA_TranslucentBackground)

    def test_apply_sidebar_effect_dark(self, qtbot):
        """Test applying dark sidebar effect"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_sidebar_effect(widget, dark=True)

        assert widget.testAttribute(Qt.WA_TranslucentBackground)
        stylesheet = widget.styleSheet()
        assert "rgba" in stylesheet.lower()
        assert "border-right" in stylesheet.lower()

    def test_apply_sidebar_effect_light(self, qtbot):
        """Test applying light sidebar effect"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_sidebar_effect(widget, dark=False)

        assert widget.testAttribute(Qt.WA_TranslucentBackground)
        stylesheet = widget.styleSheet()
        assert "rgba" in stylesheet.lower()

    def test_apply_toolbar_effect_on_non_macos(self, qtbot):
        """Test toolbar effect does nothing on non-macOS"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Linux"):
            MacOSEffects.apply_toolbar_effect(widget)

        # Should not modify stylesheet
        assert widget.styleSheet() == ""

    def test_apply_toolbar_effect_dark(self, qtbot):
        """Test applying dark toolbar effect"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_toolbar_effect(widget, dark=True)

        stylesheet = widget.styleSheet()
        assert "rgba" in stylesheet.lower()
        assert "border-bottom" in stylesheet.lower()

    def test_apply_toolbar_effect_light(self, qtbot):
        """Test applying light toolbar effect"""
        widget = QWidget()
        qtbot.addWidget(widget)

        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_toolbar_effect(widget, dark=False)

        stylesheet = widget.styleSheet()
        assert "rgba" in stylesheet.lower()

    def test_apply_blur_effect(self, qtbot):
        """Test applying blur effect"""
        widget = QWidget()
        qtbot.addWidget(widget)

        effect = MacOSEffects.apply_blur_effect(widget, blur_radius=15.0)

        # Should return a blur effect
        assert effect is not None
        assert effect.blurRadius() == 15.0

        # Widget should have the effect applied
        assert widget.graphicsEffect() is effect

    def test_apply_blur_effect_default_radius(self, qtbot):
        """Test blur effect with default radius"""
        widget = QWidget()
        qtbot.addWidget(widget)

        effect = MacOSEffects.apply_blur_effect(widget)

        assert effect is not None
        assert effect.blurRadius() == 10.0

    def test_remove_effects(self, qtbot):
        """Test removing all effects from widget"""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Apply some effects first
        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_vibrancy(widget)
            MacOSEffects.apply_blur_effect(widget)

        # Remove effects
        MacOSEffects.remove_effects(widget)

        # Should have no effects
        assert not widget.testAttribute(Qt.WA_TranslucentBackground)
        assert widget.graphicsEffect() is None
        assert widget.styleSheet() == ""

    def test_set_corner_radius(self, qtbot):
        """Test setting corner radius"""
        widget = QWidget()
        qtbot.addWidget(widget)

        MacOSEffects.set_corner_radius(widget, radius=12)

        stylesheet = widget.styleSheet()
        assert "border-radius" in stylesheet.lower()
        assert "12px" in stylesheet

    def test_set_corner_radius_default(self, qtbot):
        """Test corner radius with default value"""
        widget = QWidget()
        qtbot.addWidget(widget)

        MacOSEffects.set_corner_radius(widget)

        stylesheet = widget.styleSheet()
        assert "border-radius" in stylesheet.lower()
        assert "8px" in stylesheet

    def test_apply_shadow_placeholder(self, qtbot):
        """Test shadow application (placeholder implementation)"""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Should not raise exception
        MacOSEffects.apply_shadow(widget)

    def test_apply_hover_lift_placeholder(self, qtbot):
        """Test hover lift (placeholder implementation)"""
        widget = QWidget()
        qtbot.addWidget(widget)

        # Should not raise exception
        MacOSEffects.apply_hover_lift(widget, lift_amount=3)

    def test_vibrancy_graceful_degradation(self, qtbot):
        """Test vibrancy degrades gracefully on error"""
        # Create a mock widget that raises exception on setAttribute
        widget = Mock(spec=QWidget)
        widget.setAttribute.side_effect = Exception("Test error")

        # Should not raise exception
        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_vibrancy(widget)

    def test_sidebar_graceful_degradation(self, qtbot):
        """Test sidebar effect degrades gracefully on error"""
        widget = Mock(spec=QWidget)
        widget.setAttribute.side_effect = Exception("Test error")

        # Should not raise exception
        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_sidebar_effect(widget)

    def test_toolbar_graceful_degradation(self, qtbot):
        """Test toolbar effect degrades gracefully on error"""
        widget = Mock(spec=QWidget)
        widget.setStyleSheet.side_effect = Exception("Test error")

        # Should not raise exception
        with patch("platform.system", return_value="Darwin"):
            MacOSEffects.apply_toolbar_effect(widget)

    def test_blur_effect_error_handling(self, qtbot):
        """Test blur effect returns None on error"""
        # This will fail to create effect if Qt is not fully initialized
        widget = Mock(spec=QWidget)

        with patch("ui.theme.macos_effects.QGraphicsBlurEffect", side_effect=Exception):
            result = MacOSEffects.apply_blur_effect(widget)
            assert result is None

    def test_remove_effects_error_handling(self, qtbot):
        """Test remove effects doesn't crash on error"""
        widget = Mock(spec=QWidget)
        widget.setAttribute.side_effect = Exception("Test error")

        # Should not raise exception
        MacOSEffects.remove_effects(widget)

    def test_get_macos_effects_returns_class(self):
        """Test convenience function returns MacOSEffects class"""
        from ui.theme.macos_effects import get_macos_effects

        result = get_macos_effects()
        assert result is MacOSEffects
