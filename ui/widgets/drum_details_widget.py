"""
Drum Details Widget - LARS drum separation interface

PURPOSE: Allow users to separate drum audio into 5 stems using LARS service
CONTEXT: Displayed in main content area when Drum Details is selected in sidebar
"""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox,
    QProgressBar, QLineEdit, QSlider, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot, QThread

from ui.app_context import AppContext
from ui.theme import ThemeManager
from utils.lars_service_client import (
    separate_drum_stems, is_lars_service_available,
    LarsServiceError, LarsServiceTimeout, LarsServiceNotFound,
    SeparationResult, SUPPORTED_STEMS
)


class SeparationWorker(QThread):
    """
    Background worker thread for LARS drum separation.

    Prevents UI blocking during long-running separation tasks.
    """
    # Signals
    progress_update = Signal(int, str)  # (percentage, status_message)
    finished = Signal(object)  # SeparationResult
    error = Signal(str)  # error message

    def __init__(self, input_path: Path, output_dir: Path,
                 stems: list, device: str, wiener_filter: bool):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.stems = stems
        self.device = device
        self.wiener_filter = wiener_filter
        self._cancelled = False

    def run(self):
        """Run separation in background thread."""
        try:
            self.progress_update.emit(10, "Starting LARS service...")

            # Run separation
            result = separate_drum_stems(
                input_path=self.input_path,
                output_dir=self.output_dir,
                stems=self.stems,
                device=self.device,
                wiener_filter=self.wiener_filter,
                timeout_seconds=300.0
            )

            if not self._cancelled:
                self.progress_update.emit(100, "Complete!")
                self.finished.emit(result)

        except LarsServiceNotFound as e:
            self.error.emit(f"LARS service not found: {e}")
        except LarsServiceTimeout:
            self.error.emit("Separation timed out (5 minutes)")
        except LarsServiceError as e:
            self.error.emit(f"Separation failed: {e}")
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")

    def cancel(self):
        """Cancel the separation."""
        self._cancelled = True
        self.requestInterruption()


class DrumStemControl(QWidget):
    """
    Individual drum stem control widget.

    Phase 1: UI-only placeholder (no audio playback)
    Future: Will integrate with audio player for mute/solo/volume
    """
    # Signals for future playback integration
    mute_toggled = Signal(str, bool)  # (stem_name, is_muted)
    solo_toggled = Signal(str, bool)  # (stem_name, is_solo)
    volume_changed = Signal(str, float)  # (stem_name, volume_0_to_1)

    def __init__(self, stem_name: str, stem_path: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self.stem_name = stem_name
        self.stem_path = stem_path
        self._setup_ui()

    def _setup_ui(self):
        """Setup stem control UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Stem name label
        name_label = QLabel(self.stem_name.capitalize())
        name_label.setMinimumWidth(80)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)

        # Mute button (Phase 1: disabled)
        self.btn_mute = QPushButton("M")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedSize(30, 30)
        self.btn_mute.setToolTip("Mute (not available in Phase 1)")
        self.btn_mute.setEnabled(False)
        layout.addWidget(self.btn_mute)

        # Solo button (Phase 1: disabled)
        self.btn_solo = QPushButton("S")
        self.btn_solo.setCheckable(True)
        self.btn_solo.setFixedSize(30, 30)
        self.btn_solo.setToolTip("Solo (not available in Phase 1)")
        self.btn_solo.setEnabled(False)
        layout.addWidget(self.btn_solo)

        # Volume slider (Phase 1: disabled)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.setToolTip("Volume (not available in Phase 1)")
        self.volume_slider.setEnabled(False)
        layout.addWidget(self.volume_slider)

        # Volume label
        self.volume_label = QLabel("100%")
        self.volume_label.setMinimumWidth(50)
        layout.addWidget(self.volume_label)

        # Connect signals (for future implementation)
        self.btn_mute.toggled.connect(lambda checked: self.mute_toggled.emit(self.stem_name, checked))
        self.btn_solo.toggled.connect(lambda checked: self.solo_toggled.emit(self.stem_name, checked))
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

    def _on_volume_changed(self, value: int):
        """Handle volume slider change."""
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(self.stem_name, value / 100.0)

    def set_stem_path(self, path: Path):
        """Update stem file path."""
        self.stem_path = path

    def get_stem_path(self) -> Optional[Path]:
        """Get stem file path."""
        return self.stem_path


class DrumDetailsWidget(QWidget):
    """
    Drum Details widget - LARS drum separation interface.

    Phase 1 Features:
    - File selection for drum audio
    - Device selection (Auto/MPS/CPU)
    - Wiener filter toggle
    - Separation progress tracking
    - 5 stem controls (UI-only placeholders)
    - Export stems button

    Future Phases:
    - Integrated playback (Phase 3)
    - Automatic workflow integration (Phase 3)
    - MIDI transcription (Phase 2)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()
        self.logger = self.ctx.logger()

        # State
        self.separation_result: Optional[SeparationResult] = None
        self.worker: Optional[SeparationWorker] = None
        self.input_file_path: Optional[Path] = None
        self.output_dir: Optional[Path] = None

        # Stem controls
        self.stem_controls = {}

        self._setup_ui()
        self._connect_signals()
        self._update_button_states()

        self.logger.info("DrumDetailsWidget initialized")

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
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Input Card ===
        input_card, input_layout = self._create_card("Input Audio")

        file_row = QHBoxLayout()
        file_row.setSpacing(10)

        file_label = QLabel("Drum Audio:")
        file_label.setMinimumWidth(100)
        file_row.addWidget(file_label)

        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("Select drum audio file...")
        self.input_path_edit.setMinimumHeight(35)
        self.input_path_edit.setReadOnly(True)
        file_row.addWidget(self.input_path_edit)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setMinimumHeight(35)
        self.btn_browse.setMinimumWidth(100)
        file_row.addWidget(self.btn_browse)

        input_layout.addLayout(file_row)

        # Info label
        info_label = QLabel(
            "ℹ️ Select a drum stem or audio file containing drums to separate into "
            "Kick, Snare, Toms, Hi-Hat, and Cymbals."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        input_layout.addWidget(info_label)

        main_layout.addWidget(input_card)

        # === Separation Settings Card ===
        settings_card, settings_layout = self._create_card("Separation Settings")

        settings_row = QHBoxLayout()
        settings_row.setSpacing(30)

        # Device selection
        device_col = QHBoxLayout()
        device_label = QLabel("Device:")
        device_label.setMinimumWidth(80)
        device_col.addWidget(device_label)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["Auto", "MPS", "CPU"])
        self.device_combo.setMinimumHeight(35)
        self.device_combo.setMinimumWidth(120)
        self.device_combo.setToolTip(
            "Auto: Automatically select best device\n"
            "MPS: Apple Silicon GPU\n"
            "CPU: CPU processing"
        )
        device_col.addWidget(self.device_combo)
        device_col.addStretch()
        settings_row.addLayout(device_col)

        # Wiener filter
        self.wiener_filter_checkbox = QCheckBox("Enable Wiener Filter")
        self.wiener_filter_checkbox.setToolTip(
            "Improves separation quality at the cost of processing time"
        )
        settings_row.addWidget(self.wiener_filter_checkbox)
        settings_row.addStretch()

        settings_layout.addLayout(settings_row)

        # Separate button
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.btn_separate = QPushButton("🥁 Separate Drums")
        self.btn_separate.setMinimumWidth(180)
        self.btn_separate.setMinimumHeight(40)
        ThemeManager.set_widget_property(self.btn_separate, "buttonStyle", "primary")
        button_row.addWidget(self.btn_separate)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setVisible(False)
        button_row.addWidget(self.btn_cancel)

        button_row.addStretch()
        settings_layout.addLayout(button_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        settings_layout.addWidget(self.progress_bar)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        self.status_label.setVisible(False)
        settings_layout.addWidget(self.status_label)

        main_layout.addWidget(settings_card)

        # === Results Card ===
        results_card, results_layout = self._create_card("Drum Stems")

        results_info = QLabel(
            "Separated drum stems will appear here. "
            "Phase 1: Playback controls are placeholders."
        )
        results_info.setWordWrap(True)
        results_info.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11pt;")
        results_layout.addWidget(results_info)

        # Stem controls container
        self.stems_container = QGroupBox()
        stems_layout = QVBoxLayout(self.stems_container)
        stems_layout.setSpacing(5)

        # Create stem controls for all supported stems
        for stem_name in SUPPORTED_STEMS:
            control = DrumStemControl(stem_name)
            self.stem_controls[stem_name] = control
            stems_layout.addWidget(control)

        self.stems_container.setVisible(False)
        results_layout.addWidget(self.stems_container)

        main_layout.addWidget(results_card)

        # Stretch to push export button to bottom
        main_layout.addStretch()

        # === Export Button ===
        export_layout = QHBoxLayout()
        export_layout.addStretch()

        self.btn_export = QPushButton("💾 Export Stems")
        self.btn_export.setMinimumWidth(150)
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_export, "buttonStyle", "primary")
        self.btn_export.setToolTip("Open folder containing separated stems")
        export_layout.addWidget(self.btn_export)

        export_layout.addStretch()
        main_layout.addLayout(export_layout)

        # Check LARS service availability
        self._check_lars_availability()

    def _connect_signals(self):
        """Connect UI signals."""
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        self.btn_separate.clicked.connect(self._on_separate_clicked)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.input_path_edit.textChanged.connect(self._update_button_states)

    def _check_lars_availability(self):
        """Check if LARS service is available."""
        if not is_lars_service_available():
            self.logger.warning("LARS service binary not found")
            self.btn_separate.setEnabled(False)
            self.btn_separate.setText("⚠️ LARS Service Not Found")
            self.btn_separate.setToolTip(
                "LARS service binary not found. "
                "Build it with: cd packaging/lars_service && ./build.sh"
            )

    def _update_button_states(self):
        """Update button enabled states."""
        has_input = bool(self.input_path_edit.text())
        lars_available = is_lars_service_available()

        self.btn_separate.setEnabled(has_input and lars_available)
        self.btn_export.setEnabled(self.separation_result is not None)

    @Slot()
    def _on_browse_clicked(self):
        """Handle browse button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Drum Audio File",
            str(Path.home()),
            "Audio Files (*.wav *.flac *.mp3 *.m4a *.ogg);;All Files (*)"
        )

        if file_path:
            self.input_file_path = Path(file_path)
            self.input_path_edit.setText(str(self.input_file_path))
            self.logger.info(f"Selected input file: {self.input_file_path}")

    @Slot()
    def _on_separate_clicked(self):
        """Handle separate drums button click."""
        if not self.input_file_path or not self.input_file_path.exists():
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please select a valid audio file."
            )
            return

        # Create output directory
        self.output_dir = self.input_file_path.parent / f"{self.input_file_path.stem}_drums"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Get settings
        device_map = {"Auto": "auto", "MPS": "mps", "CPU": "cpu"}
        device = device_map[self.device_combo.currentText()]
        wiener_filter = self.wiener_filter_checkbox.isChecked()

        self.logger.info(
            f"Starting drum separation: {self.input_file_path.name} "
            f"(device={device}, wiener={wiener_filter})"
        )

        # Update UI for processing
        self.btn_separate.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Initializing...")
        self.stems_container.setVisible(False)

        # Start worker
        self.worker = SeparationWorker(
            input_path=self.input_file_path,
            output_dir=self.output_dir,
            stems=SUPPORTED_STEMS,
            device=device,
            wiener_filter=wiener_filter
        )

        self.worker.progress_update.connect(self._on_progress_update)
        self.worker.finished.connect(self._on_separation_finished)
        self.worker.error.connect(self._on_separation_error)
        self.worker.start()

    @Slot()
    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(5000)  # Wait up to 5 seconds
            self.logger.info("Separation cancelled by user")

        self._reset_ui_state()

    @Slot(int, str)
    def _on_progress_update(self, percentage: int, message: str):
        """Handle progress update from worker."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)

    @Slot(object)
    def _on_separation_finished(self, result: SeparationResult):
        """Handle successful separation."""
        self.separation_result = result

        self.logger.info(
            f"Separation complete: {result.processing_time:.1f}s on {result.backend}"
        )

        # Update stem controls with paths
        for stem_name in SUPPORTED_STEMS:
            path = result.stems.get(stem_name)
            if path:
                self.stem_controls[stem_name].set_stem_path(path)

        # Show results
        self.stems_container.setVisible(True)

        # Reset UI
        self._reset_ui_state(show_success=True)

        # Show success message
        QMessageBox.information(
            self,
            "Separation Complete",
            f"Drum stems separated successfully!\n\n"
            f"Processing time: {result.processing_time:.1f}s\n"
            f"Backend: {result.backend}\n"
            f"Output: {self.output_dir}"
        )

    @Slot(str)
    def _on_separation_error(self, error_message: str):
        """Handle separation error."""
        self.logger.error(f"Separation error: {error_message}")

        self._reset_ui_state()

        QMessageBox.critical(
            self,
            "Separation Failed",
            f"Drum separation failed:\n\n{error_message}"
        )

    def _reset_ui_state(self, show_success: bool = False):
        """Reset UI to initial state."""
        self.btn_separate.setVisible(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)

        if show_success:
            self.status_label.setText("✓ Separation complete!")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.status_label.setVisible(False)

        self._update_button_states()

    @Slot()
    def _on_export_clicked(self):
        """Handle export button click."""
        if not self.output_dir or not self.output_dir.exists():
            QMessageBox.warning(
                self,
                "No Output",
                "No separated stems available to export."
            )
            return

        # Open output directory in file manager
        import subprocess
        import sys

        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", str(self.output_dir)])
            elif sys.platform == "win32":  # Windows
                subprocess.Popen(["explorer", str(self.output_dir)])
            else:  # Linux
                subprocess.Popen(["xdg-open", str(self.output_dir)])

            self.logger.info(f"Opened output directory: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to open directory: {e}")
            QMessageBox.information(
                self,
                "Export Location",
                f"Stems exported to:\n{self.output_dir}"
            )

    def refresh(self):
        """Refresh widget state (called when navigating to this page)."""
        self._update_button_states()
        self._check_lars_availability()
