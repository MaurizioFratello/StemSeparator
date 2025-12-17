"""
Common UI Widgets - Shared components used across multiple widgets

PURPOSE: Reduce code duplication by providing reusable UI components
CONTEXT: Extracted from upload_widget.py and player_widget.py
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QListWidget
from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent


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
