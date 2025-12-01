"""
Export Loops Widget - Configure and execute sampler loop export

PURPOSE: Allow users to configure BPM-based loop export for samplers
CONTEXT: Displayed in main content area when Export Loops is selected in sidebar
"""
from pathlib import Path
from typing import Optional, NamedTuple
import tempfile
import numpy as np
import soundfile as sf

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QPushButton, QRadioButton, QButtonGroup,
    QFrame, QMessageBox, QApplication, QProgressBar,
    QProgressDialog, QFileDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QRunnable, QThreadPool, QObject

from ui.app_context import AppContext
from ui.theme import ThemeManager
from utils.loop_math import get_minimum_bpm, is_valid_for_sampler


class LoopExportSettings(NamedTuple):
    """Loop export settings data"""
    bpm: int
    bars: int
    sample_rate: int
    bit_depth: int
    channels: int
    file_format: str
    export_mode: str


class BPMDetectionWorker(QRunnable):
    """Background worker for BPM detection."""

    class Signals(QObject):
        finished = Signal(float, str, str, float)
        error = Signal(str)

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

            confidence_value = confidence if confidence is not None else 0.0
            self.signals.finished.emit(detected_bpm, bpm_message, self.source_description, confidence_value)

        except Exception as e:
            self.logger.error(f"BPM detection error: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class ExportLoopsWidget(QWidget):
    """
    Widget for configuring and executing sampler loop export.
    
    PURPOSE: Replaces LoopExportDialog as embedded content in main window
    CONTEXT: Shown when user clicks "Export Loops" in sidebar
    
    Features:
    - BPM input with auto-detection
    - Bar length selection (2, 4, or 8 bars)
    - Sample rate, bit depth, channels configuration
    - File format selection (WAV, AIFF, FLAC)
    - Real-time validation of BPM+bars against 20s sampler limit
    - Preview of chunk duration and file count
    - Direct export execution
    """
    
    export_completed = Signal(str)

    def __init__(self, player_widget=None, parent=None):
        """
        Initialize export loops widget.
        
        Args:
            player_widget: Reference to PlayerWidget for accessing stems and export logic
            parent: Parent widget
        """
        super().__init__(parent)
        self.ctx = AppContext()
        self.player_widget = player_widget
        self.detected_bpm = 120
        self.temp_bpm_file = None
        self.thread_pool = QThreadPool()
        
        self._setup_ui()
        self._connect_signals()
        self._update_validation()
        self._update_preview()
        self._update_export_button_state()
        
        self.ctx.logger().info("ExportLoopsWidget initialized")

    def set_player_widget(self, player_widget) -> None:
        """Set or update the player widget reference."""
        self.player_widget = player_widget
        self._update_preview()
        self._update_export_button_state()

    def _create_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled card frame with header"""
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
        """Setup widget UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Status Card ===
        status_card, status_layout = self._create_card("Export Status")
        
        self.status_label = QLabel("Load stems in the Stems tab to enable export.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #888; font-size: 11pt;")
        status_layout.addWidget(self.status_label)
        
        main_layout.addWidget(status_card)

        # === Tempo & Loop Length Card ===
        tempo_card, tempo_layout = self._create_card("Tempo & Loop Length")

        # Preset info (shown when Loop Preview data is available)
        self.preset_info_label = QLabel()
        self.preset_info_label.setVisible(False)
        self.preset_info_label.setStyleSheet(
            "color: #10b981; font-size: 11pt; padding: 8px; "
            "background: rgba(16, 185, 129, 0.1); border-radius: 6px;"
        )
        tempo_layout.addWidget(self.preset_info_label)

        tempo_row = QHBoxLayout()
        tempo_row.setSpacing(30)

        # BPM Section
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
        self.bpm_spin.setValue(120)
        self.bpm_spin.setSuffix(" BPM")
        self.bpm_spin.setMinimumHeight(35)
        self.bpm_spin.setMinimumWidth(150)
        bpm_label_row.addWidget(self.bpm_spin)

        self.detect_bpm_btn = QPushButton("🎵 Detect BPM")
        self.detect_bpm_btn.setMinimumHeight(35)
        self.detect_bpm_btn.setMinimumWidth(130)
        self.detect_bpm_btn.setEnabled(False)
        bpm_label_row.addWidget(self.detect_bpm_btn)

        bpm_label_row.addStretch()
        bpm_container.addLayout(bpm_label_row)

        self.bpm_info_label = QLabel("💡 Click 'Detect BPM' for automatic detection")
        self.bpm_info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        bpm_container.addWidget(self.bpm_info_label)

        self.bpm_progress = QProgressBar()
        self.bpm_progress.setMinimum(0)
        self.bpm_progress.setMaximum(0)
        self.bpm_progress.setTextVisible(True)
        self.bpm_progress.setFormat("Analyzing audio...")
        self.bpm_progress.setMinimumHeight(8)
        self.bpm_progress.setMaximumHeight(8)
        self.bpm_progress.setVisible(False)
        bpm_container.addWidget(self.bpm_progress)

        tempo_row.addLayout(bpm_container)

        # Loop Length Section
        bars_container = QVBoxLayout()
        bars_container.setSpacing(8)

        bars_label_row = QHBoxLayout()
        bars_label_row.setSpacing(10)
        bars_label_text = QLabel("Loop Length:")
        bars_label_text.setMinimumWidth(80)
        bars_label_row.addWidget(bars_label_text)

        self.bars_combo = QComboBox()
        self.bars_combo.addItems(["2 Bar", "4 Bar", "8 Bar"])
        self.bars_combo.setCurrentIndex(1)  # Default: 4 Bar
        self.bars_combo.setMinimumHeight(35)
        self.bars_combo.setMinimumWidth(120)
        bars_label_row.addWidget(self.bars_combo)
        bars_label_row.addStretch()
        bars_container.addLayout(bars_label_row)

        tempo_row.addLayout(bars_container)
        tempo_layout.addLayout(tempo_row)

        # Validation label
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("padding: 5px;")
        tempo_layout.addWidget(self.validation_label)

        main_layout.addWidget(tempo_card)

        # === Row 2: Export Mode + Audio Format ===
        row2_horizontal = QHBoxLayout()
        row2_horizontal.setSpacing(15)

        # Export Mode Card
        mode_card, mode_layout = self._create_card("Export Mode")

        self.mode_button_group = QButtonGroup(self)

        mode_options_col = QVBoxLayout()
        mode_options_col.setSpacing(10)

        self.mode_mixed = QRadioButton("Mixed Audio (all stems combined)")
        self.mode_mixed.setChecked(True)
        self.mode_button_group.addButton(self.mode_mixed)
        mode_options_col.addWidget(self.mode_mixed)

        self.mode_individual = QRadioButton("Individual Stems")
        self.mode_button_group.addButton(self.mode_individual)
        mode_options_col.addWidget(self.mode_individual)

        mode_options_col.addStretch()
        mode_layout.addLayout(mode_options_col)

        row2_horizontal.addWidget(mode_card)

        # Audio Format Card
        format_card, format_layout = self._create_card("Audio Format")

        # Sample rate
        sr_row = QHBoxLayout()
        sr_label = QLabel("Sample Rate:")
        sr_label.setMinimumWidth(80)
        sr_row.addWidget(sr_label)
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["44100 Hz", "48000 Hz"])
        self.sample_rate_combo.setCurrentIndex(0)
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
        self.bit_depth_combo.setCurrentIndex(1)
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
        self.channels_combo.setCurrentIndex(0)
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
        self.format_combo.setCurrentIndex(0)
        self.format_combo.setMinimumHeight(35)
        fmt_row.addWidget(self.format_combo)
        fmt_row.addStretch()
        format_layout.addLayout(fmt_row)

        row2_horizontal.addWidget(format_card)
        main_layout.addLayout(row2_horizontal)

        # === Preview Card ===
        preview_card, preview_layout = self._create_card("Preview")

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setStyleSheet("padding: 5px; color: rgba(255, 255, 255, 0.9);")
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

        main_layout.addStretch()

        # === Export Button ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.btn_export = QPushButton("🔁 Export Loops")
        self.btn_export.setMinimumWidth(150)
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_export, "buttonStyle", "primary")
        buttons_layout.addWidget(self.btn_export)

        main_layout.addLayout(buttons_layout)

    def _connect_signals(self):
        """Connect UI signals"""
        self.bpm_spin.valueChanged.connect(self._on_settings_changed)
        self.bars_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.mode_button_group.buttonToggled.connect(self._on_settings_changed)
        self.sample_rate_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.bit_depth_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.channels_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.format_combo.currentIndexChanged.connect(self._on_settings_changed)

        self.detect_bpm_btn.clicked.connect(self._on_detect_bpm)
        self.btn_export.clicked.connect(self._on_export_clicked)

    def _on_settings_changed(self):
        """Handle any settings change"""
        self._update_validation()
        self._update_preview()

    def _get_selected_bars(self) -> int:
        """Get currently selected bar count from ComboBox."""
        index = self.bars_combo.currentIndex()
        bar_values = [2, 4, 8]
        return bar_values[index] if 0 <= index < len(bar_values) else 4

    def _update_export_button_state(self):
        """Update export button and detect button enabled state"""
        has_stems = (
            self.player_widget is not None and 
            self.player_widget.has_stems_loaded()
        )
        
        # Check validation
        is_valid, _ = is_valid_for_sampler(
            self.bpm_spin.value(), 
            self._get_selected_bars(), 
            max_seconds=20.0
        )
        
        self.btn_export.setEnabled(has_stems and is_valid)
        self.detect_bpm_btn.setEnabled(has_stems)
        
        if has_stems:
            num_stems = len(self.player_widget.stem_files)
            duration = self.player_widget.player.get_duration()
            self.status_label.setText(
                f"✓ Ready to export: {num_stems} stems loaded, "
                f"duration: {duration:.1f}s"
            )
            self.status_label.setStyleSheet("color: #10b981; font-size: 11pt;")
            self.mode_individual.setText(f"Individual Stems ({num_stems} separate sets)")
            
            # Check for Loop Preview presets
            self._check_loop_preview_presets()
        else:
            self.status_label.setText(
                "⚠ Load stems in the Stems tab to enable export."
            )
            self.status_label.setStyleSheet("color: #888; font-size: 11pt;")
            self.mode_individual.setText("Individual Stems")
            self.preset_info_label.setVisible(False)

    def _check_loop_preview_presets(self):
        """Check if Loop Preview has detected beats and use those settings"""
        if not self.player_widget:
            return
            
        # Check for detected downbeats from Loop Preview
        if (self.player_widget.detected_downbeat_times is not None and 
            len(self.player_widget.detected_downbeat_times) >= 2):
            
            # Calculate BPM from downbeat intervals
            downbeat_intervals = np.diff(self.player_widget.detected_downbeat_times)
            median_bar_duration = float(np.median(downbeat_intervals))
            if median_bar_duration > 0:
                preset_bpm = (60.0 * 4) / median_bar_duration
                preset_bars = self.player_widget._bars_per_loop
                
                # Update UI with presets
                self.bpm_spin.setValue(int(preset_bpm))
                
                # Set bars combo
                if preset_bars == 2:
                    self.bars_combo.setCurrentIndex(0)
                elif preset_bars == 8:
                    self.bars_combo.setCurrentIndex(2)
                else:
                    self.bars_combo.setCurrentIndex(1)
                
                # Show preset info
                self.preset_info_label.setText(
                    f"✓ Using Loop Preview settings: {preset_bpm:.1f} BPM, {preset_bars} bars"
                )
                self.preset_info_label.setVisible(True)
                
                self.bpm_info_label.setText("✓ BPM from Loop Preview (editable)")
                self.bpm_info_label.setStyleSheet("color: #10b981; font-size: 11pt;")
                
                self.ctx.logger().info(
                    f"Using Loop Preview presets: {preset_bpm:.1f} BPM, {preset_bars} bars"
                )

    def _update_validation(self):
        """Update BPM+bars validation display"""
        bpm = self.bpm_spin.value()
        bars = self._get_selected_bars()

        is_valid, error_msg = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        if is_valid:
            from utils.loop_math import compute_chunk_duration_seconds
            duration = compute_chunk_duration_seconds(bpm, bars)

            self.validation_label.setText(
                f"✓ Valid: {bars} bars at {bpm} BPM = {duration:.2f}s per chunk"
            )
            self.validation_label.setStyleSheet(
                "color: rgba(100, 255, 100, 0.9); padding: 5px;"
            )
        else:
            min_bpm = get_minimum_bpm(bars, max_seconds=20.0)

            self.validation_label.setText(
                f"⚠ {error_msg}\n"
                f"Minimum BPM for {bars} bars: {min_bpm}"
            )
            self.validation_label.setStyleSheet(
                "color: rgba(255, 100, 100, 0.9); padding: 5px;"
            )
        
        # Update export button state
        has_stems = (
            self.player_widget is not None and 
            self.player_widget.has_stems_loaded()
        )
        self.btn_export.setEnabled(has_stems and is_valid)

    def _update_preview(self):
        """Update export preview"""
        if not self.player_widget or not self.player_widget.has_stems_loaded():
            self.preview_label.setText("Load stems to see preview")
            return
            
        bpm = self.bpm_spin.value()
        bars = self._get_selected_bars()
        duration_seconds = self.player_widget.player.get_duration()
        num_stems = len(self.player_widget.stem_files)

        is_valid, _ = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        if not is_valid:
            self.preview_label.setText("Configure valid settings above to see preview")
            return

        from utils.loop_math import compute_chunk_duration_seconds

        chunk_duration = compute_chunk_duration_seconds(bpm, bars)
        sr_text = self.sample_rate_combo.currentText()
        
        num_chunks = max(1, int(duration_seconds / chunk_duration))
        if duration_seconds % chunk_duration > chunk_duration * 0.1:
            num_chunks += 1

        fmt = self.format_combo.currentText()
        bit_depth_text = self.bit_depth_combo.currentText()
        channels_text = self.channels_combo.currentText()

        is_individual = self.mode_individual.isChecked()

        if is_individual:
            total_files = num_chunks * num_stems
            preview = (
                f"Will export {total_files} files ({num_stems} stems × {num_chunks} chunks):\n"
                f"• ~{chunk_duration:.2f}s per chunk ({bars} bars)\n"
                f"• Format: {fmt}, {bit_depth_text}, {channels_text}\n"
                f"• Sample rate: {sr_text}"
            )
        else:
            preview = (
                f"Will export {num_chunks} chunk(s):\n"
                f"• ~{chunk_duration:.2f}s per chunk ({bars} bars)\n"
                f"• Format: {fmt}, {bit_depth_text}, {channels_text}\n"
                f"• Sample rate: {sr_text}"
            )

        self.preview_label.setText(preview)

    def refresh(self):
        """Refresh the widget state (called when navigating to this page)"""
        self._update_export_button_state()
        self._update_validation()
        self._update_preview()

    def get_settings(self) -> LoopExportSettings:
        """Get loop export settings from widget"""
        sr_text = self.sample_rate_combo.currentText()
        sample_rate = int(sr_text.split()[0])

        bit_depth_text = self.bit_depth_combo.currentText()
        bit_depth = int(bit_depth_text.split()[0])

        channels = 2 if self.channels_combo.currentText() == "Stereo" else 1
        export_mode = 'individual' if self.mode_individual.isChecked() else 'mixed'

        return LoopExportSettings(
            bpm=self.bpm_spin.value(),
            bars=self._get_selected_bars(),
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            file_format=self.format_combo.currentText(),
            export_mode=export_mode
        )

    @Slot()
    def _on_detect_bpm(self):
        """Handle BPM detection button click"""
        if not self.player_widget:
            return

        try:
            self.detect_bpm_btn.setEnabled(False)
            self.bpm_progress.setVisible(True)
            self.bpm_info_label.setText("🔄 Detecting BPM from audio...")

            bpm_source_file, source_description = self.player_widget._get_audio_for_bpm_detection()

            if 'bpm_detect_' in str(bpm_source_file):
                self.temp_bpm_file = bpm_source_file

            logger = self.player_widget.ctx.logger()

            worker = BPMDetectionWorker(bpm_source_file, source_description, logger)
            worker.signals.finished.connect(self._on_bpm_detected)
            worker.signals.error.connect(self._on_bpm_error)

            self.thread_pool.start(worker)

        except Exception as e:
            self._on_bpm_error(str(e))

    def _on_bpm_detected(self, detected_bpm: float, message: str, source_description: str, confidence: float):
        """Handle successful BPM detection"""
        self.detected_bpm = round(detected_bpm)
        self.bpm_spin.setValue(self.detected_bpm)

        if confidence > 0:
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
                f"{confidence_icon} Detected: {self.detected_bpm} BPM ({confidence:.0%} confident)"
            )
            self.bpm_info_label.setStyleSheet(f"{color_style} font-size: 11pt;")
        else:
            self.bpm_info_label.setText(
                f"✓ Detected: {self.detected_bpm} BPM (librosa)"
            )
            self.bpm_info_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11pt;")

        self.bpm_progress.setVisible(False)
        self.detect_bpm_btn.setEnabled(True)

        self._update_validation()
        self._update_preview()
        self._cleanup_temp_bpm_file()

    def _on_bpm_error(self, error_message: str):
        """Handle BPM detection error"""
        self.bpm_info_label.setText(f"⚠ Detection failed: {error_message}")
        self.bpm_progress.setVisible(False)
        self.detect_bpm_btn.setEnabled(True)
        self._cleanup_temp_bpm_file()

        QMessageBox.warning(
            self,
            "BPM Detection Failed",
            f"Could not detect BPM:\n{error_message}\n\nPlease enter BPM manually."
        )

    def _cleanup_temp_bpm_file(self):
        """Clean up temporary BPM detection file"""
        if self.temp_bpm_file:
            try:
                if self.temp_bpm_file.exists():
                    self.temp_bpm_file.unlink()
            except Exception as e:
                self.ctx.logger().warning(f"Failed to delete temp BPM file: {e}")
            finally:
                self.temp_bpm_file = None

    @Slot()
    def _on_export_clicked(self):
        """Handle export button click"""
        if not self.player_widget or not self.player_widget.has_stems_loaded():
            QMessageBox.warning(
                self,
                "No Stems Loaded",
                "Please load stems in the Stems tab before exporting."
            )
            return

        settings = self.get_settings()

        # Ask for output directory
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Loop Export"
        )
        if not output_dir:
            return

        output_path = Path(output_dir)
        self._execute_export(output_path, settings)

    def _execute_export(self, output_path: Path, settings: LoopExportSettings):
        """Execute the loop export"""
        try:
            from core.sampler_export import export_sampler_loops

            player = self.player_widget.player
            common_filename = self.player_widget._get_common_filename()

            if settings.export_mode == 'individual':
                self._export_individual_stems(output_path, settings, common_filename)
            else:
                # Mix stems and export
                mixed_audio = player._mix_stems(0, player.duration_samples)
                if mixed_audio is None or len(mixed_audio) == 0:
                    QMessageBox.warning(
                        self, "Export Failed",
                        "Unable to mix audio for export."
                    )
                    return

                mixed_audio = mixed_audio.T

                with tempfile.NamedTemporaryFile(
                    suffix='.wav', delete=False, dir=str(output_path.parent)
                ) as temp_file:
                    temp_path = Path(temp_file.name)

                    try:
                        sf.write(
                            str(temp_path),
                            mixed_audio,
                            player.sample_rate,
                            subtype='PCM_24'
                        )

                        progress_dialog = QProgressDialog(
                            "Exporting loops...", None, 0, 100, self
                        )
                        progress_dialog.setWindowTitle("Exporting Loops")
                        progress_dialog.setWindowModality(Qt.WindowModal)
                        progress_dialog.setMinimumDuration(0)
                        progress_dialog.setValue(0)

                        def progress_callback(message: str, percent: int):
                            progress_dialog.setLabelText(message)
                            progress_dialog.setValue(percent)
                            QApplication.processEvents()

                        result = export_sampler_loops(
                            input_path=temp_path,
                            output_dir=output_path,
                            bpm=settings.bpm,
                            bars=settings.bars,
                            sample_rate=settings.sample_rate,
                            bit_depth=settings.bit_depth,
                            channels=settings.channels,
                            file_format=settings.file_format,
                            progress_callback=progress_callback,
                            common_filename=common_filename,
                            stem_name=None
                        )

                        progress_dialog.setValue(100)
                        progress_dialog.close()

                        if result.success:
                            QMessageBox.information(
                                self, "Export Successful",
                                f"Exported {result.chunk_count} loop file(s) to:\n{output_path}"
                            )
                            self.export_completed.emit(f"Exported {result.chunk_count} loops")
                        else:
                            QMessageBox.critical(
                                self, "Export Failed",
                                f"Loop export failed:\n{result.error_message}"
                            )

                    finally:
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass

        except Exception as e:
            self.ctx.logger().error(f"Loop export error: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Export Failed",
                f"An error occurred during loop export:\n{str(e)}"
            )

    def _export_individual_stems(self, output_path: Path, settings: LoopExportSettings, common_filename: str):
        """Export each stem individually as loops"""
        from core.sampler_export import export_sampler_loops

        try:
            overall_progress = QProgressDialog(
                "Preparing stem export...", None, 0,
                len(self.player_widget.stem_files) * 100, self
            )
            overall_progress.setWindowTitle("Exporting Individual Stems")
            overall_progress.setWindowModality(Qt.WindowModal)
            overall_progress.setMinimumDuration(0)
            overall_progress.setValue(0)

            total_chunks = 0
            stem_results = []

            for stem_idx, (stem_name, stem_path) in enumerate(self.player_widget.stem_files.items()):
                stem_file = Path(stem_path)
                base_progress = stem_idx * 100
                
                overall_progress.setLabelText(f"Exporting {stem_name}...")
                overall_progress.setValue(base_progress)
                QApplication.processEvents()

                def progress_callback(message: str, percent: int):
                    overall_progress.setLabelText(f"Exporting {stem_name}...\n{message}")
                    overall_progress.setValue(base_progress + percent)
                    QApplication.processEvents()

                result = export_sampler_loops(
                    input_path=stem_file,
                    output_dir=output_path,
                    bpm=settings.bpm,
                    bars=settings.bars,
                    sample_rate=settings.sample_rate,
                    bit_depth=settings.bit_depth,
                    channels=settings.channels,
                    file_format=settings.file_format,
                    progress_callback=progress_callback,
                    common_filename=common_filename,
                    stem_name=stem_name
                )

                if result.success:
                    total_chunks += result.chunk_count
                    stem_results.append((stem_name, result.chunk_count))

            overall_progress.setValue(len(self.player_widget.stem_files) * 100)
            overall_progress.close()

            if total_chunks > 0:
                summary_lines = [f"• {name}: {count} file(s)" for name, count in stem_results]
                summary_text = "\n".join(summary_lines)

                QMessageBox.information(
                    self, "Export Successful",
                    f"Exported {total_chunks} loop file(s) total from {len(stem_results)} stem(s) to:\n"
                    f"{output_path}\n\n{summary_text}"
                )
                self.export_completed.emit(f"Exported {total_chunks} loops from {len(stem_results)} stems")
            else:
                QMessageBox.critical(
                    self, "Export Failed",
                    "Failed to export any stems. Check the log for details."
                )

        except Exception as e:
            self.ctx.logger().error(f"Individual stem export error: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Export Failed",
                f"An error occurred during individual stem export:\n{str(e)}"
            )

