"""Tests for SSA Calibration Phase."""

import time
from datetime import datetime
from unittest.mock import Mock, PropertyMock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseCheckpoint,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.ssa_char import (
    SSACalLimits,
    SSACharPhase,
)
from sc_linac_physics.utils.sc_linac.linac_utils import SSAFaultError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)


@pytest.fixture
def mock_ssa():
    ssa = Mock()
    ssa.calibration_running = False
    ssa.calibration_crashed = False
    ssa.calibration_result_good = True
    ssa.measured_slope = 1.02345
    ssa.measured_slope_in_tolerance = True
    ssa.drive_max = 0.670
    ssa.max_fwd_pwr = 4500.0
    ssa.fwd_power_lower_limit = 4000.0
    return ssa


@pytest.fixture
def mock_cavity(mock_ssa):
    cavity = Mock()
    cavity.ssa = mock_ssa
    return cavity


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


@pytest.fixture
def context(mock_cavity, record):
    return PhaseContext(
        record=record,
        operator="test_op",
        parameters={"cavity": mock_cavity, "drive_max": 0.670},
    )


@pytest.fixture
def phase(context):
    return SSACharPhase(
        context,
        limits=SSACalLimits(
            cal_timeout=0.1, poll_interval=0.0, post_start_delay=0.0
        ),
    )


# ------------------------------------------------------------------
# Metadata
# ------------------------------------------------------------------


def test_phase_type(phase):
    assert phase.phase_type == CommissioningPhase.SSA_CHAR


def test_get_phase_steps(phase):
    assert phase.get_phase_steps() == [
        "verify_initial_state",
        "set_drive_max",
        "reset_and_power_on",
        "start_calibration",
        "wait_for_completion",
        "validate_and_push",
    ]


# ------------------------------------------------------------------
# validate_prerequisites
# ------------------------------------------------------------------


def test_validate_prerequisites_success(phase, mock_cavity):
    ok, _ = phase.validate_prerequisites()
    assert ok is True
    assert phase.cavity is mock_cavity


def test_validate_prerequisites_no_cavity(context):
    context.parameters["cavity"] = None
    ok, msg = SSACharPhase(context).validate_prerequisites()
    assert ok is False
    assert "cavity" in msg.lower()


def test_validate_prerequisites_no_ssa(context):
    context.parameters["cavity"].ssa = None
    ok, _ = SSACharPhase(context).validate_prerequisites()
    assert ok is False


def test_validate_prerequisites_no_drive_max(context):
    del context.parameters["drive_max"]
    ok, _ = SSACharPhase(context).validate_prerequisites()
    assert ok is False


def test_validate_prerequisites_drive_max_out_of_range(context):
    context.parameters["drive_max"] = 1.5
    ok, msg = SSACharPhase(context).validate_prerequisites()
    assert ok is False
    assert "drive_max" in msg


def test_validate_prerequisites_drive_max_zero(context):
    context.parameters["drive_max"] = 0.0
    ok, _ = SSACharPhase(context).validate_prerequisites()
    assert ok is False


# ------------------------------------------------------------------
# execute_step dispatch
# ------------------------------------------------------------------


def test_execute_step_unknown_step(phase, mock_cavity):
    phase.cavity = mock_cavity
    result = phase.execute_step("nonexistent_step")
    assert result.result == PhaseResult.FAILED
    assert "Unknown step" in result.message


def test_execute_step_without_cavity_raises(phase):
    phase.cavity = None
    with pytest.raises(Exception):
        phase.execute_step("verify_initial_state")


# ------------------------------------------------------------------
# verify_initial_state
# ------------------------------------------------------------------


def test_verify_initial_state_dry_run(context):
    context.dry_run = True
    p = SSACharPhase(context)
    p.validate_prerequisites()
    result = p._verify_initial_state()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_verify_initial_state_calibration_already_running(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_running = True
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "already running" in result.message


def test_verify_initial_state_read_exception_retries(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_running = False
    type(mock_ssa).current_slope = PropertyMock(
        side_effect=RuntimeError("read fail")
    )
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.RETRY


def test_verify_initial_state_success(phase):
    phase.validate_prerequisites()
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.SUCCESS
    assert "initial_current_slope" in result.data


# ------------------------------------------------------------------
# set_drive_max
# ------------------------------------------------------------------


def test_set_drive_max_dry_run(context):
    context.dry_run = True
    p = SSACharPhase(context)
    p.validate_prerequisites()
    result = p._set_drive_max()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_set_drive_max_success(phase, mock_ssa):
    phase.validate_prerequisites()
    result = phase._set_drive_max()
    assert result.result == PhaseResult.SUCCESS
    assert mock_ssa.drive_max == 0.670


# ------------------------------------------------------------------
# reset_and_power_on
# ------------------------------------------------------------------


def test_reset_and_power_on_dry_run(context):
    context.dry_run = True
    p = SSACharPhase(context)
    p.validate_prerequisites()
    assert p._reset_and_power_on().result == PhaseResult.SUCCESS


def test_reset_and_power_on_success(phase, mock_cavity):
    phase.validate_prerequisites()
    result = phase._reset_and_power_on()
    assert result.result == PhaseResult.SUCCESS
    mock_cavity.ssa.reset.assert_called_once()
    mock_cavity.ssa.turn_on.assert_called_once()
    mock_cavity.reset_interlocks.assert_called_once()


def test_reset_and_power_on_ssa_fault_error(phase, mock_cavity):
    phase.validate_prerequisites()
    mock_cavity.ssa.reset.side_effect = SSAFaultError("fault")
    result = phase._reset_and_power_on()
    assert result.result == PhaseResult.FAILED


def test_reset_and_power_on_transient_error_retries(phase, mock_cavity):
    phase.validate_prerequisites()
    mock_cavity.ssa.reset.side_effect = RuntimeError("transient")
    result = phase._reset_and_power_on()
    assert result.result == PhaseResult.RETRY


# ------------------------------------------------------------------
# start_calibration
# ------------------------------------------------------------------


def test_start_calibration_dry_run(context):
    context.dry_run = True
    p = SSACharPhase(context)
    p.validate_prerequisites()
    assert p._start_calibration().result == PhaseResult.SUCCESS


def test_start_calibration_crashes_immediately(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_crashed = True
    result = phase._start_calibration()
    assert result.result == PhaseResult.FAILED
    assert "crashed" in result.message.lower()


def test_start_calibration_success(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_crashed = False
    result = phase._start_calibration()
    assert result.result == PhaseResult.SUCCESS
    mock_ssa.start_calibration.assert_called_once()


# ------------------------------------------------------------------
# wait_for_completion
# ------------------------------------------------------------------


def test_wait_for_completion_dry_run(context):
    context.dry_run = True
    p = SSACharPhase(context)
    p.validate_prerequisites()
    result = p._wait_for_completion()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True
    assert result.data["slope_new"] == 1.02345


def test_wait_for_completion_already_done(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_running = False
    result = phase._wait_for_completion()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["slope_new"] == mock_ssa.measured_slope


def test_wait_for_completion_timeout(context, mock_ssa):
    p = SSACharPhase(
        context,
        limits=SSACalLimits(
            cal_timeout=0.1, poll_interval=0.1, post_start_delay=0.0
        ),
    )
    p.validate_prerequisites()
    mock_ssa.calibration_running = True
    result = p._wait_for_completion()
    assert result.result == PhaseResult.FAILED
    assert "timed out" in result.message.lower()


def test_wait_for_completion_abort_while_running(context, mock_ssa):
    p = SSACharPhase(
        context,
        limits=SSACalLimits(
            cal_timeout=100.0, poll_interval=0.0, post_start_delay=0.0
        ),
    )
    p.validate_prerequisites()
    mock_ssa.calibration_running = True
    context.request_abort()
    result = p._wait_for_completion()
    assert result.result == PhaseResult.FAILED
    assert "Abort" in result.message


def test_wait_for_completion_slope_read_error(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_running = False
    type(mock_ssa).measured_slope = PropertyMock(
        side_effect=RuntimeError("read error")
    )
    result = phase._wait_for_completion()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["slope_new"] is None


# ------------------------------------------------------------------
# validate_and_push
# ------------------------------------------------------------------


def test_validate_and_push_dry_run(context):
    context.dry_run = True
    p = SSACharPhase(context)
    p.validate_prerequisites()
    result = p._validate_and_push()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["calibration_passed"] is True


def test_validate_and_push_crashed(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_crashed = True
    result = phase._validate_and_push()
    assert result.result == PhaseResult.FAILED


def test_validate_and_push_bad_calstat(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.calibration_result_good = False
    result = phase._validate_and_push()
    assert result.result == PhaseResult.FAILED


def test_validate_and_push_low_forward_power(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.max_fwd_pwr = 100.0
    result = phase._validate_and_push()
    assert result.result == PhaseResult.FAILED
    assert "power" in result.message.lower()


def test_validate_and_push_slope_out_of_tolerance(phase, mock_ssa):
    phase.validate_prerequisites()
    mock_ssa.measured_slope_in_tolerance = False
    result = phase._validate_and_push()
    assert result.result == PhaseResult.FAILED
    assert "tolerance" in result.message.lower()


def test_validate_and_push_success(phase, mock_ssa, mock_cavity):
    phase.validate_prerequisites()
    result = phase._validate_and_push()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["calibration_passed"] is True
    mock_cavity.push_ssa_slope.assert_called_once()
    assert result.data["slope_new"] == mock_ssa.measured_slope


def test_validate_and_push_post_push_readback_error(phase, mock_ssa):
    phase.validate_prerequisites()
    call_count = {"n": 0}
    original_value = mock_ssa.measured_slope

    def _slope():
        call_count["n"] += 1
        if call_count["n"] > 1:
            raise RuntimeError("readback fail")
        return original_value

    type(mock_ssa).measured_slope = PropertyMock(side_effect=_slope)
    result = phase._validate_and_push()
    assert result.result == PhaseResult.SUCCESS


# ------------------------------------------------------------------
# finalize_phase
# ------------------------------------------------------------------


def test_finalize_phase_uses_validate_and_push_checkpoint(phase, record):
    phase.validate_prerequisites()
    phase._history_start = 0

    checkpoint = PhaseCheckpoint(
        phase=CommissioningPhase.SSA_CHAR,
        timestamp=datetime.now(),
        operator="op",
        step_name="validate_and_push",
        success=True,
        measurements={
            "slope_new": 1.05,
            "max_fwd_pwr": 4500.0,
            "max_drive": 0.670,
            "calibration_passed": True,
        },
    )
    record.phase_history.append(checkpoint)

    phase.finalize_phase()

    assert record.ssa_char is not None
    assert record.ssa_char.slope_new == 1.05
    assert record.ssa_char.calibration_passed is True
    assert record.ssa_char.max_drive == 0.670


def test_finalize_phase_no_checkpoint_creates_default(phase, record):
    phase.validate_prerequisites()
    phase._history_start = 0

    phase.finalize_phase()

    assert record.ssa_char is not None
    assert record.ssa_char.calibration_passed is False
