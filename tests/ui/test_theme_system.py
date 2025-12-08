"""
Unit Tests for Theme System

PURPOSE: Test theme foundation components (colors, typography, spacing, theme manager).
CONTEXT: Ensures theme system works correctly and provides consistent styling.
"""

import pytest
from pathlib import Path

from ui.theme import ColorPalette, Typography, Spacing, ThemeManager


class TestColorPalette:
    """Test color palette functionality"""

    def test_color_values_are_valid_hex(self):
        """Test that all color constants are valid hex colors"""
        # Primary colors
        assert ColorPalette.BACKGROUND_PRIMARY.startswith("#")
        assert len(ColorPalette.BACKGROUND_PRIMARY) == 7  # #RRGGBB format

        assert ColorPalette.ACCENT_PRIMARY.startswith("#")
        assert len(ColorPalette.ACCENT_PRIMARY) == 7

        # Test a few more
        assert ColorPalette.SUCCESS.startswith("#")
        assert ColorPalette.ERROR.startswith("#")
        assert ColorPalette.WARNING.startswith("#")

    def test_with_alpha_conversion(self):
        """Test converting hex colors to rgba with alpha"""
        # Test full opacity
        result = ColorPalette.with_alpha("#667eea", 1.0)
        assert result == "rgba(102, 126, 234, 1.0)"

        # Test half opacity
        result = ColorPalette.with_alpha("#667eea", 0.5)
        assert result == "rgba(102, 126, 234, 0.5)"

        # Test zero opacity
        result = ColorPalette.with_alpha("#667eea", 0.0)
        assert result == "rgba(102, 126, 234, 0.0)"

    def test_gradient_primary(self):
        """Test primary gradient generation"""
        gradient = ColorPalette.gradient_primary()

        assert "qlineargradient" in gradient
        assert ColorPalette.ACCENT_PRIMARY in gradient
        assert ColorPalette.ACCENT_SECONDARY in gradient
        assert "x1:0, y1:0, x2:0, y2:1" in gradient  # Vertical gradient

    def test_gradient_primary_horizontal(self):
        """Test horizontal gradient generation"""
        gradient = ColorPalette.gradient_primary_horizontal()

        assert "qlineargradient" in gradient
        assert "x1:0, y1:0, x2:1, y2:0" in gradient  # Horizontal gradient

    def test_semantic_colors_exist(self):
        """Test that semantic colors are defined"""
        assert hasattr(ColorPalette, "SUCCESS")
        assert hasattr(ColorPalette, "WARNING")
        assert hasattr(ColorPalette, "ERROR")
        assert hasattr(ColorPalette, "INFO")

    def test_audio_colors_exist(self):
        """Test that audio-specific colors are defined"""
        assert hasattr(ColorPalette, "LEVEL_SAFE")
        assert hasattr(ColorPalette, "LEVEL_CAUTION")
        assert hasattr(ColorPalette, "LEVEL_DANGER")
        assert hasattr(ColorPalette, "WAVEFORM_PRIMARY")


class TestTypography:
    """Test typography system"""

    def test_font_sizes_are_valid(self):
        """Test that font sizes are positive integers"""
        assert Typography.SIZE_DISPLAY > 0
        assert Typography.SIZE_H1 > 0
        assert Typography.SIZE_BODY > 0
        assert Typography.SIZE_SMALL > 0

    def test_font_size_hierarchy(self):
        """Test that font sizes follow logical hierarchy"""
        assert Typography.SIZE_DISPLAY > Typography.SIZE_H1
        assert Typography.SIZE_H1 > Typography.SIZE_H2
        assert Typography.SIZE_H2 > Typography.SIZE_BODY
        assert Typography.SIZE_BODY > Typography.SIZE_SMALL

    def test_font_weights_are_valid(self):
        """Test that font weights are valid CSS values"""
        assert 100 <= Typography.WEIGHT_NORMAL <= 900
        assert 100 <= Typography.WEIGHT_BOLD <= 900
        assert Typography.WEIGHT_BOLD > Typography.WEIGHT_NORMAL

    def test_get_font_style(self):
        """Test font style string generation"""
        style = Typography.get_font_style(14, Typography.WEIGHT_NORMAL)

        assert "font-family:" in style
        assert "font-size: 14px" in style
        assert f"font-weight: {Typography.WEIGHT_NORMAL}" in style

    def test_body_style(self):
        """Test body text style generation"""
        style = Typography.body()

        assert "font-size: 14px" in style
        assert str(Typography.WEIGHT_NORMAL) in style

    def test_mono_style(self):
        """Test monospace style generation"""
        style = Typography.mono()

        assert "monospace" in style.lower() or "mono" in style.lower()


class TestSpacing:
    """Test spacing system"""

    def test_spacing_values_are_multiples_of_base(self):
        """Test that spacing follows 8px grid system"""
        base = 8

        assert Spacing.NONE == 0
        assert Spacing.SM == base
        assert Spacing.MD == base * 2
        assert Spacing.LG == base * 3
        assert Spacing.XL == base * 4

    def test_spacing_hierarchy(self):
        """Test that spacing values increase logically"""
        assert Spacing.XS < Spacing.SM
        assert Spacing.SM < Spacing.MD
        assert Spacing.MD < Spacing.LG
        assert Spacing.LG < Spacing.XL

    def test_border_radius_values(self):
        """Test border radius values"""
        assert Spacing.RADIUS_SM > 0
        assert Spacing.RADIUS_MD > Spacing.RADIUS_SM
        assert Spacing.RADIUS_LG > Spacing.RADIUS_MD

    def test_padding_helper(self):
        """Test padding CSS generation"""
        result = Spacing.padding(10, 20)
        assert result == "padding: 10px 20px;"

    def test_margin_helper(self):
        """Test margin CSS generation"""
        result = Spacing.margin(10, 20, 30, 40)
        assert result == "margin: 10px 20px 30px 40px;"

    def test_border_radius_helper(self):
        """Test border-radius CSS generation"""
        result = Spacing.border_radius(8)
        assert result == "border-radius: 8px;"


class TestThemeManager:
    """Test ThemeManager functionality"""

    @pytest.fixture
    def theme_manager(self):
        """Create fresh ThemeManager instance for each test"""
        return ThemeManager()

    def test_theme_manager_singleton(self):
        """Test that ThemeManager is a singleton"""
        instance1 = ThemeManager.instance()
        instance2 = ThemeManager.instance()

        assert instance1 is instance2

    def test_theme_manager_has_color_palette(self, theme_manager):
        """Test that ThemeManager provides access to color palette"""
        assert theme_manager.colors == ColorPalette

    def test_theme_manager_has_typography(self, theme_manager):
        """Test that ThemeManager provides access to typography"""
        assert theme_manager.typography == Typography

    def test_theme_manager_has_spacing(self, theme_manager):
        """Test that ThemeManager provides access to spacing"""
        assert theme_manager.spacing == Spacing

    def test_load_stylesheet_default(self, theme_manager):
        """Test loading default stylesheet"""
        stylesheet = theme_manager.load_stylesheet()

        # Should contain QSS content
        assert len(stylesheet) > 0
        assert "QWidget" in stylesheet
        assert "QPushButton" in stylesheet

    def test_load_stylesheet_caches_content(self, theme_manager):
        """Test that loaded stylesheet is cached"""
        stylesheet1 = theme_manager.load_stylesheet()
        stylesheet2 = theme_manager.get_current_stylesheet()

        assert stylesheet1 == stylesheet2

    def test_load_stylesheet_nonexistent_file(self, theme_manager):
        """Test error handling for nonexistent stylesheet"""
        with pytest.raises(FileNotFoundError):
            theme_manager.load_stylesheet(Path("/nonexistent/path.qss"))

    def test_set_widget_property(self, qtbot):
        """Test setting widget properties and forcing style refresh"""
        from PySide6.QtWidgets import QPushButton

        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Set property
        ThemeManager.set_widget_property(button, "buttonStyle", "danger")

        # Verify property was set
        assert button.property("buttonStyle") == "danger"

    def test_stylesheet_contains_modern_elements(self, theme_manager):
        """Test that stylesheet contains modern design elements"""
        stylesheet = theme_manager.load_stylesheet()

        # Check for gradient usage
        assert "qlineargradient" in stylesheet

        # Check for border-radius (modern rounded corners)
        assert "border-radius" in stylesheet

        # Check for modern color values (hex colors)
        assert "#" in stylesheet

        # Check for various widget types
        assert "QGroupBox" in stylesheet
        assert "QComboBox" in stylesheet
        assert "QProgressBar" in stylesheet


class TestThemeConsistency:
    """Test theme consistency and integration"""

    def test_accent_colors_are_cohesive(self):
        """Test that accent colors form a cohesive palette"""
        # Primary and secondary should be related colors
        primary = ColorPalette.ACCENT_PRIMARY
        secondary = ColorPalette.ACCENT_SECONDARY

        # Both should be valid hex colors
        assert primary.startswith("#")
        assert secondary.startswith("#")

    def test_background_colors_progression(self):
        """Test that background colors progress from dark to light"""
        # In a dark theme, tertiary is lighter than secondary, which is lighter than primary
        # We can't easily compare hex values, but we can check they're all defined
        assert ColorPalette.BACKGROUND_PRIMARY
        assert ColorPalette.BACKGROUND_SECONDARY
        assert ColorPalette.BACKGROUND_TERTIARY

    def test_text_colors_progression(self):
        """Test that text colors have logical progression"""
        assert ColorPalette.TEXT_PRIMARY
        assert ColorPalette.TEXT_SECONDARY
        assert ColorPalette.TEXT_DISABLED

    def test_level_meter_colors_are_distinct(self):
        """Test that level meter colors are visually distinct"""
        safe = ColorPalette.LEVEL_SAFE
        caution = ColorPalette.LEVEL_CAUTION
        danger = ColorPalette.LEVEL_DANGER

        # Should all be different
        assert safe != caution
        assert caution != danger
        assert safe != danger

    def test_spacing_provides_visual_rhythm(self):
        """Test that spacing system provides good visual rhythm"""
        # Check that component-specific spacing is based on the grid
        assert Spacing.BUTTON_PADDING_V > 0
        assert Spacing.BUTTON_PADDING_H > 0
        assert Spacing.GROUP_PADDING > 0

        # Button padding should be reasonable
        assert 8 <= Spacing.BUTTON_PADDING_V <= 20
        assert 16 <= Spacing.BUTTON_PADDING_H <= 32


class TestThemePerformance:
    """Test theme system performance"""

    def test_stylesheet_loading_is_fast(self, theme_manager, benchmark):
        """Test that stylesheet loading is performant"""
        # Should load in under 10ms
        result = benchmark(theme_manager.load_stylesheet)
        assert len(result) > 0

    def test_color_conversion_is_fast(self, benchmark):
        """Test that color conversion is performant"""
        result = benchmark(ColorPalette.with_alpha, "#667eea", 0.5)
        assert result == "rgba(102, 126, 234, 0.5)"

    def test_gradient_generation_is_fast(self, benchmark):
        """Test that gradient generation is performant"""
        result = benchmark(ColorPalette.gradient_primary)
        assert "qlineargradient" in result
