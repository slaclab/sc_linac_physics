"""Tests for the Piezo with RF phase.

The phase drives the cavity through Cavity/Piezo helpers, so these assert
what it calls and in what order, that a dry run writes nothing, and where it
refuses to go on.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock, PropertyMock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PiezoWithRFTest,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.phases import (
    piezo_with_rf as piezo_with_rf_module,
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


class FakeClock:
    """Stands in for the phase module's ``time``: sleep advances monotonic."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(piezo_with_rf_module, "time", fake)
    return fake


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
    # Good results, but too old to skip: setup_rf re-runs both by default.
    cavity.ssa.calibration_timestamp = datetime.now() - timedelta(hours=2)
    cavity.ssa.calibration_result_good = True
    cavity.characterization_timestamp = datetime.now() - timedelta(hours=2)
    cavity.characterization_status = COMPLETE
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


def test_verify_initial_state_refuses_a_running_test(phase, mock_cavity):
    """Refused before setup_rf, which would turn RF off under the test."""
    mock_cavity.piezo.withrf_check_status_pv_obj.get.return_value = RUNNING
    result = phase.execute_step("verify_initial_state")
    assert result.result == PhaseResult.FAILED
    assert "already running" in result.message
    mock_cavity.setup_rf.assert_not_called()


def test_setup_rf_runs_setup_rf_then_sel(phase, mock_cavity):
    order = []
    mock_cavity.setup_rf.side_effect = lambda amp, **_: order.append(
        ("setup_rf", amp)
    )
    mock_cavity.set_sel_mode.side_effect = lambda: order.append("sel")

    result = phase.execute_step("setup_rf")

    assert result.result == PhaseResult.SUCCESS
    assert order == [("setup_rf", pytest.approx(6.5 * 1.038)), "sel"]


def test_setup_rf_reruns_old_results(phase, mock_cavity, record):
    phase.execute_step("setup_rf")
    mock_cavity.setup_rf.assert_called_once_with(
        pytest.approx(6.5 * 1.038), calibrate_ssa=True, characterize=True
    )
    assert "re-ran SSA calibration" in record.piezo_with_rf.notes
    assert "re-ran characterization" in record.piezo_with_rf.notes


def test_setup_rf_keeps_good_results_from_the_last_hour(
    phase, mock_cavity, record
):
    recent = datetime.now() - timedelta(minutes=30)
    mock_cavity.ssa.calibration_timestamp = recent
    mock_cavity.characterization_timestamp = recent
    result = phase.execute_step("setup_rf")
    assert result.result == PhaseResult.SUCCESS
    mock_cavity.setup_rf.assert_called_once_with(
        pytest.approx(6.5 * 1.038), calibrate_ssa=False, characterize=False
    )
    assert "kept the SSA calibration" in record.piezo_with_rf.notes
    assert "kept the characterization" in record.piezo_with_rf.notes


@pytest.mark.parametrize(
    "attr, value, kwarg",
    [
        ("ssa.calibration_result_good", False, "calibrate_ssa"),
        ("characterization_status", CRASH, "characterize"),
    ],
)
def test_setup_rf_reruns_a_recent_bad_result(
    phase, mock_cavity, attr, value, kwarg
):
    recent = datetime.now() - timedelta(minutes=30)
    mock_cavity.ssa.calibration_timestamp = recent
    mock_cavity.characterization_timestamp = recent
    target = mock_cavity
    *path, last = attr.split(".")
    for name in path:
        target = getattr(target, name)
    setattr(target, last, value)
    phase.execute_step("setup_rf")
    assert mock_cavity.setup_rf.call_args.kwargs[kwarg] is True


def test_setup_rf_retries_when_a_timestamp_read_fails(phase, mock_cavity):
    type(mock_cavity.ssa).calibration_timestamp = PropertyMock(
        side_effect=RuntimeError("CALTS disconnected")
    )
    result = phase.execute_step("setup_rf")
    assert result.result == PhaseResult.RETRY
    mock_cavity.setup_rf.assert_not_called()


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


def test_status_never_seen_running_fails(mock_cavity, record, clock):
    mock_cavity.piezo.withrf_check_status_pv_obj.get.return_value = COMPLETE
    phase = make_phase(mock_cavity, record)
    phase.limits.start_timeout_seconds = 3
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    assert "RFTESTSTS" in result.message
    # Reads at t = 0, 1, 2 and 3 s; gives up at the deadline.
    assert mock_cavity.piezo.withrf_check_status_pv_obj.get.call_count == 4
    assert clock.now == 3


def test_slow_reads_do_not_stretch_the_timeout(mock_cavity, record, clock):
    """Each RFTESTSTS read takes 2 s; the 3 s limit is elapsed time."""

    def slow_read():
        clock.now += 2
        return COMPLETE

    mock_cavity.piezo.withrf_check_status_pv_obj.get.side_effect = slow_read
    phase = make_phase(mock_cavity, record)
    phase.limits.start_timeout_seconds = 3
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    # At most one read past the deadline.
    assert clock.now <= 3 + 2


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
