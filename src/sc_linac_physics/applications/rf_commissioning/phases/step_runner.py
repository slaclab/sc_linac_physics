"""One step loop for every commissioning phase.

PhaseRun runs a list of a phase's steps (a segment) and holds the rules
every controller used to write for itself: retries, abort, pause, step mode,
checkpoints and the phase's in-memory status. A controller runs one segment
per button. Cavity char measures, waits for the operator's review, then
pushes. Frequency tuning runs four stages on one PhaseRun.

The module has no Qt dependency. ui/controllers/runner_bridge.py runs a
segment on a daemon thread and turns StepListener calls into signals. The
batch window drives one PhaseRun per cavity from its own pool threads.

Rules (decided 2026-10-15):
- Only PhaseResult.RETRY is retried, up to max_attempts attempts in all.
  An exception fails the step. A step that raised may already have written
  a PV (SEL_ASET, PROBECALSTRT, a PUSH_*.PROC), so running it again blind
  could repeat that write.
- Abort is checked before every attempt, not only between steps, and it ends
  a retry delay or a hold at once.
- An operator may skip a step (skip_step), with a justification. Nothing is
  executed. Cavity char and piezo with RF use it to decline a push and still
  complete the phase.
- Saving to the database is not done here. The controllers still call
  start/complete/fail_active_phase_instance and save_active_record.
"""

import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseResult,
    PhaseStepResult,
)

logger = logging.getLogger(__name__)


class SegmentOutcome(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class SegmentResult:
    """How a segment (or complete()) ended.

    step is the step that failed or was aborted before. results holds the
    last PhaseStepResult of each step that ran.
    """

    outcome: SegmentOutcome
    message: str = ""
    step: str | None = None
    results: dict[str, PhaseStepResult] = field(default_factory=dict)


@dataclass(frozen=True)
class AbortHook:
    """The hardware side of Abort: how to request it and how to clear it."""

    request: Callable[[], None]
    clear: Callable[[], None]


def cavity_abort_hook(cavity) -> AbortHook:
    """Abort through Cavity.abort_flag.

    request_abort() sets abort_flag. Cavity.check_abort(), called inside the
    cavity's waits (e.g. wait_for_characterization), then calls turn_off()
    and raises CavityAbortError.
    """

    def clear() -> None:
        cavity.abort_flag = False

    return AbortHook(request=cavity.request_abort, clear=clear)


def stepper_abort_hook(stepper_tuner) -> AbortHook:
    """Abort through StepperTuner.abort_flag, which its check_abort() reads."""

    def request() -> None:
        stepper_tuner.abort_flag = True

    def clear() -> None:
        stepper_tuner.abort_flag = False

    return AbortHook(request=request, clear=clear)


class StepListener:
    """What a PhaseRun reports. Every method is called on the worker thread.

    The base class does nothing; override what you need. An exception from a
    listener is logged and does not stop the run.
    """

    def on_step_started(self, step: str, index: int, total: int) -> None:
        pass

    def on_attempt(
        self, step: str, attempt: int, result: PhaseStepResult
    ) -> None:
        pass

    def on_retry_wait(self, step: str, attempt: int, delay: float) -> None:
        pass

    def on_step_finished(self, step: str, result: PhaseStepResult) -> None:
        pass

    def on_holding(self, step: str, reason: str) -> None:
        """reason is "paused" or "step_mode"."""

    def on_progress(self, step: str, percent: int) -> None:
        pass


HOLD_PAUSED = "paused"
HOLD_STEP_MODE = "step_mode"


class PhaseRun:
    """Runs a phase's steps, one segment at a time.

    Controls (pause, step mode, abort) are thread-safe and meant to be called
    from the GUI thread while a segment runs on a worker thread.
    """

    # How often a hold or retry wait re-reads context.abort_requested, for
    # code that aborts the context directly rather than through request_abort.
    _POLL_SECONDS = 0.1

    def __init__(
        self,
        phase: PhaseBase,
        *,
        max_attempts: int = 3,
        abort_hooks: Iterable[AbortHook] = (),
        listener: StepListener | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        """
        Args:
            max_attempts: attempts per step, the first included.
            abort_hooks: called by request_abort() and clear_abort().
            sleep_fn: replaces the abortable retry wait. PhaseBase.run()
                passes its own sleep_fn here; tests pass a recorder.
        """
        self.phase = phase
        self.context = phase.context
        self.max_attempts = max_attempts
        self.listener = listener or StepListener()
        self._abort_hooks = tuple(abort_hooks)
        self._sleep_fn = sleep_fn
        self._cond = threading.Condition()
        self._running = False
        self._reserved = False
        self._started = False
        self._paused = False
        self._step_mode = False
        self._step_permits = 0

    # ------------------------------------------------------------ controls

    @property
    def running(self) -> bool:
        """True while a segment runs or a RunnerBridge has reserved the run."""
        return self._running or self._reserved

    def try_reserve(self) -> bool:
        """Claim the run for one segment. False if it is reserved or running.

        RunnerBridge calls this before it touches the listener or clears
        Abort, and holds it until its worker exits, so two bridges cannot
        both start this run (and repeat its steps' PV writes).
        """
        with self._cond:
            if self._running or self._reserved:
                return False
            self._reserved = True
            return True

    def release(self) -> None:
        with self._cond:
            self._reserved = False

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def step_mode(self) -> bool:
        return self._step_mode

    def pause(self) -> None:
        with self._cond:
            self._paused = True
            self._cond.notify_all()

    def resume(self) -> None:
        with self._cond:
            self._paused = False
            self._cond.notify_all()

    def set_step_mode(self, on: bool) -> None:
        with self._cond:
            self._step_mode = on
            self._step_permits = 0
            self._cond.notify_all()

    def next_step(self) -> None:
        """Let one step run in step mode."""
        with self._cond:
            self._step_permits += 1
            self._cond.notify_all()

    def request_abort(self) -> None:
        """Abort the commissioning context and the hardware, wake any wait."""
        self.context.request_abort()
        for hook in self._abort_hooks:
            try:
                hook.request()
            except Exception:
                logger.exception("Abort hook failed")
        with self._cond:
            self._cond.notify_all()

    def clear_abort(self) -> None:
        """Forget an earlier abort before starting a segment from a button."""
        self.context.abort_requested = False
        for hook in self._abort_hooks:
            try:
                hook.clear()
            except Exception:
                logger.exception("Clearing abort hook failed")

    # ----------------------------------------------------------- lifecycle

    def start(self) -> None:
        """Mark the phase IN_PROGRESS with a phase_start checkpoint, once."""
        if self._started:
            return
        self._started = True
        self.phase._mark_phase_started()

    def complete(self) -> SegmentResult:
        """Run finalize_phase(), then mark the phase COMPLETE.

        Marking it complete also saves a "phase_complete" checkpoint.
        """
        try:
            self.phase.finalize_phase()
        except Exception as exc:
            logger.exception("finalize_phase failed")
            message = f"finalize_phase raised {type(exc).__name__}: {exc}"
            self.fail(str(exc), step="finalize_phase")
            return SegmentResult(SegmentOutcome.FAILED, message)
        self.phase._mark_phase_completed()
        return SegmentResult(SegmentOutcome.COMPLETED)

    def fail(self, message: str, step: str | None = None) -> None:
        """Mark the phase FAILED with a checkpoint carrying message."""
        self._set_failed()
        self.phase._create_checkpoint(
            step_name=step or "phase_failed",
            success=False,
            notes=message,
            error_message=message,
        )

    def skip_step(self, step: str, operator: str, justification: str) -> None:
        """Record that the operator skipped step. The step is not executed."""
        if not operator or not operator.strip():
            raise ValueError("Skipping a step needs the operator's name")
        if not justification or not justification.strip():
            raise ValueError("Skipping a step needs a justification")
        if self.running:
            raise RuntimeError("Cannot skip a step while a segment runs")
        justification = justification.strip()
        self.phase._create_checkpoint(
            step_name=step,
            success=True,
            notes=f"Skipped by operator: {justification}",
            measurements={
                "skipped_by": operator.strip(),
                "justification": justification,
            },
        )

    # ------------------------------------------------------------ segments

    def run_steps(
        self,
        steps: Iterable[str],
        *,
        progress_offset: int = 0,
        progress_total: int | None = None,
    ) -> SegmentResult:
        """Run steps in order. Blocks; call it from a worker thread.

        Progress is (progress_offset + index) / progress_total, which lets a
        staged phase report one bar across its stages. progress_total
        defaults to the number of steps in this segment.
        """
        steps = list(steps)
        with self._cond:
            if self._running:
                raise RuntimeError("A segment is already running")
            self._running = True
        try:
            self.start()
            total = progress_total or len(steps)
            results: dict[str, PhaseStepResult] = {}
            for index, step in enumerate(steps):
                position = (index, len(steps), progress_offset + index, total)
                try:
                    ended = self._run_step(step, position, results)
                except Exception as exc:
                    # A fault in the bookkeeping, not in the step. The phase
                    # must still end FAILED rather than stay IN_PROGRESS.
                    logger.exception("Running step %s failed", step)
                    message = f"{step}: {type(exc).__name__}: {exc}"
                    self.fail(message, step=step)
                    ended = SegmentResult(SegmentOutcome.FAILED, message, step)
                if ended is not None:
                    ended.results = results
                    return ended
            return SegmentResult(SegmentOutcome.COMPLETED, results=results)
        finally:
            with self._cond:
                self._running = False

    def _run_step(
        self,
        step: str,
        position: tuple[int, int, int, int],
        results: dict[str, PhaseStepResult],
    ) -> SegmentResult | None:
        """Run one step to success. Returns None, or how the segment ended."""
        index, count, progress_index, progress_total = position
        attempt = 0
        while True:
            # Before every attempt: a retry must not end in another PV write
            # after Abort or while paused.
            if not self._hold(step, wait_for_next=attempt == 0):
                return self._abort_before(step)
            if attempt == 0:
                self._notify("on_step_started", step, index, count)
                self._notify(
                    "on_progress",
                    step,
                    int(progress_index / progress_total * 100),
                )
            attempt += 1

            result, raised = self._execute(step)
            results[step] = result
            self._notify("on_attempt", step, attempt, result)
            if raised:
                return self._step_failed(step, result)

            if result.result in (PhaseResult.SUCCESS, PhaseResult.SKIP):
                self._notify("on_step_finished", step, result)
                return None

            if result.result is not PhaseResult.RETRY:
                return self._step_failed(step, result)

            if attempt >= self.max_attempts:
                return self._step_failed(
                    step,
                    result,
                    message=(
                        f"{step} gave up after {attempt} attempts: "
                        f"{result.message}"
                    ),
                )
            delay = max(0.0, float(result.retry_delay_seconds or 0.0))
            self._notify("on_retry_wait", step, attempt, delay)
            if not self._wait(delay):
                return self._abort_before(step)

    def _execute(self, step: str) -> tuple[PhaseStepResult, bool]:
        """Run one attempt of step and save its checkpoint.

        Returns the step's result, and True if the step raised an error.
        """
        try:
            result = self.phase.execute_step(step)
            if not isinstance(result, PhaseStepResult):
                raise TypeError(
                    f"execute_step returned {type(result).__name__}, "
                    "not a PhaseStepResult"
                )
        except Exception as exc:
            logger.exception("Step %s raised", step)
            message = f"{step} raised {type(exc).__name__}: {exc}"
            self.phase._create_checkpoint(
                step_name=step,
                success=False,
                notes=message,
                error_message=str(exc),
            )
            return PhaseStepResult(PhaseResult.FAILED, message), True
        self.phase._create_checkpoint(
            step_name=step,
            success=result.result in (PhaseResult.SUCCESS, PhaseResult.SKIP),
            notes=result.message,
            measurements=result.data,
        )
        return result, False

    def _step_failed(
        self, step: str, result: PhaseStepResult, message: str | None = None
    ) -> SegmentResult:
        self._set_failed()
        self._notify("on_step_finished", step, result)
        # The phases turn an abort inside a hardware wait (CavityAbortError,
        # a stepper abort) into FAILED. Reported as ABORTED so the panel can
        # tell the operator's Abort from a fault.
        outcome = (
            SegmentOutcome.ABORTED
            if self.context.is_abort_requested()
            else SegmentOutcome.FAILED
        )
        return SegmentResult(outcome, message or result.message or "", step)

    def _abort_before(self, step: str) -> SegmentResult:
        self._set_failed()
        message = f"Aborted before {step}"
        self.phase._create_checkpoint(
            step_name=step,
            success=False,
            notes=message,
            error_message="User requested abort",
        )
        return SegmentResult(SegmentOutcome.ABORTED, message, step)

    def _set_failed(self) -> None:
        self.context.record.set_phase_status(
            self.phase.phase_type, PhaseStatus.FAILED
        )

    # --------------------------------------------------------------- waits

    def _hold(self, step: str, wait_for_next: bool) -> bool:
        """Wait while paused, or in step mode for Next. False on abort."""
        announced = None
        while True:
            with self._cond:
                if self.context.is_abort_requested():
                    return False
                if self._paused:
                    reason = HOLD_PAUSED
                elif wait_for_next and self._step_mode:
                    if self._step_permits > 0:
                        self._step_permits -= 1
                        return True
                    reason = HOLD_STEP_MODE
                else:
                    return True
                if reason == announced:
                    self._cond.wait(self._POLL_SECONDS)
                    continue
            # Tell listeners after releasing the lock. A listener may then
            # call back into this run, such as to resume it, without
            # waiting on a lock this thread holds.
            announced = reason
            self._notify("on_holding", step, reason)

    def _wait(self, delay: float) -> bool:
        """Wait delay seconds before a retry. False if abort ended it."""
        if delay <= 0:
            return not self.context.is_abort_requested()
        if self._sleep_fn is not None:
            self._sleep_fn(delay)
            return not self.context.is_abort_requested()
        deadline = time.monotonic() + delay
        with self._cond:
            while not self.context.is_abort_requested():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return True
                self._cond.wait(min(remaining, self._POLL_SECONDS))
        return False

    def _notify(self, method: str, *args) -> None:
        try:
            getattr(self.listener, method)(*args)
        except Exception:
            logger.exception("StepListener.%s failed", method)
