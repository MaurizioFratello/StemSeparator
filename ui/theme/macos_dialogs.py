"""
macOS-styled dialogs and message boxes

PURPOSE: Provide native-feeling dialogs that match macOS design language
CONTEXT: Qt's default dialogs look generic; this module applies macOS-specific styling
"""
from __future__ import annotations

import platform
from typing import Optional

from PySide6.QtWidgets import QMessageBox, QWidget
from PySide6.QtCore import Qt


class MacOSDialogs:
    """
    Utility class for creating macOS-styled dialogs

    WHY: Qt's default dialogs don't match macOS appearance
         This provides consistent, native-looking dialogs across the app
    """

    # macOS dialog styling (Big Sur / Monterey / Ventura style)
    DIALOG_STYLESHEET = """
        QMessageBox {
            background-color: rgba(40, 40, 45, 0.95);
            border-radius: 12px;
            font-family: -apple-system, 'SF Pro Text', system-ui;
            font-size: 13px;
        }

        QMessageBox QLabel {
            color: rgba(255, 255, 255, 0.9);
            font-size: 13px;
            padding: 8px;
            background: transparent;
        }

        QMessageBox QPushButton {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(0, 122, 255, 1.0),
                stop:1 rgba(0, 110, 240, 1.0)
            );
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-size: 13px;
            font-weight: 500;
            min-width: 80px;
            min-height: 28px;
        }

        QMessageBox QPushButton:hover {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(10, 132, 255, 1.0),
                stop:1 rgba(10, 120, 250, 1.0)
            );
        }

        QMessageBox QPushButton:pressed {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(0, 100, 220, 1.0),
                stop:1 rgba(0, 90, 210, 1.0)
            );
        }

        QMessageBox QPushButton[text="Cancel"],
        QMessageBox QPushButton[text="No"] {
            background: rgba(60, 60, 67, 0.8);
            color: rgba(255, 255, 255, 0.85);
        }

        QMessageBox QPushButton[text="Cancel"]:hover,
        QMessageBox QPushButton[text="No"]:hover {
            background: rgba(70, 70, 77, 0.9);
        }
    """

    @classmethod
    def is_macos(cls) -> bool:
        """Check if running on macOS"""
        return platform.system() == "Darwin"

    @classmethod
    def apply_dialog_style(cls, dialog: QMessageBox) -> None:
        """
        Apply macOS styling to a message box

        Args:
            dialog: QMessageBox to style

        WHY: Consistent native appearance across all dialogs
        """
        if not cls.is_macos():
            return

        try:
            dialog.setStyleSheet(cls.DIALOG_STYLESHEET)

            # Set window flags for sheet-like appearance
            dialog.setWindowFlags(
                Qt.Dialog |
                Qt.CustomizeWindowHint |
                Qt.WindowTitleHint |
                Qt.WindowCloseButtonHint
            )

        except Exception as e:
            # Graceful degradation - use default Qt styling
            pass

    @classmethod
    def information(
        cls,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.Ok,
        default_button: QMessageBox.StandardButton = QMessageBox.Ok
    ) -> QMessageBox.StandardButton:
        """
        Show macOS-styled information dialog

        Args:
            parent: Parent widget
            title: Dialog title
            text: Message text
            buttons: Standard buttons to show
            default_button: Default button

        Returns:
            Button that was clicked
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Information)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(default_button)

        cls.apply_dialog_style(dialog)

        return dialog.exec()

    @classmethod
    def warning(
        cls,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.Ok,
        default_button: QMessageBox.StandardButton = QMessageBox.Ok
    ) -> QMessageBox.StandardButton:
        """
        Show macOS-styled warning dialog

        Args:
            parent: Parent widget
            title: Dialog title
            text: Message text
            buttons: Standard buttons to show
            default_button: Default button

        Returns:
            Button that was clicked
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(default_button)

        cls.apply_dialog_style(dialog)

        return dialog.exec()

    @classmethod
    def question(
        cls,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.Yes | QMessageBox.No,
        default_button: QMessageBox.StandardButton = QMessageBox.No
    ) -> QMessageBox.StandardButton:
        """
        Show macOS-styled question dialog

        Args:
            parent: Parent widget
            title: Dialog title
            text: Message text
            buttons: Standard buttons to show
            default_button: Default button

        Returns:
            Button that was clicked
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(default_button)

        cls.apply_dialog_style(dialog)

        return dialog.exec()

    @classmethod
    def critical(
        cls,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.Ok,
        default_button: QMessageBox.StandardButton = QMessageBox.Ok
    ) -> QMessageBox.StandardButton:
        """
        Show macOS-styled critical error dialog

        Args:
            parent: Parent widget
            title: Dialog title
            text: Message text
            buttons: Standard buttons to show
            default_button: Default button

        Returns:
            Button that was clicked
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(default_button)

        cls.apply_dialog_style(dialog)

        return dialog.exec()

    @classmethod
    def about(
        cls,
        parent: Optional[QWidget],
        title: str,
        text: str
    ) -> None:
        """
        Show macOS-styled about dialog

        Args:
            parent: Parent widget
            title: Dialog title
            text: About text
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Information)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setStandardButtons(QMessageBox.Ok)

        cls.apply_dialog_style(dialog)

        dialog.exec()


def get_macos_dialogs() -> type[MacOSDialogs]:
    """
    Convenience function to get MacOSDialogs class

    Returns:
        MacOSDialogs class
    """
    return MacOSDialogs
