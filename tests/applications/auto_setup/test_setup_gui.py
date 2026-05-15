from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from pydm.widgets.analog_indicator import PyDMAnalogIndicator
from pytestqt.qtbot import QtBot

from sc_linac_physics.applications.auto_setup.setup_gui import SetupGUI

SETUP_MACHINE = MagicMock()


@pytest.fixture(autouse=True)
def reset_setup_machine():
    SETUP_MACHINE.reset_mock()
    yield


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def setup_gui():
    with (
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
        patch(
            "sc_linac_physics.applications.auto_setup.frontend.cavity_cell.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
    ):
        gui = SetupGUI()
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        gui.machine_shutdown_popup.exec = MagicMock(
            return_value=QMessageBox.Yes
        )
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        yield gui


def test_launches(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
    assert setup_gui.windowTitle() == "SRF Auto Setup"
    assert setup_gui.ssa_cal_checkbox.isChecked()
    assert setup_gui.autotune_checkbox.isChecked()
    assert setup_gui.cav_char_checkbox.isChecked()
    assert setup_gui.rf_ramp_checkbox.isChecked()


def test_all_linacs_present(qtbot: QtBot, setup_gui):
    """All five linacs, including L4B, must appear in the matrix."""
    qtbot.addWidget(setup_gui)
    assert setup_gui.linac_names == ["L0B", "L1B", "L2B", "L3B", "L4B"]


def test_machine_setup_button(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
    SETUP_MACHINE.trigger_start.reset_mock()
    qtbot.mouseClick(setup_gui.machine_setup_button, Qt.LeftButton)
    assert (
        SETUP_MACHINE.ssa_cal_requested
        == setup_gui.ssa_cal_checkbox.isChecked()
    )
    assert (
        SETUP_MACHINE.auto_tune_requested
        == setup_gui.autotune_checkbox.isChecked()
    )
    assert (
        SETUP_MACHINE.cav_char_requested
        == setup_gui.cav_char_checkbox.isChecked()
    )
    assert (
        SETUP_MACHINE.rf_ramp_requested
        == setup_gui.rf_ramp_checkbox.isChecked()
    )
    assert SETUP_MACHINE.trigger_start.call_count == 1


def test_machine_shutdown_button(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
    SETUP_MACHINE.trigger_shutdown.reset_mock()
    qtbot.mouseClick(setup_gui.machine_shutdown_button, Qt.LeftButton)
    assert SETUP_MACHINE.trigger_shutdown.call_count == 1


def test_machine_abort_button(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
    SETUP_MACHINE.trigger_abort.reset_mock()
    qtbot.mouseClick(setup_gui.machine_abort_button, Qt.LeftButton)
    assert SETUP_MACHINE.trigger_abort.call_count == 1


def test_checkbox_updates(qtbot: QtBot, setup_gui):
    qtbot.addWidget(setup_gui)
    setup_gui.ssa_cal_checkbox.setChecked(False)
    setup_gui.autotune_checkbox.setChecked(False)
    setup_gui.cav_char_checkbox.setChecked(False)
    setup_gui.rf_ramp_checkbox.setChecked(False)
    qtbot.mouseClick(setup_gui.machine_setup_button, Qt.LeftButton)
    assert not SETUP_MACHINE.ssa_cal_requested
    assert not SETUP_MACHINE.auto_tune_requested
    assert not SETUP_MACHINE.cav_char_requested
    assert not SETUP_MACHINE.rf_ramp_requested


@pytest.fixture
def setup_gui_with_no_dialogs():
    with (
        patch(
            "sc_linac_physics.applications.auto_setup.setup_gui.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
        patch(
            "sc_linac_physics.applications.auto_setup.frontend.cavity_cell.SETUP_MACHINE",
            SETUP_MACHINE,
        ),
    ):
        gui = SetupGUI()
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.No)
        gui.machine_shutdown_popup.exec = MagicMock(return_value=QMessageBox.No)
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.No)
        yield gui


def test_dialog_cancellation(qtbot: QtBot, setup_gui_with_no_dialogs):
    qtbot.addWidget(setup_gui_with_no_dialogs)
    SETUP_MACHINE.reset_mock()
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_setup_button, Qt.LeftButton
    )
    assert SETUP_MACHINE.trigger_start.call_count == 0
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_shutdown_button, Qt.LeftButton
    )
    assert SETUP_MACHINE.trigger_shutdown.call_count == 0
    qtbot.mouseClick(
        setup_gui_with_no_dialogs.machine_abort_button, Qt.LeftButton
    )
    assert SETUP_MACHINE.trigger_abort.call_count == 0


def test_abort_button_styled(qtbot: QtBot, setup_gui):
    """Machine abort button must have the error stylesheet applied."""
    qtbot.addWidget(setup_gui)
    stylesheet = setup_gui.machine_abort_button.styleSheet().lower()
    assert "color" in stylesheet or "background" in stylesheet


def test_analog_indicators_in_cavity_panel(qtbot: QtBot, setup_gui):
    """CavityPanel (inline widget) creates one progress bar per cavity."""
    from sc_linac_physics.applications.auto_setup.frontend.cavity_cell import (
        CavityPanel,
    )

    qtbot.addWidget(setup_gui)

    panel = CavityPanel(
        cm_name="01",
        linac_idx=0,
        settings=setup_gui.settings,
    )
    qtbot.addWidget(panel)
    indicators = panel.findChildren(PyDMAnalogIndicator)
    assert len(indicators) == 8
    indicator = indicators[0]
    test_value = 42.5
    indicator.channelValueChanged(test_value)
    assert indicator.value == test_value


@pytest.mark.skip("AACT PV test needs IOC simulation")
def test_aact_pv_connections(qtbot: QtBot, setup_gui):
    pass
