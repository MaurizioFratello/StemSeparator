"""
Settings Dialog - User preferences configuration

PURPOSE: Provide GUI for modifying application settings.
CONTEXT: Settings dialog accessible from main menu.
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QPushButton,
    QLabel,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QLineEdit,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QRunnable, QThreadPool, QObject
from PySide6.QtGui import QDesktopServices

from ui.app_context import AppContext
from ui.settings_manager import get_settings_manager
from ui.theme import ThemeManager
from config import QUALITY_PRESETS


class BlackHoleInstallWorker(QRunnable):
    """
    Background worker for BlackHole installation

    PURPOSE: Install BlackHole without blocking GUI thread
    CONTEXT: Installation can take minutes and requires shell commands
    """

    class Signals(QObject):
        progress = Signal(str)  # message
        finished = Signal(bool, str)  # success, error_msg

    def __init__(self, blackhole_installer):
        super().__init__()
        self.blackhole_installer = blackhole_installer
        self.signals = self.Signals()

    def run(self):
        """Execute installation in background"""
        try:

            def progress_callback(message: str):
                self.signals.progress.emit(message)

            success, error_msg = self.blackhole_installer.install_blackhole(
                progress_callback
            )
            self.signals.finished.emit(success, error_msg or "")
        except Exception as e:
            self.signals.finished.emit(False, str(e))


class SettingsDialog(QDialog):
    """
    Dialog for configuring application settings

    Features:
    - Default model
    - GPU usage toggle
    - Chunk size configuration
    - Output directory
    - Recording settings
    - Diagnostics (log file access)
    """

    # Signal emitted when settings are saved
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()
        self.settings_mgr = get_settings_manager()
        self.blackhole_installer = self.ctx.blackhole_installer()

        # Thread pool for background tasks
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()

        self.ctx.logger().info("SettingsDialog initialized")

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
        """Setup dialog layout"""
        layout = QVBoxLayout(self)

        # Tab widget for categories
        self.tabs = QTabWidget()

        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_performance_tab(), "Performance")
        self.tabs.addTab(self._create_audio_tab(), "Audio")
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")

        layout.addWidget(self.tabs)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_reset = QPushButton("Reset to Defaults")

        buttons_layout.addWidget(self.btn_reset)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_save)

        layout.addLayout(buttons_layout)

    def _create_general_tab(self) -> QWidget:
        """Create general settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Default Model Card
        model_card, model_layout = self._create_card("Default Model")

        model_select = QHBoxLayout()
        model_select.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()

        # Load models
        model_manager = self.ctx.model_manager()
        for model_id, model_info in model_manager.available_models.items():
            self.model_combo.addItem(
                f"{model_info.name} ({model_info.stems} stems)", userData=model_id
            )

        model_select.addWidget(self.model_combo)
        model_select.addStretch()
        model_layout.addLayout(model_select)

        layout.addWidget(model_card)

        # Output Directory Card
        output_card, output_layout = self._create_card("Output Directory")

        output_select = QHBoxLayout()
        output_select.addWidget(QLabel("Directory:"))
        self.output_path = QLineEdit()
        output_select.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("Browse...")
        output_select.addWidget(self.btn_browse_output)
        output_layout.addLayout(output_select)

        layout.addWidget(output_card)

        layout.addStretch()
        return widget

    def _create_performance_tab(self) -> QWidget:
        """Create performance settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # GPU Settings Card
        gpu_card, gpu_layout = self._create_card("GPU Acceleration")

        self.gpu_checkbox = QCheckBox("Use GPU if available (MPS/CUDA)")
        gpu_layout.addWidget(self.gpu_checkbox)

        # Device info
        device_mgr = self.ctx.device_manager()
        current_device = device_mgr.get_device()
        device_info = device_mgr.get_device_info(current_device)

        if device_info:
            info_text = (
                f"Current device: {device_info.name} - {device_info.description}"
            )
        else:
            info_text = "Current device: CPU"

        device_label = QLabel(info_text)
        device_label.setStyleSheet("color: gray; font-size: 10pt;")
        gpu_layout.addWidget(device_label)

        # Device picker
        # WHY: a Windows/Linux machine can expose several GPUs (iGPU + dGPU) or
        # none, and a broken CUDA-wheel/driver pairing still has to be visible.
        # Users need to pin the device and see *why* it is or is not usable.
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Compute device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItem("Auto (best available)", userData="auto")
        for info in device_mgr.list_available_devices():
            if info.name == "cpu":
                continue
            self.device_combo.addItem(
                f"{info.name.upper()} - {info.description}", userData=info.name
            )
        self.device_combo.addItem("CPU (Universal)", userData="cpu")
        device_row.addWidget(self.device_combo, 1)
        gpu_layout.addLayout(device_row)

        self.device_status_label = QLabel()
        self.device_status_label.setStyleSheet("color: gray; font-size: 9pt;")
        self.device_status_label.setWordWrap(True)
        gpu_layout.addWidget(self.device_status_label)
        self._update_device_status()
        self.device_combo.currentIndexChanged.connect(self._update_device_status)

        layout.addWidget(gpu_card)

        # Quality Settings Card
        quality_card, quality_layout = self._create_card("Separation Quality")

        quality_select = QHBoxLayout()
        quality_select.addWidget(QLabel("Quality Preset:"))
        self.quality_combo = QComboBox()

        # Load quality presets
        for preset_id, preset_info in QUALITY_PRESETS.items():
            self.quality_combo.addItem(
                f"{preset_info['name']} - {preset_info['description']}",
                userData=preset_id,
            )

        quality_select.addWidget(self.quality_combo)
        quality_layout.addLayout(quality_select)

        quality_info = QLabel(
            "Quality-Presets beeinflussen die Parameter der Separierung:\n"
            "• Fast: Schnellere Verarbeitung (1 shift, größeres Fenster)\n"
            "• Balanced: Empfohlen für die meisten Anwendungen (2 shifts)\n"
            "• Best Quality: 2-3x langsamer, bessere Ergebnisse (5 shifts, TTA)\n"
            "• Ultra Quality: 4-5x langsamer, maximale Qualität (8 shifts, alle Optimierungen)"
        )
        quality_info.setStyleSheet("color: gray; font-size: 10pt;")
        quality_info.setWordWrap(True)
        quality_layout.addWidget(quality_info)

        layout.addWidget(quality_card)

        # Chunking Settings Card
        chunk_card, chunk_layout = self._create_card("Audio Chunking")

        chunk_select = QHBoxLayout()
        chunk_select.addWidget(QLabel("Chunk Length:"))
        self.chunk_spinbox = QSpinBox()
        self.chunk_spinbox.setRange(60, 600)
        self.chunk_spinbox.setSingleStep(30)
        self.chunk_spinbox.setSuffix(" seconds")
        chunk_select.addWidget(self.chunk_spinbox)
        chunk_select.addStretch()
        chunk_layout.addLayout(chunk_select)

        chunk_info = QLabel(
            "Larger chunks require more memory but reduce processing overhead.\n"
            "Smaller chunks are safer for limited memory systems."
        )
        chunk_info.setStyleSheet("color: gray; font-size: 10pt;")
        chunk_info.setWordWrap(True)
        chunk_layout.addWidget(chunk_info)

        layout.addWidget(chunk_card)

        layout.addStretch()
        return widget


    def _update_device_status(self):
        """
        Show what the current device choice means on this machine.

        WHY: 'CUDA' in a dropdown is not information; users need the hardware
        name and, when a device cannot be used, the reason (missing CUDA wheel
        vs. missing driver) so the fix is actionable.
        """
        device_mgr = self.ctx.device_manager()
        selected = self.device_combo.currentData() or "auto"

        if selected == "auto":
            active = device_mgr.get_device()
            info = device_mgr.get_device_info(active)
            self.device_status_label.setText(
                f"Auto-select currently uses {info.description if info else active}."
            )
            return

        info = device_mgr.get_device_info(selected)
        if info is None:
            self.device_status_label.setText(f"Unknown device '{selected}'.")
        elif not info.available:
            self.device_status_label.setText(
                f"{selected.upper()} is not usable here: {info.description}"
            )
        else:
            memory = (
                f", {info.memory_gb:.1f} GB"
                if getattr(info, "memory_gb", None)
                else ""
            )
            self.device_status_label.setText(
                f"{info.description}{memory} — separation will run on "
                f"{selected.upper()}."
            )

    def _create_audio_tab(self) -> QWidget:
        """Create audio settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Recording Settings Card
        rec_card, rec_layout = self._create_card("Recording")

        # Sample rate
        sr_select = QHBoxLayout()
        sr_select.addWidget(QLabel("Sample Rate:"))
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItem("44100 Hz", userData=44100)
        self.sample_rate_combo.addItem("48000 Hz", userData=48000)
        self.sample_rate_combo.addItem("96000 Hz", userData=96000)
        sr_select.addWidget(self.sample_rate_combo)
        sr_select.addStretch()
        rec_layout.addLayout(sr_select)

        # Channels
        ch_select = QHBoxLayout()
        ch_select.addWidget(QLabel("Channels:"))
        self.channels_combo = QComboBox()
        self.channels_combo.addItem("Mono (1)", userData=1)
        self.channels_combo.addItem("Stereo (2)", userData=2)
        ch_select.addWidget(self.channels_combo)
        ch_select.addStretch()
        rec_layout.addLayout(ch_select)

        layout.addWidget(rec_card)

        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # System-audio capture card. Its content is platform-specific by design:
        # macOS needs a virtual driver (BlackHole), Windows/Linux expose an OS
        # loopback endpoint that needs no installation, and telling Windows users
        # to install a macOS driver is worse than saying nothing (REC-03).
        from utils import platform_utils

        self._is_macos = platform_utils.is_macos()

        if self._is_macos:
            blackhole_card, capture_layout = self._create_card("BlackHole Status")

            self.blackhole_status_label = QLabel("")
            self.blackhole_status_label.setWordWrap(True)
            capture_layout.addWidget(self.blackhole_status_label)

            blackhole_buttons = QHBoxLayout()
            self.btn_install_blackhole = QPushButton("⬇️ Install BlackHole")
            ThemeManager.set_widget_property(
                self.btn_install_blackhole, "buttonStyle", "secondary"
            )
            self.btn_setup_instructions = QPushButton("ℹ️  Setup Instructions")
            ThemeManager.set_widget_property(
                self.btn_setup_instructions, "buttonStyle", "secondary"
            )
            blackhole_buttons.addWidget(self.btn_install_blackhole)
            blackhole_buttons.addWidget(self.btn_setup_instructions)
            blackhole_buttons.addStretch()
            capture_layout.addLayout(blackhole_buttons)

            blackhole_info = QLabel(
                "BlackHole is required for system audio recording on macOS."
            )
            blackhole_info.setStyleSheet("color: gray; font-size: 10pt;")
            blackhole_info.setWordWrap(True)
            capture_layout.addWidget(blackhole_info)

            layout.addWidget(blackhole_card)
        else:
            card, capture_layout = self._create_card("System Audio Capture")
            self.capture_status_label = QLabel("")
            self.capture_status_label.setWordWrap(True)
            capture_layout.addWidget(self.capture_status_label)

            platform_label = platform_utils.os_name()
            mechanism = (
                "Windows loopback endpoint (MediaFoundation/WASAPI-compatible)"
                if platform_utils.is_windows()
                else "PulseAudio/PipeWire monitor source"
            )
            info = QLabel(
                f"System audio is captured from the {mechanism}. No virtual driver "
                f"or extra installation is needed on {platform_label} — pick the "
                "'[System Audio]' entry in the Recording tab."
            )
            info.setStyleSheet("color: gray; font-size: 10pt;")
            info.setWordWrap(True)
            capture_layout.addWidget(info)

            layout.addWidget(card)

            self._refresh_capture_status()

        # Diagnostics Card
        diag_card, diag_layout = self._create_card("Diagnostics")

        self.btn_open_logs = QPushButton("Open Log File")
        self.btn_open_logs.setMaximumWidth(200)
        diag_layout.addWidget(self.btn_open_logs)

        log_info = QLabel("View application logs for debugging and diagnostics.")
        log_info.setStyleSheet("color: gray; font-size: 10pt;")
        log_info.setWordWrap(True)
        diag_layout.addWidget(log_info)

        layout.addWidget(diag_card)

        # Future settings placeholder
        info = QLabel(
            "Additional advanced settings coming soon:\n\n"
            "- Log level configuration\n"
            "- Retry strategies\n"
            "- Model cache management\n"
            "- Export format settings"
        )
        info.setStyleSheet("color: gray; font-size: 10pt;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

        if self._is_macos:
            self._check_blackhole_status()

        return widget

    def _connect_signals(self):
        """Connect signals"""
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_browse_output.clicked.connect(self._on_browse_output)
        self.btn_open_logs.clicked.connect(self._on_open_logs)
        if self._is_macos:
            self.btn_install_blackhole.clicked.connect(self._on_install_blackhole)
            self.btn_setup_instructions.clicked.connect(self._on_setup_instructions)

    def _load_current_settings(self):
        """Load current settings into UI controls"""
        # Model
        model = self.settings_mgr.get_default_model()
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == model:
                self.model_combo.setCurrentIndex(i)
                break

        # GPU
        self.gpu_checkbox.setChecked(self.settings_mgr.get_use_gpu())
        index = self.device_combo.findData(self.settings_mgr.get_compute_device())
        self.device_combo.setCurrentIndex(index if index >= 0 else 0)

        # Quality Preset
        quality_preset = self.settings_mgr.get_quality_preset()
        for i in range(self.quality_combo.count()):
            if self.quality_combo.itemData(i) == quality_preset:
                self.quality_combo.setCurrentIndex(i)
                break

        # Chunk length
        self.chunk_spinbox.setValue(self.settings_mgr.get_chunk_length())

        # Output directory
        self.output_path.setText(str(self.settings_mgr.get_output_directory()))

        # Sample rate
        sr = self.settings_mgr.get("recording_sample_rate", 44100)
        for i in range(self.sample_rate_combo.count()):
            if self.sample_rate_combo.itemData(i) == sr:
                self.sample_rate_combo.setCurrentIndex(i)
                break

        # Channels
        ch = self.settings_mgr.get("recording_channels", 2)
        for i in range(self.channels_combo.count()):
            if self.channels_combo.itemData(i) == ch:
                self.channels_combo.setCurrentIndex(i)
                break

    @Slot()
    def _on_browse_output(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(self.settings_mgr.get_output_directory()),
        )

        if directory:
            self.output_path.setText(directory)

    @Slot()
    def _on_save(self):
        """Save settings"""
        # Save all settings
        self.settings_mgr.set_default_model(self.model_combo.currentData())
        self.settings_mgr.set_quality_preset(self.quality_combo.currentData())
        self.settings_mgr.set_use_gpu(self.gpu_checkbox.isChecked())
        self.settings_mgr.set_compute_device(self.device_combo.currentData() or "auto")
        self.settings_mgr.set_chunk_length(self.chunk_spinbox.value())
        self.settings_mgr.set_output_directory(Path(self.output_path.text()))
        self.settings_mgr.set(
            "recording_sample_rate", self.sample_rate_combo.currentData()
        )
        self.settings_mgr.set("recording_channels", self.channels_combo.currentData())

        # Persist to file
        if self.settings_mgr.save():
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully.\n\n"
                "Some changes may require application restart.",
            )

            self.settings_changed.emit()
            self.accept()
        else:
            QMessageBox.critical(
                self, "Save Failed", "Failed to save settings. Check logs for details."
            )

    @Slot()
    def _on_reset(self):
        """Reset settings to defaults"""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to default values?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.settings_mgr._load_defaults()
            self._load_current_settings()

    @Slot()
    def _on_open_logs(self):
        """Open application log file in the system viewer"""
        log_path: Path = self.ctx.log_file()
        if not log_path.exists():
            self.ctx.logger().warning("Log file %s does not exist yet", log_path)
            QMessageBox.information(self, "Log File", "Log file not created yet.")
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        if not opened:
            self.ctx.logger().error("Failed to open log file: %s", log_path)
            QMessageBox.warning(
                self,
                "Log File",
                "Could not open the log file. Please open it manually.",
            )

    def _refresh_capture_status(self):
        """
        Report the detected loopback/monitor endpoint (Windows & Linux).

        WHY: the macOS tab derives status from the BlackHole installer; off-macOS
        there is no installer, so status must come from the devices the capture
        library actually sees — the user's only clue about a permission or routing
        problem.
        """
        if not hasattr(self, "capture_status_label"):
            return

        info = self.ctx.recorder().get_backend_info()
        if info.get("system_audio_available"):
            self.capture_status_label.setText(
                f"✓ System audio capture available: {info['system_audio_device']}"
            )
            self.capture_status_label.setStyleSheet("color: green;")
        elif info.get("input_devices"):
            self.capture_status_label.setText(
                "⚠ No system-audio (loopback/monitor) device found. Only "
                "microphones are available: " + ", ".join(info["input_devices"])
            )
            self.capture_status_label.setStyleSheet("color: orange;")
        else:
            self.capture_status_label.setText(
                "✗ No capture devices visible. Check the system's microphone/"
                "audio permission for StemSeparator."
                + (
                    f" ({info.get('soundcard_error')})"
                    if info.get("soundcard_error")
                    else ""
                )
            )
            self.capture_status_label.setStyleSheet("color: red;")

    def _check_blackhole_status(self):
        """
        Check BlackHole installation status

        WHY: User must have BlackHole installed for system audio recording on macOS
        """
        status = self.blackhole_installer.get_status()

        if not status.installed:
            self.blackhole_status_label.setText(
                "⚠ BlackHole not installed. System audio recording requires BlackHole."
            )
            self.blackhole_status_label.setStyleSheet("color: orange;")
            self.btn_install_blackhole.setEnabled(status.homebrew_available)
        elif not status.device_found:
            self.blackhole_status_label.setText(
                f"✓ BlackHole {status.version} installed, but device not configured. "
                "Click 'Setup Instructions' below."
            )
            self.blackhole_status_label.setStyleSheet("color: orange;")
            self.btn_install_blackhole.setEnabled(False)
        else:
            self.blackhole_status_label.setText(
                f"✓ BlackHole {status.version} ready for system audio recording"
            )
            self.blackhole_status_label.setStyleSheet("color: green;")
            self.btn_install_blackhole.setEnabled(False)

    @Slot()
    def _on_install_blackhole(self):
        """Install BlackHole via Homebrew in background thread"""
        reply = QMessageBox.question(
            self,
            "Install BlackHole",
            "This will install BlackHole via Homebrew.\n\n"
            "This may take a few minutes and requires admin privileges.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # Disable button during installation
        self.btn_install_blackhole.setEnabled(False)
        self.blackhole_status_label.setText("Installing BlackHole...")

        # Create and configure worker
        worker = BlackHoleInstallWorker(self.blackhole_installer)
        worker.signals.progress.connect(self._on_install_progress)
        worker.signals.finished.connect(self._on_install_finished)

        # Start installation in background
        self.thread_pool.start(worker)

    @Slot(str)
    def _on_install_progress(self, message: str):
        """Update progress label during installation"""
        self.blackhole_status_label.setText(message)

    @Slot(bool, str)
    def _on_install_finished(self, success: bool, error_msg: str):
        """Handle installation completion"""
        self.btn_install_blackhole.setEnabled(True)

        if success:
            QMessageBox.information(
                self,
                "Installation Complete",
                "BlackHole has been installed via Homebrew.\n\n"
                "⚠️ IMPORTANT - Manual Step Required:\n\n"
                "BlackHole needs admin privileges to install the audio driver.\n"
                "Please run this command in Terminal:\n\n"
                "    brew install --cask blackhole-2ch\n\n"
                "After installation:\n"
                "1. Restart this application\n"
                "2. Refresh device list\n"
                "3. Follow setup instructions",
            )
            self._check_blackhole_status()
        else:
            # Check if it's a password issue
            if "sudo" in error_msg.lower() or "password" in error_msg.lower():
                QMessageBox.warning(
                    self,
                    "Manual Installation Required",
                    "BlackHole installation requires admin privileges.\n\n"
                    "Please install manually via Terminal:\n\n"
                    "    brew install --cask blackhole-2ch\n\n"
                    "After installation, restart this app and refresh devices.",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Installation Failed",
                    f"Failed to install BlackHole:\n{error_msg}\n\n"
                    "You may need to install it manually:\n"
                    "brew install --cask blackhole-2ch",
                )
            self.blackhole_status_label.setText("❌ Manual installation required")

    @Slot()
    def _on_setup_instructions(self):
        """Show BlackHole setup instructions"""
        instructions = self.blackhole_installer.get_setup_instructions()

        msg = QMessageBox(self)
        msg.setWindowTitle("BlackHole Setup")
        msg.setText(
            "Follow these steps to configure BlackHole for system audio recording:"
        )
        msg.setDetailedText(instructions)
        msg.setIcon(QMessageBox.Information)

        # Add button to open Audio MIDI Setup
        open_btn = msg.addButton("Open Audio MIDI Setup", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)

        msg.exec()

        # Check if user clicked the open button
        if msg.clickedButton() == open_btn:
            self.blackhole_installer.open_audio_midi_setup()
