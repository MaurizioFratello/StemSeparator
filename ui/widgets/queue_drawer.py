"""
Queue Drawer Widget - Collapsible persistent container for the QueueWidget.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Slot, Signal
from PySide6.QtGui import QColor

from ui.widgets.queue_widget import QueueWidget
from ui.theme import ThemeManager


class QueueDrawer(QWidget):
    """
    A collapsible bottom drawer that houses the global QueueWidget.
    
    Features:
    - Persistent visibility across tabs
    - Auto-hide when empty/inactive (optional mode)
    - Smooth expand/collapse animation
    - Header summary ("Processing... 45%")
    """
    
    # Signal to notify when drawer state changes (expanded/collapsed)
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.is_expanded = False
        self.expanded_height = 400  # Target height when expanded
        self.collapsed_height = 40  # Height of just the header
        
        self._setup_ui()
        self._connect_signals()
        
        # Initialize state
        self.collapse() # Start collapsed
        self.setVisible(False) # Start hidden (until tasks are added)

    def _setup_ui(self):
        """Configure layout and components."""
        # Main layout with no margins to fit tight against bottom
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Styling for the container
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Apply a subtle top border/shadow via style or effect could be added here
        
        # --- 1. Header Bar (Always visible when drawer is 'shown') ---
        self.header = QFrame()
        self.header.setObjectName("drawer_header")
        self.header.setFixedHeight(self.collapsed_height)
        self.header.setStyleSheet("""
            QFrame#drawer_header {
                background-color: #2d2d2d;
                border-top: 1px solid #3d3d3d;
            }
        """)
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 0, 15, 0)
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
        
        # Animation setup
        self.animation = QPropertyAnimation(self, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def _connect_signals(self):
        """Wire up internal and external signals."""
        self.btn_toggle.clicked.connect(self.toggle)
        self.btn_close.clicked.connect(self.hide_drawer)
        
        # Connect QueueWidget signals to our header
        # Note: We need to implement these signals in QueueWidget first
        # Using standard signal connection pattern assuming they will exist
        if hasattr(self.queue_widget, 'status_updated'):
            self.queue_widget.status_updated.connect(self.update_status)
        
        # We also want to auto-show when tasks are added
        # This might need to be connected by the caller, or we expose a method
        
    @Slot()
    def toggle(self):
        """Switch between expanded and collapsed states."""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()
            
    @Slot()
    def expand(self):
        """Animate drawer open."""
        self.show() # Ensure visible
        self.animation.setStartValue(self.height())
        self.animation.setEndValue(self.expanded_height)
        self.animation.start()
        self.is_expanded = True
        self.btn_toggle.setText("▼")
        self.toggled.emit(True)
        
    @Slot()
    def collapse(self):
        """Animate drawer closed (mini-mode)."""
        self.animation.setStartValue(self.height())
        self.animation.setEndValue(self.collapsed_height)
        self.animation.start()
        self.is_expanded = False
        self.btn_toggle.setText("▲")
        self.toggled.emit(False)

    @Slot()
    def hide_drawer(self):
        """Completely hide the drawer."""
        self.collapse()
        # Delay hide until animation finishes? For simplicity, we just hide self
        # But animation is on maximumHeight, so we might just set visible to False
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
            self.collapse() # Show as mini-bar initially
    
    @Slot()
    def start_queue(self):
        """Start processing the queue."""
        if not self.isVisible():
            self.setVisible(True)
        self.queue_widget.start_processing()

