"""
Pulse Animation Widget - Pulsing indicator for recording/active states

PURPOSE: Provide visual feedback for active/recording states.
CONTEXT: Used in recording widget to show recording in progress.
"""

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt, Property
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtGui import QFont

from ui.theme import ColorPalette


class PulseAnimation(QLabel):
    """
    Pulsing text/icon indicator

    WHY: Eye-catching indicator for important states like recording
    """

    def __init__(self, text: str = "● REC", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)

        # Styling
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.setFont(font)

        # Opacity effect for pulsing
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        # Animation
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(1000)  # 1 second cycle
        self.animation.setStartValue(1.0)
        self.animation.setKeyValueAt(0.5, 0.3)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)
        self.animation.setLoopCount(-1)  # Infinite loop

        # Default color (red for recording)
        self.set_color(ColorPalette.ERROR)

    def start(self):
        """Start pulsing animation"""
        self.animation.start()
        self.show()

    def stop(self):
        """Stop pulsing animation"""
        self.animation.stop()
        self.opacity_effect.setOpacity(1.0)  # Reset to full opacity
        self.hide()

    def set_color(self, color: str):
        """Set text color"""
        self.setStyleSheet(f"color: {color}; font-weight: bold;")

    def set_text(self, text: str):
        """Update display text"""
        self.setText(text)
