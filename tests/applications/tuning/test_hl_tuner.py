from unittest.mock import patch

import pytest
from pytestqt.qtbot import QtBot

from applications.tuning.tuner import HLTuner


@pytest.fixture
def display():
    with patch("pydm.widgets.base.PyDMWidget.channelValueChanged", lambda x: None):
        yield HLTuner()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
