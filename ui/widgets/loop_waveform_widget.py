"""
Loop Waveform Widget - Multi-stem loop visualization with beat markers

PURPOSE: Display audio waveform(s) with detected loop segments and beat positions.
CONTEXT: Used in Loop Preview tab to visualize and select loops for playback/export.

ARCHITECTURE:
- LoopWaveformDisplay: Custom paint widget for rendering waveforms, loops, beats
- LoopWaveformWidget: Container with mode selection and controls
"""
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QButtonGroup, QPushButton
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QLinearGradient, QFont

from ui.app_context import AppContext
from ui.theme import ColorPalette


class LoopWaveformDisplay(QWidget):
    """
    Custom widget for rendering waveforms with loop segments and beat markers

    WHY: Provides visual feedback of loop boundaries and musical structure
    PERFORMANCE: Uses QPixmap caching to avoid expensive redraws

    Display Modes:
    - Combined: Single waveform showing mixed audio from all stems
    - Stacked: Multiple waveforms, one per stem (vertically stacked)
    """

    # Signal: loop_index selected
    loop_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()

        # Waveform data
        self.waveform_data: Optional[np.ndarray] = None  # Combined mode: (samples,)
        self.stem_waveforms: Dict[str, np.ndarray] = {}  # Stacked mode: {stem_name: (samples,)}
        self.duration: float = 0.0

        # Loop and beat data
        self.loop_segments: List[Tuple[float, float]] = []  # [(start_sec, end_sec), ...]
        self.beat_times: Optional[np.ndarray] = None  # Array of beat positions in seconds
        self.downbeat_times: Optional[np.ndarray] = None  # Array of downbeat positions

        # Display mode
        self.display_mode: str = "combined"  # "combined" or "stacked"

        # Selected loop
        self.selected_loop_index: int = -1  # -1 = none selected

        # UI settings
        self.setMinimumHeight(200)
        self.setMaximumHeight(600)

        # Performance: Cache waveform rendering
        self._waveform_cache: Optional[QPixmap] = None
        self._cache_size: tuple = (0, 0)

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self._hover_loop_index: int = -1

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
        self.duration = len(audio_data) / sample_rate
        self.display_mode = "combined"

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
        self.duration = max_len / sample_rate
        self.display_mode = "stacked"

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
        self.update()

    def resizeEvent(self, event):
        """Invalidate cache on resize"""
        self._waveform_cache = None
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse clicks on loop segments"""
        if event.button() != Qt.LeftButton:
            return

        # Convert click position to time
        click_x = event.pos().x()
        width = self.width()

        if self.duration == 0 or width == 0:
            return

        click_time = (click_x / width) * self.duration

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
        width = self.width()

        if self.duration == 0 or width == 0:
            return

        hover_time = (mouse_x / width) * self.duration

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

        # Downsample waveform for display
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

            # Downsample waveform
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
            # Calculate pixel positions
            start_x = int((start_time / self.duration) * width)
            end_x = int((end_time / self.duration) * width)
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
        """Draw beat and downbeat markers"""
        if self.beat_times is None or self.duration == 0:
            return

        width = self.width()
        height = self.height()

        # Draw regular beats (thin lines)
        if len(self.beat_times) > 0:
            beat_pen = QPen(QColor(ColorPalette.TEXT_SECONDARY), 1, Qt.DashLine)
            beat_pen.setDashPattern([2, 4])
            painter.setPen(beat_pen)

            for beat_time in self.beat_times:
                x = int((beat_time / self.duration) * width)
                painter.drawLine(x, 0, x, height)

        # Draw downbeats (prominent lines)
        if self.downbeat_times is not None and len(self.downbeat_times) > 0:
            downbeat_pen = QPen(QColor(ColorPalette.ACCENT_SECONDARY), 2)
            painter.setPen(downbeat_pen)

            for downbeat_time in self.downbeat_times:
                x = int((downbeat_time / self.duration) * width)
                painter.drawLine(x, 0, x, height)


class LoopWaveformWidget(QWidget):
    """
    Loop waveform visualization with mode selection and controls

    Features:
    - Combined/Stacked view mode selection
    - Visual loop segments with beat markers
    - Clickable loop selection
    - Signal emission for loop selection
    """

    # Signals
    loop_selected = Signal(int)  # loop_index
    mode_changed = Signal(str)   # "combined" or "stacked"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup widget layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Controls header
        controls_layout = QHBoxLayout()

        # View mode selector
        mode_label = QLabel("View Mode:")
        mode_label.setStyleSheet(f"color: {ColorPalette.TEXT_PRIMARY};")
        controls_layout.addWidget(mode_label)

        self.btn_combined = QPushButton("Combined")
        self.btn_combined.setCheckable(True)
        self.btn_combined.setChecked(True)
        self.btn_combined.setObjectName("toggle_button")

        self.btn_stacked = QPushButton("Stacked")
        self.btn_stacked.setCheckable(True)
        self.btn_stacked.setObjectName("toggle_button")

        # Button group for exclusive selection
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.addButton(self.btn_combined, 0)
        self.mode_button_group.addButton(self.btn_stacked, 1)

        controls_layout.addWidget(self.btn_combined)
        controls_layout.addWidget(self.btn_stacked)
        controls_layout.addStretch()

        # Info label
        self.info_label = QLabel("No loops detected")
        self.info_label.setStyleSheet(f"color: {ColorPalette.TEXT_SECONDARY}; font-size: 9pt;")
        controls_layout.addWidget(self.info_label)

        layout.addLayout(controls_layout)

        # Waveform display
        self.waveform_display = LoopWaveformDisplay()
        layout.addWidget(self.waveform_display, stretch=1)

    def _connect_signals(self):
        """Connect signals"""
        self.btn_combined.clicked.connect(lambda: self._on_mode_changed("combined"))
        self.btn_stacked.clicked.connect(lambda: self._on_mode_changed("stacked"))
        self.waveform_display.loop_selected.connect(self._on_loop_selected)

    def _on_mode_changed(self, mode: str):
        """Handle view mode change"""
        self.waveform_display.display_mode = mode
        self.waveform_display._waveform_cache = None
        self.waveform_display.update()
        self.mode_changed.emit(mode)
        self.ctx.logger().info(f"Waveform view mode: {mode}")

    def _on_loop_selected(self, loop_index: int):
        """Handle loop selection from display"""
        self.loop_selected.emit(loop_index)

    def set_combined_waveform(self, audio_data: np.ndarray, sample_rate: int):
        """Set waveform data for combined mode"""
        self.waveform_display.set_combined_waveform(audio_data, sample_rate)

    def set_stem_waveforms(self, stem_waveforms: Dict[str, np.ndarray], sample_rate: int):
        """Set waveform data for stacked mode"""
        self.waveform_display.set_stem_waveforms(stem_waveforms, sample_rate)

    def set_loop_segments(self, loop_segments: List[Tuple[float, float]]):
        """Set loop segment boundaries"""
        self.waveform_display.set_loop_segments(loop_segments)

        # Update info label
        if len(loop_segments) > 0:
            self.info_label.setText(f"{len(loop_segments)} loops detected")
        else:
            self.info_label.setText("No loops detected")

    def set_beat_times(self, beat_times: np.ndarray, downbeat_times: np.ndarray):
        """Set beat marker positions"""
        self.waveform_display.set_beat_times(beat_times, downbeat_times)

    def set_selected_loop(self, loop_index: int):
        """Select a loop segment by index"""
        self.waveform_display.set_selected_loop(loop_index)

    def clear(self):
        """Clear all data"""
        self.waveform_display.clear()
        self.info_label.setText("No loops detected")
