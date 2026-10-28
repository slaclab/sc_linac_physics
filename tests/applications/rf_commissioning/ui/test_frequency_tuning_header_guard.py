"""A header change while a frequency tuning stage runs is refused.

Before, the container replaced the active record and refresh_from_record
rebuilt the controller under the running stage, so Abort could reach the
wrong stepper.
"""

from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.container import (
    build_default_phase_specs,
)
from sc_linac_physics.applications.rf_commissioning.ui.multi_phase_screen import (
    MultiPhaseCommissioningDisplay,
)

LIFECYCLE = (
    "sc_linac_physics.applications.rf_commissioning.ui.container."
    "record_lifecycle.QMessageBox"
)


@pytest.fixture
def screen(qtbot, tmp_path):
    specs = [
        spec
        for spec in build_default_phase_specs()
        if spec.phase == CommissioningPhase.FREQUENCY_TUNING
    ]
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        display = MultiPhaseCommissioningDisplay(
            session=CommissioningSession(db_path=str(tmp_path / "c.db")),
            phase_specs=specs,
            refresh_interval_ms=10**9,
        )
    qtbot.addWidget(display)
    display.linac_combo.setCurrentText("L1B")
    display.cryomodule_combo.setCurrentText("02")
    display.cavity_combo.setCurrentText("1")
    return display


def _running_controller(screen):
    controller = screen._phase_displays[0]._controller
    tuned = Mock(name="CM02 cavity 1")
    controller._cavity = tuned
    controller._stage_running = True
    return controller, tuned


def test_display_reports_a_running_stage(screen):
    display = screen._phase_displays[0]
    assert display.is_running_phase() is False
    display._controller._stage_running = True
    assert display.is_running_phase() is True


def test_header_change_during_a_stage_is_refused_and_reverted(screen):
    controller, tuned = _running_controller(screen)
    record_before = screen.session.get_active_record()

    with patch(LIFECYCLE) as box:
        screen.cavity_combo.setCurrentText("2")

    box.warning.assert_called_once()
    assert screen.session.get_active_record() is record_before
    assert screen.cavity_combo.currentText() == "1"
    assert screen.cryomodule_combo.currentText() == "02"
    assert controller._cavity is tuned

    controller.on_abort()
    assert tuned.stepper_tuner.abort_flag is True


def test_after_the_stage_manual_moves_follow_the_header(screen):
    controller, tuned = _running_controller(screen)
    with patch(LIFECYCLE):
        screen.cavity_combo.setCurrentText("2")
    controller._stage_running = False

    moves = []
    controller._do_stepper_move = lambda cavity, positive: moves.append(cavity)
    with patch(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "frequency_tuning_controller.Thread"
    ) as thread:
        thread.side_effect = lambda target, args, daemon: Mock(
            start=lambda: target(*args)
        )
        controller.on_move_right()

    assert screen.cavity_combo.currentText() == "1"
    assert moves == [tuned]
