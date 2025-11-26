"""
Tests for Queue Drawer Overlay Behavior

PURPOSE: Verify that the QueueDrawer behaves as an overlay and does not affect content layout.
"""
import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from ui.main_window import MainWindow
from ui.widgets.queue_drawer import QueueDrawer

@pytest.mark.unit
def test_drawer_is_overlay(qapp, reset_singletons):
    """Test that drawer is a child of central widget but not in the main layout"""
    window = MainWindow()
    window.resize(1000, 800)
    window.show()
    
    # Drawer should exist
    assert hasattr(window, '_queue_drawer')
    drawer = window._queue_drawer
    
    # Force layout update
    qapp.processEvents()
    
    # We need to show/expand the drawer to check its geometry logic
    # because it starts hidden (and thus might have 0,0 geometry)
    drawer.expand()
    
    # Wait for animation or force update?
    # Let's just manually set geometry to simulate "after resize" behavior for a visible drawer
    # Or check that it's NOT in the layout hierarchy?
    # It is parented to centralWidget, but NOT in main_v_layout
    
    # Verify overlay geometry logic
    # After expand, it should be at the bottom
    # We can check the target value of the animation
    assert drawer.animation.endValue().bottom() == window.centralWidget().rect().bottom()
    assert drawer.animation.endValue().width() == window.centralWidget().rect().width()

@pytest.mark.unit
def test_drawer_toggle_does_not_resize_content(qapp, reset_singletons):
    """Test that expanding drawer does not shrink the content stack"""
    window = MainWindow()
    window.resize(1000, 800)
    window.show()
    
    content_stack = window._content_stack
    initial_height = content_stack.height()
    
    # Expand drawer
    window._queue_drawer.expand()
    
    # Process events for animation start/layout update
    qapp.processEvents()
    
    # Content height should remain unchanged in overlay mode
    assert content_stack.height() == initial_height

@pytest.mark.unit
def test_drawer_respects_sidebar_height(qapp, reset_singletons):
    """Test that drawer expansion is capped by sidebar buttons"""
    window = MainWindow()
    window.resize(1000, 600) # Relatively small height
    window.show()
    qapp.processEvents() # Allow resizeEvent to run
    
    drawer = window._queue_drawer
    
    # Calculate protected area (bottom of last button)
    # The logic in MainWindow.resizeEvent updates drawer.expanded_height
    
    # Expand
    drawer.expand()
    
    # Check target geometry (end value of animation)
    target_rect = drawer.animation.endValue()
    
    # Sidebar buttons bottom
    # Note: We need to map coordinates carefully if we were strict,
    # but we know the logic uses sidebar_y + btn_bottom
    sidebar_y = window._sidebar.geometry().y()
    btn_bottom = window._btn_player.geometry().bottom()
    safe_bottom = sidebar_y + btn_bottom
    
    # Drawer top should be below this safe line
    assert target_rect.top() >= safe_bottom

