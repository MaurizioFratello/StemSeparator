"""
Time Stretch Widget - Dedicated interface for time-stretching preview and export

PURPOSE: Provide a spacious interface for testing time-stretching functionality
CONTEXT: Standalone tab in sidebar for easier testing and development
"""

from pathlib import Path
from typing import Dict
import numpy as np
import soundfile as sf

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QComboBox,
    QProgressBar,
    QFrame,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, Slot

from ui.app_context import AppContext
from ui.theme import ThemeManager
from core.time_stretcher import calculate_stretch_factor, get_stretch_factor_description
from core.background_stretch_manager import BackgroundStretchManager, get_optimal_worker_count


class TimeStretchWidget(QWidget):
    """
    Dedicated widget for time-stretching testing.

    Features:
    - BPM configuration (original + target)
    - Background processing with progress
    - Loop preview controls
    - Playback testing
    """

    def __init__(self, player_widget=None, parent=None):
        """Initialize time stretch widget."""
        super().__init__(parent)
        self.ctx = AppContext()
        self.player_widget = player_widget

        # State
        self.original_bpm = 104
        self.target_bpm = 120
        self.current_preview_stem = 'drums'
        self.current_preview_loop = 0
        self.preview_show_stretched = False

        # Time-stretching components
        self.stretch_manager = BackgroundStretchManager(max_workers=get_optimal_worker_count())

        self._setup_ui()
        self._connect_signals()

        self.ctx.logger().info("TimeStretchWidget initialized")

    def set_player_widget(self, player_widget):
        """Set player widget reference."""
        self.player_widget = player_widget

    def _create_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled card frame with header."""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel(title)
        header.setObjectName("card_header")
        layout.addWidget(header)

        return card, layout

    def _setup_ui(self):
        """Setup widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Time-Stretching Test Interface")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; padding: 10px;")
        main_layout.addWidget(title)

        # === BPM Configuration Card ===
        bpm_card, bpm_layout = self._create_card("BPM Configuration")

        # Original BPM
        original_row = QHBoxLayout()
        original_row.setSpacing(15)

        original_label = QLabel("Original BPM:")
        original_label.setMinimumWidth(120)
        original_row.addWidget(original_label)

        self.original_bpm_spin = QSpinBox()
        self.original_bpm_spin.setMinimum(1)
        self.original_bpm_spin.setMaximum(999)
        self.original_bpm_spin.setValue(104)
        self.original_bpm_spin.setSuffix(" BPM")
        self.original_bpm_spin.setMinimumHeight(40)
        self.original_bpm_spin.setMinimumWidth(150)
        original_row.addWidget(self.original_bpm_spin)

        original_row.addStretch()
        bpm_layout.addLayout(original_row)

        # Target BPM
        target_row = QHBoxLayout()
        target_row.setSpacing(15)

        target_label = QLabel("Target BPM:")
        target_label.setMinimumWidth(120)
        target_row.addWidget(target_label)

        self.target_bpm_spin = QSpinBox()
        self.target_bpm_spin.setMinimum(1)
        self.target_bpm_spin.setMaximum(999)
        self.target_bpm_spin.setValue(120)
        self.target_bpm_spin.setSuffix(" BPM")
        self.target_bpm_spin.setMinimumHeight(40)
        self.target_bpm_spin.setMinimumWidth(150)
        target_row.addWidget(self.target_bpm_spin)

        # Stretch factor display
        self.stretch_factor_label = QLabel("↑ +15.4% faster (1.15x)")
        self.stretch_factor_label.setStyleSheet(
            "color: #10b981; font-size: 12pt; font-weight: bold; padding: 5px;"
        )
        target_row.addWidget(self.stretch_factor_label)

        target_row.addStretch()
        bpm_layout.addLayout(target_row)

        # Start processing button
        self.start_processing_btn = QPushButton("🚀 Start Background Processing")
        self.start_processing_btn.setMinimumHeight(45)
        ThemeManager.set_widget_property(self.start_processing_btn, "buttonStyle", "primary")
        bpm_layout.addWidget(self.start_processing_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Ready")
        self.progress_bar.setMinimumHeight(30)
        bpm_layout.addWidget(self.progress_bar)

        # Progress info label
        self.progress_info_label = QLabel(
            "💡 Background processing will stretch all loops in parallel. Drums are processed first."
        )
        self.progress_info_label.setWordWrap(True)
        self.progress_info_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.6); font-size: 11pt; padding: 5px;"
        )
        bpm_layout.addWidget(self.progress_info_label)

        main_layout.addWidget(bpm_card)

        # === Preview Controls Card ===
        preview_card, preview_layout = self._create_card("Preview Controls")

        # Stem selection
        stem_row = QHBoxLayout()
        stem_row.setSpacing(15)

        stem_label = QLabel("Stem:")
        stem_label.setMinimumWidth(80)
        stem_row.addWidget(stem_label)

        self.preview_stem_combo = QComboBox()
        self.preview_stem_combo.addItems(["Drums", "Vocals", "Bass", "Other"])
        self.preview_stem_combo.setCurrentIndex(0)
        self.preview_stem_combo.setMinimumHeight(35)
        self.preview_stem_combo.setMinimumWidth(150)
        stem_row.addWidget(self.preview_stem_combo)

        stem_row.addStretch()
        preview_layout.addLayout(stem_row)

        # Loop navigation
        loop_row = QHBoxLayout()
        loop_row.setSpacing(15)

        loop_label = QLabel("Loop:")
        loop_label.setMinimumWidth(80)
        loop_row.addWidget(loop_label)

        self.preview_loop_prev_btn = QPushButton("◀")
        self.preview_loop_prev_btn.setMinimumSize(35, 35)
        self.preview_loop_prev_btn.setMaximumSize(35, 35)
        loop_row.addWidget(self.preview_loop_prev_btn)

        self.preview_loop_label = QLabel("Loop 1 / 0")
        self.preview_loop_label.setMinimumWidth(100)
        self.preview_loop_label.setAlignment(Qt.AlignCenter)
        self.preview_loop_label.setStyleSheet("font-size: 11pt;")
        loop_row.addWidget(self.preview_loop_label)

        self.preview_loop_next_btn = QPushButton("▶")
        self.preview_loop_next_btn.setMinimumSize(35, 35)
        self.preview_loop_next_btn.setMaximumSize(35, 35)
        loop_row.addWidget(self.preview_loop_next_btn)

        loop_row.addStretch()
        preview_layout.addLayout(loop_row)

        # Version toggle
        version_row = QHBoxLayout()
        version_row.setSpacing(15)

        self.preview_toggle_btn = QPushButton("🎵 Original")
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(False)
        self.preview_toggle_btn.setMinimumHeight(40)
        self.preview_toggle_btn.setMinimumWidth(180)
        ThemeManager.set_widget_property(self.preview_toggle_btn, "buttonStyle", "secondary")
        version_row.addWidget(self.preview_toggle_btn)

        self.preview_play_btn = QPushButton("▶️ Play Preview")
        self.preview_play_btn.setMinimumHeight(40)
        self.preview_play_btn.setMinimumWidth(180)
        ThemeManager.set_widget_property(self.preview_play_btn, "buttonStyle", "primary")
        version_row.addWidget(self.preview_play_btn)

        version_row.addStretch()
        preview_layout.addLayout(version_row)

        # Preview status
        self.preview_status_label = QLabel("Select a loop and click Play to preview")
        self.preview_status_label.setWordWrap(True)
        self.preview_status_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.7); font-size: 11pt; padding: 10px; "
            "background: rgba(255, 255, 255, 0.05); border-radius: 6px;"
        )
        self.preview_status_label.setMinimumHeight(60)
        preview_layout.addWidget(self.preview_status_label)

        main_layout.addWidget(preview_card)

        main_layout.addStretch()
        
        # Initialize loop label with current state
        self._update_preview_loop_label()

    def _connect_signals(self):
        """Connect UI signals."""
        self.original_bpm_spin.valueChanged.connect(self._on_bpm_changed)
        self.target_bpm_spin.valueChanged.connect(self._on_bpm_changed)
        self.start_processing_btn.clicked.connect(self._on_start_processing)

        # Preview controls
        self.preview_stem_combo.currentIndexChanged.connect(self._on_preview_stem_changed)
        self.preview_loop_prev_btn.clicked.connect(self._on_preview_loop_prev)
        self.preview_loop_next_btn.clicked.connect(self._on_preview_loop_next)
        self.preview_toggle_btn.toggled.connect(self._on_preview_toggle_changed)
        self.preview_play_btn.clicked.connect(self._on_preview_play_clicked)

        # Background stretch manager signals
        self.stretch_manager.progress_updated.connect(self._on_stretch_progress_updated)
        self.stretch_manager.all_completed.connect(self._on_stretch_all_completed)

    @Slot()
    def _on_bpm_changed(self):
        """Handle BPM value changes."""
        original = self.original_bpm_spin.value()
        target = self.target_bpm_spin.value()

        if abs(original - target) < 0.1:
            self.stretch_factor_label.setText("No change (1.00x)")
            self.stretch_factor_label.setStyleSheet(
                "color: rgba(255, 255, 255, 0.7); font-size: 12pt; padding: 5px;"
            )
        else:
            stretch_factor = calculate_stretch_factor(original, target)
            description = get_stretch_factor_description(stretch_factor)
            self.stretch_factor_label.setText(f"{description} ({stretch_factor:.2f}x)")

            # Color based on direction
            color = "#10b981" if stretch_factor > 1.0 else "#3b82f6"
            self.stretch_factor_label.setStyleSheet(
                f"color: {color}; font-size: 12pt; font-weight: bold; padding: 5px;"
            )

    @Slot()
    def _on_start_processing(self):
        """Handle start processing button click."""
        if not self.player_widget or not hasattr(self.player_widget, 'stem_files'):
            self.progress_info_label.setText("❌ No stems loaded. Please load stems first.")
            return

        original_bpm = self.original_bpm_spin.value()
        target_bpm = self.target_bpm_spin.value()

        if abs(original_bpm - target_bpm) < 0.1:
            self.progress_info_label.setText("❌ Original and Target BPM are the same. No processing needed.")
            return

        # Get stem files
        stem_files = self._get_stem_files_dict()
        if not stem_files:
            self.progress_info_label.setText("❌ No stem files available.")
            return

        # Get loop segments
        loop_segments = self._get_loop_segments()
        if not loop_segments:
            self.progress_info_label.setText("❌ No loop segments available.")
            return

        # Start processing
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Starting...")

        self.progress_info_label.setText(
            f"🎵 Processing {len(stem_files)} stems × {len(loop_segments)} loops ({original_bpm} → {target_bpm} BPM)..."
        )

        self.stretch_manager.start_batch(
            stem_files=stem_files,
            loop_segments=loop_segments,
            original_bpm=original_bpm,
            target_bpm=target_bpm,
            sample_rate=44100
        )

        self.ctx.logger().info(f"Started time-stretching: {original_bpm} → {target_bpm} BPM")

    def _get_stem_files_dict(self) -> Dict[str, Path]:
        """Get stem files from player widget."""
        if not self.player_widget or not hasattr(self.player_widget, 'stem_files'):
            return {}

        stem_files = {}
        for stem_name, stem_path in self.player_widget.stem_files.items():
            if stem_path and Path(stem_path).exists():
                # Convert to lowercase for consistency with preview stem names
                stem_files[stem_name.lower()] = Path(stem_path)

        return stem_files

    def _get_loop_segments(self):
        """Get loop segments from player widget.

        Uses pre-calculated loop segments from Loop Preview tab, which already
        account for:
        - Song start marker position
        - Bars per loop setting (4, 8, 16 bars)
        - Intro handling (pad/skip)
        """
        # PRIMARY: Use pre-calculated loop segments from Loop Preview
        # These already incorporate song start marker and bars per loop settings
        if self.player_widget and hasattr(self.player_widget, 'detected_loop_segments'):
            loop_segments = self.player_widget.detected_loop_segments
            if loop_segments and len(loop_segments) > 0:
                self.ctx.logger().debug(
                    f"Using {len(loop_segments)} loop segments from Loop Preview "
                    f"(bars per loop: {getattr(self.player_widget, '_bars_per_loop', 4)})"
                )
                return loop_segments

        # FALLBACK 1: Calculate from downbeats (if loop detection was run but segments not set)
        if self.player_widget and hasattr(self.player_widget, 'detected_downbeat_times'):
            downbeats = self.player_widget.detected_downbeat_times
            bars_per_loop = getattr(self.player_widget, '_bars_per_loop', 4)

            if downbeats is not None and len(downbeats) > 0:
                segments = []
                num_downbeats_per_loop = bars_per_loop

                for i in range(0, len(downbeats) - num_downbeats_per_loop, num_downbeats_per_loop):
                    start = downbeats[i]
                    end = downbeats[i + num_downbeats_per_loop]
                    segments.append((start, end))

                if segments:
                    self.ctx.logger().warning(
                        "Using downbeats for loop segments (song start marker NOT applied)"
                    )
                    return segments

        # FALLBACK 2: Generate dummy loops based on audio duration
        if self.player_widget and hasattr(self.player_widget, 'player'):
            audio_duration = self.player_widget.player.get_duration()
            loop_duration = 10.0  # 10 second loops
            num_loops = max(1, int(audio_duration / loop_duration))

            segments = []
            for i in range(num_loops):
                start = i * loop_duration
                end = min((i + 1) * loop_duration, audio_duration)
                segments.append((start, end))

            self.ctx.logger().warning(
                f"Using {num_loops} dummy loop segments (no loop detection available)"
            )
            return segments

        return []

    @Slot(int, int)
    def _on_stretch_progress_updated(self, completed: int, total: int):
        """Handle progress update."""
        if total > 0:
            percentage = int((completed / total) * 100)
            self.progress_bar.setValue(percentage)
            self.progress_bar.setFormat(f"{completed} / {total} loops ({percentage}%)")

    @Slot()
    def _on_stretch_all_completed(self):
        """Handle completion of all stretching."""
        self.progress_info_label.setText("✅ All loops processed! Preview and export are ready.")
        self.progress_info_label.setStyleSheet(
            "color: #10b981; font-size: 11pt; padding: 5px;"
        )
        self.ctx.logger().info("Time-stretching completed")

    @Slot(int)
    def _on_preview_stem_changed(self, index: int):
        """Handle stem selection change."""
        stems = ['drums', 'vocals', 'bass', 'other']
        if 0 <= index < len(stems):
            self.current_preview_stem = stems[index]

    @Slot()
    def _on_preview_loop_prev(self):
        """Navigate to previous loop."""
        loop_segments = self._get_loop_segments()
        if loop_segments and len(loop_segments) > 0 and self.current_preview_loop > 0:
            self.current_preview_loop -= 1
            self._update_preview_loop_label()

    @Slot()
    def _on_preview_loop_next(self):
        """Navigate to next loop."""
        loop_segments = self._get_loop_segments()
        max_loops = len(loop_segments) - 1 if loop_segments else 0
        if self.current_preview_loop < max_loops:
            self.current_preview_loop += 1
            self._update_preview_loop_label()

    def _update_preview_loop_label(self):
        """Update loop navigation label."""
        loop_segments = self._get_loop_segments()
        total_loops = len(loop_segments) if loop_segments else 0
        
        # Clamp current loop index to valid range
        if total_loops > 0:
            self.current_preview_loop = max(0, min(self.current_preview_loop, total_loops - 1))
            self.preview_loop_label.setText(f"Loop {self.current_preview_loop + 1} / {total_loops}")
        else:
            self.current_preview_loop = 0
            self.preview_loop_label.setText("No loops")

    @Slot(bool)
    def _on_preview_toggle_changed(self, checked: bool):
        """Handle version toggle."""
        self.preview_show_stretched = checked

        if checked:
            self.preview_toggle_btn.setText("⚡ Stretched")
        else:
            self.preview_toggle_btn.setText("🎵 Original")

    @Slot()
    def _on_preview_play_clicked(self):
        """Handle preview play button click."""
        if not self.player_widget:
            self.preview_status_label.setText("❌ Player not available")
            return

        try:
            if self.preview_show_stretched:
                # Get stretched audio from cache
                target_bpm = self.target_bpm_spin.value()
                audio_data = self.stretch_manager.get_stretched_loop(
                    self.current_preview_stem,
                    self.current_preview_loop,
                    target_bpm
                )

                if audio_data is None:
                    self.preview_status_label.setText("❌ Stretched loop not available. Start processing first.")
                    return
            else:
                # Load original audio from stem file
                stem_files_dict = self._get_stem_files_dict()
                stem_path = stem_files_dict.get(self.current_preview_stem)

                if not stem_path or not stem_path.exists():
                    self.preview_status_label.setText(f"❌ Stem file not found: {self.current_preview_stem}")
                    return

                loop_segments = self._get_loop_segments()
                if self.current_preview_loop >= len(loop_segments):
                    self.preview_status_label.setText("❌ Loop index out of range")
                    return

                start_sec, end_sec = loop_segments[self.current_preview_loop]
                audio_full, sr = sf.read(str(stem_path), always_2d=False)

                start_sample = int(start_sec * sr)
                end_sample = int(end_sec * sr)
                start_sample = max(0, min(start_sample, len(audio_full)))
                end_sample = max(start_sample, min(end_sample, len(audio_full)))

                audio_data = audio_full[start_sample:end_sample]

            # Ensure stereo
            if audio_data.ndim == 1:
                audio_data = np.stack([audio_data, audio_data], axis=1)

            # Play via sounddevice
            import sounddevice as sd
            sd.play(audio_data, samplerate=44100, blocking=False)

            self.preview_status_label.setText(
                f"▶️ Playing {self.current_preview_stem.title()} Loop {self.current_preview_loop + 1} "
                f"({'Stretched' if self.preview_show_stretched else 'Original'})"
            )

            self.ctx.logger().info(
                f"Preview playback: {self.current_preview_stem} loop {self.current_preview_loop} "
                f"({'stretched' if self.preview_show_stretched else 'original'})"
            )

        except Exception as e:
            self.ctx.logger().error(f"Preview playback error: {e}", exc_info=True)
            self.preview_status_label.setText(f"❌ Playback error: {str(e)}")

    def refresh(self):
        """Refresh widget (called when navigating to this page).
        
        Updates loop label and clamps loop index to valid range based on
        current loop segments from Loop Preview tab.
        """
        self._update_preview_loop_label()
