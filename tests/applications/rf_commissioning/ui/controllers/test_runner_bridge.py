"""Tests for RunnerBridge: PhaseRun on a daemon thread, reported by signal."""

import threading

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
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.runner_bridge import (  # noqa: E501
    RunnerBridge,
)


class _Phase(PhaseBase):
    def __init__(self, context, script=None):
        super().__init__(context)
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.gate = None  # threading.Event the steps wait on, if set

    @property
    def phase_type(self):
        return CommissioningPhase.SSA_CHAR

    def validate_prerequisites(self):
        return True, "ok"

    def get_phase_steps(self):
        return list(self.script)

    def execute_step(self, step_name):
        if self.gate is not None:
            self.gate.wait(2)
        queue = self.script.get(step_name) or [
            PhaseStepResult(PhaseResult.SUCCESS, "ok")
        ]
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def finalize_phase(self):
        pass


def _run(script=None, **kwargs):
    context = PhaseContext(
        record=CommissioningRecord(linac=1, cryomodule="02", cavity_number=1),
        operator="tester",
    )
    phase = _Phase(context, script)
    return phase, PhaseRun(phase, **kwargs)


def _ok(message="ok"):
    return PhaseStepResult(PhaseResult.SUCCESS, message)


def _record(bridge):
    events = []
    bridge.step_started.connect(lambda s, i, n: events.append(("started", s)))
    bridge.step_finished.connect(lambda s, r: events.append(("finished", s)))
    bridge.segment_finished.connect(lambda r: events.append(("segment", r)))
    bridge.log.connect(lambda line: events.append(("log", line)))
    return events


def test_segment_signals_arrive_in_order(qtbot):
    bridge = RunnerBridge()
    events = _record(bridge)
    _, run = _run({"a": [_ok()], "b": [_ok()]})

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000) as blocker:
        assert bridge.start_segment(run, ["a", "b"]) is True

    qtbot.waitUntil(lambda: any(e[0] == "segment" for e in events))
    result = blocker.args[0]
    assert result.outcome is SegmentOutcome.COMPLETED
    order = [e for e in events if e[0] != "log"]
    assert order[:4] == [
        ("started", "a"),
        ("finished", "a"),
        ("started", "b"),
        ("finished", "b"),
    ]
    assert [e[0] for e in events].count("segment") == 1
    assert order[-1][0] == "segment"


def test_then_complete_marks_phase_complete(qtbot):
    bridge = RunnerBridge()
    phase, run = _run({"a": [_ok()]})

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000) as blocker:
        bridge.start_segment(run, ["a"], then_complete=True)

    assert blocker.args[0].outcome is SegmentOutcome.COMPLETED
    assert "a" in blocker.args[0].results
    status = phase.context.record.get_phase_status(phase.phase_type)
    assert status is PhaseStatus.COMPLETE


def test_then_complete_not_run_after_failed_segment(qtbot):
    bridge = RunnerBridge()
    phase, run = _run({"a": [PhaseStepResult(PhaseResult.FAILED, "no")]})

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000) as blocker:
        bridge.start_segment(run, ["a"], then_complete=True)

    assert blocker.args[0].outcome is SegmentOutcome.FAILED
    status = phase.context.record.get_phase_status(phase.phase_type)
    assert status is PhaseStatus.FAILED


def test_second_segment_refused_while_running(qtbot):
    bridge = RunnerBridge()
    phase, run = _run({"a": [_ok()]})
    phase.gate = threading.Event()

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000):
        assert bridge.start_segment(run, ["a"]) is True
        assert bridge.running is True
        assert bridge.start_segment(run, ["a"]) is False
        phase.gate.set()

    qtbot.waitUntil(lambda: not bridge.running)


def test_start_segment_clears_stale_abort(qtbot):
    cleared = []
    hook = AbortHook(request=lambda: None, clear=lambda: cleared.append(1))
    bridge = RunnerBridge()
    phase, run = _run({"a": [_ok()]}, abort_hooks=[hook])
    run.request_abort()

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000) as blocker:
        bridge.start_segment(run, ["a"])

    assert blocker.args[0].outcome is SegmentOutcome.COMPLETED
    assert cleared == [1]


def test_retry_and_failure_are_logged(qtbot):
    bridge = RunnerBridge()
    lines = []
    bridge.log.connect(lines.append)
    retry = PhaseStepResult(
        PhaseResult.RETRY, "settling", retry_delay_seconds=0
    )
    _, run = _run({"read": [retry]}, max_attempts=2)

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000):
        bridge.start_segment(run, ["read"])

    qtbot.waitUntil(lambda: any("gave up" in line for line in lines))
    assert "read: settling (attempt 1 of 2)" in lines
    assert "✗ read gave up after 2 attempts: settling" in lines


def test_success_and_skip_are_logged(qtbot):
    bridge = RunnerBridge()
    lines = []
    bridge.log.connect(lines.append)
    skip = PhaseStepResult(PhaseResult.SKIP, "already off")
    _, run = _run({"a": [_ok("done")], "b": [skip]})

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000):
        bridge.start_segment(run, ["a", "b"])

    qtbot.waitUntil(lambda: len(lines) >= 2)
    assert lines == ["✓ a: done", "⊘ b skipped: already off"]


def test_worker_error_becomes_failed_result(qtbot):
    bridge = RunnerBridge()
    _, run = _run({"a": [_ok()]})

    def broken(*args, **kwargs):
        raise RuntimeError("bug in run_steps")

    run.run_steps = broken

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000) as blocker:
        bridge.start_segment(run, ["a"])

    assert blocker.args[0].outcome is SegmentOutcome.FAILED
    assert "bug in run_steps" in blocker.args[0].message
    qtbot.waitUntil(lambda: not bridge.running)


def test_holding_and_progress_signals(qtbot):
    bridge = RunnerBridge()
    holds, progress = [], []
    bridge.holding.connect(lambda s, reason: holds.append((s, reason)))
    bridge.progress.connect(lambda s, pct: progress.append((s, pct)))
    _, run = _run({"a": [_ok()]})
    run.set_step_mode(True)

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000):
        bridge.start_segment(run, ["a"], progress_offset=1, progress_total=4)
        qtbot.waitUntil(lambda: holds == [("a", "step_mode")])
        run.next_step()

    qtbot.waitUntil(lambda: progress == [("a", 25)])


def test_failed_result_without_message_still_finishes(qtbot):
    bridge = RunnerBridge()
    _, run = _run({"a": [PhaseStepResult(PhaseResult.FAILED, None)]})

    with qtbot.waitSignal(bridge.segment_finished, timeout=2000) as blocker:
        bridge.start_segment(run, ["a"])

    assert blocker.args[0].outcome is SegmentOutcome.FAILED
    qtbot.waitUntil(lambda: not bridge.running)


def test_start_segment_refuses_a_run_already_running(qtbot):
    cleared = []
    hook = AbortHook(request=lambda: None, clear=lambda: cleared.append(1))
    phase, run = _run({"a": [_ok()]}, abort_hooks=[hook])
    phase.gate = threading.Event()
    first, second = RunnerBridge(), RunnerBridge()

    with qtbot.waitSignal(first.segment_finished, timeout=2000):
        first.start_segment(run, ["a"])
        qtbot.waitUntil(lambda: run.running)
        cleared.clear()
        assert second.start_segment(run, ["a"]) is False
        assert cleared == []
        phase.gate.set()


def test_two_bridges_cannot_start_one_run_before_its_worker_runs(
    qtbot, monkeypatch
):
    """The run is reserved by start_segment, not when the worker begins."""
    from sc_linac_physics.applications.rf_commissioning.ui.controllers import (
        runner_bridge,
    )

    class _NotStarted:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass  # the first bridge's worker never gets to run_steps

    cleared = []
    hook = AbortHook(request=lambda: None, clear=lambda: cleared.append(1))
    _, run = _run({"a": [_ok()]}, abort_hooks=[hook])
    first, second = RunnerBridge(), RunnerBridge()
    monkeypatch.setattr(runner_bridge.threading, "Thread", _NotStarted)

    assert first.start_segment(run, ["a"]) is True
    cleared.clear()

    assert second.start_segment(run, ["a"]) is False
    assert cleared == []
    assert run.listener is first


def test_failed_thread_start_releases_the_run(qtbot, monkeypatch):
    from sc_linac_physics.applications.rf_commissioning.ui.controllers import (
        runner_bridge,
    )

    class _CannotStart:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

    _, run = _run({"a": [_ok()]})
    bridge = RunnerBridge()
    monkeypatch.setattr(runner_bridge.threading, "Thread", _CannotStart)

    assert bridge.start_segment(run, ["a"]) is False
    assert run.running is False
    assert bridge.running is False
