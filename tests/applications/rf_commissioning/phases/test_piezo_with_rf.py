"""Tests for the Piezo with RF phase.

The phase drives the cavity through Cavity/Piezo helpers, so these assert
what it calls and in what order, that a dry run writes nothing, and where it
refuses to go on.
"""

import time
from unittest.mock import Mock

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
from sc_linac_physics.applications.rf_commissioning.phases.piezo_with_rf import (
    PiezoWithRFLimits,
    PiezoWithRFPhase,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityCharacterizationError,
    CavityHWModeError,
)

COMPLETE = 1


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
