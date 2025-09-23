from typing import List
from unittest.mock import patch

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QSizePolicy,
    QAbstractScrollArea,
    QLayout,
    QHBoxLayout,
)
from pytestqt.qtbot import QtBot

from sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display import DecoderDisplay, Row
from tests.displays.cavity_display.test_utils.utils import mock_parse


@pytest.fixture
def display():
    with patch("sc_linac_physics.displays.cavity_display.utils.utils.parse_csv", mock_parse):
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
    assert display.scroll_area.sizeAdjustPolicy() == QAbstractScrollArea.AdjustToContents


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


def test_header(qtbot: QtBot, display):
    qtbot.addWidget(display)
    scroll_area_layout: QLayout = display.groupbox.layout()

    header_row_layout: QHBoxLayout = scroll_area_layout.itemAt(0).layout()
    keys = []
    for col_num in range(header_row_layout.count()):
        keys.append(header_row_layout.itemAt(col_num).widget().text().strip())

    assert keys == ["Code", "Name", "Description", "Corrective Action"]


def test_content(qtbot: QtBot, display):
    """Testing if 1 row of data gets displayed right (does the data show up)"""
    qtbot.addWidget(display)

    scroll_area_layout: QLayout = display.groupbox.layout()
    # Header + rows
    row_data: List[Row] = []
    for fault_row_dict in mock_parse():
        row_data.append(
            Row(
                tlc=fault_row_dict["Three Letter Code"],
                long_desc=fault_row_dict["Long Description"],
                gen_short_desc=fault_row_dict["Generic Short Description for Decoder"],
                corrective_action=fault_row_dict["Recommended Corrective Actions"],
            )
        )

    row_data = sorted(row_data)

    verify_layout_structure(scroll_area_layout, len(row_data) + 1)

    for data_index, row in enumerate(row_data):
        row_num = data_index + 1
        # Row details
        row_item = scroll_area_layout.itemAt(row_num)
        # Make sure all our data fields show up in the right order
        row_layout = row_item.layout()
        assert row_layout is not None
        assert row_layout.count() == 4

        for col_index, col_name in enumerate(
            [
                "tlc",
                "gen_short_desc",
                "long_desc",
                "corrective_action",
            ]
        ):

            row_widget = row_layout.itemAt(col_index).widget()
            assert row_widget.text() == row.__dict__[col_name]
