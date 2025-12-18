"""
Export Loops Widget - Configure and execute sampler loop export

PURPOSE: Allow users to configure BPM-based loop export for samplers
CONTEXT: Displayed in main content area when Export Loops is selected in sidebar
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, NamedTuple, List
import tempfile
import numpy as np
import soundfile as sf

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QMessageBox,
    QApplication,
    QProgressDialog,
    QFileDialog,
)
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool, QObject

from ui.app_context import AppContext
from ui.theme import ThemeManager
from utils.loop_math import get_minimum_bpm, is_valid_for_sampler
from core.background_stretch_manager import BackgroundStretchManager, get_optimal_worker_count


class LoopExportSettings(NamedTuple):
    """Loop export settings data"""

    bpm: int
    bars: int
    sample_rate: int
    bit_depth: int
    channels: int
    file_format: str
    export_mode: str
    loop_version: str  # "original" | "stretched"


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
        self.thread_pool = QThreadPool()

        # Time-stretching state (manager accessed via player_widget)
        # Note: Preview functionality removed - preview is handled in Looping tab

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
        # Connect to stretch manager signals if available
        self._connect_stretch_manager_signals()
        # Update loop version checkbox state
        self._update_loop_version_checkbox_state()

    def _get_stretch_manager(self):
        """
        Get stretch manager from player widget.
        
        PURPOSE: Centralized access to stretch manager from player widget
        CONTEXT: Manager is managed by player widget, not export widget
        
        Returns:
            BackgroundStretchManager instance or None if not available
        """
        if not self.player_widget:
            return None
        return self.player_widget.get_stretch_manager()

    def _connect_stretch_manager_signals(self):
        """Connect to stretch manager signals if manager is available"""
        manager = self._get_stretch_manager()
        if manager:
            # Disconnect existing connections to avoid duplicates
            try:
                manager.progress_updated.disconnect()
                manager.all_completed.disconnect()
                manager.task_completed.disconnect()
            except TypeError:
                # Signals not connected yet, ignore
                pass
            
            # Connect signals
            manager.progress_updated.connect(self._on_stretch_progress_updated)
            manager.all_completed.connect(self._on_stretch_all_completed)
            manager.task_completed.connect(self._on_stretch_task_completed)

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
        """
        Setup widget UI.
        
        PURPOSE: Create simplified UI with only Export Mode and Audio Format cards
        CONTEXT: Tempo/Loop Length and Time-Stretching settings moved to Looping tab
        """
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Row 1: Export Mode + Audio Format ===
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

        # Loop Version Checkbox
        self.loop_version_checkbox = QCheckBox("Use Time-Stretched Loops")
        self.loop_version_checkbox.setEnabled(False)  # Disabled by default
        self.loop_version_checkbox.setToolTip("Bitte Time-Stretching im Looping-Tab aktivieren")
        mode_options_col.addWidget(self.loop_version_checkbox)

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
        """
        Connect UI signals.
        
        PURPOSE: Wire up widget signals for export mode and audio format changes
        CONTEXT: Tempo/Loop Length and Time-Stretching signals removed (handled in Looping tab)
        """
        # Export mode and audio format signals
        self.mode_button_group.buttonToggled.connect(self._on_settings_changed)
        self.sample_rate_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.bit_depth_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.channels_combo.currentIndexChanged.connect(self._on_settings_changed)
        self.format_combo.currentIndexChanged.connect(self._on_settings_changed)
        
        # Loop version checkbox signal
        self.loop_version_checkbox.toggled.connect(self._on_settings_changed)

        # Export button
        self.btn_export.clicked.connect(self._on_export_clicked)

        # Background stretch manager signals (connected via _connect_stretch_manager_signals)
        # when player_widget is set

    def _on_settings_changed(self):
        """Handle any settings change"""
        self._update_validation()
        self._update_preview()

    def _has_loop_detection(self) -> bool:
        """
        Check if loop detection has been performed.
        
        PURPOSE: Determine if user has run loop detection in Looping tab
        CONTEXT: Export requires loop detection to have valid BPM and bars settings
        
        Returns:
            True if loop detection has been performed, False otherwise
        """
        if not self.player_widget:
            return False
        return (
            self.player_widget.detected_downbeat_times is not None
            and len(self.player_widget.detected_downbeat_times) >= 2
        )

    def _get_bpm_from_player_widget(self) -> int:
        """
        Get BPM from player widget or fallback to default.
        
        PURPOSE: Retrieve BPM from loop detection or use default
        CONTEXT: BPM is calculated from detected downbeats in Looping tab
        
        Returns:
            BPM value (integer) or 120 as default fallback
        """
        if self._has_loop_detection():
            downbeat_intervals = np.diff(self.player_widget.detected_downbeat_times)
            median_bar_duration = float(np.median(downbeat_intervals))
            if median_bar_duration > 0:
                return int((60.0 * 4) / median_bar_duration)
        return 120  # Default fallback

    def _get_bars_from_player_widget(self) -> int:
        """
        Get bars per loop from player widget or fallback to default.
        
        PURPOSE: Retrieve bars per loop setting from Looping tab
        CONTEXT: Bars per loop is configured in Looping tab
        
        Returns:
            Bars per loop (2, 4, or 8) or 4 as default fallback
        """
        if self.player_widget:
            return getattr(self.player_widget, '_bars_per_loop', 4)
        return 4  # Default fallback

    def _get_target_bpm_from_player_widget(self) -> int:
        """
        Get target BPM from player widget or fallback to default.
        
        PURPOSE: Retrieve target BPM setting from Looping tab
        CONTEXT: Target BPM is configured in Looping tab for time-stretching
        
        Returns:
            Target BPM value or 120 as default fallback
        """
        if self.player_widget and hasattr(self.player_widget, 'time_stretch_target_bpm'):
            return self.player_widget.time_stretch_target_bpm
        return 120  # Default fallback

    def _has_time_stretching_enabled(self) -> bool:
        """
        Check if time-stretching is enabled in Looping tab.
        
        PURPOSE: Determine if time-stretching checkbox is checked in Looping tab
        CONTEXT: Loop version checkbox should only be enabled when time-stretching is active
        
        Returns:
            True if time-stretching is enabled, False otherwise
        """
        if not self.player_widget:
            return False
        if hasattr(self.player_widget, 'time_stretch_checkbox'):
            return self.player_widget.time_stretch_checkbox.isChecked()
        return False

    def _has_stretched_loops_ready(self) -> bool:
        """
        Check if stretched loops are ready for export.
        
        PURPOSE: Determine if stretched loops have been processed and are available
        CONTEXT: Loop version checkbox should only be enabled when loops are ready
        
        Returns:
            True if stretched loops are ready, False otherwise
        """
        manager = self._get_stretch_manager()
        if not manager:
            return False
        # Check if processing is complete and we have completed tasks
        return not manager.is_running and len(manager.completed_tasks) > 0

    def _update_loop_version_checkbox_state(self):
        """
        Update loop version checkbox enabled state.
        
        PURPOSE: Enable/disable checkbox based on time-stretching availability
        CONTEXT: Checkbox should only be enabled when time-stretching is active and loops are ready
        """
        has_stretching = self._has_time_stretching_enabled()
        has_loops_ready = self._has_stretched_loops_ready()
        
        self.loop_version_checkbox.setEnabled(has_stretching and has_loops_ready)
        
        if not has_stretching:
            self.loop_version_checkbox.setToolTip("Bitte Time-Stretching im Looping-Tab aktivieren")
        elif not has_loops_ready:
            self.loop_version_checkbox.setToolTip("Time-Stretching wird noch verarbeitet...")
        else:
            self.loop_version_checkbox.setToolTip("Exportiere time-gestretchte Loops")

    def _update_export_button_state(self):
        """
        Update export button and detect button enabled state.
        
        PURPOSE: Control export button availability based on stems and loop detection
        CONTEXT: Export requires stems loaded AND loop detection performed
        """
        has_stems = (
            self.player_widget is not None and self.player_widget.has_stems_loaded()
        )
        has_loop_detection = self._has_loop_detection()

        # Check validation (always use player widget data)
        bpm = self._get_bpm_from_player_widget()
        bars = self._get_bars_from_player_widget()
        
        is_valid, _ = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        # Export button requires: stems + loop detection + valid settings
        self.btn_export.setEnabled(has_stems and has_loop_detection and is_valid)
        
        if not has_loop_detection:
            self.btn_export.setToolTip("Bitte zuerst Loop Detection im Looping-Tab durchführen")
        else:
            self.btn_export.setToolTip("")

        if has_stems:
            num_stems = len(self.player_widget.stem_files)
            self.mode_individual.setText(
                f"Individual Stems ({num_stems} separate sets)"
            )
        else:
            self.mode_individual.setText("Individual Stems")

    def _update_validation(self):
        """
        Update BPM+bars validation.
        
        PURPOSE: Validate BPM and bars settings from player widget
        CONTEXT: Validation uses data from Looping tab, not UI controls
        """
        bpm = self._get_bpm_from_player_widget()
        bars = self._get_bars_from_player_widget()

        is_valid, error_msg = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        # Validation is now used only for export button state
        # No UI label to update (removed with Tempo Card)

    def _update_preview(self):
        """
        Update export preview.
        
        PURPOSE: Show preview of export based on settings from player widget
        CONTEXT: BPM and bars come from Looping tab, not UI controls
        """
        if not self.player_widget or not self.player_widget.has_stems_loaded():
            self.preview_label.setText("Load stems to see preview")
            return

        bpm = self._get_bpm_from_player_widget()
        bars = self._get_bars_from_player_widget()
        duration_seconds = self.player_widget.player.get_duration()
        num_stems = len(self.player_widget.stem_files)

        is_valid, _ = is_valid_for_sampler(bpm, bars, max_seconds=20.0)

        if not is_valid:
            self.preview_label.setText("Configure valid settings in Looping tab to see preview")
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
        loop_version = "stretched" if self.loop_version_checkbox.isChecked() else "original"

        if is_individual:
            total_files = num_chunks * num_stems
            preview = (
                f"Will export {total_files} files ({num_stems} stems × {num_chunks} chunks):\n"
                f"• ~{chunk_duration:.2f}s per chunk ({bars} bars at {bpm} BPM)\n"
                f"• Loop version: {loop_version}\n"
                f"• Format: {fmt}, {bit_depth_text}, {channels_text}\n"
                f"• Sample rate: {sr_text}"
            )
        else:
            preview = (
                f"Will export {num_chunks} chunk(s):\n"
                f"• ~{chunk_duration:.2f}s per chunk ({bars} bars at {bpm} BPM)\n"
                f"• Loop version: {loop_version}\n"
                f"• Format: {fmt}, {bit_depth_text}, {channels_text}\n"
                f"• Sample rate: {sr_text}"
            )

        self.preview_label.setText(preview)

    def refresh(self):
        """Refresh the widget state (called when navigating to this page)"""
        self._update_export_button_state()
        self._update_validation()
        self._update_preview()
        self._update_loop_version_checkbox_state()

    def get_settings(self) -> LoopExportSettings:
        """
        Get loop export settings from widget.
        
        PURPOSE: Collect all export settings including loop version
        CONTEXT: Settings include BPM, bars, format options, and loop version (original/stretched)
        
        Returns:
            LoopExportSettings with all export configuration
        """
        sr_text = self.sample_rate_combo.currentText()
        sample_rate = int(sr_text.split()[0])

        bit_depth_text = self.bit_depth_combo.currentText()
        bit_depth = int(bit_depth_text.split()[0])

        channels = 2 if self.channels_combo.currentText() == "Stereo" else 1
        export_mode = "individual" if self.mode_individual.isChecked() else "mixed"
        
        # Determine loop version (original or stretched)
        loop_version = "stretched" if self.loop_version_checkbox.isChecked() else "original"

        return LoopExportSettings(
            bpm=self._get_bpm_from_player_widget(),
            bars=self._get_bars_from_player_widget(),
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            file_format=self.format_combo.currentText(),
            export_mode=export_mode,
            loop_version=loop_version,
        )

    @Slot()
    def _on_export_clicked(self):
        """Handle export button click"""
        if not self.player_widget or not self.player_widget.has_stems_loaded():
            QMessageBox.warning(
                self,
                "No Stems Loaded",
                "Please load stems in the Stems tab before exporting.",
            )
            return

        settings = self.get_settings()

        # Ask for output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Directory for Loop Export"
        )
        if not output_dir:
            return

        output_path = Path(output_dir)
        self._execute_export(output_path, settings)

    def _execute_export(self, output_path: Path, settings: LoopExportSettings):
        """
        Execute the loop export.
        
        PURPOSE: Export loops based on settings, including loop version (original/stretched)
        CONTEXT: Uses loop_version from settings to determine export method
        """
        try:
            # Check if we should export stretched loops
            if settings.loop_version == "stretched" and self._all_loops_ready():
                # Export stretched loops from cache
                self._export_stretched_loops(output_path, settings)
                return

            # Otherwise, use traditional export (original BPM)
            from core.sampler_export import export_sampler_loops, export_padded_intro

            player = self.player_widget.player
            common_filename = self.player_widget._get_common_filename()

            # Check if we have leading loops
            intro_loops = getattr(self.player_widget, "detected_intro_loops", [])

            if settings.export_mode == "individual":
                self._export_individual_stems(
                    output_path, settings, common_filename, intro_loops
                )
            else:
                # Mix stems and export
                mixed_audio = player._mix_stems(0, player.duration_samples)
                if mixed_audio is None or len(mixed_audio) == 0:
                    QMessageBox.warning(
                        self, "Export Failed", "Unable to mix audio for export."
                    )
                    return

                mixed_audio = mixed_audio.T

                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False, dir=str(output_path.parent)
                ) as temp_file:
                    temp_path = Path(temp_file.name)

                    try:
                        sf.write(
                            str(temp_path),
                            mixed_audio,
                            player.sample_rate,
                            subtype="PCM_24",
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

                        total_exported = 0

                        # Export leading loops if present
                        if intro_loops:
                            for i, intro_loop in enumerate(intro_loops, start=1):
                                progress_dialog.setLabelText(
                                    f"Exporting leading loop {i}/{len(intro_loops)}..."
                                )
                                progress_dialog.setValue(5 + (i * 5 / len(intro_loops)))
                                QApplication.processEvents()

                                intro_filename = f"{common_filename}_{settings.bpm}BPM_{settings.bars}T_intro{i:03d}.{settings.file_format.lower()}"
                                intro_path = output_path / intro_filename

                                intro_success = export_padded_intro(
                                    input_path=temp_path,
                                    output_path=intro_path,
                                    intro_start=intro_loop[0],
                                    intro_end=intro_loop[1],
                                    sample_rate=settings.sample_rate,
                                    bit_depth=settings.bit_depth,
                                    channels=settings.channels,
                                    file_format=settings.file_format,
                                )

                                if intro_success:
                                    total_exported += 1
                                    self.ctx.logger().info(
                                        f"Exported leading loop {i}: {intro_filename}"
                                    )

                        # Export main loops
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
                            stem_name=None,
                        )

                        progress_dialog.setValue(100)
                        progress_dialog.close()

                        if result.success:
                            total_exported += result.chunk_count
                            intro_msg = (
                                f" (including {len(intro_loops)} leading loops)"
                                if intro_loops
                                else ""
                            )
                            QMessageBox.information(
                                self,
                                "Export Successful",
                                f"Exported {total_exported} loop file(s){intro_msg} to:\n{output_path}",
                            )
                            self.export_completed.emit(
                                f"Exported {total_exported} loops"
                            )
                        else:
                            QMessageBox.critical(
                                self,
                                "Export Failed",
                                f"Loop export failed:\n{result.error_message}",
                            )

                    finally:
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass

        except Exception as e:
            self.ctx.logger().error(f"Loop export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during loop export:\n{str(e)}",
            )

    def _export_individual_stems(
        self,
        output_path: Path,
        settings: LoopExportSettings,
        common_filename: str,
        intro_loops: List[tuple[float, float]] = None,
    ):
        """Export each stem individually as loops"""
        from core.sampler_export import export_sampler_loops, export_padded_intro

        try:
            # Default to empty list if None
            if intro_loops is None:
                intro_loops = []

            overall_progress = QProgressDialog(
                "Preparing stem export...",
                None,
                0,
                len(self.player_widget.stem_files) * 100,
                self,
            )
            overall_progress.setWindowTitle("Exporting Individual Stems")
            overall_progress.setWindowModality(Qt.WindowModal)
            overall_progress.setMinimumDuration(0)
            overall_progress.setValue(0)

            total_chunks = 0
            stem_results = []

            for stem_idx, (stem_name, stem_path) in enumerate(
                self.player_widget.stem_files.items()
            ):
                stem_file = Path(stem_path)
                base_progress = stem_idx * 100

                overall_progress.setLabelText(f"Exporting {stem_name}...")
                overall_progress.setValue(base_progress)
                QApplication.processEvents()

                def progress_callback(message: str, percent: int):
                    overall_progress.setLabelText(
                        f"Exporting {stem_name}...\n{message}"
                    )
                    overall_progress.setValue(base_progress + percent)
                    QApplication.processEvents()

                stem_chunk_count = 0

                # Export leading loops if present
                if intro_loops:
                    for i, intro_loop in enumerate(intro_loops, start=1):
                        overall_progress.setLabelText(
                            f"Exporting {stem_name} leading loop {i}/{len(intro_loops)}..."
                        )
                        overall_progress.setValue(
                            base_progress + (i * 5 / len(intro_loops))
                        )
                        QApplication.processEvents()

                        intro_filename = f"{common_filename}_{stem_name}_{settings.bpm}BPM_{settings.bars}T_intro{i:03d}.{settings.file_format.lower()}"
                        intro_path = output_path / intro_filename

                        intro_success = export_padded_intro(
                            input_path=stem_file,
                            output_path=intro_path,
                            intro_start=intro_loop[0],
                            intro_end=intro_loop[1],
                            sample_rate=settings.sample_rate,
                            bit_depth=settings.bit_depth,
                            channels=settings.channels,
                            file_format=settings.file_format,
                        )

                        if intro_success:
                            stem_chunk_count += 1
                            self.ctx.logger().info(
                                f"Exported leading loop {i} for {stem_name}: {intro_filename}"
                            )

                # Export main loops
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
                    stem_name=stem_name,
                )

                if result.success:
                    stem_chunk_count += result.chunk_count
                    total_chunks += stem_chunk_count
                    stem_results.append((stem_name, stem_chunk_count))

            overall_progress.setValue(len(self.player_widget.stem_files) * 100)
            overall_progress.close()

            if total_chunks > 0:
                summary_lines = [
                    f"• {name}: {count} file(s)" for name, count in stem_results
                ]
                summary_text = "\n".join(summary_lines)

                intro_msg = (
                    f" (including {len(intro_loops)} leading loops)"
                    if intro_loops
                    else ""
                )
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {total_chunks} loop file(s) total{intro_msg} from {len(stem_results)} stem(s) to:\n"
                    f"{output_path}\n\n{summary_text}",
                )
                self.export_completed.emit(
                    f"Exported {total_chunks} loops from {len(stem_results)} stems"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    "Failed to export any stems. Check the log for details.",
                )

        except Exception as e:
            self.ctx.logger().error(f"Individual stem export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during individual stem export:\n{str(e)}",
            )

    def _all_loops_ready(self) -> bool:
        """
        Check if all stretched loops are ready in the cache.

        Returns:
            True if all loops for all stems are ready, False otherwise
        """
        stem_files = self._get_stem_files_dict()
        loop_segments = self._get_loop_segments()

        if not stem_files or not loop_segments:
            return False

        # Check each stem × loop combination
        manager = self._get_stretch_manager()
        if not manager:
            return False
        
        target_bpm = self._get_target_bpm_from_player_widget()
        for stem_name in stem_files.keys():
            for loop_idx in range(len(loop_segments)):
                if not manager.is_loop_ready(stem_name, loop_idx, target_bpm):
                    return False

        return True

    def _export_stretched_loops(self, output_path: Path, settings: LoopExportSettings):
        """
        Export time-stretched loops from cache.

        This bypasses the traditional chunking export and directly exports
        the pre-stretched loops from the cache.
        """
        try:
            manager = self._get_stretch_manager()
            if not manager:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Stretch manager not available. Please enable time-stretching in the Looping tab first."
                )
                return
            
            common_filename = self.player_widget._get_common_filename()
            stem_files = self._get_stem_files_dict()
            loop_segments = self._get_loop_segments()
            target_bpm = self._get_target_bpm_from_player_widget()

            # Determine subtype based on bit depth
            subtype_map = {16: "PCM_16", 24: "PCM_24", 32: "PCM_32"}
            subtype = subtype_map.get(settings.bit_depth, "PCM_24")

            # Create progress dialog
            total_files = len(stem_files) * len(loop_segments)
            if settings.export_mode == "mixed":
                total_files = len(loop_segments)  # Only export mixed loops

            progress = QProgressDialog(
                "Exporting stretched loops...",
                None,
                0,
                total_files,
                self
            )
            progress.setWindowTitle("Exporting Stretched Loops")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            exported_count = 0

            if settings.export_mode == "mixed":
                # Export mixed loops (all stems combined)
                for loop_idx in range(len(loop_segments)):
                    progress.setLabelText(f"Exporting mixed loop {loop_idx + 1}/{len(loop_segments)}...")
                    progress.setValue(loop_idx)
                    QApplication.processEvents()

                    # Mix all stems for this loop
                    mixed_audio = None
                    for stem_name in stem_files.keys():
                        # Get stretched loop from cache
                        loop_audio = manager.get_stretched_loop(
                            stem_name, loop_idx, target_bpm
                        )

                        if loop_audio is None:
                            self.ctx.logger().warning(
                                f"Loop {loop_idx} for {stem_name} not found in cache, skipping"
                            )
                            continue

                        # Ensure stereo
                        if loop_audio.ndim == 1:
                            loop_audio = np.stack([loop_audio, loop_audio], axis=1)

                        # Initialize or add to mix
                        if mixed_audio is None:
                            mixed_audio = loop_audio.astype(np.float32)
                        else:
                            mixed_audio += loop_audio.astype(np.float32)

                    if mixed_audio is None:
                        self.ctx.logger().warning(f"No audio for loop {loop_idx}, skipping")
                        continue

                    # Apply channels setting
                    if settings.channels == 1 and mixed_audio.ndim == 2:
                        # Convert to mono
                        mixed_audio = np.mean(mixed_audio, axis=1)

                    # Normalize to prevent clipping
                    peak = np.max(np.abs(mixed_audio))
                    if peak > 1.0:
                        mixed_audio = mixed_audio * (0.95 / peak)

                    # Generate filename
                    filename = f"{common_filename}_{target_bpm}BPM_{settings.bars}T_{loop_idx + 1:03d}.{settings.file_format.lower()}"
                    file_path = output_path / filename

                    # Export
                    sf.write(
                        str(file_path),
                        mixed_audio,
                        settings.sample_rate,
                        subtype=subtype,
                        format=settings.file_format
                    )

                    exported_count += 1
                    self.ctx.logger().info(f"Exported mixed loop {loop_idx + 1}: {filename}")

            else:
                # Export individual stems
                file_idx = 0
                for stem_name in stem_files.keys():
                    for loop_idx in range(len(loop_segments)):
                        progress.setLabelText(
                            f"Exporting {stem_name} loop {loop_idx + 1}/{len(loop_segments)}..."
                        )
                        progress.setValue(file_idx)
                        QApplication.processEvents()
                        file_idx += 1

                        # Get stretched loop from cache
                        loop_audio = manager.get_stretched_loop(
                            stem_name, loop_idx, target_bpm
                        )

                        if loop_audio is None:
                            self.ctx.logger().warning(
                                f"Loop {loop_idx} for {stem_name} not found in cache, skipping"
                            )
                            continue

                        # Ensure stereo
                        if loop_audio.ndim == 1:
                            loop_audio = np.stack([loop_audio, loop_audio], axis=1)

                        # Apply channels setting
                        if settings.channels == 1 and loop_audio.ndim == 2:
                            # Convert to mono
                            loop_audio = np.mean(loop_audio, axis=1)

                        # Generate filename
                        filename = f"{common_filename}_{stem_name}_{target_bpm}BPM_{settings.bars}T_{loop_idx + 1:03d}.{settings.file_format.lower()}"
                        file_path = output_path / filename

                        # Export
                        sf.write(
                            str(file_path),
                            loop_audio,
                            settings.sample_rate,
                            subtype=subtype,
                            format=settings.file_format
                        )

                        exported_count += 1
                        self.ctx.logger().info(f"Exported {stem_name} loop {loop_idx + 1}: {filename}")

            progress.setValue(total_files)
            progress.close()

            if exported_count > 0:
                mode_text = "mixed" if settings.export_mode == "mixed" else "individual"
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {exported_count} stretched loop file(s) ({mode_text} mode) to:\n{output_path}\n\n"
                    f"Target BPM: {target_bpm} (stretched from {settings.bpm} BPM)"
                )
                self.export_completed.emit(f"Exported {exported_count} stretched loops")
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "No loops were exported. Check the log for details."
                )

        except Exception as e:
            self.ctx.logger().error(f"Stretched loop export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during stretched loop export:\n{str(e)}",
            )

    # ========================================================================
    # Time-Stretching Signal Handlers
    # ========================================================================

    def _get_loop_segments(self):
        """Get loop segments from player widget or BPM detection"""
        # Try to get actual loop segments from player widget (Loop Preview)
        if self.player_widget and hasattr(self.player_widget, 'detected_downbeat_times'):
            downbeats = self.player_widget.detected_downbeat_times
            bars_per_loop = getattr(self.player_widget, '_bars_per_loop', 4)

            if downbeats is not None and len(downbeats) > 0:
                # Calculate loop segments from detected downbeats
                segments = []
                num_downbeats_per_loop = bars_per_loop  # 1 downbeat per bar

                # Create loops from consecutive downbeats
                for i in range(0, len(downbeats) - num_downbeats_per_loop, num_downbeats_per_loop):
                    start = downbeats[i]
                    end = downbeats[i + num_downbeats_per_loop]
                    segments.append((start, end))

                if segments:
                    self.ctx.logger().debug(
                        f"Using {len(segments)} detected loops from Loop Preview "
                        f"({bars_per_loop} bars each)"
                    )
                    return segments

        # Fallback: Create dummy loops based on BPM, but limit to audio duration
        bars = self._get_bars_from_player_widget()
        bpm = self._get_bpm_from_player_widget()

        # Calculate loop duration in seconds
        loop_duration = (bars * 4 * 60.0) / bpm

        # Get audio duration from player widget
        audio_duration = 0.0
        if self.player_widget and hasattr(self.player_widget, 'player'):
            audio_duration = self.player_widget.player.get_duration()

        if audio_duration <= 0:
            # No audio loaded, create default 8 loops
            audio_duration = loop_duration * 8

        # Calculate how many loops fit in the audio
        num_loops = max(1, int(audio_duration / loop_duration))

        segments = []
        for i in range(num_loops):
            start = i * loop_duration
            end = min((i + 1) * loop_duration, audio_duration)
            segments.append((start, end))

        self.ctx.logger().debug(
            f"Created {len(segments)} dummy loops (duration={audio_duration:.2f}s, "
            f"loop_duration={loop_duration:.2f}s)"
        )

        return segments

    def _get_stem_files_dict(self):
        """Get stem files as a dictionary {stem_name: Path}"""
        if not self.player_widget or not hasattr(self.player_widget, 'stem_files'):
            return {}

        stem_files = {}
        for stem_name, stem_path in self.player_widget.stem_files.items():
            if stem_path and Path(stem_path).exists():
                stem_files[stem_name] = Path(stem_path)

        return stem_files

    @Slot(int, int)
    def _on_stretch_progress_updated(self, completed: int, total: int):
        """
        Handle progress update from background stretch manager.
        
        PURPOSE: Update loop version checkbox state as stretching progresses
        CONTEXT: Progress updates come from player widget's stretch manager
        """
        # Update checkbox state as progress updates
        self._update_loop_version_checkbox_state()

    @Slot()
    def _on_stretch_all_completed(self):
        """
        Handle completion of all background stretching tasks.
        
        PURPOSE: Update loop version checkbox state when all loops are ready
        CONTEXT: Called when player widget's stretch manager completes all tasks
        """
        self.ctx.logger().info("Background stretching completed")
        # Update loop version checkbox state now that loops are ready
        self._update_loop_version_checkbox_state()

    @Slot(str, int, float)
    def _on_stretch_task_completed(self, stem_name: str, loop_index: int, target_bpm: float):
        """
        Handle completion of a single stretch task.
        
        PURPOSE: Update loop version checkbox state as individual tasks complete
        CONTEXT: Called when player widget's stretch manager completes a task
        """
        # Update checkbox state as tasks complete
        self._update_loop_version_checkbox_state()
