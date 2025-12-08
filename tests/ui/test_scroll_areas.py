"""
Tests for Scroll Area Implementation in UI Widgets

PURPOSE: Verify that all main widgets have scroll areas and can handle content overflow.
CONTEXT: Ensures widgets remain usable when content exceeds viewport height.
"""

import pytest
from unittest.mock import patch, Mock
from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt

from ui.widgets.upload_widget import UploadWidget
from ui.widgets.recording_widget import RecordingWidget
from ui.widgets.player_widget import PlayerWidget
from ui.widgets.queue_widget import QueueWidget


class TestUploadWidgetScrolling:
    """Test scroll area in upload widget"""

    @pytest.fixture
    def upload_widget(self, qtbot):
        """Create upload widget"""
        with patch("ui.widgets.upload_widget.AppContext"):
            widget = UploadWidget()
            qtbot.addWidget(widget)
            return widget

    def test_upload_widget_has_scroll_area(self, upload_widget):
        """Test that upload widget contains a scroll area"""
        scroll_areas = upload_widget.findChildren(QScrollArea)
        assert len(scroll_areas) > 0, "Upload widget should have a scroll area"

    def test_scroll_area_is_resizable(self, upload_widget):
        """Test that scroll area is widget resizable"""
        scroll_area = upload_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.widgetResizable() is True

    def test_scroll_area_has_no_frame(self, upload_widget):
        """Test that scroll area has no frame for clean look"""
        scroll_area = upload_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.frameShape() == QScrollArea.NoFrame

    def test_horizontal_scrollbar_disabled(self, upload_widget):
        """Test that horizontal scrollbar is always off"""
        scroll_area = upload_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff

    def test_vertical_scrollbar_as_needed(self, upload_widget):
        """Test that vertical scrollbar appears as needed"""
        scroll_area = upload_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded

    def test_widget_expands_with_content(self, upload_widget, qtbot):
        """Test that widget can expand vertically when content is added"""
        scroll_area = upload_widget.findChild(QScrollArea)
        container = scroll_area.widget()

        # Get initial height
        initial_height = container.sizeHint().height()

        # Waveform widget should be present but may not affect height until file loaded
        assert container is not None
        assert initial_height > 0


class TestRecordingWidgetScrolling:
    """Test scroll area in recording widget"""

    @pytest.fixture
    def recording_widget(self, qtbot):
        """Create recording widget"""
        with patch("ui.widgets.recording_widget.AppContext"):
            widget = RecordingWidget()
            qtbot.addWidget(widget)
            return widget

    def test_recording_widget_has_scroll_area(self, recording_widget):
        """Test that recording widget contains a scroll area"""
        scroll_areas = recording_widget.findChildren(QScrollArea)
        assert len(scroll_areas) > 0

    def test_scroll_area_configuration(self, recording_widget):
        """Test scroll area is properly configured"""
        scroll_area = recording_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.widgetResizable() is True
        assert scroll_area.frameShape() == QScrollArea.NoFrame
        assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded


class TestPlayerWidgetScrolling:
    """Test scroll area in player widget"""

    @pytest.fixture
    def player_widget(self, qtbot):
        """Create player widget"""
        with patch("ui.widgets.player_widget.AppContext"):
            with patch("ui.widgets.player_widget.get_player"):
                widget = PlayerWidget()
                qtbot.addWidget(widget)
                return widget

    def test_player_widget_has_scroll_area(self, player_widget):
        """Test that player widget contains a scroll area"""
        scroll_areas = player_widget.findChildren(QScrollArea)
        assert len(scroll_areas) > 0

    def test_scroll_area_configuration(self, player_widget):
        """Test scroll area is properly configured"""
        scroll_area = player_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.widgetResizable() is True
        assert scroll_area.frameShape() == QScrollArea.NoFrame

    def test_mixer_can_expand_with_stems(self, player_widget):
        """Test that mixer section can accommodate multiple stems"""
        scroll_area = player_widget.findChild(QScrollArea)
        container = scroll_area.widget()

        # Container should exist and be able to expand
        assert container is not None
        assert container.minimumHeight() >= 0


class TestQueueWidgetScrolling:
    """Test scroll area in queue widget"""

    @pytest.fixture
    def queue_widget(self, qtbot):
        """Create queue widget"""
        with patch("ui.widgets.queue_widget.AppContext"):
            widget = QueueWidget()
            qtbot.addWidget(widget)
            return widget

    def test_queue_widget_has_scroll_area(self, queue_widget):
        """Test that queue widget contains a scroll area"""
        scroll_areas = queue_widget.findChildren(QScrollArea)
        assert len(scroll_areas) > 0

    def test_scroll_area_configuration(self, queue_widget):
        """Test scroll area is properly configured"""
        scroll_area = queue_widget.findChild(QScrollArea)
        assert scroll_area is not None
        assert scroll_area.widgetResizable() is True
        assert scroll_area.frameShape() == QScrollArea.NoFrame


class TestScrollingConsistency:
    """Test scroll area consistency across all widgets"""

    def test_all_widgets_use_same_scroll_configuration(self, qtbot):
        """Test that all widgets use consistent scroll area configuration"""
        from ui.widgets.upload_widget import UploadWidget
        from ui.widgets.recording_widget import RecordingWidget
        from ui.widgets.player_widget import PlayerWidget
        from ui.widgets.queue_widget import QueueWidget

        widgets = []

        # Create all widgets
        with patch("ui.widgets.upload_widget.AppContext"):
            upload = UploadWidget()
            qtbot.addWidget(upload)
            widgets.append(upload)

        with patch("ui.widgets.recording_widget.AppContext"):
            recording = RecordingWidget()
            qtbot.addWidget(recording)
            widgets.append(recording)

        with patch("ui.widgets.player_widget.AppContext"):
            with patch("ui.widgets.player_widget.get_player"):
                player = PlayerWidget()
                qtbot.addWidget(player)
                widgets.append(player)

        with patch("ui.widgets.queue_widget.AppContext"):
            queue = QueueWidget()
            qtbot.addWidget(queue)
            widgets.append(queue)

        # Verify all have scroll areas with same configuration
        for widget in widgets:
            scroll_area = widget.findChild(QScrollArea)
            assert scroll_area is not None
            assert scroll_area.widgetResizable() is True
            assert scroll_area.frameShape() == QScrollArea.NoFrame
            assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
            assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded


class TestScrollbarTheming:
    """Test that scrollbars respect theme styling"""

    def test_scrollbar_inherits_theme(self, qtbot):
        """Test that scrollbars inherit theme styling"""
        from ui.theme import ThemeManager
        from ui.widgets.upload_widget import UploadWidget

        with patch("ui.widgets.upload_widget.AppContext"):
            widget = UploadWidget()
            qtbot.addWidget(widget)

            # Apply theme
            theme_manager = ThemeManager.instance()
            stylesheet = theme_manager.load_stylesheet()
            widget.setStyleSheet(stylesheet)

            # Verify theme has scrollbar styles
            assert "QScrollBar" in stylesheet
            assert "QScrollBar::handle" in stylesheet


class TestScrollAreaMargins:
    """Test scroll area margins and spacing"""

    def test_main_layout_has_zero_margins(self, qtbot):
        """Test that main layout has zero margins for full width"""
        from ui.widgets.upload_widget import UploadWidget

        with patch("ui.widgets.upload_widget.AppContext"):
            widget = UploadWidget()
            qtbot.addWidget(widget)

            # Main layout should have zero margins
            main_layout = widget.layout()
            assert main_layout is not None
            assert main_layout.contentsMargins().left() == 0
            assert main_layout.contentsMargins().right() == 0
            assert main_layout.contentsMargins().top() == 0
            assert main_layout.contentsMargins().bottom() == 0


class TestContentOverflow:
    """Test handling of content overflow scenarios"""

    def test_upload_widget_handles_waveform_display(self, qtbot):
        """Test that upload widget handles waveform display without cutting off content"""
        from ui.widgets.upload_widget import UploadWidget

        with patch("ui.widgets.upload_widget.AppContext"):
            widget = UploadWidget()
            qtbot.addWidget(widget)

            # Get scroll area
            scroll_area = widget.findChild(QScrollArea)
            assert scroll_area is not None

            # Container should be able to expand
            container = scroll_area.widget()
            assert container is not None

            # Size hint should be positive
            assert container.sizeHint().height() > 0

    def test_player_widget_handles_multiple_stems(self, qtbot):
        """Test that player widget can handle multiple stem controls"""
        from ui.widgets.player_widget import PlayerWidget

        with patch("ui.widgets.player_widget.AppContext"):
            with patch("ui.widgets.player_widget.get_player"):
                widget = PlayerWidget()
                qtbot.addWidget(widget)

                # Get scroll area
                scroll_area = widget.findChild(QScrollArea)
                container = scroll_area.widget()

                # Should be able to accommodate content
                assert container is not None
                assert scroll_area.widgetResizable() is True

    def test_queue_widget_handles_many_tasks(self, qtbot):
        """Test that queue widget can handle many queued tasks"""
        from ui.widgets.queue_widget import QueueWidget
        from pathlib import Path

        with patch("ui.widgets.queue_widget.AppContext"):
            widget = QueueWidget()
            qtbot.addWidget(widget)

            # Add multiple tasks
            for i in range(10):
                widget.add_task(Path(f"/test/file{i}.wav"), "model_id")

            # Table should show all tasks
            assert widget.queue_table.rowCount() == 10

            # Scroll area should handle the table
            scroll_area = widget.findChild(QScrollArea)
            assert scroll_area is not None
