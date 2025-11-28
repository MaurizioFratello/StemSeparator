"""
Export Settings Dialog - Configure audio export with chunk splitting options

PURPOSE: Allow users to configure export settings including chunk splitting for samplers
CONTEXT: Used when exporting mixed or individual stems from the Player
"""
from pathlib import Path
from typing import Optional, NamedTuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QGroupBox,
    QRadioButton, QButtonGroup, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize


class ExportSettings(NamedTuple):
    """Export settings data"""
    file_format: str  # 'WAV' or 'FLAC'
    bit_depth: int  # 16, 24, or 32
    enable_chunking: bool  # Split into chunks?
    chunk_length: float  # Chunk length in seconds
    export_mode: str  # 'mixed' or 'individual'


class ExportSettingsDialog(QDialog):
    """
    Dialog for configuring export settings

    Features:
    - Chunk splitting enable/disable
    - Configurable chunk length
    - File format selection (WAV/FLAC)
    - Bit depth selection (16/24/32)
    - Export mode (Mixed vs Individual Stems)
    - Preview of number of chunks
    """

    def __init__(self, duration_seconds: float, num_stems: int, parent=None):
        """
        Initialize export settings dialog

        Args:
            duration_seconds: Total duration of audio in seconds
            num_stems: Number of loaded stems
            parent: Parent widget
        """
        super().__init__(parent)
        self.duration_seconds = duration_seconds
        self.num_stems = num_stems

        self.setWindowTitle("Export Settings")
        self.setModal(True)
        self.setMinimumWidth(594)  # 660 - 10%
        self.setMinimumHeight(633)  # 575 + 10%

        # Set a comfortable initial size (width -10%, height +10% from previous)
        self.resize(644, 696)

        self._setup_ui()
        self._connect_signals()
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
        header.setFixedHeight(30)  # Fixed height for consistent sizing
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Consistent alignment
        layout.addWidget(header)

        return card, layout

    def _setup_ui(self):
        """Setup dialog UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === File Format (full width) ===
        format_card, format_layout = self._create_card("File Format")

        # Create horizontal layout for format options
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
        self.format_combo.setMinimumWidth(120)  # Ensure readable width
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
        self.bit_depth_combo.setMinimumWidth(120)  # Ensure readable width
        depth_col.addWidget(self.bit_depth_combo)
        depth_col.addStretch()
        format_options_row.addLayout(depth_col)

        format_layout.addLayout(format_options_row)

        main_layout.addWidget(format_card)

        # === Export Mode (full width) ===
        mode_card, mode_layout = self._create_card("Export Mode")

        self.mode_button_group = QButtonGroup(self)

        # Create horizontal layout for radio buttons
        mode_options_row = QHBoxLayout()
        mode_options_row.setSpacing(30)

        self.mode_mixed = QRadioButton("Mixed Audio (all stems combined)")
        self.mode_mixed.setChecked(True)
        self.mode_button_group.addButton(self.mode_mixed)
        mode_options_row.addWidget(self.mode_mixed)

        self.mode_individual = QRadioButton(f"Individual Stems ({self.num_stems} separate files)")
        self.mode_button_group.addButton(self.mode_individual)
        mode_options_row.addWidget(self.mode_individual)

        mode_options_row.addStretch()

        mode_layout.addLayout(mode_options_row)

        main_layout.addWidget(mode_card)

        # === ROW 2: Chunk Splitting ===
        chunk_card, chunk_layout = self._create_card("Chunk Splitting")

        # Enable chunking checkbox
        self.enable_chunking = QCheckBox("Enable Chunk Splitting for Samplers")
        self.enable_chunking.setToolTip(
            "Split exported audio into smaller chunks for sampler compatibility"
        )
        chunk_layout.addWidget(self.enable_chunking)

        # Chunk length
        length_row = QHBoxLayout()
        length_label = QLabel("Chunk Length:")
        length_label.setMinimumWidth(110)
        length_row.addWidget(length_label)
        self.chunk_length = QDoubleSpinBox()
        self.chunk_length.setMinimum(0.5)  # Minimum 0.5 seconds
        self.chunk_length.setMaximum(300.0)  # Max 5 minutes per chunk
        self.chunk_length.setValue(20.0)  # Default: 20 seconds
        self.chunk_length.setSuffix(" seconds")
        self.chunk_length.setDecimals(1)  # One decimal place
        self.chunk_length.setSingleStep(0.5)  # Increment by 0.5 seconds
        self.chunk_length.setMinimumHeight(35)
        self.chunk_length.setMaximumWidth(200)
        self.chunk_length.setEnabled(False)  # Disabled until checkbox is checked
        self.chunk_length.setButtonSymbols(QDoubleSpinBox.UpDownArrows)
        # Add tooltips for clear +/- indication
        self.chunk_length.setToolTip(
            "Use arrows to adjust chunk length:\n"
            "▲ (Up) = Increase by 0.5s\n"
            "▼ (Down) = Decrease by 0.5s"
        )
        # Improve spinbox readability and button visibility
        self.chunk_length.setStyleSheet("""
            QDoubleSpinBox {
                padding: 5px 10px;
                font-size: 13pt;
            }
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid rgba(255, 255, 255, 0.2);
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid rgba(255, 255, 255, 0.2);
            }
            QDoubleSpinBox::up-arrow {
                width: 7px;
                height: 7px;
            }
            QDoubleSpinBox::down-arrow {
                width: 7px;
                height: 7px;
            }
        """)
        length_row.addWidget(self.chunk_length)
        length_row.addStretch()
        chunk_layout.addLayout(length_row)

        # Info label
        info_label = QLabel(
            "ℹ️ Chunks split at zero-crossings to prevent clicks. "
            "May be slightly shorter than specified."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        chunk_layout.addWidget(info_label)

        main_layout.addWidget(chunk_card)

        # === ROW 3: Preview ===
        preview_card, preview_layout = self._create_card("Preview")

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(50)
        self.preview_label.setStyleSheet("padding: 5px; color: rgba(255, 255, 255, 0.9);")
        preview_layout.addWidget(self.preview_label)

        main_layout.addWidget(preview_card)

        # Add stretch to push buttons to bottom
        main_layout.addStretch()

        # === Dialog Buttons ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(35)

        self.btn_ok = QPushButton("Export")
        self.btn_ok.setMinimumWidth(100)
        self.btn_ok.setMinimumHeight(35)
        self.btn_ok.setDefault(True)

        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_ok)

        main_layout.addLayout(buttons_layout)

    def _connect_signals(self):
        """Connect UI signals"""
        self.enable_chunking.toggled.connect(self._on_chunking_toggled)
        self.chunk_length.valueChanged.connect(self._update_preview)
        self.mode_button_group.buttonToggled.connect(self._update_preview)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_chunking_toggled(self, checked: bool):
        """Handle chunk splitting toggle"""
        self.chunk_length.setEnabled(checked)
        self._update_preview()

    def _update_preview(self):
        """Update preview label with estimated output"""
        if not self.enable_chunking.isChecked():
            # No chunking
            if self.mode_individual.isChecked():
                preview = f"Will export {self.num_stems} individual stem file(s)"
            else:
                preview = "Will export 1 mixed audio file"
        else:
            # With chunking
            chunk_len = self.chunk_length.value()
            chunks_per_file = int(self.duration_seconds / chunk_len) + (1 if self.duration_seconds % chunk_len > 0 else 0)

            if self.mode_individual.isChecked():
                total_files = self.num_stems * chunks_per_file
                preview = (
                    f"Will export {self.num_stems} stems × {chunks_per_file} chunks = "
                    f"{total_files} total files\n"
                    f"(e.g., vocals_1.wav, vocals_2.wav, ..., drums_1.wav, drums_2.wav, ...)"
                )
            else:
                preview = (
                    f"Will export {chunks_per_file} chunk file(s)\n"
                    f"(e.g., mixed_1.wav, mixed_2.wav, mixed_3.wav, ...)"
                )

        self.preview_label.setText(preview)

    def get_settings(self) -> ExportSettings:
        """
        Get export settings from dialog

        Returns:
            ExportSettings with user's choices
        """
        # Parse bit depth
        bit_depth_text = self.bit_depth_combo.currentText()
        bit_depth = int(bit_depth_text.split()[0])  # "24 bit" -> 24

        # Export mode
        export_mode = "individual" if self.mode_individual.isChecked() else "mixed"

        return ExportSettings(
            file_format=self.format_combo.currentText(),
            bit_depth=bit_depth,
            enable_chunking=self.enable_chunking.isChecked(),
            chunk_length=self.chunk_length.value(),
            export_mode=export_mode
        )


if __name__ == "__main__":
    """Test the dialog"""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # Test with 180 second audio, 4 stems
    dialog = ExportSettingsDialog(duration_seconds=180.0, num_stems=4)

    if dialog.exec() == QDialog.Accepted:
        settings = dialog.get_settings()
        print("Export Settings:")
        print(f"  Format: {settings.file_format}")
        print(f"  Bit Depth: {settings.bit_depth}")
        print(f"  Chunking: {settings.enable_chunking}")
        print(f"  Chunk Length: {settings.chunk_length}s")
        print(f"  Export Mode: {settings.export_mode}")
    else:
        print("Export cancelled")
