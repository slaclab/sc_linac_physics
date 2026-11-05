"""Tests for PhaseRun, the step loop every phase runs through."""

import threading
import time

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    AbortHook,
    PhaseRun,
    SegmentOutcome,
    StepListener,
    cavity_abort_hook,
    stepper_abort_hook,
)


def _ok(message="ok", **data):
    return PhaseStepResult(PhaseResult.SUCCESS, message, data or None)


def _retry(message="not yet", delay=0.0):
    return PhaseStepResult(
        PhaseResult.RETRY, message, retry_delay_seconds=delay
    )


def _failed(message="broken"):
    return PhaseStepResult(PhaseResult.FAILED, message)


class _ScriptedPhase(PhaseBase):
    """Returns (or raises) the next scripted outcome for each step."""

    def __init__(self, context, script=None, finalize_error=None):
        super().__init__(context)
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list[str] = []
        self.finalized = False
        self.finalize_error = finalize_error
        self.before_step = None  # optional callable(step), runs first

    @property
    def phase_type(self):
        return CommissioningPhase.PIEZO_PRE_RF

    def validate_prerequisites(self):
        return True, "ok"

    def get_phase_steps(self):
        return list(self.script)

    def execute_step(self, step_name):
        self.calls.append(step_name)
        if self.before_step is not None:
            self.before_step(step_name)
        queue = self.script.get(step_name) or [_ok()]
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def finalize_phase(self):
        if self.finalize_error is not None:
            raise self.finalize_error
        self.finalized = True


class _Recorder(StepListener):
    def __init__(self):
        self.events = []

    def on_step_started(self, step, index, total):
        self.events.append(("started", step, index, total))

    def on_attempt(self, step, attempt, result):
        self.events.append(("attempt", step, attempt, result.result))

    def on_retry_wait(self, step, attempt, delay):
        self.events.append(("retry_wait", step, attempt, delay))

    def on_step_finished(self, step, result):
        self.events.append(("finished", step, result.result))

    def on_holding(self, step, reason):
        self.events.append(("holding", step, reason))

    def on_progress(self, step, percent):
        self.events.append(("progress", step, percent))

    def of(self, kind):
        return [e for e in self.events if e[0] == kind]


def _context(phase_instance_id=None):
    return PhaseContext(
        record=CommissioningRecord(linac=1, cryomodule="02", cavity_number=1),
        operator="tester",
        phase_instance_id=phase_instance_id,
    )


def _make(script=None, **run_kwargs):
    phase = _ScriptedPhase(_context(), script)
    listener = _Recorder()
    run = PhaseRun(phase, listener=listener, **run_kwargs)
    return phase, run, listener


def _status(phase):
    return phase.context.record.get_phase_status(phase.phase_type)


def _checkpoints(phase, step=None):
    history = phase.context.record.phase_history
    return [c for c in history if step is None or c.step_name == step]


def _in_thread(fn):
    box = {}
    thread = threading.Thread(target=lambda: box.update(result=fn()))
    thread.start()
    return thread, box


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ---------------------------------------------------------------- results


def test_all_steps_succeed():
    phase, run, _ = _make({"a": [_ok()], "b": [_ok()]})

    result = run.run_steps(["a", "b"])

    assert result.outcome is SegmentOutcome.COMPLETED
    assert phase.calls == ["a", "b"]
    assert set(result.results) == {"a", "b"}


def test_skip_result_continues_to_next_step():
    skip = PhaseStepResult(PhaseResult.SKIP, "nothing to do")
    phase, run, _ = _make({"a": [skip], "b": [_ok()]})

    assert run.run_steps(["a", "b"]).outcome is SegmentOutcome.COMPLETED
    assert _checkpoints(phase, "a")[0].success is True


def test_failed_result_stops_segment_and_fails_phase():
    phase, run, _ = _make({"a": [_failed("no RF")], "b": [_ok()]})

    result = run.run_steps(["a", "b"])

    assert result.outcome is SegmentOutcome.FAILED
    assert result.step == "a"
    assert result.message == "no RF"
    assert phase.calls == ["a"]
    assert _status(phase) is PhaseStatus.FAILED


def test_retry_until_success():
    phase, run, listener = _make({"a": [_retry(), _retry(), _ok()]})

    assert run.run_steps(["a"]).outcome is SegmentOutcome.COMPLETED
    assert phase.calls == ["a", "a", "a"]
    assert [e[2] for e in listener.of("retry_wait")] == [1, 2]


def test_retry_gives_up_after_max_attempts():
    phase, run, _ = _make({"a": [_retry("settling")]}, max_attempts=3)

    result = run.run_steps(["a"])

    assert result.outcome is SegmentOutcome.FAILED
    assert phase.calls == ["a", "a", "a"]
    assert result.message == "a gave up after 3 attempts: settling"
    assert _status(phase) is PhaseStatus.FAILED


def test_attempts_reset_for_each_step():
    """#341: a counter carried across steps fails step b early."""
    phase, run, _ = _make(
        {"a": [_retry(), _retry(), _ok()], "b": [_retry(), _retry(), _ok()]}
    )

    assert run.run_steps(["a", "b"]).outcome is SegmentOutcome.COMPLETED
    assert phase.calls.count("b") == 3


def test_exception_fails_without_retry():
    phase, run, _ = _make({"a": [RuntimeError("PV timeout"), _ok()]})

    result = run.run_steps(["a"])

    assert result.outcome is SegmentOutcome.FAILED
    assert phase.calls == ["a"]
    assert "PV timeout" in result.message
    checkpoint = _checkpoints(phase, "a")[0]
    assert checkpoint.success is False
    assert checkpoint.error_message == "PV timeout"
    assert _status(phase) is PhaseStatus.FAILED


def test_retry_waits_the_requested_delay():
    waits = []
    phase, run, _ = _make(
        {"a": [_retry(delay=1.5), _ok()]}, sleep_fn=waits.append
    )

    run.run_steps(["a"])

    assert waits == [1.5]


def test_negative_retry_delay_does_not_wait():
    waits = []
    phase, run, _ = _make(
        {"a": [_retry(delay=-2), _ok()]}, sleep_fn=waits.append
    )

    assert run.run_steps(["a"]).outcome is SegmentOutcome.COMPLETED
    assert waits == []


# ------------------------------------------------------------ checkpoints


def test_one_checkpoint_per_attempt_with_instance_id():
    phase = _ScriptedPhase(
        _context(phase_instance_id=7), {"a": [_retry("wait"), _ok("done")]}
    )
    run = PhaseRun(phase)

    run.run_steps(["a"])

    checkpoints = _checkpoints(phase, "a")
    assert [c.notes for c in checkpoints] == ["wait", "done"]
    assert [c.success for c in checkpoints] == [False, True]
    assert all(c.measurements["phase_instance_id"] == 7 for c in checkpoints)
    assert all(c.operator == "tester" for c in checkpoints)


def test_checkpoint_keeps_step_data():
    phase, run, _ = _make({"a": [_ok(loaded_q=4.1e7)]})

    run.run_steps(["a"])

    assert _checkpoints(phase, "a")[0].measurements["loaded_q"] == 4.1e7


# --------------------------------------------------------------- lifecycle


def test_run_steps_marks_phase_started_once():
    phase, run, _ = _make({"a": [_ok()], "b": [_ok()]})

    run.run_steps(["a"])
    run.run_steps(["b"])
    run.start()

    assert len(_checkpoints(phase, "phase_start")) == 1
    assert phase.context.record.current_phase is phase.phase_type


def test_complete_finalizes_and_marks_complete():
    phase, run, _ = _make({"a": [_ok()]})
    run.run_steps(["a"])

    result = run.complete()

    assert result.outcome is SegmentOutcome.COMPLETED
    assert phase.finalized is True
    assert _status(phase) is PhaseStatus.COMPLETE
    assert len(_checkpoints(phase, "phase_complete")) == 1


def test_finalize_error_fails_phase():
    phase = _ScriptedPhase(
        _context(), {"a": [_ok()]}, finalize_error=ValueError("no data")
    )
    run = PhaseRun(phase)
    run.run_steps(["a"])

    result = run.complete()

    assert result.outcome is SegmentOutcome.FAILED
    assert "no data" in result.message
    assert _status(phase) is PhaseStatus.FAILED
    assert _checkpoints(phase, "finalize_phase")[0].success is False
    assert _checkpoints(phase, "phase_complete") == []


def test_fail_records_message():
    phase, run, _ = _make()
    run.start()

    run.fail("operator stopped", step="read_results")

    assert _status(phase) is PhaseStatus.FAILED
    checkpoint = _checkpoints(phase, "read_results")[0]
    assert checkpoint.success is False
    assert checkpoint.error_message == "operator stopped"


def test_concurrent_run_steps_is_refused():
    phase, run, _ = _make({"a": [_ok()]})
    release = threading.Event()
    phase.before_step = lambda step: release.wait(2)
    thread, _ = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: run.running)

    with pytest.raises(RuntimeError):
        run.run_steps(["a"])

    release.set()
    thread.join(2)
    assert run.running is False


# --------------------------------------------------------------- skip_step


def test_skip_step_records_operator_and_justification():
    phase, run, _ = _make({"push_results": [_ok()]})
    run.start()

    run.skip_step("push_results", "Ryan", "Loaded Q out of window")

    assert phase.calls == []
    checkpoint = _checkpoints(phase, "push_results")[0]
    assert checkpoint.success is True
    assert checkpoint.notes == "Skipped by operator: Loaded Q out of window"
    assert checkpoint.measurements["skipped_by"] == "Ryan"
    assert checkpoint.measurements["justification"] == (
        "Loaded Q out of window"
    )


@pytest.mark.parametrize("operator, why", [("Ryan", "  "), ("", "reason")])
def test_skip_step_requires_operator_and_justification(operator, why):
    _, run, _ = _make()

    with pytest.raises(ValueError):
        run.skip_step("push_results", operator, why)


def test_skip_step_refused_while_running():
    phase, run, _ = _make({"a": [_ok()]})
    release = threading.Event()
    phase.before_step = lambda step: release.wait(2)
    thread, _ = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: run.running)

    with pytest.raises(RuntimeError):
        run.skip_step("b", "Ryan", "reason")

    release.set()
    thread.join(2)


# ------------------------------------------------------------------- abort


def test_abort_before_first_attempt():
    phase, run, _ = _make({"a": [_ok()]})
    run.request_abort()

    result = run.run_steps(["a"])

    assert result.outcome is SegmentOutcome.ABORTED
    assert result.step == "a"
    assert phase.calls == []
    assert _checkpoints(phase, "a")[0].notes == "Aborted before a"
    assert _status(phase) is PhaseStatus.FAILED


def test_abort_between_steps():
    phase, run, _ = _make({"a": [_ok()], "b": [_ok()]})
    phase.before_step = lambda step: run.request_abort()

    result = run.run_steps(["a", "b"])

    assert result.outcome is SegmentOutcome.ABORTED
    assert result.step == "b"
    assert phase.calls == ["a"]


def test_abort_ends_retry_wait_without_another_attempt():
    phase, run, _ = _make({"a": [_retry(delay=30), _ok()]})
    thread, box = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: phase.calls == ["a"])

    started = time.monotonic()
    run.request_abort()
    thread.join(2)

    assert time.monotonic() - started < 1.0
    assert box["result"].outcome is SegmentOutcome.ABORTED
    assert phase.calls == ["a"]


def test_abort_calls_hooks_and_context():
    calls = []
    hook = AbortHook(
        request=lambda: calls.append("request"),
        clear=lambda: calls.append("clear"),
    )
    phase, run, _ = _make(abort_hooks=[hook])

    run.request_abort()
    assert phase.context.is_abort_requested()
    run.clear_abort()

    assert calls == ["request", "clear"]
    assert not phase.context.is_abort_requested()


def test_abort_hook_error_is_swallowed():
    calls = []

    def boom():
        raise RuntimeError("CA down")

    hooks = [
        AbortHook(request=boom, clear=boom),
        AbortHook(request=lambda: calls.append("second"), clear=lambda: None),
    ]
    phase, run, _ = _make(abort_hooks=hooks)

    run.request_abort()
    run.clear_abort()

    assert calls == ["second"]


def test_cavity_abort_hook():
    class Cavity:
        abort_flag = False

        def request_abort(self):
            self.abort_flag = True

    cavity = Cavity()
    hook = cavity_abort_hook(cavity)

    hook.request()
    assert cavity.abort_flag is True
    hook.clear()
    assert cavity.abort_flag is False


def test_stepper_abort_hook():
    class Stepper:
        abort_flag = False

    stepper = Stepper()
    hook = stepper_abort_hook(stepper)

    hook.request()
    assert stepper.abort_flag is True
    hook.clear()
    assert stepper.abort_flag is False


# ------------------------------------------------------- pause, step mode


def test_pause_holds_until_resume():
    phase, run, listener = _make({"a": [_ok()]})
    run.pause()
    thread, box = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: listener.of("holding"))
    assert phase.calls == []

    run.resume()
    thread.join(2)

    assert box["result"].outcome is SegmentOutcome.COMPLETED
    assert listener.of("holding") == [("holding", "a", "paused")]


def test_pause_applies_between_retry_attempts():
    phase, run, _ = _make({"a": [_retry(), _ok()]})
    phase.before_step = lambda step: run.pause()
    thread, box = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: run.paused and phase.calls == ["a"])
    time.sleep(0.2)
    assert phase.calls == ["a"]

    phase.before_step = None
    run.resume()
    thread.join(2)
    assert box["result"].outcome is SegmentOutcome.COMPLETED


def test_abort_ends_pause():
    phase, run, _ = _make({"a": [_ok()]})
    run.pause()
    thread, box = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: run.running)

    run.request_abort()
    thread.join(2)

    assert box["result"].outcome is SegmentOutcome.ABORTED
    assert phase.calls == []


def test_context_abort_ends_pause():
    """Code that aborts the context directly still ends a hold."""
    phase, run, _ = _make({"a": [_ok()]})
    run.pause()
    thread, box = _in_thread(lambda: run.run_steps(["a"]))
    assert _wait_until(lambda: run.running)

    phase.context.request_abort()
    thread.join(2)

    assert not thread.is_alive()
    assert box["result"].outcome is SegmentOutcome.ABORTED


def test_step_mode_runs_one_step_per_next():
    phase, run, listener = _make({"a": [_ok()], "b": [_ok()]})
    run.set_step_mode(True)
    thread, box = _in_thread(lambda: run.run_steps(["a", "b"]))
    assert _wait_until(lambda: listener.of("holding"))
    assert phase.calls == []

    run.next_step()
    assert _wait_until(lambda: len(listener.of("holding")) == 2)
    assert phase.calls == ["a"]

    run.next_step()
    thread.join(2)
    assert phase.calls == ["a", "b"]
    assert box["result"].outcome is SegmentOutcome.COMPLETED
    assert listener.of("holding") == [
        ("holding", "a", "step_mode"),
        ("holding", "b", "step_mode"),
    ]


def test_step_mode_does_not_hold_retries():
    phase, run, _ = _make({"a": [_retry(), _ok()]})
    run.set_step_mode(True)
    run.next_step()

    assert run.run_steps(["a"]).outcome is SegmentOutcome.COMPLETED
    assert phase.calls == ["a", "a"]


def test_step_mode_off_releases_hold():
    phase, run, listener = _make({"a": [_ok()], "b": [_ok()]})
    run.set_step_mode(True)
    thread, box = _in_thread(lambda: run.run_steps(["a", "b"]))
    assert _wait_until(lambda: listener.of("holding"))

    run.set_step_mode(False)
    thread.join(2)

    assert phase.calls == ["a", "b"]
    assert box["result"].outcome is SegmentOutcome.COMPLETED


# ---------------------------------------------------- progress, listeners


def test_progress_within_segment():
    _, run, listener = _make({"a": [_ok()], "b": [_ok()]})

    run.run_steps(["a", "b"])

    assert listener.of("progress") == [
        ("progress", "a", 0),
        ("progress", "b", 50),
    ]
    assert listener.of("started") == [
        ("started", "a", 0, 2),
        ("started", "b", 1, 2),
    ]


def test_progress_with_offset_across_stages():
    _, run, listener = _make({"c": [_ok()]})

    run.run_steps(["c"], progress_offset=6, progress_total=8)

    assert listener.of("progress") == [("progress", "c", 75)]


def test_listener_sees_attempts_and_finish():
    _, run, listener = _make({"a": [_retry(), _ok()]})

    run.run_steps(["a"])

    assert listener.of("attempt") == [
        ("attempt", "a", 1, PhaseResult.RETRY),
        ("attempt", "a", 2, PhaseResult.SUCCESS),
    ]
    assert listener.of("finished") == [("finished", "a", PhaseResult.SUCCESS)]


def test_listener_error_does_not_stop_run():
    class Broken(StepListener):
        def on_step_started(self, step, index, total):
            raise RuntimeError("widget gone")

    phase = _ScriptedPhase(_context(), {"a": [_ok()]})
    run = PhaseRun(phase, listener=Broken())

    assert run.run_steps(["a"]).outcome is SegmentOutcome.COMPLETED


def test_empty_segment_completes():
    _, run, _ = _make()

    assert run.run_steps([]).outcome is SegmentOutcome.COMPLETED


# ------------------------------------------------- review fixes (final)


def test_step_returning_none_fails_phase():
    """A step method missing its return must fail the phase, not escape."""
    phase, run, _ = _make({"a": [None]})

    result = run.run_steps(["a"])

    assert result.outcome is SegmentOutcome.FAILED
    assert result.step == "a"
    assert _status(phase) is PhaseStatus.FAILED
    assert _checkpoints(phase, "a")[-1].success is False
    assert run.running is False


def test_abort_during_step_reports_aborted():
    """Phases turn an abort inside a hardware wait into FAILED."""
    phase, run, _ = _make({"wait": [_failed("Aborted during wait")]})
    phase.before_step = lambda step: run.request_abort()

    result = run.run_steps(["wait"])

    assert result.outcome is SegmentOutcome.ABORTED
    assert result.message == "Aborted during wait"
    assert _status(phase) is PhaseStatus.FAILED


def test_abort_hook_error_still_aborts_context():
    def boom():
        raise RuntimeError("CA down")

    phase, run, _ = _make(abort_hooks=[AbortHook(request=boom, clear=boom)])

    run.request_abort()

    assert phase.context.is_abort_requested()


def test_exception_attempt_is_reported_and_kept_in_results():
    phase, run, listener = _make({"a": [_retry(), RuntimeError("PV gone")]})

    result = run.run_steps(["a"])

    assert result.results["a"].result is PhaseResult.FAILED
    assert "PV gone" in result.results["a"].message
    assert listener.of("attempt") == [
        ("attempt", "a", 1, PhaseResult.RETRY),
        ("attempt", "a", 2, PhaseResult.FAILED),
    ]


def test_reserved_run_counts_as_running_and_refuses_another_reserve():
    _, run, _ = _make({"a": [_ok()]})

    assert run.try_reserve() is True
    assert run.running is True
    assert run.try_reserve() is False
    with pytest.raises(RuntimeError):
        run.skip_step("a", "Ryan", "reason")

    run.release()
    assert run.running is False
    assert run.try_reserve() is True
