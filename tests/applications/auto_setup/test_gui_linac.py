from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QMessageBox

from sc_linac_physics.applications.auto_setup.frontend.gui_linac import GUILinac
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_RUNNING_VALUE


def _mock_cavity(n):
    c = MagicMock()
    c.status_pv = f"fake://S{n}"
    c.progress_pv = f"fake://P{n}"
    c.status_msg_pv = f"fake://M{n}"
    c.note_pv = f"fake://N{n}"
    c.edm_macro_string = f"CM=04,CAVNO={n}"
    c.script_is_running = False
    c.is_online = True
    return c


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def gui_linac(qtbot):
    mock_settings = MagicMock()
    for attr in (
        "ssa_cal_checkbox",
        "auto_tune_checkbox",
        "cav_char_checkbox",
        "rf_ramp_checkbox",
    ):
        getattr(mock_settings, attr).isChecked.return_value = True

    cm_names = ["04", "05"]
    machine = MagicMock()
    machine.cryomodules = {
        cm_name: MagicMock(cavities={n: _mock_cavity(n) for n in range(1, 9)})
        for cm_name in cm_names
    }

    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        linac = GUILinac(
            name="L2B", idx=2, cryomodule_names=cm_names, settings=mock_settings
        )
        qtbot.addWidget(linac.tile)
        qtbot.addWidget(linac.detail_panel)
        yield linac


def test_tile_and_detail_panel_built(gui_linac):
    assert gui_linac.tile is not None
    assert gui_linac.detail_panel is not None


def test_cm_chips_created(gui_linac):
    assert set(gui_linac._cm_chips.keys()) == {"04", "05"}


def test_gui_cryomodules_created(gui_linac):
    assert set(gui_linac.gui_cryomodules.keys()) == {"04", "05"}


def test_detail_panel_hidden_initially(gui_linac):
    assert gui_linac.detail_panel.isHidden()


def test_on_cm_status_changed_updates_chip(gui_linac):
    from sc_linac_physics.applications.auto_setup.frontend.style import (
        STATUS_RUNNING_BORDER,
    )

    gui_linac._on_cm_status_changed("04", STATUS_RUNNING_VALUE)
    chip = gui_linac._cm_chips["04"]
    assert STATUS_RUNNING_BORDER in chip.styleSheet()
    assert "⟳CM04" == chip.text()


def test_lock_linac_cascades_to_cms(gui_linac):
    gui_linac._lock_linac()
    assert gui_linac.is_locked
    for gui_cm in gui_linac.gui_cryomodules.values():
        assert gui_cm.is_locked


def test_unlock_linac_releases_cascade(gui_linac):
    gui_linac._lock_linac()
    gui_linac._unlock_linac()
    assert not gui_linac.is_locked
    for gui_cm in gui_linac.gui_cryomodules.values():
        assert not gui_cm.is_locked


def test_trigger_setup_confirmed(gui_linac):
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_linac.make_sanity_check_popup"
    ) as mock_popup:
        mock_popup.return_value.exec.return_value = QMessageBox.Yes
        gui_linac.trigger_setup()
    for gui_cm in gui_linac.gui_cryomodules.values():
        for gui_cav in gui_cm.gui_cavities.values():
            gui_cav.cavity.trigger_start.assert_called()


def test_trigger_setup_cancelled(gui_linac):
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_linac.make_sanity_check_popup"
    ) as mock_popup:
        mock_popup.return_value.exec.return_value = QMessageBox.Cancel
        gui_linac.trigger_setup()
    for gui_cm in gui_linac.gui_cryomodules.values():
        for gui_cav in gui_cm.gui_cavities.values():
            gui_cav.cavity.trigger_start.assert_not_called()
