"""
Queue Drawer Widget - Collapsible persistent container for the QueueWidget.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Slot, Signal, QRect
from PySide6.QtGui import QColor

from ui.widgets.queue_widget import QueueWidget
from ui.theme import ThemeManager


class QueueDrawer(QWidget):
    """
    A collapsible bottom drawer that houses the global QueueWidget.
    
    Features:
    - Persistent overlay across tabs
    - Auto-hide when empty/inactive (optional mode)
    - Smooth expand/collapse animation (modifies geometry)
    - Header summary ("Processing... 45%")
    """
    
    # Signal to notify when drawer state changes (expanded/collapsed)
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.is_expanded = False
        self.expanded_height = 300  # Default, will be overridden by parent resize
        self.collapsed_height = 65  # Increased height for better visibility
        
        self._setup_ui()
        self._connect_signals()
        
        # Initialize state
        self.setVisible(False) # Start hidden (until tasks are added)

        # Animation setup - targets geometry (QRect)
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def _setup_ui(self):
        """Configure layout and components."""
        # Main layout with no margins to fit tight against bottom
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Styling for the container
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Add shadow for depth perception since it is an overlay
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, -2)
        self.setGraphicsEffect(shadow)
        
        # --- 1. Header Bar (Always visible when drawer is 'shown') ---
        self.header = QFrame()
        self.header.setObjectName("drawer_header")
        self.header.setFixedHeight(self.collapsed_height)
        self.header.setStyleSheet("""
            QFrame#drawer_header {
                background-color: #2d2d2d;
                border-top: 1px solid #3d3d3d;
                padding: 0px;
            }
        """)
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 5, 15, 5)  # Add vertical padding to center content
        header_layout.setSpacing(10)
        
        # Toggle Button (Chevron)
        self.btn_toggle = QPushButton("▲")
        self.btn_toggle.setFixedSize(24, 24)
        self.btn_toggle.setFlat(True)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setStyleSheet("font-weight: bold; color: #888;")
        
        # Status Label (Summary)
        self.lbl_status = QLabel("Queue Idle")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #ccc;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        
        # Close/Hide Button
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setFlat(True)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Hide Queue Drawer")
        self.btn_close.setStyleSheet("font-weight: bold; color: #888;")
        
        header_layout.addWidget(self.btn_toggle)
        header_layout.addWidget(self.lbl_status, stretch=1)
        header_layout.addWidget(self.btn_close)
        
        # --- 2. Content Area (Collapsible) ---
        self.content_frame = QFrame()
        self.content_frame.setObjectName("drawer_content")
        self.content_frame.setStyleSheet("""
            QFrame#drawer_content {
                background-color: #232323;
            }
        """)
        
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Embed the existing QueueWidget
        self.queue_widget = QueueWidget()
        content_layout.addWidget(self.queue_widget)
        
        # Add to main layout
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.content_frame)

    def _connect_signals(self):
        """Wire up internal and external signals."""
        self.btn_toggle.clicked.connect(self.toggle)
        self.btn_close.clicked.connect(self.hide_drawer)
        
        # Connect QueueWidget signals to our header
        if hasattr(self.queue_widget, 'status_updated'):
            self.queue_widget.status_updated.connect(self.update_status)
        
    def update_overlay_geometry(self):
        """
        Recalculate and apply position based on parent size and expanded state.
        Used by parent resize events and internal state changes.
        """
        if not self.parent():
            return
            
        parent_rect = self.parent().rect()
        
        # Sliding Drawer Logic:
        # Height is ALWAYS the full expanded_height to prevent content compression.
        # We simply slide the widget down so content is off-screen.
        target_h = self.expanded_height
        
        if self.is_expanded:
            target_y = parent_rect.height() - target_h
        else:
            # When collapsed, we want only the header visible.
            # So we position the top of the drawer at (parent_height - header_height)
            target_y = parent_rect.height() - self.collapsed_height
            
        self.setGeometry(0, target_y, parent_rect.width(), target_h)
        self.raise_()

    @Slot()
    def toggle(self):
        """Switch between expanded and collapsed states."""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()
            
    @Slot()
    def expand(self):
        """Animate drawer open (Slide Up)."""
        if not self.parent():
            return
            
        # Ensure valid start position if previously hidden/misplaced
        if not self.isVisible() or self.y() == 0:
             self.update_overlay_geometry()
             
        self.show() # Ensure visible
        self.raise_() # Ensure on top
        
        parent_rect = self.parent().rect()
        current_rect = self.geometry()
        
        # Target: Fully visible (Slide Up)
        target_h = self.expanded_height
        target_y = parent_rect.height() - target_h
        target_rect = QRect(0, target_y, parent_rect.width(), target_h)
        
        # Update start value to ensure smooth animation from current position
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(target_rect)
        self.animation.start()
        
        self.is_expanded = True
        self.btn_toggle.setText("▼")
        self.toggled.emit(True)
        
    @Slot()
    def collapse(self):
        """Animate drawer closed (Slide Down)."""
        if not self.parent():
            return
            
        self.raise_() # Ensure on top
            
        parent_rect = self.parent().rect()
        current_rect = self.geometry()
        
        # Target: Only header visible (Slide Down)
        # Height remains full expanded_height!
        target_h = self.expanded_height 
        target_y = parent_rect.height() - self.collapsed_height
        target_rect = QRect(0, target_y, parent_rect.width(), target_h)
        
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(target_rect)
        self.animation.start()
        
        self.is_expanded = False
        self.btn_toggle.setText("▲")
        self.toggled.emit(False)

    @Slot()
    def hide_drawer(self):
        """Completely hide the drawer."""
        self.collapse()
        # Ideally wait for animation, but simple hide is ok for now
        self.setVisible(False)

    @Slot(str, int)
    def update_status(self, message: str, progress: int):
        """Update the header summary."""
        self.lbl_status.setText(f"{message} ({progress}%)" if progress < 100 else message)
        
    def add_task(self, *args, **kwargs):
        """Proxy to queue_widget.add_task and auto-show drawer."""
        self.queue_widget.add_task(*args, **kwargs)
        if not self.isVisible():
            self.setVisible(True)
            self.is_expanded = False # Force collapsed state logic
            self.update_overlay_geometry() # Snap to position
            self.raise_()
    
    @Slot()
    def start_queue(self):
        """Start processing the queue."""
        if not self.isVisible():
            self.setVisible(True)
            self.is_expanded = False
            self.update_overlay_geometry()
        self.raise_()
        self.queue_widget.start_processing()
