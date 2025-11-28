#!/usr/bin/env python3
"""
Stem Separator - Main Entry Point

KI-gestützte Audio Stem Separation mit modernsten Open-Source-Modellen
"""
import sys
import os
import fcntl
import atexit
from pathlib import Path

# Füge Projekt-Root zum Python Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger
from utils.i18n import set_language
from core.model_manager import get_model_manager
from config import APP_NAME, APP_VERSION, DEFAULT_LANGUAGE, LOG_FILE, USER_DIR

logger = get_logger()

# Single-instance lock file
LOCK_FILE = USER_DIR / ".stemseparator.lock"
_lock_file_handle = None


def acquire_lock():
    """
    Acquire single-instance lock
    
    WHY: Prevent multiple app instances from running simultaneously,
    which causes resource conflicts and infinite loop behavior.
    """
    global _lock_file_handle
    
    try:
        # Create lock file directory if needed
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Try to open lock file in exclusive mode
        _lock_file_handle = open(LOCK_FILE, 'w')
        
        # Try to acquire exclusive lock (non-blocking)
        fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Write PID to lock file
        _lock_file_handle.write(str(os.getpid()) + '\n')
        _lock_file_handle.flush()
        
        # Register cleanup function
        atexit.register(release_lock)
        
        logger.info(f"Single-instance lock acquired: {LOCK_FILE}")
        return True
        
    except (IOError, OSError) as e:
        # Lock file is locked by another instance
        if _lock_file_handle:
            _lock_file_handle.close()
            _lock_file_handle = None
        
        logger.warning(f"Another instance is already running (lock: {LOCK_FILE})")
        return False


def release_lock():
    """Release single-instance lock"""
    global _lock_file_handle
    
    if _lock_file_handle:
        try:
            fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_UN)
            _lock_file_handle.close()
            _lock_file_handle = None
            
            # Remove lock file
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
            
            logger.info("Single-instance lock released")
        except Exception as e:
            logger.warning(f"Error releasing lock: {e}")


# Import os after path setup
import os


def check_dependencies():
    """Prüft ob alle Dependencies installiert sind"""
    missing_deps = []

    try:
        import PySide6
    except ImportError:
        missing_deps.append('PySide6')

    try:
        import soundfile
    except ImportError:
        missing_deps.append('soundfile')

    try:
        import numpy
    except ImportError:
        missing_deps.append('numpy')

    if missing_deps:
        logger.error("Missing dependencies: " + ", ".join(missing_deps))
        logger.error("Please run: pip install -r requirements.txt")
        return False

    return True


def initialize_app():
    """Initialisiert die Anwendung"""
    logger.info("=" * 60)
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logger.info("=" * 60)

    # Setze Sprache
    set_language(DEFAULT_LANGUAGE)
    logger.info(f"Language set to: {DEFAULT_LANGUAGE}")

    # Initialisiere Model Manager
    logger.info("Initializing Model Manager...")
    model_manager = get_model_manager()

    # Zeige verfügbare Modelle
    logger.info("Available models:")
    for model_id, model_info in model_manager.available_models.items():
        status = "✓ Downloaded" if model_info.downloaded else "✗ Not downloaded"
        logger.info(f"  - {model_info.name}: {status} ({model_info.size_mb}MB)")

    logger.info("Initialization complete")


def main():
    """Main Entry Point"""
    try:
        # CRITICAL: Check for single instance (prevent multiple app instances)
        if not acquire_lock():
            from PySide6.QtWidgets import QApplication, QMessageBox
            
            # Create minimal QApplication for message box
            app = QApplication(sys.argv)
            QMessageBox.warning(
                None,
                "Already Running",
                f"{APP_NAME} is already running.\n\n"
                "Please close the existing instance before starting a new one."
            )
            sys.exit(1)
        
        # Prüfe Dependencies
        if not check_dependencies():
            release_lock()
            sys.exit(1)

        # Initialisiere App
        initialize_app()

        # Starte GUI
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtGui import QIcon

        from ui.main_window import MainWindow
        from ui.theme import ThemeManager
        from config import ICONS_DIR

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationDisplayName(APP_NAME)  # macOS menu bar & fullscreen title
        app.setApplicationVersion(APP_VERSION)
        
        # Set application icon (for Dock, menu bar, etc.)
        icon_path = ICONS_DIR / "app_icon_1024.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            logger.info(f"Application icon set: {icon_path}")
        else:
            logger.warning(f"Icon not found: {icon_path}")

        # Apply theme at application level for consistent styling
        try:
            theme_manager = ThemeManager.instance()
            theme_manager.apply_to_app(app)
            logger.info("Application theme applied successfully")
        except Exception as theme_error:
            logger.warning(f"Failed to apply theme: {theme_error}. Using default Qt theme.")

        try:
            window = MainWindow()
            window.show()
            exit_code = app.exec()
            release_lock()  # Release lock before exit
            sys.exit(exit_code)
        except Exception as gui_error:  # pragma: no cover - GUI bootstrap failure is fatal
            logger.critical(
                f"Failed to start GUI: {gui_error}",
                exc_info=True,
            )
            QMessageBox.critical(
                None,
                "Application Error",
                f"Unable to start the GUI.\n\nDetails: {gui_error}\nSee log file: {LOG_FILE}",
            )
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
        release_lock()
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        release_lock()
        sys.exit(1)


if __name__ == "__main__":
    main()
