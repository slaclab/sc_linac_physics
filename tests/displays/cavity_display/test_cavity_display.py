import pytest
from pytestqt.qtbot import QtBot

from displays.cavity_display.cavity_display import CavityDisplayGUI


@pytest.fixture
def display():
    yield CavityDisplayGUI()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
