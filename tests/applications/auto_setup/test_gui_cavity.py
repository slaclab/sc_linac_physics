from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QFrame, QMessageBox
from pydm.widgets.line_edit import PyDMLineEdit

from sc_linac_physics.applications.auto_setup.frontend.gui_cavity import (
    GUICavity,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
)


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def gui_cavity(qtbot):
    mock_cavity = MagicMock()
    mock_cavity.status_pv = "fake://STATUS"
    mock_cavity.progress_pv = "fake://PROG"
    mock_cavity.status_msg_pv = "fake://MSG"
    mock_cavity.note_pv = "fake://NOTE"
    mock_cavity.edm_macro_string = "CM=01,CAVNO=1"
    mock_cavity.script_is_running = False
    mock_cavity.is_online = True

    machine = MagicMock()
    machine.cryomodules = {"01": MagicMock(cavities={1: mock_cavity})}

    mock_settings = MagicMock()
    mock_settings.ssa_cal_checkbox.isChecked.return_value = True
    mock_settings.auto_tune_checkbox.isChecked.return_value = True
    mock_settings.cav_char_checkbox.isChecked.return_value = True
    mock_settings.rf_ramp_checkbox.isChecked.return_value = True

    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        cav = GUICavity(
            number=1,
            prefix="ACCL:L0B:0110:",
            cm="01",
            settings=mock_settings,
        )
        qtbot.addWidget(cav.frame)
        yield cav


def test_frame_is_qframe(gui_cavity):
    assert isinstance(gui_cavity.frame, QFrame)


def test_acon_edit_is_line_edit(gui_cavity):
    assert isinstance(gui_cavity.acon_edit, PyDMLineEdit)


def test_initial_state_not_locked(gui_cavity):
    assert gui_cavity.locked is False


def test_setup_button_enabled_when_ready(gui_cavity):
    gui_cavity._handle_status_value(STATUS_READY_VALUE)
    assert gui_cavity.setup_button.isEnabled()


def test_setup_button_disabled_when_running(gui_cavity):
    gui_cavity._handle_status_value(STATUS_RUNNING_VALUE)
    assert not gui_cavity.setup_button.isEnabled()


def test_lock_disables_setup_and_shutdown(gui_cavity):
    gui_cavity.lock()
    assert gui_cavity.locked is True
    assert not gui_cavity.setup_button.isEnabled()
    assert not gui_cavity.shutdown_button.isEnabled()


def test_lock_keeps_abort_enabled(gui_cavity):
    gui_cavity.lock()
    assert gui_cavity.abort_button.isEnabled()


def test_unlock_no_confirm_restores_state(gui_cavity):
    gui_cavity.lock()
    gui_cavity.unlock_no_confirm()
    assert gui_cavity.locked is False
    assert gui_cavity.setup_button.isEnabled()


def test_step_label_updates_on_progress(gui_cavity):
    gui_cavity._handle_progress_value(30)
    assert "Auto Tune" in gui_cavity._step_label.text()
    gui_cavity._handle_progress_value(75)
    assert "RF Ramp" in gui_cavity._step_label.text()


def test_on_status_changed_callback_fires(gui_cavity):
    received = []
    gui_cavity.on_status_changed = lambda num, status: received.append(
        (num, status)
    )
    gui_cavity._handle_status_value(STATUS_RUNNING_VALUE)
    assert received == [(1, STATUS_RUNNING_VALUE)]


def test_trigger_setup_skipped_when_locked(gui_cavity):
    gui_cavity.lock()
    gui_cavity.trigger_setup()
    gui_cavity.cavity.trigger_start.assert_not_called()


def test_trigger_setup_applies_settings(gui_cavity):
    gui_cavity.trigger_setup()
    gui_cavity.cavity.trigger_start.assert_called_once()
    assert gui_cavity.cavity.ssa_cal_requested is True


def test_trigger_shutdown_skipped_when_locked(gui_cavity):
    gui_cavity.lock()
    gui_cavity.trigger_shutdown()
    gui_cavity.cavity.trigger_shutdown.assert_not_called()


def test_request_abort_always_works(gui_cavity):
    gui_cavity.lock()
    gui_cavity.request_abort()
    gui_cavity.cavity.trigger_abort.assert_called_once()


def test_on_lock_clicked_when_unlocked_locks_without_dialog(gui_cavity):
    with patch("PyQt5.QtWidgets.QMessageBox.question") as mock_q:
        gui_cavity._on_lock_clicked()
        mock_q.assert_not_called()
    assert gui_cavity.locked is True


def test_on_lock_clicked_when_locked_yes_unlocks(gui_cavity):
    gui_cavity.lock()
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.QMessageBox.question",
        return_value=QMessageBox.Yes,
    ):
        gui_cavity._on_lock_clicked()
    assert gui_cavity.locked is False


def test_on_lock_clicked_when_locked_no_stays_locked(gui_cavity):
    gui_cavity.lock()
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.QMessageBox.question",
        return_value=QMessageBox.No,
    ):
        gui_cavity._on_lock_clicked()
    assert gui_cavity.locked is True
