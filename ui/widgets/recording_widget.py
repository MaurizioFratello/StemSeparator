"""
Recording Widget - System audio recording controls with level metering

PURPOSE: Enable users to record system audio via BlackHole and control recording state.
CONTEXT: Integrates core.recorder.Recorder with thread-safe GUI updates.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QProgressBar, QGroupBox, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QPalette, QColor

from ui.app_context import AppContext
from core.recorder import RecordingState, RecordingInfo
from ui.theme import ThemeManager


class RecordingWidget(QWidget):
    """
    Widget for system audio recording

    Features:
    - Device selection (BlackHole, microphones)
    - Recording controls (start/pause/resume/stop/cancel)
    - Real-time audio level meter
    - Duration display
    """
    
    # Signal emitted when recording is saved
    recording_saved = Signal(Path)  # file_path
    
    # Signal emitted when audio level updates (from recorder thread)
    level_updated = Signal(float)  # level (0.0-1.0)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()
        self.recorder = self.ctx.recorder()

        # Timer for updating duration and level
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(100)  # 100ms updates
        self.update_timer.timeout.connect(self._update_display)
        
        self._setup_ui()
        self._connect_signals()
        self._refresh_devices()
        self.apply_translations()
        
        self.ctx.logger().info("RecordingWidget initialized")
    
    def _setup_ui(self):
        """Setup widget layout and components"""
        # Create main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create container widget for scrollable content
        container = QWidget()
        layout = QVBoxLayout(container)

        # Device Selection Group
        device_group = QGroupBox("Recording Device")
        device_layout = QVBoxLayout()
        
        device_select = QHBoxLayout()
        device_select.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        device_select.addWidget(self.device_combo, stretch=1)
        self.btn_refresh_devices = QPushButton("🔄 Refresh")
        ThemeManager.set_widget_property(self.btn_refresh_devices, "buttonStyle", "secondary")
        device_select.addWidget(self.btn_refresh_devices)
        device_layout.addLayout(device_select)
        
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)
        
        # Recording Controls Group
        controls_group = QGroupBox("Recording")
        controls_layout = QVBoxLayout()
        
        # Level meter (RMS with ballistics)
        meter_layout = QHBoxLayout()
        meter_label = QLabel("Level (RMS):")
        meter_label.setToolTip(
            "Audio level meter with professional ballistics\n"
            "Range: -60 dBFS (silence) to 0 dBFS (clipping)\n"
            "Green: Normal (<-12 dB)\n"
            "Yellow: High (-12 to -3 dB)\n"
            "Red: Danger (>-3 dB - risk of clipping)"
        )
        meter_layout.addWidget(meter_label)
        self.level_meter = QProgressBar()
        ThemeManager.set_widget_property(self.level_meter, "progressStyle", "large")
        self.level_meter.setRange(0, 100)
        self.level_meter.setValue(0)
        self.level_meter.setTextVisible(True)
        self.level_meter.setFormat("Silence")
        meter_layout.addWidget(self.level_meter)
        controls_layout.addLayout(meter_layout)
        
        # Duration display (monospace for better readability)
        self.duration_label = QLabel("Duration: 00:00.0")
        self.duration_label.setAlignment(Qt.AlignCenter)
        ThemeManager.set_widget_property(self.duration_label, "labelStyle", "mono")
        font = self.duration_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.duration_label.setFont(font)
        controls_layout.addWidget(self.duration_label)
        
        # State label
        self.state_label = QLabel("Ready")
        self.state_label.setAlignment(Qt.AlignCenter)
        controls_layout.addWidget(self.state_label)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        self.btn_start = QPushButton("🔴 Start Recording")
        ThemeManager.set_widget_property(self.btn_start, "buttonStyle", "success")

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_pause, "buttonStyle", "secondary")

        self.btn_stop = QPushButton("💾 Stop & Save")
        self.btn_stop.setEnabled(False)
        # Stop uses primary style (default)

        self.btn_cancel = QPushButton("❌ Cancel")
        self.btn_cancel.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_cancel, "buttonStyle", "danger")

        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_pause)
        buttons_layout.addWidget(self.btn_stop)
        buttons_layout.addWidget(self.btn_cancel)
        controls_layout.addLayout(buttons_layout)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        layout.addStretch()

        # Set the container in the scroll area
        scroll_area.setWidget(container)

        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)

    def _connect_signals(self):
        """Connect button signals to handlers"""
        self.btn_refresh_devices.clicked.connect(self._refresh_devices)
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)

        # Connect internal signal for thread-safe level updates
        self.level_updated.connect(self._update_level_meter)
    
    def _refresh_devices(self):
        """
        Refresh available audio devices
        
        WHY: Devices can change when hardware is connected/disconnected
        """
        self.device_combo.clear()
        
        devices = self.recorder.get_available_devices()
        
        if not devices:
            self.device_combo.addItem("No devices found", userData=None)
            self.ctx.logger().warning("No audio devices found")
            return
        
        # Add devices to combo box
        for device in devices:
            self.device_combo.addItem(device, userData=device)
        
        # Try to select BlackHole by default
        blackhole_device = self.recorder.find_blackhole_device()
        if blackhole_device:
            for i in range(self.device_combo.count()):
                if 'blackhole' in self.device_combo.itemText(i).lower():
                    self.device_combo.setCurrentIndex(i)
                    break
        
        self.ctx.logger().info(f"Refreshed devices: {len(devices)} found")

    @Slot(int)
    def _on_device_changed(self, index: int):
        """
        Handle device selection change - start monitoring the selected device

        WHY: Allows users to see input levels before starting recording
        """
        # Stop any existing monitoring
        if self.recorder.is_monitoring():
            self.recorder.stop_monitoring()

        # Don't start monitoring if we're currently recording
        if self.recorder.is_recording():
            return

        # Get selected device
        device_name = self.device_combo.currentData()

        if not device_name:
            # No device selected (e.g., "No devices found")
            return

        # Start monitoring with level callback
        success = self.recorder.start_monitoring(
            device_name=device_name,
            level_callback=self._on_level_update
        )

        if success:
            self.ctx.logger().info(f"Started monitoring: {device_name}")
            self.state_label.setText("Monitoring...")
        else:
            self.ctx.logger().warning(f"Failed to start monitoring: {device_name}")

    @Slot()
    def _on_start_clicked(self):
        """
        Start recording
        
        WHY: Initiates recording in background thread with level callback
        """
        device_name = self.device_combo.currentData()
        
        if not device_name:
            QMessageBox.warning(
                self,
                "No Device",
                "Please select a recording device"
            )
            return
        
        # Start recording with level callback
        success = self.recorder.start_recording(
            device_name=device_name,
            level_callback=self._on_level_update
        )
        
        if success:
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self.device_combo.setEnabled(False)
            self.btn_refresh_devices.setEnabled(False)
            
            self.update_timer.start()
            self.ctx.logger().info("Recording started")
        else:
            QMessageBox.critical(
                self,
                "Recording Failed",
                "Failed to start recording. Check that BlackHole is configured correctly."
            )
    
    @Slot()
    def _on_pause_clicked(self):
        """Pause or resume recording"""
        state = self.recorder.get_state()
        
        if state == RecordingState.RECORDING:
            if self.recorder.pause_recording():
                self.btn_pause.setText("Resume")
                self.ctx.logger().info("Recording paused")
        elif state == RecordingState.PAUSED:
            if self.recorder.resume_recording():
                self.btn_pause.setText("Pause")
                self.ctx.logger().info("Recording resumed")
    
    @Slot()
    def _on_stop_clicked(self):
        """
        Stop recording and save
        
        WHY: Finalizes recording and emits signal for downstream processing
        """
        self.update_timer.stop()
        
        info = self.recorder.stop_recording()
        
        if info:
            self.ctx.logger().info(
                f"Recording saved: {info.file_path} "
                f"({info.duration_seconds:.1f}s, peak: {info.peak_level:.2f})"
            )
            
            QMessageBox.information(
                self,
                "Recording Saved",
                f"Recording saved successfully!\n\n"
                f"Duration: {info.duration_seconds:.1f}s\n"
                f"Sample Rate: {info.sample_rate} Hz\n"
                f"Channels: {info.channels}\n"
                f"Peak Level: {info.peak_level:.2f}\n\n"
                f"File: {info.file_path.name}"
            )
            
            # Emit signal for potential downstream processing
            self.recording_saved.emit(info.file_path)
        else:
            QMessageBox.warning(
                self,
                "Recording Failed",
                "Failed to save recording. No audio was recorded."
            )
        
        self._reset_controls()
    
    @Slot()
    def _on_cancel_clicked(self):
        """Cancel recording without saving"""
        reply = QMessageBox.question(
            self,
            "Cancel Recording",
            "Are you sure you want to cancel?\n\nRecording will be discarded.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.update_timer.stop()
            self.recorder.cancel_recording()
            self._reset_controls()
            self.ctx.logger().info("Recording cancelled")
    
    def _reset_controls(self):
        """Reset UI controls to initial state"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("Pause")
        self.btn_stop.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.device_combo.setEnabled(True)
        self.btn_refresh_devices.setEnabled(True)

        self.level_meter.setValue(0)
        self.level_meter.setFormat("Silence")
        from ui.theme import ThemeManager
        ThemeManager.set_widget_property(self.level_meter, "meterLevel", "safe")  # Reset to default
        self.duration_label.setText("Duration: 00:00.0")
        self.state_label.setText("Ready")
    
    def _on_level_update(self, level: float):
        """
        Handle audio level update from recorder thread
        
        WHY: Called from recorder thread, must emit signal for thread-safety
        IMPORTANT: Do NOT update GUI directly from here - use signal instead!
        """
        # Emit signal - Qt will marshal this to the GUI thread safely
        self.level_updated.emit(level)
    
    @Slot(float)
    def _update_level_meter(self, level: float):
        """
        Update level meter (runs in GUI thread)

        WHY: Receives level_updated signal and safely updates GUI

        IMPORTANT: The level value now represents calibrated dBFS scale:
                   - 0.0 = -60 dBFS (silence/very quiet)
                   - 0.5 = -30 dBFS (moderate level)
                   - 1.0 = 0 dBFS (digital full scale - clipping!)

        Professional audio meter color standards:
                   - Green: Normal operating range (below -12 dBFS, level < 0.80)
                   - Yellow: High but safe range (-12 to -3 dBFS, level 0.80-0.95)
                   - Red: Danger zone (above -3 dBFS, level > 0.95) - risk of clipping
        """
        # Convert level (0.0-1.0) to percentage for display
        level_percent = int(level * 100)
        self.level_meter.setValue(level_percent)

        # Calculate actual dBFS for user feedback
        # Meter range: -60 dBFS to 0 dBFS
        db_range = 60.0  # Full range width
        dbfs = -60.0 + (level * db_range)

        # Update text to show dBFS value
        if level < 0.01:  # Very quiet
            self.level_meter.setFormat("Silence")
        elif dbfs >= -0.1:  # Essentially at 0 dBFS
            self.level_meter.setFormat("0 dB (CLIP!)")
        else:
            self.level_meter.setFormat(f"{dbfs:.1f} dB")

        self.level_meter.setTextVisible(True)

        # Color code based on professional audio standards using Qt properties
        # WHY: These thresholds match broadcast and recording industry standards
        # PERFORMANCE: Using properties instead of setStyleSheet avoids CSS parsing overhead
        from ui.theme import ThemeManager

        if level > 0.95:  # Above -3 dBFS
            # RED: Danger zone - very close to clipping
            ThemeManager.set_widget_property(self.level_meter, "meterLevel", "danger")
        elif level > 0.80:  # Above -12 dBFS
            # YELLOW/ORANGE: High level - still safe but approaching limit
            ThemeManager.set_widget_property(self.level_meter, "meterLevel", "caution")
        else:  # Below -12 dBFS
            # GREEN: Normal operating range
            ThemeManager.set_widget_property(self.level_meter, "meterLevel", "safe")
    
    @Slot()
    def _update_display(self):
        """
        Update duration display and state label
        
        WHY: Called by timer every 100ms to show current recording time
        """
        duration = self.recorder.get_recording_duration()
        
        # Format duration as MM:SS.d
        minutes = int(duration // 60)
        seconds = duration % 60
        self.duration_label.setText(f"Duration: {minutes:02d}:{seconds:04.1f}")
        
        # Update state label
        state = self.recorder.get_state()
        state_text = {
            RecordingState.IDLE: "Ready",
            RecordingState.RECORDING: "● Recording",
            RecordingState.PAUSED: "⏸ Paused",
            RecordingState.STOPPED: "Stopped"
        }.get(state, "Unknown")

        self.state_label.setText(state_text)

        # Constant red indicator during recording
        if state == RecordingState.RECORDING:
            self.state_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.state_label.setStyleSheet("")
    
    def apply_translations(self):
        """
        Apply current language translations

        WHY: Called when language changes; updates all visible text
        """
        # Note: Translation keys would be defined in resources/translations/*.json
        # For now, using English defaults
        pass

    def closeEvent(self, event):
        """Clean up monitoring when widget is closed"""
        if self.recorder.is_monitoring():
            self.recorder.stop_monitoring()
        super().closeEvent(event)

