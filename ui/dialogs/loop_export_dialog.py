"""
Loop Export Dialog - Configure sampler loop export settings

PURPOSE: Allow users to configure BPM-based loop export for samplers
CONTEXT: Used when exporting audio from Player as musical loops (2/4/8 bars)
"""
from pathlib import Path
from typing import Optional, NamedTuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QPushButton, QGroupBox, QRadioButton, QButtonGroup,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt

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
        detected_bpm: Optional[float] = None,
        duration_seconds: float = 0.0,
        num_stems: int = 1,
        parent=None
    ):
        """
        Initialize loop export dialog.

        Args:
            detected_bpm: Auto-detected BPM (optional, will be rounded to int)
            duration_seconds: Total duration of audio in seconds (for preview)
            num_stems: Number of loaded stems (for individual export preview)
            parent: Parent widget
        """
        super().__init__(parent)
        self.duration_seconds = duration_seconds
        self.num_stems = num_stems
        self.detected_bpm = round(detected_bpm) if detected_bpm else 120

        self.setWindowTitle("Sampler Loop Export")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.setMinimumHeight(600)

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
        """Setup dialog UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === BPM Settings ===
        bpm_card, bpm_layout = self._create_card("Tempo (BPM)")

        bpm_row = QHBoxLayout()
        bpm_label = QLabel("BPM:")
        bpm_label.setMinimumWidth(100)
        bpm_row.addWidget(bpm_label)

        self.bpm_spin = QSpinBox()
        self.bpm_spin.setMinimum(1)
        self.bpm_spin.setMaximum(999)
        self.bpm_spin.setValue(self.detected_bpm)
        self.bpm_spin.setSuffix(" BPM")
        self.bpm_spin.setMinimumHeight(35)
        self.bpm_spin.setMinimumWidth(150)
        bpm_row.addWidget(self.bpm_spin)

        bpm_row.addStretch()
        bpm_layout.addLayout(bpm_row)

        # BPM info label
        self.bpm_info_label = QLabel(
            f"💡 Auto-detected: {self.detected_bpm} BPM (editable)"
        )
        self.bpm_info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        bpm_layout.addWidget(self.bpm_info_label)

        main_layout.addWidget(bpm_card)

        # === Export Mode ===
        mode_card, mode_layout = self._create_card("Export Mode")

        self.mode_button_group = QButtonGroup(self)

        # Create horizontal layout for radio buttons
        mode_options_row = QHBoxLayout()
        mode_options_row.setSpacing(30)

        self.mode_mixed = QRadioButton("Mixed Audio (all stems combined)")
        self.mode_mixed.setChecked(True)
        self.mode_button_group.addButton(self.mode_mixed)
        mode_options_row.addWidget(self.mode_mixed)

        self.mode_individual = QRadioButton(f"Individual Stems ({self.num_stems} separate sets)")
        self.mode_button_group.addButton(self.mode_individual)
        mode_options_row.addWidget(self.mode_individual)

        mode_options_row.addStretch()

        mode_layout.addLayout(mode_options_row)

        main_layout.addWidget(mode_card)

        # === Bar Length ===
        bars_card, bars_layout = self._create_card("Loop Length")

        self.bars_button_group = QButtonGroup(self)

        bars_options_row = QHBoxLayout()
        bars_options_row.setSpacing(20)

        self.bars_2 = QRadioButton("2 bars")
        self.bars_button_group.addButton(self.bars_2)
        bars_options_row.addWidget(self.bars_2)

        self.bars_4 = QRadioButton("4 bars")
        self.bars_4.setChecked(True)  # Default
        self.bars_button_group.addButton(self.bars_4)
        bars_options_row.addWidget(self.bars_4)

        self.bars_8 = QRadioButton("8 bars")
        self.bars_button_group.addButton(self.bars_8)
        bars_options_row.addWidget(self.bars_8)

        bars_options_row.addStretch()
        bars_layout.addLayout(bars_options_row)

        # Validation label (updated dynamically)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("padding: 5px;")
        bars_layout.addWidget(self.validation_label)

        main_layout.addWidget(bars_card)

        # === Audio Format ===
        format_card, format_layout = self._create_card("Audio Format")

        # Sample rate
        sr_row = QHBoxLayout()
        sr_label = QLabel("Sample Rate:")
        sr_label.setMinimumWidth(100)
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
        depth_label.setMinimumWidth(100)
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
        channels_label.setMinimumWidth(100)
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
        fmt_label.setMinimumWidth(100)
        fmt_row.addWidget(fmt_label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["WAV", "AIFF", "FLAC"])
        self.format_combo.setCurrentIndex(0)  # Default: WAV
        self.format_combo.setMinimumHeight(35)
        fmt_row.addWidget(self.format_combo)

        fmt_row.addStretch()
        format_layout.addLayout(fmt_row)

        main_layout.addWidget(format_card)

        # === Preview ===
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
        self.bars_button_group.buttonToggled.connect(self._on_settings_changed)
        self.mode_button_group.buttonToggled.connect(self._on_settings_changed)
        self.sample_rate_combo.currentIndexChanged.connect(self._on_settings_changed)

        self.btn_export.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_settings_changed(self):
        """Handle any settings change"""
        self._update_validation()
        self._update_preview()

    def _get_selected_bars(self) -> int:
        """Get currently selected bar count"""
        if self.bars_2.isChecked():
            return 2
        elif self.bars_4.isChecked():
            return 4
        elif self.bars_8.isChecked():
            return 8
        return 4  # Fallback

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
                f"⚠ {error_msg}\n"
                f"Minimum BPM for {bars} bars: {min_bpm}"
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

        from utils.loop_math import compute_chunk_duration_seconds, compute_samples_per_chunk

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


if __name__ == "__main__":
    """Test the dialog"""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # Test with detected BPM of 128.5 (will be rounded to 129)
    # and 180 second audio
    dialog = LoopExportDialog(detected_bpm=128.5, duration_seconds=180.0)

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
