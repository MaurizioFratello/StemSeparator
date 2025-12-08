#!/usr/bin/env python3

"""
Stem Separator - Main Entry Point

KI-gestützte Audio Stem Separation mit modernsten Open-Source-Modellen
"""
import sys
import os
import fcntl
import atexit
import json
from pathlib import Path
from typing import Optional, Callable

# Füge Projekt-Root zum Python Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

# Add bundled FFmpeg to PATH (if running from app bundle)
# WHY: Allow app to work without requiring users to install FFmpeg via homebrew
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    bundle_dir = Path(sys._MEIPASS)
    ffmpeg_bin_dir = bundle_dir / "bin"
    if ffmpeg_bin_dir.exists():
        # Prepend to PATH so bundled FFmpeg is found first
        os.environ["PATH"] = (
            str(ffmpeg_bin_dir) + os.pathsep + os.environ.get("PATH", "")
        )

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
        _lock_file_handle = open(LOCK_FILE, "w")

        # Try to acquire exclusive lock (non-blocking)
        fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Write PID to lock file
        _lock_file_handle.write(str(os.getpid()) + "\n")
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


def check_dependencies(status_callback: Optional[Callable[[str], None]] = None):
    """
    Prüft ob alle Dependencies installiert sind

    Args:
        status_callback: Optional callback to update status messages
    """
    if status_callback:
        status_callback("Checking dependencies...")

    missing_deps = []

    try:
        import PySide6
    except ImportError:
        missing_deps.append("PySide6")

    try:
        import soundfile
    except ImportError:
        missing_deps.append("soundfile")

    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")

    if missing_deps:
        error_msg = "Missing dependencies: " + ", ".join(missing_deps)
        logger.error(error_msg)
        logger.error("Please run: pip install -r requirements.txt")
        if status_callback:
            status_callback(f"Error: {error_msg}")
        return False

    return True


def initialize_app(status_callback: Optional[Callable[[str], None]] = None):
    """
    Initialisiert die Anwendung

    Args:
        status_callback: Optional callback to update status messages
    """
    logger.info("=" * 60)
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logger.info("=" * 60)

    if status_callback:
        status_callback(f"Starting {APP_NAME} v{APP_VERSION}")

    # Setze Sprache
    if status_callback:
        status_callback("Setting language...")
    set_language(DEFAULT_LANGUAGE)
    logger.info(f"Language set to: {DEFAULT_LANGUAGE}")

    # Initialisiere Model Manager
    if status_callback:
        status_callback("Initializing Model Manager...")
    logger.info("Initializing Model Manager...")
    model_manager = get_model_manager()

    # Zeige verfügbare Modelle
    if status_callback:
        status_callback("Checking available models...")
    logger.info("Available models:")
    for model_id, model_info in model_manager.available_models.items():
        status = "✓ Downloaded" if model_info.downloaded else "✗ Not downloaded"
        logger.info(f"  - {model_info.name}: {status} ({model_info.size_mb}MB)")

    if status_callback:
        status_callback("Initialization complete")
    logger.info("Initialization complete")


def main():
    """Main Entry Point"""
    splash: Optional["SplashScreen"] = None
    app: Optional["QApplication"] = None

    # Lightweight CLI entry for separation subprocess when running as a frozen app.
    # Check both command line flag and environment variable (belt and suspenders)
    if (
        "--separation-subprocess" in sys.argv
        or os.environ.get("STEMSEPARATOR_SUBPROCESS") == "1"
    ):
        from core.separation_subprocess import run_separation_subprocess

        try:
            params = json.loads(sys.stdin.read())
            params["audio_file"] = Path(params["audio_file"])
            params["output_dir"] = Path(params["output_dir"])
            params["models_dir"] = Path(params["models_dir"])

            stems = run_separation_subprocess(**params)
            result = {"success": True, "stems": stems, "error": None}
            print(json.dumps(result))
            sys.exit(0)
        except Exception as e:
            result = {"success": False, "stems": {}, "error": str(e)}
            print(json.dumps(result))
            sys.exit(1)

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
                "Please close the existing instance before starting a new one.",
            )
            sys.exit(1)

        # Create QApplication early for splash screen
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtGui import QIcon
        from ui.splash_screen import SplashScreen
        from config import ICONS_DIR

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationDisplayName(APP_NAME)  # macOS menu bar & fullscreen title
        app.setApplicationVersion(APP_VERSION)

        # Create and show splash screen
        icon_path = ICONS_DIR / "app_icon_1024.png"
        splash = SplashScreen(icon_path)
        splash.show()
        splash.raise_()
        splash.activateWindow()

        # Process events multiple times to ensure splash is fully rendered
        for _ in range(5):
            app.processEvents()

        # Small delay to ensure splash is visible before starting initialization
        import time

        time.sleep(0.15)

        # Status callback for splash screen
        def update_status(message: str):
            if splash:
                splash.update_status(message)
            app.processEvents()  # Keep UI responsive

        # Prüfe Dependencies
        if not check_dependencies(status_callback=update_status):
            if splash:
                splash.update_status("Error: Missing dependencies")
                app.processEvents()
                import time

                time.sleep(2)  # Show error message briefly
            release_lock()
            sys.exit(1)

        # Initialisiere App
        initialize_app(status_callback=update_status)
        app.processEvents()

        # Set application icon (for Dock, menu bar, etc.)
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            logger.info(f"Application icon set: {icon_path}")
            update_status("Application icon set")
        else:
            logger.warning(f"Icon not found: {icon_path}")

        # Apply theme at application level for consistent styling
        try:
            update_status("Applying theme...")
            from ui.theme import ThemeManager

            theme_manager = ThemeManager.instance()
            theme_manager.apply_to_app(app)
            logger.info("Application theme applied successfully")
            update_status("Theme applied")
        except Exception as theme_error:
            logger.warning(
                f"Failed to apply theme: {theme_error}. Using default Qt theme."
            )
            update_status("Using default theme")

        # Start BeatNet warm-up in background (after QApplication is ready, before window shown)
        # WHY: Pre-approve binary with XProtect silently in background, user won't notice
        from utils.beatnet_warmup import warmup_beatnet_async

        warmup_beatnet_async()

        # Create main window
        update_status("Loading main window...")
        from ui.main_window import MainWindow

        window = MainWindow()
        app.processEvents()

        # Show main window
        window.show()
        app.processEvents()

        # Close splash screen after main window is ready
        if splash:
            splash.finish(window)
            splash = None

        exit_code = app.exec()
        release_lock()  # Release lock before exit
        sys.exit(exit_code)

    except Exception as gui_error:  # pragma: no cover - GUI bootstrap failure is fatal
        logger.critical(
            f"Failed to start GUI: {gui_error}",
            exc_info=True,
        )

        # Show error in splash if still visible
        if splash and app:
            splash.update_status(f"Error: {str(gui_error)}")
            app.processEvents()
            import time

            time.sleep(2)
            splash.close()

        if app:
            QMessageBox.critical(
                None,
                "Application Error",
                f"Unable to start the GUI.\n\nDetails: {gui_error}\nSee log file: {LOG_FILE}",
            )
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
        if splash:
            splash.close()
        release_lock()
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        if splash:
            splash.close()
        release_lock()
        sys.exit(1)
    finally:
        # Ensure splash is closed
        if splash:
            splash.close()


if __name__ == "__main__":
    main()
