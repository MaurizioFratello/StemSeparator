"""
Export Mixed Widget - Configure and execute mixed audio export

PURPOSE: Allow users to configure export settings and export mixed/individual stems
CONTEXT: Displayed in main content area when Export Mixed is selected in sidebar
"""
from pathlib import Path
from typing import Optional, NamedTuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QDoubleSpinBox, QComboBox, QPushButton, QRadioButton,
    QButtonGroup, QFrame, QFileDialog, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal, Slot

from ui.app_context import AppContext
from ui.theme import ThemeManager


class ExportSettings(NamedTuple):
    """Export settings data"""
    file_format: str  # 'WAV' or 'FLAC'
    bit_depth: int  # 16, 24, or 32
    enable_chunking: bool  # Split into chunks?
    chunk_length: float  # Chunk length in seconds
    export_mode: str  # 'mixed' or 'individual'


class ExportMixedWidget(QWidget):
    """
    Widget for configuring and executing mixed audio export.
    
    PURPOSE: Replaces ExportSettingsDialog as embedded content in main window
    CONTEXT: Shown when user clicks "Export Mixed" in sidebar
    
    Features:
    - File format selection (WAV/FLAC)
    - Bit depth selection (16/24/32)
    - Chunk splitting enable/disable
    - Export mode (Mixed vs Individual Stems)
    - Preview of output files
    - Direct export execution
    """
    
    # Signal emitted when export completes successfully
    export_completed = Signal(str)  # success message

    def __init__(self, player_widget=None, parent=None):
        """
        Initialize export mixed widget.
        
        Args:
            player_widget: Reference to PlayerWidget for accessing stems and export logic
            parent: Parent widget
        """
        super().__init__(parent)
        self.ctx = AppContext()
        self.player_widget = player_widget
        
        self._setup_ui()
        self._connect_signals()
        self._update_preview()
        self._update_export_button_state()
        
        self.ctx.logger().info("ExportMixedWidget initialized")

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

        # === File Format Card ===
        format_card, format_layout = self._create_card("File Format")

        format_options_row = QHBoxLayout()
        format_options_row.setSpacing(20)

        # Format selection
        format_col = QHBoxLayout()
        format_label = QLabel("Format:")
        format_label.setMinimumWidth(80)
        format_col.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["WAV", "FLAC"])
        self.format_combo.setMinimumHeight(35)
        self.format_combo.setMinimumWidth(120)
        format_col.addWidget(self.format_combo)
        format_col.addStretch()
        format_options_row.addLayout(format_col)

        # Bit depth selection
        depth_col = QHBoxLayout()
        depth_label = QLabel("Bit Depth:")
        depth_label.setMinimumWidth(80)
        depth_col.addWidget(depth_label)
        self.bit_depth_combo = QComboBox()
        self.bit_depth_combo.addItems(["16 bit", "24 bit", "32 bit"])
        self.bit_depth_combo.setCurrentIndex(1)  # Default: 24 bit
        self.bit_depth_combo.setMinimumHeight(35)
        self.bit_depth_combo.setMinimumWidth(120)
        depth_col.addWidget(self.bit_depth_combo)
        depth_col.addStretch()
        format_options_row.addLayout(depth_col)

        format_layout.addLayout(format_options_row)
        main_layout.addWidget(format_card)

        # === Export Mode Card ===
        mode_card, mode_layout = self._create_card("Export Mode")

        self.mode_button_group = QButtonGroup(self)

        mode_options_row = QHBoxLayout()
        mode_options_row.setSpacing(30)

        self.mode_mixed = QRadioButton("Mixed Audio (all stems combined)")
        self.mode_mixed.setChecked(True)
        self.mode_button_group.addButton(self.mode_mixed)
        mode_options_row.addWidget(self.mode_mixed)

        self.mode_individual = QRadioButton("Individual Stems")
        self.mode_button_group.addButton(self.mode_individual)
        mode_options_row.addWidget(self.mode_individual)

        mode_options_row.addStretch()
        mode_layout.addLayout(mode_options_row)
        main_layout.addWidget(mode_card)

        # === Chunk Splitting Card ===
        chunk_card, chunk_layout = self._create_card("Chunk Splitting")

        self.enable_chunking = QCheckBox("Enable Chunk Splitting for Samplers")
        self.enable_chunking.setToolTip(
            "Split exported audio into smaller chunks for sampler compatibility"
        )
        chunk_layout.addWidget(self.enable_chunking)

        length_row = QHBoxLayout()
        length_label = QLabel("Chunk Length:")
        length_label.setMinimumWidth(110)
        length_row.addWidget(length_label)
        
        self.chunk_length = QDoubleSpinBox()
        self.chunk_length.setMinimum(0.5)
        self.chunk_length.setMaximum(300.0)
        self.chunk_length.setValue(20.0)
        self.chunk_length.setSuffix(" seconds")
        self.chunk_length.setDecimals(1)
        self.chunk_length.setSingleStep(0.5)
        self.chunk_length.setMinimumHeight(35)
        self.chunk_length.setMaximumWidth(200)
        self.chunk_length.setEnabled(False)
        length_row.addWidget(self.chunk_length)
        length_row.addStretch()
        chunk_layout.addLayout(length_row)

        info_label = QLabel(
            "ℹ️ Chunks split at zero-crossings to prevent clicks. "
            "May be slightly shorter than specified."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        chunk_layout.addWidget(info_label)

        main_layout.addWidget(chunk_card)

        # === Preview Card ===
        preview_card, preview_layout = self._create_card("Preview")

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(50)
        self.preview_label.setStyleSheet("padding: 5px; color: rgba(255, 255, 255, 0.9);")
        preview_layout.addWidget(self.preview_label)

        main_layout.addWidget(preview_card)

        # Stretch to push button to bottom
        main_layout.addStretch()

        # === Export Button ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.btn_export = QPushButton("💾 Export Now")
        self.btn_export.setMinimumWidth(150)
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_export, "buttonStyle", "primary")
        buttons_layout.addWidget(self.btn_export)

        main_layout.addLayout(buttons_layout)

    def _connect_signals(self):
        """Connect UI signals"""
        self.enable_chunking.toggled.connect(self._on_chunking_toggled)
        self.chunk_length.valueChanged.connect(self._update_preview)
        self.mode_button_group.buttonToggled.connect(self._update_preview)
        self.format_combo.currentIndexChanged.connect(self._update_preview)
        self.bit_depth_combo.currentIndexChanged.connect(self._update_preview)
        
        self.btn_export.clicked.connect(self._on_export_clicked)

    def _on_chunking_toggled(self, checked: bool):
        """Handle chunk splitting toggle"""
        self.chunk_length.setEnabled(checked)
        self._update_preview()

    def _update_export_button_state(self):
        """Update export button enabled state based on stems availability"""
        has_stems = (
            self.player_widget is not None and
            self.player_widget.has_stems_loaded()
        )
        self.btn_export.setEnabled(has_stems)

        if has_stems:
            num_stems = len(self.player_widget.stem_files)
            # Update individual mode label with stem count
            self.mode_individual.setText(f"Individual Stems ({num_stems} separate files)")
        else:
            self.mode_individual.setText("Individual Stems")

    def _update_preview(self):
        """Update preview label with estimated output"""
        if not self.player_widget or not self.player_widget.has_stems_loaded():
            self.preview_label.setText("Load stems to see preview")
            return
            
        num_stems = len(self.player_widget.stem_files)
        duration_seconds = self.player_widget.player.get_duration()
        
        if not self.enable_chunking.isChecked():
            if self.mode_individual.isChecked():
                preview = f"Will export {num_stems} individual stem file(s)"
            else:
                preview = "Will export 1 mixed audio file"
        else:
            chunk_len = self.chunk_length.value()
            chunks_per_file = int(duration_seconds / chunk_len)
            if duration_seconds % chunk_len > 0:
                chunks_per_file += 1

            if self.mode_individual.isChecked():
                total_files = num_stems * chunks_per_file
                preview = (
                    f"Will export {num_stems} stems × {chunks_per_file} chunks = "
                    f"{total_files} total files\n"
                    f"(e.g., vocals_01.wav, vocals_02.wav, ..., drums_01.wav, drums_02.wav, ...)"
                )
            else:
                preview = (
                    f"Will export {chunks_per_file} chunk file(s)\n"
                    f"(e.g., mixed_01.wav, mixed_02.wav, mixed_03.wav, ...)"
                )

        self.preview_label.setText(preview)

    def refresh(self):
        """Refresh the widget state (called when navigating to this page)"""
        self._update_export_button_state()
        self._update_preview()

    def get_settings(self) -> ExportSettings:
        """Get export settings from widget"""
        bit_depth_text = self.bit_depth_combo.currentText()
        bit_depth = int(bit_depth_text.split()[0])

        export_mode = "individual" if self.mode_individual.isChecked() else "mixed"

        return ExportSettings(
            file_format=self.format_combo.currentText(),
            bit_depth=bit_depth,
            enable_chunking=self.enable_chunking.isChecked(),
            chunk_length=self.chunk_length.value(),
            export_mode=export_mode
        )

    @Slot()
    def _on_export_clicked(self):
        """Handle export button click - execute the export"""
        if not self.player_widget or not self.player_widget.has_stems_loaded():
            QMessageBox.warning(
                self,
                "No Stems Loaded",
                "Please load stems in the Stems tab before exporting."
            )
            return

        settings = self.get_settings()
        
        # Ask user for output location
        if settings.enable_chunking and settings.export_mode == 'individual':
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory for Stem Chunks",
                ""
            )
            if not output_dir:
                return
            output_path = Path(output_dir)
        else:
            extension = f".{settings.file_format.lower()}"
            filter_str = f"{settings.file_format} Files (*{extension})"

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Audio",
                "",
                filter_str
            )
            if not save_path:
                return
            output_path = Path(save_path)

        # Execute export
        self._execute_export(output_path, settings)

    def _execute_export(self, output_path: Path, settings: ExportSettings):
        """Execute the export with given settings"""
        success = False
        result_message = ""
        
        # Get common filename from player widget
        common_filename = self.player_widget._get_common_filename()

        try:
            player = self.player_widget.player
            
            if settings.enable_chunking:
                if settings.export_mode == 'mixed':
                    chunk_paths = player.export_mix_chunked(
                        output_path,
                        settings.chunk_length,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
                        common_filename=common_filename
                    )

                    if chunk_paths:
                        success = True
                        result_message = (
                            f"Mixed audio exported as {len(chunk_paths)} chunks:\n"
                            f"{output_path.parent}"
                        )
                    else:
                        result_message = "Failed to export chunks. Check the log for details."
                else:
                    all_chunks = player.export_stems_chunked(
                        output_path,
                        settings.chunk_length,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
                        common_filename=common_filename
                    )

                    if all_chunks:
                        success = True
                        total_files = sum(len(chunks) for chunks in all_chunks.values())
                        result_message = (
                            f"Exported {len(all_chunks)} stems as {total_files} total chunks:\n"
                            f"{output_path}"
                        )
                    else:
                        result_message = "Failed to export stem chunks. Check the log for details."
            else:
                if settings.export_mode == 'mixed':
                    success = player.export_mix(
                        output_path,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth
                    )

                    if success:
                        result_message = f"Mixed audio exported to:\n{output_path}"
                    else:
                        result_message = "Failed to export mixed audio. Check the log for details."
                else:
                    all_chunks = player.export_stems_chunked(
                        output_path,
                        chunk_length_seconds=999999,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth
                    )

                    if all_chunks:
                        success = True
                        result_message = (
                            f"Exported {len(all_chunks)} individual stems:\n"
                            f"{output_path}"
                        )
                    else:
                        result_message = "Failed to export stems. Check the log for details."

            if success:
                QMessageBox.information(self, "Export Successful", result_message)
                self.export_completed.emit(result_message)
            else:
                QMessageBox.critical(self, "Export Failed", result_message)

        except Exception as e:
            self.ctx.logger().error(f"Export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during export:\n{str(e)}"
            )

