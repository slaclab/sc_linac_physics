"""Controller for batch Piezo Pre-RF execution across multiple cavities."""

import logging
from dataclasses import dataclass, field
from queue import Queue
from threading import Event, Thread
from typing import Optional

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
COLLECT_STEPS = ("wait_for_completion", "validate_results")


@dataclass
class CavitySpec:
    """Identifies a single cavity for batch execution."""

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

    # Maximum concurrent trigger workers.  32 is more than enough for a full
    # machine run and keeps CA channel churn manageable.
    _POOL_SIZE = 32

    def __init__(self, session: CommissioningSession) -> None:
        super().__init__()
        self.session = session
        self._machine: Machine | None = None
        self._abort_event = Event()
        self._worker_thread: Thread | None = None

        # Persistent trigger pool — threads are created once and never exit so
        # EPICS's TLS cleanup (`free_threadInfo`) is never triggered.
        self._trigger_queue: Queue = Queue()
        self._pool_ready = False

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
        for spec in cavities:
            state = CavityRunState(spec=spec)
            try:
                self._init_record_and_context(state, operator)
            except Exception as exc:
                logger.exception(
                    "Failed to init record for %s: %s", spec.key, exc
                )
                state.error = str(exc)
                self.cavity_status_changed.emit(spec.key, self.STATUS_ERROR)
                self.log_message.emit(f"[{spec.key}] Init failed: {exc}")
            states.append(state)
        return states

    def _init_record_and_context(
        self, state: CavityRunState, operator: str
    ) -> None:
        spec = state.spec
        linac_idx = spec.linac_idx
        if linac_idx is None:
            raise ValueError(
                f"Cannot determine linac for CM {spec.cryomodule!r}"
            )

        # Load or create the commissioning record for this cavity
        record_id = self.session.db.get_record_id_for_cavity(
            linac_idx, spec.cryomodule, str(spec.cavity_number)
        )
        if record_id is not None:
            loaded = self.session.db.get_record_with_version(record_id)
            if loaded is None:
                raise ValueError(f"Record {record_id} not found in database")
            record, version = loaded
            state.record_version = version
        else:
            record = CommissioningRecord(
                linac=linac_idx,
                cryomodule=spec.cryomodule,
                cavity_number=spec.cavity_number,
            )
            record_id = self.session.db.save_record(record)
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
                "Could not start phase instance for %s: %s", spec.key, exc
            )
            state.phase_instance_id = None

        machine_cavity = self._get_machine_cavity(spec)
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

        self.cavity_status_changed.emit(spec.key, self.STATUS_PENDING)

    def _ensure_pool(self) -> None:
        """Lazily start the persistent trigger worker pool.

        Workers are daemon threads that loop on a Queue and never exit.
        Because they never exit, EPICS never runs its TLS cleanup
        (free_threadInfo / cantProceed) and the pthread_attr_destroy errors
        that occur when short-lived threads leave the CA layer are avoided.
        """
        if self._pool_ready:
            return
        self._pool_ready = True
        for _ in range(self._POOL_SIZE):
            t = Thread(target=self._pool_worker, daemon=True)
            t.start()

    def _pool_worker(self) -> None:
        """Persistent worker loop — attach to the CA context, then run forever."""
        try:
            import epics

            epics.ca.use_initial_context()
        except Exception:
            pass  # Not fatal; CA will self-initialize on first PV access

        while True:
            state, done_event = self._trigger_queue.get()
            try:
                self._trigger_cavity(state)
            except Exception as exc:
                state.error = str(exc)
                self.cavity_status_changed.emit(
                    state.spec.key, self.STATUS_ERROR
                )
                self.log_message.emit(
                    f"[{state.spec.key}] Trigger exception: {exc}"
                )
            finally:
                self._trigger_queue.task_done()
                done_event.set()

    def _trigger_cavities_parallel(self, states: list[CavityRunState]) -> None:
        """Dispatch trigger work to the persistent pool and wait for completion.

        Each cavity touches independent PVs on its own IOC, so there are no
        shared-resource conflicts. All CA connections and the per-cavity
        sleep(0.5) in trigger_prerf_test overlap instead of stacking.
        """
        if not states:
            return

        if self._abort_event.is_set():
            self._mark_remaining_skipped(states)
            return

        self._ensure_pool()

        done_events = [Event() for _ in states]
        for state, done in zip(states, done_events):
            self._trigger_queue.put((state, done))

        for done in done_events:
            done.wait()

    def _run_step(self, state: CavityRunState, step: str) -> bool:
        """Run one step via _execute_step_with_retry so checkpoints are created.

        _retry_count must be reset before each call, matching the reset that
        PhaseBase.run() does at the top of its step loop.
        """
        state.phase._retry_count = 0
        return state.phase._execute_step_with_retry(step)

    def _trigger_cavity(self, state: CavityRunState) -> None:
        if state.error or state.phase is None:
            return

        spec = state.spec
        self.cavity_status_changed.emit(spec.key, self.STATUS_TRIGGERING)
        self.log_message.emit(f"[{spec.key}] Triggering...")

        for step in TRIGGER_STEPS:
            if self._abort_event.is_set():
                state.error = "Aborted"
                self.cavity_status_changed.emit(spec.key, self.STATUS_ERROR)
                return

            if state.context:
                state.context.abort_requested = self._abort_event.is_set()

            if not self._run_step(state, step):
                state.error = f"{step} failed"
                self.cavity_status_changed.emit(spec.key, self.STATUS_ERROR)
                self.log_message.emit(f"[{spec.key}] {step} failed")
                self._fail_phase_instance(state, state.error)
                return

        state.triggered = True
        self.cavity_status_changed.emit(spec.key, self.STATUS_TRIGGERED)
        self.log_message.emit(f"[{spec.key}] Test triggered")

    def _collect_cavity(self, state: CavityRunState) -> None:
        spec = state.spec
        self.cavity_status_changed.emit(spec.key, self.STATUS_COLLECTING)
        self.log_message.emit(f"[{spec.key}] Collecting results...")

        if state.context:
            state.context.abort_requested = self._abort_event.is_set()

        for step in COLLECT_STEPS:
            if self._abort_event.is_set():
                state.error = "Aborted"
                self.cavity_status_changed.emit(spec.key, self.STATUS_ERROR)
                self._fail_phase_instance(state, "Aborted")
                return

            if not self._run_step(state, step):
                state.error = f"{step} failed"
                self.cavity_status_changed.emit(spec.key, self.STATUS_FAILED)
                self.log_message.emit(f"[{spec.key}] {step} failed")
                self._fail_phase_instance(state, state.error)
                self._persist_record(state)
                return

        # Checkpoints are now in phase_history — finalize_phase can find them.
        try:
            state.phase.finalize_phase()
        except Exception as exc:
            logger.exception("finalize_phase failed for %s: %s", spec.key, exc)

        result_data: PiezoPreRFCheck | None = (
            state.record.piezo_pre_rf if state.record else None
        )

        if result_data and result_data.passed:
            self.cavity_status_changed.emit(spec.key, self.STATUS_PASSED)
            self.log_message.emit(
                f"[{spec.key}] PASSED (Cap A={result_data.capacitance_a * 1e9:.1f} nF, "
                f"Cap B={result_data.capacitance_b * 1e9:.1f} nF)"
            )
        else:
            self.cavity_status_changed.emit(spec.key, self.STATUS_FAILED)
            notes = result_data.notes if result_data else "No data"
            self.log_message.emit(f"[{spec.key}] FAILED: {notes}")

        self._complete_phase_instance(state, result_data)
        self._persist_record(state)
        self.cavity_result_ready.emit(spec.key, result_data)

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
                "complete_phase_instance failed for %s: %s", state.spec.key, exc
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
                "fail_phase_instance failed for %s: %s", state.spec.key, exc
            )

    def _persist_record(self, state: CavityRunState) -> None:
        if state.record is None or state.record_id is None:
            return
        try:
            self.session.db.save_record(
                state.record,
                state.record_id,
                expected_version=state.record_version,
            )
            if state.record_version is not None:
                state.record_version += 1
        except Exception as exc:
            logger.warning("save_record failed for %s: %s", state.spec.key, exc)

    def _mark_remaining_skipped(
        self, states: list[CavityRunState], only_triggered: bool = False
    ) -> None:
        for state in states:
            if state.error or state.triggered == only_triggered:
                continue
            self.cavity_status_changed.emit(state.spec.key, self.STATUS_SKIPPED)

    # ------------------------------------------------------------------
    # Machine / cavity resolution
    # ------------------------------------------------------------------

    def _get_machine(self) -> Machine:
        if self._machine is None:
            self._machine = Machine(piezo_class=CommissioningPiezo)
        return self._machine

    def _get_machine_cavity(self, spec: CavitySpec):
        machine = self._get_machine()
        cm_key = (
            f"{int(spec.cryomodule):02d}"
            if spec.cryomodule.isdigit()
            else spec.cryomodule
        )
        return machine.cryomodules[cm_key].cavities[spec.cavity_number]
