"""Tests for the Piezo with RF phase.

The phase drives the cavity through Cavity/Piezo helpers, so these assert
what it calls and in what order, that a dry run writes nothing, and where it
refuses to go on.
"""

import time
from unittest.mock import Mock, PropertyMock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseStatus,
    PiezoWithRFTest,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_with_rf import (
    PiezoWithRFLimits,
    PiezoWithRFPhase,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityCharacterizationError,
    CavityHWModeError,
)

CRASH = 0
COMPLETE = 1
RUNNING = 2


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)


@pytest.fixture
def mock_cavity():
    cavity = Mock()
    cavity.piezo = Mock(spec=CommissioningPiezo)
    cavity.is_online = True
    cavity.stepper_tuner.motor_moving = False
    cavity.ssa.calibration_running = False
    cavity.length = 1.038
    cavity.measured_loaded_q = 4.0e7
    cavity.measured_scale_factor = 30.0
    cavity.detune = 12.0
    cavity.detune_invalid = False
    cavity.piezo.withrf_check_status_pv_obj.get.return_value = COMPLETE
    return cavity


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


def make_phase(cavity, record, dry_run=False, **params):
    context = PhaseContext(
        record=record,
        operator="test_op",
        dry_run=dry_run,
        parameters={"cavity": cavity, **params},
    )
    phase = PiezoWithRFPhase(context, limits=PiezoWithRFLimits(poll_interval=1))
    phase.validate_prerequisites()
    return phase


@pytest.fixture
def phase(mock_cavity, record):
    return make_phase(mock_cavity, record)


def test_phase_type(phase):
    assert phase.phase_type == CommissioningPhase.PIEZO_WITH_RF


def test_rejects_a_plain_piezo(mock_cavity, record):
    mock_cavity.piezo = Mock()  # not a CommissioningPiezo
    context = PhaseContext(
        record=record, operator="op", parameters={"cavity": mock_cavity}
    )
    ok, message = PiezoWithRFPhase(context).validate_prerequisites()
    assert not ok
    assert "CommissioningPiezo" in message


@pytest.mark.parametrize(
    "attr, value, text",
    [
        ("is_online", False, "not online"),
        ("ssa.calibration_running", True, "SSA calibration"),
        ("stepper_tuner.motor_moving", True, "Stepper"),
    ],
)
def test_verify_initial_state_refuses(phase, mock_cavity, attr, value, text):
    target = mock_cavity
    *path, last = attr.split(".")
    for name in path:
        target = getattr(target, name)
    setattr(target, last, value)
    result = phase.execute_step("verify_initial_state")
    assert result.result == PhaseResult.FAILED
    assert text in result.message


def test_verify_initial_state_passes(phase):
    assert (
        phase.execute_step("verify_initial_state").result == PhaseResult.SUCCESS
    )


def test_setup_rf_runs_setup_rf_then_sel(phase, mock_cavity):
    order = []
    mock_cavity.setup_rf.side_effect = lambda amp: order.append(
        ("setup_rf", amp)
    )
    mock_cavity.set_sel_mode.side_effect = lambda: order.append("sel")

    result = phase.execute_step("setup_rf")

    assert result.result == PhaseResult.SUCCESS
    assert order == [("setup_rf", pytest.approx(6.5 * 1.038)), "sel"]


def test_setup_rf_notes_the_values_it_left(phase, mock_cavity, record):
    mock_cavity.measured_loaded_q = 4.1e7
    mock_cavity.measured_scale_factor = 31.0
    phase.execute_step("setup_rf")
    notes = record.piezo_with_rf.notes
    assert "4.100e+07" in notes
    assert "31.0" in notes


def test_setup_rf_appends_to_existing_notes(phase, record):
    record.piezo_with_rf = PiezoWithRFTest(notes="operator note")
    phase.execute_step("setup_rf")
    assert record.piezo_with_rf.notes.startswith("operator note\n")


def test_setup_rf_error_fails_without_retry(phase, mock_cavity):
    mock_cavity.setup_rf.side_effect = CavityCharacterizationError("crashed")
    result = phase.execute_step("setup_rf")
    assert result.result == PhaseResult.FAILED
    mock_cavity.set_sel_mode.assert_not_called()


def test_setup_rf_offline_fails(phase, mock_cavity):
    mock_cavity.setup_rf.side_effect = CavityHWModeError("offline")
    assert phase.execute_step("setup_rf").result == PhaseResult.FAILED


def test_setup_rf_abort_fails(phase, mock_cavity):
    mock_cavity.setup_rf.side_effect = CavityAbortError("abort")
    result = phase.execute_step("setup_rf")
    assert result.result == PhaseResult.FAILED
    assert "Aborted" in result.message


def test_setup_rf_failure_notes_what_it_may_have_pushed(
    phase, mock_cavity, record
):
    mock_cavity.measured_loaded_q = 4.1e7
    mock_cavity.measured_scale_factor = 31.0
    mock_cavity.setup_rf.side_effect = CavityCharacterizationError("crashed")
    result = phase.execute_step("setup_rf")
    assert result.result == PhaseResult.FAILED
    notes = record.piezo_with_rf.notes
    assert "setup_rf() failed: crashed" in notes
    assert "4.100e+07" in notes
    assert "31.0" in notes
    assert "may have been pushed" in notes


def test_setup_rf_abort_notes_what_it_may_have_pushed(
    phase, mock_cavity, record
):
    mock_cavity.setup_rf.side_effect = CavityAbortError("abort")
    assert phase.execute_step("setup_rf").result == PhaseResult.FAILED
    assert "may have been pushed" in record.piezo_with_rf.notes


def test_setup_rf_failure_without_readback_adds_no_note(
    phase, mock_cavity, record
):
    mock_cavity.setup_rf.side_effect = CavityCharacterizationError("crashed")
    type(mock_cavity).measured_loaded_q = PropertyMock(
        side_effect=RuntimeError("no read")
    )
    result = phase.execute_step("setup_rf")
    assert result.result == PhaseResult.FAILED
    assert record.piezo_with_rf is None


def test_setup_piezo_abort_fails_with_rf_off(phase, mock_cavity):
    mock_cavity.piezo.enable.side_effect = CavityAbortError("abort")
    result = phase.execute_step("setup_piezo")
    assert result.result == PhaseResult.FAILED
    assert "Aborted during piezo setup — RF is off" in result.message
    mock_cavity.piezo.set_to_manual.assert_not_called()


def test_setup_piezo_enables_then_manual(phase, mock_cavity):
    order = []
    mock_cavity.piezo.enable.side_effect = lambda: order.append("enable")
    mock_cavity.piezo.set_to_manual.side_effect = lambda: order.append("manual")
    assert phase.execute_step("setup_piezo").result == PhaseResult.SUCCESS
    assert order == ["enable", "manual"]


def test_setup_piezo_enable_gives_up(phase, mock_cavity):
    mock_cavity.piezo.enable.side_effect = RuntimeError("failed to enable")
    result = phase.execute_step("setup_piezo")
    assert result.result == PhaseResult.FAILED
    mock_cavity.piezo.set_to_manual.assert_not_called()


@pytest.mark.parametrize("step", ["setup_rf", "setup_piezo"])
def test_dry_run_writes_nothing(mock_cavity, record, step):
    phase = make_phase(mock_cavity, record, dry_run=True)
    assert phase.execute_step(step).result == PhaseResult.SUCCESS
    mock_cavity.setup_rf.assert_not_called()
    mock_cavity.set_sel_mode.assert_not_called()
    mock_cavity.piezo.enable.assert_not_called()
    mock_cavity.piezo.set_to_manual.assert_not_called()


def test_steps_in_order(phase):
    assert phase.get_phase_steps() == [
        "verify_initial_state",
        "setup_rf",
        "setup_piezo",
        "check_detune",
        "start_test",
        "wait_for_completion",
        "read_results",
        "push_detune_gain",
        "record_results",
    ]


@pytest.mark.parametrize(
    "detune, invalid, expected",
    [
        (100.0, False, PhaseResult.SUCCESS),
        (-100.0, False, PhaseResult.SUCCESS),
        (101.0, False, PhaseResult.FAILED),
        (-101.0, False, PhaseResult.FAILED),
        (0.0, True, PhaseResult.FAILED),
    ],
)
def test_check_detune(phase, mock_cavity, detune, invalid, expected):
    mock_cavity.detune = detune
    mock_cavity.detune_invalid = invalid
    assert phase.execute_step("check_detune").result == expected


def test_start_test_writes_rfteststrt(phase, mock_cavity):
    result = phase.execute_step("start_test")
    assert result.result == PhaseResult.SUCCESS
    mock_cavity.piezo.withrf_run_check_pv_obj.put.assert_called_once_with(
        1, wait=False
    )


def test_start_test_refuses_while_a_test_is_running(phase, mock_cavity):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.return_value = RUNNING
    result = phase.execute_step("start_test")
    assert result.result == PhaseResult.FAILED
    mock_cavity.piezo.withrf_run_check_pv_obj.put.assert_not_called()


def test_wait_sees_running_then_complete(phase, mock_cavity):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.side_effect = [
        CRASH,
        RUNNING,
        RUNNING,
        COMPLETE,
    ]
    assert (
        phase.execute_step("wait_for_completion").result == PhaseResult.SUCCESS
    )


def test_wait_accepts_crash_as_finished(phase, mock_cavity):
    """Leaving Running ends the wait; read_results judges Crash."""
    mock_cavity.piezo.withrf_check_status_pv_obj.get.side_effect = [
        RUNNING,
        CRASH,
    ]
    assert (
        phase.execute_step("wait_for_completion").result == PhaseResult.SUCCESS
    )


def test_status_never_seen_running_fails(mock_cavity, record):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.return_value = COMPLETE
    phase = make_phase(mock_cavity, record)
    phase.limits.start_timeout_seconds = 3
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    assert "RFTESTSTS" in result.message
    assert mock_cavity.piezo.withrf_check_status_pv_obj.get.call_count == 3


def test_wait_times_out_while_running(mock_cavity, record):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.return_value = RUNNING
    phase = make_phase(mock_cavity, record)
    phase.limits.test_timeout_seconds = 5
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    assert "timed out" in result.message.lower()


def test_wait_abort_fails(phase, mock_cavity):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.return_value = RUNNING
    mock_cavity.check_abort.side_effect = [None, CavityAbortError("abort")]
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    assert "Abort" in result.message


@pytest.mark.parametrize(
    "step", ["check_detune", "start_test", "wait_for_completion"]
)
def test_dry_run_reads_and_writes_nothing(mock_cavity, record, step):
    phase = make_phase(mock_cavity, record, dry_run=True)
    assert phase.execute_step(step).result == PhaseResult.SUCCESS
    mock_cavity.piezo.withrf_run_check_pv_obj.put.assert_not_called()
    mock_cavity.piezo.withrf_check_status_pv_obj.get.assert_not_called()


def test_wait_resumes_after_running_on_retry(phase, mock_cavity):
    """A read error after Running was seen retries the wait for the finish."""
    status = mock_cavity.piezo.withrf_check_status_pv_obj.get
    status.side_effect = [RUNNING, Exception("CA timeout")]
    assert phase.execute_step("wait_for_completion").result == PhaseResult.RETRY
    status.side_effect = [COMPLETE]
    assert (
        phase.execute_step("wait_for_completion").result == PhaseResult.SUCCESS
    )


def test_check_detune_read_error_retries(phase, mock_cavity):
    type(mock_cavity).detune = PropertyMock(side_effect=RuntimeError("CA"))
    assert phase.execute_step("check_detune").result == PhaseResult.RETRY


def test_start_test_put_error_retries(phase, mock_cavity):
    mock_cavity.piezo.withrf_run_check_pv_obj.put.side_effect = RuntimeError(
        "CA"
    )
    assert phase.execute_step("start_test").result == PhaseResult.RETRY


def test_wait_first_read_error_retries(phase, mock_cavity):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.side_effect = RuntimeError(
        "CA"
    )
    assert phase.execute_step("wait_for_completion").result == PhaseResult.RETRY


PASS, WARNING, FAIL = 0, 1, 2


@pytest.fixture
def finished(mock_cavity):
    """A cavity whose with-RF test just completed with a Pass."""
    piezo = mock_cavity.piezo
    piezo.withrf_check_status_pv_obj.get.return_value = COMPLETE
    piezo.withrf_status_pv_obj.get.return_value = PASS
    piezo.amplifiergain_a_pv_obj.get.return_value = 1.05
    piezo.amplifiergain_b_pv_obj.get.return_value = 0.98
    piezo.detunegain_new_pv_obj.get.return_value = 0.85
    return mock_cavity


def test_read_pass_stores_gains(phase, finished, record):
    result = phase.execute_step("read_results")
    assert result.result == PhaseResult.SUCCESS
    data = record.piezo_with_rf
    assert (data.amplifier_gain_a, data.amplifier_gain_b) == (1.05, 0.98)
    assert data.detune_gain == 0.85
    assert data.rf_test_status == "Pass"
    assert data.passed


def test_read_warning_is_complete_not_passed(phase, finished, record):
    finished.piezo.withrf_status_pv_obj.get.return_value = WARNING
    assert phase.execute_step("read_results").result == PhaseResult.SUCCESS
    assert record.piezo_with_rf.is_complete
    assert not record.piezo_with_rf.passed


def test_read_fail_fails_and_stores_no_gains(phase, finished, record):
    finished.piezo.withrf_status_pv_obj.get.return_value = FAIL
    assert phase.execute_step("read_results").result == PhaseResult.FAILED
    assert record.piezo_with_rf is None or (
        record.piezo_with_rf.detune_gain is None
    )


def test_read_crash_fails(phase, finished):
    finished.piezo.withrf_check_status_pv_obj.get.return_value = CRASH
    result = phase.execute_step("read_results")
    assert result.result == PhaseResult.FAILED
    assert "Crash" in result.message


def test_reading_pushes_nothing(phase, finished):
    phase.execute_step("read_results")
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()
    finished.piezo.withrf_save_dfgain_pv_obj.put.assert_not_called()


def test_push_without_confirmation_is_refused(phase, finished):
    phase.execute_step("read_results")
    result = phase.execute_step("push_detune_gain")
    assert result.result == PhaseResult.FAILED
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()


def test_push_before_reading_fails(mock_cavity, record):
    phase = make_phase(mock_cavity, record, confirmed_detune_gain=0.85)
    assert phase.execute_step("push_detune_gain").result == PhaseResult.FAILED
    mock_cavity.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()


def test_confirming_another_value_does_not_push(finished, record):
    phase = make_phase(finished, record, confirmed_detune_gain=0.80)
    phase.execute_step("read_results")
    assert phase.execute_step("push_detune_gain").result == PhaseResult.FAILED
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()


def test_push_processes_push_then_save(finished, record):
    order = []
    piezo = finished.piezo
    piezo.withrf_push_dfgain_pv_obj.put.side_effect = (
        lambda v, **kw: order.append(("PUSH_DFGAIN.PROC", v))
    )
    piezo.withrf_save_dfgain_pv_obj.put.side_effect = (
        lambda v, **kw: order.append(("SAVE_DFGAIN.PROC", v))
    )
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    assert phase.execute_step("push_detune_gain").result == PhaseResult.SUCCESS
    assert order == [("PUSH_DFGAIN.PROC", 1), ("SAVE_DFGAIN.PROC", 1)]
    piezo.withrf_push_dfgain_pv_obj.put.assert_called_once_with(1, wait=False)
    piezo.withrf_save_dfgain_pv_obj.put.assert_called_once_with(1, wait=False)
    assert record.piezo_with_rf.detune_gain_pushed is True


def test_push_refuses_if_detune_gain_changed(finished, record):
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    finished.piezo.detunegain_new_pv_obj.get.return_value = 0.91
    result = phase.execute_step("push_detune_gain")
    assert result.result == PhaseResult.FAILED
    assert "DFGAIN_NEW" in result.message
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()


def test_push_refuses_if_a_new_test_is_running(finished, record):
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    finished.piezo.withrf_check_status_pv_obj.get.return_value = RUNNING
    assert phase.execute_step("push_detune_gain").result == PhaseResult.FAILED
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()


def test_warning_still_lets_the_operator_push(finished, record):
    finished.piezo.withrf_status_pv_obj.get.return_value = WARNING
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    assert phase.execute_step("push_detune_gain").result == PhaseResult.SUCCESS


def test_full_run_without_confirmation_never_pushes(phase, finished, record):
    # run() refuses to start unless the previous phase is complete.
    record.set_phase_status(
        CommissioningPhase.CAVITY_CHAR, PhaseStatus.COMPLETE
    )
    finished.piezo.withrf_check_status_pv_obj.get.side_effect = [
        COMPLETE,
        RUNNING,
        COMPLETE,
    ] + [COMPLETE] * 10
    assert phase.run() is False
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()
    assert not (
        phase.context.record.piezo_with_rf
        and phase.context.record.piezo_with_rf.detune_gain_pushed
    )


def test_full_run_with_confirmation_pushes_once(finished, record):
    finished.piezo.withrf_check_status_pv_obj.get.side_effect = [
        COMPLETE,
        RUNNING,
        COMPLETE,
    ] + [COMPLETE] * 10
    record.set_phase_status(
        CommissioningPhase.CAVITY_CHAR, PhaseStatus.COMPLETE
    )
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    assert phase.run() is True
    piezo = finished.piezo
    piezo.withrf_push_dfgain_pv_obj.put.assert_called_once_with(1, wait=False)
    piezo.withrf_save_dfgain_pv_obj.put.assert_called_once_with(1, wait=False)
    data = record.piezo_with_rf
    assert (data.amplifier_gain_a, data.amplifier_gain_b) == (1.05, 0.98)
    assert data.detune_gain == 0.85
    assert data.rf_test_status == "Pass"
    assert data.detune_gain_pushed is True
    assert data.passed


def test_record_results_is_a_no_op_step(phase, finished):
    result = phase.execute_step("record_results")
    assert result.result == PhaseResult.SUCCESS
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()


@pytest.mark.parametrize("step", ["read_results", "push_detune_gain"])
def test_dry_run_reads_results_and_pushes_nothing(finished, record, step):
    phase = make_phase(finished, record, dry_run=True)
    assert phase.execute_step(step).result == PhaseResult.SUCCESS
    finished.piezo.withrf_push_dfgain_pv_obj.put.assert_not_called()
    finished.piezo.withrf_save_dfgain_pv_obj.put.assert_not_called()


def test_save_failure_after_push_fails_without_retry(finished, record):
    """PUSH_DFGAIN processed means the gain is live; a retry must not run."""
    piezo = finished.piezo
    piezo.withrf_save_dfgain_pv_obj.put.side_effect = RuntimeError("CA")
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    result = phase.execute_step("push_detune_gain")
    assert result.result == PhaseResult.FAILED
    assert "SAVE_DFGAIN" in result.message
    assert piezo.withrf_push_dfgain_pv_obj.put.call_count == 1
    assert record.piezo_with_rf.detune_gain_pushed is True


def test_push_failure_retries_and_saves_nothing(finished, record):
    piezo = finished.piezo
    piezo.withrf_push_dfgain_pv_obj.put.side_effect = RuntimeError("CA")
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    assert phase.execute_step("push_detune_gain").result == PhaseResult.RETRY
    piezo.withrf_save_dfgain_pv_obj.put.assert_not_called()
    assert record.piezo_with_rf.detune_gain_pushed is False


def test_warning_then_confirmed_push_is_pushed_not_passed(finished, record):
    finished.piezo.withrf_status_pv_obj.get.return_value = WARNING
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    assert phase.execute_step("push_detune_gain").result == PhaseResult.SUCCESS
    data = record.piezo_with_rf
    assert data.rf_test_status == "Warning"
    assert data.detune_gain_pushed is True
    assert data.passed is False


def test_rerun_that_fails_after_a_push_keeps_a_note(finished, record):
    phase = make_phase(finished, record, confirmed_detune_gain=0.85)
    phase.execute_step("read_results")
    assert phase.execute_step("push_detune_gain").result == PhaseResult.SUCCESS
    finished.piezo.withrf_status_pv_obj.get.return_value = FAIL
    rerun = make_phase(finished, record)
    assert rerun.execute_step("read_results").result == PhaseResult.FAILED
    data = record.piezo_with_rf
    assert data.amplifier_gain_a is None
    assert data.detune_gain is None
    assert data.rf_test_status is None
    assert data.detune_gain_pushed is False
    assert "Earlier run pushed detune gain 0.850000 (Pass)" in data.notes
