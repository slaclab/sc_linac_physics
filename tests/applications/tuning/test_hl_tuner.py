from unittest.mock import patch

import pytest
from pytestqt.qtbot import QtBot

from applications.tuning.tuner import HLTuner
from utils.qt import MockWidget


@pytest.fixture
def display():
    with patch("pydm.widgets.spinbox.PyDMSpinbox", MockWidget):
        yield HLTuner()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
