"""
Player Widget - Stem playback and mixing

PURPOSE: Allow users to play back separated stems with individual volume/mute/solo controls.
CONTEXT: Provides mixing interface for separated audio stems with real-time playback.
"""
from pathlib import Path
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QGroupBox, QFileDialog, QMessageBox, QListWidget,
    QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from ui.app_context import AppContext
from core.player import get_player, PlaybackState


class StemControl(QWidget):
    """
    Individual stem control with volume, mute, solo

    WHY: Encapsulates per-stem mixing controls for cleaner layout
    """

    mute_changed = Signal(str, bool)  # stem_name, is_muted
    solo_changed = Signal(str, bool)  # stem_name, is_solo
    volume_changed = Signal(str, int)  # stem_name, volume (0-100)

    def __init__(self, stem_name: str, parent=None):
        super().__init__(parent)
        self.stem_name = stem_name
        self.is_muted = False
        self.is_solo = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup stem control layout"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stem name
        name_label = QLabel(self.stem_name.capitalize())
        name_label.setMinimumWidth(80)
        layout.addWidget(name_label)

        # Mute button
        self.btn_mute = QPushButton("M")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setMaximumWidth(30)
        self.btn_mute.setToolTip("Mute this stem")
        self.btn_mute.clicked.connect(self._on_mute_clicked)
        layout.addWidget(self.btn_mute)

        # Solo button
        self.btn_solo = QPushButton("S")
        self.btn_solo.setCheckable(True)
        self.btn_solo.setMaximumWidth(30)
        self.btn_solo.setToolTip("Solo this stem (mute all others)")
        self.btn_solo.clicked.connect(self._on_solo_clicked)
        layout.addWidget(self.btn_solo)

        # Volume slider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(75)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider)

        # Volume label
        self.volume_label = QLabel("75%")
        self.volume_label.setMinimumWidth(40)
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}%")
        )
        layout.addWidget(self.volume_label)

    @Slot()
    def _on_mute_clicked(self):
        """Handle mute button click"""
        self.is_muted = self.btn_mute.isChecked()
        self.mute_changed.emit(self.stem_name, self.is_muted)

        # Update style
        if self.is_muted:
            self.btn_mute.setStyleSheet("background-color: #ff6b6b;")
        else:
            self.btn_mute.setStyleSheet("")

    @Slot()
    def _on_solo_clicked(self):
        """Handle solo button click"""
        self.is_solo = self.btn_solo.isChecked()
        self.solo_changed.emit(self.stem_name, self.is_solo)

        # Update style
        if self.is_solo:
            self.btn_solo.setStyleSheet("background-color: #51cf66;")
        else:
            self.btn_solo.setStyleSheet("")

    @Slot()
    def _on_volume_changed(self):
        """Handle volume change"""
        volume = self.volume_slider.value()
        self.volume_changed.emit(self.stem_name, volume)


class PlayerWidget(QWidget):
    """
    Widget for playing and mixing separated stems

    Features:
    - Load separated stems
    - Individual volume control per stem
    - Mute/solo per stem
    - Master volume
    - Playback controls (play/pause/stop)
    - Position slider with seek
    - Export mixed audio
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = AppContext()
        self.player = get_player()
        self.stem_files: Dict[str, Path] = {}
        self.stem_controls: Dict[str, StemControl] = {}

        # Position update timer
        self.position_timer = QTimer(self)
        self.position_timer.timeout.connect(self._update_position)
        self.position_timer.setInterval(100)  # 100ms updates

        # Track if user is seeking
        self._user_seeking = False

        # Setup player callbacks
        self.player.position_callback = self._on_position_update
        self.player.state_callback = self._on_state_changed

        self._setup_ui()
        self._connect_signals()
        self.apply_translations()

        self.ctx.logger().info("PlayerWidget initialized with real playback")

    def _setup_ui(self):
        """Setup widget layout"""
        layout = QVBoxLayout(self)

        # File Loading Group
        load_group = QGroupBox("Load Stems")
        load_layout = QVBoxLayout()

        # Recent files list
        self.stems_list = QListWidget()
        self.stems_list.setMaximumHeight(100)
        load_layout.addWidget(self.stems_list)

        # Load buttons
        load_buttons = QHBoxLayout()
        self.btn_load_dir = QPushButton("Load from Directory")
        self.btn_load_files = QPushButton("Load Individual Files")
        load_buttons.addWidget(self.btn_load_dir)
        load_buttons.addWidget(self.btn_load_files)
        load_buttons.addStretch()
        load_layout.addLayout(load_buttons)

        load_group.setLayout(load_layout)
        layout.addWidget(load_group)

        # Mixer Group
        mixer_group = QGroupBox("Mixer")
        mixer_layout = QVBoxLayout()

        self.stems_container = QVBoxLayout()
        mixer_layout.addLayout(self.stems_container)

        # Master volume
        master_layout = QHBoxLayout()
        master_layout.addWidget(QLabel("Master Volume:"))
        self.master_slider = QSlider(Qt.Horizontal)
        self.master_slider.setRange(0, 100)
        self.master_slider.setValue(100)
        master_layout.addWidget(self.master_slider)
        self.master_label = QLabel("100%")
        self.master_slider.valueChanged.connect(self._on_master_volume_changed)
        master_layout.addWidget(self.master_label)
        mixer_layout.addLayout(master_layout)

        mixer_group.setLayout(mixer_layout)
        layout.addWidget(mixer_group)

        # Playback Controls Group
        controls_group = QGroupBox("Playback")
        controls_layout = QVBoxLayout()

        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setEnabled(False)
        self.position_slider.setTracking(True)  # Enable continuous updates
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        controls_layout.addWidget(self.position_slider)

        # Time labels
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.duration_label = QLabel("00:00")
        time_layout.addWidget(self.current_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.duration_label)
        controls_layout.addLayout(time_layout)

        # Control buttons
        buttons_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setEnabled(False)
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setEnabled(False)
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_export = QPushButton("💾 Export Mixed Audio")
        self.btn_export.setEnabled(False)

        buttons_layout.addWidget(self.btn_play)
        buttons_layout.addWidget(self.btn_pause)
        buttons_layout.addWidget(self.btn_stop)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_export)
        controls_layout.addLayout(buttons_layout)

        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        # Info label
        self.info_label = QLabel(
            "Load separated stems to use the mixer and playback."
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        layout.addStretch()

    def _connect_signals(self):
        """Connect signals"""
        self.btn_load_dir.clicked.connect(self._on_load_dir)
        self.btn_load_files.clicked.connect(self._on_load_files)
        self.btn_play.clicked.connect(self._on_play)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_export.clicked.connect(self._on_export)

    @Slot()
    def _on_load_dir(self):
        """Load all stems from directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory with Stems"
        )

        if not directory:
            return

        dir_path = Path(directory)

        # Find audio files
        file_manager = self.ctx.file_manager()
        audio_files = file_manager.list_audio_files(dir_path)

        if not audio_files:
            QMessageBox.warning(
                self,
                "No Audio Files",
                f"No supported audio files found in:\n{dir_path}"
            )
            return

        self._load_stems(audio_files)

    @Slot()
    def _on_load_files(self):
        """Load individual stem files"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg *.aac)")

        if file_dialog.exec():
            file_paths = [Path(f) for f in file_dialog.selectedFiles()]
            self._load_stems(file_paths)

    def _load_stems(self, file_paths: list[Path]):
        """Load stem files into player"""
        self.stem_files.clear()

        # Clear existing controls
        for control in self.stem_controls.values():
            control.deleteLater()
        self.stem_controls.clear()

        # Clear stems list
        self.stems_list.clear()

        # Parse stem files
        for file_path in file_paths:
            # Try to extract stem name from filename
            # Expected formats:
            # - "songname_(StemName)_modelname.wav"
            # - "songname_stemname.wav"
            # - "stemname.wav"
            import re
            match = re.search(r'\(([^)]+)\)', file_path.stem)
            if match:
                stem_name = match.group(1)
            else:
                name_parts = file_path.stem.split('_')
                stem_name = name_parts[-1] if len(name_parts) > 1 else file_path.stem

            self.stem_files[stem_name] = file_path

            # Add to list
            self.stems_list.addItem(f"{stem_name}: {file_path.name}")

            # Create control
            control = StemControl(stem_name, self)
            control.volume_changed.connect(self._on_stem_volume_changed)
            control.mute_changed.connect(self._on_stem_mute_changed)
            control.solo_changed.connect(self._on_stem_solo_changed)
            self.stem_controls[stem_name] = control
            self.stems_container.addWidget(control)

        # Load into player
        if self.stem_files:
            success = self.player.load_stems(self.stem_files)

            if success:
                # Enable controls
                self.btn_play.setEnabled(True)
                self.btn_export.setEnabled(True)
                self.position_slider.setEnabled(True)

                # Update duration
                duration = self.player.get_duration()
                self.duration_label.setText(self._format_time(duration))
                self.position_slider.setRange(0, int(duration * 1000))  # milliseconds

                self.info_label.setText(
                    f"✓ Loaded {len(self.stem_files)} stems. "
                    f"Duration: {self._format_time(duration)}"
                )

                self.ctx.logger().info(f"Loaded {len(self.stem_files)} stems for playback")
            else:
                QMessageBox.critical(
                    self,
                    "Loading Failed",
                    "Failed to load stems. Check the log for details."
                )

    @Slot(str, int)
    def _on_stem_volume_changed(self, stem_name: str, volume: int):
        """Handle stem volume change"""
        # Convert 0-100 to 0.0-1.0
        volume_float = volume / 100.0
        self.player.set_stem_volume(stem_name, volume_float)

    @Slot(str, bool)
    def _on_stem_mute_changed(self, stem_name: str, is_muted: bool):
        """Handle stem mute change"""
        self.player.set_stem_mute(stem_name, is_muted)

    @Slot(str, bool)
    def _on_stem_solo_changed(self, stem_name: str, is_solo: bool):
        """Handle stem solo change"""
        self.player.set_stem_solo(stem_name, is_solo)

    @Slot()
    def _on_master_volume_changed(self):
        """Handle master volume change"""
        volume = self.master_slider.value()
        volume_float = volume / 100.0
        self.player.set_master_volume(volume_float)
        self.master_label.setText(f"{volume}%")

    @Slot()
    def _on_play(self):
        """Start playback"""
        success = self.player.play()

        if not success:
            QMessageBox.warning(
                self,
                "Playback Failed",
                "Failed to start playback. Make sure audio device is available."
            )

    @Slot()
    def _on_pause(self):
        """Pause playback"""
        self.player.pause()

    @Slot()
    def _on_stop(self):
        """Stop playback"""
        self.player.stop()
        self.position_slider.setValue(0)
        self.current_time_label.setText("00:00")

    @Slot()
    def _on_export(self):
        """Export mixed audio to file"""
        if not self.stem_files:
            return

        save_path, file_filter = QFileDialog.getSaveFileName(
            self,
            "Export Mixed Audio",
            "",
            "WAV Files (*.wav);;FLAC Files (*.flac)"
        )

        if not save_path:
            return

        # Determine format from filter
        file_format = 'WAV' if 'WAV' in file_filter else 'FLAC'

        # Export
        success = self.player.export_mix(Path(save_path), file_format=file_format)

        if success:
            QMessageBox.information(
                self,
                "Export Successful",
                f"Mixed audio exported to:\n{save_path}"
            )
        else:
            QMessageBox.critical(
                self,
                "Export Failed",
                "Failed to export mixed audio. Check the log for details."
            )

    def _on_position_update(self, position: float, duration: float):
        """Callback from player for position updates"""
        # Update in GUI thread
        # This is called from playback thread, so we use a timer for updates
        pass

    def _on_state_changed(self, state: PlaybackState):
        """Callback from player for state changes"""
        # Update button states based on playback state
        if state == PlaybackState.PLAYING:
            self.btn_play.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.position_timer.start()
        elif state == PlaybackState.PAUSED:
            self.btn_play.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.position_timer.stop()
        else:  # STOPPED
            self.btn_play.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.position_timer.stop()

    @Slot()
    def _update_position(self):
        """Update position slider from player (called by timer)"""
        # Don't update if user is currently seeking
        if self._user_seeking:
            return

        position = self.player.get_position()
        duration = self.player.get_duration()

        # Update slider
        self.position_slider.blockSignals(True)  # Prevent triggering valueChanged
        self.position_slider.setValue(int(position * 1000))
        self.position_slider.blockSignals(False)

        # Update time label
        self.current_time_label.setText(self._format_time(position))

    @Slot()
    def _on_slider_pressed(self):
        """Handle slider press (start seeking)"""
        self._user_seeking = True
        self.ctx.logger().debug("User started seeking")

    @Slot()
    def _on_slider_moved(self, value):
        """Handle slider movement (update time display while seeking)"""
        # Update time display to show where we would seek to
        position_s = value / 1000.0
        self.current_time_label.setText(self._format_time(position_s))

    @Slot()
    def _on_slider_released(self):
        """Handle slider release (perform seek)"""
        position_ms = self.position_slider.value()
        position_s = position_ms / 1000.0

        # Perform the seek
        self.player.set_position(position_s)
        self.ctx.logger().info(f"User seeked to {self._format_time(position_s)}")

        # Explicitly set slider to the seek position to prevent jump-back
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position_ms)
        self.position_slider.blockSignals(False)

        # Use QTimer.singleShot to re-enable updates after a short delay
        # This prevents race condition with position timer
        QTimer.singleShot(50, lambda: setattr(self, '_user_seeking', False))

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def load_separation_result(self, stems: Dict[str, Path]):
        """Load stems from separation result"""
        if stems:
            self._load_stems(list(stems.values()))

    def apply_translations(self):
        """Apply current language translations"""
        # Translation keys would be defined in resources/translations/*.json
        pass

    def closeEvent(self, event):
        """Handle widget close"""
        # Stop playback and cleanup
        self.player.stop()
        super().closeEvent(event)
