"""
Main window scaffolding for the Stem Separator GUI.
"""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Dict

from PySide6.QtCore import QUrl, Qt, Slot, QSize
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QFrame,
    QPushButton,
    QButtonGroup,
)
from PySide6.QtGui import QDesktopServices

from config import APP_NAME, ICONS_DIR
from ui.app_context import AppContext, get_app_context
from ui.widgets.upload_widget import UploadWidget
from ui.widgets.recording_widget import RecordingWidget
from ui.widgets.queue_widget import QueueWidget
from ui.widgets.player_widget import PlayerWidget
from ui.widgets.settings_dialog import SettingsDialog
from ui.theme.macos_effects import MacOSEffects
from ui.theme.macos_dialogs import MacOSDialogs


class MainWindow(QMainWindow):
    """
    PURPOSE: Provide the top-level PySide6 window that hosts all GUI components.
    CONTEXT: Replaced TabWidget with Sidebar + StackedWidget layout for modern UX.
    """

    def __init__(self) -> None:
        super().__init__()
        self._context: AppContext = get_app_context()
        self._logger = self._context.logger()
        self._icons_cache: Dict[str, QIcon] = {}

        # Theme is now applied at application level in main.py

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._connect_actions()
        self._apply_translations()

        self._logger.info("Main window initialised")

    def _setup_ui(self) -> None:
        """
        PURPOSE: Configure the central layout with Sidebar and StackedWidget.
        CONTEXT: Replaces QTabWidget with a persistent left sidebar and content area.
        """

        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)  # Larger default size for modern displays
        
        # Set window icon
        icon_path = ICONS_DIR / "app_icon_1024.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # macOS-specific window configuration
        if platform.system() == "Darwin":
            # Enable native full-screen button
            self.setWindowFlag(Qt.WindowFullscreenButtonHint, True)
            # Set minimum size to prevent tiny windows
            self.setMinimumSize(1000, 700)
            # Center window on screen
            self._center_on_screen()

        # Main container
        main_widget = QWidget()
        main_v_layout = QVBoxLayout(main_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)
        
        # Content container (Sidebar + Stack)
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        self.setCentralWidget(main_widget)

        # 1. LEFT SIDEBAR
        self._sidebar = QFrame()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(220)  # Wide sidebar for text labels
        
        # Sidebar layout
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 10, 0, 20)
        sidebar_layout.setSpacing(0)

        # Navigation Button Group (Exclusive)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        # 2. RIGHT CONTENT AREA (Stacked)
        self._content_stack = QStackedWidget()

        # Initialize Widgets
        self._upload_widget = UploadWidget(self)
        self._recording_widget = RecordingWidget(self)
        self._queue_widget = QueueWidget(self)
        self._player_widget = PlayerWidget(self)

        # Add to Stack
        self._content_stack.addWidget(self._upload_widget)    # Index 0
        self._content_stack.addWidget(self._recording_widget) # Index 1
        self._content_stack.addWidget(self._queue_widget)     # Index 2
        self._content_stack.addWidget(self._player_widget)    # Index 3

        # Create Nav Buttons
        # We will set text in _apply_translations
        self._btn_upload = self._create_nav_button("upload", 0)
        self._btn_record = self._create_nav_button("mic", 1)
        self._btn_queue = self._create_nav_button("list", 2)
        self._btn_player = self._create_nav_button("play", 3)
        
        # --- SIDEBAR STRUCTURE ---
        
        # SECTION: INPUT
        self._lbl_input = QLabel("Input")
        self._lbl_input.setObjectName("sidebar_header")
        sidebar_layout.addWidget(self._lbl_input)
        sidebar_layout.addWidget(self._btn_upload)
        sidebar_layout.addWidget(self._btn_record)
        
        # SEPARATOR 1
        sep1 = QFrame()
        sep1.setObjectName("sidebar_separator")
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Plain)
        sidebar_layout.addWidget(sep1)

        # SECTION: PROCESSING
        self._lbl_process = QLabel("Processing")
        self._lbl_process.setObjectName("sidebar_header")
        sidebar_layout.addWidget(self._lbl_process)
        sidebar_layout.addWidget(self._btn_queue)
        
        # SEPARATOR 2
        sep2 = QFrame()
        sep2.setObjectName("sidebar_separator")
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Plain)
        sidebar_layout.addWidget(sep2)

        # SECTION: MONITORING & EXPORT
        self._lbl_monitoring = QLabel("Monitoring & Export")
        self._lbl_monitoring.setObjectName("sidebar_header")
        sidebar_layout.addWidget(self._lbl_monitoring)
        sidebar_layout.addWidget(self._btn_player)
        
        sidebar_layout.addStretch() # Push buttons to top

        # Set default selection
        self._btn_upload.setChecked(True)

        # Assemble Content Layout
        content_layout.addWidget(self._sidebar)
        content_layout.addWidget(self._content_stack)
        
        # Add content to main VBox with stretch factor 1 to allow shrinking
        main_v_layout.addWidget(content_widget, stretch=1)
        
        # Wire up signals between widgets
        self._upload_widget.file_queued.connect(self._queue_widget.add_task)
        self._upload_widget.start_queue_requested.connect(self._on_start_queue_requested)
        self._recording_widget.recording_saved.connect(self._on_recording_saved)

        status_bar = QStatusBar(self)
        status_bar.showMessage(self._context.translate("status.ready", fallback="Ready"))
        self.setStatusBar(status_bar)

        # Apply macOS vibrancy effects (Sidebar)
        if platform.system() == "Darwin":
            # Dark sidebar effect
            MacOSEffects.apply_sidebar_effect(self._sidebar, dark=True)

    def _create_nav_button(self, icon_name: str, index: int) -> QPushButton:
        """Helper to create sidebar navigation buttons"""
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setObjectName("sidebar_button") # For styling
        # Connect click to page switch
        btn.clicked.connect(lambda: self._content_stack.setCurrentIndex(index))
        self._nav_group.addButton(btn)
        # TODO: Load icon here once we have them, or use unicode/text for now
        return btn

    def _center_on_screen(self) -> None:
        """Center window on primary screen"""
        try:
            from PySide6.QtGui import QScreen
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.availableGeometry()
                self.move(
                    (geometry.width() - self.width()) // 2,
                    (geometry.height() - self.height()) // 2
                )
        except Exception:
            pass

    def _setup_menu(self) -> None:
        """Build menu bar."""
        menubar = self.menuBar()

        if platform.system() == "Darwin":
            menubar.setNativeMenuBar(True)

        # File menu
        self._file_menu = menubar.addMenu("")
        self._open_files_action = QAction(self._load_icon("folder-open"), "", self)
        self._file_menu.addAction(self._open_files_action)
        self._file_menu.addSeparator()

        if platform.system() == "Darwin":
            self._close_window_action = QAction("Close Window", self)
            self._close_window_action.setShortcut(QKeySequence("Ctrl+W"))
            self._file_menu.addAction(self._close_window_action)

            self._minimize_action = QAction("Minimize", self)
            self._minimize_action.setShortcut(QKeySequence("Ctrl+M"))
            self._file_menu.addAction(self._minimize_action)
            self._file_menu.addSeparator()

        self._quit_action = QAction(self._load_icon("application-exit"), "", self)
        self._quit_action.setShortcut(QKeySequence.Quit)
        self._file_menu.addAction(self._quit_action)

        # Edit menu (standard macOS menu)
        if platform.system() == "Darwin":
            self._setup_edit_menu(menubar)

        # View menu
        self._view_menu = menubar.addMenu("")
        self._settings_action = QAction(self._load_icon("preferences-system"), "", self)
        if platform.system() == "Darwin":
            self._settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self._view_menu.addAction(self._settings_action)

        # Help menu
        self._help_menu = menubar.addMenu("")
        self._about_action = QAction(self._load_icon("help-about"), "", self)
        self._help_menu.addAction(self._about_action)

    def _setup_edit_menu(self, menubar) -> None:
        """Setup standard Edit menu"""
        self._edit_menu = menubar.addMenu("Edit")
        
        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.Undo)
        self._undo_action.setEnabled(False)
        self._edit_menu.addAction(self._undo_action)
        
        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.Redo)
        self._redo_action.setEnabled(False)
        self._edit_menu.addAction(self._redo_action)
        
        self._edit_menu.addSeparator()
        
        self._cut_action = QAction("Cut", self)
        self._cut_action.setShortcut(QKeySequence.Cut)
        self._cut_action.setEnabled(False)
        self._edit_menu.addAction(self._cut_action)
        
        self._copy_action = QAction("Copy", self)
        self._copy_action.setShortcut(QKeySequence.Copy)
        self._copy_action.setEnabled(False)
        self._edit_menu.addAction(self._copy_action)
        
        self._paste_action = QAction("Paste", self)
        self._paste_action.setShortcut(QKeySequence.Paste)
        self._paste_action.setEnabled(False)
        self._edit_menu.addAction(self._paste_action)
        
        self._edit_menu.addSeparator()
        
        self._select_all_action = QAction("Select All", self)
        self._select_all_action.setShortcut(QKeySequence.SelectAll)
        self._select_all_action.setEnabled(False)
        self._edit_menu.addAction(self._select_all_action)

    def _setup_toolbar(self) -> None:
        """Provide a main toolbar with quick-access actions."""
        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        if platform.system() == "Darwin":
            toolbar.setStyleSheet("""
                QToolBar {
                    background: transparent;
                    border: none;
                    spacing: 12px;
                    padding: 8px;
                }
                QToolButton {
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 6px;
                    font-size: 11px;
                }
                QToolButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                }
                QToolButton:pressed {
                    background: rgba(255, 255, 255, 0.15);
                }
            """)

        toolbar.addAction(self._settings_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar.addWidget(spacer)

        toolbar.addAction(self._about_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _connect_actions(self) -> None:
        """Wire UI actions to their respective slots."""
        self._open_files_action.triggered.connect(self._choose_files)
        self._quit_action.triggered.connect(QApplication.instance().quit)
        self._settings_action.triggered.connect(self._show_settings)
        self._about_action.triggered.connect(self._show_about_dialog)

        if platform.system() == "Darwin":
            self._close_window_action.triggered.connect(self.close)
            self._minimize_action.triggered.connect(self.showMinimized)

    def _apply_translations(self) -> None:
        """Refresh all text labels using the translation system."""
        translator = self._context.translate
        self.setWindowTitle(translator("app.title", fallback=APP_NAME))

        self._file_menu.setTitle(translator("menu.file", fallback="File"))
        self._open_files_action.setText(translator("menu.file.open_files", fallback="Open Audio Files"))
        self._quit_action.setText(translator("menu.file.quit", fallback="Quit"))

        self._view_menu.setTitle(translator("menu.view", fallback="View"))
        self._settings_action.setText(translator("menu.view.settings", fallback="Settings"))

        self._help_menu.setTitle(translator("menu.help", fallback="Help"))
        self._about_action.setText(translator("menu.help.about", fallback="About"))

        # Update Sidebar Headers
        self._lbl_input.setText(translator("sidebar.input", fallback="INPUT"))
        self._lbl_process.setText(translator("sidebar.processing", fallback="PROCESSING"))
        self._lbl_monitoring.setText(translator("sidebar.monitoring", fallback="MONITORING & EXPORT"))

        # Update Sidebar Buttons
        self._btn_upload.setText(translator("tabs.upload", fallback="Upload"))
        self._btn_record.setText(translator("tabs.recording", fallback="Recording"))
        self._btn_queue.setText(translator("tabs.queue", fallback="Queue"))
        self._btn_player.setText(translator("tabs.player", fallback="Player"))

        if self.statusBar():
            self.statusBar().showMessage(translator("status.ready", fallback="Ready"))

    def _load_icon(self, name: str) -> QIcon:
        """Load icons from the configured resources directory."""
        if name in self._icons_cache:
            return self._icons_cache[name]
        candidate = ICONS_DIR / f"{name}.png"
        icon = QIcon(str(candidate)) if candidate.exists() else QIcon()
        self._icons_cache[name] = icon
        return icon

    @Slot()
    def _choose_files(self) -> None:
        """Allow selecting audio files using native file dialog."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.ExistingFiles)

        if platform.system() == "Darwin":
            dialog.setOption(QFileDialog.DontUseNativeDialog, False)
            dialog.setOption(QFileDialog.DontUseCustomDirectoryIcons, False)

        dialog.setNameFilters(
            [
                self._context.translate(
                    "dialog.files.filter.audio",
                    fallback="Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg *.aac)",
                ),
                self._context.translate("dialog.files.filter.all", fallback="All Files (*)"),
            ]
        )

        if dialog.exec():
            selected_files = dialog.selectedFiles()
            self._logger.info("Selected files for processing: %s", selected_files)
            self.statusBar().showMessage(
                self._context.translate(
                    "status.files.selected",
                    fallback=f"Selected {len(selected_files)} file(s)",
                    count=len(selected_files),
                ),
                5000,
            )
            # If we are not on upload tab, switch to it? 
            # Maybe better to let user decide, but we could:
            # self._content_stack.setCurrentIndex(0)
            # self._btn_upload.setChecked(True)

    @Slot()
    def _show_about_dialog(self) -> None:
        """Display application metadata."""
        info = self._context.translate(
            "dialog.about.body",
            fallback=f"{APP_NAME}\n\nSystem audio stem separation with AI models.",
        )
        MacOSDialogs.about(self, self.windowTitle(), info)

    @Slot()
    def _show_settings(self) -> None:
        """Display settings dialog."""
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    @Slot()
    def _on_settings_changed(self) -> None:
        """React to settings changes."""
        self._logger.info("Settings changed, refreshing UI")
        self._apply_translations()

    @Slot()
    def _on_start_queue_requested(self):
        """Handle start request: Switch to queue and start"""
        self._content_stack.setCurrentIndex(2) # Queue Tab
        self._btn_queue.setChecked(True)
        self._queue_widget.start_processing()

    @Slot()
    def _on_recording_saved(self, file_path: Path) -> None:
        """Handle recording saved signal."""
        self._logger.info(f"Recording saved: {file_path}")
        if self.statusBar():
            self.statusBar().showMessage(f"Recording saved: {file_path.name}", 5000)
        
        # Auto-switch to Upload/Input tab to let user proceed
        self._content_stack.setCurrentIndex(0)
        self._btn_upload.setChecked(True)
        self._upload_widget.add_file(file_path)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Intercept close event for graceful shutdown."""
        self._logger.info("Application shutdown requested")
        event.accept()
