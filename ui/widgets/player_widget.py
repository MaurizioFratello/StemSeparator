"""
Player Widget - Stem playback and mixing

PURPOSE: Allow users to play back separated stems with individual volume/mute/solo controls.
CONTEXT: Provides mixing interface for separated audio stems with real-time playback.
"""

from pathlib import Path
from typing import Optional, Dict, List, Tuple
import numpy as np
import soundfile as sf

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QProgressBar,
    QFrame,
    QStackedWidget,
    QSpinBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QRunnable, QThreadPool, QObject
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from ui.app_context import AppContext
from core.player import get_player, PlaybackState
from ui.theme import ThemeManager
from ui.dialogs import ExportSettingsDialog, LoopExportDialog
from ui.widgets.loop_waveform_widget import LoopWaveformWidget
from utils import beat_detection

# Forward reference for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.background_stretch_manager import BackgroundStretchManager


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


class BeatAnalysisWorker(QRunnable):
    """
    Background worker for beat analysis.

    PURPOSE: Run BeatNet beat detection without blocking GUI thread
    CONTEXT: Uses beat_service_client subprocess for isolation
    """

    class Signals(QObject):
        finished = Signal(object, object, float, str)  # beats, downbeats, first_db, msg
        error = Signal(str)
        progress = Signal(str, str)  # phase, detail

    def __init__(self, audio_path: Path, logger, bpm_audio_path: Optional[Path] = None):
        super().__init__()
        self.audio_path = audio_path
        self.bpm_audio_path = (
            bpm_audio_path  # Separate path for BPM detection (e.g., drums)
        )
        self.logger = logger
        self.signals = self.Signals()
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the analysis."""
        self._cancelled = True

    def _progress_callback(self, phase: str, detail: str):
        """Callback for progress updates from beat_detection."""
        if not self._cancelled:
            self.signals.progress.emit(phase, detail)

    def run(self):
        """Execute beat analysis in background."""
        try:
            self.signals.progress.emit("Starting", "Preparing beat analysis...")

            if self._cancelled:
                return

            beat_times, downbeat_times, first_downbeat, conf_msg = (
                beat_detection.detect_beats_and_downbeats(
                    self.audio_path,
                    bpm_audio_path=self.bpm_audio_path,
                    progress_callback=self._progress_callback,
                )
            )

            if self._cancelled:
                return

            self.signals.progress.emit("Complete", "Processing results...")
            self.signals.finished.emit(
                beat_times, downbeat_times, first_downbeat, conf_msg
            )

        except Exception as e:
            if not self._cancelled:
                self.logger.error(f"Beat analysis error: {e}", exc_info=True)
                self.signals.error.emit(str(e))


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
        self.btn_mute.setFocusPolicy(Qt.NoFocus)  # Prevent auto-focus blue border
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
    - Export mixed audio (triggered from sidebar)
    """

    # Signal to handle state changes from worker thread safely
    sig_state_changed = Signal(object)  # PlaybackState

    # Signal emitted when stems are loaded or cleared
    # WHY: Allows MainWindow to enable/disable Export buttons in sidebar
    stems_loaded_changed = Signal(bool)  # True if stems loaded, False if cleared

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

        # Loop preview state
        self.detected_beat_times: Optional[np.ndarray] = None
        self.detected_downbeat_times: Optional[np.ndarray] = None
        self.detected_loop_segments: List[Tuple[float, float]] = []
        self.detected_intro_loops: List[Tuple[float, float]] = (
            []
        )  # Leading loops if song start marker is set
        self.selected_loop_index: int = -1
        self._bars_per_loop: int = 4  # Default: 4 bars per loop

        # Song start marker state
        self.song_start_downbeat_index: Optional[int] = (
            None  # Index in detected_downbeat_times
        )
        self.intro_handling: str = "pad"  # "pad" or "skip"

        # Beat analysis worker (for async detection)
        self._beat_analysis_worker: Optional[BeatAnalysisWorker] = None
        self._thread_pool = QThreadPool()

        # Time-stretching state
        self.time_stretch_enabled: bool = False
        self.time_stretch_target_bpm: int = 120
        self.stretch_manager: Optional['BackgroundStretchManager'] = None
        self._loop_index_mapping: Dict[int, int] = {}  # Maps original loop index to filtered index

        # Beat analysis countdown timer
        self._beat_analysis_timer = QTimer(self)
        self._beat_analysis_timer.timeout.connect(self._update_beat_analysis_countdown)
        self._beat_analysis_timer.setInterval(1000)  # Update every second
        self._beat_analysis_start_time: float = 0.0
        self._beat_analysis_timeout: float = 120.0
        self._beat_analysis_phase: str = ""
        self._beat_analysis_detail: str = ""

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

    def _extract_bpm_summary(self, conf_msg: str) -> Optional[str]:
        """
        Extract a compact 'BPM (confidence)' summary from conf_msg.

        Expected formats:
            "DeepRhythm (85%): 104.0 BPM, 87 downbeats (grid: BeatNet)"
            "librosa: 104.0 BPM, 87 downbeats (grid: BeatNet)"
            "Fallback: 103.0 BPM (63%) - ..."
        """
        import re

        if not conf_msg:
            return None

        # DeepRhythm with confidence: "DeepRhythm (85%): 104.0 BPM, ..."
        m = re.search(r"DeepRhythm\s*\((\d+)%\):\s*([\d.]+)\s*BPM", conf_msg)
        if m:
            conf = m.group(1)
            bpm = m.group(2)
            return f"{bpm} BPM ({conf}%)"

        # Fallback pattern: "Fallback: 103.0 BPM (63%) - ..."
        m = re.search(r"Fallback:\s*([\d.]+)\s*BPM\s*\((\d+)%\)", conf_msg)
        if m:
            bpm = m.group(1)
            conf = m.group(2)
            return f"{bpm} BPM ({conf}%)"

        # Generic BPM only: "... 104.0 BPM ..."
        m = re.search(r"([\d.]+)\s*BPM", conf_msg)
        if m:
            bpm = m.group(1)
            return f"{bpm} BPM"

        return None

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
        """
        Setup widget layout with stacked pages (navigation via sidebar).

        PURPOSE: Provide 3 pages (Stems, Playback, Looping) controlled by MainWindow sidebar
        CONTEXT: Replaced QTabWidget with QStackedWidget for sidebar-based navigation
        """
        # Create main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # === STACKED WIDGET (navigation via sidebar, not tabs) ===
        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("playerPages")

        # Create pages (3 pages: Stems, Playback, Looping)
        self.stems_page = self._create_stems_tab()
        self.playback_page = self._create_playback_tab()
        self.looping_page = self._create_loop_preview_tab()

        # Add pages to stack
        self._page_stack.addWidget(self.stems_page)  # Index 0
        self._page_stack.addWidget(self.playback_page)  # Index 1
        self._page_stack.addWidget(self.looping_page)  # Index 2

        main_layout.addWidget(self._page_stack)

        # Connect page change signal (for internal logic like loop preparation)
        self._page_stack.currentChanged.connect(self._on_page_changed)

    def _create_stems_tab(self) -> QWidget:
        """
        Create stems tab for loading stem files.

        PURPOSE: Separate tab for stem file management (Load, Remove, Clear)
        CONTEXT: Part of UI restructuring - moved from Playback tab
        """
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(15)

        # File Loading Card
        load_card, load_layout = self._create_card("Load Stems")

        # Recent files list with drag-and-drop support
        self.stems_list = DragDropListWidget()
        self.stems_list.setMinimumHeight(200)
        load_layout.addWidget(self.stems_list)

        # Load buttons
        load_buttons = QHBoxLayout()
        self.btn_load_dir = QPushButton("📁 Load from Directory")
        ThemeManager.set_widget_property(self.btn_load_dir, "buttonStyle", "secondary")
        self.btn_load_dir.setToolTip("Load all stems from a separated audio directory")

        self.btn_load_files = QPushButton("📄 Load Individual Files")
        ThemeManager.set_widget_property(
            self.btn_load_files, "buttonStyle", "secondary"
        )
        self.btn_load_files.setToolTip("Load individual stem files")

        self.btn_remove_selected = QPushButton("Remove Selected")
        ThemeManager.set_widget_property(
            self.btn_remove_selected, "buttonStyle", "secondary"
        )
        self.btn_remove_selected.setToolTip(
            "Remove selected stems from list (available when stems are selected)"
        )

        self.btn_clear = QPushButton("Clear All")
        ThemeManager.set_widget_property(self.btn_clear, "buttonStyle", "secondary")
        self.btn_clear.setToolTip(
            "Clear all stems from list (available when stems are present)"
        )
        load_buttons.addWidget(self.btn_load_dir)
        load_buttons.addWidget(self.btn_load_files)
        load_buttons.addWidget(self.btn_remove_selected)
        load_buttons.addWidget(self.btn_clear)
        load_buttons.addStretch()
        load_layout.addLayout(load_buttons)

        tab_layout.addWidget(load_card)

        # Info label for stems tab
        self.stems_info_label = QLabel(
            "Drag & drop stem files here, or use the buttons above to load stems.\n"
            "Supported formats: WAV, MP3, FLAC, M4A, OGG, AAC"
        )
        self.stems_info_label.setAlignment(Qt.AlignCenter)
        self.stems_info_label.setWordWrap(True)
        self.stems_info_label.setStyleSheet(
            "color: #888; font-size: 10pt; padding: 20px;"
        )
        tab_layout.addWidget(self.stems_info_label)

        tab_layout.addStretch()

        return tab

    def _create_playback_tab(self) -> QWidget:
        """Create playback tab with mixer and transport controls (no export buttons)"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(15)

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

        tab_layout.addWidget(mixer_card, stretch=1)  # Allow mixer to expand

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

        # Control buttons (transport only - export moved to sidebar)
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

        buttons_layout.addWidget(self.btn_play)
        buttons_layout.addWidget(self.btn_pause)
        buttons_layout.addWidget(self.btn_stop)
        buttons_layout.addStretch()
        controls_layout.addLayout(buttons_layout)

        tab_layout.addWidget(controls_card)

        # Info label
        self.info_label = QLabel("Load separated stems to use the mixer and playback.")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        tab_layout.addWidget(self.info_label)

        return tab

    def _create_loop_preview_tab(self) -> QWidget:
        """Create loop preview tab with waveform visualization"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Loop detection card
        detection_card, detection_layout = self._create_card("Loop Detection")

        # Split detection area horizontally:
        # Left: Detect Loops button (vertically centered)
        # Right: 3 status lines (vertically centered)
        detection_split_layout = QHBoxLayout()
        detection_split_layout.setSpacing(20)

        # --- Left side: Detect Loops button, vertically centered ---
        left_layout = QVBoxLayout()
        left_layout.addStretch()

        self.btn_detect_loops = QPushButton("🔍 Detect Loops")
        ThemeManager.set_widget_property(
            self.btn_detect_loops, "buttonStyle", "primary"
        )
        self.btn_detect_loops.setMinimumWidth(140)
        self.btn_detect_loops.setMinimumHeight(36)
        left_layout.addWidget(self.btn_detect_loops, alignment=Qt.AlignLeft)

        left_layout.addStretch()

        detection_split_layout.addLayout(left_layout, stretch=0)

        # --- Right side: 3 status lines, vertically centered ---
        right_layout = QVBoxLayout()
        right_layout.addStretch()

        # Container for 3 status lines
        status_container = QVBoxLayout()
        status_container.setSpacing(4)

        # Status line 1: Current phase/action
        self.loop_status_line1 = QLabel(
            "Click 'Detect Loops' to analyze beat structure"
        )
        self.loop_status_line1.setStyleSheet("color: #aaa; font-size: 10pt;")
        self.loop_status_line1.setWordWrap(True)
        status_container.addWidget(self.loop_status_line1)

        # Status line 2: Progress/timing info
        self.loop_status_line2 = QLabel("")
        self.loop_status_line2.setStyleSheet("color: #888; font-size: 9pt;")
        self.loop_status_line2.setWordWrap(True)
        status_container.addWidget(self.loop_status_line2)

        # Status line 3: Additional details
        self.loop_status_line3 = QLabel("")
        self.loop_status_line3.setStyleSheet("color: #666; font-size: 9pt;")
        self.loop_status_line3.setWordWrap(True)
        status_container.addWidget(self.loop_status_line3)

        right_layout.addLayout(status_container)
        right_layout.addStretch()

        detection_split_layout.addLayout(right_layout, stretch=1)

        detection_layout.addLayout(detection_split_layout)

        # === MANUAL GRID DEFINITION CARD (Combined BPM + Downbeat) ===
        self.manual_grid_card, manual_grid_layout = self._create_card(
            "Manual Grid Definition"
        )
        self.manual_grid_card.setVisible(False)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)

        # Place Downbeat toggle
        self.btn_place_downbeat = QPushButton("Place Downbeat")
        self.btn_place_downbeat.setCheckable(True)
        ThemeManager.set_widget_property(
            self.btn_place_downbeat, "buttonStyle", "secondary"
        )
        self.btn_place_downbeat.setMinimumWidth(130)
        controls_layout.addWidget(self.btn_place_downbeat)

        # Clear button
        self.btn_clear_downbeat = QPushButton("Clear")
        ThemeManager.set_widget_property(
            self.btn_clear_downbeat, "buttonStyle", "secondary"
        )
        self.btn_clear_downbeat.setEnabled(False)
        controls_layout.addWidget(self.btn_clear_downbeat)

        controls_layout.addSpacing(20)

        # BPM spinbox
        bpm_label = QLabel("BPM:")
        bpm_label.setStyleSheet("color: #e0e0e0; font-size: 10pt;")
        controls_layout.addWidget(bpm_label)

        self.manual_grid_bpm_spin = QSpinBox()
        self.manual_grid_bpm_spin.setRange(60, 200)
        self.manual_grid_bpm_spin.setSuffix(" BPM")
        self.manual_grid_bpm_spin.setMinimumWidth(100)
        self.manual_grid_bpm_spin.setEnabled(False)
        controls_layout.addWidget(self.manual_grid_bpm_spin)

        # Apply Grid button
        self.btn_apply_grid = QPushButton("Apply Grid")
        ThemeManager.set_widget_property(self.btn_apply_grid, "buttonStyle", "primary")
        self.btn_apply_grid.setEnabled(False)
        self.btn_apply_grid.setMinimumWidth(120)
        self.btn_apply_grid.setMinimumHeight(32)
        controls_layout.addWidget(self.btn_apply_grid)

        controls_layout.addStretch()
        manual_grid_layout.addLayout(controls_layout)

        # Status label
        self.manual_grid_info_label = QLabel(
            "Click 'Place Downbeat' and then click on waveform"
        )
        self.manual_grid_info_label.setStyleSheet("color: #888; font-size: 9pt;")
        self.manual_grid_info_label.setWordWrap(True)
        manual_grid_layout.addWidget(self.manual_grid_info_label)

        # Add both cards side-by-side in upper box area
        upper_cards_layout = QHBoxLayout()
        upper_cards_layout.setSpacing(15)
        upper_cards_layout.addWidget(detection_card, stretch=1)
        upper_cards_layout.addWidget(self.manual_grid_card, stretch=1)
        layout.addLayout(upper_cards_layout)

        # Initialize state
        self.manual_downbeat_anchor: Optional[Tuple[float, Optional[str]]] = (
            None  # (time, stem_name)
        )
        self.detected_bpm: Optional[float] = None

        # Waveform visualization
        self.loop_waveform_widget = LoopWaveformWidget()
        # Sync default bars per loop (4 bars)
        self.loop_waveform_widget.set_bars_per_loop(4)
        layout.addWidget(self.loop_waveform_widget, stretch=1)

        # Loop playback controls card
        playback_card, playback_layout = self._create_card("Loop Playback")

        # Playback controls
        playback_controls_layout = QHBoxLayout()

        self.btn_play_loop = QPushButton("▶ Play Loop")
        ThemeManager.set_widget_property(self.btn_play_loop, "buttonStyle", "primary")
        self.btn_play_loop.setEnabled(False)  # Disabled until loop selected

        self.btn_play_loop_repeat = QPushButton("🔁 Play Loop (Repeat)")
        ThemeManager.set_widget_property(
            self.btn_play_loop_repeat, "buttonStyle", "secondary"
        )
        self.btn_play_loop_repeat.setEnabled(False)

        self.btn_stop_loop = QPushButton("⏹ Stop")
        ThemeManager.set_widget_property(self.btn_stop_loop, "buttonStyle", "secondary")
        self.btn_stop_loop.setEnabled(False)

        playback_controls_layout.addWidget(self.btn_play_loop)
        playback_controls_layout.addWidget(self.btn_play_loop_repeat)
        playback_controls_layout.addWidget(self.btn_stop_loop)
        playback_controls_layout.addStretch()

        playback_layout.addLayout(playback_controls_layout)

        # Loop info label
        self.loop_playback_info_label = QLabel("Select a loop to play")
        self.loop_playback_info_label.setStyleSheet("color: #888; font-size: 10pt;")
        playback_layout.addWidget(self.loop_playback_info_label)

        # Time-Stretching Controls
        time_stretch_row = QHBoxLayout()
        time_stretch_row.setSpacing(10)

        self.time_stretch_checkbox = QCheckBox("Enable Time Stretching")
        self.time_stretch_checkbox.setChecked(False)
        time_stretch_row.addWidget(self.time_stretch_checkbox)

        time_stretch_row.addWidget(QLabel("Target BPM:"))

        self.target_bpm_spin = QSpinBox()
        self.target_bpm_spin.setMinimum(1)
        self.target_bpm_spin.setMaximum(999)
        self.target_bpm_spin.setValue(120)
        self.target_bpm_spin.setSuffix(" BPM")
        self.target_bpm_spin.setEnabled(False)  # Disabled until checkbox checked
        time_stretch_row.addWidget(self.target_bpm_spin)

        self.btn_start_stretch_processing = QPushButton("Start Processing")
        ThemeManager.set_widget_property(self.btn_start_stretch_processing, "buttonStyle", "primary")
        self.btn_start_stretch_processing.setEnabled(False)
        time_stretch_row.addWidget(self.btn_start_stretch_processing)

        time_stretch_row.addStretch()
        playback_layout.addLayout(time_stretch_row)

        # Progress bar (initially hidden)
        self.stretch_progress_bar = QProgressBar()
        self.stretch_progress_bar.setVisible(False)
        self.stretch_progress_bar.setMinimum(0)
        self.stretch_progress_bar.setMaximum(100)
        self.stretch_progress_bar.setValue(0)
        self.stretch_progress_bar.setTextVisible(True)
        self.stretch_progress_bar.setFormat("Ready")
        playback_layout.addWidget(self.stretch_progress_bar)

        layout.addWidget(playback_card)

        # Connect signals
        self.btn_detect_loops.clicked.connect(self._on_detect_loops_clicked)
        self.loop_waveform_widget.bars_per_loop_changed.connect(
            self._on_bars_per_loop_changed
        )
        self.loop_waveform_widget.loop_selected.connect(self._on_loop_waveform_selected)
        self.loop_waveform_widget.waveform_display.song_start_marker_requested.connect(
            self._on_song_start_marker_requested
        )
        self.btn_play_loop.clicked.connect(self._on_play_loop_clicked)
        self.btn_play_loop_repeat.clicked.connect(self._on_play_loop_repeat_clicked)
        self.btn_stop_loop.clicked.connect(self._on_stop_loop_clicked)

        # Time-stretching signals
        self.time_stretch_checkbox.toggled.connect(self._on_time_stretch_enabled_changed)
        self.target_bpm_spin.valueChanged.connect(self._on_target_bpm_changed)
        self.btn_start_stretch_processing.clicked.connect(self._on_start_stretch_processing_clicked)

        # Manual Grid Definition signals
        self.btn_place_downbeat.toggled.connect(self._on_place_downbeat_toggled)
        self.btn_clear_downbeat.clicked.connect(self._on_clear_downbeat_clicked)
        self.manual_grid_bpm_spin.valueChanged.connect(self._on_manual_grid_bpm_changed)
        self.btn_apply_grid.clicked.connect(self._on_apply_grid_clicked)

        # Waveform manual downbeat signals (simplified - single downbeat only)
        self.loop_waveform_widget.waveform_display.manual_downbeat_placed.connect(
            self._on_single_downbeat_placed
        )
        self.loop_waveform_widget.waveform_display.manual_downbeat_moved.connect(
            self._on_single_downbeat_moved
        )

        return tab

    def _on_page_changed(self, index: int):
        """
        Handle page change events (internal callback).

        PURPOSE: React to page switches (e.g., prepare loop preview)
        CONTEXT: Called when page changes via set_page() from MainWindow sidebar
        """
        page_names = ["Stems", "Playback", "Looping"]
        self.ctx.logger().info(f"Switched to page: {page_names[index]}")

        # Trigger loop analysis when switching to Looping page
        if index == 2:  # Looping page
            self._prepare_loop_preview()

    # === PUBLIC PAGE NAVIGATION (called from MainWindow sidebar) ===

    def set_page(self, index: int) -> None:
        """
        Set the currently visible page.

        PURPOSE: Allow MainWindow sidebar to control which page is shown
        CONTEXT: Called when user clicks Stems/Playback/Looping in sidebar

        Args:
            index: Page index (0=Stems, 1=Playback, 2=Looping)
        """
        if 0 <= index < self._page_stack.count():
            self._page_stack.setCurrentIndex(index)

    def get_current_page(self) -> int:
        """Get the currently visible page index."""
        return self._page_stack.currentIndex()

    def _prepare_loop_preview(self):
        """Prepare loop preview when tab is activated"""
        # Check if we have loops already detected
        if self.detected_loop_segments:
            self.ctx.logger().info("Loop preview already prepared")
            return

        # Check if stems are loaded
        if not self.stem_files:
            self._set_loop_status(
                "⚠ No stems loaded", "Load stems in the Playback tab first.", ""
            )
            return

        # Show hint to user
        self._set_loop_status("Click 'Detect Loops' to analyze beat structure", "", "")

    def _set_loop_status(self, line1: str, line2: str = "", line3: str = ""):
        """
        Update the 3 status lines in the Loop Detection card.

        Args:
            line1: Primary status message (most prominent)
            line2: Secondary info (progress/timing)
            line3: Additional details (less prominent)
        """
        self.loop_status_line1.setText(line1)
        self.loop_status_line2.setText(line2)
        self.loop_status_line3.setText(line3)

    def _reset_loop_detection_state(self):
        """
        Reset all loop detection state variables and UI elements.
        Called when loading new stems or clearing all stems to ensure clean slate.
        """
        # Cancel any running beat analysis worker
        if self._beat_analysis_worker:
            self._beat_analysis_worker.cancel()
            self._beat_analysis_worker = None

        # Stop analysis timer
        if hasattr(self, "_beat_analysis_timer"):
            self._beat_analysis_timer.stop()

        # Delete temporary analysis file
        if hasattr(self, "_beat_analysis_tmp_path") and self._beat_analysis_tmp_path:
            if self._beat_analysis_tmp_path.exists():
                try:
                    self._beat_analysis_tmp_path.unlink(missing_ok=True)
                except Exception as e:
                    self.ctx.logger().warning(f"Could not delete temp file: {e}")
            self._beat_analysis_tmp_path = None

        # Clear cached audio data
        self._beat_analysis_mixed_audio = None
        self._beat_analysis_sample_rate = 0
        self._beat_analysis_start_time = 0.0
        self._beat_analysis_phase = ""
        self._beat_analysis_detail = ""

        # Reset loop detection results
        self.detected_beat_times = None
        self.detected_downbeat_times = None
        self.detected_loop_segments = []
        self.detected_intro_loops = []
        self.selected_loop_index = -1

        # Reset song start marker
        self.song_start_downbeat_index = None

        # Clear waveform widget visualization
        if hasattr(self, "loop_waveform_widget"):
            self.loop_waveform_widget.clear()

        # Reset loop playback buttons
        if hasattr(self, "btn_play_loop"):
            self.btn_play_loop.setEnabled(False)
        if hasattr(self, "btn_play_loop_repeat"):
            self.btn_play_loop_repeat.setEnabled(False)
        if hasattr(self, "btn_stop_loop"):
            self.btn_stop_loop.setEnabled(False)

        # Re-enable detect loops button
        if hasattr(self, "btn_detect_loops"):
            self.btn_detect_loops.setEnabled(True)

        # Reset status labels
        if hasattr(self, "loop_status_line1"):
            self._set_loop_status(
                "Click 'Detect Loops' to analyze beat structure", "", ""
            )

        # Reset manual grid UI
        if hasattr(self, "manual_grid_card"):
            self.manual_grid_card.setVisible(False)
            self.detected_bpm = None
            self.manual_grid_bpm_spin.setEnabled(False)
            self.manual_grid_bpm_spin.setValue(120)
            self.btn_place_downbeat.setChecked(False)
            self.btn_clear_downbeat.setEnabled(False)
            self.btn_apply_grid.setEnabled(False)
            self.manual_grid_info_label.setText("")
            self.manual_downbeat_anchor = None

            if hasattr(self.loop_waveform_widget, "waveform_display"):
                self.loop_waveform_widget.waveform_display.clear_manual_downbeats()
                self.loop_waveform_widget.waveform_display.set_manual_placement_mode(
                    False
                )

        self.ctx.logger().debug("Loop detection state reset")

    def _on_detect_loops_clicked(self):
        """Handle 'Detect Loops' button click - starts async beat analysis"""
        if not self.stem_files:
            QMessageBox.warning(
                self,
                "No Stems Loaded",
                "Please load stems in the Playback tab before detecting loops.",
            )
            return

        # Cancel any existing analysis
        if self._beat_analysis_worker:
            self._beat_analysis_worker.cancel()
            self._beat_analysis_worker = None

        try:
            # New detection run: Initial Status
            self._set_loop_status(
                "🔍 Preparing audio for analysis...", "Mixing stems...", ""
            )
            self.btn_detect_loops.setEnabled(False)
            self.ctx.logger().info("Starting loop detection...")

            # Step 1: Mix all stems to create master track for beat detection (BeatNet needs full mix)
            self.ctx.logger().info("Mixing stems for beat detection...")
            mixed_audio, sample_rate = self._mix_stems_to_array()

            # Step 2: Save to temporary file
            import tempfile

            tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            self._beat_analysis_tmp_path = Path(tmp_file.name)
            tmp_file.close()

            sf.write(str(self._beat_analysis_tmp_path), mixed_audio, sample_rate)

            # Store for later use in callback
            self._beat_analysis_mixed_audio = mixed_audio
            self._beat_analysis_sample_rate = sample_rate

            # Step 3: Find drums stem for BPM detection (more accurate than mixed)
            drums_path = self._find_drums_stem_path()
            if drums_path:
                self.ctx.logger().info(
                    f"Using drums stem for BPM detection: {drums_path.name}"
                )
            else:
                self.ctx.logger().info(
                    "No drums stem found, using mixed audio for BPM detection"
                )

            # Step 4: Calculate timeout and start countdown timer
            # Increased timeout for M1 and less performant Macs
            import time

            audio_duration = len(mixed_audio) / sample_rate
            self._beat_analysis_timeout = max(120.0, 60.0 + audio_duration * 1.0)
            self._beat_analysis_start_time = time.time()
            self._beat_analysis_phase = "Starting"
            self._beat_analysis_detail = "Initializing..."
            self._beat_analysis_timer.start()

            # Step 5: Start async beat analysis
            self._beat_analysis_worker = BeatAnalysisWorker(
                self._beat_analysis_tmp_path,
                self.ctx.logger(),
                bpm_audio_path=drums_path,  # Pass drums for better BPM accuracy
            )
            self._beat_analysis_worker.signals.finished.connect(
                self._on_beat_analysis_finished
            )
            self._beat_analysis_worker.signals.error.connect(
                self._on_beat_analysis_error
            )
            self._beat_analysis_worker.signals.progress.connect(
                self._on_beat_analysis_progress
            )

            self._thread_pool.start(self._beat_analysis_worker)

        except Exception as e:
            error_msg = str(e)
            self._set_loop_status("❌ Loop detection failed", error_msg, "")
            self.ctx.logger().error(f"Loop detection failed: {e}", exc_info=True)
            self.btn_detect_loops.setEnabled(True)

    def _on_beat_analysis_progress(self, phase: str, detail: str):
        """Update status label with progress message (stores for countdown display)."""
        self._beat_analysis_phase = phase
        self._beat_analysis_detail = detail
        # Trigger immediate countdown update
        self._update_beat_analysis_countdown()

    def _update_beat_analysis_countdown(self):
        """Update countdown timer display."""
        import time

        # Map phases to emoji icons
        phase_icons = {
            "Starting": "🔄",
            "Initializing": "📊",
            "BeatNet": "🥁",
            "DeepRhythm": "🎵",
            "Complete": "✅",
        }

        elapsed = time.time() - self._beat_analysis_start_time
        remaining = max(0, self._beat_analysis_timeout - elapsed)

        icon = phase_icons.get(self._beat_analysis_phase, "🔍")

        # Format countdown
        mins, secs = divmod(int(remaining), 60)
        if mins > 0:
            countdown_str = f"{mins}m {secs}s"
        else:
            countdown_str = f"{secs}s"

        # Format elapsed
        elapsed_mins, elapsed_secs = divmod(int(elapsed), 60)
        if elapsed_mins > 0:
            elapsed_str = f"{elapsed_mins}m {elapsed_secs}s"
        else:
            elapsed_str = f"{elapsed_secs}s"

        # Update 3 status lines with phase, detail, and timing
        self._set_loop_status(
            f"{icon} [{self._beat_analysis_phase}] {self._beat_analysis_detail}",
            f"Elapsed: {elapsed_str}",
            f"Timeout in: {countdown_str}",
        )

    def _on_beat_analysis_finished(
        self, beat_times, downbeat_times, first_downbeat, conf_msg
    ):
        """Handle successful beat analysis completion."""
        # Stop countdown timer
        self._beat_analysis_timer.stop()

        try:
            # Clean up temp file
            if (
                hasattr(self, "_beat_analysis_tmp_path")
                and self._beat_analysis_tmp_path.exists()
            ):
                self._beat_analysis_tmp_path.unlink(missing_ok=True)

            self.detected_beat_times = beat_times
            self.detected_downbeat_times = downbeat_times

            # Check for fallback mode (no true downbeats)
            is_fallback = conf_msg.startswith("Fallback:")
            if is_fallback:
                QMessageBox.warning(
                    self,
                    "Eingeschränkte Beat-Erkennung",
                    "BeatNet ist nicht verfügbar. Die Loop-Erkennung basiert nur auf BPM.\n\n"
                    "Downbeat-genaue Loops sind möglicherweise nicht exakt.",
                )

            # Get bars per loop setting
            bars_per_loop = self._bars_per_loop

            # Calculate loop segments
            duration = self.player.get_duration()
            loops, intro_loops = beat_detection.calculate_loops_from_downbeats(
                downbeat_times,
                bars_per_loop,
                duration,
                song_start_downbeat_index=getattr(
                    self, "song_start_downbeat_index", None
                ),
                intro_handling=getattr(self, "intro_handling", "pad"),
            )
            self.detected_loop_segments = loops
            self.detected_intro_loops = intro_loops

            # Load waveforms into widget
            self._set_loop_status(
                "🎨 Rendering waveforms...", "Loading stem data...", ""
            )

            # Get player's actual sample rate and duration for accurate beat alignment
            # WHY: Player may have resampled audio, so we must use player's rate and duration
            player_sample_rate = self.player.sample_rate
            player_duration = self.player.get_duration()

            # Re-mix stems using player's sample rate to ensure consistency
            # WHY: Original mix may have used file's native rate, but player uses different rate
            mixed_audio, sample_rate = self._mix_stems_to_array()

            # Store for potential reuse
            self._beat_analysis_mixed_audio = mixed_audio
            self._beat_analysis_sample_rate = sample_rate

            # Combined mode: use mixed audio with player's sample rate
            self.loop_waveform_widget.set_combined_waveform(
                mixed_audio, sample_rate, duration=player_duration
            )

            # Stacked mode: load individual stems
            # WHY: Resample to player's sample rate for consistency
            player_sample_rate = self.player.sample_rate
            stem_waveforms = {}
            for stem_name, stem_path in self.stem_files.items():
                audio_data, file_sr = sf.read(stem_path, dtype="float32")

                # Resample to player's sample rate if needed
                # WHY: Ensures waveform uses same sample rate as playback
                if file_sr != player_sample_rate:
                    import librosa

                    audio_data = librosa.resample(
                        audio_data,
                        orig_sr=file_sr,
                        target_sr=player_sample_rate,
                        res_type="kaiser_best",
                    )
                    self.ctx.logger().debug(
                        f"Resampled {stem_name} for stacked waveform: {file_sr} Hz -> {player_sample_rate} Hz"
                    )

                stem_waveforms[stem_name] = audio_data

            self.loop_waveform_widget.set_stem_waveforms(
                stem_waveforms, player_sample_rate, duration=player_duration
            )

            # Set beat times and loop segments
            self.loop_waveform_widget.set_beat_times(beat_times, downbeat_times)
            self.loop_waveform_widget.set_loop_segments(self.detected_loop_segments)

            # Success message (3 status lines)
            num_loops = len(self.detected_loop_segments)
            status_icon = "⚠" if is_fallback else "✓"
            self._set_loop_status(
                f"{status_icon} Detection complete",
                f"{num_loops} loops ({bars_per_loop} bars each)",
                f"{len(downbeat_times)} downbeats, {len(beat_times)} beats",
            )

            # Calculate BPM from downbeat intervals for consistent display
            # WHY: Use same BPM calculation as export to avoid confusion
            calculated_bpm = None
            if len(downbeat_times) >= 2:
                downbeat_intervals = np.diff(downbeat_times)
                median_bar_duration = float(np.median(downbeat_intervals))
                if median_bar_duration > 0:
                    # 4 beats per bar in 4/4 time
                    calculated_bpm = (60.0 * 4) / median_bar_duration

            # Extract confidence from conf_msg
            confidence_str = ""
            if "DeepRhythm" in conf_msg:
                import re

                match = re.search(r"DeepRhythm\s*\((\d+)%\)", conf_msg)
                if match:
                    confidence_str = f" ({match.group(1)}%)"

            # Format BPM for display (one decimal place for accuracy)
            # WHY: Shows exact BPM used for beat calculation, ensuring consistency
            if calculated_bpm:
                bpm_prefix = f"{calculated_bpm:.1f} BPM{confidence_str}"
            else:
                # Fallback: extract from conf_msg
                bpm_prefix = self._extract_bpm_summary(conf_msg)
                if bpm_prefix is None:
                    bpm_prefix = ""

            # Update header info above waveform: "BPM (conf) • X loops detected • Y bars total"
            self.loop_waveform_widget.set_summary_prefix(bpm_prefix)

            # Enable time-stretch start button if time-stretching is enabled
            if self.time_stretch_enabled:
                self.btn_start_stretch_processing.setEnabled(
                    len(self.detected_loop_segments) > 0 and len(self.stem_files) > 0
                )

            # Initialize correction UIs after successful detection
            if calculated_bpm:
                detected_bpm_value = calculated_bpm
            else:
                import re

                bpm_match = re.search(r"(\d+\.?\d*)\s*BPM", conf_msg)
                detected_bpm_value = float(bpm_match.group(1)) if bpm_match else 120.0

            self.detected_bpm = detected_bpm_value

            # Show manual grid definition card
            self.manual_grid_card.setVisible(True)
            self.manual_grid_bpm_spin.setValue(int(detected_bpm_value))
            self.manual_grid_bpm_spin.setEnabled(True)
            self.btn_place_downbeat.setChecked(False)
            self.btn_clear_downbeat.setEnabled(False)
            self.btn_apply_grid.setEnabled(False)
            self.manual_grid_info_label.setText(
                "Click 'Place Downbeat' to define custom grid anchor"
            )
            self.manual_grid_info_label.setStyleSheet("color: #888; font-size: 9pt;")

            # Detect transients per stem for stem-specific snapping
            try:
                stem_waveforms = {}
                for stem_name, stem_path in self.stem_files.items():
                    audio_data_stem, sr = sf.read(stem_path, dtype="float32")
                    if audio_data_stem.ndim == 2:
                        audio_data_stem = np.mean(audio_data_stem, axis=1)
                    stem_waveforms[stem_name] = audio_data_stem

                # Also include mixed audio for fallback
                stem_waveforms["mixed"] = mixed_audio

                transient_dict = beat_detection.detect_transients_per_stem(
                    stem_waveforms=stem_waveforms,
                    sample_rate=sample_rate,
                    threshold=0.3,
                    min_distance=0.1,
                )

                self.loop_waveform_widget.waveform_display.set_transient_times_per_stem(
                    transient_dict
                )

                total = sum(len(t) for t in transient_dict.values())
                self.ctx.logger().info(
                    f"Transients: {len(transient_dict)} stems, {total} total"
                )

            except Exception as e:
                self.ctx.logger().warning(f"Per-stem transient detection failed: {e}")

            # Reset manual downbeat state
            self.manual_downbeat_anchor = None
            self.loop_waveform_widget.waveform_display.clear_manual_downbeats()

            self.ctx.logger().info(
                f"Loop detection complete: {num_loops} loops detected"
            )

        except Exception as e:
            self._on_beat_analysis_error(str(e))

        finally:
            self.btn_detect_loops.setEnabled(True)
            self._beat_analysis_worker = None

    def _on_beat_analysis_error(self, error_msg: str):
        """Handle beat analysis error."""
        # Stop countdown timer
        self._beat_analysis_timer.stop()

        # Clean up temp file
        if (
            hasattr(self, "_beat_analysis_tmp_path")
            and self._beat_analysis_tmp_path.exists()
        ):
            self._beat_analysis_tmp_path.unlink(missing_ok=True)

        self._set_loop_status(
            "❌ Loop detection failed", error_msg, "Check the log for details."
        )
        self.ctx.logger().error(f"Loop detection failed: {error_msg}")

        QMessageBox.critical(
            self,
            "Loop Detection Failed",
            f"Failed to detect loops:\n\n{error_msg}\n\n" "Check the log for details.",
        )

        self.btn_detect_loops.setEnabled(True)
        self._beat_analysis_worker = None

    def _on_bars_per_loop_changed(self, bars_per_loop: int):
        """Handle bars per loop setting change - re-calculate loops if already detected"""
        self._bars_per_loop = bars_per_loop

        if (
            not self.detected_downbeat_times is None
            and len(self.detected_downbeat_times) > 0
        ):
            # Re-calculate loops with new bar count
            duration = self.player.get_duration()

            loops, intro_loops = beat_detection.calculate_loops_from_downbeats(
                self.detected_downbeat_times,
                bars_per_loop,
                duration,
                song_start_downbeat_index=getattr(
                    self, "song_start_downbeat_index", None
                ),
                intro_handling=getattr(self, "intro_handling", "pad"),
            )
            self.detected_loop_segments = loops
            self.detected_intro_loops = intro_loops

            # Update widget
            if intro_loops:
                # Add leading loops to display if present
                all_segments = intro_loops + self.detected_loop_segments
                self.loop_waveform_widget.set_loop_segments(all_segments)
            else:
                self.loop_waveform_widget.set_loop_segments(self.detected_loop_segments)

            num_loops = len(self.detected_loop_segments)
            self._set_loop_status(
                f"✓ Recalculated", f"{num_loops} loops ({bars_per_loop} bars each)", ""
            )
            self.ctx.logger().info(
                f"Recalculated loops: {num_loops} loops, {bars_per_loop} bars each"
            )

    # === MANUAL GRID DEFINITION EVENT HANDLERS ===

    def _on_place_downbeat_toggled(self, checked: bool):
        """Toggle manual downbeat placement mode."""
        self.loop_waveform_widget.waveform_display.set_manual_placement_mode(checked)

        if checked:
            self.btn_place_downbeat.setText("Cancel Placement")
            if self.manual_downbeat_anchor is not None:
                self.manual_grid_info_label.setText(
                    "✓ Placement active - Click to reposition downbeat"
                )
            else:
                self.manual_grid_info_label.setText(
                    "✓ Placement active - Click on stem waveform to place downbeat anchor"
                )
            self.manual_grid_info_label.setStyleSheet("color: #10b981; font-size: 9pt;")
        else:
            self.btn_place_downbeat.setText("Place Downbeat")
            if self.manual_downbeat_anchor is not None:
                time, stem = self.manual_downbeat_anchor
                stem_info = f" ({stem})" if stem else ""
                self.manual_grid_info_label.setText(
                    f"Downbeat at {time:.2f}s{stem_info} - Adjust BPM and click Apply"
                )
            else:
                self.manual_grid_info_label.setText(
                    "Click 'Place Downbeat' to position anchor point"
                )
            self.manual_grid_info_label.setStyleSheet("color: #888; font-size: 9pt;")

    def _on_clear_downbeat_clicked(self):
        """Clear the single manual downbeat."""
        self.loop_waveform_widget.waveform_display.clear_manual_downbeats()
        self.manual_downbeat_anchor = None
        self._update_manual_grid_ui()
        self.manual_grid_info_label.setText("Downbeat cleared")

    def _on_manual_grid_bpm_changed(self, value: int):
        """Handle BPM spinbox value change."""
        has_downbeat = self.manual_downbeat_anchor is not None
        bpm_changed = bool(self.detected_bpm and abs(value - self.detected_bpm) > 0.5)
        # Enable Apply Grid if EITHER downbeat is placed OR BPM is changed
        self.btn_apply_grid.setEnabled(has_downbeat or bpm_changed)
        self._update_manual_grid_ui()

    def _on_single_downbeat_placed(self, time: float, stem_name: str):
        """Handle single downbeat placement from waveform."""
        stem = stem_name if stem_name else None
        self.manual_downbeat_anchor = (time, stem)
        self._update_manual_grid_ui()
        self.ctx.logger().info(f"Manual downbeat anchor placed at {time:.2f}s")

    def _on_single_downbeat_moved(self, index: int, new_time: float):
        """Handle downbeat repositioning."""
        if self.manual_downbeat_anchor is not None:
            _, stem = self.manual_downbeat_anchor
            self.manual_downbeat_anchor = (new_time, stem)
            self._update_manual_grid_ui()

    def _update_manual_grid_ui(self):
        """Update UI state based on current downbeat and BPM."""
        has_downbeat = self.manual_downbeat_anchor is not None
        bpm_changed = (
            self.detected_bpm
            and abs(self.manual_grid_bpm_spin.value() - self.detected_bpm) > 0.5
        )

        self.btn_clear_downbeat.setEnabled(has_downbeat)
        # Enable Apply Grid if EITHER downbeat is placed OR BPM is changed
        bpm_changed_bool = bool(self.detected_bpm and abs(self.manual_grid_bpm_spin.value() - self.detected_bpm) > 0.5)
        self.btn_apply_grid.setEnabled(has_downbeat or bpm_changed_bool)

        # Update message based on current state
        if has_downbeat and bpm_changed:
            # Both downbeat and BPM changed
            time, stem = self.manual_downbeat_anchor
            stem_info = f" ({stem})" if stem else ""
            bpm_diff = self.manual_grid_bpm_spin.value() - self.detected_bpm
            self.manual_grid_info_label.setText(
                f"Downbeat at {time:.2f}s{stem_info} + BPM {bpm_diff:+.0f} - Click Apply"
            )
            self.manual_grid_info_label.setStyleSheet("color: #f59e0b; font-size: 9pt;")
        elif has_downbeat:
            # Only downbeat placed (no BPM change)
            time, stem = self.manual_downbeat_anchor
            stem_info = f" ({stem})" if stem else ""
            self.manual_grid_info_label.setText(
                f"Downbeat at {time:.2f}s{stem_info} - Click Apply to realign grid"
            )
            self.manual_grid_info_label.setStyleSheet("color: #10b981; font-size: 9pt;")
        elif bpm_changed:
            # Only BPM changed (no downbeat)
            bpm_diff = self.manual_grid_bpm_spin.value() - self.detected_bpm
            self.manual_grid_info_label.setText(
                f"BPM {bpm_diff:+.0f} from detected - Click Apply to adjust grid"
            )
            self.manual_grid_info_label.setStyleSheet("color: #f59e0b; font-size: 9pt;")
        else:
            # No changes
            self.manual_grid_info_label.setText(
                "Place downbeat or adjust BPM to modify grid"
            )
            self.manual_grid_info_label.setStyleSheet("color: #888; font-size: 9pt;")

    def _on_apply_grid_clicked(self):
        """Apply manual downbeat and/or BPM change and recalculate beat grid."""
        try:
            has_downbeat = self.manual_downbeat_anchor is not None
            has_bpm_change = (
                self.detected_bpm
                and abs(self.manual_grid_bpm_spin.value() - self.detected_bpm) > 0.5
            )

            if not has_downbeat and not has_bpm_change:
                QMessageBox.warning(
                    self, "No Changes", "Please place a downbeat or adjust BPM first."
                )
                return

            # Determine anchor and BPM based on what changed
            if has_downbeat:
                downbeat_time, downbeat_stem = self.manual_downbeat_anchor
                anchor_time = downbeat_time
                stem_info = f" ({downbeat_stem})" if downbeat_stem else ""
            else:
                # No manual downbeat, use first auto-detected downbeat
                anchor_time = self.detected_downbeat_times[0]
                downbeat_stem = None
                stem_info = ""

            if has_bpm_change:
                new_bpm = float(self.manual_grid_bpm_spin.value())
            else:
                # No BPM change, use detected BPM
                new_bpm = self.detected_bpm

            # Set status message based on what's being applied
            # WHY: Use .1f for consistency with all BPM displays
            if has_downbeat and has_bpm_change:
                status_msg = f"Applying manual anchor + {new_bpm:.1f} BPM"
            elif has_downbeat:
                status_msg = f"Realigning grid to manual anchor"
            else:
                status_msg = f"Adjusting grid to {new_bpm:.1f} BPM"

            self._set_loop_status("🔄 Recalculating beat grid...", status_msg, "")
            self.btn_apply_grid.setEnabled(False)

            duration = self.player.get_duration()

            # Recalculate grid using existing function
            new_beat_times, new_downbeat_times, first_downbeat = (
                beat_detection.recalculate_beat_grid_from_bpm(
                    current_beat_times=self.detected_beat_times,
                    current_downbeat_times=self.detected_downbeat_times,
                    new_bpm=new_bpm,
                    audio_duration=duration,
                    first_downbeat_anchor=anchor_time,
                )
            )

            # Store new grid
            self.detected_beat_times = new_beat_times
            self.detected_downbeat_times = new_downbeat_times
            self.detected_bpm = new_bpm

            # Recalculate loops
            bars_per_loop = self._bars_per_loop
            loops, intro_loops = beat_detection.calculate_loops_from_downbeats(
                new_downbeat_times,
                bars_per_loop,
                duration,
                song_start_downbeat_index=getattr(
                    self, "song_start_downbeat_index", None
                ),
                intro_handling=getattr(self, "intro_handling", "pad"),
            )
            self.detected_loop_segments = loops
            self.detected_intro_loops = intro_loops

            # Update waveform
            self.loop_waveform_widget.set_beat_times(new_beat_times, new_downbeat_times)

            if intro_loops:
                all_segments = intro_loops + self.detected_loop_segments
                self.loop_waveform_widget.set_loop_segments(all_segments)
            else:
                self.loop_waveform_widget.set_loop_segments(self.detected_loop_segments)

            # Update display with appropriate label (one decimal place for accuracy)
            # WHY: Shows exact BPM used for beat calculation, ensuring consistency
            if has_downbeat and has_bpm_change:
                bpm_prefix = f"{new_bpm:.1f} BPM (manual{stem_info})"
            elif has_downbeat:
                bpm_prefix = f"{new_bpm:.1f} BPM (realigned{stem_info})"
            else:
                bpm_prefix = f"{new_bpm:.1f} BPM (adjusted)"
            self.loop_waveform_widget.set_summary_prefix(bpm_prefix)

            # Success status
            num_loops = len(self.detected_loop_segments)

            # Set appropriate success message based on what was applied
            if has_downbeat and has_bpm_change:
                status_title = "✓ Manual grid applied"
                status_detail = f"Anchor: {anchor_time:.2f}s{stem_info}"
                info_msg = f"✓ Applied - Grid anchored at {anchor_time:.2f}s{stem_info}"
                log_msg = f"Manual grid: {new_bpm:.1f} BPM, anchor {anchor_time:.2f}s, {num_loops} loops"
            elif has_downbeat:
                status_title = "✓ Grid realigned"
                status_detail = f"Anchor: {anchor_time:.2f}s{stem_info}"
                info_msg = (
                    f"✓ Applied - Grid realigned to {anchor_time:.2f}s{stem_info}"
                )
                log_msg = (
                    f"Grid realigned: anchor {anchor_time:.2f}s, {num_loops} loops"
                )
            else:
                status_title = "✓ BPM adjusted"
                status_detail = f"Using auto-detected anchor"
                info_msg = f"✓ Applied - BPM adjusted to {new_bpm:.1f}"
                log_msg = f"BPM adjusted: {new_bpm:.1f} BPM, {num_loops} loops"

            self._set_loop_status(
                status_title,
                f"{num_loops} loops ({bars_per_loop} bars) at {new_bpm:.1f} BPM",
                status_detail,
            )

            self.manual_grid_info_label.setText(info_msg)
            self.manual_grid_info_label.setStyleSheet("color: #10b981; font-size: 9pt;")

            self.ctx.logger().info(log_msg)

        except Exception as e:
            self.ctx.logger().error(f"Manual grid failed: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Manual Grid Error", f"Failed to apply manual grid:\n\n{str(e)}"
            )
            self._set_loop_status("❌ Manual grid failed", str(e), "")
            self.btn_apply_grid.setEnabled(True)

    def set_song_start_marker(self, downbeat_index: int):
        """
        Set song start marker at specified downbeat index.

        WHY: Allows marking a specific downbeat as the "true" song start for loop calculation.
        EXAMPLE: Song has 2-bar intro, set marker at downbeat index 2 to start 4-bar loops from there.

        Args:
            downbeat_index: Index in self.detected_downbeat_times array
        """
        if (
            self.detected_downbeat_times is None
            or len(self.detected_downbeat_times) == 0
        ):
            self.ctx.logger().warning(
                "Cannot set song start marker: No downbeats detected"
            )
            return

        if downbeat_index < 0 or downbeat_index >= len(self.detected_downbeat_times):
            self.ctx.logger().warning(
                f"Invalid downbeat_index {downbeat_index}, "
                f"must be 0-{len(self.detected_downbeat_times)-1}"
            )
            return

        self.song_start_downbeat_index = downbeat_index
        self.ctx.logger().info(
            f"Song start marker set at downbeat {downbeat_index} "
            f"({self.detected_downbeat_times[downbeat_index]:.2f}s)"
        )

        # Re-calculate loops with new song start marker
        self._recalculate_loops_with_current_settings()

        # Update waveform widget to show marker
        if hasattr(self.loop_waveform_widget, "set_song_start_marker"):
            self.loop_waveform_widget.set_song_start_marker(downbeat_index)

    def clear_song_start_marker(self):
        """Clear song start marker and recalculate loops from beginning."""
        if self.song_start_downbeat_index is None:
            return

        self.ctx.logger().info("Clearing song start marker")
        self.song_start_downbeat_index = None
        self.detected_intro_loops = []

        # Re-calculate loops from beginning
        self._recalculate_loops_with_current_settings()

        # Update waveform widget
        if hasattr(self.loop_waveform_widget, "clear_song_start_marker"):
            self.loop_waveform_widget.clear_song_start_marker()

    def set_intro_handling(self, handling: str):
        """
        Set how to handle intro before song start marker.

        Args:
            handling: "pad" (create padded intro loop) or "skip" (skip intro)
        """
        if handling not in ("pad", "skip"):
            self.ctx.logger().warning(
                f"Invalid intro_handling: {handling}, must be 'pad' or 'skip'"
            )
            return

        self.intro_handling = handling
        self.ctx.logger().info(f"Intro handling set to: {handling}")

        # Re-calculate loops if song start marker is set
        if self.song_start_downbeat_index is not None:
            self._recalculate_loops_with_current_settings()

    def _recalculate_loops_with_current_settings(self):
        """Recalculate loops with current bars_per_loop and song_start_marker settings."""
        if (
            self.detected_downbeat_times is None
            or len(self.detected_downbeat_times) == 0
        ):
            return

        duration = self.player.get_duration()
        loops, intro_loops = beat_detection.calculate_loops_from_downbeats(
            self.detected_downbeat_times,
            self._bars_per_loop,
            duration,
            song_start_downbeat_index=self.song_start_downbeat_index,
            intro_handling=self.intro_handling,
        )
        self.detected_loop_segments = loops
        self.detected_intro_loops = intro_loops

        # Update widget
        if intro_loops:
            # Show leading loops + main loops
            all_segments = intro_loops + self.detected_loop_segments
            self.loop_waveform_widget.set_loop_segments(all_segments)
        else:
            self.loop_waveform_widget.set_loop_segments(self.detected_loop_segments)

        # Enable time-stretch start button if time-stretching is enabled
        if self.time_stretch_enabled:
            self.btn_start_stretch_processing.setEnabled(
                len(self.detected_loop_segments) > 0 and len(self.stem_files) > 0
            )

        # Update status
        if self.song_start_downbeat_index is not None:
            if intro_loops:
                # Calculate total intro duration and padding info
                first_loop = intro_loops[0]
                last_loop = intro_loops[-1]

                # Check if first intro loop has padding (negative start time)
                if first_loop[0] < 0:
                    padding_duration = abs(first_loop[0])
                    actual_intro_duration = last_loop[1]
                    total_duration = padding_duration + actual_intro_duration
                    intro_info = (
                        f"{len(intro_loops)} leading loops: {total_duration:.1f}s "
                        f"({padding_duration:.1f}s silence + {actual_intro_duration:.1f}s audio), "
                    )
                else:
                    intro_info = (
                        f"{len(intro_loops)} leading loops: {last_loop[1]:.1f}s, "
                    )
            else:
                intro_info = "intro skipped, "
            status_msg = f"✓ Loops from marker (bar {self.song_start_downbeat_index})"
        else:
            intro_info = ""
            status_msg = "✓ Loops calculated"

        num_loops = len(self.detected_loop_segments)
        self._set_loop_status(
            status_msg,
            f"{intro_info}{num_loops} loops ({self._bars_per_loop} bars each)",
            "",
        )

    def _on_song_start_marker_requested(self, downbeat_index: int):
        """Handle song start marker request from waveform widget."""
        if downbeat_index < 0:
            # Clear marker
            self.clear_song_start_marker()
        else:
            # Set marker
            self.set_song_start_marker(downbeat_index)

    def _get_all_loop_segments(self) -> List[Tuple[float, float]]:
        """
        Get combined list of all loop segments (intro + main).

        WHY: Waveform displays all loops, so selection index must match combined list.

        Returns:
            Combined list: [intro_loop1, intro_loop2, ..., main_loop1, main_loop2, ...]
        """
        return self.detected_intro_loops + self.detected_loop_segments

    def _on_loop_waveform_selected(self, loop_index: int):
        """Handle loop selection from waveform widget"""
        self.selected_loop_index = loop_index

        # Get combined list of all loops (intro + main)
        all_loops = self._get_all_loop_segments()

        if 0 <= loop_index < len(all_loops):
            start_time, end_time = all_loops[loop_index]
            duration = end_time - start_time

            # Determine if this is a leading loop or main loop
            is_leading_loop = loop_index < len(self.detected_intro_loops)
            loop_type = "Leading Loop" if is_leading_loop else "Main Loop"
            relative_index = (
                loop_index + 1
                if is_leading_loop
                else (loop_index - len(self.detected_intro_loops) + 1)
            )

            self.loop_playback_info_label.setText(
                f"{loop_type} {relative_index} selected: {start_time:.2f}s - {end_time:.2f}s "
                f"(duration: {duration:.2f}s)"
            )

            # Enable playback buttons
            self.btn_play_loop.setEnabled(True)
            self.btn_play_loop_repeat.setEnabled(True)

            self.ctx.logger().info(
                f"{loop_type} {relative_index} selected: {start_time:.2f}s - {end_time:.2f}s"
            )

    def _on_play_loop_clicked(self):
        """Handle 'Play Loop' button click (play once)"""
        all_loops = self._get_all_loop_segments()

        if self.selected_loop_index < 0 or self.selected_loop_index >= len(all_loops):
            QMessageBox.warning(self, "No Loop Selected", "Please select a loop first.")
            return

        start_time, end_time = all_loops[self.selected_loop_index]

        # Determine loop type for display
        is_leading_loop = self.selected_loop_index < len(self.detected_intro_loops)
        loop_type = "Leading Loop" if is_leading_loop else "Main Loop"
        relative_index = (
            self.selected_loop_index + 1
            if is_leading_loop
            else (self.selected_loop_index - len(self.detected_intro_loops) + 1)
        )

        # Stop position timer for Playback tab (loop playback shouldn't update it)
        self.position_timer.stop()

        # Check if time-stretching is enabled and processing is complete
        if self.time_stretch_enabled and self.stretch_manager:
            # Play stretched version
            self._play_stretched_loop_segment(self.selected_loop_index, repeat=False)
            return

        # Play loop segment once (no repeat) - normal playback
        success = self.player.play_loop_segment(start_time, end_time, repeat=False)

        if success:
            self.btn_stop_loop.setEnabled(True)
            self.loop_playback_info_label.setText(
                f"Playing {loop_type} {relative_index} (once): "
                f"{start_time:.2f}s - {end_time:.2f}s"
            )
            self.ctx.logger().info(f"Playing {loop_type.lower()} {relative_index} once")
        else:
            QMessageBox.warning(
                self,
                "Playback Failed",
                "Failed to start loop playback. Check that sounddevice is installed.",
            )

    def _on_play_loop_repeat_clicked(self):
        """Handle 'Play Loop (Repeat)' button click"""
        all_loops = self._get_all_loop_segments()

        if self.selected_loop_index < 0 or self.selected_loop_index >= len(all_loops):
            QMessageBox.warning(self, "No Loop Selected", "Please select a loop first.")
            return

        start_time, end_time = all_loops[self.selected_loop_index]

        # Determine loop type for display
        is_leading_loop = self.selected_loop_index < len(self.detected_intro_loops)
        loop_type = "Leading Loop" if is_leading_loop else "Main Loop"
        relative_index = (
            self.selected_loop_index + 1
            if is_leading_loop
            else (self.selected_loop_index - len(self.detected_intro_loops) + 1)
        )

        # Stop position timer for Playback tab (loop playback shouldn't update it)
        self.position_timer.stop()

        # Check if time-stretching is enabled and processing is complete
        if self.time_stretch_enabled and self.stretch_manager:
            # Play stretched version
            self._play_stretched_loop_segment(self.selected_loop_index, repeat=True)
            return

        # Play loop segment with repeat - normal playback
        success = self.player.play_loop_segment(start_time, end_time, repeat=True)

        if success:
            self.btn_stop_loop.setEnabled(True)
            self.loop_playback_info_label.setText(
                f"Playing {loop_type} {relative_index} (repeating): "
                f"{start_time:.2f}s - {end_time:.2f}s"
            )
            self.ctx.logger().info(
                f"Playing {loop_type.lower()} {relative_index} with repeat"
            )
        else:
            QMessageBox.warning(
                self,
                "Playback Failed",
                "Failed to start loop playback. Check that sounddevice is installed.",
            )

    def _on_stop_loop_clicked(self):
        """Handle 'Stop' button click for loop playback"""
        # Stop normal playback
        self.player.stop()
        
        # Stop stretched playback if active
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass  # sounddevice might not be available
        
        self.btn_stop_loop.setEnabled(False)

        if self.selected_loop_index >= 0:
            self.loop_playback_info_label.setText(
                f"Loop {self.selected_loop_index + 1} playback stopped"
            )
        else:
            self.loop_playback_info_label.setText("Playback stopped")

        self.ctx.logger().info("Loop playback stopped")

    @Slot(bool)
    def _on_time_stretch_enabled_changed(self, enabled: bool):
        """Handle time-stretching checkbox toggle."""
        self.time_stretch_enabled = enabled
        self.target_bpm_spin.setEnabled(enabled)
        self.btn_start_stretch_processing.setEnabled(
            enabled and len(self.detected_loop_segments) > 0 and len(self.stem_files) > 0
        )
        
        if not enabled:
            # Cancel processing and clear manager if disabled
            if self.stretch_manager:
                self.stretch_manager.cancel()
            self.stretch_manager = None
            self.stretch_progress_bar.setVisible(False)

    @Slot(int)
    def _on_target_bpm_changed(self, value: int):
        """Handle target BPM change."""
        self.time_stretch_target_bpm = value
        # Update button enabled state if needed
        if self.time_stretch_enabled:
            self.btn_start_stretch_processing.setEnabled(
                len(self.detected_loop_segments) > 0 and len(self.stem_files) > 0
            )

    @Slot()
    def _on_start_stretch_processing_clicked(self):
        """Start background time-stretching processing."""
        # Get original BPM from detected BPM (fallback: 120.0)
        original_bpm = self.detected_bpm if self.detected_bpm else 120.0
        
        # Get all loop segments (intro loops + main loops)
        all_loops = self._get_all_loop_segments()
        
        if not all_loops:
            QMessageBox.warning(self, "No Loops", "Please detect loops first.")
            return
        
        if not self.stem_files:
            QMessageBox.warning(self, "No Stems", "Please load stems first.")
            return
        
        # Filter out loops with negative start times (leading loops with padding)
        # WHY: Leading loops with negative start times contain silence padding that
        #      cannot be time-stretched. Only process loops with valid (non-negative) start times.
        valid_loops = []
        self._loop_index_mapping = {}  # Clear previous mapping
        
        for orig_idx, (start, end) in enumerate(all_loops):
            if start >= 0.0 and end > start:
                # Valid loop - add to valid_loops and create mapping
                filtered_idx = len(valid_loops)
                valid_loops.append((start, end))
                self._loop_index_mapping[orig_idx] = filtered_idx
        
        if not valid_loops:
            QMessageBox.warning(
                self,
                "No Valid Loops",
                "No loops with valid start times found. Leading loops with padding cannot be time-stretched."
            )
            return
        
        # Log if some loops were filtered out
        filtered_count = len(all_loops) - len(valid_loops)
        if filtered_count > 0:
            self.ctx.logger().warning(
                f"Filtered out {filtered_count} loop(s) with negative start times "
                f"(leading loops with padding cannot be time-stretched). "
                f"Only {len(valid_loops)} loop(s) will be processed."
            )
        
        # Initialize stretch manager if needed
        if not self.stretch_manager:
            from core.background_stretch_manager import BackgroundStretchManager, get_optimal_worker_count
            self.stretch_manager = BackgroundStretchManager(max_workers=get_optimal_worker_count())
            self.stretch_manager.progress_updated.connect(self._on_stretch_progress_updated)
            self.stretch_manager.all_completed.connect(self._on_stretch_all_completed)
        
        # Start batch processing
        self.stretch_progress_bar.setVisible(True)
        self.stretch_progress_bar.setValue(0)
        self.stretch_progress_bar.setFormat("Starting...")
        self.btn_start_stretch_processing.setEnabled(False)
        
        self.stretch_manager.start_batch(
            stem_files=self.stem_files,
            loop_segments=valid_loops,
            original_bpm=original_bpm,
            target_bpm=float(self.time_stretch_target_bpm),
            sample_rate=44100
        )
        
        self.ctx.logger().info(
            f"Started time-stretching: {original_bpm} → {self.time_stretch_target_bpm} BPM, "
            f"{len(all_loops)} loops, {len(self.stem_files)} stems"
        )

    @Slot(int, int)
    def _on_stretch_progress_updated(self, completed: int, total: int):
        """Handle stretch progress update."""
        if total > 0:
            percentage = int((completed / total) * 100)
            self.stretch_progress_bar.setValue(percentage)
            self.stretch_progress_bar.setFormat(f"{completed} / {total} loops ({percentage}%)")
            
            # Update info label with progress
            self.loop_playback_info_label.setText(
                f"Processing time-stretching: {completed} / {total} loops ({percentage}%)"
            )

    @Slot()
    def _on_stretch_all_completed(self):
        """Handle stretch completion."""
        self.stretch_progress_bar.setVisible(False)
        self.btn_start_stretch_processing.setEnabled(True)
        
        # Validate that all expected loops are available (if manager exists)
        if self.stretch_manager and self.stem_files:
            missing_loops = []
            all_loops = self._get_all_loop_segments()
            valid_loops = [(start, end) for start, end in all_loops if start >= 0.0]
            
            # Check each valid loop and stem combination
            for loop_idx in range(len(valid_loops)):
                for stem_name in self.stem_files.keys():
                    stem_name_lower = stem_name.lower()
                    if not self.stretch_manager.is_loop_ready(
                        stem_name_lower, loop_idx, self.time_stretch_target_bpm
                    ):
                        # Map back to original loop index if mapping exists
                        if self._loop_index_mapping:
                            orig_idx = None
                            for orig, filtered in self._loop_index_mapping.items():
                                if filtered == loop_idx:
                                    orig_idx = orig
                                    break
                            if orig_idx is not None:
                                missing_loops.append(f"{stem_name} Loop {orig_idx + 1}")
                            else:
                                missing_loops.append(f"{stem_name} Loop {loop_idx + 1} (filtered)")
                        else:
                            missing_loops.append(f"{stem_name} Loop {loop_idx + 1}")
            
            if missing_loops:
                failed_count = len(missing_loops)
                total_expected = len(valid_loops) * len(self.stem_files)
                success_count = total_expected - failed_count
                
                self.ctx.logger().warning(
                    f"Time-stretching completed with {failed_count} failed loops "
                    f"({success_count}/{total_expected} successful). "
                    f"Failed: {missing_loops[:5]}{'...' if len(missing_loops) > 5 else ''}"
                )
                
                self.loop_playback_info_label.setText(
                    f"⚠️ Processing completed: {success_count}/{total_expected} loops ready. "
                    f"Some loops may not be available."
                )
            else:
                self.ctx.logger().info(
                    f"Time-stretching completed successfully: "
                    f"{len(valid_loops)} loops × {len(self.stem_files)} stems = "
                    f"{len(valid_loops) * len(self.stem_files)} total loops ready"
                )
                
                self.loop_playback_info_label.setText(
                    "✅ Time-stretching completed. Ready to play stretched loops."
                )
        else:
            # Fallback if manager or stems not available
            self.loop_playback_info_label.setText(
                "Time-stretching completed. Ready to play stretched loops."
            )
        self.ctx.logger().info("Time-stretching processing completed")

    def _mix_stretched_stems(self, stretched_loops: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Mix stretched loop segments with current stem settings.
        
        Similar to AudioPlayer._mix_stems() but for pre-stretched audio.
        
        Args:
            stretched_loops: Dict mapping stem names to stretched audio arrays
            
        Returns:
            Mixed audio (channels, samples) as float32
        """
        # Find the length of the longest stretched loop
        if not stretched_loops:
            return np.zeros((2, 0), dtype=np.float32)
        
        max_length = max(len(audio) for audio in stretched_loops.values())
        
        # Initialize output (stereo)
        mixed = np.zeros((2, max_length), dtype=np.float32)
        
        # Check if any stem is solo
        any_solo = any(
            settings.is_solo 
            for settings in self.player.stem_settings.values()
        )
        
        # Mix stretched loops
        for stem_name, stretched_audio in stretched_loops.items():
            # Get stem settings from player
            if stem_name not in self.player.stem_settings:
                continue
                
            settings = self.player.stem_settings[stem_name]
            
            # Skip if muted
            if settings.is_muted:
                continue
            
            # Skip if not solo and another stem is solo
            if any_solo and not settings.is_solo:
                continue
            
            # Ensure stereo
            if stretched_audio.ndim == 1:
                audio_stereo = np.stack([stretched_audio, stretched_audio], axis=1)
            else:
                audio_stereo = stretched_audio
            
            # Ensure same length (pad if necessary)
            if len(audio_stereo) < max_length:
                padding = max_length - len(audio_stereo)
                audio_stereo = np.pad(audio_stereo, ((0, padding), (0, 0)), mode='constant')
            elif len(audio_stereo) > max_length:
                audio_stereo = audio_stereo[:max_length]
            
            # Transpose to (channels, samples) format
            audio_stereo = audio_stereo.T
            
            # Apply volume
            audio_stereo = audio_stereo * settings.volume
            
            # Add to mix
            mixed += audio_stereo
        
        # Apply master volume
        mixed = mixed * self.player.master_volume
        
        # Soft clipping to prevent harsh distortion
        peak = np.max(np.abs(mixed))
        if peak > 1.0:
            # Normalize to prevent clipping, with some headroom
            mixed = mixed * (0.95 / peak)
        
        # Final safety clip
        mixed = np.clip(mixed, -1.0, 1.0)
        
        return mixed

    def _play_stretched_loop_segment(self, loop_index: int, repeat: bool = False):
        """
        Play time-stretched loop segment.
        
        Args:
            loop_index: Index of loop in combined list (intro + main)
            repeat: If True, loop repeats continuously
        """
        if not self.stretch_manager:
            QMessageBox.warning(
                self, 
                "Not Ready", 
                "Time-stretching processing not complete. Please start processing first."
            )
            return
        
        # Map original loop index to filtered index
        # WHY: Some loops (with negative start times) were filtered out during processing,
        #      so we need to map the original index to the filtered index used by BackgroundStretchManager
        if self._loop_index_mapping:
            # Mapping exists - some loops were filtered out
            if loop_index not in self._loop_index_mapping:
                QMessageBox.warning(
                    self,
                    "Loop Not Available",
                    f"Loop {loop_index + 1} cannot be time-stretched (contains padding). "
                    f"Please select a different loop."
                )
                return
            filtered_loop_index = self._loop_index_mapping[loop_index]
        else:
            # No mapping exists - all loops were valid, use original index
            # Check if this loop has negative start time (shouldn't happen, but safety check)
            all_loops = self._get_all_loop_segments()
            if loop_index < len(all_loops):
                start_time, _ = all_loops[loop_index]
                if start_time < 0.0:
                    QMessageBox.warning(
                        self,
                        "Loop Not Available",
                        f"Loop {loop_index + 1} cannot be time-stretched (contains padding). "
                        f"Please select a different loop."
                    )
                    return
            filtered_loop_index = loop_index
        
        # Get stretched loops for all stems
        stretched_loops = {}
        target_bpm = self.time_stretch_target_bpm
        
        for stem_name in self.stem_files.keys():
            # BackgroundStretchManager expects lowercase stem names
            # WHY: Task IDs are created with lowercase stem names for consistency
            stem_name_lower = stem_name.lower()
            
            # Debug: Log what we're looking for
            task_id_expected = f"{stem_name_lower}_{filtered_loop_index}_{int(target_bpm)}"
            self.ctx.logger().debug(
                f"Retrieving stretched loop: stem={stem_name_lower}, "
                f"loop_idx={filtered_loop_index} (original={loop_index}), "
                f"bpm={target_bpm}, expected_task_id={task_id_expected}"
            )
            
            stretched_audio = self.stretch_manager.get_stretched_loop(
                stem_name_lower,
                filtered_loop_index,  # Use filtered index
                target_bpm
            )
            
            if stretched_audio is not None:
                stretched_loops[stem_name] = stretched_audio
                self.ctx.logger().debug(
                    f"✓ Found stretched loop for {stem_name} (task_id: {task_id_expected})"
                )
            else:
                # Debug: Check if loop is marked as ready
                is_ready = self.stretch_manager.is_loop_ready(
                    stem_name_lower, filtered_loop_index, target_bpm
                )
                self.ctx.logger().warning(
                    f"✗ Stretched loop not found for {stem_name} "
                    f"(task_id: {task_id_expected}, is_ready: {is_ready})"
                )
        
        if not stretched_loops:
            # Collect debug info for better error message
            debug_info = []
            available_stems = []
            missing_stems = []
            
            for stem_name in self.stem_files.keys():
                stem_name_lower = stem_name.lower()
                task_id_expected = f"{stem_name_lower}_{filtered_loop_index}_{int(target_bpm)}"
                is_ready = self.stretch_manager.is_loop_ready(
                    stem_name_lower, filtered_loop_index, target_bpm
                )
                
                if is_ready:
                    available_stems.append(stem_name)
                    debug_info.append(f"  ✓ {stem_name}: Ready (task_id: {task_id_expected})")
                else:
                    missing_stems.append(stem_name)
                    debug_info.append(f"  ✗ {stem_name}: Not found (task_id: {task_id_expected})")
            
            # Check if processing is still running
            if hasattr(self.stretch_manager, 'is_running') and self.stretch_manager.is_running:
                # Processing still in progress - show progress info
                try:
                    progress = self.stretch_manager.get_progress()
                    if progress and len(progress) == 2:
                        completed, total = progress
                        percentage = int((completed/total)*100) if total > 0 else 0
                        QMessageBox.information(
                            self,
                            "Processing In Progress",
                            f"Time-stretching is still processing.\n\n"
                            f"Progress: {completed} / {total} loops ({percentage}%)\n\n"
                            f"Loop {loop_index + 1} will be available once all stems are processed.\n"
                            f"Please wait for processing to complete."
                        )
                    else:
                        QMessageBox.information(
                            self,
                            "Processing In Progress",
                            f"Time-stretching is still processing.\n\n"
                            f"Loop {loop_index + 1} will be available once all stems are processed.\n"
                            f"Please wait for processing to complete."
                        )
                except Exception:
                    # Fallback if get_progress() fails
                    QMessageBox.information(
                        self,
                        "Processing In Progress",
                        f"Time-stretching is still processing.\n\n"
                        f"Loop {loop_index + 1} will be available once all stems are processed.\n"
                        f"Please wait for processing to complete."
                    )
            else:
                # Processing completed but no loops available - show detailed error
                error_msg = (
                    f"Stretched loops for Loop {loop_index + 1} are not available.\n\n"
                    f"Debug Information:\n" + "\n".join(debug_info) + "\n\n"
                )
                
                if missing_stems:
                    error_msg += (
                        f"Missing stems: {', '.join(missing_stems)}\n\n"
                    )
                
                error_msg += (
                    f"Possible causes:\n"
                    f"- Processing failed for some stems\n"
                    f"- Loop index mismatch (filtered index: {filtered_loop_index})\n"
                    f"- Stem name case mismatch\n"
                    f"- Please try starting processing again"
                )
                
                QMessageBox.warning(
                    self,
                    "Not Ready",
                    error_msg
                )
            return
        
        # Mix stretched stems
        mixed_audio = self._mix_stretched_stems(stretched_loops)
        
        # Determine loop type for display
        all_loops = self._get_all_loop_segments()
        is_leading_loop = loop_index < len(self.detected_intro_loops)
        loop_type = "Leading Loop" if is_leading_loop else "Main Loop"
        relative_index = (
            loop_index + 1
            if is_leading_loop
            else (loop_index - len(self.detected_intro_loops) + 1)
        )
        
        # Stop position timer
        self.position_timer.stop()
        
        # Play via sounddevice
        try:
            import sounddevice as sd
            
            if repeat:
                # Create multiple repetitions for seamless looping
                num_reps = 10
                # Transpose to (samples, channels) for sounddevice
                mixed_transposed = mixed_audio.T
                mixed_repeated = np.tile(mixed_transposed, (num_reps, 1))
                sd.play(mixed_repeated, samplerate=44100, blocking=False)
            else:
                # Transpose to (samples, channels) for sounddevice
                mixed_transposed = mixed_audio.T
                sd.play(mixed_transposed, samplerate=44100, blocking=False)
            
            self.btn_stop_loop.setEnabled(True)
            self.loop_playback_info_label.setText(
                f"Playing {loop_type} {relative_index} (stretched, {'repeating' if repeat else 'once'}): "
                f"{all_loops[loop_index][0]:.2f}s - {all_loops[loop_index][1]:.2f}s"
            )
            self.ctx.logger().info(
                f"Playing stretched {loop_type.lower()} {relative_index} ({'repeat' if repeat else 'once'})"
            )
            
        except Exception as e:
            self.ctx.logger().error(f"Failed to play stretched loop: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Playback Failed",
                f"Failed to play stretched loop: {str(e)}"
            )

    def _find_drums_stem_path(self) -> Optional[Path]:
        """
        Find drums stem path if available.

        WHY: Drums stem gives more accurate BPM detection with DeepRhythm.
             Same logic as _get_audio_for_bpm_detection() but returns Path only.

        Returns:
            Path to drums stem or None if not found
        """
        drums_stem_names = ["drums", "Drums", "DRUMS", "drum", "Drum", "DRUM"]
        for stem_name in drums_stem_names:
            if stem_name in self.stem_files:
                return Path(self.stem_files[stem_name])
        return None

    def _mix_stems_to_array(self) -> Tuple[np.ndarray, int]:
        """
        Mix all loaded stems into a single audio array

        Returns:
            Tuple of (mixed_audio, sample_rate)

        WHY: Uses player's sample rate to ensure waveform matches playback exactly.
        This prevents drift between beat markers and actual audio playback.
        """
        if not self.stem_files:
            raise ValueError("No stems loaded")

        # Use player's sample rate for consistency
        # WHY: Player may have resampled stems, so we must use same rate for waveform
        player_sample_rate = self.player.sample_rate
        if player_sample_rate == 0:
            # Player not initialized yet, use first file's rate as fallback
            first_path = next(iter(self.stem_files.values()))
            _, fallback_sr = sf.info(str(first_path))
            player_sample_rate = fallback_sr
            self.ctx.logger().warning(
                f"Player sample rate not set, using file rate: {player_sample_rate} Hz"
            )

        mixed_audio = None

        for stem_name, stem_path in self.stem_files.items():
            audio_data, file_sr = sf.read(stem_path, dtype="float32")

            # Ensure mono
            if audio_data.ndim == 2:
                audio_data = np.mean(audio_data, axis=1)

            # Resample to player's sample rate if needed
            # WHY: Ensures waveform uses same sample rate as playback
            if file_sr != player_sample_rate:
                import librosa

                audio_data = librosa.resample(
                    audio_data,
                    orig_sr=file_sr,
                    target_sr=player_sample_rate,
                    res_type="kaiser_best",
                )
                self.ctx.logger().debug(
                    f"Resampled {stem_name} for waveform: {file_sr} Hz -> {player_sample_rate} Hz"
                )

            if mixed_audio is None:
                mixed_audio = audio_data
            else:
                # Mix with existing (handle different lengths)
                min_len = min(len(mixed_audio), len(audio_data))
                mixed_audio[:min_len] += audio_data[:min_len]

        # Normalize to prevent clipping
        max_val = np.max(np.abs(mixed_audio))
        if max_val > 0:
            mixed_audio = mixed_audio / max_val

        return mixed_audio, player_sample_rate

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
        # Export buttons moved to sidebar - connected via MainWindow

    @Slot()
    def _on_load_dir(self):
        """Load all stems from directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory with Stems"
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
                f"No supported audio files found in:\n{dir_path}",
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
        audio_files = [f for f in file_paths if file_manager.is_supported_format(f)]

        if not audio_files:
            QMessageBox.warning(
                self,
                "No Audio Files",
                "No supported audio files were dropped.\n\n"
                "Supported formats: WAV, MP3, FLAC, M4A, OGG, AAC",
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

        # Disable playback buttons
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

        # Notify sidebar that stems are cleared
        self.stems_loaded_changed.emit(False)

        # Reset info label
        self.info_label.setText("Load separated stems to use the mixer and playback.")

        # Reset all loop detection state
        self._reset_loop_detection_state()

        self.ctx.logger().info("Cleared all loaded stems")

        # Update button states (all should be disabled now)
        self._update_button_states()

    def _load_stems(self, file_paths: list[Path]):
        """Load stem files into player"""
        # Reset all loop detection state before loading new stems
        self._reset_loop_detection_state()

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
            match = re.search(r"\(([^)]+)\)", file_path.stem)
            if match:
                stem_name = match.group(1)
            else:
                # Second try: Parse filename parts, skip model/ensemble suffixes
                name_parts = file_path.stem.split("_")

                # Known suffixes to ignore (model names, ensemble marker)
                ignore_suffixes = {
                    "ensemble",
                    "bs-roformer",
                    "mel-roformer",
                    "demucs",
                    "htdemucs",
                    "4s",
                    "6s",
                    "v4",
                    "demucs4s",
                    "demucs6s",
                }

                # Filter out ignored suffixes from the end
                stem_parts = []
                for part in reversed(name_parts):
                    part_lower = part.lower()
                    # Stop when we hit an ignored suffix
                    if part_lower in ignore_suffixes or any(
                        suffix in part_lower for suffix in ignore_suffixes
                    ):
                        continue
                    stem_parts.insert(0, part)

                # Use the last meaningful part as stem name
                if stem_parts:
                    stem_name = stem_parts[-1]
                else:
                    # Fallback: use original last part or whole filename
                    stem_name = (
                        name_parts[-1] if len(name_parts) > 1 else file_path.stem
                    )

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
                self.position_slider.setEnabled(True)

                # Notify sidebar that stems are loaded (enables export buttons)
                self.stems_loaded_changed.emit(True)

                # Update duration
                duration = self.player.get_duration()
                self.duration_label.setText(self._format_time(duration))
                self.position_slider.setRange(0, int(duration * 1000))  # milliseconds

                self.info_label.setText(
                    f"✓ Loaded {len(self.stem_files)} stems. "
                    f"Duration: {self._format_time(duration)}"
                )

                self.ctx.logger().info(
                    f"Loaded {len(self.stem_files)} stems for playback"
                )

                # Check if playback is available and warn user if not
                is_available, error_msg = self.player.is_playback_available()
                if not is_available:
                    # Show warning but don't block loading
                    QMessageBox.warning(
                        self,
                        "Playback Not Available",
                        f"Stems loaded successfully, but playback is not available:\n\n{error_msg}\n\n"
                        "You can still export mixed audio, but cannot play it back in the app.",
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
                    "Failed to load stems. Check the log for details.",
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
        match = re.search(r"^(.+?)_\([^)]+\)", stem_name)
        if match:
            return match.group(1)

        # Pattern 2: "songname_stemname_modelname" -> "songname"
        # Known suffixes to remove
        ignore_suffixes = {
            "ensemble",
            "bs-roformer",
            "mel-roformer",
            "demucs",
            "htdemucs",
            "4s",
            "6s",
            "v4",
            "demucs4s",
            "demucs6s",
        }

        parts = stem_name.split("_")
        # Find where stem name starts (usually after common filename)
        # Common pattern: commonname_stemname_suffix
        if len(parts) >= 2:
            # Try to identify stem name (common stem names)
            common_stem_names = [
                "vocals",
                "vocal",
                "drums",
                "drum",
                "bass",
                "other",
                "piano",
                "guitar",
                "instrumental",
                "instrum",
            ]

            # Find first part that looks like a stem name
            for i, part in enumerate(parts[1:], 1):
                part_lower = part.lower()
                if part_lower in common_stem_names or any(
                    suffix in part_lower for suffix in ignore_suffixes
                ):
                    # Everything before this is the common filename
                    return "_".join(parts[:i])

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
            QMessageBox.critical(self, "Playback Not Available", error_msg)
            return

        # Try to start playback
        success = self.player.play()

        if not success:
            QMessageBox.warning(
                self,
                "Playback Failed",
                "Failed to start playback. Make sure audio device is available.",
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
        duration_seconds = (
            self.player.duration_samples / self.player.sample_rate
            if self.player.sample_rate > 0
            else 0.0
        )

        dialog = ExportSettingsDialog(
            duration_seconds=duration_seconds,
            num_stems=len(self.stem_files),
            parent=self,
        )

        if dialog.exec() != ExportSettingsDialog.Accepted:
            # User cancelled
            return

        # Get settings from dialog
        settings = dialog.get_settings()

        # Ask user for output location
        if settings.enable_chunking and settings.export_mode == "individual":
            # Individual stems with chunking - ask for directory
            output_dir = QFileDialog.getExistingDirectory(
                self, "Select Output Directory for Stem Chunks", ""
            )

            if not output_dir:
                return

            output_path = Path(output_dir)

        else:
            # Mixed audio (with or without chunking) - ask for file
            extension = f".{settings.file_format.lower()}"
            filter_str = f"{settings.file_format} Files (*{extension})"

            save_path, _ = QFileDialog.getSaveFileName(
                self, "Export Audio", "", filter_str
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
                if settings.export_mode == "mixed":
                    # Mixed audio in chunks
                    chunk_paths = self.player.export_mix_chunked(
                        output_path,
                        settings.chunk_length,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
                        common_filename=common_filename,
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
                        result_message = (
                            "Failed to export chunks. Check the log for details."
                        )

                else:  # individual stems
                    # Individual stems in chunks
                    all_chunks = self.player.export_stems_chunked(
                        output_path,
                        settings.chunk_length,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
                        common_filename=common_filename,
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
                        result_message = (
                            "Failed to export stem chunks. Check the log for details."
                        )

            else:
                # No chunking - standard export
                if settings.export_mode == "mixed":
                    # Standard mixed export
                    success = self.player.export_mix(
                        output_path,
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
                    )

                    if success:
                        result_message = f"Mixed audio exported to:\n{output_path}"
                    else:
                        result_message = (
                            "Failed to export mixed audio. Check the log for details."
                        )

                else:  # individual stems without chunking
                    # Export individual stems as full files
                    all_chunks = self.player.export_stems_chunked(
                        output_path,
                        chunk_length_seconds=999999,  # Very long chunks = no splitting
                        file_format=settings.file_format,
                        bit_depth=settings.bit_depth,
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
                        result_message = (
                            "Failed to export stems. Check the log for details."
                        )

            # Show result message
            if success:
                QMessageBox.information(self, "Export Successful", result_message)
            else:
                QMessageBox.critical(self, "Export Failed", result_message)

        except Exception as e:
            self.ctx.logger().error(f"Export error: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Export Failed", f"An error occurred during export:\n{str(e)}"
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
        drums_stem_names = ["drums", "Drums", "DRUMS", "drum", "Drum", "DRUM"]
        for stem_name in drums_stem_names:
            if stem_name in self.stem_files:
                drums_path = Path(self.stem_files[stem_name])
                self.ctx.logger().info(
                    f"Using drums stem for BPM detection: {drums_path.name}"
                )
                return drums_path, f"drums stem ({drums_path.name})"

        # Priority 2: No drums found, create mixed audio from all stems
        self.ctx.logger().info(
            "No drums stem found, using mixed audio for BPM detection"
        )

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
                suffix=".wav", delete=False, prefix="bpm_detect_"
            )
            temp_path = Path(temp_file.name)
            temp_file.close()

            # Write mixed audio to temp file
            sf.write(
                str(temp_path), mixed_audio, self.player.sample_rate, subtype="PCM_24"
            )

            self.ctx.logger().info(
                f"Created mixed audio for BPM detection: {temp_path.name}"
            )
            return temp_path, "mixed audio (all stems)"

        except Exception as e:
            self.ctx.logger().error(
                f"Failed to create mixed audio file for BPM detection: {e}"
            )
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
                    "No stems loaded. Please load audio files first.",
                )
                return

            # Mix all stems to get complete audio
            # _mix_stems returns audio in shape (channels, samples)
            mixed_audio = self.player._mix_stems(0, self.player.duration_samples)

            if mixed_audio is None or len(mixed_audio) == 0:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "Unable to mix audio for export. Please try loading stems again.",
                )
                return

            # Transpose to (samples, channels) for soundfile compatibility
            mixed_audio = mixed_audio.T

            # Calculate duration
            duration_seconds = (
                self.player.duration_samples / self.player.sample_rate
                if self.player.sample_rate > 0
                else 0.0
            )

            # Get common filename from first loaded stem
            common_filename = self._get_common_filename()

            # Check if Loop Preview has detected beats - use those settings as presets
            preset_bpm = None
            preset_bars = None

            if (
                self.detected_downbeat_times is not None
                and len(self.detected_downbeat_times) >= 2
            ):
                # Calculate BPM from downbeat intervals (more accurate than beat intervals)
                downbeat_intervals = np.diff(self.detected_downbeat_times)
                median_bar_duration = float(np.median(downbeat_intervals))
                if median_bar_duration > 0:
                    # 4 beats per bar in 4/4 time
                    preset_bpm = (60.0 * 4) / median_bar_duration
                    self.ctx.logger().info(
                        f"Using Loop Preview BPM: {preset_bpm:.1f} "
                        f"(from {len(self.detected_downbeat_times)} downbeats)"
                    )

                # Use the bars per loop setting from Loop Preview
                preset_bars = self._bars_per_loop
                self.ctx.logger().info(f"Using Loop Preview bars: {preset_bars}")

            # Show loop export dialog with presets from Loop Preview (if available)
            dialog = LoopExportDialog(
                player_widget=self,
                duration_seconds=duration_seconds,
                num_stems=len(self.stem_files),
                preset_bpm=preset_bpm,
                preset_bars=preset_bars,
                parent=self,
            )

            if dialog.exec() != LoopExportDialog.Accepted:
                return

            # Get settings from dialog
            settings = dialog.get_settings()

            # Ask user for output directory
            output_dir = QFileDialog.getExistingDirectory(
                self, "Select Output Directory for Loop Export"
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
            if settings.export_mode == "individual":
                # Export each stem individually
                self._export_individual_stems(
                    output_path=output_path, settings=settings
                )
            else:
                # Export mixed audio (original logic)
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False, dir=str(output_path.parent)
                ) as temp_file:
                    temp_path = Path(temp_file.name)

                    try:
                        # Export current mix to temporary file
                        sf.write(
                            str(temp_path),
                            mixed_audio,
                            self.player.sample_rate,
                            subtype="PCM_24",
                        )

                        # Progress dialog
                        progress_dialog = QProgressDialog(
                            "Preparing export...", None, 0, 100, self
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
                            stem_name=None,  # Mixed audio, no stem name
                        )

                        # Close progress dialog
                        progress_dialog.setValue(100)
                        progress_dialog.close()
                        QApplication.processEvents()

                        # Show result
                        if result.success:
                            warning_text = ""
                            if result.warning_messages:
                                warning_text = "\n\nWarnings:\n" + "\n".join(
                                    f"• {w}" for w in result.warning_messages
                                )

                            QMessageBox.information(
                                self,
                                "Export Successful",
                                f"Exported {result.chunk_count} loop file(s) to:\n{output_path}\n\n"
                                f"Format: {settings.file_format}, {settings.bit_depth} bit, "
                                f"{'Stereo' if settings.channels == 2 else 'Mono'}\n"
                                f"Loop length: {settings.bars} bars at {settings.bpm} BPM"
                                f"{warning_text}",
                            )
                        else:
                            QMessageBox.critical(
                                self,
                                "Export Failed",
                                f"Loop export failed:\n{result.error_message}",
                            )

                    finally:
                        # Clean up temporary file
                        try:
                            temp_path.unlink()
                        except Exception as e:
                            self.ctx.logger().warning(
                                f"Failed to delete temp file {temp_path}: {e}"
                            )

        except Exception as e:
            self.ctx.logger().error(f"Loop export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during loop export:\n{str(e)}",
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
                "Preparing stem export...", None, 0, len(self.stem_files) * 100, self
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
                    overall_progress.setLabelText(
                        f"Exporting {stem_name}...\n{message}"
                    )
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
                    stem_name=stem_name,  # Individual stem export
                )

                if result.success:
                    total_chunks += result.chunk_count
                    stem_results.append((stem_name, result.chunk_count))
                    if result.warning_messages:
                        all_warnings.extend(
                            [f"{stem_name}: {w}" for w in result.warning_messages]
                        )
                else:
                    # Log error but continue with other stems
                    self.ctx.logger().error(
                        f"Failed to export {stem_name}: {result.error_message}"
                    )
                    all_warnings.append(
                        f"{stem_name}: Export failed - {result.error_message}"
                    )

            # Close progress dialog
            overall_progress.setValue(len(self.stem_files) * 100)
            overall_progress.close()
            QApplication.processEvents()

            # Show summary
            if total_chunks > 0:
                # Build summary text
                summary_lines = [
                    f"• {name}: {count} file(s)" for name, count in stem_results
                ]
                summary_text = "\n".join(summary_lines)

                warning_text = ""
                if all_warnings:
                    warning_text = "\n\nWarnings:\n" + "\n".join(
                        f"• {w}" for w in all_warnings
                    )

                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {total_chunks} loop file(s) total from {len(stem_results)} stem(s) to:\n{output_path}\n\n"
                    f"{summary_text}\n\n"
                    f"Format: {settings.file_format}, {settings.bit_depth} bit, "
                    f"{'Stereo' if settings.channels == 2 else 'Mono'}\n"
                    f"Loop length: {settings.bars} bars at {settings.bpm} BPM"
                    f"{warning_text}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    "Failed to export any stems. Check the log for details.",
                )

        except Exception as e:
            self.ctx.logger().error(f"Individual stem export error: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Failed",
                f"An error occurred during individual stem export:\n{str(e)}",
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
            # Reset position display to 0 (avoid get_position() lock acquisition)
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(0)
            self.position_slider.blockSignals(False)
            self.current_time_label.setText("00:00")

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
        QTimer.singleShot(50, lambda: setattr(self, "_user_seeking", False))

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def load_separation_result(self, stems: Dict[str, Path]):
        """Load stems from separation result"""
        if stems:
            self._load_stems(list(stems.values()))

    # === PUBLIC EXPORT METHODS (called from MainWindow sidebar) ===

    def has_stems_loaded(self) -> bool:
        """
        Check if stems are currently loaded.

        WHY: Used by MainWindow to determine export button states
        """
        return len(self.stem_files) > 0

    @Slot()
    def export_mixed_audio(self):
        """
        Public method to trigger mixed audio export.

        PURPOSE: Called from MainWindow sidebar export button
        CONTEXT: Wrapper around internal _on_export method
        """
        self._on_export()

    @Slot()
    def export_loops(self):
        """
        Public method to trigger loop export.

        PURPOSE: Called from MainWindow sidebar export button
        CONTEXT: Wrapper around internal _on_export_loops method
        """
        self._on_export_loops()

    def apply_translations(self):
        """Apply current language translations"""
        # Translation keys would be defined in resources/translations/*.json
        pass

    def closeEvent(self, event):
        """Handle widget close"""
        # Stop playback and cleanup
        self.player.stop()
        super().closeEvent(event)
