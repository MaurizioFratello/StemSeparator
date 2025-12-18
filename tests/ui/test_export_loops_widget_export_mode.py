"""
Unit and Integration Tests for Export Loops Widget Export Mode Extension

PURPOSE: Test export mode card extension with loop version checkbox
CONTEXT: Phase 3 of Export Loops refactoring - Export Mode Card Erweiterung
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from PySide6.QtWidgets import QApplication

from ui.widgets.export_loops_widget import ExportLoopsWidget, LoopExportSettings
from ui.widgets.player_widget import PlayerWidget


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
    widget.time_stretch_checkbox = Mock()
    widget.time_stretch_checkbox.isChecked = Mock(return_value=False)
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
class TestLoopVersionCheckbox:
    """Test loop version checkbox UI component"""

    def test_loop_version_checkbox_exists(self, export_widget):
        """Test that checkbox exists in UI"""
        assert hasattr(export_widget, 'loop_version_checkbox')
        assert export_widget.loop_version_checkbox is not None

    def test_loop_version_checkbox_disabled_by_default(self, export_widget):
        """Test that checkbox is disabled by default"""
        assert export_widget.loop_version_checkbox.isEnabled() is False

    def test_loop_version_checkbox_enabled_with_stretching(self, export_widget, mock_player_widget):
        """Test that checkbox is enabled when time-stretching is available"""
        # Enable time-stretching
        mock_player_widget.time_stretch_checkbox.isChecked = Mock(return_value=True)
        
        # Create mock manager with completed tasks
        mock_manager = MagicMock()
        mock_manager.is_running = False
        mock_manager.completed_tasks = {'task1': Mock()}
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        export_widget._update_loop_version_checkbox_state()
        
        assert export_widget.loop_version_checkbox.isEnabled() is True

    def test_loop_version_checkbox_tooltip_no_stretching(self, export_widget, mock_player_widget):
        """Test checkbox tooltip when time-stretching not enabled"""
        mock_player_widget.time_stretch_checkbox.isChecked = Mock(return_value=False)
        mock_player_widget.get_stretch_manager = Mock(return_value=None)
        
        export_widget._update_loop_version_checkbox_state()
        
        assert "Time-Stretching im Looping-Tab aktivieren" in export_widget.loop_version_checkbox.toolTip()

    def test_loop_version_checkbox_tooltip_processing(self, export_widget, mock_player_widget):
        """Test checkbox tooltip when processing"""
        mock_player_widget.time_stretch_checkbox.isChecked = Mock(return_value=True)
        
        # Manager is running
        mock_manager = MagicMock()
        mock_manager.is_running = True
        mock_manager.completed_tasks = {}
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        export_widget._update_loop_version_checkbox_state()
        
        assert "verarbeitet" in export_widget.loop_version_checkbox.toolTip()


@pytest.mark.unit
class TestGetSettingsLoopVersion:
    """Test get_settings() with loop_version field"""

    def test_get_settings_loop_version_original(self, export_widget):
        """Test that settings contain 'original' when checkbox unchecked"""
        export_widget.loop_version_checkbox.setChecked(False)
        
        settings = export_widget.get_settings()
        
        assert settings.loop_version == "original"
        assert isinstance(settings, LoopExportSettings)
        assert hasattr(settings, 'loop_version')

    def test_get_settings_loop_version_stretched(self, export_widget):
        """Test that settings contain 'stretched' when checkbox checked"""
        export_widget.loop_version_checkbox.setChecked(True)
        
        settings = export_widget.get_settings()
        
        assert settings.loop_version == "stretched"

    def test_get_settings_all_fields_present(self, export_widget, mock_player_widget):
        """Test that all required fields are present in settings"""
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0])
        
        settings = export_widget.get_settings()
        
        assert hasattr(settings, 'bpm')
        assert hasattr(settings, 'bars')
        assert hasattr(settings, 'sample_rate')
        assert hasattr(settings, 'bit_depth')
        assert hasattr(settings, 'channels')
        assert hasattr(settings, 'file_format')
        assert hasattr(settings, 'export_mode')
        assert hasattr(settings, 'loop_version')


@pytest.mark.unit
class TestCheckboxStateManagement:
    """Test checkbox state management methods"""

    def test_has_time_stretching_enabled_true(self, export_widget, mock_player_widget):
        """Test that time-stretching enabled is detected correctly"""
        mock_player_widget.time_stretch_checkbox.isChecked = Mock(return_value=True)
        
        result = export_widget._has_time_stretching_enabled()
        
        assert result is True

    def test_has_time_stretching_enabled_false(self, export_widget, mock_player_widget):
        """Test that time-stretching disabled is detected correctly"""
        mock_player_widget.time_stretch_checkbox.isChecked = Mock(return_value=False)
        
        result = export_widget._has_time_stretching_enabled()
        
        assert result is False

    def test_has_stretched_loops_ready_true(self, export_widget, mock_player_widget):
        """Test that ready loops are detected correctly"""
        mock_manager = MagicMock()
        mock_manager.is_running = False
        mock_manager.completed_tasks = {'task1': Mock(), 'task2': Mock()}
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        result = export_widget._has_stretched_loops_ready()
        
        assert result is True

    def test_has_stretched_loops_ready_false_processing(self, export_widget, mock_player_widget):
        """Test that processing loops are not considered ready"""
        mock_manager = MagicMock()
        mock_manager.is_running = True
        mock_manager.completed_tasks = {}
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        result = export_widget._has_stretched_loops_ready()
        
        assert result is False

    def test_has_stretched_loops_ready_false_no_manager(self, export_widget, mock_player_widget):
        """Test that no manager returns False"""
        mock_player_widget.get_stretch_manager = Mock(return_value=None)
        
        result = export_widget._has_stretched_loops_ready()
        
        assert result is False


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestExportModeWorkflow:
    """Integration tests for export mode workflow"""

    def test_export_mode_workflow(self, export_widget, mock_player_widget):
        """Test complete export mode workflow"""
        # Set up player widget with detection
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0])
        mock_player_widget._bars_per_loop = 4
        mock_player_widget.has_stems_loaded = Mock(return_value=True)
        
        # Get settings with original loops
        export_widget.loop_version_checkbox.setChecked(False)
        settings1 = export_widget.get_settings()
        assert settings1.loop_version == "original"
        
        # Get settings with stretched loops
        export_widget.loop_version_checkbox.setChecked(True)
        settings2 = export_widget.get_settings()
        assert settings2.loop_version == "stretched"
        
        # Verify other settings remain the same
        assert settings1.export_mode == settings2.export_mode
        assert settings1.sample_rate == settings2.sample_rate

    def test_loop_version_checkbox_updates_on_stretching(self, export_widget, mock_player_widget):
        """Test that checkbox updates when stretching status changes"""
        # Initially disabled
        export_widget._update_loop_version_checkbox_state()
        assert export_widget.loop_version_checkbox.isEnabled() is False
        
        # Enable time-stretching
        mock_player_widget.time_stretch_checkbox.isChecked = Mock(return_value=True)
        mock_manager = MagicMock()
        mock_manager.is_running = False
        mock_manager.completed_tasks = {'task1': Mock()}
        mock_player_widget.get_stretch_manager = Mock(return_value=mock_manager)
        
        export_widget._update_loop_version_checkbox_state()
        
        assert export_widget.loop_version_checkbox.isEnabled() is True

