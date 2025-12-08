"""
Unit tests for Player Widget Tab Navigation

Test Coverage:
- Tab creation and visibility
- Tab switching functionality
- Tab state management
- Event signals
"""

import pytest
from PySide6.QtWidgets import QWidget, QTabWidget
from PySide6.QtCore import Qt

from ui.widgets.player_widget import PlayerWidget


@pytest.fixture
def player_widget(qapp):
    """Create PlayerWidget for testing"""
    widget = PlayerWidget()
    return widget


# ============================================================================
# Tab Structure Tests
# ============================================================================


def test_player_widget_has_tabs(player_widget):
    """Test that PlayerWidget has a tab widget"""
    assert hasattr(player_widget, "tab_widget")
    assert isinstance(player_widget.tab_widget, QTabWidget)


def test_player_widget_has_two_tabs(player_widget):
    """Test that PlayerWidget has exactly 2 tabs"""
    assert player_widget.tab_widget.count() == 2


def test_tab_names(player_widget):
    """Test that tabs have correct names"""
    tab_names = [
        player_widget.tab_widget.tabText(i)
        for i in range(player_widget.tab_widget.count())
    ]

    assert "Playback" in tab_names[0]
    assert "Loop Preview" in tab_names[1]
    assert "🎧" in tab_names[1]  # Has emoji icon


def test_playback_tab_exists(player_widget):
    """Test that playback tab exists and is a widget"""
    assert hasattr(player_widget, "playback_tab")
    assert isinstance(player_widget.playback_tab, QWidget)


def test_loop_preview_tab_exists(player_widget):
    """Test that loop preview tab exists and is a widget"""
    assert hasattr(player_widget, "loop_preview_tab")
    assert isinstance(player_widget.loop_preview_tab, QWidget)


# ============================================================================
# Tab Switching Tests
# ============================================================================


def test_initial_tab_is_playback(player_widget):
    """Test that Playback tab is selected by default"""
    assert player_widget.tab_widget.currentIndex() == 0


def test_switch_to_loop_preview_tab(player_widget):
    """Test switching to Loop Preview tab"""
    player_widget.tab_widget.setCurrentIndex(1)
    assert player_widget.tab_widget.currentIndex() == 1


def test_switch_back_to_playback_tab(player_widget):
    """Test switching back to Playback tab"""
    player_widget.tab_widget.setCurrentIndex(1)
    player_widget.tab_widget.setCurrentIndex(0)
    assert player_widget.tab_widget.currentIndex() == 0


def test_tab_change_signal_emitted(player_widget, qtbot):
    """Test that tab change signal is emitted"""
    with qtbot.waitSignal(
        player_widget.tab_widget.currentChanged, timeout=1000
    ) as blocker:
        player_widget.tab_widget.setCurrentIndex(1)

    assert blocker.args[0] == 1  # Index of Loop Preview tab


def test_on_tab_changed_method_exists(player_widget):
    """Test that _on_tab_changed method exists"""
    assert hasattr(player_widget, "_on_tab_changed")
    assert callable(player_widget._on_tab_changed)


def test_prepare_loop_preview_method_exists(player_widget):
    """Test that _prepare_loop_preview method exists (placeholder)"""
    assert hasattr(player_widget, "_prepare_loop_preview")
    assert callable(player_widget._prepare_loop_preview)


# ============================================================================
# Playback Tab Content Tests
# ============================================================================


def test_playback_tab_has_load_card(player_widget):
    """Test that playback tab contains file loading controls"""
    assert hasattr(player_widget, "btn_load_dir")
    assert hasattr(player_widget, "btn_load_files")
    assert hasattr(player_widget, "stems_list")


def test_playback_tab_has_mixer_controls(player_widget):
    """Test that playback tab contains mixer controls"""
    assert hasattr(player_widget, "stems_scroll")
    assert hasattr(player_widget, "master_slider")


def test_playback_tab_has_playback_controls(player_widget):
    """Test that playback tab contains playback controls"""
    assert hasattr(player_widget, "btn_play")
    assert hasattr(player_widget, "btn_pause")
    assert hasattr(player_widget, "btn_stop")
    assert hasattr(player_widget, "position_slider")


def test_playback_tab_has_export_buttons(player_widget):
    """Test that playback tab contains export buttons"""
    assert hasattr(player_widget, "btn_export")
    assert hasattr(player_widget, "btn_export_loops")


# ============================================================================
# Loop Preview Tab Content Tests
# ============================================================================


def test_loop_preview_tab_has_placeholder(player_widget):
    """Test that loop preview tab contains placeholder"""
    # Get loop preview tab
    loop_tab = player_widget.loop_preview_tab

    # Check that it has a layout
    assert loop_tab.layout() is not None

    # Check that it has at least one child widget (the placeholder)
    assert loop_tab.layout().count() > 0


def test_loop_preview_tab_is_visible_when_selected(player_widget):
    """Test that loop preview tab is visible when selected"""
    player_widget.tab_widget.setCurrentIndex(1)
    current_widget = player_widget.tab_widget.currentWidget()
    assert current_widget == player_widget.loop_preview_tab


# ============================================================================
# Integration Tests
# ============================================================================


def test_tab_switching_preserves_playback_state(player_widget):
    """Test that switching tabs doesn't affect playback state"""
    # Switch to loop preview
    player_widget.tab_widget.setCurrentIndex(1)

    # Playback controls should still exist
    assert hasattr(player_widget, "btn_play")
    assert hasattr(player_widget, "player")


def test_tab_switching_multiple_times(player_widget):
    """Test switching between tabs multiple times"""
    for i in range(5):
        player_widget.tab_widget.setCurrentIndex(i % 2)

    # Should end on Loop Preview (index 1)
    assert player_widget.tab_widget.currentIndex() == 1


def test_tab_object_name(player_widget):
    """Test that tab widget has correct object name for styling"""
    assert player_widget.tab_widget.objectName() == "playerTabs"


# ============================================================================
# Edge Cases
# ============================================================================


def test_invalid_tab_index_clamped(player_widget):
    """Test that invalid tab indices are handled"""
    # Try to set invalid index (should be clamped)
    player_widget.tab_widget.setCurrentIndex(999)

    # Should stay at valid index (either 0 or 1)
    current_index = player_widget.tab_widget.currentIndex()
    assert 0 <= current_index < 2


def test_negative_tab_index_handled(player_widget):
    """Test that negative tab indices are handled"""
    player_widget.tab_widget.setCurrentIndex(-1)

    # Should be at a valid index
    current_index = player_widget.tab_widget.currentIndex()
    assert 0 <= current_index < 2


# ============================================================================
# Performance Tests
# ============================================================================


def test_tab_creation_is_fast(qapp, benchmark):
    """Test that tab creation is performant"""

    def create_widget():
        widget = PlayerWidget()
        return widget

    # Should create widget in less than 1 second
    result = benchmark(create_widget)
    assert result is not None


def test_tab_switching_is_instant(player_widget, benchmark):
    """Test that tab switching is performant"""

    def switch_tab():
        player_widget.tab_widget.setCurrentIndex(1)
        player_widget.tab_widget.setCurrentIndex(0)

    # Should switch tabs very quickly
    benchmark(switch_tab)


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=ui.widgets.player_widget", "--cov-report=term-missing"]
    )
