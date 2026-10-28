"""Tests for the setup steps phases share with auto setup."""

from datetime import datetime, timedelta
from unittest.mock import Mock, call

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.phases import (
    cavity_setup,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    SSACalibrationError,
    StepperTempError,
)


def _rack_cavity(number, rf_on):
    other = Mock()
    other.number = number
    other.is_on = rf_on
    return other


@pytest.fixture
def cavity():
    cav = Mock()
    cav.number = 1
    cav.rack.rack_name = "A"
    cav.rack.cavities = {1: cav, 2: _rack_cavity(2, rf_on=False)}
    cav.ssa.drive_max = 0.8
    cav.ssa.measured_slope = 1.02
    cav.ssa.max_fwd_pwr = 4200.0
    cav.is_on = True
    cav.detune_invalid = False
    cav.detune = 10.0
    return cav


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


@pytest.fixture
def context(record):
    return PhaseContext(record=record, operator="op")


# ---------------------------------------------------------------------------
# calibrate_ssa
# ---------------------------------------------------------------------------


def test_calibration_follows_auto_setup_order(cavity, context):
    """RF off, both DACs to 0, then SSA.calibrate — as request_ssa_cal does."""
    order = Mock()
    order.attach_mock(cavity.turn_off, "turn_off")
    order.attach_mock(cavity.ssa.calibrate, "calibrate")

    result = cavity_setup.calibrate_ssa(cavity, context, drive_max=0.7)

    assert result.result == PhaseResult.SUCCESS, result.message
    assert order.mock_calls == [
        call.turn_off(),
        call.calibrate(0.7, attempt=cavity_setup.SSA_CAL_START_ATTEMPT),
    ]
    assert cavity.rack.rfs1.dac_amp == 0
    assert cavity.rack.rfs2.dac_amp == 0


def test_calibration_defaults_to_the_saved_drive_max(cavity, context):
    cavity_setup.calibrate_ssa(cavity, context)
    cavity.ssa.calibrate.assert_called_once_with(0.8, attempt=2)


def test_calibration_replaces_the_ssa_record(cavity, context, record):
    record.ssa_char = SSACharacterization(max_drive=0.9, slope_new=0.95)

    cavity_setup.calibrate_ssa(cavity, context, drive_max=0.7)

    assert record.ssa_char.max_drive == 0.7
    assert record.ssa_char.slope_new == 1.02
    assert record.ssa_char.max_fwd_pwr == 4200.0
    assert record.ssa_char.calibration_passed is True


def test_failed_calibration_fails_and_keeps_the_record(cavity, context, record):
    previous = SSACharacterization(max_drive=0.9, slope_new=0.95)
    record.ssa_char = previous
    cavity.ssa.calibrate.side_effect = SSACalibrationError("result not good")

    result = cavity_setup.calibrate_ssa(cavity, context)

    assert result.result == PhaseResult.FAILED
    assert "result not good" in result.message
    assert record.ssa_char is previous


def test_cavity_abort_during_calibration_is_terminal(cavity, context):
    cavity.ssa.calibrate.side_effect = CavityAbortError("abort")
    result = cavity_setup.calibrate_ssa(cavity, context)
    assert result.result == PhaseResult.FAILED


def test_unexpected_error_during_calibration_retries(cavity, context):
    cavity.ssa.calibrate.side_effect = TimeoutError("CA timeout")
    result = cavity_setup.calibrate_ssa(cavity, context)
    assert result.result == PhaseResult.RETRY


def test_commissioning_abort_stops_calibration_before_any_write(
    cavity, context
):
    context.request_abort()
    result = cavity_setup.calibrate_ssa(cavity, context)
    assert result.result == PhaseResult.FAILED
    cavity.turn_off.assert_not_called()
    cavity.ssa.calibrate.assert_not_called()


# ---------------------------------------------------------------------------
# Rack gate on the DAC zeroing
# ---------------------------------------------------------------------------


def test_another_cavity_with_rf_on_blocks_the_dac_zeroing(cavity, context):
    cavity.rack.cavities[3] = _rack_cavity(3, rf_on=True)

    result = cavity_setup.calibrate_ssa(cavity, context)

    assert result.result == PhaseResult.FAILED
    assert "DAC_AMPLITUDE" in result.message
    cavity.turn_off.assert_not_called()
    cavity.ssa.calibrate.assert_not_called()


def test_this_cavity_having_rf_on_does_not_block(cavity, context):
    """The cavity being set up is turned off by the step itself."""
    cavity.is_on = True
    result = cavity_setup.calibrate_ssa(cavity, context)
    assert result.result == PhaseResult.SUCCESS


def test_rack_check_callback_replaces_the_rf_state_check(cavity, context):
    cavity.rack.cavities[3] = _rack_cavity(3, rf_on=True)
    context.parameters["rack_check_callback"] = lambda rack: (True, "")

    result = cavity_setup.calibrate_ssa(cavity, context)

    assert result.result == PhaseResult.SUCCESS


def test_rack_check_callback_can_refuse(cavity, context):
    context.parameters["rack_check_callback"] = lambda rack: (
        False,
        "CM02 cavity 3 is mid-commissioning",
    )

    result = cavity_setup.calibrate_ssa(cavity, context)

    assert result.result == PhaseResult.FAILED
    assert "cavity 3" in result.message
    cavity.turn_off.assert_not_called()


def test_rack_check_that_raises_retries(cavity, context):
    def broken(rack):
        raise RuntimeError("db locked")

    context.parameters["rack_check_callback"] = broken

    result = cavity_setup.calibrate_ssa(cavity, context)

    assert result.result == PhaseResult.RETRY
    cavity.turn_off.assert_not_called()


# ---------------------------------------------------------------------------
# tune_to_resonance
# ---------------------------------------------------------------------------


def test_tuning_delegates_with_the_temp_limit(cavity, context):
    result = cavity_setup.tune_to_resonance(cavity, context, 70.0)

    assert result.result == PhaseResult.SUCCESS, result.message
    cavity.move_to_resonance.assert_called_once_with(max_stepper_temp=70.0)


def test_over_temperature_stops_tuning(cavity, context):
    cavity.move_to_resonance.side_effect = StepperTempError("71 K")
    result = cavity_setup.tune_to_resonance(cavity, context, 70.0)
    assert result.result == PhaseResult.FAILED
    assert "71 K" in result.message


def test_tuned_but_rf_off_fails(cavity, context):
    cavity.is_on = False
    result = cavity_setup.tune_to_resonance(cavity, context, 70.0)
    assert result.result == PhaseResult.FAILED
    assert "RF is off" in result.message


def test_tuned_but_detune_invalid_fails(cavity, context):
    cavity.detune_invalid = True
    result = cavity_setup.tune_to_resonance(cavity, context, 70.0)
    assert result.result == PhaseResult.FAILED
    assert "invalid" in result.message


def test_commissioning_abort_stops_tuning_before_it_starts(cavity, context):
    context.request_abort()
    result = cavity_setup.tune_to_resonance(cavity, context, 70.0)
    assert result.result == PhaseResult.FAILED
    cavity.move_to_resonance.assert_not_called()


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_dry_run_touches_nothing(cavity, record):
    context = PhaseContext(record=record, operator="op", dry_run=True)

    assert (
        cavity_setup.calibrate_ssa(cavity, context).result
        == PhaseResult.SUCCESS
    )
    assert (
        cavity_setup.tune_to_resonance(cavity, context, 70.0).result
        == PhaseResult.SUCCESS
    )

    cavity.turn_off.assert_not_called()
    cavity.ssa.calibrate.assert_not_called()
    cavity.move_to_resonance.assert_not_called()
    assert not isinstance(cavity.rack.rfs1.dac_amp, int)
    assert record.ssa_char is None


# ---------------------------------------------------------------------------
# Last setup results
# ---------------------------------------------------------------------------

NOW = datetime(2026, 10, 19, 12, 0, 0)


def _result(hours_old, good=True):
    return cavity_setup.LastSetupResult(
        name="SSA calibration",
        timestamp=NOW - timedelta(hours=hours_old),
        good=good,
    )


@pytest.mark.parametrize(
    "hours_old, good, recent",
    [(0.5, True, True), (1.5, True, False), (0.5, False, False)],
)
def test_is_recent_needs_good_and_under_an_hour(hours_old, good, recent):
    assert _result(hours_old, good).is_recent(now=NOW) is recent


def test_describe_gives_hours_then_days():
    assert _result(3.2).describe(now=NOW) == (
        "SSA calibration from 2026-10-19 08:48, 3.2 h old"
    )
    assert _result(72).describe(now=NOW).endswith("3 days old")
    assert (
        _result(0.5, good=False).describe(now=NOW).endswith(", result not good")
    )


def test_last_ssa_calibration_reads_calts_and_calstat():
    cavity = Mock()
    cavity.ssa.calibration_timestamp = NOW
    cavity.ssa.calibration_result_good = False
    last = cavity_setup.last_ssa_calibration(cavity)
    assert (last.timestamp, last.good) == (NOW, False)


@pytest.mark.parametrize("status, good", [(1, True), (0, False), (2, False)])
def test_last_characterization_is_good_only_when_complete(status, good):
    cavity = Mock()
    cavity.characterization_timestamp = NOW
    cavity.characterization_status = status
    assert cavity_setup.last_characterization(cavity).good is good


def _cal(good=True, hours_old=0.2):
    return cavity_setup.LastSetupResult(
        name="SSA calibration",
        timestamp=datetime.now() - timedelta(hours=hours_old),
        good=good,
    )


def test_decide_keeps_a_recent_good_calibration_without_asking():
    last = _cal()
    ask = Mock()

    assert cavity_setup.decide_ssa_calibration(last, "op", ask) == (last, None)
    ask.assert_not_called()


def test_decide_calibrates_when_the_last_one_could_not_be_read():
    ask = Mock()

    assert cavity_setup.decide_ssa_calibration(None, "op", ask) == (None, None)
    ask.assert_not_called()


@pytest.mark.parametrize("last", [_cal(hours_old=2), _cal(good=False)])
@pytest.mark.parametrize(
    "choice, expected",
    [("rerun", (None, None)), ("skip", "kept"), ("cancel", None)],
)
def test_decide_asks_about_an_old_or_bad_calibration(last, choice, expected):
    ask = Mock(return_value=choice)

    decision = cavity_setup.decide_ssa_calibration(last, "op", ask)

    ask.assert_called_once_with(last.describe())
    assert decision == ((last, "op") if expected == "kept" else expected)


def test_kept_note_names_who_skipped():
    last = _cal(hours_old=5)

    assert cavity_setup.kept_ssa_calibration_note(last, None).startswith(
        "Kept the SSA calibration from"
    )
    assert cavity_setup.kept_ssa_calibration_note(last, "op").startswith(
        "SSA calibration skipped by op: SSA calibration from"
    )
