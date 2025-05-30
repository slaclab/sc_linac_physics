from unittest.mock import patch

import pytest
from pytestqt.qtbot import QtBot

from applications.auto_setup.setup_gui import SetupGUI
from utils.qt import MockWidget


@pytest.fixture
def setup_gui():
    with patch("pydm.widgets.analog_indicator.PyDMAnalogIndicator", MockWidget):
        yield SetupGUI()


def test_launches(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
