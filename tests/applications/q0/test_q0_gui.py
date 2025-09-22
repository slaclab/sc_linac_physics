import pytest
from pytestqt.qtbot import QtBot

from sc_linac_physics.applications.q0.q0_gui import Q0GUI


@pytest.fixture
def display():
    yield Q0GUI()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
