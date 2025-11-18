"""
Loading Spinner Widget - Animated loading indicator

PURPOSE: Provide visual feedback during async operations.
CONTEXT: Modern replacement for static "Loading..." text.
"""
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

from ui.theme import ColorPalette


class LoadingSpinner(QLabel):
    """
    Animated loading spinner using Unicode characters

    WHY: Provides better UX feedback during async operations without heavy dependencies
    """

    def __init__(self, parent=None, size: int = 16):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)

        # Unicode spinner frames (various styles available)
        self.frames = [
            "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"  # Dots style
            # Alternative: ["◐", "◓", "◑", "◒"]  # Circle style
            # Alternative: ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]  # Bar style
        ]
        self.frame_idx = 0

        # Timer for animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.setInterval(80)  # 80ms per frame (faster = smoother)

        # Styling
        font = QFont("monospace", size)
        self.setFont(font)
        self.setStyleSheet(f"color: {ColorPalette.ACCENT_PRIMARY};")

        # Initial frame
        self.setText(self.frames[0])

    def start(self):
        """Start the spinner animation"""
        self.timer.start()
        self.show()

    def stop(self):
        """Stop the spinner animation"""
        self.timer.stop()
        self.hide()

    def _rotate(self):
        """Advance to next frame"""
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        self.setText(self.frames[self.frame_idx])
