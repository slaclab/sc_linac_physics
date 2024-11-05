import pytest
from pytestqt.qtbot import QtBot

from displays.srfhome.srf_home import SRFHome


@pytest.mark.skip(reason="This test hangs for some reason")
def test_launches(qtbot: QtBot):
    gui = SRFHome()
    qtbot.addWidget(gui)
