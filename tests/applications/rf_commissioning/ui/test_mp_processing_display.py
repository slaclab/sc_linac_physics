"""Tests for MPProcessingDisplay: registry, Settings, toolbar, quench table."""

from datetime import datetime, timedelta
from unittest.mock import PropertyMock, patch

import pytest
from pydm.widgets import PyDMLabel

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    MPProcessingData,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    MPProcessingUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays.mp_processing import (  # noqa: E501
    PAUSE_TEXT,
    RESUME_TEXT,
    MPProcessingDisplay,
    since_last_quench_text,
)

T0 = datetime(2026, 11, 23, 9, 0, 0)


@pytest.fixture
def display(qtbot, tmp_path):
    s = CommissioningSession(db_path=str(tmp_path / "mp.db"))
    d = MPProcessingDisplay(session=s)
    qtbot.addWidget(d)
    return d


def _with_quenches(display, *offsets_s):
    """Give the controller a run whose record has these quenches."""
    data = MPProcessingData(max_amplitude_reached=14.25)
    for offset in offsets_s:
        data.add_quench(
            amplitude=14.0, timestamp=T0 + timedelta(seconds=offset)
        )
    record = CommissioningRecord(
        linac=1, cryomodule="02", cavity_number=1, mp_processing=data
    )
    display.controller.context = PhaseContext(record=record, operator="x")
    return data


def test_registry_and_package_export_name_this_display():
    from sc_linac_physics.applications.rf_commissioning import ui as ui_pkg
    from sc_linac_physics.applications.rf_commissioning.ui.displays import (
        standard,
    )
    from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (  # noqa: E501
        PHASE_DISPLAY_MAP,
    )

    assert (
        PHASE_DISPLAY_MAP[CommissioningPhase.MP_PROCESSING]
        is MPProcessingDisplay
    )
    assert ui_pkg.MPProcessingDisplay is MPProcessingDisplay
    assert not hasattr(standard, "HighPowerMPProcessingDisplay")
    assert MPProcessingDisplay.UI_CLASS is MPProcessingUI


def test_live_readouts_are_pydm_labels(display):
    for name in (
        "pydm_ades",
        "pydm_aact",
        "pydm_ades_max",
        "pydm_quench_latch",
        "pydm_rf_mode",
        "pydm_rf_state",
    ):
        assert isinstance(getattr(display, name), PyDMLabel), name


def test_settings_default_to_the_phase_limits_and_stable_is_in_minutes(
    display,
):
    assert display.stable_minutes_spin.value() == 5.0
    display.stable_minutes_spin.setValue(10.0)
    display.start_mv_spin.setValue(7.5)
    settings = display.read_settings()
    assert settings["stable_seconds"] == 600.0
    assert settings["start_amplitude_mv"] == 7.5
    assert settings["step_mv"] == 0.1
    assert settings["step_seconds"] == 1.0
    assert settings["quench_hold_seconds"] == 30.0


def test_running_locks_settings_and_offers_pause_only_in_process(display):
    display.set_running(True)
    assert not display.start_mv_spin.isEnabled()
    assert not display.quench_hold_spin.isEnabled()
    assert not display.pause_button.isEnabled()
    assert display.abort_button.isEnabled()
    display.set_running(False)
    assert display.start_mv_spin.isEnabled()
    assert not display.pause_button.isEnabled()


def test_progress_fills_counts_and_adds_quench_rows_once(display):
    _with_quenches(display, 0, 95)
    display.refresh_progress()
    display.refresh_progress()
    assert display.quench_count_label.text() == "2"
    assert display.max_ades_label.text() == "14.25 MV"
    table = display.quench_table
    assert table.rowCount() == 2
    assert [table.item(1, c).text() for c in range(4)] == [
        "2",
        "09:01:35",
        "14.00",
        "95",
    ]
    assert table.item(0, 3).text() == "-"


def test_refresh_scrolls_only_when_a_quench_row_is_added(display):
    _with_quenches(display, 0, 95)
    table = display.quench_table
    with patch.object(table, "scrollToBottom") as scroll:
        display.refresh_progress()
        assert scroll.call_count == 1
        # No new quench: the operator's scroll position is left alone.
        display.refresh_progress()
        assert scroll.call_count == 1


def test_clear_run_empties_the_table(display):
    _with_quenches(display, 0)
    display.refresh_progress()
    display.clear_run()
    assert display.quench_table.rowCount() == 0
    assert display.quench_count_label.text() == "-"


def test_retry_save_relabels_start(display):
    display.set_retry_save()
    assert display.run_button.isEnabled()
    assert "Retry save" in display.run_button.text()


@pytest.mark.parametrize(
    "button, expected", [("Rerun", True), ("Skip", False), ("Cancel", None)]
)
def test_stale_prompt_answers(display, button, expected):
    from PyQt5.QtWidgets import QMessageBox

    def click(box):
        next(b for b in box.buttons() if b.text() == button).click()

    with patch.object(QMessageBox, "exec_", click):
        answer = display.ask_rerun("SSA calibration", "CALTS", T0, True)
    assert answer is expected


def test_process_start_time_is_noted(display):
    display.on_step_started("setup_rf")
    assert display._process_started is None
    display.on_step_started("process")
    assert display._process_started is not None


def test_since_last_quench_counts_from_the_latest_quench():
    data = MPProcessingData()
    data.add_quench(amplitude=12.0, timestamp=T0)
    data.add_quench(amplitude=12.0, timestamp=T0 + timedelta(seconds=60))
    now = T0 + timedelta(seconds=60 + 252)
    assert since_last_quench_text(data, T0, now) == "4 min 12 s"


def test_since_last_quench_before_any_counts_from_the_process_step():
    now = T0 + timedelta(seconds=65)
    assert (
        since_last_quench_text(MPProcessingData(), T0, now)
        == "1 min 05 s (no quench yet)"
    )


def test_since_last_quench_before_the_process_step_is_blank():
    assert since_last_quench_text(None, None, T0) == "-"
    assert since_last_quench_text(MPProcessingData(), None, T0) == "-"


def test_since_last_quench_never_goes_negative():
    data = MPProcessingData()
    data.add_quench(amplitude=12.0, timestamp=T0 + timedelta(seconds=5))
    assert since_last_quench_text(data, T0, T0) == "0 min 00 s"


def test_a_different_record_object_forgets_the_run(display):
    _with_quenches(display, 0)
    other = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    display.refresh_from_record(other)
    assert display.controller.context is None


def test_the_same_record_keeps_the_run(display):
    _with_quenches(display, 0)
    display.refresh_from_record(display.controller.context.record)
    assert display.controller.context is not None


def test_clearing_the_run_puts_start_test_back_after_retry_save(display):
    display.set_retry_save()
    display.clear_run()
    assert "Retry save" not in display.run_button.text()
    assert "Start Test" in display.run_button.text()


def test_a_rerun_clears_the_previous_runs_rows(display):
    _with_quenches(display, 0, 30, 60)
    display.refresh_progress()
    # verify_initial_state on a rerun starts a new MPProcessingData.
    new = MPProcessingData()
    new.add_quench(amplitude=13.0, timestamp=T0)
    display.controller.context.record.mp_processing = new
    display.refresh_progress()
    assert display.quench_table.rowCount() == 1
    assert display.quench_table.item(0, 2).text() == "13.00"


def test_amplitudes_show_two_decimals_whatever_the_pv_prec(display):
    for name in ("pydm_ades", "pydm_aact", "pydm_ades_max"):
        label = getattr(display, name)
        assert label.precisionFromPV is False, name
        assert label.precision == 2, name
    assert display.pydm_rf_state.precisionFromPV is True


def test_pause_button_follows_the_phase_during_process(display):
    display.set_running(True)
    display.on_step_started("setup_rf")
    assert not display.pause_button.isEnabled()
    display.on_step_started("process")
    assert display.pause_button.isEnabled()

    with patch.object(
        type(display.controller), "pause_state", new_callable=PropertyMock
    ) as state:
        state.return_value = "pausing"
        display.refresh_progress()
        assert not display.pause_button.isEnabled()
        assert display.local_phase_status.text() == "PAUSING"
        state.return_value = "paused"
        display.refresh_progress()
        assert display.pause_button.isEnabled()
        assert display.pause_button.text() == RESUME_TEXT
        assert display.local_phase_status.text() == "PAUSED"
        indicator = display.ui.widgets["status_indicator"]
        assert indicator.text() == "● PAUSED"
        # A refused resume: the phase is still paused, Resume comes back.
        state.return_value = "resuming"
        display.refresh_progress()
        assert not display.pause_button.isEnabled()
        state.return_value = "paused"
        display.refresh_progress()
        assert display.pause_button.text() == RESUME_TEXT
        state.return_value = "running"
        display.refresh_progress()
        assert display.pause_button.text() == PAUSE_TEXT
        assert indicator.text() == "● RUNNING"

    display.on_step_started("record_results")
    assert not display.pause_button.isEnabled()


def test_first_quench_after_a_pause_shows_no_interval(display):
    _with_quenches(display, 0, 95)
    display.controller.mp_data.quench_events[1].after_pause = True
    display.refresh_progress()
    assert display.quench_table.item(1, 3).text() == "after pause"


def test_since_last_quench_counts_from_a_later_resume():
    data = MPProcessingData()
    data.add_quench(amplitude=14.0, timestamp=T0)
    resumed = T0 + timedelta(seconds=100)
    now = T0 + timedelta(seconds=130)
    text = since_last_quench_text(data, T0, now, resumed_at=resumed)
    assert text == "0 min 30 s (since resume)"
    # An earlier resume doesn't change the count from the last quench.
    early = since_last_quench_text(
        data, T0, now, resumed_at=T0 - timedelta(seconds=5)
    )
    assert early == "2 min 10 s"


def test_field_emission_box_reads_none_at_not_seen(display):
    assert display.fe_onset_spin.text() == "not seen"
    display.fe_50_spin.setValue(15.25)
    assert display.read_fe_fields() == {
        "field_emission_onset": None,
        "fe_50_mr_h_amplitude": 15.25,
    }


def test_field_emission_box_shows_the_stored_run(display):
    data = MPProcessingData(field_emission_onset=13.5)
    display.show_fe_fields(data)
    assert display.fe_onset_spin.value() == 13.5
    assert display.fe_50_spin.text() == "not seen"
    assert display.fe_save_button.isEnabled()
    display.show_fe_fields(None)
    assert display.fe_onset_spin.text() == "not seen"
    assert not display.fe_save_button.isEnabled()


def test_field_emission_box_stays_editable_during_a_run(display):
    display.show_fe_fields(MPProcessingData())
    display.set_running(True)
    assert display.fe_onset_spin.isEnabled()
    assert not display.fe_save_button.isEnabled()
