from unittest.mock import patch

import pytest
from pytestqt.qtbot import QtBot

from sc_linac_physics.applications.tuning.tuning_gui import Tuner


@pytest.fixture
def display():
    with patch("pydm.widgets.base.PyDMWidget.channelValueChanged", lambda x: None):
        yield Tuner()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
