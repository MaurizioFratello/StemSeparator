"""
Waveform Widget - Audio visualization with trim controls

PURPOSE: Display audio waveform with draggable trim markers for start/end positions.
CONTEXT: Used in Upload tab to allow users to trim audio before stem separation.
"""
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import soundfile as sf

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QLinearGradient, QPixmap

from ui.app_context import AppContext
from ui.theme import ColorPalette


class WaveformDisplay(QWidget):
    """
    Custom widget for rendering audio waveform with performance optimizations

    WHY: Provides visual feedback of audio content and trim regions
    PERFORMANCE: Uses QPixmap caching to avoid expensive redraws
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.waveform_data: Optional[np.ndarray] = None
        self.duration: float = 0.0
        self.trim_start: float = 0.0  # in seconds
        self.trim_end: float = 0.0    # in seconds (0 means end of file)
        self.setMinimumHeight(120)
        self.setMaximumHeight(200)

        # Performance: Cache waveform rendering
        self._waveform_cache: Optional[QPixmap] = None
        self._cache_size: tuple = (0, 0)

    def set_audio_data(self, audio_data: np.ndarray, sample_rate: int):
        """
        Load audio data for visualization

        Args:
            audio_data: numpy array of shape (frames, channels) or (frames,)
            sample_rate: sample rate in Hz
        """
        # Convert to mono if stereo
        if audio_data.ndim == 2:
            audio_data = np.mean(audio_data, axis=1)

        self.waveform_data = audio_data
        self.duration = len(audio_data) / sample_rate
        self.trim_start = 0.0
        self.trim_end = self.duration

        # Invalidate cache
        self._waveform_cache = None
        self.update()

    def set_trim_range(self, start_sec: float, end_sec: float):
        """Update trim marker positions"""
        self.trim_start = start_sec
        self.trim_end = end_sec
        self.update()

    def clear(self):
        """Clear waveform data"""
        self.waveform_data = None
        self.duration = 0.0
        self.trim_start = 0.0
        self.trim_end = 0.0
        self._waveform_cache = None
        self.update()

    def resizeEvent(self, event):
        """Invalidate cache on resize"""
        self._waveform_cache = None
        super().resizeEvent(event)

    def paintEvent(self, event):
        """Render waveform with trim markers and modern styling (optimized with caching)"""
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        # Modern gradient background
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor(ColorPalette.WAVEFORM_BACKGROUND))
        gradient.setColorAt(1, QColor("#0f0f0f"))
        painter.fillRect(self.rect(), gradient)

        if self.waveform_data is None or len(self.waveform_data) == 0:
            # Show placeholder text with modern styling
            painter.setPen(QColor(ColorPalette.TEXT_SECONDARY))
            painter.drawText(self.rect(), Qt.AlignCenter, "Select a file to view waveform")
            return

        # Use cached waveform if available and size hasn't changed
        if self._waveform_cache is None or self._cache_size != (width, height):
            self._render_waveform_to_cache()

        # Draw cached waveform
        if self._waveform_cache:
            painter.drawPixmap(0, 0, self._waveform_cache)

        # Draw dynamic overlays (not cached to allow smooth updates)
        center_y = height / 2

        # Draw trimmed-out regions with modern overlay
        if self.trim_start > 0 or self.trim_end < self.duration:
            overlay_color = QColor(ColorPalette.BACKGROUND_TERTIARY)
            overlay_color.setAlpha(200)

            if self.trim_start > 0:
                painter.fillRect(
                    0, 0,
                    int(width * (self.trim_start / self.duration)), height,
                    overlay_color
                )
            if self.trim_end < self.duration:
                painter.fillRect(
                    int(width * (self.trim_end / self.duration)), 0,
                    width, height,
                    overlay_color
                )

        # Draw trim markers with modern accent colors
        trim_start_x = int(width * (self.trim_start / self.duration))
        trim_end_x = int(width * (self.trim_end / self.duration))

        marker_pen = QPen(QColor(ColorPalette.ACCENT_PRIMARY), 3)
        painter.setPen(marker_pen)
        painter.drawLine(trim_start_x, 0, trim_start_x, height)
        painter.drawLine(trim_end_x, 0, trim_end_x, height)

        # Draw trim marker labels
        painter.setPen(QColor(ColorPalette.TEXT_PRIMARY))
        if self.trim_start > 0:
            painter.drawText(trim_start_x + 5, 20, f"{self.trim_start:.1f}s")
        if self.trim_end < self.duration:
            painter.drawText(trim_end_x + 5, 20, f"{self.trim_end:.1f}s")

    def _render_waveform_to_cache(self):
        """Render waveform to cached pixmap (performance optimization)"""
        width = self.width()
        height = self.height()

        if width <= 0 or height <= 0:
            return

        # Create pixmap for caching
        self._waveform_cache = QPixmap(width, height)
        self._waveform_cache.fill(Qt.transparent)
        self._cache_size = (width, height)

        painter = QPainter(self._waveform_cache)
        # Disable antialiasing for better performance
        # painter.setRenderHint(QPainter.Antialiasing, False)

        center_y = height / 2

        # Downsample waveform for display
        samples_per_pixel = max(1, len(self.waveform_data) // width)

        # Draw waveform using lines (faster than path)
        waveform_pen = QPen(QColor(ColorPalette.WAVEFORM_PRIMARY), 1)
        painter.setPen(waveform_pen)

        for x in range(width):
            # Get chunk of samples for this pixel
            start_idx = int(x * samples_per_pixel)
            end_idx = min(start_idx + samples_per_pixel, len(self.waveform_data))

            if start_idx >= len(self.waveform_data):
                break

            # Get max/min for this chunk (for envelope)
            chunk = self.waveform_data[start_idx:end_idx]
            max_val = np.max(chunk)
            min_val = np.min(chunk)

            # Scale to widget height (with padding)
            max_y = center_y - (max_val * center_y * 0.9)
            min_y = center_y - (min_val * center_y * 0.9)

            # Draw vertical line from min to max (direct line, no path)
            painter.drawLine(x, int(max_y), x, int(min_y))

        # Draw center line with modern color
        painter.setPen(QPen(QColor(ColorPalette.BORDER_DEFAULT), 1))
        painter.drawLine(0, int(center_y), width, int(center_y))

        painter.end()


class WaveformWidget(QWidget):
    """
    Waveform visualization with trim controls

    Features:
    - Visual waveform display
    - Start/end trim sliders
    - Time display for trim positions
    - Signal emission when trim changes
    """

    # Signal: (start_seconds, end_seconds)
    trim_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()
        self.current_file: Optional[Path] = None
        self.audio_data: Optional[np.ndarray] = None
        self.sample_rate: int = 0
        self.duration: float = 0.0

        self._setup_ui()
        self._connect_signals()

        # Start hidden
        self.setVisible(False)

    def _setup_ui(self):
        """Setup widget layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box
        group = QGroupBox("Audio Trim")
        group_layout = QVBoxLayout()

        # Waveform display
        self.waveform_display = WaveformDisplay()
        group_layout.addWidget(self.waveform_display)
        
        # Add spacing between waveform and controls
        group_layout.addSpacing(15)

        # Trim controls
        controls_layout = QVBoxLayout()

        # Start trim
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start:"))
        self.start_slider = QSlider(Qt.Horizontal)
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(1000)  # Will be scaled to duration
        self.start_slider.setValue(0)
        start_layout.addWidget(self.start_slider, stretch=1)
        self.start_time_label = QLabel("0:00.0")
        self.start_time_label.setMinimumWidth(60)
        start_layout.addWidget(self.start_time_label)
        controls_layout.addLayout(start_layout)

        # End trim
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End:"))
        self.end_slider = QSlider(Qt.Horizontal)
        self.end_slider.setMinimum(0)
        self.end_slider.setMaximum(1000)
        self.end_slider.setValue(1000)
        end_layout.addWidget(self.end_slider, stretch=1)
        self.end_time_label = QLabel("0:00.0")
        self.end_time_label.setMinimumWidth(60)
        end_layout.addWidget(self.end_time_label)
        controls_layout.addLayout(end_layout)

        group_layout.addLayout(controls_layout)

        # Info label
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #888; font-size: 10pt;")
        group_layout.addWidget(self.info_label)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _connect_signals(self):
        """Connect slider signals"""
        self.start_slider.valueChanged.connect(self._on_start_changed)
        self.end_slider.valueChanged.connect(self._on_end_changed)

    def load_file(self, file_path: Path):
        """
        Load audio file for trimming

        Args:
            file_path: Path to audio file
        """
        try:
            self.ctx.logger().info(f"Loading waveform for: {file_path.name}")

            # Read audio file
            audio_data, sample_rate = sf.read(file_path, dtype='float32')

            self.current_file = file_path
            self.audio_data = audio_data
            self.sample_rate = sample_rate
            # Calculate duration in seconds (len gives frames for both mono and stereo)
            self.duration = len(audio_data) / sample_rate

            # Update waveform display
            self.waveform_display.set_audio_data(audio_data, sample_rate)

            # Reset sliders
            self.start_slider.setValue(0)
            self.end_slider.setValue(1000)

            # Update labels
            self._update_time_labels()
            self._update_info()

            self.setVisible(True)

        except Exception as e:
            self.ctx.logger().error(f"Failed to load waveform: {e}", exc_info=True)
            self.clear()

    def clear(self):
        """Clear waveform and hide widget"""
        self.current_file = None
        self.audio_data = None
        self.sample_rate = 0
        self.duration = 0.0
        self.waveform_display.clear()
        self.setVisible(False)

    def get_trim_range(self) -> Tuple[float, float]:
        """
        Get current trim range in seconds

        Returns:
            (start_seconds, end_seconds)
        """
        start_sec = (self.start_slider.value() / 1000.0) * self.duration
        end_sec = (self.end_slider.value() / 1000.0) * self.duration
        return start_sec, end_sec

    def _on_start_changed(self, value: int):
        """Handle start slider change"""
        # Ensure start doesn't exceed end
        if value > self.end_slider.value():
            self.start_slider.setValue(self.end_slider.value())
            return

        self._update_time_labels()
        self._update_waveform_markers()
        self._update_info()

        start_sec, end_sec = self.get_trim_range()
        self.trim_changed.emit(start_sec, end_sec)

    def _on_end_changed(self, value: int):
        """Handle end slider change"""
        # Ensure end doesn't go below start
        if value < self.start_slider.value():
            self.end_slider.setValue(self.start_slider.value())
            return

        self._update_time_labels()
        self._update_waveform_markers()
        self._update_info()

        start_sec, end_sec = self.get_trim_range()
        self.trim_changed.emit(start_sec, end_sec)

    def _update_time_labels(self):
        """Update time display labels"""
        start_sec, end_sec = self.get_trim_range()

        self.start_time_label.setText(self._format_time(start_sec))
        self.end_time_label.setText(self._format_time(end_sec))

    def _update_waveform_markers(self):
        """Update trim markers in waveform display"""
        start_sec, end_sec = self.get_trim_range()
        self.waveform_display.set_trim_range(start_sec, end_sec)

    def _update_info(self):
        """Update info label with trim statistics"""
        start_sec, end_sec = self.get_trim_range()
        trimmed_duration = end_sec - start_sec

        if trimmed_duration < self.duration:
            removed_sec = self.duration - trimmed_duration
            percent_kept = (trimmed_duration / self.duration) * 100
            self.info_label.setText(
                f"Trimmed duration: {self._format_time(trimmed_duration)} "
                f"({percent_kept:.1f}% of original, {self._format_time(removed_sec)} removed)"
            )
        else:
            self.info_label.setText("No trimming applied")

    def _format_time(self, seconds: float) -> str:
        """
        Format seconds as M:SS.s

        Args:
            seconds: Time in seconds

        Returns:
            Formatted string like "3:45.2"
        """
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:04.1f}"
