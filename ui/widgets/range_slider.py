"""
Range Slider Widget - Dual-handle slider for start/end range selection.

PURPOSE: Provide a single slider control with two handles (start and end).
CONTEXT: Used in Audio Trim widget to replace two separate sliders and save space.
"""

from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent

from ui.app_context import AppContext


class RangeSlider(QWidget):
    """
    Custom range slider with two handles for start and end values.

    WHY: Qt's QSlider doesn't natively support dual handles; this provides a compact solution.
    """

    # Signal: (start_value, end_value) as floats in range [0.0, 1.0]
    values_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_value: float = 0.0  # Range: 0.0 to 1.0
        self._end_value: float = 1.0
        self._min_range: float = 0.01  # Minimum gap between handles
        self._dragging_handle: Optional[str] = None  # None, 'start', or 'end'

        self.setMinimumHeight(40)
        self.setMinimumWidth(200)

    def set_range(self, start: float, end: float):
        """
        Set start and end values (0.0 to 1.0).

        WHY: Allows external code to set values programmatically.
        """
        start = max(0.0, min(1.0, start))
        end = max(0.0, min(1.0, end))

        # Ensure end >= start + min_range
        if end < start + self._min_range:
            end = min(1.0, start + self._min_range)

        self._start_value = start
        self._end_value = end
        self.update()
        self.values_changed.emit(self._start_value, self._end_value)

    def get_range(self) -> tuple[float, float]:
        """Get current start and end values."""
        return self._start_value, self._end_value

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press to determine which handle to drag."""
        if event.button() != Qt.LeftButton:
            return

        x = event.position().x()
        width = self.width()

        # Calculate handle positions in pixels
        track_left = 20  # Left margin for handle
        track_right = width - 20  # Right margin
        track_width = track_right - track_left

        start_x = track_left + (self._start_value * track_width)
        end_x = track_left + (self._end_value * track_width)

        handle_size = 12  # Visual handle size in pixels
        tolerance = 8  # Click tolerance

        # Determine which handle is closest (or if clicking on track)
        dist_to_start = abs(x - start_x)
        dist_to_end = abs(x - end_x)

        if dist_to_start < tolerance:
            self._dragging_handle = "start"
        elif dist_to_end < tolerance:
            self._dragging_handle = "end"
        elif start_x < x < end_x:
            # Clicking between handles - move closest handle
            if dist_to_start < dist_to_end:
                self._dragging_handle = "start"
            else:
                self._dragging_handle = "end"
        else:
            # Clicking outside range - move nearest handle
            if x < start_x:
                self._dragging_handle = "start"
            else:
                self._dragging_handle = "end"

        if self._dragging_handle:
            self.mouseMoveEvent(event)  # Immediately update position

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse drag to update selected handle position."""
        if not self._dragging_handle or not (event.buttons() & Qt.LeftButton):
            return

        x = event.position().x()
        width = self.width()

        track_left = 20
        track_right = width - 20
        track_width = track_right - track_left

        # Convert mouse X to value (0.0 to 1.0)
        raw_value = (x - track_left) / track_width
        raw_value = max(0.0, min(1.0, raw_value))

        if self._dragging_handle == "start":
            # Don't allow start to exceed end - min_range
            new_start = min(raw_value, self._end_value - self._min_range)
            self._start_value = max(0.0, new_start)
        elif self._dragging_handle == "end":
            # Don't allow end to go below start + min_range
            new_end = max(raw_value, self._start_value + self._min_range)
            self._end_value = min(1.0, new_end)

        self.update()
        self.values_changed.emit(self._start_value, self._end_value)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Stop dragging on mouse release."""
        if event.button() == Qt.LeftButton:
            self._dragging_handle = None

    def paintEvent(self, event):
        """Draw the range slider with track and two handles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_y = height / 2

        # Track dimensions
        track_left = 20
        track_right = width - 20
        track_width = track_right - track_left
        track_height = 4

        # Draw inactive track (outside selection)
        inactive_color = QColor("#3d3d3d")
        painter.setPen(Qt.NoPen)
        painter.setBrush(inactive_color)

        # Left inactive region
        start_x = track_left + (self._start_value * track_width)
        painter.drawRoundedRect(
            track_left,
            center_y - track_height // 2,
            start_x - track_left,
            track_height,
            2,
            2,
        )

        # Right inactive region
        end_x = track_left + (self._end_value * track_width)
        painter.drawRoundedRect(
            end_x, center_y - track_height // 2, track_right - end_x, track_height, 2, 2
        )

        # Draw active track (selected range)
        active_color = QColor("#667eea")  # Accent color
        painter.setBrush(active_color)
        painter.drawRoundedRect(
            start_x, center_y - track_height // 2, end_x - start_x, track_height, 2, 2
        )

        # Draw handles
        handle_size = 12
        handle_color = QColor("#ffffff")
        handle_border = QColor("#667eea")

        # Start handle
        painter.setPen(QPen(handle_border, 2))
        painter.setBrush(handle_color)
        painter.drawEllipse(
            int(start_x - handle_size // 2),
            int(center_y - handle_size // 2),
            handle_size,
            handle_size,
        )

        # End handle
        painter.drawEllipse(
            int(end_x - handle_size // 2),
            int(center_y - handle_size // 2),
            handle_size,
            handle_size,
        )
