#!/usr/bin/env python3
"""
Stem Separator - Main Entry Point

KI-gestützte Audio Stem Separation mit modernsten Open-Source-Modellen
"""
import sys
from pathlib import Path

# Füge Projekt-Root zum Python Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger
from utils.i18n import set_language
from core.model_manager import get_model_manager
from config import APP_NAME, APP_VERSION, DEFAULT_LANGUAGE, LOG_FILE

logger = get_logger()


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
        # Prüfe Dependencies
        if not check_dependencies():
            sys.exit(1)

        # Initialisiere App
        initialize_app()

        # Starte GUI
        from PySide6.QtWidgets import QApplication, QMessageBox

        from ui.main_window import MainWindow
        from ui.theme import ThemeManager

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)

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
            sys.exit(app.exec())
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
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
