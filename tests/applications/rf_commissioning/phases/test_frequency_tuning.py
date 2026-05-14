"""Tests for Frequency Tuning Phase."""

import time
from datetime import datetime
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseCheckpoint,
)
from sc_linac_physics.applications.rf_commissioning.phases.frequency_tuning import (
    FrequencyTuningLimits,
    FrequencyTuningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    StepperError,
)

# ---------------------------------------------------------------------------
# Autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_stepper():
    stepper = Mock()
    stepper.motor_moving = False
    stepper.on_limit_switch = False
    stepper.hz_per_microstep = 2.0
    stepper.steps_cold_landing_pv = "ACCL:L1B:0210:STEP:NSTEPS_COLD"
    return stepper


@pytest.fixture
def mock_cavity(mock_stepper):
    cavity = Mock()
    cavity.stepper_tuner = mock_stepper
    cavity.stepper_temp_pv = "ACCL:L1B:0210:STEPTEMP"
    cavity.detune_invalid = False
    cavity.detune_chirp = 5000.0
    return cavity


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


@pytest.fixture
def context(mock_cavity, record):
    return PhaseContext(
        record=record,
        operator="test_op",
        parameters={"cavity": mock_cavity},
    )


@pytest.fixture
def fast_limits():
    return FrequencyTuningLimits(
        tolerance_hz=500.0,
        probe_steps=10,
        max_steps_per_move=50,
        temp_limit_c=70.0,
        max_total_steps=10_000,
        cool_down_retries=2,
        cool_down_interval=0.0,
        motor_start_wait=0.0,
        motor_poll_interval=0.0,
    )


@pytest.fixture
def phase(context, fast_limits):
    p = FrequencyTuningPhase(context, limits=fast_limits)
    return p


def _setup_phase(phase, temp_c=25.0):
    """Call validate_prerequisites and inject pre-built PV mocks."""
    phase.validate_prerequisites()
    phase._stepper_temp_pv_obj = Mock()
    phase._stepper_temp_pv_obj.get.return_value = temp_c
    phase._df_cold_pv_obj = Mock()
    phase._nsteps_cold_pv_obj = Mock()
    phase._hz_per_microstep = 2.0
    return phase


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_phase_type(phase):
    assert phase.phase_type == CommissioningPhase.FREQUENCY_TUNING


def test_get_phase_steps(phase):
    assert phase.get_phase_steps() == [
        "verify_initial_state",
        "record_cold_landing",
        "probe_stepper_direction",
        "tune_to_resonance",
        "record_results",
    ]


# ---------------------------------------------------------------------------
# validate_prerequisites
# ---------------------------------------------------------------------------


def test_validate_prerequisites_success(phase, mock_cavity):
    ok, _ = phase.validate_prerequisites()
    assert ok is True
    assert phase.cavity is mock_cavity


def test_validate_prerequisites_no_cavity(context):
    context.parameters["cavity"] = None
    ok, msg = FrequencyTuningPhase(context).validate_prerequisites()
    assert ok is False
    assert "cavity" in msg.lower()


def test_validate_prerequisites_no_stepper(context):
    context.parameters["cavity"].stepper_tuner = None
    ok, _ = FrequencyTuningPhase(context).validate_prerequisites()
    assert ok is False


def test_validate_prerequisites_no_temp_pv(context):
    context.parameters["cavity"].stepper_temp_pv = ""
    ok, _ = FrequencyTuningPhase(context).validate_prerequisites()
    assert ok is False


# ---------------------------------------------------------------------------
# execute_step dispatch
# ---------------------------------------------------------------------------


def test_execute_step_unknown_step(phase):
    _setup_phase(phase)
    result = phase.execute_step("nonexistent_step")
    assert result.result == PhaseResult.FAILED
    assert "Unknown step" in result.message


def test_execute_step_without_cavity_raises(phase):
    with pytest.raises(Exception):
        phase.execute_step("verify_initial_state")


# ---------------------------------------------------------------------------
# verify_initial_state
# ---------------------------------------------------------------------------


def test_verify_initial_state_dry_run(context, fast_limits):
    context.dry_run = True
    p = FrequencyTuningPhase(context, limits=fast_limits)
    p.validate_prerequisites()
    result = p._verify_initial_state()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_verify_initial_state_motor_already_moving(phase, mock_stepper):
    _setup_phase(phase)
    mock_stepper.motor_moving = True
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "moving" in result.message.lower()


def test_verify_initial_state_on_limit_switch(phase, mock_stepper):
    _setup_phase(phase)
    mock_stepper.on_limit_switch = True
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "limit switch" in result.message.lower()


def test_verify_initial_state_detune_invalid(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.detune_invalid = True
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "chirp" in result.message.lower()


def test_verify_initial_state_read_exception_retries(phase, mock_cavity):
    _setup_phase(phase, temp_c=25.0)
    phase._stepper_temp_pv_obj.get.side_effect = RuntimeError("PV timeout")
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.RETRY


def test_verify_initial_state_success(phase):
    _setup_phase(phase, temp_c=30.0)
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["initial_temp_c"] == 30.0
    assert "initial_detune_hz" in result.data


# ---------------------------------------------------------------------------
# record_cold_landing
# ---------------------------------------------------------------------------


def test_record_cold_landing_dry_run(context, fast_limits):
    context.dry_run = True
    p = FrequencyTuningPhase(context, limits=fast_limits)
    p.validate_prerequisites()
    result = p._record_cold_landing()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_record_cold_landing_success(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 8000.0
    result = phase._record_cold_landing()
    assert result.result == PhaseResult.SUCCESS
    assert "hz_per_microstep" not in result.data
    assert "cold_landing_steps" not in result.data
    assert result.data["initial_detune_hz"] == 8000.0
    assert "initial_timestamp" in result.data
    phase._df_cold_pv_obj.put.assert_called_once_with(8000.0)


def test_record_cold_landing_df_cold_write_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 8000.0
    phase._df_cold_pv_obj.put.side_effect = RuntimeError("PV timeout")
    result = phase._record_cold_landing()
    assert result.result == PhaseResult.RETRY
    assert "DF_COLD" in result.message


def test_record_cold_landing_detune_read_error_retries(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.detune_chirp = property(
        Mock(side_effect=RuntimeError("PV timeout"))
    )
    # Simulate detune_chirp raising on access
    type(phase.cavity).detune_chirp = property(
        Mock(side_effect=RuntimeError("PV timeout"))
    )
    result = phase._record_cold_landing()
    assert result.result == PhaseResult.RETRY


# ---------------------------------------------------------------------------
# probe_stepper_direction
# ---------------------------------------------------------------------------


def test_probe_stepper_direction_dry_run(context, fast_limits):
    context.dry_run = True
    p = FrequencyTuningPhase(context, limits=fast_limits)
    p.validate_prerequisites()
    result = p._probe_stepper_direction()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_probe_stepper_direction_positive_increases_frequency(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(steps, *args, **kwargs):
        if steps > 0:
            mock_cavity.detune_chirp = (
                1500.0  # freq went up after positive move
            )
        else:
            mock_cavity.detune_chirp = 1000.0  # restored

    mock_stepper.move.side_effect = after_move

    result = phase._probe_stepper_direction()

    assert result.result == PhaseResult.SUCCESS
    assert result.data["positive_step_increases_frequency"] is True
    # delta=500, probe_steps=10 (fast_limits) → 50 Hz/step
    assert result.data["hz_per_microstep"] == pytest.approx(50.0)
    assert phase._hz_per_microstep == pytest.approx(50.0)
    mock_stepper.hz_per_microstep_pv_obj.put.assert_called_once_with(
        pytest.approx(50.0)
    )
    assert mock_stepper.move.call_count == 2
    assert mock_stepper.move.call_args_list[0][0][0] > 0
    assert mock_stepper.move.call_args_list[1][0][0] < 0


def test_probe_stepper_direction_positive_decreases_frequency(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(steps, *args, **kwargs):
        if steps > 0:
            mock_cavity.detune_chirp = (
                800.0  # freq went down after positive move
            )
        else:
            mock_cavity.detune_chirp = 1000.0

    mock_stepper.move.side_effect = after_move

    result = phase._probe_stepper_direction()

    assert result.result == PhaseResult.SUCCESS
    assert result.data["positive_step_increases_frequency"] is False
    # delta=-200, probe_steps=10 → abs = 20 Hz/step; signed written to PV is -20
    assert result.data["hz_per_microstep"] == pytest.approx(20.0)
    mock_stepper.hz_per_microstep_pv_obj.put.assert_called_once_with(
        pytest.approx(-20.0)
    )


def test_probe_stepper_direction_delta_too_small(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(steps, *args, **kwargs):
        if steps > 0:
            mock_cavity.detune_chirp = 1001.0  # barely any change

    mock_stepper.move.side_effect = after_move

    result = phase._probe_stepper_direction()

    assert result.result == PhaseResult.FAILED
    assert "minimum" in result.message.lower()
    assert mock_stepper.hz_per_microstep_pv_obj.put.call_count == 0


def test_probe_stepper_direction_stepper_error(phase, mock_stepper):
    _setup_phase(phase)
    mock_stepper.move.side_effect = StepperError("limit switch")
    result = phase._probe_stepper_direction()
    assert result.result == PhaseResult.FAILED
    assert "limit switch" in result.message.lower()


def test_probe_stepper_direction_transient_error_retries(phase, mock_stepper):
    _setup_phase(phase)
    mock_stepper.move.side_effect = RuntimeError("transient")
    result = phase._probe_stepper_direction()
    assert result.result == PhaseResult.RETRY


# ---------------------------------------------------------------------------
# tune_to_resonance
# ---------------------------------------------------------------------------


def test_tune_to_resonance_dry_run(context, fast_limits):
    context.dry_run = True
    p = FrequencyTuningPhase(context, limits=fast_limits)
    p.validate_prerequisites()
    result = p._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_tune_to_resonance_already_at_resonance(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 100.0  # within tolerance
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["total_steps"] == 0


def test_tune_to_resonance_converges_one_iteration(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 5000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 100.0

    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()

    assert result.result == PhaseResult.SUCCESS
    assert result.data["total_steps"] > 0
    mock_stepper.move.assert_called_once()


def test_tune_to_resonance_moves_positive_for_positive_detune(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move

    phase._tune_to_resonance()

    first_step_arg = mock_stepper.move.call_args_list[0][0][0]
    assert first_step_arg > 0


def test_tune_to_resonance_moves_negative_for_negative_detune(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = -1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move

    phase._tune_to_resonance()

    first_step_arg = mock_stepper.move.call_args_list[0][0][0]
    assert first_step_arg < 0


def test_tune_to_resonance_max_steps_exceeded(phase, mock_cavity):
    _setup_phase(phase)
    phase.limits.max_total_steps = 0
    mock_cavity.detune_chirp = 5000.0
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "max step limit" in result.message.lower()


def test_tune_to_resonance_temperature_over_limit_then_cools(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    phase.limits.temp_limit_c = 70.0

    # Reads: (1) initial peak_temp, (2) loop-iter-1 first check = over limit,
    # (3) cool-down retry = OK, (4) loop-iter-2 check after move resolves detune.
    temp_values = iter([25.0, 80.0, 60.0, 25.0])
    phase._stepper_temp_pv_obj.get.side_effect = lambda: next(temp_values)

    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS


def test_tune_to_resonance_temperature_never_cools(phase, mock_cavity):
    _setup_phase(phase)
    phase.limits.temp_limit_c = 70.0
    phase.limits.cool_down_retries = 2

    # Always over limit
    phase._stepper_temp_pv_obj.get.return_value = 85.0
    mock_cavity.detune_chirp = 5000.0

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "temp" in result.message.lower()


def test_tune_to_resonance_abort_requested(phase, mock_cavity, context):
    _setup_phase(phase)
    context.request_abort()
    mock_cavity.detune_chirp = 5000.0
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "abort" in result.message.lower()


def test_tune_to_resonance_stepper_error(phase, mock_cavity, mock_stepper):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0
    mock_stepper.move.side_effect = StepperError("limit switch")
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED


def test_tune_to_resonance_detune_read_error_retries(phase, mock_cavity):
    # Simulate PV read failure on temp: phase should return RETRY.
    _setup_phase(phase)
    # Initial read (before loop) silently swallows errors, loop read will RETRY.
    phase._stepper_temp_pv_obj.get.side_effect = RuntimeError("PV timeout")
    mock_cavity.detune_chirp = 5000.0
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.RETRY


def test_tune_to_resonance_missing_hz_per_microstep(phase, mock_cavity):
    _setup_phase(phase)
    phase._hz_per_microstep = None
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "probe_stepper_direction" in result.message


def test_tune_to_resonance_tracks_peak_temp(phase, mock_cavity, mock_stepper):
    _setup_phase(phase)
    phase.limits.temp_limit_c = 100.0

    # Reads: (1) initial peak_temp, then one per loop iteration (3 iterations
    # before detune hits tolerance), plus one final read after last move.
    temp_values = iter([30.0, 55.0, 40.0, 25.0])
    phase._stepper_temp_pv_obj.get.side_effect = lambda: next(temp_values)

    detunes = [2000.0, 1000.0, 100.0]
    move_count = [0]

    def after_move(*args, **kwargs):
        move_count[0] += 1
        mock_cavity.detune_chirp = detunes[move_count[0]]

    mock_cavity.detune_chirp = detunes[0]
    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS
    assert "total_steps" in result.data


def test_tune_to_resonance_writes_nsteps_cold(phase, mock_cavity, mock_stepper):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()

    assert result.result == PhaseResult.SUCCESS
    # cold_landing_steps in data should be the negated signed total
    assert "cold_landing_steps" in result.data
    assert result.data["cold_landing_steps"] == -result.data["total_steps"]
    phase._nsteps_cold_pv_obj.put.assert_called_once_with(
        result.data["cold_landing_steps"]
    )


def test_tune_to_resonance_nsteps_cold_write_error(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move
    phase._nsteps_cold_pv_obj.put.side_effect = RuntimeError("PV timeout")

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.RETRY
    assert "NSTEPS_COLD" in result.message


# ---------------------------------------------------------------------------
# record_results
# ---------------------------------------------------------------------------


def test_record_results_success(phase):
    _setup_phase(phase)
    result = phase._record_results()
    assert result.result == PhaseResult.SUCCESS


# ---------------------------------------------------------------------------
# finalize_phase
# ---------------------------------------------------------------------------


def _make_checkpoint(phase_type, step_name, measurements):
    return PhaseCheckpoint(
        phase=phase_type,
        timestamp=datetime.now(),
        operator="op",
        step_name=step_name,
        success=True,
        measurements=measurements,
    )


def test_finalize_phase_populates_frequency_tuning_data(phase, record):
    _setup_phase(phase)
    phase._history_start = 0

    record.phase_history.extend(
        [
            _make_checkpoint(
                CommissioningPhase.FREQUENCY_TUNING,
                "record_cold_landing",
                {
                    "initial_detune_hz": 8000.0,
                    "initial_timestamp": datetime.now().isoformat(),
                },
            ),
            _make_checkpoint(
                CommissioningPhase.FREQUENCY_TUNING,
                "probe_stepper_direction",
                {
                    "d0_hz": 8000.0,
                    "d1_hz": 8200.0,
                    "delta_hz": 200.0,
                    "positive_step_increases_frequency": True,
                    "hz_per_microstep": 2.0,
                },
            ),
            _make_checkpoint(
                CommissioningPhase.FREQUENCY_TUNING,
                "tune_to_resonance",
                {
                    "total_steps": 4000,
                    "cold_landing_steps": -4000,
                    "final_timestamp": datetime.now().isoformat(),
                },
            ),
        ]
    )

    phase.finalize_phase()

    ft = record.frequency_tuning
    assert ft is not None
    assert ft.initial_detune_hz == 8000.0
    assert ft.steps_to_resonance == 4000
    assert ft.positive_step_increases_frequency is True
    assert ft.hz_per_microstep == 2.0
    assert ft.cold_landing_steps == -4000
    assert ft.initial_timestamp is not None
    assert ft.final_timestamp is not None


def test_finalize_phase_no_checkpoints_creates_defaults(phase, record):
    _setup_phase(phase)
    phase._history_start = 0

    phase.finalize_phase()

    ft = record.frequency_tuning
    assert ft is not None
    assert ft.initial_detune_hz is None
    assert ft.steps_to_resonance is None
    assert ft.positive_step_increases_frequency is None
