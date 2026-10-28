"""Tests for the Piezo with RF display."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from pydm.widgets import PyDMLabel
from PyQt5.QtWidgets import QMessageBox

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
    PiezoWithRFUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays.piezo_with_rf import (  # noqa: E501
    PiezoWithRFDisplay,
    age_text,
)

DISPLAY = (
    "sc_linac_physics.applications.rf_commissioning.ui.displays.piezo_with_rf"
)
READ_DATA = {
    "amplifier_gain_a": 1.23,
    "amplifier_gain_b": 1.19,
    "detune_gain": 0.004512,
    "rf_test_status": "Warning",
}


@pytest.fixture
def display(qtbot, tmp_path):
    s = CommissioningSession(db_path=str(tmp_path / "piezo_rf.db"))
    d = PiezoWithRFDisplay(session=s)
    qtbot.addWidget(d)
    return d


def test_the_tab_is_no_longer_a_placeholder(display):
    assert display.UI_CLASS is PiezoWithRFUI
    assert display.UI_CLASS is not GenericPhaseUI


def test_registry_and_package_export_name_this_display():
    from sc_linac_physics.applications.rf_commissioning import ui as ui_pkg
    from sc_linac_physics.applications.rf_commissioning.ui import displays
    from sc_linac_physics.applications.rf_commissioning.ui.displays import (
        standard,
    )
    from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (  # noqa: E501
        PHASE_DISPLAY_MAP,
    )

    assert (
        PHASE_DISPLAY_MAP[CommissioningPhase.PIEZO_WITH_RF]
        is PiezoWithRFDisplay
    )
    assert displays.PiezoWithRFDisplay is PiezoWithRFDisplay
    assert ui_pkg.PiezoWithRFDisplay is PiezoWithRFDisplay
    assert not hasattr(standard, "PiezoWithRFDisplay")


def test_live_readouts_are_pydm_labels(display):
    for name in (
        "pydm_test_run",
        "pydm_test_status",
        "pydm_gain_a",
        "pydm_gain_b",
        "pydm_dfgain_new",
        "pydm_dfgain_current",
        "pydm_rf_state",
    ):
        assert isinstance(getattr(display, name), PyDMLabel), name


def test_buttons_say_where_the_push_goes(display):
    assert display.push_button.text() == "Push to IOC…"
    assert display.decline_button.text() == "Don't Push…"
    assert not display.push_button.isEnabled()
    assert not display.decline_button.isEnabled()


def test_review_shows_a_warning_as_complete_not_passed(display):
    display.show_review(READ_DATA)
    assert display.detune_gain_label.text() == "0.004512"
    assert display.gain_a_label.text() == "1.230000"
    assert display.test_result_label.text() == (
        "Warning — complete, not passed"
    )
    assert display.push_button.isEnabled()
    assert display.decline_button.isEnabled()


def test_running_disables_review(display):
    display.show_review(READ_DATA)
    display.set_running(True)
    assert not display.push_button.isEnabled()
    assert not display.run_button.isEnabled()
    assert display.abort_button.isEnabled()


@pytest.mark.parametrize(
    "answer, pushed", [(QMessageBox.Yes, True), (QMessageBox.No, False)]
)
def test_push_asks_first(display, answer, pushed):
    display.controller = Mock(review_data=READ_DATA, phase=None)
    with patch(f"{DISPLAY}.QMessageBox.question", return_value=answer) as ask:
        display.on_push()
    assert "0.004512" in ask.call_args.args[2]
    assert display.controller.on_push.called is pushed


@pytest.mark.parametrize(
    "reply, declined", [(("too high", True), True), (("", False), False)]
)
def test_dont_push_needs_a_justification(display, reply, declined):
    display.controller = Mock()
    with patch(f"{DISPLAY}.QInputDialog.getText", return_value=reply):
        display.on_decline_push()
    assert display.controller.on_decline_push.called is declined


def test_after_a_failed_save_push_retries_without_asking(display):
    # _on_finished has already cleared review_data by then.
    display.controller = Mock(stage="unsaved", review_data=None)
    with patch(f"{DISPLAY}.QMessageBox.question") as ask:
        display.on_push()
    ask.assert_not_called()
    display.controller.on_push.assert_called_once()


def test_after_a_failed_save_dont_push_retries_without_asking(display):
    display.controller = Mock(stage="unsaved", review_data=None)
    with patch(f"{DISPLAY}.QInputDialog.getText") as ask:
        display.on_decline_push()
    ask.assert_not_called()
    display.controller.on_decline_push.assert_called_once()


def test_changing_cavity_blanks_the_old_review(display):
    display.show_review(READ_DATA)
    display.controller.drop_review()
    for label in (
        display.gain_a_label,
        display.detune_gain_label,
        display.test_result_label,
        display.local_phase_status,
    ):
        assert label.text() == "-"
    assert not display.push_button.isEnabled()


@pytest.mark.parametrize(
    "button, expected", [("Rerun", True), ("Skip", False), ("Cancel", None)]
)
def test_stale_prompt_answers(display, button, expected):
    def click(box):
        match = [b for b in box.buttons() if button in b.text()]
        match[0].click()
        return 0

    with patch.object(QMessageBox, "exec_", click):
        answer = display.ask_rerun(
            "SSA calibration", "CALTS", datetime(2026, 10, 20, 9, 0), True
        )
    assert answer is expected


def test_age_text():
    now = datetime(2026, 10, 20, 14, 57)
    assert age_text(datetime(2026, 10, 20, 11, 52), now) == "3 h 05 min"
    assert age_text(None) == "unknown"


def test_finishing_resets_the_panel(display):
    display.show_review(READ_DATA)
    display.set_paused(True)
    display.on_phase_finished("COMPLETED")
    assert display.local_phase_status.text() == "COMPLETED"
    assert display.pause_button.text() == "⏸ Pause"
    assert not display.push_button.isEnabled()


def test_loading_a_record_drops_the_review(display):
    display.show_review(READ_DATA)
    display.controller = Mock(context=None)
    record = Mock(cryomodule="02", cavity_number=1, piezo_with_rf=None)
    display.on_record_loaded(record, 1)
    display.controller.drop_review.assert_called_once()
    assert display.detune_gain_label.text() == "-"
    assert not display.push_button.isEnabled()


def test_stored_data_shows_the_record(display):
    from sc_linac_physics.applications.rf_commissioning.models.data_models import (  # noqa: E501
        PiezoWithRFTest,
    )

    record = Mock(
        piezo_with_rf=PiezoWithRFTest(
            detune_gain=0.004512, rf_test_status="Warning"
        )
    )
    display.refresh_from_record(record)
    assert display.piezo_rf_detune_gain.text() == "0.004512"


def test_a_reloaded_record_drops_the_review(display):
    # Reselecting the same cavity from the header reloads its record as a
    # new object; a push must not go to the old one.
    old_record = Mock(piezo_with_rf=None)
    display.controller = Mock(context=Mock(record=old_record))
    display.refresh_from_record(old_record)
    display.controller.drop_review.assert_not_called()
    display.refresh_from_record(Mock(piezo_with_rf=None))
    display.controller.drop_review.assert_called_once()


def _indicator(display):
    return display.ui.widgets["status_indicator"].text()


def test_toolbar_indicator_follows_the_run(display):
    display.set_running(True)
    assert _indicator(display) == "● RUNNING"
    display.set_paused(True)
    assert _indicator(display) == "● PAUSED"
    # Pause resumes on this tab; Start Test stays off.
    assert display.pause_button.isEnabled()
    assert not display.run_button.isEnabled()
    display.set_paused(False)
    assert _indicator(display) == "● RUNNING"
    display.set_running(False)
    display.show_review(READ_DATA)
    assert _indicator(display) == "● REVIEW"


@pytest.mark.parametrize(
    "status, shown", [("COMPLETED", "✓ COMPLETE"), ("FAILED", "✗ ERROR")]
)
def test_toolbar_indicator_after_the_phase(display, status, shown):
    display.set_running(True)
    display.on_phase_finished(status)
    assert _indicator(display) == shown
    assert display.run_button.isEnabled()
    assert not display.abort_button.isEnabled()
