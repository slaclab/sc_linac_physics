from pytestqt.qtbot import QtBot

from displays.srfhome.srf_home import SRFHome


def test_launches(qtbot: QtBot):
    gui = SRFHome()
    qtbot.addWidget(gui)
