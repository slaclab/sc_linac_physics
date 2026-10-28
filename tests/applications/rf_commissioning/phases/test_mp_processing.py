"""Tests for the MP processing phase.

A fake cavity quenches on a schedule in fake-clock seconds. The tests
assert which ADES values the phase writes, when it resets interlocks, what
it records and when it stops.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    MPProcessingData,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.phases import (
    mp_processing as mp_processing_module,
)
from sc_linac_physics.applications.rf_commissioning.phases.mp_processing import (
    MPProcessingLimits,
    MPProcessingPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CALIBRATION_COMPLETE_VALUE,
    CavityAbortError,
    CavityFaultError,
)


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
    monkeypatch.setattr(mp_processing_module, "time", fake)
    return fake


class FakeCavity:
    """Quenches at the clock times in ``quench_at``; reset clears the latch.

    ``ades_writes`` holds every value written to ADES, in order.
    """

    def __init__(self, clock, start=5.0, ades_max=6.0, quench_at=()):
        self.clock = clock
        self.is_online = True
        self.ades_max = ades_max
        self._ades = start
        self.ades_writes = []
        self.quench_at = sorted(quench_at)
        self._latched = False
        self.resets = []
        self.setup_rf_calls = []
        self.abort_at = None
        self.reset_error = None
        # Set to request an abort while reset_interlocks is retrying.
        self.abort_during_reset = False
        # A good SSA calibration and characterization from 10 min ago:
        # recent, so setup_rf keeps both unless a test makes them stale.
        recent = datetime.now() - timedelta(minutes=10)
        self.ssa = SimpleNamespace(
            calibration_timestamp=recent, calibration_result_good=True
        )
        self.characterization_timestamp = recent
        self.characterization_status = CALIBRATION_COMPLETE_VALUE

    @property
    def ades(self):
        return self._ades

    @ades.setter
    def ades(self, value):
        self._ades = value
        self.ades_writes.append(value)

    @property
    def is_quenched(self):
        if self.quench_at and self.clock.now >= self.quench_at[0]:
            self.quench_at.pop(0)
            self._latched = True
        return self._latched

    def reset_interlocks(self):
        if self.abort_during_reset:
            self.abort_at = self.clock.now
        if self.reset_error:
            raise self.reset_error
        self.resets.append(self.clock.now)
        self._latched = False

    def setup_rf(self, des_amp, calibrate_ssa=True, characterize=True):
        self.setup_rf_calls.append((des_amp, calibrate_ssa, characterize))
        self._ades = min(des_amp, self.ades_max)

    def check_abort(self):
        if self.abort_at is not None and self.clock.now >= self.abort_at:
            raise CavityAbortError("Abort requested")


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="H1", cavity_number=1)


def make_phase(cavity, record, dry_run=False, **limits):
    context = PhaseContext(
        record=record,
        operator="test_op",
        dry_run=dry_run,
        parameters={"cavity": cavity},
    )
    phase = MPProcessingPhase(context, limits=MPProcessingLimits(**limits))
    phase.validate_prerequisites()
    return phase


def run_steps(phase):
    """Run every step in order and return the last result."""
    for step in phase.get_phase_steps():
        result = phase.execute_step(step)
        if result.result is not PhaseResult.SUCCESS:
            return result
    return result


def test_phase_type(clock, record):
    phase = make_phase(FakeCavity(clock), record)
    assert phase.phase_type == CommissioningPhase.MP_PROCESSING


def test_requires_a_cavity(record):
    context = PhaseContext(record=record, operator="op")
    ok, message = MPProcessingPhase(context).validate_prerequisites()
    assert not ok
    assert "No cavity" in message


def test_refuses_an_offline_cavity(clock, record):
    cavity = FakeCavity(clock)
    cavity.is_online = False
    result = make_phase(cavity, record).execute_step("verify_initial_state")
    assert result.result is PhaseResult.FAILED
    assert "not online" in result.message


def test_setup_rf_keeps_earlier_calibration_and_starts_at_start_amp(
    clock, record
):
    cavity = FakeCavity(clock, start=0.0)
    phase = make_phase(cavity, record, start_amplitude_mv=5.0)
    assert phase.execute_step("setup_rf").result is PhaseResult.SUCCESS
    assert cavity.setup_rf_calls == [(5.0, False, False)]


def make_stale(cavity, ssa=False, char=False):
    old = datetime.now() - timedelta(hours=2)
    if ssa:
        cavity.ssa.calibration_timestamp = old
    if char:
        cavity.characterization_timestamp = old


def test_verify_reports_which_results_are_stale(clock, record):
    cavity = FakeCavity(clock)
    make_stale(cavity, ssa=True)
    result = make_phase(cavity, record).execute_step("verify_initial_state")
    assert result.data["ssa_calibration_recent"] is False
    assert result.data["characterization_recent"] is True


@pytest.mark.parametrize(
    "stale_ssa, stale_char",
    [(True, False), (False, True), (True, True)],
)
def test_setup_rf_reruns_only_stale_results(
    clock, record, stale_ssa, stale_char
):
    cavity = FakeCavity(clock, start=0.0)
    make_stale(cavity, ssa=stale_ssa, char=stale_char)
    phase = make_phase(cavity, record)
    phase.execute_step("verify_initial_state")

    assert phase.execute_step("setup_rf").result is PhaseResult.SUCCESS

    assert cavity.setup_rf_calls == [(5.0, stale_ssa, stale_char)]


def test_failed_calibration_counts_as_stale(clock, record):
    cavity = FakeCavity(clock, start=0.0)
    cavity.ssa.calibration_result_good = False
    phase = make_phase(cavity, record)

    phase.execute_step("setup_rf")

    assert cavity.setup_rf_calls == [(5.0, True, False)]


def test_operator_can_keep_stale_results(clock, record):
    cavity = FakeCavity(clock, start=0.0)
    make_stale(cavity, ssa=True, char=True)
    phase = make_phase(cavity, record)
    phase.context.parameters.update(
        rerun_ssa_calibration=False, rerun_characterization=False
    )
    phase.execute_step("verify_initial_state")

    phase.execute_step("setup_rf")

    assert cavity.setup_rf_calls == [(5.0, False, False)]
    notes = record.mp_processing.notes
    assert "kept a stale SSA calibration" in notes
    assert "kept a stale characterization" in notes
    assert "operator chose Skip" in notes


def test_rerun_answer_does_not_rerun_a_recent_result(clock, record):
    cavity = FakeCavity(clock, start=0.0)
    phase = make_phase(cavity, record)
    phase.context.parameters.update(
        rerun_ssa_calibration=True, rerun_characterization=True
    )

    phase.execute_step("setup_rf")

    assert cavity.setup_rf_calls == [(5.0, False, False)]


def test_unreadable_calibration_time_retries_before_any_write(clock, record):
    cavity = FakeCavity(clock, start=0.0)
    del cavity.ssa.calibration_timestamp
    phase = make_phase(cavity, record)

    result = phase.execute_step("setup_rf")

    assert result.result is PhaseResult.RETRY
    assert cavity.setup_rf_calls == []


def test_no_quench_walks_to_ades_max_then_holds(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=6.0)
    phase = make_phase(cavity, record, step_seconds=30, stable_seconds=300)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    assert cavity.ades_writes == pytest.approx([5.2, 5.4, 5.6, 5.8, 6.0])
    # Five 30 s steps from 5.0 to 6.0, then 300 s quench-free at 6.0.
    assert clock.now == pytest.approx(5 * 30 + 300)
    assert cavity.resets == []
    data = record.mp_processing
    assert data.quench_count == 0
    assert data.max_amplitude_reached == pytest.approx(6.0)


def test_quench_is_reset_and_held_until_stable_then_walk_continues(
    clock, record
):
    # Quench 10 s into the 5.4 MV step (5.2 at t=30, 5.4 at t=60).
    cavity = FakeCavity(clock, start=5.0, ades_max=5.6, quench_at=[70])
    phase = make_phase(cavity, record, step_seconds=30, stable_seconds=300)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    assert len(cavity.resets) == 1
    # It held 5.4 MV for 300 s after the reset before writing 5.6.
    assert cavity.ades_writes == pytest.approx([5.2, 5.4, 5.6])
    data = record.mp_processing
    assert data.quench_count == 1
    assert data.quench_events[0].amplitude == pytest.approx(5.4)
    assert data.max_amplitude_reached == pytest.approx(5.6)


def test_repeated_quenches_at_one_amplitude_are_each_recorded(clock, record):
    # Quenches 100 s and 250 s apart: shorter than stable_seconds.
    cavity = FakeCavity(clock, start=5.0, ades_max=5.0, quench_at=[10, 110])
    phase = make_phase(cavity, record, stable_seconds=300)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    assert len(cavity.resets) == 2
    assert record.mp_processing.quench_count == 2
    assert cavity.ades_writes == []


def test_stable_time_is_configurable(clock, record):
    # A quench 200 s after the reset breaks a 300 s hold but not a 150 s one.
    times = [10]
    short = FakeCavity(clock, start=5.0, ades_max=5.0, quench_at=times)
    phase = make_phase(short, record, stable_seconds=150)
    reset_wait = phase.limits.quench_settle_seconds
    short.quench_at.append(10 + reset_wait + 200)

    assert run_steps(phase).result is PhaseResult.SUCCESS
    assert record.mp_processing.quench_count == 1


def test_quench_during_final_hold_is_processed(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=5.0, quench_at=[120])
    phase = make_phase(cavity, record, stable_seconds=300)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    assert len(cavity.resets) == 1
    # 120 s to the quench, the settle wait, then 300 s stable.
    expected = 120 + phase.limits.quench_settle_seconds + 300
    assert clock.now == pytest.approx(expected)


def test_abort_fails_the_step_and_keeps_recorded_quenches(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=6.0, quench_at=[10])
    cavity.abort_at = 50
    phase = make_phase(cavity, record, stable_seconds=300)

    result = run_steps(phase)

    assert result.result is PhaseResult.FAILED
    assert "RF is off" in result.message
    assert record.mp_processing.quench_count == 1


def test_float_ades_max_is_reached_and_never_exceeded(clock, record):
    # ADES_MAX as a float PV reads it back: just over 5.6.
    ades_max = 5.600000381469727
    cavity = FakeCavity(clock, start=5.0, ades_max=ades_max)
    phase = make_phase(cavity, record, stable_seconds=300)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    # 5.6 rounds just under the cap; the next step is capped at ADES_MAX
    # exactly, and the final hold follows.
    assert cavity.ades_writes[-1] == ades_max
    assert len(cavity.ades_writes) == 4
    assert max(cavity.ades_writes) <= ades_max


def test_abort_during_the_settle_wait_writes_no_reset(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=6.0, quench_at=[10])
    # Requested after the quench is seen, before the settle wait ends.
    cavity.abort_at = 10.5
    phase = make_phase(cavity, record)

    result = run_steps(phase)

    assert result.result is PhaseResult.FAILED
    assert "RF is off" in result.message
    assert cavity.resets == []


def test_abort_during_a_failing_reset_turns_rf_off(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=6.0, quench_at=[10])
    cavity.reset_error = CavityFaultError("still faulted")
    cavity.abort_during_reset = True
    phase = make_phase(cavity, record)

    result = run_steps(phase)

    assert result.result is PhaseResult.FAILED
    # check_abort ran after the reset failed: the abort, not the fault.
    assert "RF is off" in result.message


def test_failed_reset_fails_the_step(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=6.0, quench_at=[10])
    cavity.reset_error = CavityFaultError("still faulted")
    phase = make_phase(cavity, record)

    result = run_steps(phase)

    assert result.result is PhaseResult.FAILED
    assert "still faulted" in result.message


def test_rerun_replaces_the_last_result(clock, record):
    record.mp_processing = MPProcessingData(max_amplitude_reached=9.0)
    record.mp_processing.add_quench(amplitude=9.0)
    cavity = FakeCavity(clock, start=5.0, ades_max=5.0)
    phase = make_phase(cavity, record)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    assert record.mp_processing.quench_count == 0
    assert record.mp_processing.max_amplitude_reached == pytest.approx(5.0)


def test_dry_run_writes_nothing(clock, record):
    cavity = FakeCavity(clock, start=5.0, ades_max=6.0, quench_at=[10])
    phase = make_phase(cavity, record, dry_run=True)

    assert run_steps(phase).result is PhaseResult.SUCCESS

    assert cavity.setup_rf_calls == []
    assert cavity.ades_writes == []
    assert cavity.resets == []


def test_full_run_completes_the_phase(clock, record):
    record.set_phase_status(
        CommissioningPhase.PIEZO_WITH_RF, PhaseStatus.COMPLETE
    )
    cavity = FakeCavity(clock, start=5.0, ades_max=5.4, quench_at=[40])
    phase = make_phase(cavity, record)

    assert phase.run() is True

    assert (
        record.get_phase_status(CommissioningPhase.MP_PROCESSING)
        is PhaseStatus.COMPLETE
    )
    assert record.mp_processing.quench_count == 1
