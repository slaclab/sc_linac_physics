"""Run a blocking call off the Qt main thread and report back by signal.

This replaces Worker(QThread) in utils/qt.py. Usage::

    def ramp(task, cavity, amp):
        task.report_status(f"Ramping {cavity} to {amp} MV")
        cavity.setup_rf(amp)
        return amp

    self.ramp_task = BackgroundTask(ramp, cavity, 16.0, name="q0-ramp")
    self.ramp_task.status.connect(self.status_label.setText)
    self.ramp_task.failed.connect(self.show_error)
    self.ramp_task.start()

The target runs on a daemon threading.Thread. The task is a QObject made
on the main thread, so its signals reach main-thread slots through Qt's
event queue, the same way FaultCountDisplay._start_fetch reports (#325).

Not QThread: QThreads that outlived their owner crashed test workers
(#307, #308). Not ThreadPoolExecutor: Python joins its workers at exit, so
a call stuck in archiver retries keeps the app open. A daemon thread is
abandoned at exit instead. The cost: exit can stop the thread at any line,
including between two PV writes. Apps that write PVs should stop their
task cleanly before closing.
"""

import logging
import threading
from typing import Any, Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# ca_attach_context in libca is not safe to call from two threads at once
# (see launcher_service.py::_ca_init_lock), so attaching takes this lock.
_ca_attach_lock = threading.Lock()

Runner = Callable[["BackgroundTask"], None]


def run_in_daemon_thread(task: "BackgroundTask") -> None:
    """The default runner: run the task on a new daemon thread."""
    task._thread = threading.Thread(
        target=_run_with_ca_context, args=(task,), daemon=True, name=task.name
    )
    task._thread.start()


def run_inline(task: "BackgroundTask") -> None:
    """Run the task on the calling thread, before start() returns.

    For tests: the signals fire in order, with no thread to wait for.
    """
    task._run()


def _run_with_ca_context(task: "BackgroundTask") -> None:
    """Attach the pyepics initial CA context, run the task, detach.

    Without it, pyepics in this thread makes its own CA context, which
    libCom's thread-exit cleanup can crash on (see
    launcher_service.py::_epics_thread).
    """
    import epics.ca

    attached = False
    try:
        with _ca_attach_lock:
            epics.ca.use_initial_context()
        attached = True
    except Exception:  # not fatal: pyepics makes a context on first use
        logger.warning("Could not attach the CA context", exc_info=True)
    try:
        task._run()
    finally:
        if attached:
            epics.ca.detach_context()


class BackgroundTask(QObject):
    """Run target(task, *args, **kwargs) once, off the main thread.

    Signals, all delivered on the main thread:

    - status(str), progress(int): sent by the target through
      report_status() and report_progress(). Use those, not .emit():
      if the owner deletes the task mid-run, they do nothing, where
      .emit() would raise inside the target and skip the rest of it.
    - succeeded(object): the target's return value.
    - failed(str): "ExcType: message" for any exception the target raised.
      The traceback goes to the log.
    - done(): last, after succeeded or failed. Connect cleanup here.

    Cancelling is cooperative. request_cancel() sets a flag that the
    target reads as task.cancel_requested. Nothing stops the thread from
    outside. Code with its own abort flag (Q0Cryomodule.abort_flag,
    Cavity.request_abort) keeps using it.
    """

    status = pyqtSignal(str)
    progress = pyqtSignal(int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    done = pyqtSignal()

    def __init__(
        self,
        target: Callable[..., Any],
        *args,
        name: str = "background-task",
        runner: Runner = run_in_daemon_thread,
        parent: Optional[QObject] = None,
        **kwargs,
    ):
        super().__init__(parent)
        self.name = name
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._runner = runner
        self._cancel = threading.Event()
        self._started = False
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the target. A task runs once; make a new one to rerun."""
        if self._started:
            raise RuntimeError(f"{self.name} already started")
        self._started = True
        self._running = True
        self._runner(self)

    def report_status(self, message: str) -> None:
        self._emit("status", message)

    def report_progress(self, percent: int) -> None:
        self._emit("progress", percent)

    def request_cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    @property
    def is_running(self) -> bool:
        return self._running

    def _run(self) -> None:
        try:
            result = self._target(self, *self._args, **self._kwargs)
        except Exception as e:
            logger.exception("%s failed", self.name)
            self._running = False
            self._emit("failed", f"{type(e).__name__}: {e}")
        else:
            self._running = False
            self._emit("succeeded", result)
        self._emit("done")

    def _emit(self, signal_name: str, *args) -> None:
        # Look the signal up inside the try: on a task its owner deleted
        # mid-run, even reading the signal attribute raises.
        try:
            getattr(self, signal_name).emit(*args)
        except RuntimeError:
            pass
