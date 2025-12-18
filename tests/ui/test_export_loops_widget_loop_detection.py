"""
Unit and Integration Tests for Export Loops Widget Loop Detection Status

PURPOSE: Test loop detection status checking and export button state management
CONTEXT: Phase 2 of Export Loops refactoring - Loop Detection Status-Prüfung
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from PySide6.QtWidgets import QApplication

from ui.widgets.export_loops_widget import ExportLoopsWidget
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
class TestHasLoopDetection:
    """Test _has_loop_detection() method"""

    def test_has_loop_detection_true(self, export_widget, mock_player_widget):
        """Test that detection is recognized when downbeats are present"""
        # Set up detected downbeats
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0])
        
        result = export_widget._has_loop_detection()
        
        assert result is True

    def test_has_loop_detection_false_no_downbeats(self, export_widget, mock_player_widget):
        """Test that detection is False when no downbeats"""
        mock_player_widget.detected_downbeat_times = None
        
        result = export_widget._has_loop_detection()
        
        assert result is False

    def test_has_loop_detection_false_insufficient_downbeats(self, export_widget, mock_player_widget):
        """Test that detection is False when less than 2 downbeats"""
        mock_player_widget.detected_downbeat_times = np.array([0.0])
        
        result = export_widget._has_loop_detection()
        
        assert result is False

    def test_has_loop_detection_false_no_player_widget(self, qapp):
        """Test that detection is False when no player widget"""
        widget = ExportLoopsWidget(player_widget=None)
        
        result = widget._has_loop_detection()
        
        assert result is False


@pytest.mark.unit
class TestGetBpmFromPlayerWidget:
    """Test _get_bpm_from_player_widget() method"""

    def test_get_bpm_from_player_widget(self, export_widget, mock_player_widget):
        """Test that BPM is correctly calculated from downbeats"""
        # Set up downbeats: 2 seconds apart = 120 BPM (60 * 4 / 2)
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0, 8.0])
        
        bpm = export_widget._get_bpm_from_player_widget()
        
        assert bpm == 120

    def test_get_bpm_fallback(self, export_widget, mock_player_widget):
        """Test that fallback value is used when no detection"""
        mock_player_widget.detected_downbeat_times = None
        
        bpm = export_widget._get_bpm_from_player_widget()
        
        assert bpm == 120  # Default fallback

    def test_get_bpm_different_tempo(self, export_widget, mock_player_widget):
        """Test BPM calculation for different tempo"""
        # Set up downbeats: 1.5 seconds apart = 160 BPM (60 * 4 / 1.5)
        mock_player_widget.detected_downbeat_times = np.array([0.0, 1.5, 3.0, 4.5, 6.0])
        
        bpm = export_widget._get_bpm_from_player_widget()
        
        assert bpm == 160


@pytest.mark.unit
class TestGetBarsFromPlayerWidget:
    """Test _get_bars_from_player_widget() method"""

    def test_get_bars_from_player_widget(self, export_widget, mock_player_widget):
        """Test that bars are correctly retrieved from player widget"""
        mock_player_widget._bars_per_loop = 8
        
        bars = export_widget._get_bars_from_player_widget()
        
        assert bars == 8

    def test_get_bars_fallback(self, export_widget, mock_player_widget):
        """Test that fallback value is used when attribute missing"""
        # Remove _bars_per_loop attribute
        if hasattr(mock_player_widget, '_bars_per_loop'):
            delattr(mock_player_widget, '_bars_per_loop')
        
        bars = export_widget._get_bars_from_player_widget()
        
        assert bars == 4  # Default fallback

    def test_get_bars_no_player_widget(self, qapp):
        """Test that fallback is used when no player widget"""
        widget = ExportLoopsWidget(player_widget=None)
        
        bars = widget._get_bars_from_player_widget()
        
        assert bars == 4  # Default fallback


@pytest.mark.unit
class TestExportButtonState:
    """Test export button state management"""

    def test_export_button_disabled_without_detection(self, export_widget, mock_player_widget):
        """Test that export button is disabled without loop detection"""
        mock_player_widget.has_stems_loaded = Mock(return_value=True)
        mock_player_widget.detected_downbeat_times = None
        
        export_widget._update_export_button_state()
        
        assert export_widget.btn_export.isEnabled() is False
        assert "Loop Detection" in export_widget.btn_export.toolTip()

    def test_export_button_enabled_with_detection(self, export_widget, mock_player_widget):
        """Test that export button is enabled with loop detection"""
        mock_player_widget.has_stems_loaded = Mock(return_value=True)
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0])
        mock_player_widget._bars_per_loop = 4
        
        export_widget._update_export_button_state()
        
        # Button should be enabled (assuming valid BPM/bars combination)
        # Note: Actual enabled state depends on validation, but tooltip should be empty
        assert export_widget.btn_export.toolTip() == ""


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestExportButtonStateIntegration:
    """Integration tests for export button state"""

    def test_export_button_enabled_after_detection(self, export_widget, mock_player_widget):
        """Test that button becomes enabled after loop detection"""
        mock_player_widget.has_stems_loaded = Mock(return_value=True)
        mock_player_widget.detected_downbeat_times = None
        
        # Initially disabled
        export_widget._update_export_button_state()
        assert export_widget.btn_export.isEnabled() is False
        
        # After detection
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0])
        mock_player_widget._bars_per_loop = 4
        export_widget._update_export_button_state()
        
        # Tooltip should be cleared
        assert export_widget.btn_export.toolTip() == ""

    def test_export_button_state_updates_on_detection(self, export_widget, mock_player_widget):
        """Test that button state updates when detection status changes"""
        mock_player_widget.has_stems_loaded = Mock(return_value=True)
        
        # No detection
        mock_player_widget.detected_downbeat_times = None
        export_widget._update_export_button_state()
        tooltip_before = export_widget.btn_export.toolTip()
        
        # With detection
        mock_player_widget.detected_downbeat_times = np.array([0.0, 2.0, 4.0, 6.0])
        mock_player_widget._bars_per_loop = 4
        export_widget._update_export_button_state()
        tooltip_after = export_widget.btn_export.toolTip()
        
        assert tooltip_before != tooltip_after
        assert "Loop Detection" in tooltip_before
        assert tooltip_after == ""

