"""
Test main window structure and sidebar configuration.
"""

import pytest
from PySide6.QtWidgets import QFrame, QPushButton, QLabel, QStackedWidget
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def test_sidebar_navigation_buttons_select_existing_content(qapp, reset_singletons):
    """Each sidebar control exposes a reachable page in the content stack."""
    window = MainWindow()

    sidebar = window.findChild(QFrame, "sidebar")
    assert sidebar is not None
    assert sidebar.width() == 220

    buttons = sidebar.findChildren(QPushButton, "sidebar_button")
    assert buttons

    for button in buttons:
        button.click()
        assert window._content_stack.currentWidget() is not None




def test_sidebar_style_selectors_target_navigation_elements(qapp, reset_singletons):
    """Sidebar styling identifiers distinguish headers from interactive controls."""
    window = MainWindow()
    sidebar = window.findChild(QFrame, "sidebar")

    headers = sidebar.findChildren(QLabel, "sidebar_header")
    buttons = sidebar.findChildren(QPushButton, "sidebar_button")

    assert headers
    assert buttons
    assert not set(headers) & set(buttons)
