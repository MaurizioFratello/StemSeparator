"""Player page navigation tests."""

import pytest

from ui.widgets.player_widget import PlayerWidget


@pytest.fixture
def player_widget(qtbot, reset_singletons):
    widget = PlayerWidget()
    qtbot.addWidget(widget)
    return widget


def test_player_widget_exposes_three_sidebar_pages(player_widget):
    assert player_widget._page_stack.count() == 3
    assert player_widget._page_stack.objectName() == "playerPages"


def test_player_widget_starts_on_stems_page(player_widget):
    assert player_widget.get_current_page() == 0
    assert player_widget._page_stack.currentWidget() is player_widget.stems_page


@pytest.mark.parametrize(
    ("page", "expected_widget"),
    [(0, "stems_page"), (1, "playback_page"), (2, "looping_page")],
)
def test_sidebar_page_navigation_selects_requested_page(
    player_widget, page, expected_widget
):
    player_widget.set_page(page)

    assert player_widget.get_current_page() == page
    assert player_widget._page_stack.currentWidget() is getattr(player_widget, expected_widget)


@pytest.mark.parametrize("invalid_page", [-1, 3])
def test_sidebar_page_navigation_ignores_invalid_page(player_widget, invalid_page):
    initial_page = player_widget.get_current_page()

    player_widget.set_page(invalid_page)

    assert player_widget.get_current_page() == initial_page
