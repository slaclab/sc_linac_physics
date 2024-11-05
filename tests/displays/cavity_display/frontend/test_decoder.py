from unittest.mock import patch

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSizePolicy, QAbstractScrollArea
from pytestqt.qtbot import QtBot

from displays.cavity_display.frontend.fault_decoder_display import (
    DecoderDisplay,
)

TEST_ACTION = "Test Action"
TEST_SHORT_DESC = "Test Short"
TEST_LONG_DESC = "Test Description"
TEST_TLC = "ABC"
TEST_TLC_2 = "XYZ"


def mock_parse():
    return [
        {
            "Three Letter Code": TEST_TLC,
            "Long Description": TEST_LONG_DESC,
            "Generic Short Description for Decoder": TEST_SHORT_DESC,
            "Recommended Corrective Actions": TEST_ACTION,
        },
        {
            "Three Letter Code": TEST_TLC_2,
            "Long Description": TEST_LONG_DESC,
            "Generic Short Description for Decoder": TEST_SHORT_DESC,
            "Recommended Corrective Actions": TEST_ACTION,
        },
    ]


@pytest.fixture
def display():
    with patch("displays.cavity_display.utils.utils.parse_csv", mock_parse):
        yield DecoderDisplay()


def test_initialization(qtbot: QtBot, display):
    """Testing basic setup stuff, .i.e window and main components exists
    Does our window have the right title and components?"""
    qtbot.addWidget(display)

    assert display.windowTitle() == "Three Letter Codes"
    assert display.scroll_area is not None
    assert display.groupbox is not None


def test_layout_creation(qtbot: QtBot, display):
    """Checking if our layout structure is right, esp for header"""
    qtbot.addWidget(display)
    scroll_area_layout = display.groupbox.layout()
    assert scroll_area_layout is not None

    # Want to make sure our header has all the right column titles
    header_layout = scroll_area_layout.itemAt(0).layout()
    assert header_layout is not None
    assert header_layout.count() == 4
    assert header_layout.itemAt(0).widget().text() == "Code"
    assert header_layout.itemAt(1).widget().text() == "Name"
    assert header_layout.itemAt(2).widget().text() == "Description"
    assert header_layout.itemAt(3).widget().text() == "Corrective Action"


def test_scroll_area_configuration(qtbot: QtBot, display):
    """Making sure our scroll area behaves right"""
    qtbot.addWidget(display)
    # Test all scroll area properties
    # Vertical scrollbar should always be visible
    assert display.scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn
    # Content should resize with the window
    assert display.scroll_area.widgetResizable()
    # Scroll area should adjust to show all the content
    assert (
        display.scroll_area.sizeAdjustPolicy() == QAbstractScrollArea.AdjustToContents
    )


def test_visual_properties(qtbot: QtBot, display):
    qtbot.addWidget(display)

    scroll_area_layout = display.groupbox.layout()

    # Test header styling and properties
    header_layout = scroll_area_layout.itemAt(0).layout()
    header_properties = {
        0: ("Code", 30, 30, QSizePolicy.Preferred),
        1: ("Name", 100, 30, QSizePolicy.Preferred),
        2: ("Description", 100, 30, QSizePolicy.Minimum),
        3: ("Corrective Action", 100, 30, QSizePolicy.Minimum),
    }

    for idx, (
        text,
        min_width,
        min_height,
        size_policy,
    ) in header_properties.items():
        label = header_layout.itemAt(idx).widget()
        # Every header should be underlined & sized right
        assert label.styleSheet() == "text-decoration: underline"
        assert label.minimumSize().width() == min_width
        assert label.minimumSize().height() == min_height
        assert label.sizePolicy().horizontalPolicy() == size_policy
        assert label.sizePolicy().verticalPolicy() == QSizePolicy.Preferred

    # Checking actual data row properties
    row_layout = scroll_area_layout.itemAt(1).layout()

    # Test description label
    description_label = row_layout.itemAt(2).widget()
    assert description_label.wordWrap()
    assert description_label.minimumSize().width() == 100
    assert description_label.minimumSize().height() == 50
    assert description_label.sizePolicy().horizontalPolicy() == QSizePolicy.Minimum
    assert description_label.sizePolicy().verticalPolicy() == QSizePolicy.Minimum

    # Same for action
    action_label = row_layout.itemAt(3).widget()
    assert action_label.wordWrap()
    assert action_label.minimumSize().width() == 100
    assert action_label.minimumSize().height() == 50
    assert action_label.sizePolicy().horizontalPolicy() == QSizePolicy.Minimum
    assert action_label.sizePolicy().verticalPolicy() == QSizePolicy.Minimum


def verify_layout_structure(layout, expected_count):
    """Helper method to verify layout structure"""
    assert layout is not None
    actual_count = layout.count()
    # This makes our test failures better by showing what we expected vs what we got
    assert actual_count == expected_count


def test_row_creation(qtbot: QtBot, display):
    """Testing if 1 row of data gets displayed right (does the data show up)"""
    qtbot.addWidget(display)

    scroll_area_layout = display.groupbox.layout()
    # Header + 1 row
    verify_layout_structure(scroll_area_layout, 3)
    # Row details
    row_item = scroll_area_layout.itemAt(1)
    # Make sure all our data fields show up in the right order
    row_layout = row_item.layout()
    assert row_layout is not None
    assert row_layout.count() == 4
    assert row_layout.itemAt(0).widget().text().strip() == TEST_TLC
    assert row_layout.itemAt(1).widget().text().strip() == TEST_SHORT_DESC
    assert row_layout.itemAt(2).widget().text().strip() == TEST_LONG_DESC
    assert row_layout.itemAt(3).widget().text().strip() == TEST_ACTION

    row2_layout = scroll_area_layout.itemAt(2).layout()
    assert row2_layout.itemAt(0).widget().text().strip() == TEST_TLC_2
