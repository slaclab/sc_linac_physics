import sys

import pytest
from pytestqt.qtbot import QtBot

from sc_linac_physics.displays.cavity_display.cavity_display import CavityDisplayGUI


@pytest.fixture
def display():
    yield CavityDisplayGUI()


@pytest.mark.skipif(sys.version_info[:2] == (3, 13), reason="PV connections are still being attempted in Python 3.13")
def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
