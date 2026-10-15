"""Run a PhaseRun segment on a daemon thread and report it by signal.

A controller owns one RunnerBridge, connects its signals to the view, and
calls start_segment() from a button. The steps run on a daemon
threading.Thread (not a QThread). Each StepListener call is re-emitted as a
signal, so slots on the GUI thread receive it queued and in emit order: a
step_finished slot always runs before that segment's segment_finished slot.
"""

import logging
import threading
from collections.abc import Iterable

from PyQt5.QtCore import QObject, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    PhaseRun,
    SegmentOutcome,
    SegmentResult,
    StepListener,
)

logger = logging.getLogger(__name__)


class RunnerBridge(QObject, StepListener):
    """One segment at a time, on a daemon thread."""

    step_started = pyqtSignal(str, int, int)  # step, index, steps in segment
    attempt_finished = pyqtSignal(str, int, object)  # step, attempt, result
    retry_waiting = pyqtSignal(str, int, float)  # step, attempt, delay (s)
    step_finished = pyqtSignal(str, object)  # step, PhaseStepResult
    holding = pyqtSignal(str, str)  # step, "paused" or "step_mode"
    progress = pyqtSignal(str, int)  # step, percent
    log = pyqtSignal(str)  # one line for the panel's log
    segment_finished = pyqtSignal(object)  # SegmentResult, exactly once

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        self._max_attempts = 0

    @property
    def running(self) -> bool:
        return self._busy

    def start_segment(
        self,
        run: PhaseRun,
        steps: Iterable[str],
        *,
        progress_offset: int = 0,
        progress_total: int | None = None,
        then_complete: bool = False,
    ) -> bool:
        """Start steps on a daemon thread. False if a segment is running.

        Call from the GUI thread. A button press is a fresh request, so an
        Abort left over from an earlier segment is cleared first, on the
        context and on every AbortHook. With then_complete, a segment that
        completes is followed by run.complete() (finalize_phase and COMPLETE)
        on the same thread.
        """
        if self._busy:
            return False
        self._busy = True
        steps = list(steps)
        run.listener = self
        self._max_attempts = run.max_attempts
        run.clear_abort()

        def work() -> None:
            try:
                result = run.run_steps(
                    steps,
                    progress_offset=progress_offset,
                    progress_total=progress_total,
                )
                if then_complete and result.outcome is SegmentOutcome.COMPLETED:
                    completed = run.complete()
                    completed.results = result.results
                    result = completed
            except Exception as exc:
                logger.exception("Segment %s raised", steps)
                result = SegmentResult(
                    SegmentOutcome.FAILED,
                    f"Run failed: {type(exc).__name__}: {exc}",
                )
            self._log_outcome(result)
            # Cleared before the emit, so a segment_finished slot may start
            # the next segment straight away.
            self._busy = False
            self.segment_finished.emit(result)

        threading.Thread(
            target=work, name="phase-step-runner", daemon=True
        ).start()
        return True

    def _log_outcome(self, result: SegmentResult) -> None:
        if result.outcome is SegmentOutcome.COMPLETED:
            return
        message = result.message
        if result.step and not message.startswith(result.step):
            message = f"{result.step}: {message}"
        mark = "✗" if result.outcome is SegmentOutcome.FAILED else "⊘"
        self.log.emit(f"{mark} {message}")

    # ---------------------------------------------------- StepListener

    def on_step_started(self, step: str, index: int, total: int) -> None:
        self.step_started.emit(step, index, total)

    def on_attempt(
        self, step: str, attempt: int, result: PhaseStepResult
    ) -> None:
        self.attempt_finished.emit(step, attempt, result)
        if result.result is PhaseResult.RETRY:
            self.log.emit(
                f"{step}: {result.message} "
                f"(attempt {attempt} of {self._max_attempts})"
            )

    def on_retry_wait(self, step: str, attempt: int, delay: float) -> None:
        self.retry_waiting.emit(step, attempt, delay)

    def on_step_finished(self, step: str, result: PhaseStepResult) -> None:
        if result.result is PhaseResult.SUCCESS:
            self.log.emit(f"✓ {step}: {result.message}")
        elif result.result is PhaseResult.SKIP:
            self.log.emit(f"⊘ {step} skipped: {result.message}")
        self.step_finished.emit(step, result)

    def on_holding(self, step: str, reason: str) -> None:
        self.holding.emit(step, reason)

    def on_progress(self, step: str, percent: int) -> None:
        self.progress.emit(step, percent)
