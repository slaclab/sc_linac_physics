import threading
from unittest.mock import patch

import pytest
from PyQt5.QtCore import QCoreApplication

from sc_linac_physics.utils import background
from sc_linac_physics.utils.background import BackgroundTask, run_inline


class Recorder:
    """Collect every signal a task emits, in order."""

    def __init__(self, task: BackgroundTask):
        self.events = []
        self.threads = []
        for name in ("status", "progress", "succeeded", "failed"):
            getattr(task, name).connect(
                lambda value, name=name: self._record(name, value)
            )
        task.done.connect(lambda: self._record("done", None))

    def _record(self, name, value):
        self.events.append((name, value))
        self.threads.append(threading.current_thread())


def _deliver(task: BackgroundTask):
    """Wait for a real thread, then deliver its queued signals.

    Not qtbot.waitSignal: its event loop returns at once in an xdist worker
    where an earlier test called app.quit().
    """
    task._thread.join(timeout=5)
    assert not task._thread.is_alive()
    QCoreApplication.sendPostedEvents()


def test_success_emits_status_then_result_then_done(qapp):
    def target(task, cavity, amp):
        task.status.emit(f"ramping {cavity}")
        task.progress.emit(50)
        return amp * 2

    task = BackgroundTask(target, "CM01 cav 1", 8.0, runner=run_inline)
    recorder = Recorder(task)
    task.start()
    assert recorder.events == [
        ("status", "ramping CM01 cav 1"),
        ("progress", 50),
        ("succeeded", 16.0),
        ("done", None),
    ]
    assert not task.is_running


def test_exception_emits_failed_then_done_and_logs(qapp):
    def target(task):
        raise ValueError("bad setpoint")

    task = BackgroundTask(target, runner=run_inline)
    recorder = Recorder(task)
    with patch.object(background, "logger") as logger:
        task.start()
    assert recorder.events == [
        ("failed", "ValueError: bad setpoint"),
        ("done", None),
    ]
    logger.exception.assert_called_once()


def test_keyword_arguments_reach_the_target(qapp):
    task = BackgroundTask(lambda task, *, amp: amp, amp=3.0, runner=run_inline)
    recorder = Recorder(task)
    task.start()
    assert ("succeeded", 3.0) in recorder.events


def test_cancel_is_cooperative(qapp):
    seen = []

    def target(task):
        seen.append(task.cancel_requested)
        task.request_cancel()
        seen.append(task.cancel_requested)

    BackgroundTask(target, runner=run_inline).start()
    assert seen == [False, True]


def test_start_twice_raises(qapp):
    task = BackgroundTask(lambda task: None, runner=run_inline)
    task.start()
    with pytest.raises(RuntimeError, match="already started"):
        task.start()


def test_default_runner_uses_a_daemon_thread_and_delivers_on_main(qapp):
    worker_threads = []

    def target(task):
        worker_threads.append(threading.current_thread())
        task.status.emit("working")
        return "ok"

    task = BackgroundTask(target, name="test-task")
    recorder = Recorder(task)
    task.start()
    _deliver(task)

    worker = worker_threads[0]
    assert worker is not threading.main_thread()
    assert worker.daemon
    assert worker.name == "test-task"
    assert [name for name, _ in recorder.events] == [
        "status",
        "succeeded",
        "done",
    ]
    assert all(t is threading.main_thread() for t in recorder.threads)


def test_default_runner_attaches_and_detaches_the_ca_context(qapp):
    import epics.ca

    calls = []
    with (
        patch.object(
            epics.ca,
            "use_initial_context",
            side_effect=lambda: calls.append("attach"),
        ),
        patch.object(
            epics.ca,
            "detach_context",
            side_effect=lambda: calls.append("detach"),
        ),
    ):
        task = BackgroundTask(lambda task: calls.append("target"))
        task.start()
        _deliver(task)
    assert calls == ["attach", "target", "detach"]


def test_ca_attach_failure_still_runs_the_target(qapp):
    import epics.ca

    with patch.object(
        epics.ca, "use_initial_context", side_effect=RuntimeError("no libca")
    ):
        task = BackgroundTask(lambda task: "ran")
        recorder = Recorder(task)
        task.start()
        _deliver(task)
    assert ("succeeded", "ran") in recorder.events


def test_deleted_task_does_not_raise_from_the_thread(qapp):
    """The owner may delete the task while its thread still runs."""
    from PyQt5 import sip

    release = threading.Event()
    errors = []

    def target(task):
        release.wait(5)
        return "late"

    task = BackgroundTask(target)
    with (
        patch.object(
            background.logger,
            "exception",
            side_effect=lambda *a, **k: errors.append(a),
        ),
        patch.object(
            threading,
            "excepthook",
            side_effect=lambda args: errors.append(args.exc_value),
        ),
    ):
        task.start()
        sip.delete(task)
        release.set()
        task._thread.join(timeout=5)
    assert not errors
