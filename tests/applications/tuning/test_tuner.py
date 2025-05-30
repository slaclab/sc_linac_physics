from unittest.mock import patch

import pytest
from pytestqt.qtbot import QtBot

from applications.tuning.tuner import Tuner


@pytest.fixture
def display():
    with patch("pydm.widgets.base.PyDMWidget.channelValueChanged", lambda x: None):
        yield Tuner()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
