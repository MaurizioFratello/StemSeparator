"""
Recording Widget - System audio recording controls with level metering

PURPOSE: Enable users to record system audio via BlackHole and control recording state.
CONTEXT: Integrates core.recorder.Recorder with thread-safe GUI updates.
"""
from pathlib import Path
from typing import Optional
import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QProgressBar, QGroupBox, QMessageBox, QScrollArea, QFrame
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

        # Track if widget is visible for resource-efficient monitoring
        self._is_visible = False
        self._last_selected_device = None

        self._setup_ui()
        self._connect_signals()
        self._refresh_devices()
        self.apply_translations()

        self.ctx.logger().info("RecordingWidget initialized")
    
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
        """Setup widget layout and components"""
        # Create main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Device Selection Card
        device_card, device_layout = self._create_card("Recording Device")
        
        device_select = QHBoxLayout()
        device_select.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        device_select.addWidget(self.device_combo, stretch=1)
        self.btn_refresh_devices = QPushButton("🔄 Refresh")
        ThemeManager.set_widget_property(self.btn_refresh_devices, "buttonStyle", "secondary")
        device_select.addWidget(self.btn_refresh_devices)
        device_layout.addLayout(device_select)
        
        main_layout.addWidget(device_card)
        
        # Recording Controls Card
        controls_card, controls_layout = self._create_card("Recording")
        
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
        self.btn_start.setToolTip("Start recording system audio")

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_pause, "buttonStyle", "secondary")
        self.btn_pause.setToolTip("Pause/resume recording (available during recording)")

        self.btn_stop = QPushButton("💾 Stop & Save")
        self.btn_stop.setEnabled(False)
        # Stop uses primary style (default)
        self.btn_stop.setToolTip("Stop recording and save file (available during recording)")

        self.btn_cancel = QPushButton("❌ Cancel")
        self.btn_cancel.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_cancel, "buttonStyle", "danger")
        self.btn_cancel.setToolTip("Cancel recording without saving (available during recording)")

        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_pause)
        buttons_layout.addWidget(self.btn_stop)
        buttons_layout.addWidget(self.btn_cancel)
        controls_layout.addLayout(buttons_layout)
        
        main_layout.addWidget(controls_card)

        main_layout.addStretch()

        # Removed scroll area logic

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

        # Check if ScreenCaptureKit is available
        backend_info = self.recorder.get_backend_info()
        screencapture_available = backend_info.get('screencapture_available', False)

        # Add ScreenCaptureKit as first option if available (macOS 13+)
        if screencapture_available:
            self.device_combo.addItem(
                "System Audio",
                userData="__screencapture__"
            )

        devices = self.recorder.get_available_devices()

        if not devices and not screencapture_available:
            self.device_combo.addItem("No devices found", userData=None)
            self.ctx.logger().warning("No audio devices found")
            return

        # Add physical devices to combo box
        for device in devices:
            self.device_combo.addItem(device, userData=device)

        # Auto-select best default option:
        # 1. ScreenCaptureKit if available (best option for system audio)
        # 2. BlackHole if available (traditional system audio)
        # 3. First device otherwise
        if screencapture_available:
            self.device_combo.setCurrentIndex(0)  # ScreenCaptureKit
            self.ctx.logger().info("Auto-selected ScreenCaptureKit for system audio recording")
        else:
            # Try to select BlackHole
            blackhole_device = self.recorder.find_blackhole_device()
            if blackhole_device:
                for i in range(self.device_combo.count()):
                    if 'blackhole' in self.device_combo.itemText(i).lower():
                        self.device_combo.setCurrentIndex(i)
                        break

        device_count = len(devices) + (1 if screencapture_available else 0)
        self.ctx.logger().info(f"Refreshed devices: {device_count} found")

    @Slot(int)
    def _on_device_changed(self, index: int):
        """
        Handle device selection change - start monitoring only if tab is visible

        WHY: Allows users to see input levels before starting recording
             Only monitors when tab is active to save resources
        """
        # Get selected device and remember it
        device_data = self.device_combo.currentData()
        self._last_selected_device = device_data

        if not device_data:
            # No device selected (e.g., "No devices found")
            return

        # Don't start monitoring if we're currently recording
        if self.recorder.is_recording():
            return

        # Only start monitoring if widget is visible (tab is active)
        if not self._is_visible:
            self.ctx.logger().debug(
                f"Device changed to {device_data}, but widget not visible - "
                f"monitoring will start when tab becomes active"
            )
            return

        # Stop any existing monitoring
        if self.recorder.is_monitoring():
            self.recorder.stop_monitoring()

        # Convert ScreenCaptureKit marker to None for monitoring
        # Note: ScreenCaptureKit doesn't support pre-recording monitoring yet,
        # so we skip monitoring for ScreenCaptureKit devices
        if device_data == "__screencapture__":
            self.ctx.logger().info("ScreenCaptureKit selected - monitoring will start during recording")
            self.state_label.setText("Ready (ScreenCaptureKit)")
            return

        # Start monitoring with level callback for physical devices
        success = self.recorder.start_monitoring(
            device_name=device_data,
            level_callback=self._on_level_update
        )

        if success:
            self.ctx.logger().info(f"Started monitoring: {device_data}")
            self.state_label.setText("Monitoring...")
        else:
            self.ctx.logger().warning(f"Failed to start monitoring: {device_data}")

    @Slot()
    def _on_start_clicked(self):
        """
        Start recording
        
        WHY: Initiates recording in background thread with level callback
        """
        device_data = self.device_combo.currentData()

        if device_data is None:
            QMessageBox.warning(
                self,
                "No Device",
                "Please select a recording device"
            )
            return

        # Check if ScreenCaptureKit is selected
        if device_data == "__screencapture__":
            # ScreenCaptureKit: pass None to use backend auto-selection
            device_name = None
            using_screencapture = True
        else:
            # Physical device (BlackHole, microphone, etc.)
            device_name = device_data
            using_screencapture = False

        # Reset Level Meter before starting
        self.level_meter.setValue(0)
        
        # Start recording with level callback
        # IMPORTANT: We pass self._on_level_update which emits the signal to the GUI thread
        # self.ctx.logger().info(f"Starting recording with callback: {self._on_level_update}")
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

            if using_screencapture:
                self.ctx.logger().info("Recording started with ScreenCaptureKit")
            else:
                self.ctx.logger().info(f"Recording started with device: {device_name}")
        else:
            error_msg = (
                "Failed to start recording.\n\n"
                "If using ScreenCaptureKit:\n"
                "• Grant Screen Recording permission in System Settings\n"
                "• Privacy & Security → Screen Recording\n\n"
                "If using BlackHole:\n"
                "• Check that BlackHole is configured correctly"
            )
            QMessageBox.critical(
                self,
                "Recording Failed",
                error_msg
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
    
    def _peak_to_dbfs(self, peak_level: float) -> float:
        """
        Convert peak level (0.0-1.0) to dBFS (decibels relative to full scale)
        
        WHY: Professional audio meters use dBFS scale where:
             - 0 dBFS = maximum possible digital level (clipping)
             - -∞ dBFS = digital silence
             - Peak values are converted directly: dBFS = 20 * log10(peak)
        
        Args:
            peak_level: Peak audio level (0.0-1.0)
        
        Returns:
            dBFS value (typically -∞ to 0 dBFS)
        """
        if peak_level <= 1e-10:  # Avoid log(0) which would be -infinity
            return -100.0  # Very quiet, below useful display range
        
        # Convert peak to dBFS: dBFS = 20 * log10(peak)
        dbfs = 20.0 * math.log10(peak_level)
        return float(dbfs)
    
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
            
            # Convert peak level to dBFS for display
            peak_dbfs = self._peak_to_dbfs(info.peak_level)
            if peak_dbfs <= -100.0:
                peak_display = "Silence (< -100 dB)"
            elif peak_dbfs >= -0.1:
                peak_display = f"{peak_dbfs:.1f} dB (CLIP!)"
            else:
                peak_display = f"{peak_dbfs:.1f} dB"
            
            QMessageBox.information(
                self,
                "Recording Saved",
                f"Recording saved successfully!\n\n"
                f"Duration: {info.duration_seconds:.1f}s\n"
                f"Sample Rate: {info.sample_rate} Hz\n"
                f"Channels: {info.channels}\n"
                f"Peak Level: {peak_display}\n\n"
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

        # Restart monitoring if tab is visible and a device is selected
        if self._is_visible and self._last_selected_device:
            # Skip monitoring for ScreenCaptureKit (only monitor physical devices)
            if self._last_selected_device == "__screencapture__":
                self.state_label.setText("Ready (ScreenCaptureKit)")
            else:
                success = self.recorder.start_monitoring(
                    device_name=self._last_selected_device,
                    level_callback=self._on_level_update
                )
                if success:
                    self.ctx.logger().info(f"Restarted monitoring after recording: {self._last_selected_device}")
                    self.state_label.setText("Monitoring...")
    
    def _on_level_update(self, level: float):
        """
        Handle audio level update from recorder thread
        
        WHY: Called from recorder thread, must emit signal for thread-safety
        IMPORTANT: Do NOT update GUI directly from here - use signal instead!
        """
        # Emit signal - Qt will marshal this to the GUI thread safely
        self.level_updated.emit(float(level))
    
    @Slot(float)
    def _update_level_meter(self, level: float):
        """
        Update level meter (runs in GUI thread)

        WHY: Receives level_updated signal and safely updates GUI
        """
        # print(f"DEBUG GUI: Updating meter to {level:.3f}")
        
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
        Update duration display, state label, and level meter (polling)
        
        WHY: Called by timer every 100ms. Handles both duration and level updates.
             Polling is more robust than signals for cross-thread updates from ScreenCaptureKit.
        """
        # Update Duration
        duration = self.recorder.get_recording_duration()
        
        # Format duration as MM:SS.d
        minutes = int(duration // 60)
        seconds = duration % 60
        self.duration_label.setText(f"Duration: {minutes:02d}:{seconds:04.1f}")
        
        # Update State Label
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

        # Update Level Meter (Polling)
        # If recording or monitoring, get level directly from recorder
        if state == RecordingState.RECORDING or self.recorder.is_monitoring():
            level = self.recorder.get_current_level()
            self._update_level_meter(level)
    
    def apply_translations(self):
        """
        Apply current language translations

        WHY: Called when language changes; updates all visible text
        """
        # Note: Translation keys would be defined in resources/translations/*.json
        # For now, using English defaults
        pass

    def showEvent(self, event):
        """
        Start monitoring when tab becomes visible

        WHY: Resource-efficient - only monitor when user is viewing the recording tab
        """
        super().showEvent(event)
        self._is_visible = True

        # Start monitoring if a device is selected and we're not recording
        if self._last_selected_device and not self.recorder.is_recording():
            # Skip monitoring for ScreenCaptureKit (only monitor physical devices)
            if self._last_selected_device == "__screencapture__":
                self.state_label.setText("Ready (ScreenCaptureKit)")
                return

            # Only start if not already monitoring
            if not self.recorder.is_monitoring():
                success = self.recorder.start_monitoring(
                    device_name=self._last_selected_device,
                    level_callback=self._on_level_update
                )
                if success:
                    self.ctx.logger().info(
                        f"Recording tab became visible - started monitoring: "
                        f"{self._last_selected_device}"
                    )
                    self.state_label.setText("Monitoring...")

    def hideEvent(self, event):
        """
        Stop monitoring when tab becomes hidden

        WHY: Resource-efficient - don't monitor when user is not viewing the tab
        """
        super().hideEvent(event)
        self._is_visible = False

        # Stop monitoring if active (but don't stop recording!)
        if self.recorder.is_monitoring() and not self.recorder.is_recording():
            self.recorder.stop_monitoring()
            self.ctx.logger().info("Recording tab hidden - stopped monitoring")
            # Reset state label only if not recording
            if not self.recorder.is_recording():
                self.state_label.setText("Ready")

    def closeEvent(self, event):
        """Clean up monitoring when widget is closed"""
        if self.recorder.is_monitoring():
            self.recorder.stop_monitoring()
        super().closeEvent(event)

