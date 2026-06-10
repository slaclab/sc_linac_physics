from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QMessageBox

from sc_linac_physics.applications.auto_setup.setup_gui import SetupGUI
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_MAP


def _mock_cavity(n):
    c = MagicMock()
    c.status_pv = f"fake://S{n}"
    c.progress_pv = f"fake://P{n}"
    c.status_msg_pv = f"fake://M{n}"
    c.note_pv = f"fake://N{n}"
    c.edm_macro_string = f"CAVNO={n}"
    c.script_is_running = False
    c.is_online = True
    return c


def _build_machine_mock():
    machine = MagicMock()
    all_cm_names = [cm for linac_cms in LINAC_CM_MAP for cm in linac_cms]
    cryomodules = {}
    for cm_name in all_cm_names:
        cm = MagicMock()
        cm.cavities = {n: _mock_cavity(n) for n in range(1, 9)}
        cryomodules[cm_name] = cm
    machine.cryomodules = cryomodules
    return machine


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
    machine = _build_machine_mock()
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        gui = SetupGUI()
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        gui.machine_shutdown_popup.exec = MagicMock(
            return_value=QMessageBox.Yes
        )
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        yield gui


def test_launches(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    assert setup_gui.windowTitle() == "SRF Auto Setup"
    assert setup_gui.ssa_cal_checkbox.isChecked()
    assert setup_gui.autotune_checkbox.isChecked()
    assert setup_gui.cav_char_checkbox.isChecked()
    assert setup_gui.rf_ramp_checkbox.isChecked()


def test_five_linac_widgets(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    assert len(setup_gui.linac_widgets) == 5
    assert [w.name for w in setup_gui.linac_widgets] == [
        "L0B",
        "L1B",
        "L2B",
        "L3B",
        "L4B",
    ]


def test_machine_setup_calls_unlocked_cavities(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    first_linac = setup_gui.linac_widgets[0]
    first_cm = next(iter(first_linac.gui_cryomodules.values()))
    locked_cav = first_cm.gui_cavities[1]
    unlocked_cav = first_cm.gui_cavities[2]
    locked_cav.lock()

    setup_gui.trigger_machine_setup()

    locked_cav.cavity.trigger_start.assert_not_called()
    unlocked_cav.cavity.trigger_start.assert_called()


def test_machine_setup_cancelled(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    setup_gui.machine_setup_popup.exec = MagicMock(
        return_value=QMessageBox.Cancel
    )
    setup_gui.trigger_machine_setup()
    for linac in setup_gui.linac_widgets:
        for gui_cm in linac.gui_cryomodules.values():
            for gui_cav in gui_cm.gui_cavities.values():
                gui_cav.cavity.trigger_start.assert_not_called()


def test_machine_shutdown_skips_locked(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    first_cm = next(iter(setup_gui.linac_widgets[0].gui_cryomodules.values()))
    locked_cav = first_cm.gui_cavities[1]
    locked_cav.lock()
    setup_gui.trigger_machine_shutdown()
    locked_cav.cavity.trigger_shutdown.assert_not_called()


def test_machine_abort_ignores_lock(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    first_cm = next(iter(setup_gui.linac_widgets[0].gui_cryomodules.values()))
    locked_cav = first_cm.gui_cavities[1]
    locked_cav.lock()
    setup_gui.trigger_machine_abort()
    locked_cav.cavity.trigger_abort.assert_called()


def test_checkbox_state_propagates(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    setup_gui.ssa_cal_checkbox.setChecked(False)
    setup_gui.autotune_checkbox.setChecked(False)
    first_cm = next(iter(setup_gui.linac_widgets[0].gui_cryomodules.values()))
    gui_cav = first_cm.gui_cavities[1]
    setup_gui.trigger_machine_setup()
    assert gui_cav.cavity.ssa_cal_requested is False
    assert gui_cav.cavity.auto_tune_requested is False
