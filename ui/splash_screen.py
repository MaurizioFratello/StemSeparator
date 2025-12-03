"""
Splash Screen Widget

PURPOSE: Display app icon with initialization status messages during startup
CONTEXT: Shows progress during app initialization before main window appears
"""
from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import QSplashScreen
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, QBrush

from config import ICONS_DIR


class SplashScreen(QSplashScreen):
    """
    Custom splash screen with transparent background showing only app icon.
    
    Displays:
    - App icon (centered, scaled to 50% of original size)
    - 4-line status text box overlaid at bottom of icon (white text on dark background)
    
    WHY: Provides clean, professional startup experience with visual feedback
    """
    
    def __init__(self, icon_path: Optional[Path] = None):
        """
        Initialize splash screen with transparent background.
        
        Args:
            icon_path: Path to app icon (defaults to ICONS_DIR/app_icon_1024.png)
        """
        # Load icon for custom drawing
        if icon_path is None:
            icon_path = ICONS_DIR / "app_icon_1024.png"
        
        # Store icon path for custom drawing
        self._icon_path = icon_path
        
        # Create transparent pixmap for base (QSplashScreen requires a pixmap)
        # We'll draw everything ourselves in paintEvent with transparent background
        pixmap = QPixmap(1024, 1024)
        pixmap.fill(Qt.transparent)  # Transparent background
        
        super().__init__(pixmap)
        
        # Status messages buffer (max 4 lines)
        self._status_messages: list[str] = []
        
        # Load icon pixmap for drawing
        if icon_path.exists():
            self._icon_pixmap = QPixmap(str(icon_path))
        else:
            self._icon_pixmap = QPixmap()
        
        # Set window flags with transparent background support
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.SplashScreen | 
            Qt.FramelessWindowHint
        )
        
        # Enable transparent background
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set fixed size
        self.setFixedSize(1024, 1024)
        
        # Center on screen (will be called after QApplication is created)
        # We'll call this explicitly after showing
    
    def center_on_screen(self):
        """Center splash screen on primary screen."""
        from PySide6.QtWidgets import QApplication
        # Ensure QApplication exists
        app = QApplication.instance()
        if app is None:
            return
        
        # Get primary screen geometry
        screen = app.primaryScreen()
        if screen is None:
            return
        
        screen_geometry = screen.geometry()
        splash_width = self.width()
        splash_height = self.height()
        
        # Center on screen
        self.move(
            (screen_geometry.width() - splash_width) // 2,
            (screen_geometry.height() - splash_height) // 2
        )
    
    def showEvent(self, event):
        """Override showEvent to center splash when shown."""
        super().showEvent(event)
        self.center_on_screen()
    
    def update_status(self, message: str):
        """
        Add new status message to display.
        
        Args:
            message: Status message to display (will be added to 4-line buffer)
        
        WHY: Shows initialization progress in real-time
        """
        # Add new message
        self._status_messages.append(message)
        
        # Keep only last 4 messages
        if len(self._status_messages) > 4:
            self._status_messages.pop(0)
        
        # Trigger repaint
        self.repaint()
    
    def show_message(self, message: str):
        """Alias for update_status for QSplashScreen compatibility."""
        self.update_status(message)
    
    def paintEvent(self, event):
        """
        Custom paint event to draw icon and status box with transparent background.
        
        WHY: QSplashScreen's default painting doesn't support transparent backgrounds
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Get window size
        width = self.width()
        height = self.height()
        
        # Clear with transparent background
        painter.fillRect(self.rect(), Qt.transparent)
        
        # Draw icon (centered, scaled to 50% of original size)
        if not self._icon_pixmap.isNull():
            # Scale icon to 50% of original size
            icon_width = self._icon_pixmap.width()
            icon_height = self._icon_pixmap.height()
            
            # 50% scale
            scale = 0.5
            scaled_width = int(icon_width * scale)
            scaled_height = int(icon_height * scale)
            
            # Center icon horizontally, position vertically centered
            icon_x = (width - scaled_width) // 2
            icon_y = (height - scaled_height) // 2
            
            # Draw scaled icon
            scaled_pixmap = self._icon_pixmap.scaled(
                scaled_width,
                scaled_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(icon_x, icon_y, scaled_pixmap)
        
        # Draw status text box centered at bottom (overlaid on icon)
        self._draw_status_box(painter, width, height)
    
    def _draw_status_box(self, painter: QPainter, width: int, height: int):
        """
        Draw semi-transparent status text box overlaid at bottom of icon.
        
        Args:
            painter: QPainter instance
            width: Window width
            height: Window height
        
        WHY: Provides readable status messages overlaid on icon with good contrast
        """
        if not self._status_messages:
            return
        
        # Calculate icon position and size (50% scaled, centered)
        icon_scale = 0.5
        icon_scaled_height = int(self._icon_pixmap.height() * icon_scale) if not self._icon_pixmap.isNull() else 512
        icon_y = (height - icon_scaled_height) // 2
        
        # Box dimensions and position - overlay at bottom of icon area
        box_margin = 30  # Margin from bottom of icon
        box_width = 450
        box_height = 100  # Enough for 4 lines + padding
        
        # Center box horizontally, position at bottom of icon area (overlaid on icon)
        box_x = (width - box_width) // 2
        box_y = icon_y + icon_scaled_height - box_height - box_margin
        
        # Background color (semi-transparent dark for good contrast)
        bg_color = QColor(0, 0, 0, 200)  # Black with 200/255 opacity for better readability
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        
        # Draw rounded rectangle background with slight blur effect
        radius = 10
        painter.drawRoundedRect(
            box_x, box_y, box_width, box_height,
            radius, radius
        )
        
        # Text settings - white text for good contrast
        font = QFont()
        font.setPointSize(11)
        font.setFamily("SF Pro Display, Helvetica Neue, Arial")  # macOS system font
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))  # White text for maximum contrast
        
        # Text padding
        text_padding = 14
        line_height = 20
        text_x = box_x + text_padding
        text_y = box_y + text_padding + line_height
        
        # Draw status messages (last 4, bottom to top)
        messages_to_show = self._status_messages[-4:]  # Last 4 messages
        
        for i, message in enumerate(messages_to_show):
            y_pos = text_y + (i * line_height)
            # Truncate message if too long
            display_message = message
            if len(display_message) > 55:
                display_message = display_message[:52] + "..."
            painter.drawText(text_x, y_pos, display_message)

