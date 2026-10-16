"""Controller for batch Piezo Pre-RF execution across multiple cavities."""

import functools
import logging
from dataclasses import dataclass, field
from queue import Queue
from threading import Event, Lock, Thread
from typing import Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_pre_rf import (
    PiezoPreRFPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import get_linac_for_cryomodule

logger = logging.getLogger(__name__)

# Linac name → integer index used in DB (e.g. "L1B" → 1)
_LINAC_NAME_TO_IDX = {"L0B": 0, "L1B": 1, "L2B": 2, "L3B": 3, "L4B": 4}

# verify_initial_state is skipped in the batch trigger sweep: it does 3 extra
# synchronous EPICS reads that aren't needed when firing off many cavities
# quickly, and any "test already running" condition will surface during the
# collect phase wait instead.
TRIGGER_STEPS = ("setup_piezo", "trigger_prerf_test")


class _TriggerPool:
    """Worker threads, shared by every controller in the process, that run
    trigger jobs.

    The threads are daemons that wait on a Queue for jobs and never exit.
    When a thread that used Channel Access exits, EPICS frees the data it
    kept for that thread (free_threadInfo / cantProceed). Short-lived threads
    hit pthread_attr_destroy errors there. Threads that never exit avoid
    those errors.

    One pool per process, not one per controller: each window used to start
    its own 32 threads, and each thread held its controller alive forever.
    A job is a plain callable, and a worker drops it once it has run, so the
    pool keeps no controller alive.
    """

    def __init__(self, size: int) -> None:
        self._size = size
        self._queue: Queue = Queue()
        self._lock = Lock()
        self._started = False

    def run_all(self, jobs: list[Callable[[], None]]) -> None:
        """Run every job on the pool and return once all have finished.

        Two batches running at once share the same workers.
        """
        self._start()
        done_events = [Event() for _ in jobs]
        for job, done in zip(jobs, done_events):
            self._queue.put((job, done))
        for done in done_events:
            done.wait()

    def _start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            for _ in range(self._size):
                Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        """Attach to the CA context, then run queued jobs forever."""
        try:
            import epics

            epics.ca.use_initial_context()
        except Exception:
            pass  # Not fatal; CA will self-initialize on first PV access

        while True:
            job, done = self._queue.get()
            try:
                job()
            except Exception:
                # A job reports its own errors; this only keeps the
                # worker alive if one gets through.
                logger.exception("Trigger job raised")
            finally:
                # Let go of the job now. Otherwise this worker keeps the last
                # job, and the controller it belongs to, alive until the next
                # job arrives. Do it before done.set(), so the caller never
                # sees a finished job that a worker still holds.
                del job
                done.set()
                del done


# Maximum concurrent trigger workers. 32 is more than enough for a full
# machine run and keeps CA channel churn manageable.
_TRIGGER_POOL = _TriggerPool(size=32)
COLLECT_STEPS = ("wait_for_completion", "validate_results")


@dataclass
class CavitySpec:
    """Identifies a single cavity specification for batch execution."""

    cryomodule: str
    cavity_number: int

    @property
    def key(self) -> str:
        return f"{self.cryomodule}_CAV{self.cavity_number}"

    @property
    def linac_name(self) -> str | None:
        return get_linac_for_cryomodule(self.cryomodule)

    @property
    def linac_idx(self) -> int | None:
        name = self.linac_name
        return _LINAC_NAME_TO_IDX.get(name) if name else None


@dataclass
class CavityRunState:
    """Mutable runtime state for a single cavity during a batch run."""

    spec: CavitySpec
    record: CommissioningRecord | None = None
    record_id: int | None = None
    record_version: int | None = None
    phase_instance_id: int | None = None
    context: PhaseContext | None = None
    phase: PiezoPreRFPhase | None = None
    triggered: bool = False
    error: str | None = field(default=None)

    @property
    def cavity_spec(self) -> CavitySpec:
        """Readable alias for legacy `spec` field used by existing callers."""
        return self.spec

    @cavity_spec.setter
    def cavity_spec(self, value: CavitySpec) -> None:
        self.spec = value


class BatchPiezoPreRFController(QObject):
    """Runs the Piezo Pre-RF phase for multiple cavities using trigger-then-collect.

    Execution model:
      Phase 1 – trigger sweep: for each cavity run verify → setup_piezo →
                trigger_prerf_test sequentially, then immediately move to the next.
      Phase 2 – collect sweep: for each triggered cavity run
                wait_for_completion → validate_results → persist results.

    This gives near-parallel hardware execution (all tests run concurrently in
    firmware) without spawning hundreds of OS threads.
    """

    cavity_status_changed = pyqtSignal(str, str)
    cavity_result_ready = pyqtSignal(str, object)
    batch_progress = pyqtSignal(int, int)
    batch_finished = pyqtSignal()
    log_message = pyqtSignal(str)

    STATUS_PENDING = "PENDING"
    STATUS_TRIGGERING = "TRIGGERING"
    STATUS_TRIGGERED = "TRIGGERED"
    STATUS_COLLECTING = "COLLECTING"
    STATUS_PASSED = "PASSED"
    STATUS_FAILED = "FAILED"
    STATUS_ERROR = "ERROR"
    STATUS_SKIPPED = "SKIPPED"

    def __init__(self, session: CommissioningSession) -> None:
        super().__init__()
        self.session = session
        self._machine: Machine | None = None
        self._abort_event = Event()
        self._worker_thread: Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_batch(self, cavities: list[CavitySpec], operator: str) -> None:
        """Start batch execution in a background thread.

        Args:
            cavities: Ordered list of cavities to process.
            operator: Name of the operator running the batch.
        """
        if self._worker_thread and self._worker_thread.is_alive():
            self.log_message.emit("Batch already running")
            return

        self._abort_event.clear()

        def worker():
            self._run_batch(cavities, operator)

        self._worker_thread = Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def abort(self) -> None:
        """Request graceful abort of the running batch."""
        self._abort_event.set()
        self.log_message.emit(
            "Abort requested — finishing current cavity step..."
        )

    def is_running(self) -> bool:
        return (
            self._worker_thread is not None and self._worker_thread.is_alive()
        )

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _run_batch(self, cavities: list[CavitySpec], operator: str) -> None:
        total = len(cavities)
        self.log_message.emit(
            f"Starting batch run for {total} cavit{'y' if total == 1 else 'ies'}"
        )

        states = self._prepare_states(cavities, operator)

        # Phase 1: trigger sweep — run all cavities in parallel so CA connections
        # and the per-cavity sleep(0.5) overlap instead of stacking.
        self.log_message.emit("--- Trigger sweep (parallel) ---")
        self._trigger_cavities_parallel(states)

        # Phase 2: collect sweep
        self.log_message.emit("--- Collect sweep ---")
        completed = 0
        for state in states:
            if self._abort_event.is_set():
                self._mark_remaining_skipped(states, only_triggered=True)
                break
            if state.triggered:
                self._collect_cavity(state)
            completed += 1
            self.batch_progress.emit(completed, total)

        self.log_message.emit("Batch run finished")
        self.batch_finished.emit()

    def _prepare_states(
        self, cavities: list[CavitySpec], operator: str
    ) -> list[CavityRunState]:
        states = []
        for cavity_spec in cavities:
            state = CavityRunState(spec=cavity_spec)
            try:
                self._init_record_and_context(state, operator)
            except Exception as exc:
                logger.exception(
                    "Failed to init record for %s: %s", cavity_spec.key, exc
                )
                state.error = str(exc)
                self.cavity_status_changed.emit(
                    cavity_spec.key, self.STATUS_ERROR
                )
                self.log_message.emit(f"[{cavity_spec.key}] Init failed: {exc}")
            states.append(state)
        return states

    def _init_record_and_context(
        self, state: CavityRunState, operator: str
    ) -> None:
        cavity_spec = state.cavity_spec
        linac_idx = cavity_spec.linac_idx
        if linac_idx is None:
            raise ValueError(
                f"Cannot determine linac for CM {cavity_spec.cryomodule!r}"
            )

        # Load or create the commissioning record for this cavity
        record_id = self.session.get_record_id_for_cavity(
            linac_idx,
            cavity_spec.cryomodule,
            str(cavity_spec.cavity_number),
        )
        if record_id is not None:
            loaded = self.session.get_record_with_version(record_id)
            if loaded is None:
                raise ValueError(f"Record {record_id} not found in database")
            record, version = loaded
            state.record_version = version
        else:
            record = CommissioningRecord(
                linac=linac_idx,
                cryomodule=cavity_spec.cryomodule,
                cavity_number=cavity_spec.cavity_number,
            )
            record_id = self.session.save_record(record)
            state.record_version = 1

        state.record = record
        state.record_id = record_id

        # Start a phase instance for this run
        try:
            phase_start = self.session.workflow.start_phase_for_record(
                record_id=record_id,
                phase=CommissioningPhase.PIEZO_PRE_RF,
                operator=operator,
            )
            state.phase_instance_id = (
                phase_start.phase_instance_id if phase_start else None
            )
        except Exception as exc:
            logger.warning(
                "Could not start phase instance for %s: %s",
                cavity_spec.key,
                exc,
            )
            state.phase_instance_id = None

        machine_cavity = self._get_machine_cavity(cavity_spec)
        state.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": machine_cavity},
            phase_instance_id=state.phase_instance_id,
            run_intent="commissioning",
        )
        state.phase = PiezoPreRFPhase(state.context)

        is_valid, msg = state.phase.validate_prerequisites()
        if not is_valid:
            raise ValueError(f"Prerequisites not met: {msg}")

        self.cavity_status_changed.emit(cavity_spec.key, self.STATUS_PENDING)

    def _trigger_one(self, state: CavityRunState) -> None:
        """Trigger one cavity on a pool thread; report any exception as an error."""
        try:
            self._trigger_cavity(state)
        except Exception as exc:
            state.error = str(exc)
            self.cavity_status_changed.emit(
                state.cavity_spec.key, self.STATUS_ERROR
            )
            self.log_message.emit(
                f"[{state.cavity_spec.key}] Trigger exception: {exc}"
            )

    def _trigger_cavities_parallel(self, states: list[CavityRunState]) -> None:
        """Dispatch trigger work to the shared pool and wait for completion.

        Each cavity touches independent PVs on its own IOC, so there are no
        shared-resource conflicts. All CA connections and the per-cavity
        sleep(0.5) in trigger_prerf_test overlap instead of stacking.
        """
        if not states:
            return

        if self._abort_event.is_set():
            self._mark_remaining_skipped(states, only_triggered=True)
            return

        _TRIGGER_POOL.run_all(
            [functools.partial(self._trigger_one, state) for state in states]
        )

    def _run_step(self, state: CavityRunState, step: str) -> bool:
        """Run one step via _execute_step_with_retry so checkpoints are created.

        _retry_count must be reset before each call so retries are scoped to
        the current step.
        """
        state.phase._retry_count = 0
        return state.phase._execute_step_with_retry(step)

    def _trigger_cavity(self, state: CavityRunState) -> None:
        if state.error or state.phase is None:
            return

        cavity_spec = state.cavity_spec
        self.cavity_status_changed.emit(cavity_spec.key, self.STATUS_TRIGGERING)
        self.log_message.emit(f"[{cavity_spec.key}] Triggering...")

        for step in TRIGGER_STEPS:
            if self._abort_event.is_set():
                state.error = "Aborted"
                self.cavity_status_changed.emit(
                    cavity_spec.key, self.STATUS_ERROR
                )
                return

            if state.context:
                state.context.abort_requested = self._abort_event.is_set()

            if not self._run_step(state, step):
                state.error = f"{step} failed"
                self.cavity_status_changed.emit(
                    cavity_spec.key, self.STATUS_ERROR
                )
                self.log_message.emit(f"[{cavity_spec.key}] {step} failed")
                self._fail_phase_instance(state, state.error)
                return

        state.triggered = True
        self.cavity_status_changed.emit(cavity_spec.key, self.STATUS_TRIGGERED)
        self.log_message.emit(f"[{cavity_spec.key}] Test triggered")

    def _collect_cavity(self, state: CavityRunState) -> None:
        cavity_spec = state.cavity_spec
        self.cavity_status_changed.emit(cavity_spec.key, self.STATUS_COLLECTING)
        self.log_message.emit(f"[{cavity_spec.key}] Collecting results...")

        if state.context:
            state.context.abort_requested = self._abort_event.is_set()

        for step in COLLECT_STEPS:
            if self._abort_event.is_set():
                state.error = "Aborted"
                self.cavity_status_changed.emit(
                    cavity_spec.key, self.STATUS_ERROR
                )
                self._fail_phase_instance(state, "Aborted")
                return

            if not self._run_step(state, step):
                state.error = f"{step} failed"
                self.cavity_status_changed.emit(
                    cavity_spec.key, self.STATUS_FAILED
                )
                self.log_message.emit(f"[{cavity_spec.key}] {step} failed")
                self._fail_phase_instance(state, state.error)
                self._persist_record(state)
                return

        # Checkpoints are now in phase_history — finalize_phase can find them.
        try:
            state.phase.finalize_phase()
        except Exception as exc:
            logger.exception(
                "finalize_phase failed for %s: %s", cavity_spec.key, exc
            )

        result_data: PiezoPreRFCheck | None = (
            state.record.piezo_pre_rf if state.record else None
        )

        if result_data and result_data.passed:
            self.cavity_status_changed.emit(cavity_spec.key, self.STATUS_PASSED)
            self.log_message.emit(
                f"[{cavity_spec.key}] PASSED (Cap A={result_data.capacitance_a * 1e9:.1f} nF, "
                f"Cap B={result_data.capacitance_b * 1e9:.1f} nF)"
            )
            self._complete_phase_instance(state, result_data)
        else:
            self.cavity_status_changed.emit(cavity_spec.key, self.STATUS_FAILED)
            notes = result_data.notes if result_data else "No data"
            self.log_message.emit(f"[{cavity_spec.key}] FAILED: {notes}")
            self._fail_phase_instance(state, notes)

        self._persist_record(state)
        self.cavity_result_ready.emit(cavity_spec.key, result_data)

    def _complete_phase_instance(
        self, state: CavityRunState, result_data: Optional[PiezoPreRFCheck]
    ) -> None:
        if state.phase_instance_id is None or state.record_id is None:
            return
        try:
            payload = result_data.to_dict() if result_data else None
            self.session.workflow.complete_phase_instance(
                record_id=state.record_id,
                phase_instance_id=state.phase_instance_id,
                phase=CommissioningPhase.PIEZO_PRE_RF,
                artifact_payload=payload,
            )
        except Exception as exc:
            logger.warning(
                "complete_phase_instance failed for %s: %s",
                state.cavity_spec.key,
                exc,
            )

    def _fail_phase_instance(
        self, state: CavityRunState, error_msg: str
    ) -> None:
        if state.phase_instance_id is None or state.record_id is None:
            return
        try:
            payload = None
            if state.record and state.record.piezo_pre_rf:
                payload = state.record.piezo_pre_rf.to_dict()
            self.session.workflow.fail_phase_instance(
                record_id=state.record_id,
                phase_instance_id=state.phase_instance_id,
                phase=CommissioningPhase.PIEZO_PRE_RF,
                error_message=error_msg,
                artifact_payload=payload,
            )
        except Exception as exc:
            logger.warning(
                "fail_phase_instance failed for %s: %s",
                state.cavity_spec.key,
                exc,
            )

    def _persist_record(self, state: CavityRunState) -> None:
        if state.record is None or state.record_id is None:
            return
        try:
            self.session.save_record(
                state.record,
                state.record_id,
                expected_version=state.record_version,
            )
            if state.record_version is not None:
                state.record_version += 1
        except Exception as exc:
            logger.warning(
                "save_record failed for %s: %s",
                state.cavity_spec.key,
                exc,
            )

    def _mark_remaining_skipped(
        self, states: list[CavityRunState], only_triggered: bool = False
    ) -> None:
        for state in states:
            if state.error or state.triggered == only_triggered:
                continue
            self.cavity_status_changed.emit(
                state.cavity_spec.key, self.STATUS_SKIPPED
            )

    # ------------------------------------------------------------------
    # Machine / cavity resolution
    # ------------------------------------------------------------------

    def _get_machine(self) -> Machine:
        if self._machine is None:
            self._machine = Machine(piezo_class=CommissioningPiezo)
        return self._machine

    def _get_machine_cavity(self, cavity_spec: CavitySpec):
        machine = self._get_machine()
        cm_key = (
            f"{int(cavity_spec.cryomodule):02d}"
            if cavity_spec.cryomodule.isdigit()
            else cavity_spec.cryomodule
        )
        return machine.cryomodules[cm_key].cavities[cavity_spec.cavity_number]
