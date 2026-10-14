"""Tests for the Cavity Characterization phase.

The phase is deliberately a thin wrapper over Cavity, so most of these assert
delegation and boundaries rather than arithmetic: that it calls the shared
implementation, refuses to start against a cavity that is not ready, and stops
cleanly on an abort, a crash or a timeout.
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

PRIOR_RESULT_TIME = datetime(2026, 10, 14, 12, 0, 0)


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
    cavity.characterization_timestamp = PRIOR_RESULT_TIME
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


def test_unknown_step_fails(phase):
    result = phase.execute_step("not_a_step")
    assert result.result == PhaseResult.FAILED


# ---------------------------------------------------------------------------
# Delegation — the shared implementation must be used, not reimplemented
# ---------------------------------------------------------------------------


def test_start_delegates_to_the_cavity(phase, mock_cavity):
    phase.execute_step("start_characterization")
    mock_cavity.start_characterization.assert_called_once()


# ---------------------------------------------------------------------------
# Results on the record
# ---------------------------------------------------------------------------


def test_starting_a_new_run_clears_the_previous_results(phase, record):
    """Otherwise this run's loaded Q would sit beside the last run's probe Q."""
    record.cavity_char = CavityCharacterization(
        loaded_q=4.0e7,
        scale_factor=30.0,
        probe_q=2.0e9,
    )

    phase.execute_step("start_characterization")

    assert record.cavity_char.loaded_q is None
    assert record.cavity_char.scale_factor is None
    assert record.cavity_char.probe_q is None


def test_a_failed_start_keeps_the_previous_results(phase, record, mock_cavity):
    """Nothing new was measured, so nothing on the record is invalidated."""
    mock_cavity.start_characterization.side_effect = RuntimeError("no CA")
    record.cavity_char = CavityCharacterization(loaded_q=4.0e7, probe_q=2.0e9)

    phase.execute_step("start_characterization")

    assert record.cavity_char.probe_q == 2.0e9


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
    """The same wait auto setup runs, with this phase's limits."""
    result = phase.execute_step("wait_for_completion")

    assert result.result == PhaseResult.SUCCESS
    mock_cavity.wait_for_characterization.assert_called_once_with(
        timeout=phase.limits.characterization_timeout_seconds,
        poll_interval=phase.limits.status_poll_interval,
    )


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


def test_recent_complete_from_before_the_start_fails(phase, mock_cavity):
    """A COMPLETE under 300 s old passes the cavity wait; it must not pass here.

    The start put does not wait, so the wait can read the previous run's
    status before PROBECALSTS goes to RUNNING.
    """
    phase.execute_step("start_characterization")
    # PROBECALTS unchanged: the result is the one read before the start.

    result = phase.execute_step("wait_for_completion")

    assert result.result == PhaseResult.FAILED
    assert "PROBECALTS" in result.message


def test_a_result_newer_than_the_start_passes(phase, mock_cavity):
    phase.execute_step("start_characterization")
    mock_cavity.characterization_timestamp = PRIOR_RESULT_TIME + timedelta(
        seconds=40
    )

    result = phase.execute_step("wait_for_completion")

    assert result.result == PhaseResult.SUCCESS


def test_unreadable_prior_timestamp_retries_without_starting(
    phase, mock_cavity, record
):
    type(mock_cavity).characterization_timestamp = property(
        Mock(side_effect=RuntimeError("no CA"))
    )
    record.cavity_char = CavityCharacterization(probe_q=2.0e9)

    result = phase.execute_step("start_characterization")

    assert result.result == PhaseResult.RETRY
    mock_cavity.start_characterization.assert_not_called()
    assert record.cavity_char.probe_q == 2.0e9


def test_abort_is_terminal_not_retried(phase, mock_cavity):
    """An abort reaches the phase as CavityAbortError."""
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

    An earlier version skipped the steps that did not check context.dry_run,
    so it passed while set_drive_level wrote SEL_ASET.
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
    mock_cavity.reset_interlocks.assert_not_called()

    # drive_level is an attribute assignment, not a call: _set_drive_level
    # would put a float there. An untouched Mock attribute is still a Mock.
    assert not isinstance(
        mock_cavity.drive_level, float
    ), "dry run wrote SEL_ASET via cavity.drive_level"

    # Reads
    mock_cavity.check_abort.assert_not_called()
    mock_cavity.wait_for_characterization.assert_not_called()


def test_prerequisites_need_an_ssa(record):
    cavity = Mock()
    cavity.ssa = None
    context = PhaseContext(
        record=record, operator="op", parameters={"cavity": cavity}
    )
    ok, message = CavityCharPhase(context).validate_prerequisites()
    assert ok is False
    assert "SSA" in message
