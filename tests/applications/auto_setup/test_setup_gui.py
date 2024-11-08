import pytest
from pytestqt.qtbot import QtBot

from applications.auto_setup.setup_gui import SetupGUI


@pytest.fixture
def setup_gui():
    yield SetupGUI()


def test_launches(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
