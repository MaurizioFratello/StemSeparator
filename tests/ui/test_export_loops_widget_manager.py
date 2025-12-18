"""
Unit and Integration Tests for Export Loops Widget Manager Migration

PURPOSE: Test Background Stretch Manager migration from Export Widget to Player Widget
CONTEXT: Phase 1 of Export Loops refactoring - Manager centralization
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject

from ui.widgets.export_loops_widget import ExportLoopsWidget
from ui.widgets.player_widget import PlayerWidget
from core.background_stretch_manager import BackgroundStretchManager


@pytest.fixture
def qapp():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_player_widget(qapp):
    """Create mock player widget"""
    widget = Mock(spec=PlayerWidget)
    widget.stem_files = {}
    widget.has_stems_loaded = Mock(return_value=False)
    widget.detected_downbeat_times = None
    widget._bars_per_loop = 4
    widget.player = Mock()
    widget.player.get_duration = Mock(return_value=10.0)
    widget.ctx = Mock()
    widget.ctx.logger = Mock(return_value=Mock())
    return widget


@pytest.fixture
def export_widget(qapp, mock_player_widget):
    """Create export loops widget with mock player widget"""
    widget = ExportLoopsWidget(player_widget=mock_player_widget)
    return widget


# ============================================================================
# Unit Tests
# ============================================================================

@pytest.mark.unit
class TestGetStretchManagerFromPlayerWidget:
    """Test getting stretch manager from player widget"""

    def test_get_stretch_manager_from_player_widget(self, export_widget, mock_player_widget):
        """Test that manager is correctly retrieved from player widget"""
        # Create mock manager
        mock_manager = MagicMock(spec=BackgroundStretchManager)
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        # Get manager via export widget
        manager = export_widget._get_stretch_manager()
        
        # Verify manager is returned
        assert manager is mock_manager
        mock_player_widget.get_stretch_manager.assert_called_once()

    def test_stretch_manager_none_when_no_player_widget(self, qapp):
        """Test that None is returned when no player widget is set"""
        widget = ExportLoopsWidget(player_widget=None)
        
        manager = widget._get_stretch_manager()
        
        assert manager is None

    def test_stretch_manager_none_when_player_widget_returns_none(self, export_widget, mock_player_widget):
        """Test that None is returned when player widget returns None"""
        mock_player_widget.get_stretch_manager = Mock(return_value=None)
        
        manager = export_widget._get_stretch_manager()
        
        assert manager is None

    def test_stretch_manager_signals_connected(self, export_widget, mock_player_widget):
        """Test that signals are connected when manager is available"""
        # Create mock manager with signals
        mock_manager = MagicMock(spec=BackgroundStretchManager)
        mock_manager.progress_updated = Mock(spec=QObject)
        mock_manager.all_completed = Mock(spec=QObject)
        mock_manager.task_completed = Mock(spec=QObject)
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        # Connect signals
        export_widget._connect_stretch_manager_signals()
        
        # Verify signals are connected
        assert mock_manager.progress_updated.connect.called
        assert mock_manager.all_completed.connect.called
        assert mock_manager.task_completed.connect.called


@pytest.mark.unit
class TestPlayerWidgetGetStretchManager:
    """Test PlayerWidget.get_stretch_manager() method"""

    @patch('core.background_stretch_manager.BackgroundStretchManager')
    @patch('core.background_stretch_manager.get_optimal_worker_count')
    def test_get_stretch_manager_lazy_initialization(self, mock_get_workers, mock_manager_class, qapp):
        """Test that manager is lazily initialized on first access"""
        mock_get_workers.return_value = 4
        mock_manager = MagicMock(spec=BackgroundStretchManager)
        mock_manager.progress_updated = Mock(spec=QObject)
        mock_manager.all_completed = Mock(spec=QObject)
        mock_manager_class.return_value = mock_manager
        
        widget = PlayerWidget()
        widget.ctx = Mock()
        widget.ctx.logger = Mock(return_value=Mock())
        
        # First access should create manager
        manager1 = widget.get_stretch_manager()
        
        assert manager1 is mock_manager
        mock_manager_class.assert_called_once_with(max_workers=4)
        
        # Second access should return same instance
        manager2 = widget.get_stretch_manager()
        
        assert manager2 is manager1
        assert mock_manager_class.call_count == 1  # Not called again

    @patch('core.background_stretch_manager.BackgroundStretchManager')
    @patch('core.background_stretch_manager.get_optimal_worker_count')
    def test_get_stretch_manager_signals_connected(self, mock_get_workers, mock_manager_class, qapp):
        """Test that signals are connected when manager is created"""
        mock_get_workers.return_value = 4
        mock_manager = MagicMock(spec=BackgroundStretchManager)
        mock_manager.progress_updated = Mock(spec=QObject)
        mock_manager.all_completed = Mock(spec=QObject)
        mock_manager_class.return_value = mock_manager
        
        widget = PlayerWidget()
        widget.ctx = Mock()
        widget.ctx.logger = Mock(return_value=Mock())
        
        widget.get_stretch_manager()
        
        # Verify signals are connected
        assert mock_manager.progress_updated.connect.called
        assert mock_manager.all_completed.connect.called


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestManagerSharingBetweenWidgets:
    """Test manager sharing between player and export widgets"""

    @patch('core.background_stretch_manager.BackgroundStretchManager')
    @patch('core.background_stretch_manager.get_optimal_worker_count')
    def test_manager_shared_between_widgets(self, mock_get_workers, mock_manager_class, qapp):
        """Test that manager is shared between widgets"""
        mock_get_workers.return_value = 4
        mock_manager = MagicMock(spec=BackgroundStretchManager)
        mock_manager.progress_updated = Mock(spec=QObject)
        mock_manager.all_completed = Mock(spec=QObject)
        mock_manager_class.return_value = mock_manager
        
        # Create player widget
        player_widget = PlayerWidget()
        player_widget.ctx = Mock()
        player_widget.ctx.logger = Mock(return_value=Mock())
        
        # Create export widget with player widget
        export_widget = ExportLoopsWidget(player_widget=player_widget)
        
        # Get manager from both widgets
        manager1 = player_widget.get_stretch_manager()
        manager2 = export_widget._get_stretch_manager()
        
        # Verify same instance is returned
        assert manager1 is manager2
        assert manager1 is mock_manager

    @patch('core.background_stretch_manager.BackgroundStretchManager')
    @patch('core.background_stretch_manager.get_optimal_worker_count')
    def test_stretch_processing_from_player_widget(self, mock_get_workers, mock_manager_class, qapp):
        """Test that stretching processing works from player widget"""
        mock_get_workers.return_value = 4
        mock_manager = MagicMock(spec=BackgroundStretchManager)
        mock_manager.progress_updated = Mock(spec=QObject)
        mock_manager.all_completed = Mock(spec=QObject)
        mock_manager.start_batch = Mock()
        mock_manager.is_running = False
        mock_manager.completed_tasks = {}
        mock_manager_class.return_value = mock_manager
        
        # Create player widget
        player_widget = PlayerWidget()
        player_widget.ctx = Mock()
        player_widget.ctx.logger = Mock(return_value=Mock())
        player_widget.stem_files = {'drums': Mock()}
        player_widget.detected_loop_segments = [(0.0, 2.0)]
        player_widget.detected_bpm = 120.0
        player_widget.time_stretch_target_bpm = 140
        player_widget.stretch_progress_bar = Mock()
        player_widget.btn_start_stretch_processing = Mock()
        player_widget.loop_playback_info_label = Mock()
        
        # Start processing
        player_widget._on_start_stretch_processing_clicked()
        
        # Verify batch was started
        assert mock_manager.start_batch.called

