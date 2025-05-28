import pytest
from pytestqt.qtbot import QtBot

from applications.tuning.tuner import HLTuner


@pytest.fixture
def display():
    yield HLTuner()


def test_launches(qtbot: QtBot, display):
    qtbot.addWidget(display)
