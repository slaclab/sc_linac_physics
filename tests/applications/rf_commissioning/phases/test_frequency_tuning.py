"""Tests for Frequency Tuning Phase."""

import time
from datetime import datetime
from unittest.mock import Mock, patch

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
    CavityFaultError,
    DetuneError,
    StepperError,
    TUNE_CONFIG_COLD_VALUE,
    TUNE_CONFIG_RESONANCE_VALUE,
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
    stepper.max_steps = 50
    stepper.steps_cold_landing_pv = "ACCL:L1B:0210:STEP:NSTEPS_COLD"
    return stepper


@pytest.fixture
def mock_cavity(mock_stepper):
    cavity = Mock()
    cavity.stepper_tuner = mock_stepper
    cavity.stepper_temp_pv = "ACCL:L1B:0210:STEPTEMP"
    cavity.detune_invalid = False
    cavity.detune_chirp = 5000.0
    cavity.is_online = True
    # Cavities launch at cold landing (COLD == 1).
    cavity.tune_config_pv_obj.get.return_value = TUNE_CONFIG_COLD_VALUE
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
        temp_limit_c=70.0,
        max_total_steps=10_000,
    )


@pytest.fixture
def phase(context, fast_limits):
    p = FrequencyTuningPhase(context, limits=fast_limits)
    return p


def _seed_cold_landing(phase, df_cold_hz=5000.0):
    """Record a cold-landing checkpoint and make DF_COLD read back matching it,
    so the DF_COLD gate in _tune_to_resonance is satisfied."""
    phase.context.record.phase_history.append(
        PhaseCheckpoint(
            phase=phase.phase_type,
            timestamp=datetime.now(),
            operator="test_op",
            step_name="record_cold_landing",
            success=True,
            measurements={"df_cold_hz": df_cold_hz},
        )
    )
    phase.cavity.df_cold_pv_obj.get.return_value = df_cold_hz


def _setup_phase(phase, temp_c=25.0, initial_signed_steps=0, seed_cold=True):
    """Call validate_prerequisites and inject pre-built PV mocks."""
    phase.validate_prerequisites()
    # STEPTEMP / DF_COLD / signed-step PVs now come from the cavity+stepper
    # accessors (mock_cavity is a Mock, so these are auto-mocks).
    phase.cavity.stepper_temp_pv_obj.get.return_value = temp_c
    stepper = phase.cavity.stepper_tuner
    stepper.step_signed_pv_obj.get.return_value = initial_signed_steps
    phase._hz_per_microstep = 2.0
    # Satisfy the DF_COLD gate for tune_to_resonance tests by default.
    if seed_cold:
        _seed_cold_landing(phase)
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
        "apply_hz_per_step",
        "tune_to_resonance",
        "measure_pi_modes",
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
    # Guard fails before any cavity preparation.
    phase.cavity.setup_tuning.assert_not_called()


def test_verify_initial_state_on_limit_switch(phase, mock_stepper):
    _setup_phase(phase)
    mock_stepper.on_limit_switch = True
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "limit switch" in result.message.lower()
    phase.cavity.setup_tuning.assert_not_called()


def test_verify_initial_state_offline_fails(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.is_online = False
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "online" in result.message.lower()
    mock_cavity.setup_tuning.assert_not_called()


def test_verify_initial_state_detune_error_fails(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.setup_tuning.side_effect = DetuneError("no valid detune")
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "detune" in result.message.lower()


def test_verify_initial_state_fault_error_fails(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.reset_interlocks.side_effect = CavityFaultError("still faulted")
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.FAILED
    assert "fault" in result.message.lower()


def test_verify_initial_state_read_exception_retries(phase, mock_cavity):
    _setup_phase(phase, temp_c=25.0)
    phase.cavity.stepper_temp_pv_obj.get.side_effect = RuntimeError(
        "PV timeout"
    )
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.RETRY


def test_verify_initial_state_success(phase, mock_cavity):
    _setup_phase(phase, temp_c=30.0)
    mock_cavity.tune_config_pv_obj.get.return_value = TUNE_CONFIG_COLD_VALUE
    result = phase._verify_initial_state()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["initial_temp_c"] == 30.0
    assert "initial_detune_hz" in result.data
    # The cavity was prepared for tuning (production sequence).
    mock_cavity.turn_off.assert_called_once()
    mock_cavity.ssa.turn_on.assert_called_once()
    mock_cavity.reset_interlocks.assert_called_once()
    mock_cavity.setup_tuning.assert_called_once()
    # COLD start → no warning
    assert result.data["tune_config_warning"] is None
    assert "WARNING" not in result.message


def test_verify_initial_state_warns_when_not_cold(phase, mock_cavity):
    _setup_phase(phase, temp_c=30.0)
    mock_cavity.tune_config_pv_obj.get.return_value = (
        TUNE_CONFIG_RESONANCE_VALUE
    )
    result = phase._verify_initial_state()
    # Not fatal — still SUCCESS, but flagged.
    assert result.result == PhaseResult.SUCCESS
    assert result.data["tune_config_warning"] is not None
    assert "WARNING" in result.message


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
    assert result.data["df_cold_hz"] == 8000.0
    assert "initial_timestamp" in result.data
    # DF_COLD is written by the operator via the UI button, not auto-written here.
    phase.cavity.df_cold_pv_obj.put.assert_not_called()


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
            # CHIRP:DF = ref − cav; freq increased → CHIRP:DF decreases
            mock_cavity.detune_chirp = 500.0
        else:
            mock_cavity.detune_chirp = 1000.0  # restored

    mock_stepper.move.side_effect = after_move

    result = phase._probe_stepper_direction()

    assert result.result == PhaseResult.SUCCESS
    # delta=-500, probe_steps=10 (fast_limits) → signed_hz=+50 Hz/step
    assert result.data["hz_per_microstep"] == pytest.approx(50.0)
    assert phase._hz_per_microstep == pytest.approx(50.0)
    # SCALE PV is NOT written by the probe step — operator confirms via apply_hz_per_step
    mock_stepper.hz_per_microstep_pv_obj.put.assert_not_called()
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
            # CHIRP:DF = ref − cav; freq decreased → CHIRP:DF increases
            mock_cavity.detune_chirp = 1200.0
        else:
            mock_cavity.detune_chirp = 1000.0

    mock_stepper.move.side_effect = after_move

    result = phase._probe_stepper_direction()

    assert result.result == PhaseResult.SUCCESS
    # delta=+200, probe_steps=10 → signed_hz=-20 Hz/step
    assert result.data["hz_per_microstep"] == pytest.approx(-20.0)
    assert phase._hz_per_microstep == pytest.approx(-20.0)
    mock_stepper.hz_per_microstep_pv_obj.put.assert_not_called()


def test_probe_stepper_direction_delta_too_small(
    phase, mock_cavity, mock_stepper
):
    # A change below min_probe_delta_hz (default 100 Hz) fails — a 50 Hz probe
    # response is treated as a degraded/uncoupled stepper, not a valid measurement.
    assert phase.limits.min_probe_delta_hz == 100.0
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(steps, *args, **kwargs):
        if steps > 0:
            mock_cavity.detune_chirp = 1050.0  # only 50 Hz — below the floor

    mock_stepper.move.side_effect = after_move

    result = phase._probe_stepper_direction()

    assert result.result == PhaseResult.FAILED
    assert "minimum" in result.message.lower()
    mock_stepper.hz_per_microstep_pv_obj.put.assert_not_called()


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
# apply_hz_per_step
# ---------------------------------------------------------------------------


def test_apply_hz_per_step_dry_run(context, fast_limits):
    context.dry_run = True
    p = FrequencyTuningPhase(context, limits=fast_limits)
    p.validate_prerequisites()
    result = p._apply_hz_per_step()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_apply_hz_per_step_not_measured(phase):
    phase.validate_prerequisites()
    result = phase._apply_hz_per_step()
    assert result.result == PhaseResult.FAILED
    assert "probe_stepper_direction" in result.message


def test_apply_hz_per_step_writes_scale_calc_pv(phase, mock_stepper):
    _setup_phase(phase)
    phase._hz_per_microstep = 42.5
    result = phase._apply_hz_per_step()
    assert result.result == PhaseResult.SUCCESS
    # SCALE is derived (read-only); the phase must write SCALE_CALC.B, not SCALE.
    mock_stepper.set_hz_per_microstep.assert_called_once_with(42.5)
    mock_stepper.hz_per_microstep_pv_obj.put.assert_not_called()


def test_apply_hz_per_step_pv_error_retries(phase, mock_stepper):
    _setup_phase(phase)
    phase._hz_per_microstep = 10.0
    mock_stepper.set_hz_per_microstep.side_effect = RuntimeError("timeout")
    result = phase._apply_hz_per_step()
    assert result.result == PhaseResult.RETRY
    assert "SCALE_CALC.B" in result.message


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


def test_tune_to_resonance_fails_when_df_cold_not_recorded(phase, mock_cavity):
    # No record_cold_landing checkpoint at all.
    _setup_phase(phase, seed_cold=False)
    mock_cavity.detune_chirp = 5000.0
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "record_cold_landing" in result.message


def test_tune_to_resonance_fails_when_df_cold_mismatched(phase, mock_cavity):
    # Cold landing was recorded, but DF_COLD PV was never pushed to match it.
    _setup_phase(phase, seed_cold=False)
    _seed_cold_landing(phase, df_cold_hz=5000.0)
    phase.cavity.df_cold_pv_obj.get.return_value = 0.0  # operator did not push
    mock_cavity.detune_chirp = 5000.0
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "DF_COLD not recorded" in result.message


def test_tune_to_resonance_proceeds_when_df_cold_matches(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase, seed_cold=False)
    _seed_cold_landing(phase, df_cold_hz=5000.0)
    mock_cavity.detune_chirp = 5000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 100.0

    mock_stepper.move.side_effect = after_move
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS


def test_tune_to_resonance_sets_tune_config_resonance(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 5000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 100.0

    mock_stepper.move.side_effect = after_move
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS
    mock_cavity.tune_config_pv_obj.put.assert_called_once_with(
        TUNE_CONFIG_RESONANCE_VALUE
    )


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


def test_tune_to_resonance_over_temp_fails_without_ack(phase, mock_cavity):
    # No automatic cool-down: an over-temp reading fails the step and flags
    # that an operator acknowledgement is required.
    _setup_phase(phase)
    phase.limits.temp_limit_c = 70.0
    phase.cavity.stepper_temp_pv_obj.get.return_value = 85.0
    mock_cavity.detune_chirp = 5000.0

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert result.data["requires_over_temp_ack"] is True
    assert result.data["stepper_temp_c"] == 85.0
    assert result.data["temp_limit_c"] == 70.0
    assert "85" in result.message


def test_tune_to_resonance_over_temp_proceeds_with_ack(
    phase, mock_cavity, mock_stepper, context
):
    # With an acknowledgement ceiling >= the reading, tuning proceeds and the
    # acknowledging operator is recorded.
    _setup_phase(phase)
    phase.limits.temp_limit_c = 70.0
    context.parameters["over_temp_ack_c"] = 90.0
    phase.cavity.stepper_temp_pv_obj.get.return_value = 85.0
    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["over_temp_acknowledged_c"] == 85.0
    assert result.data["over_temp_acknowledged_by"] == context.operator


def test_tune_to_resonance_hotter_breach_requires_new_ack(
    phase, mock_cavity, mock_stepper, context
):
    # Ack ceiling authorizes up to 90 °C, but a later reading climbs above it
    # → fail again for a fresh acknowledgement.
    _setup_phase(phase)
    phase.limits.temp_limit_c = 70.0
    context.parameters["over_temp_ack_c"] = 90.0

    # (1) init read OK, (2) iter-1 = 85 (acked, proceeds), (3) iter-2 = 95 (> ceiling → fail)
    temp_values = iter([25.0, 85.0, 95.0])
    phase.cavity.stepper_temp_pv_obj.get.side_effect = lambda: next(temp_values)
    mock_cavity.detune_chirp = 5000.0  # never converges, keeps looping

    def after_move(*args, **kwargs):
        pass  # detune unchanged → second iteration runs

    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert result.data["requires_over_temp_ack"] is True
    assert result.data["stepper_temp_c"] == 95.0


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
    phase.cavity.stepper_temp_pv_obj.get.side_effect = RuntimeError(
        "PV timeout"
    )
    mock_cavity.detune_chirp = 5000.0
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.RETRY


def test_tune_to_resonance_missing_hz_per_microstep(phase, mock_cavity):
    _setup_phase(phase)
    phase._hz_per_microstep = None
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.FAILED
    assert "probe_stepper_direction" in result.message


def test_tune_to_resonance_signed_step_read_error_retries(phase, mock_cavity):
    # A failure reading the resume step count must abort with RETRY rather
    # than silently resuming at 0 and corrupting NSTEPS_COLD.
    _setup_phase(phase)
    mock_cavity.detune_chirp = 5000.0
    phase.cavity.stepper_tuner.step_signed_pv_obj.get.side_effect = (
        RuntimeError("PV timeout")
    )
    result = phase._tune_to_resonance()
    assert result.result == PhaseResult.RETRY


def test_tune_to_resonance_tracks_peak_temp(phase, mock_cavity, mock_stepper):
    _setup_phase(phase)
    phase.limits.temp_limit_c = 100.0

    # Reads: (1) initial peak_temp, then one per loop iteration (3 iterations
    # before detune hits tolerance), plus one final read after last move.
    temp_values = iter([30.0, 55.0, 40.0, 25.0])
    phase.cavity.stepper_temp_pv_obj.get.side_effect = lambda: next(temp_values)

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
    mock_stepper.steps_cold_landing_pv_obj.put.assert_called_once_with(
        result.data["cold_landing_steps"]
    )


def test_tune_to_resonance_accumulates_steps_across_restarts(
    phase, mock_cavity, mock_stepper
):
    """NSTEPS_COLD must reflect total steps from cold landing, not just this run."""
    prior_steps = -500_000
    _setup_phase(phase, initial_signed_steps=prior_steps)
    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move

    result = phase._tune_to_resonance()

    assert result.result == PhaseResult.SUCCESS
    cold_landing_steps = result.data["cold_landing_steps"]
    total_steps_this_run = result.data["total_steps"]
    # cold_landing_steps = -(prior_signed_offset + signed_steps_this_run).
    # Its magnitude must exceed what this run contributed alone, proving the
    # prior accumulated offset was preserved rather than reset to zero.
    assert (
        abs(cold_landing_steps) > total_steps_this_run
    ), "cold_landing_steps must reflect steps from prior (aborted) runs"
    mock_stepper.steps_cold_landing_pv_obj.put.assert_called_once_with(
        cold_landing_steps
    )


def test_tune_to_resonance_nsteps_cold_write_error(
    phase, mock_cavity, mock_stepper
):
    _setup_phase(phase)
    mock_cavity.detune_chirp = 1000.0

    def after_move(*args, **kwargs):
        mock_cavity.detune_chirp = 0.0

    mock_stepper.move.side_effect = after_move
    mock_stepper.steps_cold_landing_pv_obj.put.side_effect = RuntimeError(
        "PV timeout"
    )

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
    _setup_phase(phase, seed_cold=False)
    phase._history_start = 0

    record.phase_history.extend(
        [
            _make_checkpoint(
                CommissioningPhase.FREQUENCY_TUNING,
                "record_cold_landing",
                {
                    "df_cold_hz": 8000.0,
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
    assert ft.df_cold_hz == 8000.0
    assert ft.steps_to_resonance == 4000
    assert ft.positive_step_increases_frequency is True
    assert ft.hz_per_microstep == 2.0
    assert ft.cold_landing_steps == -4000
    assert ft.initial_timestamp is not None
    assert ft.final_timestamp is not None


def test_finalize_phase_no_checkpoints_creates_defaults(phase, record):
    _setup_phase(phase, seed_cold=False)
    phase._history_start = 0

    phase.finalize_phase()

    ft = record.frequency_tuning
    assert ft is not None
    assert ft.df_cold_hz is None
    assert ft.steps_to_resonance is None
    assert ft.positive_step_increases_frequency is None


# ---------------------------------------------------------------------------
# _do_probe_move — probe callback paths
# ---------------------------------------------------------------------------

_FT_MODULE = (
    "sc_linac_physics.applications.rf_commissioning.phases.frequency_tuning.PV"
)


def test_do_probe_move_invokes_callbacks(phase, mock_cavity, mock_stepper):
    """probe_cb must be called with (0, d0) before and (probe, d1) after move."""
    _setup_phase(phase)
    called_with = []
    mock_cavity.detune_chirp = 1000.0

    def probe_cb(steps, hz):
        called_with.append((steps, hz))

    phase._do_probe_move(10, probe_cb, speed=1000)

    assert len(called_with) == 2
    assert called_with[0] == (0, 1000.0)
    assert called_with[1][0] == 10


def test_do_probe_move_callback_exception_is_swallowed(
    phase, mock_cavity, mock_stepper
):
    """A failing probe_cb must not propagate — the move should succeed."""
    _setup_phase(phase)

    def bad_cb(*_):
        raise RuntimeError("callback error")

    phase._do_probe_move(10, bad_cb)
    assert mock_stepper.move.call_count == 2


# ---------------------------------------------------------------------------
# _measure_pi_modes — dry-run and live paths
# ---------------------------------------------------------------------------


def _make_rack(phase, fscan_stat_sequence):
    """Build a mock rack and wire mock_cavity.rack to it."""
    rack = Mock()
    rack.pv_prefix = "ACCL:L1B:0210:"
    rack.rack_name = "A"

    cav2 = Mock()
    cav2.pv_addr = lambda s: f"ACCL:L1B:0220:{s}"
    rack.cavities = {
        phase.cavity.number: phase.cavity,
        phase.cavity.number + 1: cav2,
    }

    phase.cavity.rack = rack
    phase.cavity.pv_addr = lambda s: f"ACCL:L1B:0210:{s}"
    phase.cavity.number = 1

    return rack, fscan_stat_sequence


def _make_pv_factory(stat_sequence):
    """Return a PV factory that replays stat_sequence on FSCAN:STAT reads."""
    stat_iter = iter(stat_sequence)

    def factory(addr):
        pv = Mock()
        if "FSCAN:STAT" in addr:
            pv.get.side_effect = lambda: next(stat_iter)
        elif "8PI9MODE" in addr:
            pv.get.return_value = 1_400_000_000.0
        elif "7PI9MODE" in addr:
            pv.get.return_value = 1_399_000_000.0
        else:
            pv.get.return_value = 0
        return pv

    return factory


def test_measure_pi_modes_dry_run(phase):
    _setup_phase(phase)
    phase.context.dry_run = True
    result = phase._measure_pi_modes()
    assert result.result == PhaseResult.SUCCESS
    assert result.data["dry_run"] is True


def test_measure_pi_modes_success(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    rack, _ = _make_rack(phase, [3, 5])  # 3=in-progress, 5=done

    with patch(_FT_MODULE, side_effect=_make_pv_factory([3, 5])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.SUCCESS
    assert "mode_8pi_9_hz" in result.data
    assert "mode_7pi_9_hz" in result.data


def test_measure_pi_modes_rack_check_blocks(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [])
    phase.context.parameters["rack_check_callback"] = lambda rack: (
        False,
        "another cavity active",
    )

    with patch(_FT_MODULE, side_effect=_make_pv_factory([])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.FAILED
    assert "rack" in result.message.lower()


def test_measure_pi_modes_rack_check_callback_raises(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [])
    phase.context.parameters["rack_check_callback"] = Mock(
        side_effect=RuntimeError("unexpected")
    )

    with patch(_FT_MODULE, side_effect=_make_pv_factory([])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


def test_measure_pi_modes_fscan_aborted(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [6])  # 6=scan aborted

    with patch(_FT_MODULE, side_effect=_make_pv_factory([6])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.FAILED
    assert "aborted" in result.message.lower() or "FSCAN" in result.message


def test_measure_pi_modes_fscan_timeout(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    phase.limits.pi_scan_timeout_seconds = 0.0  # expire immediately
    _make_rack(phase, [])

    with patch(_FT_MODULE, side_effect=_make_pv_factory([])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.FAILED
    assert "did not complete" in result.message


def test_measure_pi_modes_abort_during_wait(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    phase.limits.pi_scan_timeout_seconds = 60.0
    _make_rack(phase, [3])  # stays in-progress

    phase.context.abort_requested = True

    with patch(_FT_MODULE, side_effect=_make_pv_factory([3])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.FAILED
    assert "Abort" in result.message


def test_measure_pi_modes_sel_pv_write_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [])

    def pv_factory(addr):
        pv = Mock()
        if "FSCAN:SEL" in addr:
            pv.put.side_effect = RuntimeError("write timeout")
        return pv

    with patch(_FT_MODULE, side_effect=pv_factory):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


def test_measure_pi_modes_fscan_param_write_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [])

    def pv_factory(addr):
        pv = Mock()
        if "FSCAN:FREQ_START" in addr:
            pv.put.side_effect = RuntimeError("write timeout")
        return pv

    with patch(_FT_MODULE, side_effect=pv_factory):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


def test_measure_pi_modes_start_write_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [])

    def pv_factory(addr):
        pv = Mock()
        if "FSCAN:START" in addr:
            pv.put.side_effect = RuntimeError("write timeout")
        return pv

    with patch(_FT_MODULE, side_effect=pv_factory):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


def test_measure_pi_modes_stat_read_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    phase.limits.pi_scan_timeout_seconds = 60.0
    _make_rack(phase, [])

    def pv_factory(addr):
        pv = Mock()
        if "FSCAN:STAT" in addr:
            pv.get.side_effect = RuntimeError("read timeout")
        return pv

    with patch(_FT_MODULE, side_effect=pv_factory):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


def test_measure_pi_modes_status_callback_invoked(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    phase.limits.pi_scan_timeout_seconds = 60.0
    _make_rack(phase, [3, 5])

    status_msgs = []
    phase.context.parameters["status_update_callback"] = status_msgs.append

    with patch(_FT_MODULE, side_effect=_make_pv_factory([3, 5])):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.SUCCESS
    assert any("FSCAN" in m for m in status_msgs)


def test_measure_pi_modes_push_results_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [5])

    def pv_factory(addr):
        pv = Mock()
        if "FSCAN:STAT" in addr:
            pv.get.return_value = 5
        elif "PUSH_8PI9" in addr:
            pv.put.side_effect = RuntimeError("put failed")
        return pv

    with patch(_FT_MODULE, side_effect=pv_factory):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


def test_measure_pi_modes_read_frequency_error(phase, mock_cavity):
    _setup_phase(phase)
    mock_cavity.number = 1
    _make_rack(phase, [5])

    def pv_factory(addr):
        pv = Mock()
        if "FSCAN:STAT" in addr:
            pv.get.return_value = 5
        elif "8PI9MODE" in addr:
            pv.get.side_effect = RuntimeError("read failed")
        return pv

    with patch(_FT_MODULE, side_effect=pv_factory):
        result = phase._measure_pi_modes()

    assert result.result == PhaseResult.RETRY


# ---------------------------------------------------------------------------
# _initialize_tuning_state — lazy PV init
# ---------------------------------------------------------------------------


def test_initialize_tuning_state_reads_stepper_signed_pv(
    phase, mock_cavity, mock_stepper
):
    """Signed step count is read from the stepper's step_signed_pv_obj."""
    _setup_phase(phase)
    mock_stepper.step_signed_pv_obj.get.return_value = -200_000

    total, signed, peak, err = phase._initialize_tuning_state(None)

    assert signed == -200_000
    assert err is None


def test_initialize_tuning_state_pv_read_error_returns_retry(
    phase, mock_cavity, mock_stepper
):
    """A PV read exception during init must surface a RETRY, not default to 0.

    Silently resuming at 0 would corrupt the NSTEPS_COLD return-trip value.
    """
    _setup_phase(phase)
    mock_stepper.step_signed_pv_obj.get.side_effect = RuntimeError("read error")

    total, signed, peak, err = phase._initialize_tuning_state(None)
    assert signed == 0
    assert err is not None
    assert err.result == PhaseResult.RETRY
