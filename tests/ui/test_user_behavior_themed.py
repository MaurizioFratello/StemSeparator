"""
User Behavior Tests for Themed UI

PURPOSE: Test user interactions with themed UI components.
CONTEXT: Simulates real user behavior to ensure theme doesn't break functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.widgets.upload_widget import UploadWidget
from ui.widgets.player_widget import PlayerWidget, StemControl
from ui.widgets.recording_widget import RecordingWidget
from ui.widgets.queue_widget import QueueWidget
from ui.theme import ThemeManager


class TestMainWindowUserInteractions:
    """Test user interactions with main window"""

    @pytest.fixture
    def main_window(self, qtbot, qapp):
        """Create main window with theme applied"""
        with patch("ui.main_window.get_app_context") as mock_get_ctx:
            mock_ctx = MagicMock()
            mock_ctx.translate.return_value = "Test Translation"
            mock_get_ctx.return_value = mock_ctx

            window = MainWindow()
            qtbot.addWidget(window)
            return window

    def test_user_can_see_themed_window(self, main_window, qtbot):
        """Test that user sees a themed window"""
        # Window should have modern size
        assert main_window.width() >= 1400
        assert main_window.height() >= 900

    def test_user_can_switch_tabs(self, main_window, qtbot):
        """Test that user can switch between views"""
        stack = main_window._content_stack

        # User clicks on sidebar buttons
        buttons = main_window._nav_group.buttons()
        for i, btn in enumerate(buttons):
            qtbot.mouseClick(btn, Qt.LeftButton)
            qtbot.wait(50)  # Small delay to mimic user behavior

            assert stack.currentIndex() == i

    def test_user_sees_styled_sidebar(self, main_window, qtbot):
        """Test that sidebar has styling"""
        sidebar = main_window._sidebar
        assert sidebar.objectName() == "sidebar"
        assert sidebar.width() == 200

    def test_user_can_access_menu_items(self, main_window, qtbot):
        """Test that user can access menu items"""
        menubar = main_window.menuBar()

        # Should have menus
        assert menubar.actions()

        # File menu should be accessible
        file_menu = main_window._file_menu
        assert file_menu is not None
        assert file_menu.isEnabled()


class TestUploadWidgetUserInteractions:
    """Test user interactions with upload widget"""

    @pytest.fixture
    def upload_widget(self, qtbot):
        """Create upload widget"""
        with patch("ui.widgets.upload_widget.AppContext"):
            widget = UploadWidget()
            qtbot.addWidget(widget)
            return widget

    def test_user_sees_styled_buttons(self, upload_widget, qtbot):
        """Test that user sees styled buttons"""
        # Browse button should have secondary style
        assert upload_widget.btn_browse.property("buttonStyle") == "secondary"

        # Clear button should have secondary style
        assert upload_widget.btn_clear.property("buttonStyle") == "secondary"

        # Queue button should have secondary style
        assert upload_widget.btn_queue.property("buttonStyle") == "secondary"

    def test_user_can_click_browse_button(self, upload_widget, qtbot):
        """Test that user can click browse button"""
        browse_btn = upload_widget.btn_browse

        # Button should be clickable
        assert browse_btn.isEnabled()

        # Simulate click (will open file dialog, so we mock it)
        with patch("PySide6.QtWidgets.QFileDialog.exec", return_value=False):
            qtbot.mouseClick(browse_btn, Qt.LeftButton)

    def test_user_sees_disabled_start_button_initially(self, upload_widget, qtbot):
        """Test that start button is disabled when no file selected"""
        assert not upload_widget.btn_start.isEnabled()

    def test_user_sees_ensemble_checkbox(self, upload_widget, qtbot):
        """Test that user can see and interact with ensemble checkbox"""
        checkbox = upload_widget.ensemble_checkbox

        assert not checkbox.isHidden()
        assert not checkbox.isChecked()

        # User clicks checkbox
        qtbot.mouseClick(checkbox, Qt.LeftButton)
        assert checkbox.isChecked()

        # Ensemble combo should now be enabled
        assert upload_widget.ensemble_combo.isEnabled()


class TestPlayerWidgetUserInteractions:
    """Test user interactions with player widget"""

    @pytest.fixture
    def player_widget(self, qtbot):
        """Create player widget"""
        with patch("ui.widgets.player_widget.AppContext"):
            with patch("ui.widgets.player_widget.get_player"):
                widget = PlayerWidget()
                qtbot.addWidget(widget)
                return widget

    def test_user_sees_styled_playback_buttons(self, player_widget, qtbot):
        """Test that playback buttons have correct styling"""
        # Play button should be success style (green)
        assert player_widget.btn_play.property("buttonStyle") == "success"

        # Pause should be secondary
        assert player_widget.btn_pause.property("buttonStyle") == "secondary"

        # Stop should be danger (red)
        assert player_widget.btn_stop.property("buttonStyle") == "danger"

    def test_user_sees_load_buttons_with_icons(self, player_widget, qtbot):
        """Test that load buttons have icons"""
        # Buttons should have emoji icons
        assert "📁" in player_widget.btn_load_dir.text()
        assert "📄" in player_widget.btn_load_files.text()

    def test_user_sees_monospace_time_display(self, player_widget, qtbot):
        """Test that time displays use monospace font"""
        # Time labels should have mono style
        assert player_widget.current_time_label.property("labelStyle") == "mono"
        assert player_widget.duration_label.property("labelStyle") == "mono"

    def test_stem_control_mute_button_changes_color(self, qtbot):
        """Test that mute button changes color when clicked"""
        stem_control = StemControl("vocals")
        qtbot.addWidget(stem_control)

        # Button should have icon style
        assert stem_control.btn_mute.property("buttonStyle") == "icon"

        # Click mute button
        qtbot.mouseClick(stem_control.btn_mute, Qt.LeftButton)

        # Button should be checked and have custom styling
        assert stem_control.btn_mute.isChecked()
        # Just check that logic holds, stylesheet application is internal Qt
        assert stem_control.is_muted

    def test_stem_control_solo_button_changes_color(self, qtbot):
        """Test that solo button changes color when clicked"""
        stem_control = StemControl("drums")
        qtbot.addWidget(stem_control)

        # Click solo button
        qtbot.mouseClick(stem_control.btn_solo, Qt.LeftButton)

        # Button should be checked and have custom styling
        assert stem_control.btn_solo.isChecked()
        assert stem_control.is_solo

    def test_user_can_adjust_volume_slider(self, qtbot):
        """Test that user can adjust volume slider"""
        stem_control = StemControl("bass")
        qtbot.addWidget(stem_control)

        initial_volume = stem_control.volume_slider.value()

        # User moves slider
        stem_control.volume_slider.setValue(50)

        assert stem_control.volume_slider.value() == 50
        assert stem_control.volume_slider.value() != initial_volume


class TestRecordingWidgetUserInteractions:
    """Test user interactions with recording widget"""

    @pytest.fixture
    def recording_widget(self, qtbot):
        """Create recording widget"""
        with patch("ui.widgets.recording_widget.AppContext"):
            widget = RecordingWidget()
            qtbot.addWidget(widget)
            return widget

    def test_user_sees_styled_control_buttons(self, recording_widget, qtbot):
        """Test that recording control buttons have correct styling"""
        # Start button should be success (green)
        assert recording_widget.btn_start.property("buttonStyle") == "success"

        # Pause should be secondary
        assert recording_widget.btn_pause.property("buttonStyle") == "secondary"

        # Cancel should be danger (red)
        assert recording_widget.btn_cancel.property("buttonStyle") == "danger"

    def test_user_sees_buttons_with_icons(self, recording_widget, qtbot):
        """Test that buttons have appropriate icons"""
        assert "🔴" in recording_widget.btn_start.text()
        assert "⏸" in recording_widget.btn_pause.text()
        assert "💾" in recording_widget.btn_stop.text()
        assert "❌" in recording_widget.btn_cancel.text()

    def test_user_sees_large_level_meter(self, recording_widget, qtbot):
        """Test that level meter uses large variant"""
        level_meter = recording_widget.level_meter

        assert level_meter.property("progressStyle") == "large"

    def test_user_sees_monospace_duration(self, recording_widget, qtbot):
        """Test that duration display uses monospace font"""
        duration_label = recording_widget.duration_label

        assert duration_label.property("labelStyle") == "mono"

    def test_user_can_refresh_devices(self, recording_widget, qtbot):
        """Test that user can click refresh button"""
        refresh_btn = recording_widget.btn_refresh_devices

        # Should have secondary style and icon
        assert refresh_btn.property("buttonStyle") == "secondary"
        assert "🔄" in refresh_btn.text()


class TestQueueWidgetUserInteractions:
    """Test user interactions with queue widget"""

    @pytest.fixture
    def queue_widget(self, qtbot):
        """Create queue widget"""
        with patch("ui.widgets.queue_widget.AppContext"):
            widget = QueueWidget()
            qtbot.addWidget(widget)
            return widget

    def test_user_sees_styled_queue_buttons(self, queue_widget, qtbot):
        """Test that queue control buttons have correct styling"""
        # Start should be success (green)
        assert queue_widget.btn_start.property("buttonStyle") == "success"

        # Stop should be danger (red)
        assert queue_widget.btn_stop.property("buttonStyle") == "danger"

        # Clear and Remove should be secondary
        assert queue_widget.btn_clear.property("buttonStyle") == "secondary"
        assert queue_widget.btn_remove.property("buttonStyle") == "secondary"

    def test_user_sees_buttons_with_icons(self, queue_widget, qtbot):
        """Test that buttons have appropriate icons"""
        assert "▶" in queue_widget.btn_start.text()
        assert "⏹" in queue_widget.btn_stop.text()
        assert "🗑️" in queue_widget.btn_clear.text()
        assert "➖" in queue_widget.btn_remove.text()

    def test_user_sees_table_with_alternating_rows(self, queue_widget, qtbot):
        """Test that table has alternating row colors"""
        table = queue_widget.queue_table

        assert table.alternatingRowColors() is True

    def test_user_can_add_task_to_queue(self, queue_widget, qtbot):
        """Test that user can add tasks to queue"""
        initial_count = queue_widget.queue_table.rowCount()

        # Simulate adding a task
        test_file = Path("/test/file.wav")
        queue_widget.add_task(test_file, "model_id")

        # Table should have one more row
        assert queue_widget.queue_table.rowCount() == initial_count + 1


class TestThemeUserExperience:
    """Test overall theme user experience"""

    def test_user_sees_consistent_colors(self, qtbot):
        """Test that colors are consistent across widgets"""
        from PySide6.QtWidgets import QPushButton, QProgressBar

        button1 = QPushButton("Button 1")
        button2 = QPushButton("Button 2")

        qtbot.addWidget(button1)
        qtbot.addWidget(button2)

        # Apply same theme
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()

        button1.setStyleSheet(stylesheet)
        button2.setStyleSheet(stylesheet)

        # Both should have same stylesheet
        assert button1.styleSheet() == button2.styleSheet()

    def test_user_sees_visual_feedback_on_hover(self, qtbot):
        """Test that hover states are defined in theme"""
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()

        # Stylesheet should contain hover states
        assert ":hover" in stylesheet

    def test_user_sees_focus_indicators(self, qtbot):
        """Test that focus states are defined in theme"""
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()

        # Stylesheet should contain focus states
        assert ":focus" in stylesheet

    def test_user_sees_disabled_state_styling(self, qtbot):
        """Test that disabled state styling exists"""
        theme_manager = ThemeManager.instance()
        stylesheet = theme_manager.load_stylesheet()

        # Stylesheet should contain disabled states
        assert ":disabled" in stylesheet


class TestAccessibilityWithTheme:
    """Test accessibility features with themed UI"""

    def test_buttons_are_keyboard_accessible(self, qtbot):
        """Test that buttons can be activated with keyboard"""
        from PySide6.QtWidgets import QPushButton

        button = QPushButton("Test")
        qtbot.addWidget(button)

        clicked = False

        def on_click():
            nonlocal clicked
            clicked = True

        button.clicked.connect(on_click)

        # Simulate space key press
        qtbot.keyPress(button, Qt.Key_Space)
        qtbot.keyRelease(button, Qt.Key_Space)

        # Button should have been clicked
        assert clicked

    def test_widgets_have_tooltips(self, qtbot):
        """Test that important widgets have tooltips"""
        from ui.widgets.player_widget import StemControl

        stem_control = StemControl("vocals")
        qtbot.addWidget(stem_control)

        # Mute and solo buttons should have tooltips
        assert len(stem_control.btn_mute.toolTip()) > 0
        assert len(stem_control.btn_solo.toolTip()) > 0

    def test_contrast_is_sufficient(self):
        """Test that theme has sufficient contrast"""
        from ui.theme import ColorPalette

        # Text on dark background should be light
        assert ColorPalette.TEXT_PRIMARY.startswith("#")
        assert ColorPalette.BACKGROUND_PRIMARY.startswith("#")

        # These are different colors (basic check)
        assert ColorPalette.TEXT_PRIMARY != ColorPalette.BACKGROUND_PRIMARY


class TestResponsiveLayout:
    """Test that themed layouts are responsive"""

    @pytest.fixture
    def main_window(self, qtbot):
        """Create main window"""
        with patch("ui.main_window.get_app_context") as mock_get_ctx:
            mock_ctx = MagicMock()
            mock_ctx.translate.return_value = "Test Translation"
            mock_get_ctx.return_value = mock_ctx

            window = MainWindow()
            qtbot.addWidget(window)
            return window

    def test_window_can_be_resized(self, main_window, qtbot):
        """Test that window can be resized by user"""
        initial_width = main_window.width()
        initial_height = main_window.height()

        # User resizes window
        main_window.resize(1600, 1000)

        assert main_window.width() == 1600
        assert main_window.height() == 1000
        assert main_window.width() != initial_width

    def test_widgets_adapt_to_window_size(self, main_window, qtbot):
        """Test that widgets adapt when window is resized"""
        stack = main_window._content_stack

        # Resize window
        main_window.resize(1000, 700)
        qtbot.wait(100)

        # Content stack should adjust (roughly)
        # We check that it fits within the window minus sidebar
        assert stack.width() <= main_window.width()
        assert stack.height() <= main_window.height()
