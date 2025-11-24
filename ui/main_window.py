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
from ui.theme.macos_effects import MacOSEffects
from ui.theme.macos_dialogs import MacOSDialogs


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
                 Includes macOS-specific window management and visual effects.
        """

        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)  # Larger default size for modern displays

        # macOS-specific window configuration
        if platform.system() == "Darwin":
            # Enable native full-screen button
            self.setWindowFlag(Qt.WindowFullscreenButtonHint, True)

            # Set minimum size to prevent tiny windows
            self.setMinimumSize(1000, 700)

            # Center window on screen (macOS convention)
            self._center_on_screen()

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

        # Apply macOS vibrancy effects to tab bar (on macOS only)
        if platform.system() == "Darwin":
            MacOSEffects.apply_toolbar_effect(self._tab_widget.tabBar(), dark=True)

    def _center_on_screen(self) -> None:
        """
        Center window on primary screen

        WHY: macOS convention - apps should launch centered, not in arbitrary positions
        """
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
            # Fail gracefully if screen detection doesn't work
            pass

    def _setup_menu(self) -> None:
        """
        PURPOSE: Build menu bar with placeholders for file/view/help actions.
        CONTEXT: Menus expose core diagnostics (logs), localisation, and about dialogs from the
                 outset to keep workflow consistent as widgets arrive.
                 Includes macOS-specific native menu bar and standard menus.
        """

        menubar = self.menuBar()

        # Enable native macOS menu bar (appears in system menu bar, not in-window)
        if platform.system() == "Darwin":
            menubar.setNativeMenuBar(True)

        # File menu
        self._file_menu = menubar.addMenu("")  # Populated in _apply_translations.
        self._open_files_action = QAction(self._load_icon("folder-open"), "", self)
        self._file_menu.addAction(self._open_files_action)

        self._file_menu.addSeparator()

        # macOS-specific: Close Window (Cmd+W)
        if platform.system() == "Darwin":
            self._close_window_action = QAction("Close Window", self)
            self._close_window_action.setShortcut(QKeySequence("Ctrl+W"))  # Ctrl = Cmd on Mac
            self._file_menu.addAction(self._close_window_action)

            # Minimize (Cmd+M)
            self._minimize_action = QAction("Minimize", self)
            self._minimize_action.setShortcut(QKeySequence("Ctrl+M"))
            self._file_menu.addAction(self._minimize_action)

            self._file_menu.addSeparator()

        self._quit_action = QAction(self._load_icon("application-exit"), "", self)
        self._quit_action.setShortcut(QKeySequence.Quit)  # Cmd+Q on Mac, Ctrl+Q on others
        self._file_menu.addAction(self._quit_action)

        # Edit menu (standard macOS menu)
        if platform.system() == "Darwin":
            self._setup_edit_menu(menubar)

        # View menu
        self._view_menu = menubar.addMenu("")
        self._settings_action = QAction(self._load_icon("preferences-system"), "", self)
        # macOS convention: Settings shortcut is Cmd+,
        if platform.system() == "Darwin":
            self._settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self._view_menu.addAction(self._settings_action)

        # Help menu
        self._help_menu = menubar.addMenu("")
        self._about_action = QAction(self._load_icon("help-about"), "", self)
        self._help_menu.addAction(self._about_action)

    def _setup_edit_menu(self, menubar) -> None:
        """
        Setup standard Edit menu (macOS convention)

        WHY: macOS apps are expected to have an Edit menu with Undo/Redo/Cut/Copy/Paste
              even if some actions aren't fully implemented yet
        """
        self._edit_menu = menubar.addMenu("Edit")

        # Undo
        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.Undo)
        self._undo_action.setEnabled(False)  # Disabled for now
        self._edit_menu.addAction(self._undo_action)

        # Redo
        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.Redo)
        self._redo_action.setEnabled(False)  # Disabled for now
        self._edit_menu.addAction(self._redo_action)

        self._edit_menu.addSeparator()

        # Cut
        self._cut_action = QAction("Cut", self)
        self._cut_action.setShortcut(QKeySequence.Cut)
        self._cut_action.setEnabled(False)  # Disabled for now
        self._edit_menu.addAction(self._cut_action)

        # Copy
        self._copy_action = QAction("Copy", self)
        self._copy_action.setShortcut(QKeySequence.Copy)
        self._copy_action.setEnabled(False)  # Disabled for now
        self._edit_menu.addAction(self._copy_action)

        # Paste
        self._paste_action = QAction("Paste", self)
        self._paste_action.setShortcut(QKeySequence.Paste)
        self._paste_action.setEnabled(False)  # Disabled for now
        self._edit_menu.addAction(self._paste_action)

        self._edit_menu.addSeparator()

        # Select All
        self._select_all_action = QAction("Select All", self)
        self._select_all_action.setShortcut(QKeySequence.SelectAll)
        self._select_all_action.setEnabled(False)  # Disabled for now
        self._edit_menu.addAction(self._select_all_action)

    def _setup_toolbar(self) -> None:
        """
        PURPOSE: Provide a main toolbar with quick-access actions.
        CONTEXT: Toolbar mirrors menu entries to streamline future UX polish.
                 macOS-optimized with standard icon sizes and styling.
        """

        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))  # Standard macOS toolbar icon size
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # macOS-specific toolbar styling
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

        # Add key actions to toolbar
        toolbar.addAction(self._open_files_action)
        toolbar.addSeparator()
        toolbar.addAction(self._settings_action)

        # Add spacer to push help to the right (macOS convention)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar.addWidget(spacer)

        toolbar.addAction(self._about_action)

        self.addToolBar(Qt.TopToolBarArea, toolbar)

    def _connect_actions(self) -> None:
        """
        PURPOSE: Wire UI actions to their respective slots.
        CONTEXT: Keeps behaviour declarative and simplifies unit testing by isolating slot logic.
                 Includes macOS-specific action connections.
        """

        self._open_files_action.triggered.connect(self._choose_files)
        self._quit_action.triggered.connect(QApplication.instance().quit)
        self._settings_action.triggered.connect(self._show_settings)
        self._about_action.triggered.connect(self._show_about_dialog)

        # macOS-specific actions
        if platform.system() == "Darwin":
            self._close_window_action.triggered.connect(self.close)
            self._minimize_action.triggered.connect(self.showMinimized)

    def _apply_translations(self) -> None:
        """
        PURPOSE: Refresh all text labels using the translation system.
        CONTEXT: Called during initialisation and whenever the user switches language.
        """

        translator = self._context.translate
        self.setWindowTitle(translator("app.title", fallback=APP_NAME))

        self._file_menu.setTitle(translator("menu.file", fallback="File"))
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
    def _choose_files(self) -> None:
        """
        PURPOSE: Allow selecting audio files using native file dialog.
        CONTEXT: Provides early ability to inspect file selection flow and ensures the File menu
                 remains functional during scaffold stage.
                 Uses native macOS file dialog for better integration.
        """

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.ExistingFiles)

        # Use native macOS file dialog (CRITICAL for native feel)
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

    @Slot()
    def _show_about_dialog(self) -> None:
        """
        PURPOSE: Display application metadata and diagnostics hints.
        CONTEXT: Standard part of macOS/Windows desktop UX, helps users confirm version info.
                 Uses macOS-styled dialogs for native appearance.
        """

        info = self._context.translate(
            "dialog.about.body",
            fallback=f"{APP_NAME}\n\nSystem audio stem separation with AI models.",
        )
        MacOSDialogs.about(self, self.windowTitle(), info)

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
        CONTEXT: Shows notification when recording is saved.
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
                 On macOS, window close (Cmd+W or red button) hides the window but keeps app running.
                 Cmd+Q properly quits via the quit action.
        """

        self._logger.info("Close event received")

        # macOS convention: closing window (Cmd+W) should minimize to dock, not quit
        # The app continues running and can be reopened from dock or Cmd+Tab
        if platform.system() == "Darwin" and not event.spontaneous():
            # Non-spontaneous events are programmatic closes (like from quit action)
            # These should be allowed to close normally
            self._logger.info("Application shutdown requested (programmatic)")
            event.accept()
        elif platform.system() == "Darwin":
            # Spontaneous close events (user clicking close or Cmd+W) should hide
            self._logger.info("Window close requested - hiding window (macOS convention)")
            event.ignore()
            self.hide()
        else:
            # On Windows/Linux, close means quit the application
            self._logger.info("Application shutdown requested")
            event.accept()

