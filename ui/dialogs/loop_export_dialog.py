"""
Loop Export Dialog - Configure sampler loop export settings

PURPOSE: Allow users to configure BPM-based loop export for samplers
CONTEXT: Used when exporting audio from Player as musical loops (2/4/8 bars)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, NamedTuple
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QComboBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QFrame,
    QMessageBox,
    QApplication,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QRunnable, QThreadPool, QObject

from utils.loop_math import get_minimum_bpm, is_valid_for_sampler


class LoopExportSettings(NamedTuple):
    """Loop export settings data"""

    bpm: int  # Beats per minute (integer)
    bars: int  # Number of bars (2, 4, or 8)
    sample_rate: int  # Target sample rate (44100 or 48000)
    bit_depth: int  # Bit depth (16, 24, or 32)
    channels: int  # Channels (1=mono, 2=stereo)
    file_format: str  # File format ('WAV', 'AIFF', or 'FLAC')
    export_mode: str  # Export mode ('mixed' or 'individual')


class BPMDetectionWorker(QRunnable):
    """
    Background worker for BPM detection.

    PURPOSE: Detect BPM without blocking GUI thread
    CONTEXT: BPM detection uses DeepRhythm (fast, 95%+ accurate) or librosa fallback
    """

    class Signals(QObject):
        finished = Signal(
            float, str, str, float
        )  # detected_bpm, message, source_description, confidence
        error = Signal(str)  # error_message

    def __init__(self, audio_path: Path, source_description: str, logger):
        super().__init__()
        self.audio_path = audio_path
        self.source_description = source_description
        self.logger = logger
        self.signals = self.Signals()

    def run(self):
        """Execute BPM detection in background"""
        try:
            from core.sampler_export import detect_audio_bpm

            detected_bpm, bpm_message, confidence = detect_audio_bpm(self.audio_path)

            self.logger.info(
                f"BPM detection: {detected_bpm:.1f} BPM from {self.source_description} - {bpm_message}"
            )

            # Emit confidence (use 0.0 if None for signal compatibility)
            confidence_value = confidence if confidence is not None else 0.0
            self.signals.finished.emit(
                detected_bpm, bpm_message, self.source_description, confidence_value
            )

        except Exception as e:
            self.logger.error(f"BPM detection error: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class LoopExportDialog(QDialog):
    """
    Dialog for configuring sampler loop export settings.

    Features:
    - BPM input with auto-detection suggestion
    - Bar length selection (2, 4, or 8 bars)
    - Sample rate selection (44.1kHz or 48kHz)
    - Bit depth selection (16, 24, or 32 bit)
    - Channel configuration (stereo or mono)
    - File format selection (WAV, AIFF, FLAC)
    - Real-time validation of BPM+bars against 20s sampler limit
    - Preview of chunk duration and file count estimate
    """

    def __init__(
        self,
        player_widget=None,
        duration_seconds: float = 0.0,
        num_stems: int = 1,
        preset_bpm: Optional[float] = None,
        preset_bars: Optional[int] = None,
        parent=None,
    ):
        """
        Initialize loop export dialog.

        Args:
            player_widget: Reference to PlayerWidget for BPM detection (optional)
            duration_seconds: Total duration of audio in seconds (for preview)
            num_stems: Number of loaded stems (for individual export preview)
            preset_bpm: Pre-detected BPM from Loop Preview (skips BPM detection)
            preset_bars: Pre-selected bars per loop from Loop Preview
            parent: Parent widget
        """
        super().__init__(parent)
        self.player_widget = player_widget
        self.duration_seconds = duration_seconds
        self.num_stems = num_stems
        self.preset_bpm = preset_bpm
        self.preset_bars = preset_bars
        self.detected_bpm = (
            int(preset_bpm) if preset_bpm else 120
        )  # Use preset or default
        self.temp_bpm_file = None  # Track temp file for cleanup
        self.thread_pool = QThreadPool()

        self.setWindowTitle("Sampler Loop Export")
        self.setModal(True)

        # Set dimensions to use screen height minus 10%
        # WHY: Configure dialog to use 90% of screen height for better field visibility
        # while leaving small margin for system UI elements
        screen = QApplication.primaryScreen().availableGeometry()
        screen_height = screen.height()
        default_width = 780  # Keep current width
        default_height = int(screen_height * 0.9)  # Screen height minus 10%

        self.setMinimumWidth(default_width)
        self.setMinimumHeight(default_height)
        self.resize(
            default_width, default_height
        )  # Set default size to full screen height

        self._setup_ui()
        self._connect_signals()
        self._update_validation()
        self._update_preview()

    def _create_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled card frame with header (matching main app design)"""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel(title)
        header.setObjectName("card_header")
        header.setFixedHeight(30)
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(header)

        return card, layout

    def _setup_ui(self):
        """
        Setup dialog UI with horizontal layout for compact arrangement.

        WHY: Reduces window height by arranging elements horizontally:
        - Row 1: BPM + Loop Length (side by side)
        - Row 2: Export Mode + Audio Format (side by side)
        """
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Row 1: BPM + Loop Length ===
        row1_card, row1_layout = self._create_card("Tempo & Loop Length")

        # Show Loop Preview preset info if available
        if self.preset_bpm is not None or self.preset_bars is not None:
            preset_info = QLabel()
            preset_parts = []
            if self.preset_bpm:
                preset_parts.append(f"{self.preset_bpm:.1f} BPM")
            if self.preset_bars:
                preset_parts.append(f"{self.preset_bars} bars")
            preset_info.setText(
                f"✓ Using Loop Preview settings: {', '.join(preset_parts)}"
            )
            preset_info.setStyleSheet(
                "color: #10b981; font-size: 11pt; padding: 8px; "
                "background: rgba(16, 185, 129, 0.1); border-radius: 6px;"
            )
            row1_layout.addWidget(preset_info)

        row1_horizontal = QHBoxLayout()
        row1_horizontal.setSpacing(30)

        # BPM Section (left side)
        bpm_container = QVBoxLayout()
        bpm_container.setSpacing(8)

        bpm_label_row = QHBoxLayout()
        bpm_label_row.setSpacing(10)
        bpm_label_text = QLabel("BPM:")
        bpm_label_text.setMinimumWidth(60)
        bpm_label_row.addWidget(bpm_label_text)

        self.bpm_spin = QSpinBox()
        self.bpm_spin.setMinimum(1)
        self.bpm_spin.setMaximum(999)
        self.bpm_spin.setValue(self.detected_bpm)
        self.bpm_spin.setSuffix(" BPM")
        self.bpm_spin.setMinimumHeight(35)
        self.bpm_spin.setMinimumWidth(150)
        bpm_label_row.addWidget(self.bpm_spin)

        # Detect BPM button - hide if preset is available
        self.detect_bpm_btn = QPushButton("🎵 Detect BPM")
        self.detect_bpm_btn.setMinimumHeight(35)
        self.detect_bpm_btn.setMinimumWidth(130)
        # Disable if no player_widget OR if preset BPM is already set
        self.detect_bpm_btn.setEnabled(
            self.player_widget is not None and self.preset_bpm is None
        )
        if self.preset_bpm is not None:
            self.detect_bpm_btn.setVisible(False)  # Hide button when preset is used
        bpm_label_row.addWidget(self.detect_bpm_btn)

        bpm_label_row.addStretch()
        bpm_container.addLayout(bpm_label_row)

        # BPM info label - show different message based on preset
        if self.preset_bpm is not None:
            self.bpm_info_label = QLabel("✓ BPM from Loop Preview (editable)")
            self.bpm_info_label.setStyleSheet("color: #10b981; font-size: 11pt;")
        else:
            self.bpm_info_label = QLabel(
                "💡 Click 'Detect BPM' for automatic detection"
            )
            self.bpm_info_label.setStyleSheet(
                "color: rgba(255, 255, 255, 0.6); font-size: 11pt;"
            )
        bpm_container.addWidget(self.bpm_info_label)

        # Progress bar (hidden by default)
        self.bpm_progress = QProgressBar()
        self.bpm_progress.setMinimum(0)
        self.bpm_progress.setMaximum(0)  # Indeterminate mode
        self.bpm_progress.setTextVisible(True)
        self.bpm_progress.setFormat("Analyzing audio...")
        self.bpm_progress.setMinimumHeight(8)
        self.bpm_progress.setMaximumHeight(8)
        self.bpm_progress.setVisible(False)
        bpm_container.addWidget(self.bpm_progress)

        row1_horizontal.addLayout(bpm_container)

        # Loop Length Section (right side)
        bars_container = QVBoxLayout()
        bars_container.setSpacing(8)

        bars_label_row = QHBoxLayout()
        bars_label_row.setSpacing(10)
        bars_label_text = QLabel("Loop Length:")
        bars_label_text.setMinimumWidth(80)
        bars_label_row.addWidget(bars_label_text)

        self.bars_combo = QComboBox()
        self.bars_combo.addItems(["2 Bar", "4 Bar", "8 Bar"])
        # Set index based on preset_bars or default to 4
        if self.preset_bars == 2:
            self.bars_combo.setCurrentIndex(0)
        elif self.preset_bars == 8:
            self.bars_combo.setCurrentIndex(2)
        else:
            self.bars_combo.setCurrentIndex(1)  # Default: 4 Bar
        self.bars_combo.setMinimumHeight(35)
        self.bars_combo.setMinimumWidth(120)
        bars_label_row.addWidget(self.bars_combo)
        bars_label_row.addStretch()
        bars_container.addLayout(bars_label_row)

        # Info label for bars - show different message based on preset
        if self.preset_bars is not None:
            bars_info = QLabel("✓ From Loop Preview")
            bars_info.setStyleSheet("color: #10b981; font-size: 11pt;")
        else:
            bars_info = QLabel()  # Empty placeholder
        bars_info.setFixedHeight(self.bpm_info_label.sizeHint().height())
        bars_container.addWidget(bars_info)

        row1_horizontal.addLayout(bars_container)
        row1_layout.addLayout(row1_horizontal)

        # Validation label (updated dynamically, spans full width)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("padding: 5px;")
        row1_layout.addWidget(self.validation_label)

        main_layout.addWidget(row1_card)

        # === Row 2: Export Mode + Audio Format ===
        row2_horizontal = QHBoxLayout()
        row2_horizontal.setSpacing(15)

        # Export Mode Card (left side)
        mode_card, mode_layout = self._create_card("Export Mode")

        self.mode_button_group = QButtonGroup(self)

        # Create vertical layout for radio buttons
        mode_options_col = QVBoxLayout()
        mode_options_col.setSpacing(10)

        self.mode_mixed = QRadioButton("Mixed Audio (all stems combined)")
        self.mode_mixed.setChecked(True)
        self.mode_button_group.addButton(self.mode_mixed)
        mode_options_col.addWidget(self.mode_mixed)

        self.mode_individual = QRadioButton(
            f"Individual Stems ({self.num_stems} separate sets)"
        )
        self.mode_button_group.addButton(self.mode_individual)
        mode_options_col.addWidget(self.mode_individual)

        mode_options_col.addStretch()
        mode_layout.addLayout(mode_options_col)

        row2_horizontal.addWidget(mode_card)

        # Audio Format Card (right side)
        format_card, format_layout = self._create_card("Audio Format")

        # Sample rate
        sr_row = QHBoxLayout()
        sr_label = QLabel("Sample Rate:")
        sr_label.setMinimumWidth(80)
        sr_row.addWidget(sr_label)

        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["44100 Hz", "48000 Hz"])
        self.sample_rate_combo.setCurrentIndex(0)  # Default: 44.1kHz
        self.sample_rate_combo.setMinimumHeight(35)
        sr_row.addWidget(self.sample_rate_combo)
        sr_row.addStretch()
        format_layout.addLayout(sr_row)

        # Bit depth
        depth_row = QHBoxLayout()
        depth_label = QLabel("Bit Depth:")
        depth_label.setMinimumWidth(80)
        depth_row.addWidget(depth_label)

        self.bit_depth_combo = QComboBox()
        self.bit_depth_combo.addItems(["16 bit", "24 bit", "32 bit"])
        self.bit_depth_combo.setCurrentIndex(1)  # Default: 24 bit
        self.bit_depth_combo.setMinimumHeight(35)
        depth_row.addWidget(self.bit_depth_combo)
        depth_row.addStretch()
        format_layout.addLayout(depth_row)

        # Channels
        channels_row = QHBoxLayout()
        channels_label = QLabel("Channels:")
        channels_label.setMinimumWidth(80)
        channels_row.addWidget(channels_label)

        self.channels_combo = QComboBox()
        self.channels_combo.addItems(["Stereo", "Mono"])
        self.channels_combo.setCurrentIndex(0)  # Default: Stereo
        self.channels_combo.setMinimumHeight(35)
        channels_row.addWidget(self.channels_combo)
        channels_row.addStretch()
        format_layout.addLayout(channels_row)

        # File format
        fmt_row = QHBoxLayout()
        fmt_label = QLabel("Format:")
        fmt_label.setMinimumWidth(80)
        fmt_row.addWidget(fmt_label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["WAV", "AIFF", "FLAC"])
        self.format_combo.setCurrentIndex(0)  # Default: WAV
        self.format_combo.setMinimumHeight(35)
        fmt_row.addWidget(self.format_combo)
        fmt_row.addStretch()
        format_layout.addLayout(fmt_row)

        row2_horizontal.addWidget(format_card)
        main_layout.addLayout(row2_horizontal)

        # === Preview ===
        preview_card, preview_layout = self._create_card("Preview")

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setStyleSheet(
            "padding: 5px; color: rgba(255, 255, 255, 0.9);"
        )
        preview_layout.addWidget(self.preview_label)

        main_layout.addWidget(preview_card)

        # Info note
        info_label = QLabel(
            "ℹ️ Chunks split at zero-crossings to prevent clicks. "
            "Export starts at sample 0 (no automatic grid alignment)."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        main_layout.addWidget(info_label)

        # Add stretch to push buttons to bottom
        main_layout.addStretch()

        # === Dialog Buttons ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(35)

        self.btn_export = QPushButton("Export Loops")
        self.btn_export.setMinimumWidth(120)
        self.btn_export.setMinimumHeight(35)
        self.btn_export.setDefault(True)

        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_export)

        main_layout.addLayout(buttons_layout)

    def _connect_signals(self):
        """Connect UI signals"""
        self.bpm_spin.valueChanged.connect(self._on_settings_changed)
        self.bars_combo.currentIndexChanged.connect(
            self._on_settings_changed
        )  # Changed from button group
        self.mode_button_group.buttonToggled.connect(self._on_settings_changed)
        self.sample_rate_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.bit_depth_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.channels_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.format_combo.currentIndexChanged.connect(self._on_settings_changed)

        self.detect_bpm_btn.clicked.connect(self._on_detect_bpm)

        self.btn_export.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_settings_changed(self):
        """Handle any settings change"""
        self._update_validation()
        self._update_preview()

    def _get_selected_bars(self) -> int:
        """
        Get currently selected bar count from ComboBox.

        WHY: Changed from radio buttons to ComboBox for compact horizontal layout.
        ComboBox index maps to bar values: 0=2 bars, 1=4 bars, 2=8 bars
        """
        index = self.bars_combo.currentIndex()
        bar_values = [2, 4, 8]
        return (
            bar_values[index] if 0 <= index < len(bar_values) else 4
        )  # Default to 4 bars

    def _update_validation(self):
        """Update BPM+bars validation display"""
        bpm = self.bpm_spin.value()
        bars = self._get_selected_bars()

        is_valid, error_msg = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        if is_valid:
            # Valid combination
            from utils.loop_math import compute_chunk_duration_seconds

            duration = compute_chunk_duration_seconds(bpm, bars)

            self.validation_label.setText(
                f"✓ Valid: {bars} bars at {bpm} BPM = {duration:.2f}s per chunk"
            )
            self.validation_label.setStyleSheet(
                "color: rgba(100, 255, 100, 0.9); padding: 5px;"
            )
            self.btn_export.setEnabled(True)

        else:
            # Invalid combination
            min_bpm = get_minimum_bpm(bars, max_seconds=20.0)

            self.validation_label.setText(
                f"⚠ {error_msg}\n" f"Minimum BPM for {bars} bars: {min_bpm}"
            )
            self.validation_label.setStyleSheet(
                "color: rgba(255, 100, 100, 0.9); padding: 5px;"
            )
            self.btn_export.setEnabled(False)

    def _update_preview(self):
        """Update export preview"""
        bpm = self.bpm_spin.value()
        bars = self._get_selected_bars()

        # Only show preview if combination is valid
        is_valid, _ = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        if not is_valid or self.duration_seconds == 0:
            self.preview_label.setText("Configure settings above to see preview")
            return

        from utils.loop_math import (
            compute_chunk_duration_seconds,
            compute_samples_per_chunk,
        )

        chunk_duration = compute_chunk_duration_seconds(bpm, bars)

        # Parse sample rate
        sr_text = self.sample_rate_combo.currentText()
        sample_rate = int(sr_text.split()[0])  # "44100 Hz" -> 44100

        samples_per_chunk = compute_samples_per_chunk(bpm, bars, sample_rate)

        # Estimate number of chunks
        if self.duration_seconds > 0:
            num_chunks = max(1, int(self.duration_seconds / chunk_duration))
            if self.duration_seconds % chunk_duration > chunk_duration * 0.1:
                # Account for remainder
                num_chunks += 1
        else:
            num_chunks = 1

        # File format info
        fmt = self.format_combo.currentText()
        bit_depth_text = self.bit_depth_combo.currentText()
        bit_depth = int(bit_depth_text.split()[0])
        channels_text = self.channels_combo.currentText()

        # Check export mode
        is_individual = self.mode_individual.isChecked()

        # Build preview text
        if is_individual:
            # Individual stems mode
            total_files = num_chunks * self.num_stems
            if num_chunks == 1:
                preview = (
                    f"Will export {self.num_stems} files (1 per stem):\n"
                    f"• Duration: ~{chunk_duration:.2f}s ({bars} bars)\n"
                    f"• Format: {fmt}, {bit_depth} bit, {channels_text}\n"
                    f"• Sample rate: {sr_text}\n"
                    f"• Files: drums_{bpm}_{bars}t.{fmt.lower()}, bass_{bpm}_{bars}t.{fmt.lower()}, ..."
                )
            else:
                preview = (
                    f"Will export {total_files} files ({self.num_stems} stems × {num_chunks} chunks):\n"
                    f"• ~{chunk_duration:.2f}s per chunk ({bars} bars)\n"
                    f"• Format: {fmt}, {bit_depth} bit, {channels_text}\n"
                    f"• Sample rate: {sr_text}\n"
                    f"• Files: drums_{bpm}_{bars}t_part01.{fmt.lower()}, ..., bass_{bpm}_{bars}t_part01.{fmt.lower()}, ..."
                )
        else:
            # Mixed audio mode
            if num_chunks == 1:
                preview = (
                    f"Will export 1 file:\n"
                    f"• Duration: ~{chunk_duration:.2f}s ({bars} bars)\n"
                    f"• Format: {fmt}, {bit_depth} bit, {channels_text}\n"
                    f"• Sample rate: {sr_text}"
                )
            else:
                preview = (
                    f"Will export {num_chunks} chunks:\n"
                    f"• ~{chunk_duration:.2f}s per chunk ({bars} bars)\n"
                    f"• Format: {fmt}, {bit_depth} bit, {channels_text}\n"
                    f"• Sample rate: {sr_text}\n"
                    f"• Files: MyLoop_{bpm}_{bars}t_part01.{fmt.lower()}, ..."
                )

        self.preview_label.setText(preview)

    def _on_detect_bpm(self):
        """Handle BPM detection button click"""
        if not self.player_widget:
            QMessageBox.warning(
                self,
                "Detection Unavailable",
                "BPM detection is not available in this context.",
            )
            return

        try:
            # Disable button and show progress
            self.detect_bpm_btn.setEnabled(False)
            self.bpm_progress.setVisible(True)
            self.bpm_info_label.setText("🔄 Detecting BPM from audio...")

            # Get audio source for BPM detection
            bpm_source_file, source_description = (
                self.player_widget._get_audio_for_bpm_detection()
            )

            # Track temp file for cleanup
            if "bpm_detect_" in str(bpm_source_file):
                self.temp_bpm_file = bpm_source_file

            # Get logger from player widget context
            logger = self.player_widget.ctx.logger()

            # Create and start worker
            worker = BPMDetectionWorker(bpm_source_file, source_description, logger)
            worker.signals.finished.connect(self._on_bpm_detected)
            worker.signals.error.connect(self._on_bpm_error)

            self.thread_pool.start(worker)

        except Exception as e:
            self._on_bpm_error(str(e))

    def _on_bpm_detected(
        self,
        detected_bpm: float,
        message: str,
        source_description: str,
        confidence: float,
    ):
        """Handle successful BPM detection"""
        # Update UI
        self.detected_bpm = round(detected_bpm)
        self.bpm_spin.setValue(self.detected_bpm)

        # Show confidence-based feedback
        if confidence > 0:
            # DeepRhythm with confidence score
            if confidence >= 0.9:
                confidence_icon = "✓"
                color_style = "color: rgba(100, 255, 100, 0.9);"
            elif confidence >= 0.7:
                confidence_icon = "⚠"
                color_style = "color: rgba(255, 200, 100, 0.9);"
            else:
                confidence_icon = "⚠"
                color_style = "color: rgba(255, 150, 100, 0.9);"

            self.bpm_info_label.setText(
                f"{confidence_icon} Detected: {self.detected_bpm} BPM from {source_description} ({confidence:.0%} confident)"
            )
            self.bpm_info_label.setStyleSheet(f"{color_style} font-size: 11pt;")
        else:
            # Librosa without confidence
            self.bpm_info_label.setText(
                f"✓ Detected: {self.detected_bpm} BPM from {source_description} (librosa)"
            )
            self.bpm_info_label.setStyleSheet(
                "color: rgba(255, 255, 255, 0.7); font-size: 11pt;"
            )

        self.bpm_progress.setVisible(False)
        self.detect_bpm_btn.setEnabled(True)

        # Update validation and preview
        self._update_validation()
        self._update_preview()

        # Cleanup temp file
        self._cleanup_temp_bpm_file()

    def _on_bpm_error(self, error_message: str):
        """Handle BPM detection error"""
        self.bpm_info_label.setText(f"⚠ Detection failed: {error_message}")
        self.bpm_progress.setVisible(False)
        self.detect_bpm_btn.setEnabled(True)

        # Cleanup temp file
        self._cleanup_temp_bpm_file()

        QMessageBox.warning(
            self,
            "BPM Detection Failed",
            f"Could not detect BPM:\n{error_message}\n\nPlease enter BPM manually.",
        )

    def _cleanup_temp_bpm_file(self):
        """Clean up temporary BPM detection file if it exists"""
        if self.temp_bpm_file:
            try:
                if self.temp_bpm_file.exists():
                    self.temp_bpm_file.unlink()
            except Exception as e:
                if self.player_widget:
                    self.player_widget.ctx.logger().warning(
                        f"Failed to delete temp BPM detection file: {e}"
                    )
            finally:
                self.temp_bpm_file = None

    def closeEvent(self, event):
        """Cleanup when dialog is closed"""
        self._cleanup_temp_bpm_file()
        super().closeEvent(event)

    def get_settings(self) -> LoopExportSettings:
        """
        Get loop export settings from dialog.

        Returns:
            LoopExportSettings with user's choices
        """
        # Parse sample rate
        sr_text = self.sample_rate_combo.currentText()
        sample_rate = int(sr_text.split()[0])  # "44100 Hz" -> 44100

        # Parse bit depth
        bit_depth_text = self.bit_depth_combo.currentText()
        bit_depth = int(bit_depth_text.split()[0])  # "24 bit" -> 24

        # Parse channels
        channels = 2 if self.channels_combo.currentText() == "Stereo" else 1

        # Get export mode
        export_mode = "individual" if self.mode_individual.isChecked() else "mixed"

        return LoopExportSettings(
            bpm=self.bpm_spin.value(),
            bars=self._get_selected_bars(),
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            file_format=self.format_combo.currentText(),
            export_mode=export_mode,
        )


if __name__ == "__main__":
    """Test the dialog"""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # Test with 180 second audio (BPM detection not available in standalone test)
    dialog = LoopExportDialog(player_widget=None, duration_seconds=180.0)

    if dialog.exec() == QDialog.Accepted:
        settings = dialog.get_settings()
        print("Loop Export Settings:")
        print(f"  BPM: {settings.bpm}")
        print(f"  Bars: {settings.bars}")
        print(f"  Sample Rate: {settings.sample_rate}")
        print(f"  Bit Depth: {settings.bit_depth}")
        print(f"  Channels: {settings.channels}")
        print(f"  Format: {settings.file_format}")
    else:
        print("Export cancelled")
