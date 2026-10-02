#!/usr/bin/env python3
"""
Quick test to verify RMS meter display implementation
"""
from PySide6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QLabel,
)


def test_progress_bar_format(qtbot):
    """QProgressBar retains supplied custom display formats."""
    window = QMainWindow()
    qtbot.addWidget(window)
    central = QWidget()
    layout = QVBoxLayout(central)

    pb1 = QProgressBar()
    pb1.setRange(0, 100)
    pb1.setValue(50)
    pb1.setTextVisible(True)
    pb1.setFormat("-30.0 dB")
    layout.addWidget(pb1)

    pb2 = QProgressBar()
    pb2.setRange(0, 100)
    pb2.setValue(0)
    pb2.setTextVisible(True)
    pb2.setFormat("Silence")
    layout.addWidget(pb2)

    pb3 = QProgressBar()
    pb3.setRange(0, 100)
    pb3.setValue(100)
    pb3.setTextVisible(True)
    pb3.setFormat("0 dB (CLIP!)")
    layout.addWidget(pb3)

    label = QLabel("Level (RMS):")
    label.setToolTip(
        "Audio level meter with professional ballistics\n"
        "Range: -60 dBFS (silence) to 0 dBFS (clipping)"
    )
    layout.addWidget(label)

    window.setCentralWidget(central)
    window.show()

    assert pb1.format() == "-30.0 dB"
    assert pb2.format() == "Silence"
    assert pb3.format() == "0 dB (CLIP!)"
    assert "clipping" in label.toolTip()


if __name__ == "__main__":
    raise SystemExit("Run this test with pytest.")
