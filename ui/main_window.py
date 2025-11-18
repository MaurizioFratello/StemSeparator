"""
Main window scaffolding for the Stem Separator GUI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from PySide6.QtCore import QUrl, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QDesktopServices

from config import APP_NAME, ICONS_DIR
from ui.app_context import AppContext, get_app_context
from ui.widgets.upload_widget import UploadWidget
from ui.widgets.recording_widget import RecordingWidget
from ui.widgets.queue_widget import QueueWidget
from ui.widgets.player_widget import PlayerWidget
from ui.widgets.settings_dialog import SettingsDialog
from ui.theme import ThemeManager


class MainWindow(QMainWindow):
    """
    PURPOSE: Provide the top-level PySide6 window that hosts all GUI components.
    CONTEXT: First step of Phase 4 – establishes shared menus, toolbar slots, and tab placeholders
             so subsequent widgets can be integrated incrementally.
    """

    def __init__(self) -> None:
        super().__init__()
        self._context: AppContext = get_app_context()
        self._logger = self._context.logger()
        self._tab_widget = QTabWidget()
        self._icons_cache: Dict[str, QIcon] = {}

        # Apply modern theme
        self._apply_theme()

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._connect_actions()
        self._apply_translations()

        self._logger.info("Main window initialised")

    def _apply_theme(self) -> None:
        """
        PURPOSE: Apply modern dark theme to the application.
        CONTEXT: Loads and applies QSS stylesheet for consistent modern look.
        """
        try:
            theme_manager = ThemeManager.instance()
            stylesheet = theme_manager.load_stylesheet()
            self.setStyleSheet(stylesheet)
            self._logger.info("Modern theme applied successfully")
        except Exception as e:
            self._logger.warning(f"Failed to load theme: {e}. Using default Qt theme.")

    def _setup_ui(self) -> None:
        """
        PURPOSE: Configure the central layout and default tabs.
        CONTEXT: Tabs currently use placeholders that will be replaced by concrete widgets in later
                 tasks while preserving tab order and identifiers.
        """

        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)  # Larger default size for modern displays
        self.setCentralWidget(self._tab_widget)

        # Modern tab widget configuration
        self._tab_widget.setDocumentMode(True)  # Cleaner look without frame

        # WHY: Provide predictable tab indices for upcoming widgets.
        self._upload_widget = UploadWidget(self)
        self._recording_widget = RecordingWidget(self)
        self._queue_widget = QueueWidget(self)
        self._player_widget = PlayerWidget(self)
        
        self._tab_widget.addTab(self._upload_widget, "Upload")
        self._tab_widget.addTab(self._recording_widget, "Recording")
        self._tab_widget.addTab(self._queue_widget, "Queue")
        self._tab_widget.addTab(self._player_widget, "Player")
        
        # Wire up signals between widgets
        self._upload_widget.file_queued.connect(self._queue_widget.add_task)
        self._recording_widget.recording_saved.connect(self._on_recording_saved)

        status_bar = QStatusBar(self)
        status_bar.showMessage(self._context.translate("status.ready", fallback="Ready"))
        self.setStatusBar(status_bar)

    def _setup_menu(self) -> None:
        """
        PURPOSE: Build menu bar with placeholders for file/view/help actions.
        CONTEXT: Menus expose core diagnostics (logs), localisation, and about dialogs from the
                 outset to keep workflow consistent as widgets arrive.
        """

        menubar = self.menuBar()

        self._file_menu = menubar.addMenu("")  # Populated in _apply_translations.
        self._open_logs_action = QAction(self._load_icon("document-open"), "", self)
        self._file_menu.addAction(self._open_logs_action)

        self._open_files_action = QAction(self._load_icon("folder-open"), "", self)
        self._file_menu.addAction(self._open_files_action)

        self._file_menu.addSeparator()
        self._quit_action = QAction(self._load_icon("application-exit"), "", self)
        self._quit_action.setShortcut("Ctrl+Q")
        self._file_menu.addAction(self._quit_action)

        self._view_menu = menubar.addMenu("")
        self._settings_action = QAction(self._load_icon("preferences-system"), "", self)
        self._view_menu.addAction(self._settings_action)

        self._help_menu = menubar.addMenu("")
        self._about_action = QAction(self._load_icon("help-about"), "", self)
        self._help_menu.addAction(self._about_action)

    def _setup_toolbar(self) -> None:
        """
        PURPOSE: Provide a main toolbar with quick-access actions for diagnostics.
        CONTEXT: Toolbar mirrors menu entries to streamline future UX polish.
        """

        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.addAction(self._open_logs_action)
        toolbar.addAction(self._open_files_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _connect_actions(self) -> None:
        """
        PURPOSE: Wire UI actions to their respective slots.
        CONTEXT: Keeps behaviour declarative and simplifies unit testing by isolating slot logic.
        """

        self._open_logs_action.triggered.connect(self._open_logs)
        self._open_files_action.triggered.connect(self._choose_files)
        self._quit_action.triggered.connect(QApplication.instance().quit)
        self._settings_action.triggered.connect(self._show_settings)
        self._about_action.triggered.connect(self._show_about_dialog)

    def _apply_translations(self) -> None:
        """
        PURPOSE: Refresh all text labels using the translation system.
        CONTEXT: Called during initialisation and whenever the user switches language.
        """

        translator = self._context.translate
        self.setWindowTitle(translator("app.title", fallback=APP_NAME))

        self._file_menu.setTitle(translator("menu.file", fallback="File"))
        self._open_logs_action.setText(translator("menu.file.open_logs", fallback="Open Logs"))
        self._open_files_action.setText(translator("menu.file.open_files", fallback="Open Audio Files"))
        self._quit_action.setText(translator("menu.file.quit", fallback="Quit"))

        self._view_menu.setTitle(translator("menu.view", fallback="View"))
        self._settings_action.setText(translator("menu.view.settings", fallback="Settings"))

        self._help_menu.setTitle(translator("menu.help", fallback="Help"))
        self._about_action.setText(translator("menu.help.about", fallback="About"))

        tab_titles = [
            translator("tabs.upload", fallback="Upload"),
            translator("tabs.recording", fallback="Recording"),
            translator("tabs.queue", fallback="Queue"),
            translator("tabs.player", fallback="Player"),
        ]
        for index, title in enumerate(tab_titles):
            self._tab_widget.setTabText(index, title)

        if self.statusBar():
            self.statusBar().showMessage(translator("status.ready", fallback="Ready"))

    def _create_placeholder(self, translation_key: str) -> QWidget:
        """
        PURPOSE: Create placeholder widget for tabs before real widgets arrive.
        CONTEXT: Gives immediate visual feedback that tabs load while avoiding unimplemented UI.
        """

        placeholder = QWidget(self)
        layout = QVBoxLayout(placeholder)
        label = QLabel(
            self._context.translate(
                translation_key,
                fallback="Coming soon",
            ),
            parent=placeholder,
        )
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()
        return placeholder

    def _load_icon(self, name: str) -> QIcon:
        """
        PURPOSE: Load icons from the configured resources directory with simple caching.
        CONTEXT: Prevents repeated disk access when actions share icons.
        """

        if name in self._icons_cache:
            return self._icons_cache[name]

        candidate = ICONS_DIR / f"{name}.png"
        icon = QIcon(str(candidate)) if candidate.exists() else QIcon()
        self._icons_cache[name] = icon
        return icon

    @Slot()
    def _open_logs(self) -> None:
        """
        PURPOSE: Open application log file in the system viewer.
        CONTEXT: Provides quick access to diagnostics for users and developers.
        """

        log_path: Path = self._context.log_file()
        if not log_path.exists():
            self._logger.warning("Log file %s does not exist yet", log_path)
            QMessageBox.information(
                self,
                self._context.translate("dialog.logs.title", fallback="Log File"),
                self._context.translate("dialog.logs.missing", fallback="Log file not created yet."),
            )
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        if not opened:
            self._logger.error("Failed to open log file: %s", log_path)
            QMessageBox.warning(
                self,
                self._context.translate("dialog.logs.title", fallback="Log File"),
                self._context.translate(
                    "dialog.logs.failed",
                    fallback="Could not open the log file. Please open it manually.",
                ),
            )

    @Slot()
    def _choose_files(self) -> None:
        """
        PURPOSE: Allow selecting audio files before the upload widget is implemented.
        CONTEXT: Provides early ability to inspect file selection flow and ensures the File menu
                 remains functional during scaffold stage.
        """

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.ExistingFiles)
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

    @Slot()
    def _show_about_dialog(self) -> None:
        """
        PURPOSE: Display application metadata and diagnostics hints.
        CONTEXT: Standard part of macOS/Windows desktop UX, helps users confirm version info.
        """

        info = self._context.translate(
            "dialog.about.body",
            fallback=f"{APP_NAME}\n\nSystem audio stem separation with AI models.",
        )
        QMessageBox.about(self, self.windowTitle(), info)

    @Slot()
    def _show_settings(self) -> None:
        """
        PURPOSE: Display settings dialog.
        CONTEXT: Allows user to configure app preferences.
        """
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    @Slot()
    def _on_settings_changed(self) -> None:
        """
        PURPOSE: React to settings changes.
        CONTEXT: Some settings (like language) require UI refresh.
        """
        self._logger.info("Settings changed, refreshing UI")
        self._apply_translations()

    @Slot()
    def _on_recording_saved(self, file_path: Path) -> None:
        """
        PURPOSE: Handle recording saved signal.
        CONTEXT: Optionally queue recording for separation or switch to player tab.
        """
        self._logger.info(f"Recording saved: {file_path}")
        
        # Show notification in status bar
        if self.statusBar():
            self.statusBar().showMessage(
                f"Recording saved: {file_path.name}",
                5000
            )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """
        PURPOSE: Intercept close event for graceful shutdown.
        CONTEXT: Allows future integration of pending-task prompts while ensuring a clean exit now.
        """

        self._logger.info("Application shutdown requested")
        event.accept()

