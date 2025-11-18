"""
Settings Dialog - User preferences configuration

PURPOSE: Provide GUI for modifying application settings.
CONTEXT: Settings dialog accessible from main menu.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QComboBox, QCheckBox, QSpinBox,
    QLineEdit, QGroupBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices

from ui.app_context import AppContext
from ui.settings_manager import get_settings_manager
from config import QUALITY_PRESETS


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
        
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(600, 500)
        
        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()
        
        self.ctx.logger().info("SettingsDialog initialized")
    
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

        # Default Model
        model_group = QGroupBox("Default Model")
        model_layout = QVBoxLayout()
        
        model_select = QHBoxLayout()
        model_select.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        
        # Load models
        model_manager = self.ctx.model_manager()
        for model_id, model_info in model_manager.available_models.items():
            self.model_combo.addItem(
                f"{model_info.name} ({model_info.stems} stems)",
                userData=model_id
            )
        
        model_select.addWidget(self.model_combo)
        model_select.addStretch()
        model_layout.addLayout(model_select)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # Output Directory
        output_group = QGroupBox("Output Directory")
        output_layout = QVBoxLayout()
        
        output_select = QHBoxLayout()
        output_select.addWidget(QLabel("Directory:"))
        self.output_path = QLineEdit()
        output_select.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("Browse...")
        output_select.addWidget(self.btn_browse_output)
        output_layout.addLayout(output_select)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        layout.addStretch()
        return widget
    
    def _create_performance_tab(self) -> QWidget:
        """Create performance settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # GPU Settings
        gpu_group = QGroupBox("GPU Acceleration")
        gpu_layout = QVBoxLayout()
        
        self.gpu_checkbox = QCheckBox("Use GPU if available (MPS/CUDA)")
        gpu_layout.addWidget(self.gpu_checkbox)
        
        # Device info
        device_mgr = self.ctx.device_manager()
        current_device = device_mgr.get_device()
        device_info = device_mgr.get_device_info(current_device)
        
        if device_info:
            info_text = f"Current device: {device_info.name} - {device_info.description}"
        else:
            info_text = "Current device: CPU"
        
        device_label = QLabel(info_text)
        device_label.setStyleSheet("color: gray; font-size: 10pt;")
        gpu_layout.addWidget(device_label)
        
        gpu_group.setLayout(gpu_layout)
        layout.addWidget(gpu_group)

        # Quality Settings
        quality_group = QGroupBox("Separation Quality")
        quality_layout = QVBoxLayout()

        quality_select = QHBoxLayout()
        quality_select.addWidget(QLabel("Quality Preset:"))
        self.quality_combo = QComboBox()

        # Load quality presets
        for preset_id, preset_info in QUALITY_PRESETS.items():
            self.quality_combo.addItem(
                f"{preset_info['name']} - {preset_info['description']}",
                userData=preset_id
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

        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)

        # Chunking Settings
        chunk_group = QGroupBox("Audio Chunking")
        chunk_layout = QVBoxLayout()
        
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
        
        chunk_group.setLayout(chunk_layout)
        layout.addWidget(chunk_group)
        
        layout.addStretch()
        return widget
    
    def _create_audio_tab(self) -> QWidget:
        """Create audio settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Recording Settings
        rec_group = QGroupBox("Recording")
        rec_layout = QVBoxLayout()
        
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
        
        # Auto-separate option
        self.auto_separate_checkbox = QCheckBox(
            "Automatically separate recordings after saving"
        )
        rec_layout.addWidget(self.auto_separate_checkbox)
        
        rec_group.setLayout(rec_layout)
        layout.addWidget(rec_group)
        
        layout.addStretch()
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Diagnostics group
        diag_group = QGroupBox("Diagnostics")
        diag_layout = QVBoxLayout()

        self.btn_open_logs = QPushButton("Open Log File")
        self.btn_open_logs.setMaximumWidth(200)
        diag_layout.addWidget(self.btn_open_logs)

        log_info = QLabel(
            "View application logs for debugging and diagnostics."
        )
        log_info.setStyleSheet("color: gray; font-size: 10pt;")
        log_info.setWordWrap(True)
        diag_layout.addWidget(log_info)

        diag_group.setLayout(diag_layout)
        layout.addWidget(diag_group)

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
        return widget
    
    def _connect_signals(self):
        """Connect signals"""
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_browse_output.clicked.connect(self._on_browse_output)
        self.btn_open_logs.clicked.connect(self._on_open_logs)
    
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
        sr = self.settings_mgr.get('recording_sample_rate', 44100)
        for i in range(self.sample_rate_combo.count()):
            if self.sample_rate_combo.itemData(i) == sr:
                self.sample_rate_combo.setCurrentIndex(i)
                break
        
        # Channels
        ch = self.settings_mgr.get('recording_channels', 2)
        for i in range(self.channels_combo.count()):
            if self.channels_combo.itemData(i) == ch:
                self.channels_combo.setCurrentIndex(i)
                break
        
        # Auto-separate
        self.auto_separate_checkbox.setChecked(
            self.settings_mgr.get('auto_separate_after_recording', False)
        )
    
    @Slot()
    def _on_browse_output(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(self.settings_mgr.get_output_directory())
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
        self.settings_mgr.set_chunk_length(self.chunk_spinbox.value())
        self.settings_mgr.set_output_directory(Path(self.output_path.text()))
        self.settings_mgr.set('recording_sample_rate', self.sample_rate_combo.currentData())
        self.settings_mgr.set('recording_channels', self.channels_combo.currentData())
        self.settings_mgr.set('auto_separate_after_recording', self.auto_separate_checkbox.isChecked())
        
        # Persist to file
        if self.settings_mgr.save():
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully.\n\n"
                "Some changes may require application restart."
            )
            
            self.settings_changed.emit()
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Save Failed",
                "Failed to save settings. Check logs for details."
            )
    
    @Slot()
    def _on_reset(self):
        """Reset settings to defaults"""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to default values?",
            QMessageBox.Yes | QMessageBox.No
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
            QMessageBox.information(
                self,
                "Log File",
                "Log file not created yet."
            )
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        if not opened:
            self.ctx.logger().error("Failed to open log file: %s", log_path)
            QMessageBox.warning(
                self,
                "Log File",
                "Could not open the log file. Please open it manually."
            )

