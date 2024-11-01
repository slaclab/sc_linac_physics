from unittest.mock import MagicMock

import pytest
from pydm import Display
from pytestqt.qtbot import QtBot

from displays.cavity_display.frontend.gui_cavity import GUICavity


def mock_ssa_class(**kwargs) -> MagicMock:
    ssa = MagicMock()
    ssa.status_pv = "MOCK:SSA:STATUS:PV"
    return ssa


@pytest.fixture
def gui_cavity() -> GUICavity:
    rack = MagicMock()
    rack.ssa_class = mock_ssa_class
    return GUICavity(1, rack)


def test_populate_fault_display(qtbot: QtBot, gui_cavity):
    gui_cavity.populate_fault_display()


def test_show_fault_display(qtbot: QtBot, gui_cavity):
    gui_cavity.show_fault_display()
    assert gui_cavity._fault_display is not None


def test_fault_display_already_exists(qtbot: QtBot, gui_cavity):
    gui_cavity._fault_display = MagicMock()
    assert gui_cavity.fault_display == gui_cavity._fault_display


def test_fault_display(qtbot: QtBot, gui_cavity):
    gui_cavity.populate_fault_display = MagicMock()
    fault_display = gui_cavity.fault_display
    gui_cavity.populate_fault_display.assert_called()
    assert isinstance(fault_display, Display)
