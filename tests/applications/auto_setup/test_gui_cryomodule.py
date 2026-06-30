from unittest.mock import patch, MagicMock

import pytest
from sc_linac_physics.applications.auto_setup.frontend.gui_cryomodule import (
    GUICryomodule,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


def _mock_cavity(n):
    c = MagicMock()
    c.status_pv = f"fake://S{n}"
    c.progress_pv = f"fake://P{n}"
    c.status_msg_pv = f"fake://M{n}"
    c.note_pv = f"fake://N{n}"
    c.edm_macro_string = f"CM=01,CAVNO={n}"
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
def gui_cm(qtbot):
    mock_settings = MagicMock()
    for attr in (
        "ssa_cal_checkbox",
        "auto_tune_checkbox",
        "cav_char_checkbox",
        "rf_ramp_checkbox",
    ):
        getattr(mock_settings, attr).isChecked.return_value = True

    machine = MagicMock()
    machine.cryomodules = {
        "01": MagicMock(cavities={n: _mock_cavity(n) for n in range(1, 9)})
    }

    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        gui = GUICryomodule(linac_idx=0, name="01", settings=mock_settings)
        qtbot.addWidget(gui.tile)
        qtbot.addWidget(gui.detail_panel)
        yield gui


def test_tile_and_detail_panel_built(gui_cm):
    assert gui_cm.tile is not None
    assert gui_cm.detail_panel is not None


def test_eight_cavity_cards_built(gui_cm):
    assert len(gui_cm.gui_cavities) == 8


def test_eight_dots_built(gui_cm):
    assert len(gui_cm._dots) == 8


def test_detail_panel_hidden_initially(gui_cm):
    assert gui_cm.detail_panel.isHidden()


def test_on_cavity_status_changed_updates_dot(gui_cm):
    from sc_linac_physics.applications.auto_setup.frontend.style import (
        STATUS_ERROR_BORDER,
    )

    gui_cm._on_cavity_status_changed(1, STATUS_ERROR_VALUE)
    assert STATUS_ERROR_BORDER in gui_cm._dots[1].styleSheet()


def test_on_status_changed_callback_fires(gui_cm):
    received = []
    gui_cm.on_status_changed = lambda name, status: received.append(
        (name, status)
    )
    gui_cm._on_cavity_status_changed(1, STATUS_RUNNING_VALUE)
    assert received == [("01", STATUS_RUNNING_VALUE)]


def test_lock_cascades_to_all_cavities(gui_cm):
    gui_cm.lock()
    assert gui_cm.is_locked
    for gui_cav in gui_cm.gui_cavities.values():
        assert gui_cav.locked


def test_unlock_no_confirm_releases_cascade_locked(gui_cm):
    gui_cm.lock()
    gui_cm.unlock_no_confirm()
    assert not gui_cm.is_locked
    for gui_cav in gui_cm.gui_cavities.values():
        assert not gui_cav.locked


def test_unlock_preserves_pre_locked_cavities(gui_cm):
    gui_cm.gui_cavities[3].lock()
    gui_cm.lock()
    gui_cm.unlock_no_confirm()
    assert gui_cm.gui_cavities[3].locked  # was locked before cascade
    assert not gui_cm.gui_cavities[1].locked  # was not locked before cascade


def test_trigger_setup_all_skips_locked(gui_cm):
    gui_cm.gui_cavities[1].lock()
    gui_cm.trigger_setup_all()
    gui_cm.gui_cavities[1].cavity.trigger_start.assert_not_called()
    gui_cm.gui_cavities[2].cavity.trigger_start.assert_called_once()


def test_trigger_abort_all_ignores_lock(gui_cm):
    gui_cm.gui_cavities[1].lock()
    gui_cm.trigger_abort_all()
    gui_cm.gui_cavities[1].cavity.trigger_abort.assert_called_once()
