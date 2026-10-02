"""Tests for the Cavity Characterization phase.

The phase is deliberately a thin wrapper over Cavity, so most of these assert
delegation and boundaries rather than arithmetic: that it calls the shared
implementation, that it does not push before the operator confirms, and that an
out-of-tolerance loaded Q is recorded as such rather than quietly passing.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    CommissioningPhase,
    CommissioningRecord,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.phases.cavity_char import (
    CavityCharLimits,
    CavityCharPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityCharacterizationError,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)


@pytest.fixture
def mock_cavity():
    cavity = Mock()
    cavity.is_online = True
    cavity.stepper_tuner.motor_moving = False
    cavity.ssa.is_on = True
    cavity.ssa.calibration_running = False
    cavity.characterization_running = False
    cavity.characterization_crashed = False
    cavity.measured_loaded_q = 4.0e7
    cavity.measured_scale_factor = 30.0
    cavity.measured_loaded_q_in_tolerance = True
    cavity.measured_scale_factor_in_tolerance = True
    cavity.scale_factor_lower_limit = 10.0
    cavity.scale_factor_upper_limit = 50.0
    cavity.loaded_q_lower_limit = 2.5e7
    cavity.loaded_q_upper_limit = 5.1e7
    # Deliberately does NOT set probe_q: the real Cavity has no such
    # attribute and no probe-Q readback PV. Setting it on the Mock is what
    # previously made this suite pass against an API that does not exist.
    return cavity


@pytest.fixture
def record():
    return CommissioningRecord(linac=4, cryomodule="37", cavity_number=1)


@pytest.fixture
def phase(mock_cavity, record):
    context = PhaseContext(
        record=record,
        operator="test_op",
        parameters={"cavity": mock_cavity},
    )
    p = CavityCharPhase(context, limits=CavityCharLimits(status_settle_delay=0))
    p.validate_prerequisites()
    return p


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_phase_type(phase):
    assert phase.phase_type == CommissioningPhase.CAVITY_CHAR


def test_steps_separate_reading_from_pushing(phase):
    """The order is the point: read, then a distinct operator-gated push."""
    steps = phase.get_phase_steps()
    assert steps.index("read_results") < steps.index("push_results")


def test_unknown_step_fails(phase):
    result = phase.execute_step("not_a_step")
    assert result.result == PhaseResult.FAILED


# ---------------------------------------------------------------------------
# Delegation — the shared implementation must be used, not reimplemented
# ---------------------------------------------------------------------------


def test_start_delegates_to_the_cavity(phase, mock_cavity):
    phase.execute_step("start_characterization")
    mock_cavity.start_characterization.assert_called_once()


def test_read_triggers_the_probe_q_calculation(phase, mock_cavity):
    """QPROBE_CALC1.PROC derives probe Q; it must be processed before reading."""
    phase.execute_step("read_results")
    mock_cavity.calculate_probe_q.assert_called_once()


def test_tolerance_comes_from_the_cavity_not_from_here(phase, mock_cavity):
    """The per-cavity-class window lives on Cavity; don't duplicate the limits."""
    mock_cavity.measured_loaded_q_in_tolerance = False

    phase.execute_step("read_results")

    assert phase._loaded_q_in_tolerance is False


# ---------------------------------------------------------------------------
# Nothing reaches the cavity before the operator confirms
# ---------------------------------------------------------------------------


def test_reading_pushes_nothing(phase, mock_cavity):
    """Reading is the review step — the cavity must be untouched by it."""
    phase.execute_step("read_results")

    mock_cavity.push_loaded_q.assert_not_called()
    mock_cavity.push_scale_factor.assert_not_called()


def _confirm(phase):
    """What the UI does when the operator confirms the values on screen."""
    phase.context.parameters["confirmed_loaded_q"] = phase._loaded_q


def test_push_step_pushes(phase, mock_cavity):
    phase.execute_step("read_results")
    _confirm(phase)
    result = phase.execute_step("push_results")

    assert result.result == PhaseResult.SUCCESS
    mock_cavity.push_loaded_q.assert_called_once()
    mock_cavity.push_scale_factor.assert_called_once()


def test_push_before_measuring_fails(phase, mock_cavity):
    result = phase.execute_step("push_results")

    assert result.result == PhaseResult.FAILED
    mock_cavity.push_loaded_q.assert_not_called()


def test_out_of_tolerance_still_lets_the_operator_push(phase, mock_cavity):
    """Flagged, not blocked — whether to push is the operator's call."""
    mock_cavity.measured_loaded_q_in_tolerance = False
    read = phase.execute_step("read_results")

    assert read.result == PhaseResult.SUCCESS
    assert "OUTSIDE" in read.message

    _confirm(phase)
    assert phase.execute_step("push_results").result == PhaseResult.SUCCESS


def test_push_without_confirmation_is_refused(phase, mock_cavity):
    """PhaseBase.run() does not pause between read and push; this step must."""
    phase.execute_step("read_results")
    result = phase.execute_step("push_results")

    assert result.result == PhaseResult.FAILED
    mock_cavity.push_loaded_q.assert_not_called()
    mock_cavity.push_scale_factor.assert_not_called()


def test_confirming_an_older_measurement_does_not_push(phase, mock_cavity):
    phase.context.parameters["confirmed_loaded_q"] = 3.0e7
    phase.execute_step("read_results")  # reads 4.0e7

    result = phase.execute_step("push_results")

    assert result.result == PhaseResult.FAILED
    mock_cavity.push_loaded_q.assert_not_called()


def test_full_run_without_confirmation_never_pushes(phase, mock_cavity):
    assert phase.run() is False
    mock_cavity.push_loaded_q.assert_not_called()
    mock_cavity.push_scale_factor.assert_not_called()


# ---------------------------------------------------------------------------
# Results on the record
# ---------------------------------------------------------------------------


def test_results_are_stored_on_the_record_as_they_are_read(phase, record):
    """Durable as it goes, like the tuning phase — phase_history does not persist."""
    phase.execute_step("read_results")

    data = record.cavity_char
    assert data.loaded_q == 4.0e7
    assert data.scale_factor == 30.0
    assert data.loaded_q_in_tolerance is True


def test_probe_q_is_not_invented_when_no_readback_exists(phase, record):
    """QPROBE_CALC1.PROC triggers the calculation; nothing reads it back.

    There is no probe-Q value PV and no push PV for it anywhere in the codebase.
    The record must be left empty rather than carrying a fabricated number — an
    earlier version of this suite passed only because the Mock supplied a
    probe_q attribute the real Cavity does not have.
    """
    phase.execute_step("read_results")

    assert record.cavity_char.probe_q is None


def test_real_cavity_has_no_probe_q_readback():
    """Pins the gap, so this fails the day the PV is added and can be wired up."""
    from sc_linac_physics.utils.sc_linac.linac import Machine

    cavity = Machine().cryomodules["37"].cavities[1]

    assert not hasattr(cavity, "probe_q")
    assert not hasattr(cavity, "measured_probe_q")
    # The trigger does exist; only the readback is missing.
    assert hasattr(cavity, "calc_probe_q_pv")


def test_scale_factor_out_of_tolerance_is_flagged_and_recorded(
    phase, record, mock_cavity
):
    """The check finish_characterization() makes before pushing scale factor."""
    mock_cavity.measured_scale_factor_in_tolerance = False

    result = phase.execute_step("read_results")

    assert result.result == PhaseResult.SUCCESS
    assert "scale factor is OUTSIDE" in result.message
    assert "loaded Q is OUTSIDE" not in result.message
    assert record.cavity_char.scale_factor_in_tolerance is False
    assert record.cavity_char.passed is False


def test_scale_factor_out_of_tolerance_can_still_be_pushed(phase, mock_cavity):
    """Unlike auto setup: the operator confirmed, so it is their call."""
    mock_cavity.measured_scale_factor_in_tolerance = False
    phase.execute_step("read_results")
    _confirm(phase)

    assert phase.execute_step("push_results").result == PhaseResult.SUCCESS
    mock_cavity.push_scale_factor.assert_called_once()


def test_both_in_tolerance_says_so(phase):
    result = phase.execute_step("read_results")
    assert "both in tolerance" in result.message


def test_out_of_tolerance_is_recorded_as_not_passed(phase, record, mock_cavity):
    """Flagging the value is pointless if the record still says it passed."""
    mock_cavity.measured_loaded_q_in_tolerance = False

    phase.execute_step("read_results")

    assert record.cavity_char.is_complete is True
    assert record.cavity_char.passed is False


def test_finalize_keeps_values_when_steps_ran_in_an_earlier_session(
    phase, record
):
    """A run split across launches must not finalize with fields blanked."""
    record.cavity_char = CavityCharacterization(
        loaded_q=4.0e7, scale_factor=30.0, probe_q=2.0e9
    )

    phase.finalize_phase()

    assert record.cavity_char.loaded_q == 4.0e7
    assert record.cavity_char.scale_factor == 30.0
    assert record.cavity_char.probe_q == 2.0e9


def test_starting_a_new_run_clears_the_previous_results(phase, record):
    """Otherwise this run's loaded Q would sit beside the last run's probe Q."""
    record.cavity_char = CavityCharacterization(
        loaded_q=4.0e7,
        scale_factor=30.0,
        probe_q=2.0e9,
        loaded_q_in_tolerance=True,
        scale_factor_in_tolerance=True,
    )

    phase.execute_step("start_characterization")

    assert record.cavity_char.loaded_q is None
    assert record.cavity_char.scale_factor is None
    assert record.cavity_char.probe_q is None
    assert record.cavity_char.loaded_q_in_tolerance is None
    assert record.cavity_char.scale_factor_in_tolerance is None


def test_a_failed_start_keeps_the_previous_results(phase, record, mock_cavity):
    """Nothing new was measured, so nothing on the record is invalidated."""
    mock_cavity.start_characterization.side_effect = RuntimeError("no CA")
    record.cavity_char = CavityCharacterization(loaded_q=4.0e7, probe_q=2.0e9)

    phase.execute_step("start_characterization")

    assert record.cavity_char.probe_q == 2.0e9


def test_store_skips_none_so_a_later_step_cannot_erase_an_earlier_one(
    phase, record
):
    phase._store_phase_fields(loaded_q=4.0e7)
    phase._store_phase_fields(loaded_q=None, scale_factor=30.0)

    assert record.cavity_char.loaded_q == 4.0e7
    assert record.cavity_char.scale_factor == 30.0


# ---------------------------------------------------------------------------
# Drive level — operator-settable, bounded
# ---------------------------------------------------------------------------


def test_drive_level_defaults_to_the_safe_pulsed_level(phase, mock_cavity):
    from sc_linac_physics.utils.sc_linac import linac_utils

    phase.execute_step("set_drive_level")

    assert mock_cavity.drive_level == linac_utils.SAFE_PULSED_DRIVE_LEVEL


def test_operator_can_override_the_drive_level(mock_cavity, record):
    context = PhaseContext(
        record=record,
        operator="op",
        parameters={"cavity": mock_cavity, "drive_level": 15.0},
    )
    p = CavityCharPhase(context)
    p.validate_prerequisites()

    p.execute_step("set_drive_level")

    assert mock_cavity.drive_level == 15.0


@pytest.mark.parametrize("bad", [0, -5, 99, "abc", None])
def test_drive_level_outside_the_allowed_range_is_refused(
    mock_cavity, record, bad
):
    """Drive goes to a cold cavity; a nonsense value must not be written."""
    context = PhaseContext(
        record=record,
        operator="op",
        parameters={"cavity": mock_cavity, "drive_level": bad},
    )
    p = CavityCharPhase(context)
    p.validate_prerequisites()
    mock_cavity.drive_level = "untouched"

    result = p.execute_step("set_drive_level")

    assert result.result == PhaseResult.FAILED
    assert mock_cavity.drive_level == "untouched"


# ---------------------------------------------------------------------------
# Gates and waiting
# ---------------------------------------------------------------------------


def test_offline_cavity_is_refused(phase, mock_cavity):
    mock_cavity.is_online = False
    result = phase.execute_step("verify_initial_state")
    assert result.result == PhaseResult.FAILED
    assert "not online" in result.message


def test_moving_stepper_is_refused(phase, mock_cavity):
    mock_cavity.stepper_tuner.motor_moving = True
    result = phase.execute_step("verify_initial_state")
    assert result.result == PhaseResult.FAILED
    assert "moving" in result.message.lower()


def test_stale_upstream_results_warn_rather_than_block(phase, record):
    """The workflow already guarantees those phases ran; recency is advice."""
    record.ssa_char = SSACharacterization(
        timestamp=datetime.now() - timedelta(hours=72)
    )

    result = phase.execute_step("verify_initial_state")

    assert result.result == PhaseResult.SUCCESS
    assert "SSA calibration" in result.message


def test_fresh_upstream_results_do_not_warn(phase, record):
    record.ssa_char = SSACharacterization(timestamp=datetime.now())

    result = phase.execute_step("verify_initial_state")

    assert "note:" not in result.message


def test_ssa_off_is_refused(phase, mock_cavity):
    mock_cavity.ssa.is_on = False
    result = phase.execute_step("verify_initial_state")
    assert result.result == PhaseResult.FAILED
    assert "SSA is not on" in result.message


def test_ssa_calibrating_is_refused(phase, mock_cavity):
    mock_cavity.ssa.calibration_running = True
    result = phase.execute_step("verify_initial_state")
    assert result.result == PhaseResult.FAILED
    assert "SSA calibration is running" in result.message


def test_crash_is_reported(phase, mock_cavity):
    mock_cavity.wait_for_characterization.side_effect = (
        CavityCharacterizationError("CM37 cavity 1 characterization crashed")
    )
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    assert "crashed" in result.message.lower()


def test_wait_delegates_to_the_shared_cavity_wait(phase, mock_cavity):
    """The same wait auto setup runs, with this phase's limits and abort."""
    result = phase.execute_step("wait_for_completion")

    assert result.result == PhaseResult.SUCCESS
    mock_cavity.wait_for_characterization.assert_called_once_with(
        timeout=phase.limits.characterization_timeout_seconds,
        poll_interval=phase.limits.status_poll_interval,
        should_abort=phase.context.is_abort_requested,
    )


def test_wait_passes_a_live_view_of_the_commissioning_abort(phase, mock_cavity):
    """PhaseBase.run() only checks the context flag between steps."""
    phase.execute_step("wait_for_completion")
    should_abort = mock_cavity.wait_for_characterization.call_args.kwargs[
        "should_abort"
    ]

    assert should_abort() is False
    phase.context.request_abort()
    assert should_abort() is True


def test_stale_complete_from_an_earlier_run_fails(phase, mock_cavity):
    """PROBECALSTS still COMPLETE from last time must not pass as this run."""
    mock_cavity.wait_for_characterization.side_effect = (
        CavityCharacterizationError(
            "No valid CM37 cavity 1 characterization within the last 5 min"
        )
    )
    result = phase.execute_step("wait_for_completion")
    assert result.result == PhaseResult.FAILED
    assert "PROBECALTS" in result.message


def test_abort_is_terminal_not_retried(phase, mock_cavity):
    """Either abort reaches the phase as CavityAbortError."""
    mock_cavity.wait_for_characterization.side_effect = CavityAbortError(
        "abort"
    )

    result = phase.execute_step("wait_for_completion")

    assert result.result == PhaseResult.FAILED
    assert "Aborted" in result.message


def test_timeout_fails_rather_than_hangs(phase, mock_cavity):
    mock_cavity.wait_for_characterization.side_effect = (
        CavityCharacterizationError(
            "CM37 cavity 1 characterization did not finish within 300 s"
        )
    )

    result = phase.execute_step("wait_for_completion")

    assert result.result == PhaseResult.FAILED
    assert "did not finish" in result.message


def test_dry_run_touches_no_hardware(mock_cavity, record):
    """Every step, not just the ones that were already guarded.

    The earlier version ran the three steps that checked context.dry_run and
    skipped the three that did not, so it passed while set_drive_level wrote
    SEL_ASET and read_results processed QPROBE_CALC1.PROC.
    """
    context = PhaseContext(
        record=record,
        operator="op",
        parameters={"cavity": mock_cavity},
        dry_run=True,
    )
    p = CavityCharPhase(context)
    p.validate_prerequisites()

    for step in p.get_phase_steps():
        assert p.execute_step(step).result == PhaseResult.SUCCESS, step

    # Writes
    mock_cavity.start_characterization.assert_not_called()
    mock_cavity.push_loaded_q.assert_not_called()
    mock_cavity.push_scale_factor.assert_not_called()
    mock_cavity.reset_interlocks.assert_not_called()
    mock_cavity.calculate_probe_q.assert_not_called()

    # drive_level is an attribute assignment, not a call: _set_drive_level
    # would put a float there. An untouched Mock attribute is still a Mock.
    assert not isinstance(
        mock_cavity.drive_level, float
    ), "dry run wrote SEL_ASET via cavity.drive_level"

    # Reads
    mock_cavity.check_abort.assert_not_called()
    mock_cavity.wait_for_characterization.assert_not_called()


def test_dry_run_does_not_store_measurements(mock_cavity, record):
    """A rehearsal must not leave invented numbers on the record."""
    context = PhaseContext(
        record=record,
        operator="op",
        parameters={"cavity": mock_cavity},
        dry_run=True,
    )
    p = CavityCharPhase(context)
    p.validate_prerequisites()
    p.execute_step("read_results")

    data = record.cavity_char
    assert data is None or (data.loaded_q is None and data.scale_factor is None)


def test_prerequisites_need_an_ssa(record):
    cavity = Mock()
    cavity.ssa = None
    context = PhaseContext(
        record=record, operator="op", parameters={"cavity": cavity}
    )
    ok, message = CavityCharPhase(context).validate_prerequisites()
    assert ok is False
    assert "SSA" in message
