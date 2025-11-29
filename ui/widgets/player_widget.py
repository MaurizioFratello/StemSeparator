"""
Player Widget - Stem playback and mixing

PURPOSE: Allow users to play back separated stems with individual volume/mute/solo controls.
CONTEXT: Provides mixing interface for separated audio stems with real-time playback.
"""
from pathlib import Path
from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QGroupBox, QFileDialog, QMessageBox, QListWidget,
    QListWidgetItem, QScrollArea, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from ui.app_context import AppContext
from core.player import get_player, PlaybackState
from ui.theme import ThemeManager
from ui.dialogs import ExportSettingsDialog, LoopExportDialog


class DragDropListWidget(QListWidget):
    """
    QListWidget with drag-and-drop support for audio files

    WHY: QListWidget doesn't support drag-and-drop by default for external files
    """
    files_dropped = Signal(list)  # Emits list of Path objects

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept drag events with file URLs"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Accept drag move events with file URLs"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle dropped files"""
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                file_path = Path(url.toLocalFile())
                if file_path.exists() and file_path.is_file():
                    file_paths.append(file_path)

            if file_paths:
                self.files_dropped.emit(file_paths)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()


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
        
        # Enable styling and set ID for Channel Strip look
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("channelStrip")

        self._setup_ui()

    def _setup_ui(self):
        """Setup stem control layout"""
        # Vertical layout for mixer strip
        layout = QVBoxLayout(self)
        # Increased padding to avoid content touching border
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(10)

        # 1. Stem name (Top)
        name_label = QLabel(self.stem_name.capitalize())
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        # Truncate long names visually if needed, but WordWrap helps
        layout.addWidget(name_label)

        # 2. Mute/Solo buttons (Row)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.setAlignment(Qt.AlignCenter)

        # Mute button
        self.btn_mute = QPushButton("M")
        self.btn_mute.setCheckable(True)
        ThemeManager.set_widget_property(self.btn_mute, "buttonStyle", "icon")
        ThemeManager.set_widget_property(self.btn_mute, "buttonRole", "mute")
        self.btn_mute.setToolTip("Mute this stem")
        self.btn_mute.clicked.connect(self._on_mute_clicked)
        btn_layout.addWidget(self.btn_mute)

        # Solo button
        self.btn_solo = QPushButton("S")
        self.btn_solo.setCheckable(True)
        ThemeManager.set_widget_property(self.btn_solo, "buttonStyle", "icon")
        ThemeManager.set_widget_property(self.btn_solo, "buttonRole", "solo")
        self.btn_solo.setToolTip("Solo this stem (mute all others)")
        self.btn_solo.clicked.connect(self._on_solo_clicked)
        btn_layout.addWidget(self.btn_solo)
        
        layout.addLayout(btn_layout)

        # 3. Fader Section (Meter + Slider side-by-side)
        fader_layout = QHBoxLayout()
        fader_layout.setAlignment(Qt.AlignCenter)
        fader_layout.setSpacing(10)

        # Level Meter (Simulated for now)
        self.meter = QProgressBar()
        self.meter.setOrientation(Qt.Vertical)
        self.meter.setRange(0, 100)
        self.meter.setValue(0)  # Default to 0 until playback
        self.meter.setTextVisible(False)
        self.meter.setFixedWidth(6)
        ThemeManager.set_widget_property(self.meter, "meterStyle", "level")
        fader_layout.addWidget(self.meter)

        # Volume slider (Vertical)
        self.volume_slider = QSlider(Qt.Vertical)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(75)
        self.volume_slider.setMinimumHeight(150)  # Make faders tall enough
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        fader_layout.addWidget(self.volume_slider)

        layout.addLayout(fader_layout)

        # 4. Volume label (Bottom)
        self.volume_label = QLabel("75%")
        self.volume_label.setAlignment(Qt.AlignCenter)
        self.volume_label.setMinimumWidth(40)
        ThemeManager.set_widget_property(self.volume_label, "labelStyle", "caption")
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}%")
        )
        layout.addWidget(self.volume_label)
        
        # Add fixed width to the whole strip to make it look like a channel strip
        self.setFixedWidth(90)

    @Slot()
    def _on_mute_clicked(self):
        """Handle mute button click"""
        self.is_muted = self.btn_mute.isChecked()
        # Force style update for dynamic property
        self.btn_mute.style().unpolish(self.btn_mute)
        self.btn_mute.style().polish(self.btn_mute)
        
        self.mute_changed.emit(self.stem_name, self.is_muted)

    @Slot()
    def _on_solo_clicked(self):
        """Handle solo button click"""
        self.is_solo = self.btn_solo.isChecked()
        # Force style update for dynamic property
        self.btn_solo.style().unpolish(self.btn_solo)
        self.btn_solo.style().polish(self.btn_solo)
        
        self.solo_changed.emit(self.stem_name, self.is_solo)

    @Slot()
    def _on_volume_changed(self):
        """Handle volume change"""
        volume = self.volume_slider.value()
        self.volume_changed.emit(self.stem_name, volume)
        # Update meter to reflect fader position as a simple visual indicator
        self.meter.setValue(volume)


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
    
    # Signal to handle state changes from worker thread safely
    sig_state_changed = Signal(object)  # PlaybackState

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
        # Connect signal to slot for thread safety, then emit signal in callback
        self.sig_state_changed.connect(self._on_state_changed)
        self.player.state_callback = self.sig_state_changed.emit

        self._setup_ui()
        self._connect_signals()
        self.apply_translations()
        
        # Set initial button states (stems list is empty initially)
        self._update_button_states()

        self.ctx.logger().info("PlayerWidget initialized with real playback")

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
        """Setup widget layout"""
        # Create main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # File Loading Card
        load_card, load_layout = self._create_card("Load Stems")

        # Recent files list with drag-and-drop support
        self.stems_list = DragDropListWidget()
        self.stems_list.setMaximumHeight(100)
        load_layout.addWidget(self.stems_list)

        # Load buttons
        load_buttons = QHBoxLayout()
        self.btn_load_dir = QPushButton("📁 Load from Directory")
        ThemeManager.set_widget_property(self.btn_load_dir, "buttonStyle", "secondary")
        self.btn_load_dir.setToolTip("Load all stems from a separated audio directory")
        
        self.btn_load_files = QPushButton("📄 Load Individual Files")
        ThemeManager.set_widget_property(self.btn_load_files, "buttonStyle", "secondary")
        self.btn_load_files.setToolTip("Load individual stem files")
        
        self.btn_remove_selected = QPushButton("Remove Selected")
        ThemeManager.set_widget_property(self.btn_remove_selected, "buttonStyle", "secondary")
        self.btn_remove_selected.setToolTip("Remove selected stems from list (available when stems are selected)")
        
        self.btn_clear = QPushButton("Clear All")
        ThemeManager.set_widget_property(self.btn_clear, "buttonStyle", "secondary")
        self.btn_clear.setToolTip("Clear all stems from list (available when stems are present)")
        load_buttons.addWidget(self.btn_load_dir)
        load_buttons.addWidget(self.btn_load_files)
        load_buttons.addWidget(self.btn_remove_selected)
        load_buttons.addWidget(self.btn_clear)
        load_buttons.addStretch()
        load_layout.addLayout(load_buttons)

        main_layout.addWidget(load_card)

        # Mixer Card
        mixer_card, mixer_layout = self._create_card("Mixer")

        # Scrollable area for stem controls
        self.stems_scroll = QScrollArea()
        self.stems_scroll.setWidgetResizable(True)
        self.stems_scroll.setFrameShape(QScrollArea.NoFrame)
        self.stems_scroll.setStyleSheet("background: transparent;")
        self.stems_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stems_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.stems_scroll_widget = QWidget()
        self.stems_container = QHBoxLayout(self.stems_scroll_widget)
        self.stems_container.setContentsMargins(0, 0, 0, 0)
        self.stems_container.setSpacing(2)  # Tight spacing between strips
        self.stems_container.setAlignment(Qt.AlignLeft)  # Start from left
        
        self.stems_scroll.setWidget(self.stems_scroll_widget)
        mixer_layout.addWidget(self.stems_scroll)

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

        main_layout.addWidget(mixer_card, stretch=1) # Allow mixer to expand

        # Playback Controls Card
        controls_card, controls_layout = self._create_card("Playback")

        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setEnabled(False)
        self.position_slider.setTracking(True)  # Enable continuous updates
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        controls_layout.addWidget(self.position_slider)

        # Time labels (monospace for better readability)
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        ThemeManager.set_widget_property(self.current_time_label, "labelStyle", "mono")
        self.duration_label = QLabel("00:00")
        ThemeManager.set_widget_property(self.duration_label, "labelStyle", "mono")
        time_layout.addWidget(self.current_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.duration_label)
        controls_layout.addLayout(time_layout)

        # Control buttons
        buttons_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_play, "buttonStyle", "success")
        self.btn_play.setToolTip("Play stems (available when stems are loaded)")

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_pause, "buttonStyle", "secondary")
        self.btn_pause.setToolTip("Pause playback (available during playback)")

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        ThemeManager.set_widget_property(self.btn_stop, "buttonStyle", "danger")
        self.btn_stop.setToolTip("Stop playback (available during playback)")

        self.btn_export = QPushButton("💾 Export Mixed Audio")
        self.btn_export.setEnabled(False)
        # Export uses primary style (default)

        self.btn_export_loops = QPushButton("🔁 Export Loops")
        self.btn_export_loops.setEnabled(False)
        self.btn_export_loops.setToolTip("Export as musical loops for samplers (2/4/8 bars)")

        buttons_layout.addWidget(self.btn_play)
        buttons_layout.addWidget(self.btn_pause)
        buttons_layout.addWidget(self.btn_stop)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_export)
        buttons_layout.addWidget(self.btn_export_loops)
        controls_layout.addLayout(buttons_layout)

        main_layout.addWidget(controls_card)

        # Info label
        self.info_label = QLabel(
            "Load separated stems to use the mixer and playback."
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        # Removed global scroll area logic

    def _connect_signals(self):
        """Connect signals"""
        self.btn_load_dir.clicked.connect(self._on_load_dir)
        self.btn_load_files.clicked.connect(self._on_load_files)
        self.btn_remove_selected.clicked.connect(self._on_remove_selected_clicked)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        self.stems_list.files_dropped.connect(self._on_files_dropped)
        self.stems_list.itemSelectionChanged.connect(self._update_button_states)
        self.btn_play.clicked.connect(self._on_play)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_export_loops.clicked.connect(self._on_export_loops)

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

    @Slot(list)
    def _on_files_dropped(self, file_paths: List[Path]):
        """Handle dropped files from drag-and-drop"""
        # Filter to only audio files
        file_manager = self.ctx.file_manager()
        audio_files = [
            f for f in file_paths
            if file_manager.is_supported_format(f)
        ]

        if not audio_files:
            QMessageBox.warning(
                self,
                "No Audio Files",
                "No supported audio files were dropped.\n\n"
                "Supported formats: WAV, MP3, FLAC, M4A, OGG, AAC"
            )
            return

        self._load_stems(audio_files)

    @Slot()
    def _on_remove_selected_clicked(self):
        """Remove selected stem(s) from list and player"""
        selected_items = self.stems_list.selectedItems()
        if not selected_items:
            return

        # Collect stems to remove
        stems_to_remove = []
        for item in selected_items:
            # Extract stem name from list item text (format: "stem_name: filename.wav")
            item_text = item.text()
            stem_name = item_text.split(":")[0].strip()
            stems_to_remove.append(stem_name)

        # Remove items from list
        for item in selected_items:
            row = self.stems_list.row(item)
            self.stems_list.takeItem(row)

        # Remove stems from dictionaries and UI
        for stem_name in stems_to_remove:
            if stem_name in self.stem_files:
                del self.stem_files[stem_name]

            if stem_name in self.stem_controls:
                control = self.stem_controls[stem_name]
                control.deleteLater()
                del self.stem_controls[stem_name]

        # If no stems remain, reset everything
        if len(self.stem_files) == 0:
            self._on_clear_clicked()
        else:
            # Reload remaining stems into player
            self.player.load_stems(self.stem_files)

            # Update duration if stems still loaded
            if self.stem_files:
                duration = self.player.get_duration()
                self.duration_label.setText(self._format_time(duration))
                self.position_slider.setRange(0, int(duration * 1000))
                self.info_label.setText(
                    f"✓ Loaded {len(self.stem_files)} stems. "
                    f"Duration: {self._format_time(duration)}"
                )

        self.ctx.logger().info(f"Removed {len(stems_to_remove)} stem(s) from player")
        
        # Update button states
        self._update_button_states()

    @Slot()
    def _on_clear_clicked(self):
        """Clear all loaded stems and reset player"""
        # Stop playback
        self.player.stop()

        # Clear stem files dictionary
        self.stem_files.clear()

        # Remove and delete all stem controls from layout directly to ensure complete cleanup
        # (Handles cases where dictionary might be out of sync with layout)
        while self.stems_container.count():
            item = self.stems_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.stem_controls.clear()

        # Clear stems list widget
        self.stems_list.clear()

        # Reset player state
        self.position_slider.setValue(0)
        self.position_slider.setEnabled(False)
        self.current_time_label.setText("00:00")
        self.duration_label.setText("00:00")

        # Disable playback and export buttons
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_export_loops.setEnabled(False)

        # Reset info label
        self.info_label.setText(
            "Load separated stems to use the mixer and playback."
        )

        self.ctx.logger().info("Cleared all loaded stems")
        
        # Update button states (all should be disabled now)
        self._update_button_states()

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
            # - "songname_(StemName)_ensemble.wav"  (Ensemble mode)
            # - "songname_stemname_modelname.wav"
            # - "songname_stemname.wav"
            # - "stemname.wav"
            import re

            # First try: Look for stem name in parentheses (most reliable)
            match = re.search(r'\(([^)]+)\)', file_path.stem)
            if match:
                stem_name = match.group(1)
            else:
                # Second try: Parse filename parts, skip model/ensemble suffixes
                name_parts = file_path.stem.split('_')

                # Known suffixes to ignore (model names, ensemble marker)
                ignore_suffixes = {'ensemble', 'bs-roformer', 'mel-roformer', 'demucs',
                                   'htdemucs', '4s', '6s', 'v4', 'demucs4s', 'demucs6s'}

                # Filter out ignored suffixes from the end
                stem_parts = []
                for part in reversed(name_parts):
                    part_lower = part.lower()
                    # Stop when we hit an ignored suffix
                    if part_lower in ignore_suffixes or any(suffix in part_lower for suffix in ignore_suffixes):
                        continue
                    stem_parts.insert(0, part)

                # Use the last meaningful part as stem name
                if stem_parts:
                    stem_name = stem_parts[-1]
                else:
                    # Fallback: use original last part or whole filename
                    stem_name = name_parts[-1] if len(name_parts) > 1 else file_path.stem

            # Ensure unique stem name to prevent overwriting/UI issues
            base_name = stem_name
            counter = 1
            while stem_name in self.stem_files:
                stem_name = f"{base_name} ({counter})"
                counter += 1

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
                # Enable controls (but Play button will check sounddevice availability)
                self.btn_play.setEnabled(True)
                self.btn_export.setEnabled(True)  # Export works without sounddevice
                self.btn_export_loops.setEnabled(True)  # Loop export also works without sounddevice
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

                # Check if playback is available and warn user if not
                is_available, error_msg = self.player.is_playback_available()
                if not is_available:
                    # Show warning but don't block loading
                    QMessageBox.warning(
                        self,
                        "Playback Not Available",
                        f"Stems loaded successfully, but playback is not available:\n\n{error_msg}\n\n"
                        "You can still export mixed audio, but cannot play it back in the app."
                    )
                    # Update info label to reflect this
                    self.info_label.setText(
                        f"✓ Loaded {len(self.stem_files)} stems. "
                        f"Duration: {self._format_time(duration)}\n"
                        "⚠ Playback unavailable (sounddevice not installed)"
                    )
            else:
                QMessageBox.critical(
                    self,
                    "Loading Failed",
                    "Failed to load stems. Check the log for details."
                )
        
        # Update button states based on loaded stems
        self._update_button_states()

    def _get_common_filename(self) -> str:
        """
        Extract common filename from first loaded stem.
        
        WHY: Provides consistent base name for all exports derived from the original
        source file that was separated into stems.
        
        Returns:
            Common filename (e.g., "MySong" from "MySong_(vocals)_ensemble.wav")
            Returns "export" as fallback if no stems are loaded
        """
        if not self.stem_files:
            return "export"
        
        # Get first stem file path
        first_stem_path = Path(list(self.stem_files.values())[0])
        stem_name = first_stem_path.stem
        
        # Try to extract common filename by removing stem name and model suffixes
        import re
        
        # Pattern 1: "songname_(StemName)_modelname" -> "songname"
        match = re.search(r'^(.+?)_\([^)]+\)', stem_name)
        if match:
            return match.group(1)
        
        # Pattern 2: "songname_stemname_modelname" -> "songname"
        # Known suffixes to remove
        ignore_suffixes = {'ensemble', 'bs-roformer', 'mel-roformer', 'demucs',
                          'htdemucs', '4s', '6s', 'v4', 'demucs4s', 'demucs6s'}
        
        parts = stem_name.split('_')
        # Find where stem name starts (usually after common filename)
        # Common pattern: commonname_stemname_suffix
        if len(parts) >= 2:
            # Try to identify stem name (common stem names)
            common_stem_names = ['vocals', 'vocal', 'drums', 'drum', 'bass', 'other',
                                'piano', 'guitar', 'instrumental', 'instrum']
            
            # Find first part that looks like a stem name
            for i, part in enumerate(parts[1:], 1):
                part_lower = part.lower()
                if part_lower in common_stem_names or any(suffix in part_lower for suffix in ignore_suffixes):
                    # Everything before this is the common filename
                    return '_'.join(parts[:i])
        
        # Fallback: use first part or whole name if no pattern matches
        return parts[0] if parts else stem_name

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
        # Check if playback is available first
        is_available, error_msg = self.player.is_playback_available()

        if not is_available:
            QMessageBox.critical(
                self,
                "Playback Not Available",
                error_msg
            )
            return

        # Try to start playback
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
        """Export audio with configurable settings (chunking, format, etc.)"""
        if not self.stem_files:
            return

        # Show export settings dialog
        # Calculate duration in seconds from samples
        duration_seconds = self.player.duration_samples / self.player.sample_rate if self.player.sample_rate > 0 else 0.0

        dialog = ExportSettingsDialog(
            duration_seconds=duration_seconds,
            num_stems=len(self.stem_files),
            parent=self
        )

        if dialog.exec() != ExportSettingsDialog.Accepted:
            # User cancelled
            return

        # Get settings from dialog
        settings = dialog.get_settings()

        # Ask user for output location
        if settings.enable_chunking and settings.export_mode == 'individual':
            # Individual stems with chunking - ask for directory
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory for Stem Chunks",
                ""
            )

            if not output_dir:
                return

            output_path = Path(output_dir)

        else:
            # Mixed audio (with or without chunking) - ask for file
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

        # Execute export based on settings
        success = False
        result_message = ""
        
        # Get common filename from first loaded stem
        common_filename = self._get_common_filename()

        try:
            if settings.enable_chunking:
                if settings.export_mode == 'mixed':
                    # Mixed audio in chunks
                    chunk_paths = self.player.export_mix_chunked(
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
                            f"{output_path.parent}\n\n"
                            f"Files: {common_filename}_01{output_path.suffix}, "
                            f"{common_filename}_02{output_path.suffix}, ..."
                        )
                    else:
                        result_message = "Failed to export chunks. Check the log for details."

                else:  # individual stems
                    # Individual stems in chunks
                    all_chunks = self.player.export_stems_chunked(
                        output_path,
                        settings.chunk_length,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
                        common_filename=common_filename
                    )

                    if all_chunks:
                        success = True
                        total_files = sum(len(chunks) for chunks in all_chunks.values())
                        stems_list = ", ".join(all_chunks.keys())
                        result_message = (
                            f"Exported {len(all_chunks)} stems as {total_files} total chunks:\n"
                            f"{output_path}\n\n"
                            f"Stems: {stems_list}"
                        )
                    else:
                        result_message = "Failed to export stem chunks. Check the log for details."

            else:
                # No chunking - standard export
                if settings.export_mode == 'mixed':
                    # Standard mixed export
                    success = self.player.export_mix(
                        output_path,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth
                    )

                    if success:
                        result_message = f"Mixed audio exported to:\n{output_path}"
                    else:
                        result_message = "Failed to export mixed audio. Check the log for details."

                else:  # individual stems without chunking
                    # Export individual stems as full files
                    all_chunks = self.player.export_stems_chunked(
                        output_path,
                        chunk_length_seconds=999999,  # Very long chunks = no splitting
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth
                    )

                    if all_chunks:
                        success = True
                        stems_list = ", ".join(all_chunks.keys())
                        result_message = (
                            f"Exported {len(all_chunks)} individual stems:\n"
                            f"{output_path}\n\n"
                            f"Stems: {stems_list}"
                        )
                    else:
                        result_message = "Failed to export stems. Check the log for details."

            # Show result message
            if success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    result_message
                )
            else:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    result_message
                )

        except Exception as e:
            self.ctx.logger().error(f"Export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during export:\n{str(e)}"
            )

    def _get_audio_for_bpm_detection(self) -> tuple[Path, str]:
        """
        Get the best audio source for BPM detection with hierarchical selection.

        Priority:
        1. Drums stem (best for rhythm detection)
        2. Mixed audio of all stems (fallback)

        Returns:
            Tuple of (audio_file_path, source_description)
        """
        import tempfile
        import soundfile as sf

        # Priority 1: Check if drums stem is available
        drums_stem_names = ['drums', 'Drums', 'DRUMS', 'drum', 'Drum', 'DRUM']
        for stem_name in drums_stem_names:
            if stem_name in self.stem_files:
                drums_path = Path(self.stem_files[stem_name])
                self.ctx.logger().info(f"Using drums stem for BPM detection: {drums_path.name}")
                return drums_path, f"drums stem ({drums_path.name})"

        # Priority 2: No drums found, create mixed audio from all stems
        self.ctx.logger().info("No drums stem found, using mixed audio for BPM detection")

        # Mix all stems
        mixed_audio = self.player._mix_stems(0, self.player.duration_samples)
        if mixed_audio is None or len(mixed_audio) == 0:
            # Fallback to first available stem if mixing fails
            first_stem_name = list(self.stem_files.keys())[0]
            first_stem_path = Path(self.stem_files[first_stem_name])
            self.ctx.logger().warning(
                f"Failed to mix stems, falling back to first stem: {first_stem_name}"
            )
            return first_stem_path, f"first available stem ({first_stem_name})"

        # Transpose to (samples, channels) for soundfile
        mixed_audio = mixed_audio.T

        # Create temporary file with mixed audio
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.wav',
                delete=False,
                prefix='bpm_detect_'
            )
            temp_path = Path(temp_file.name)
            temp_file.close()

            # Write mixed audio to temp file
            sf.write(
                str(temp_path),
                mixed_audio,
                self.player.sample_rate,
                subtype='PCM_24'
            )

            self.ctx.logger().info(f"Created mixed audio for BPM detection: {temp_path.name}")
            return temp_path, "mixed audio (all stems)"

        except Exception as e:
            self.ctx.logger().error(f"Failed to create mixed audio file for BPM detection: {e}")
            # Final fallback: use first stem
            first_stem_name = list(self.stem_files.keys())[0]
            first_stem_path = Path(self.stem_files[first_stem_name])
            return first_stem_path, f"first available stem ({first_stem_name})"

    @Slot()
    def _on_export_loops(self):
        """Export audio as sampler loops with BPM-based bar lengths"""
        if not self.stem_files:
            return

        try:
            # Check if stems are loaded
            if not self.player.stems:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "No stems loaded. Please load audio files first."
                )
                return

            # Mix all stems to get complete audio
            # _mix_stems returns audio in shape (channels, samples)
            mixed_audio = self.player._mix_stems(0, self.player.duration_samples)

            if mixed_audio is None or len(mixed_audio) == 0:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Unable to mix audio for export. Please try loading stems again."
                )
                return

            # Transpose to (samples, channels) for soundfile compatibility
            mixed_audio = mixed_audio.T

            # Calculate duration
            duration_seconds = self.player.duration_samples / self.player.sample_rate if self.player.sample_rate > 0 else 0.0

            # Get common filename from first loaded stem
            common_filename = self._get_common_filename()

            # Show loop export dialog (BPM detection moved inside dialog)
            dialog = LoopExportDialog(
                player_widget=self,
                duration_seconds=duration_seconds,
                num_stems=len(self.stem_files),
                parent=self
            )

            if dialog.exec() != LoopExportDialog.Accepted:
                return

            # Get settings from dialog
            settings = dialog.get_settings()

            # Ask user for output directory
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory for Loop Export"
            )

            if not output_dir:
                return

            output_path = Path(output_dir)

            # Import required modules
            import tempfile
            import soundfile as sf
            from core.sampler_export import export_sampler_loops
            from PySide6.QtWidgets import QProgressDialog, QApplication

            # Check export mode
            if settings.export_mode == 'individual':
                # Export each stem individually
                self._export_individual_stems(
                    output_path=output_path,
                    settings=settings
                )
            else:
                # Export mixed audio (original logic)
                with tempfile.NamedTemporaryFile(
                    suffix='.wav',
                    delete=False,
                    dir=str(output_path.parent)
                ) as temp_file:
                    temp_path = Path(temp_file.name)

                    try:
                        # Export current mix to temporary file
                        sf.write(
                            str(temp_path),
                            mixed_audio,
                            self.player.sample_rate,
                            subtype='PCM_24'
                        )

                        # Progress dialog
                        progress_dialog = QProgressDialog(
                            "Preparing export...",
                            None,
                            0,
                            100,
                            self
                        )
                        progress_dialog.setWindowTitle("Exporting Loops")
                        progress_dialog.setWindowModality(Qt.WindowModal)
                        progress_dialog.setMinimumDuration(0)
                        progress_dialog.setValue(0)

                        # Export with progress callback
                        def progress_callback(message: str, percent: int):
                            progress_dialog.setLabelText(message)
                            progress_dialog.setValue(percent)
                            QApplication.processEvents()

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
                            stem_name=None  # Mixed audio, no stem name
                        )

                        # Close progress dialog
                        progress_dialog.setValue(100)
                        progress_dialog.close()
                        QApplication.processEvents()

                        # Show result
                        if result.success:
                            warning_text = ""
                            if result.warning_messages:
                                warning_text = "\n\nWarnings:\n" + "\n".join(f"• {w}" for w in result.warning_messages)

                            QMessageBox.information(
                                self,
                                "Export Successful",
                                f"Exported {result.chunk_count} loop file(s) to:\n{output_path}\n\n"
                                f"Format: {settings.file_format}, {settings.bit_depth} bit, "
                                f"{'Stereo' if settings.channels == 2 else 'Mono'}\n"
                                f"Loop length: {settings.bars} bars at {settings.bpm} BPM"
                                f"{warning_text}"
                            )
                        else:
                            QMessageBox.critical(
                                self,
                                "Export Failed",
                                f"Loop export failed:\n{result.error_message}"
                            )

                    finally:
                        # Clean up temporary file
                        try:
                            temp_path.unlink()
                        except Exception as e:
                            self.ctx.logger().warning(f"Failed to delete temp file {temp_path}: {e}")

        except Exception as e:
            self.ctx.logger().error(f"Loop export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during loop export:\n{str(e)}"
            )

    def _export_individual_stems(self, output_path: Path, settings):
        """Export each stem individually as loops"""
        import soundfile as sf
        from core.sampler_export import export_sampler_loops
        from PySide6.QtWidgets import QProgressDialog, QApplication

        # Get common filename from first loaded stem
        common_filename = self._get_common_filename()

        try:
            # Create progress dialog for overall progress
            overall_progress = QProgressDialog(
                "Preparing stem export...",
                None,
                0,
                len(self.stem_files) * 100,
                self
            )
            overall_progress.setWindowTitle("Exporting Individual Stems")
            overall_progress.setWindowModality(Qt.WindowModal)
            overall_progress.setMinimumDuration(0)
            overall_progress.setValue(0)

            total_chunks = 0
            all_warnings = []
            stem_results = []

            # Export each stem
            for stem_idx, (stem_name, stem_path) in enumerate(self.stem_files.items()):
                stem_file = Path(stem_path)

                # Update overall progress
                base_progress = stem_idx * 100
                overall_progress.setLabelText(f"Exporting {stem_name}...")
                overall_progress.setValue(base_progress)
                QApplication.processEvents()

                # Progress callback for this stem
                def progress_callback(message: str, percent: int):
                    overall_progress.setLabelText(f"Exporting {stem_name}...\n{message}")
                    overall_progress.setValue(base_progress + percent)
                    QApplication.processEvents()

                # Export this stem as loops
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
                    stem_name=stem_name  # Individual stem export
                )

                if result.success:
                    total_chunks += result.chunk_count
                    stem_results.append((stem_name, result.chunk_count))
                    if result.warning_messages:
                        all_warnings.extend([f"{stem_name}: {w}" for w in result.warning_messages])
                else:
                    # Log error but continue with other stems
                    self.ctx.logger().error(f"Failed to export {stem_name}: {result.error_message}")
                    all_warnings.append(f"{stem_name}: Export failed - {result.error_message}")

            # Close progress dialog
            overall_progress.setValue(len(self.stem_files) * 100)
            overall_progress.close()
            QApplication.processEvents()

            # Show summary
            if total_chunks > 0:
                # Build summary text
                summary_lines = [f"• {name}: {count} file(s)" for name, count in stem_results]
                summary_text = "\n".join(summary_lines)

                warning_text = ""
                if all_warnings:
                    warning_text = "\n\nWarnings:\n" + "\n".join(f"• {w}" for w in all_warnings)

                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {total_chunks} loop file(s) total from {len(stem_results)} stem(s) to:\n{output_path}\n\n"
                    f"{summary_text}\n\n"
                    f"Format: {settings.file_format}, {settings.bit_depth} bit, "
                    f"{'Stereo' if settings.channels == 2 else 'Mono'}\n"
                    f"Loop length: {settings.bars} bars at {settings.bpm} BPM"
                    f"{warning_text}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    "Failed to export any stems. Check the log for details."
                )

        except Exception as e:
            self.ctx.logger().error(f"Individual stem export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during individual stem export:\n{str(e)}"
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
            # Update position display to reflect reset to 0
            # This ensures UI is in sync when playback finishes naturally
            position = self.player.get_position()
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(int(position * 1000))
            self.position_slider.blockSignals(False)
            self.current_time_label.setText(self._format_time(position))

    def _update_button_states(self):
        """
        Update button enabled states based on stem list and selection
        
        WHY: Buttons should only be enabled when their action is meaningful.
             Consistent with UploadWidget behavior.
        """
        has_stems = self.stems_list.count() > 0
        has_selection = len(self.stems_list.selectedItems()) > 0

        self.btn_remove_selected.setEnabled(has_selection)
        self.btn_clear.setEnabled(has_stems)

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

        # Perform the seek (works even when stopped - allows restarting from different position)
        self.player.set_position(position_s)
        self.ctx.logger().info(f"User seeked to {self._format_time(position_s)}")

        # Explicitly set slider to the seek position to prevent jump-back
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position_ms)
        self.position_slider.blockSignals(False)

        # Update time label immediately
        self.current_time_label.setText(self._format_time(position_s))

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
