"""
Loop Waveform Widget - Multi-stem loop visualization with beat markers

PURPOSE: Display audio waveform(s) with detected loop segments and beat positions.
CONTEXT: Used in Loop Preview tab to visualize and select loops for playback/export.

ARCHITECTURE:
- LoopWaveformDisplay: Custom paint widget for rendering waveforms, loops, beats
- LoopWaveformWidget: Container with scroll area, mode selection and controls

SCROLLING: Shows 16 bars at a time with horizontal scrollbar for long songs
"""
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QButtonGroup, QPushButton,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QLinearGradient, QFont

from ui.app_context import AppContext
from ui.theme import ColorPalette


# Display constants
DEFAULT_VISIBLE_BARS = 16    # Default number of bars visible without scrolling
MIN_PIXELS_PER_BAR = 40      # Minimum width per bar for readability


class LoopWaveformDisplay(QWidget):
    """
    Custom widget for rendering waveforms with loop segments and beat markers

    WHY: Provides visual feedback of loop boundaries and musical structure
    PERFORMANCE: Uses QPixmap caching to avoid expensive redraws

    Display Modes:
    - Combined: Single waveform showing mixed audio from all stems
    - Stacked: Multiple waveforms, one per stem (vertically stacked)

    SCROLLING: Widget width is dynamic based on song length and bar duration
    """

    # Signals
    loop_selected = Signal(int)
    song_start_marker_requested = Signal(int)  # downbeat_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()

        # Waveform data
        self.waveform_data: Optional[np.ndarray] = None  # Combined mode: (samples,)
        self.stem_waveforms: Dict[str, np.ndarray] = {}  # Stacked mode: {stem_name: (samples,)}
        self.sample_rate: int = 44100
        self.duration: float = 0.0

        # Loop and beat data
        self.loop_segments: List[Tuple[float, float]] = []  # [(start_sec, end_sec), ...]
        self.beat_times: Optional[np.ndarray] = None  # Array of beat positions in seconds
        self.downbeat_times: Optional[np.ndarray] = None  # Array of downbeat positions

        # Display mode
        self.display_mode: str = "stacked"  # "combined" or "stacked" (default: stacked)

        # Selected loop
        self.selected_loop_index: int = -1  # -1 = none selected

        # Song start marker
        self.song_start_marker_index: Optional[int] = None  # Index in downbeat_times

        # Scrolling: calculate bar duration from downbeats
        self._bar_duration: float = 2.0  # Default 2 seconds per bar (120 BPM, 4/4)
        self._content_width: int = 800  # Calculated based on song length
        self._visible_bars: int = DEFAULT_VISIBLE_BARS  # Bars visible in viewport
        self._viewport_width: int = 800  # Will be set by parent scroll area

        # UI settings - height will be set dynamically by parent
        self.setMinimumHeight(150)

        # Performance: Cache waveform rendering
        self._waveform_cache: Optional[QPixmap] = None
        self._cache_size: tuple = (0, 0)

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self._hover_loop_index: int = -1

    def _calculate_bar_duration(self):
        """
        Calculate average bar duration from downbeat times.
        
        WHY: Bar duration is needed to determine content width for scrolling.
        """
        if self.downbeat_times is not None and len(self.downbeat_times) >= 2:
            # Average interval between downbeats
            intervals = np.diff(self.downbeat_times)
            self._bar_duration = float(np.median(intervals))
        elif self.beat_times is not None and len(self.beat_times) >= 4:
            # Fallback: assume 4 beats per bar
            intervals = np.diff(self.beat_times)
            self._bar_duration = float(np.median(intervals)) * 4
        else:
            # Default: 2 seconds (120 BPM, 4/4)
            self._bar_duration = 2.0

    def _calculate_content_width(self):
        """
        Calculate total content width based on song duration, bar duration, and visible bars setting.
        
        WHY: More visible bars = less detail but more overview
             Fewer visible bars = more detail but more scrolling
        """
        if self.duration <= 0 or self._bar_duration <= 0:
            self._content_width = self._viewport_width
            return

        # Calculate pixels per bar based on viewport width and visible bars setting
        pixels_per_bar = max(MIN_PIXELS_PER_BAR, self._viewport_width / self._visible_bars)

        # Calculate total bars in song
        num_bars = self.duration / self._bar_duration

        # Content width = total bars × pixels per bar
        self._content_width = max(int(num_bars * pixels_per_bar), self._viewport_width)

        # Update widget size
        self.setMinimumWidth(self._content_width)
        self.setFixedWidth(self._content_width)

    def set_visible_bars(self, num_bars: int):
        """
        Set number of bars visible in viewport without scrolling.
        
        Args:
            num_bars: Number of bars to show (typically 2, 4, 8, or 16)
        """
        self._visible_bars = max(1, num_bars)
        self._calculate_content_width()
        self._waveform_cache = None
        self.update()

    def set_viewport_width(self, width: int):
        """Set viewport width (called by parent scroll area on resize)."""
        self._viewport_width = max(100, width)
        self._calculate_content_width()
        self._waveform_cache = None
        self.update()

    def _time_to_x(self, time_sec: float) -> int:
        """Convert time in seconds to x pixel position."""
        if self.duration <= 0:
            return 0
        return int((time_sec / self.duration) * self._content_width)

    def _x_to_time(self, x: int) -> float:
        """Convert x pixel position to time in seconds."""
        if self._content_width <= 0:
            return 0.0
        return (x / self._content_width) * self.duration

    def set_combined_waveform(self, audio_data: np.ndarray, sample_rate: int):
        """
        Set waveform data for combined mode (all stems mixed)

        Args:
            audio_data: numpy array of shape (samples,) or (samples, channels)
            sample_rate: sample rate in Hz
        """
        # Convert to mono if stereo
        if audio_data.ndim == 2:
            audio_data = np.mean(audio_data, axis=1)

        self.waveform_data = audio_data
        self.sample_rate = sample_rate
        self.duration = len(audio_data) / sample_rate
        self.display_mode = "combined"

        # Recalculate dimensions
        self._calculate_bar_duration()
        self._calculate_content_width()

        # Invalidate cache
        self._waveform_cache = None
        self.update()

    def set_stem_waveforms(self, stem_waveforms: Dict[str, np.ndarray], sample_rate: int):
        """
        Set waveform data for stacked mode (separate per stem)

        Args:
            stem_waveforms: Dict mapping stem names to audio data arrays
            sample_rate: sample rate in Hz
        """
        # Convert all to mono
        processed = {}
        max_len = 0

        for stem_name, audio_data in stem_waveforms.items():
            if audio_data.ndim == 2:
                audio_data = np.mean(audio_data, axis=1)
            processed[stem_name] = audio_data
            max_len = max(max_len, len(audio_data))

        self.stem_waveforms = processed
        self.sample_rate = sample_rate
        self.duration = max_len / sample_rate
        self.display_mode = "stacked"

        # Recalculate dimensions
        self._calculate_bar_duration()
        self._calculate_content_width()

        # Invalidate cache
        self._waveform_cache = None
        self.update()

    def set_loop_segments(self, loop_segments: List[Tuple[float, float]]):
        """
        Set loop segment boundaries

        Args:
            loop_segments: List of (start_sec, end_sec) tuples
        """
        self.loop_segments = loop_segments
        self._waveform_cache = None
        self.update()

    def set_beat_times(self, beat_times: np.ndarray, downbeat_times: np.ndarray):
        """
        Set beat marker positions

        Args:
            beat_times: Array of beat positions in seconds
            downbeat_times: Array of downbeat positions in seconds
        """
        self.beat_times = beat_times
        self.downbeat_times = downbeat_times

        # Recalculate bar duration from new downbeat data
        self._calculate_bar_duration()
        self._calculate_content_width()

        self._waveform_cache = None
        self.update()

    def set_selected_loop(self, loop_index: int):
        """Select a loop segment by index"""
        if -1 <= loop_index < len(self.loop_segments):
            self.selected_loop_index = loop_index
            self.update()

    def clear(self):
        """Clear all data"""
        self.waveform_data = None
        self.stem_waveforms = {}
        self.duration = 0.0
        self.loop_segments = []
        self.beat_times = None
        self.downbeat_times = None
        self.selected_loop_index = -1
        self._hover_loop_index = -1
        self._waveform_cache = None
        self._content_width = self._viewport_width
        self.setMinimumWidth(self._viewport_width)
        self.update()

    def resizeEvent(self, event):
        """Invalidate cache on resize"""
        self._waveform_cache = None
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse clicks on loop segments and song start marker"""
        click_x = event.pos().x()

        # Right-click: Show song start marker context menu
        if event.button() == Qt.RightButton:
            # Find nearest downbeat
            downbeat_idx = self._find_nearest_downbeat(click_x, max_distance_px=30)
            if downbeat_idx is not None:
                self._show_song_start_context_menu(event.globalPos(), downbeat_idx)
            return

        # Left-click: Select loop
        if event.button() != Qt.LeftButton:
            return

        # Convert click position to time
        click_time = self._x_to_time(click_x)

        if self.duration == 0:
            return

        # Find which loop was clicked
        for i, (start_time, end_time) in enumerate(self.loop_segments):
            if start_time <= click_time <= end_time:
                self.selected_loop_index = i
                self.loop_selected.emit(i)
                self.update()
                self.ctx.logger().info(f"Loop {i + 1} selected: {start_time:.2f}s - {end_time:.2f}s")
                break

    def mouseMoveEvent(self, event):
        """Handle mouse hover for loop highlighting"""
        mouse_x = event.pos().x()
        hover_time = self._x_to_time(mouse_x)

        if self.duration == 0:
            return

        # Find which loop is being hovered
        new_hover_index = -1
        for i, (start_time, end_time) in enumerate(self.loop_segments):
            if start_time <= hover_time <= end_time:
                new_hover_index = i
                break

        if new_hover_index != self._hover_loop_index:
            self._hover_loop_index = new_hover_index
            self.update()

    def paintEvent(self, event):
        """Render waveform(s) with loop segments and beat markers"""
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        # Modern gradient background
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor(ColorPalette.WAVEFORM_BACKGROUND))
        gradient.setColorAt(1, QColor("#0f0f0f"))
        painter.fillRect(self.rect(), gradient)

        # Check if we have data
        has_data = (
            (self.display_mode == "combined" and self.waveform_data is not None) or
            (self.display_mode == "stacked" and len(self.stem_waveforms) > 0)
        )

        if not has_data:
            # Show placeholder
            painter.setPen(QColor(ColorPalette.TEXT_SECONDARY))
            painter.drawText(self.rect(), Qt.AlignCenter,
                           "Load stems and detect beats to view loops")
            return

        # Use cached waveform if available and size hasn't changed
        if self._waveform_cache is None or self._cache_size != (width, height):
            self._render_waveform_to_cache()

        # Draw cached waveform
        if self._waveform_cache:
            painter.drawPixmap(0, 0, self._waveform_cache)

        # Draw dynamic overlays (not cached for smooth interaction)
        self._draw_loop_overlays(painter)
        self._draw_beat_markers(painter)
        self._draw_song_start_marker(painter)

    def _render_waveform_to_cache(self):
        """Render waveform(s) to cached pixmap"""
        width = self.width()
        height = self.height()

        if width <= 0 or height <= 0:
            return

        # Create pixmap for caching
        self._waveform_cache = QPixmap(width, height)
        self._waveform_cache.fill(Qt.transparent)
        self._cache_size = (width, height)

        painter = QPainter(self._waveform_cache)

        if self.display_mode == "combined":
            self._render_combined_waveform(painter, width, height)
        else:
            self._render_stacked_waveforms(painter, width, height)

        painter.end()

    def _render_combined_waveform(self, painter: QPainter, width: int, height: int):
        """Render single combined waveform"""
        if self.waveform_data is None or len(self.waveform_data) == 0:
            return

        center_y = height / 2

        # Calculate samples per pixel based on content width
        samples_per_pixel = max(1, len(self.waveform_data) // width)

        # Draw waveform
        waveform_pen = QPen(QColor(ColorPalette.WAVEFORM_PRIMARY), 2)
        painter.setPen(waveform_pen)

        for x in range(width):
            start_idx = int(x * samples_per_pixel)
            end_idx = min(start_idx + samples_per_pixel, len(self.waveform_data))

            if start_idx >= len(self.waveform_data):
                break

            # Get max/min envelope
            chunk = self.waveform_data[start_idx:end_idx]
            max_val = np.max(chunk)
            min_val = np.min(chunk)

            # Scale to height (with padding)
            max_y = center_y - (max_val * center_y * 0.85)
            min_y = center_y - (min_val * center_y * 0.85)

            painter.drawLine(x, int(max_y), x, int(min_y))

        # Draw center line
        painter.setPen(QPen(QColor(ColorPalette.BORDER_DEFAULT), 1))
        painter.drawLine(0, int(center_y), width, int(center_y))

    def _render_stacked_waveforms(self, painter: QPainter, width: int, height: int):
        """Render multiple stacked waveforms (one per stem)"""
        if not self.stem_waveforms:
            return

        num_stems = len(self.stem_waveforms)
        stem_height = height // num_stems

        # Define colors for different stems
        stem_colors = [
            ColorPalette.WAVEFORM_PRIMARY,
            ColorPalette.ACCENT_PRIMARY,
            ColorPalette.ACCENT_SECONDARY,
            "#ff6b9d",  # Pink
            "#4ecdc4",  # Teal
        ]

        for i, (stem_name, waveform_data) in enumerate(self.stem_waveforms.items()):
            if len(waveform_data) == 0:
                continue

            # Calculate vertical position
            y_offset = i * stem_height
            center_y = y_offset + stem_height / 2

            # Calculate samples per pixel
            samples_per_pixel = max(1, len(waveform_data) // width)

            # Draw waveform with unique color
            color = stem_colors[i % len(stem_colors)]
            waveform_pen = QPen(QColor(color), 1)
            painter.setPen(waveform_pen)

            for x in range(width):
                start_idx = int(x * samples_per_pixel)
                end_idx = min(start_idx + samples_per_pixel, len(waveform_data))

                if start_idx >= len(waveform_data):
                    break

                # Get max/min envelope
                chunk = waveform_data[start_idx:end_idx]
                max_val = np.max(chunk)
                min_val = np.min(chunk)

                # Scale to stem height (with padding)
                scale = (stem_height / 2) * 0.8
                max_y = center_y - (max_val * scale)
                min_y = center_y - (min_val * scale)

                painter.drawLine(x, int(max_y), x, int(min_y))

            # Draw center line for this stem
            painter.setPen(QPen(QColor(ColorPalette.BORDER_DEFAULT), 1, Qt.DotLine))
            painter.drawLine(0, int(center_y), width, int(center_y))

            # Draw stem label
            painter.setPen(QColor(ColorPalette.TEXT_SECONDARY))
            painter.drawText(5, y_offset + 15, stem_name)

    def _draw_loop_overlays(self, painter: QPainter):
        """Draw loop segment boundaries and highlights"""
        if not self.loop_segments or self.duration == 0:
            return

        width = self.width()
        height = self.height()

        for i, (start_time, end_time) in enumerate(self.loop_segments):
            # Calculate pixel positions using time_to_x
            start_x = self._time_to_x(start_time)
            end_x = self._time_to_x(end_time)
            loop_width = end_x - start_x

            # Highlight selected loop
            if i == self.selected_loop_index:
                highlight_color = QColor(ColorPalette.ACCENT_PRIMARY)
                highlight_color.setAlpha(40)
                painter.fillRect(start_x, 0, loop_width, height, highlight_color)

            # Highlight hovered loop
            elif i == self._hover_loop_index:
                hover_color = QColor(ColorPalette.ACCENT_SECONDARY)
                hover_color.setAlpha(20)
                painter.fillRect(start_x, 0, loop_width, height, hover_color)

            # Draw loop boundaries
            boundary_pen = QPen(QColor(ColorPalette.ACCENT_PRIMARY), 2)
            painter.setPen(boundary_pen)
            painter.drawLine(start_x, 0, start_x, height)
            painter.drawLine(end_x, 0, end_x, height)

            # Draw loop number label
            painter.setPen(QColor(ColorPalette.TEXT_PRIMARY))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)

            loop_label = f"Loop {i + 1}"
            label_x = start_x + 5
            label_y = 20

            # Draw label background
            label_rect = painter.fontMetrics().boundingRect(loop_label)
            label_rect.moveTopLeft(QPoint(int(label_x), int(label_y - label_rect.height())))
            label_rect.adjust(-3, -2, 3, 2)

            bg_color = QColor(ColorPalette.BACKGROUND_PRIMARY)
            bg_color.setAlpha(180)
            painter.fillRect(label_rect, bg_color)

            # Draw label text
            painter.drawText(label_x, label_y, loop_label)

    def _draw_beat_markers(self, painter: QPainter):
        """Draw beat, half-beat and downbeat markers"""
        if self.beat_times is None or self.duration == 0:
            return

        height = self.height()

        # --- Regular beats (thin dashed lines) ---
        if len(self.beat_times) > 0:
            beat_pen = QPen(QColor(ColorPalette.TEXT_SECONDARY), 1, Qt.DashLine)
            beat_pen.setDashPattern([2, 4])
            painter.setPen(beat_pen)

            for beat_time in self.beat_times:
                x = self._time_to_x(beat_time)
                painter.drawLine(x, 0, x, height)

        # --- Half beats (between consecutive beats, lighter dotted lines) ---
        if len(self.beat_times) > 1:
            half_beat_pen = QPen(QColor(ColorPalette.TEXT_SECONDARY), 1, Qt.DotLine)
            # Slightly lower alpha to avoid clutter
            color = half_beat_pen.color()
            color.setAlpha(120)
            half_beat_pen.setColor(color)
            painter.setPen(half_beat_pen)

            for i in range(len(self.beat_times) - 1):
                t1 = self.beat_times[i]
                t2 = self.beat_times[i + 1]
                mid_time = (t1 + t2) / 2.0
                x = self._time_to_x(mid_time)
                painter.drawLine(x, 0, x, height)

        # --- Downbeats (prominent solid lines) ---
        if self.downbeat_times is not None and len(self.downbeat_times) > 0:
            downbeat_pen = QPen(QColor(ColorPalette.ACCENT_SECONDARY), 2)
            painter.setPen(downbeat_pen)

            for downbeat_time in self.downbeat_times:
                x = self._time_to_x(downbeat_time)
                painter.drawLine(x, 0, x, height)

    def _draw_song_start_marker(self, painter: QPainter):
        """Draw song start marker as prominent vertical line."""
        if self.song_start_marker_index is None:
            return

        if self.downbeat_times is None or len(self.downbeat_times) == 0:
            return

        if self.song_start_marker_index >= len(self.downbeat_times):
            return

        # Get marker position
        marker_time = self.downbeat_times[self.song_start_marker_index]
        marker_x = self._time_to_x(marker_time)

        height = self.height()

        # Draw prominent orange line with glow effect
        # Background glow
        glow_pen = QPen(QColor(255, 165, 0, 100), 8)
        painter.setPen(glow_pen)
        painter.drawLine(marker_x, 0, marker_x, height)

        # Main marker line
        marker_pen = QPen(QColor(255, 165, 0), 3)
        painter.setPen(marker_pen)
        painter.drawLine(marker_x, 0, marker_x, height)

        # Draw label at bottom (near yellow bar)
        label = f"Song Start (Bar {self.song_start_marker_index})"
        font = QFont()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)

        # Background for label - positioned at bottom
        label_width = 150
        label_height = 20
        label_x = max(5, min(marker_x - label_width // 2, self.width() - label_width - 5))
        label_y = height - label_height - 5  # 5px from bottom

        painter.fillRect(label_x, label_y, label_width, label_height, QColor(255, 165, 0, 200))

        # Label text
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawText(label_x, label_y, label_width, label_height,
                        Qt.AlignCenter, label)

    def set_song_start_marker(self, downbeat_index: int):
        """
        Set song start marker at specified downbeat index.

        Args:
            downbeat_index: Index in self.downbeat_times array
        """
        if self.downbeat_times is None or downbeat_index >= len(self.downbeat_times):
            return

        self.song_start_marker_index = downbeat_index
        self.update()  # Trigger repaint

    def clear_song_start_marker(self):
        """Clear song start marker."""
        self.song_start_marker_index = None
        self.update()  # Trigger repaint

    def _find_nearest_downbeat(self, x: int, max_distance_px: int = 20) -> Optional[int]:
        """
        Find nearest downbeat to given x position.

        Args:
            x: X pixel position
            max_distance_px: Maximum distance in pixels to consider (default: 20px)

        Returns:
            Downbeat index if found within max_distance, None otherwise
        """
        if self.downbeat_times is None or len(self.downbeat_times) == 0:
            return None

        click_time = self._x_to_time(x)

        # Find nearest downbeat
        nearest_idx = None
        min_distance = float('inf')

        for idx, downbeat_time in enumerate(self.downbeat_times):
            downbeat_x = self._time_to_x(downbeat_time)
            distance = abs(downbeat_x - x)

            if distance < min_distance and distance <= max_distance_px:
                min_distance = distance
                nearest_idx = idx

        return nearest_idx

    def _show_song_start_context_menu(self, global_pos: QPoint, downbeat_idx: int):
        """
        Show context menu for setting/clearing song start marker.

        Args:
            global_pos: Global position for menu
            downbeat_idx: Index of downbeat near click position
        """
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)

        # Check if this downbeat already has the marker
        if self.song_start_marker_index == downbeat_idx:
            # Option to clear marker
            action = menu.addAction("✕ Clear Song Start Marker")
            if menu.exec_(global_pos) == action:
                self.clear_song_start_marker()
                self.ctx.logger().info("Song start marker cleared")
                # Emit signal to notify PlayerWidget
                self.song_start_marker_requested.emit(-1)  # -1 = clear marker
        else:
            # Option to set marker at this downbeat
            downbeat_time = self.downbeat_times[downbeat_idx]
            action = menu.addAction(f"⚑ Set Song Start at Bar {downbeat_idx} ({downbeat_time:.2f}s)")
            if menu.exec_(global_pos) == action:
                self.set_song_start_marker(downbeat_idx)
                self.ctx.logger().info(f"Song start marker set at bar {downbeat_idx}")
                # Emit signal to notify PlayerWidget
                self.song_start_marker_requested.emit(downbeat_idx)


class LoopWaveformWidget(QWidget):
    """
    Loop waveform visualization with scrollable view and mode selection

    Features:
    - Horizontal scrolling for long songs (16 bars visible at a time)
    - Combined/Stacked view mode selection
    - Visual loop segments with beat markers
    - Clickable loop selection
    - Signal emission for loop selection
    """

    # Signals
    loop_selected = Signal(int)  # loop_index
    mode_changed = Signal(str)   # "combined" or "stacked"
    bars_per_loop_changed = Signal(int)  # 2, 4, or 8 bars per loop

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()

        self._setup_ui()
        self._connect_signals()

        # Summary info for header label
        self._summary_prefix: str = ""   # e.g. "104.0 BPM (85%)"
        self._loops_count: int = 0
        self._bars_total: int = 0

    def _setup_ui(self):
        """Setup widget layout with scroll area"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Controls header - horizontal layout with vertical separators
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)

        # 1. View mode selector
        mode_label = QLabel("View:")
        mode_label.setStyleSheet(f"color: {ColorPalette.TEXT_PRIMARY};")
        controls_layout.addWidget(mode_label)

        self.btn_combined = QPushButton("Combined")
        self.btn_combined.setCheckable(True)
        self.btn_combined.setObjectName("toggle_button_wide")

        self.btn_stacked = QPushButton("Stacked")
        self.btn_stacked.setCheckable(True)
        self.btn_stacked.setChecked(True)  # Default: Stacked view
        self.btn_stacked.setObjectName("toggle_button_wide")

        # Button group for exclusive selection
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.addButton(self.btn_combined, 0)
        self.mode_button_group.addButton(self.btn_stacked, 1)

        controls_layout.addWidget(self.btn_combined)
        controls_layout.addWidget(self.btn_stacked)

        # Vertical separator 1
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setStyleSheet("color: #333; max-width: 1px;")
        controls_layout.addWidget(separator1)

        # 2. Bars per loop selector
        bars_per_loop_label = QLabel("Bars per loop:")
        bars_per_loop_label.setStyleSheet(f"color: {ColorPalette.TEXT_PRIMARY};")
        controls_layout.addWidget(bars_per_loop_label)

        self.btn_loop_2 = QPushButton("2")
        self.btn_loop_2.setCheckable(True)
        self.btn_loop_2.setObjectName("toggle_button")
        self.btn_loop_2.setToolTip("2 bars per loop")

        self.btn_loop_4 = QPushButton("4")
        self.btn_loop_4.setCheckable(True)
        self.btn_loop_4.setChecked(True)  # Default
        self.btn_loop_4.setObjectName("toggle_button")
        self.btn_loop_4.setToolTip("4 bars per loop")

        self.btn_loop_8 = QPushButton("8")
        self.btn_loop_8.setCheckable(True)
        self.btn_loop_8.setObjectName("toggle_button")
        self.btn_loop_8.setToolTip("8 bars per loop")

        # Button group for bars per loop
        self.bars_per_loop_group = QButtonGroup(self)
        self.bars_per_loop_group.addButton(self.btn_loop_2, 2)
        self.bars_per_loop_group.addButton(self.btn_loop_4, 4)
        self.bars_per_loop_group.addButton(self.btn_loop_8, 8)

        controls_layout.addWidget(self.btn_loop_2)
        controls_layout.addWidget(self.btn_loop_4)
        controls_layout.addWidget(self.btn_loop_8)

        # Vertical separator 2
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setStyleSheet("color: #333; max-width: 1px;")
        controls_layout.addWidget(separator2)

        # 3. Bars visible (zoom) selector
        zoom_label = QLabel("Bars visible:")
        zoom_label.setStyleSheet(f"color: {ColorPalette.TEXT_PRIMARY};")
        controls_layout.addWidget(zoom_label)

        self.btn_2_bars = QPushButton("2")
        self.btn_2_bars.setCheckable(True)
        self.btn_2_bars.setObjectName("toggle_button")
        self.btn_2_bars.setToolTip("Show 2 bars (most detail)")

        self.btn_4_bars = QPushButton("4")
        self.btn_4_bars.setCheckable(True)
        self.btn_4_bars.setObjectName("toggle_button")
        self.btn_4_bars.setToolTip("Show 4 bars")

        self.btn_8_bars = QPushButton("8")
        self.btn_8_bars.setCheckable(True)
        self.btn_8_bars.setObjectName("toggle_button")
        self.btn_8_bars.setToolTip("Show 8 bars")

        self.btn_16_bars = QPushButton("16")
        self.btn_16_bars.setCheckable(True)
        self.btn_16_bars.setChecked(True)  # Default
        self.btn_16_bars.setObjectName("toggle_button")
        self.btn_16_bars.setToolTip("Show 16 bars (overview)")

        # Button group for zoom selection
        self.zoom_button_group = QButtonGroup(self)
        self.zoom_button_group.addButton(self.btn_2_bars, 2)
        self.zoom_button_group.addButton(self.btn_4_bars, 4)
        self.zoom_button_group.addButton(self.btn_8_bars, 8)
        self.zoom_button_group.addButton(self.btn_16_bars, 16)

        controls_layout.addWidget(self.btn_2_bars)
        controls_layout.addWidget(self.btn_4_bars)
        controls_layout.addWidget(self.btn_8_bars)
        controls_layout.addWidget(self.btn_16_bars)

        controls_layout.addStretch()

        # Info label
        self.info_label = QLabel("No loops detected")
        self.info_label.setStyleSheet(f"color: {ColorPalette.TEXT_SECONDARY}; font-size: 9pt;")
        controls_layout.addWidget(self.info_label)

        layout.addLayout(controls_layout)

        # Scroll area for waveform display
        self.scroll_area = QScrollArea()
        # Start with widgetResizable=True for placeholder (will be set to False when content loads)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Ensure scroll area expands to fill available space (for placeholder visibility)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background: #1a1a1a;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #444;
                border-radius: 5px;
                min-width: 40px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #555;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        # Waveform display (inside scroll area)
        self.waveform_display = LoopWaveformDisplay()
        # Size policy: width managed by setWidgetResizable toggle, height expands
        self.waveform_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.waveform_display.setMinimumHeight(150)  # Minimum height for readability
        self.scroll_area.setWidget(self.waveform_display)

        layout.addWidget(self.scroll_area, stretch=1)

        # Schedule initial dimension update after layout is complete
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._update_display_dimensions)

    def _connect_signals(self):
        """Connect signals"""
        self.btn_combined.clicked.connect(lambda: self._on_mode_changed("combined"))
        self.btn_stacked.clicked.connect(lambda: self._on_mode_changed("stacked"))
        self.waveform_display.loop_selected.connect(self._on_loop_selected)

        # Bars per loop buttons
        self.bars_per_loop_group.idClicked.connect(self._on_bars_per_loop_changed)

        # Zoom buttons
        self.zoom_button_group.idClicked.connect(self._on_zoom_changed)

        # Install event filter on scroll area viewport to catch resize events
        self.scroll_area.viewport().installEventFilter(self)

    def _on_mode_changed(self, mode: str):
        """Handle view mode change"""
        self.waveform_display.display_mode = mode
        self.waveform_display._waveform_cache = None
        self.waveform_display.update()
        self.mode_changed.emit(mode)
        self.ctx.logger().info(f"Waveform view mode: {mode}")

    def _on_bars_per_loop_changed(self, num_bars: int):
        """Handle bars per loop change"""
        self.bars_per_loop_changed.emit(num_bars)
        self.ctx.logger().info(f"Bars per loop changed: {num_bars}")

    def set_bars_per_loop(self, num_bars: int):
        """Set bars per loop selection (called from parent)"""
        button = self.bars_per_loop_group.button(num_bars)
        if button:
            button.setChecked(True)

    def _on_zoom_changed(self, num_bars: int):
        """Handle visible bars (zoom) change"""
        self.waveform_display.set_visible_bars(num_bars)
        self.ctx.logger().info(f"Waveform zoom: {num_bars} bars visible")

    def resizeEvent(self, event):
        """Update waveform display when widget resizes"""
        super().resizeEvent(event)
        # Use singleShot to ensure layout is complete before updating dimensions
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._update_display_dimensions)

    def showEvent(self, event):
        """Update dimensions when widget becomes visible (e.g., tab switch, fullscreen)"""
        super().showEvent(event)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._update_display_dimensions)

    def eventFilter(self, watched, event):
        """
        Catch resize events on scroll area viewport.
        
        WHY: When window goes fullscreen, the viewport resizes but resizeEvent
        of the parent widget may not trigger dimension updates correctly.
        """
        from PySide6.QtCore import QEvent
        if watched == self.scroll_area.viewport() and event.type() == QEvent.Resize:
            # Defer update to ensure layout is complete
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._update_display_dimensions)
        return super().eventFilter(watched, event)

    def _update_display_dimensions(self):
        """
        Update waveform display dimensions based on current scroll area size.
        
        WHY: Ensures waveform fills available space both horizontally and vertically.
        Called on resize and before loading new waveform data.
        """
        # Update viewport width for proper horizontal scaling
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width > 0:
            self.waveform_display.set_viewport_width(viewport_width)

        # Update height to fill available vertical space
        viewport_height = self.scroll_area.viewport().height()
        if viewport_height > 0:
            # Set waveform display to fill the viewport height
            self.waveform_display.setFixedHeight(viewport_height)
            # Invalidate cache since dimensions changed
            self.waveform_display._waveform_cache = None

    def _on_loop_selected(self, loop_index: int):
        """Handle loop selection from display"""
        self.loop_selected.emit(loop_index)

        # Auto-scroll to selected loop
        if 0 <= loop_index < len(self.waveform_display.loop_segments):
            start_time, end_time = self.waveform_display.loop_segments[loop_index]
            loop_center_x = self.waveform_display._time_to_x((start_time + end_time) / 2)

            # Center the loop in the viewport
            viewport_width = self.scroll_area.viewport().width()
            scroll_to = max(0, loop_center_x - viewport_width // 2)
            self.scroll_area.horizontalScrollBar().setValue(scroll_to)

    def set_combined_waveform(self, audio_data: np.ndarray, sample_rate: int):
        """Set waveform data for combined mode"""
        # Ensure viewport dimensions are current before setting data
        self._update_display_dimensions()
        # Disable widget resizing to allow scrolling for content
        self.scroll_area.setWidgetResizable(False)
        self.waveform_display.set_combined_waveform(audio_data, sample_rate)

    def set_stem_waveforms(self, stem_waveforms: Dict[str, np.ndarray], sample_rate: int):
        """Set waveform data for stacked mode"""
        # Ensure viewport dimensions are current before setting data
        self._update_display_dimensions()
        # Disable widget resizing to allow scrolling for content
        self.scroll_area.setWidgetResizable(False)
        self.waveform_display.set_stem_waveforms(stem_waveforms, sample_rate)

    def set_loop_segments(self, loop_segments: List[Tuple[float, float]]):
        """Set loop segment boundaries"""
        self.waveform_display.set_loop_segments(loop_segments)

        # Store counts for header info
        self._loops_count = len(loop_segments)
        if self._loops_count > 0 and self.waveform_display._bar_duration > 0:
            self._bars_total = int(self.waveform_display.duration / self.waveform_display._bar_duration)
        else:
            self._bars_total = 0

        self._update_info_label()

    def set_beat_times(self, beat_times: np.ndarray, downbeat_times: np.ndarray):
        """Set beat marker positions"""
        self.waveform_display.set_beat_times(beat_times, downbeat_times)

    def set_summary_prefix(self, prefix: str):
        """
        Set textual prefix for header info, e.g. "104.0 BPM (85%)".

        WHY: Allows PlayerWidget to inject BPM + confidence before loops/bars info.
        """
        self._summary_prefix = prefix
        self._update_info_label()

    def _update_info_label(self):
        """Update compact header info label above waveform."""
        if self._loops_count <= 0:
            self.info_label.setText("No loops detected")
            return

        parts = []
        if self._summary_prefix:
            parts.append(self._summary_prefix)

        parts.append(f"{self._loops_count} loops detected")

        if self._bars_total > 0:
            parts.append(f"{self._bars_total} bars total")

        self.info_label.setText(" • ".join(parts))

    def set_selected_loop(self, loop_index: int):
        """Select a loop segment by index"""
        self.waveform_display.set_selected_loop(loop_index)

    def clear(self):
        """Clear all data"""
        # Enable widget resizing so placeholder fills scroll area horizontally
        self.scroll_area.setWidgetResizable(True)
        self.waveform_display.clear()
        self.info_label.setText("No loops detected")
