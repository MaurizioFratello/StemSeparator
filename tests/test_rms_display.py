#!/usr/bin/env python3
"""
Quick test to verify RMS meter display implementation
"""
import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QLabel,
)


def test_progress_bar_format():
    """Test that QProgressBar can display custom format text"""
    app = QApplication(sys.argv)

    window = QMainWindow()
    central = QWidget()
    layout = QVBoxLayout(central)

    # Test 1: Basic format
    pb1 = QProgressBar()
    pb1.setRange(0, 100)
    pb1.setValue(50)
    pb1.setTextVisible(True)
    pb1.setFormat("-30.0 dB")
    pb1.setMinimumHeight(30)
    layout.addWidget(QLabel("Test 1: Should show '-30.0 dB'"))
    layout.addWidget(pb1)

    # Test 2: Silence
    pb2 = QProgressBar()
    pb2.setRange(0, 100)
    pb2.setValue(0)
    pb2.setTextVisible(True)
    pb2.setFormat("Silence")
    pb2.setMinimumHeight(30)
    layout.addWidget(QLabel("Test 2: Should show 'Silence'"))
    layout.addWidget(pb2)

    # Test 3: Clipping
    pb3 = QProgressBar()
    pb3.setRange(0, 100)
    pb3.setValue(100)
    pb3.setTextVisible(True)
    pb3.setFormat("0 dB (CLIP!)")
    pb3.setMinimumHeight(30)
    pb3.setStyleSheet(
        """
        QProgressBar::chunk { background-color: #ff0000; }
        QProgressBar { color: white; font-weight: bold; }
    """
    )
    layout.addWidget(QLabel("Test 3: Should show '0 dB (CLIP!)' in red"))
    layout.addWidget(pb3)

    # Test 4: Tooltip
    label = QLabel("Level (RMS):")
    label.setToolTip(
        "Audio level meter with professional ballistics\n"
        "Range: -60 dBFS (silence) to 0 dBFS (clipping)\n"
        "Green: Normal (<-12 dB)\n"
        "Yellow: High (-12 to -3 dB)\n"
        "Red: Danger (>-3 dB - risk of clipping)"
    )
    layout.addWidget(QLabel("\nTest 4: Hover over the label below to see tooltip"))
    layout.addWidget(label)

    window.setCentralWidget(central)
    window.setWindowTitle("RMS Display Test")
    window.resize(500, 400)
    window.show()

    print("✓ Test window created successfully")
    print("✓ Check that:")
    print("  1. Progress bars show custom text (dB values)")
    print("  2. Third bar is RED with white text")
    print("  3. Tooltip appears when hovering over 'Level (RMS):' label")

    sys.exit(app.exec())


if __name__ == "__main__":
    test_progress_bar_format()
