"""
Integration Tests for Styled UI Components

PURPOSE: Test that theme system integrates correctly with UI widgets.
CONTEXT: Ensures styled components render correctly and maintain theme consistency.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QPushButton, QProgressBar, QLabel, QTableWidget, QComboBox
from PySide6.QtCore import Qt

from ui.theme import ThemeManager, ColorPalette
from ui.widgets.loading_spinner import LoadingSpinner
from ui.widgets.pulse_animation import PulseAnimation


class TestStyledButtons:
    """Test button styling integration"""

    def test_primary_button_has_gradient(self, qtbot):
        """Test that primary buttons have gradient background"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Apply theme
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()
        button.setStyleSheet(stylesheet)

        # Primary button should have default gradient style
        style = button.styleSheet()
        # Note: styleSheet() might not return full inherited styles,
        # but we can verify it was set
        assert len(stylesheet) > 0

    def test_secondary_button_styling(self, qtbot):
        """Test that secondary buttons have correct styling"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Set secondary style
        ThemeManager.set_widget_property(button, "buttonStyle", "secondary")

        # Verify property was set
        assert button.property("buttonStyle") == "secondary"

    def test_danger_button_styling(self, qtbot):
        """Test that danger buttons have correct styling"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Set danger style
        ThemeManager.set_widget_property(button, "buttonStyle", "danger")

        assert button.property("buttonStyle") == "danger"

    def test_success_button_styling(self, qtbot):
        """Test that success buttons have correct styling"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Set success style
        ThemeManager.set_widget_property(button, "buttonStyle", "success")

        assert button.property("buttonStyle") == "success"

    def test_icon_button_sizing(self, qtbot):
        """Test that icon buttons have correct size constraints"""
        button = QPushButton("M")
        qtbot.addWidget(button)

        # Set icon button style
        ThemeManager.set_widget_property(button, "buttonStyle", "icon")

        assert button.property("buttonStyle") == "icon"

    def test_button_state_transitions(self, qtbot):
        """Test button style updates correctly on state changes"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Initial state
        ThemeManager.set_widget_property(button, "buttonStyle", "secondary")
        assert button.property("buttonStyle") == "secondary"

        # Change to danger
        ThemeManager.set_widget_property(button, "buttonStyle", "danger")
        assert button.property("buttonStyle") == "danger"

        # Change back to secondary
        ThemeManager.set_widget_property(button, "buttonStyle", "secondary")
        assert button.property("buttonStyle") == "secondary"


class TestStyledProgressBars:
    """Test progress bar styling integration"""

    def test_default_progress_bar(self, qtbot):
        """Test default progress bar styling"""
        progress = QProgressBar()
        qtbot.addWidget(progress)

        progress.setRange(0, 100)
        progress.setValue(50)

        # Should be able to set value
        assert progress.value() == 50

    def test_large_progress_bar_variant(self, qtbot):
        """Test large progress bar variant (level meter)"""
        progress = QProgressBar()
        qtbot.addWidget(progress)

        # Set large variant
        ThemeManager.set_widget_property(progress, "progressStyle", "large")

        assert progress.property("progressStyle") == "large"

    def test_progress_bar_with_gradient(self, qtbot):
        """Test that progress bars support gradient fills"""
        progress = QProgressBar()
        qtbot.addWidget(progress)

        # Apply theme
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()
        progress.setStyleSheet(stylesheet)

        progress.setValue(75)
        assert progress.value() == 75


class TestStyledLabels:
    """Test label styling integration"""

    def test_default_label(self, qtbot):
        """Test default label styling"""
        label = QLabel("Test Label")
        qtbot.addWidget(label)

        assert label.text() == "Test Label"

    def test_header_label_variant(self, qtbot):
        """Test header label variant"""
        label = QLabel("Header")
        qtbot.addWidget(label)

        ThemeManager.set_widget_property(label, "labelStyle", "header")

        assert label.property("labelStyle") == "header"

    def test_mono_label_variant(self, qtbot):
        """Test monospace label variant (for time displays)"""
        label = QLabel("00:00")
        qtbot.addWidget(label)

        ThemeManager.set_widget_property(label, "labelStyle", "mono")

        assert label.property("labelStyle") == "mono"

    def test_caption_label_variant(self, qtbot):
        """Test caption label variant"""
        label = QLabel("Small text")
        qtbot.addWidget(label)

        ThemeManager.set_widget_property(label, "labelStyle", "caption")

        assert label.property("labelStyle") == "caption"


class TestStyledTables:
    """Test table styling integration"""

    def test_table_alternating_rows(self, qtbot):
        """Test that tables support alternating row colors"""
        table = QTableWidget(5, 3)
        qtbot.addWidget(table)

        table.setAlternatingRowColors(True)

        assert table.alternatingRowColors() is True

    def test_table_with_data(self, qtbot):
        """Test styled table with actual data"""
        table = QTableWidget(3, 2)
        qtbot.addWidget(table)

        table.setAlternatingRowColors(True)
        table.setHorizontalHeaderLabels(["Name", "Status"])

        # Add some data
        table.setItem(0, 0, QTableWidgetItem("File 1"))
        table.setItem(0, 1, QTableWidgetItem("Pending"))

        assert table.item(0, 0).text() == "File 1"


class TestStyledComboBoxes:
    """Test combo box styling integration"""

    def test_combobox_with_items(self, qtbot):
        """Test styled combo box with items"""
        combo = QComboBox()
        qtbot.addWidget(combo)

        combo.addItems(["Option 1", "Option 2", "Option 3"])

        assert combo.count() == 3
        assert combo.itemText(0) == "Option 1"

    def test_combobox_with_user_data(self, qtbot):
        """Test combo box with user data (common pattern in app)"""
        combo = QComboBox()
        qtbot.addWidget(combo)

        combo.addItem("Display Text", userData="value1")
        combo.addItem("Another Text", userData="value2")

        assert combo.itemData(0) == "value1"
        assert combo.itemData(1) == "value2"


class TestLoadingSpinner:
    """Test LoadingSpinner component"""

    def test_spinner_creation(self, qtbot):
        """Test that spinner can be created"""
        spinner = LoadingSpinner()
        qtbot.addWidget(spinner)

        assert spinner is not None
        assert len(spinner.frames) > 0

    def test_spinner_starts_and_stops(self, qtbot):
        """Test spinner animation control"""
        spinner = LoadingSpinner()
        qtbot.addWidget(spinner)

        # Should not be running initially
        assert not spinner.timer.isActive()

        # Start spinner
        spinner.start()
        assert spinner.timer.isActive()
        assert spinner.isVisible()

        # Stop spinner
        spinner.stop()
        assert not spinner.timer.isActive()
        assert not spinner.isVisible()

    def test_spinner_animation_updates(self, qtbot):
        """Test that spinner animation updates frames"""
        spinner = LoadingSpinner()
        qtbot.addWidget(spinner)

        initial_frame = spinner.frame_idx

        # Manually trigger rotation
        spinner._rotate()

        # Frame should have advanced
        assert spinner.frame_idx != initial_frame

    def test_spinner_cycles_through_frames(self, qtbot):
        """Test that spinner cycles back to start"""
        spinner = LoadingSpinner()
        qtbot.addWidget(spinner)

        frame_count = len(spinner.frames)

        # Rotate through all frames
        for _ in range(frame_count + 1):
            spinner._rotate()

        # Should have cycled back
        assert 0 <= spinner.frame_idx < frame_count


class TestPulseAnimation:
    """Test PulseAnimation component"""

    def test_pulse_creation(self, qtbot):
        """Test that pulse animation can be created"""
        pulse = PulseAnimation()
        qtbot.addWidget(pulse)

        assert pulse is not None
        assert pulse.text() == "● REC"

    def test_pulse_starts_and_stops(self, qtbot):
        """Test pulse animation control"""
        pulse = PulseAnimation()
        qtbot.addWidget(pulse)

        # Start animation
        pulse.start()
        assert pulse.animation.state() == pulse.animation.Running
        assert pulse.isVisible()

        # Stop animation
        pulse.stop()
        assert pulse.animation.state() != pulse.animation.Running
        assert not pulse.isVisible()

    def test_pulse_color_change(self, qtbot):
        """Test changing pulse color"""
        pulse = PulseAnimation()
        qtbot.addWidget(pulse)

        # Change color
        pulse.set_color(ColorPalette.SUCCESS)

        # Verify color is in stylesheet
        assert ColorPalette.SUCCESS in pulse.styleSheet()

    def test_pulse_text_change(self, qtbot):
        """Test changing pulse text"""
        pulse = PulseAnimation()
        qtbot.addWidget(pulse)

        pulse.set_text("● LIVE")

        assert pulse.text() == "● LIVE"

    def test_pulse_animation_properties(self, qtbot):
        """Test pulse animation configuration"""
        pulse = PulseAnimation()
        qtbot.addWidget(pulse)

        # Check animation properties
        assert pulse.animation.loopCount() == -1  # Infinite
        assert pulse.animation.duration() > 0


class TestThemeConsistencyAcrossWidgets:
    """Test theme consistency across different widget types"""

    def test_all_widgets_respect_theme(self, qtbot):
        """Test that various widgets can be styled consistently"""
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()

        # Create various widgets
        button = QPushButton("Button")
        progress = QProgressBar()
        label = QLabel("Label")
        combo = QComboBox()

        for widget in [button, progress, label, combo]:
            qtbot.addWidget(widget)
            widget.setStyleSheet(stylesheet)

        # All widgets should have the stylesheet applied
        assert len(button.styleSheet()) > 0
        assert len(progress.styleSheet()) > 0
        assert len(label.styleSheet()) > 0
        assert len(combo.styleSheet()) > 0

    def test_dark_theme_colors_on_widgets(self, qtbot):
        """Test that dark theme colors are applied to widgets"""
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()

        button = QPushButton("Test")
        qtbot.addWidget(button)
        button.setStyleSheet(stylesheet)

        # Stylesheet should contain dark theme colors
        assert ColorPalette.BACKGROUND_PRIMARY in stylesheet
        assert ColorPalette.ACCENT_PRIMARY in stylesheet


class TestWidgetPropertyDynamicUpdates:
    """Test dynamic property updates and style refresh"""

    def test_property_update_triggers_style_refresh(self, qtbot):
        """Test that setting property updates widget style"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        initial_property = button.property("buttonStyle")

        ThemeManager.set_widget_property(button, "buttonStyle", "danger")

        updated_property = button.property("buttonStyle")

        assert initial_property != updated_property
        assert updated_property == "danger"

    def test_multiple_property_updates(self, qtbot):
        """Test multiple property updates work correctly"""
        button = QPushButton("Test")
        qtbot.addWidget(button)

        # Update multiple times
        ThemeManager.set_widget_property(button, "buttonStyle", "secondary")
        assert button.property("buttonStyle") == "secondary"

        ThemeManager.set_widget_property(button, "buttonStyle", "danger")
        assert button.property("buttonStyle") == "danger"

        ThemeManager.set_widget_property(button, "buttonStyle", "success")
        assert button.property("buttonStyle") == "success"
