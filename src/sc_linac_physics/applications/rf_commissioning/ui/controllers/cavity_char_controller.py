"""Controller for the Cavity Characterization display.

Drives CavityCharPhase and owns every write this phase makes to the machine:
SEL_ASET (drive level) and PROBECALSTRT (start) here, and in a later change
PUSH_QLOADED.PROC / PUSH_CAV_SCALE.PROC once the operator has reviewed the
measurement.
"""

import threading
import time
from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PhaseCheckpoint,
)
from sc_linac_physics.applications.rf_commissioning.phases.cavity_char import (
    CavityCharLimits,
    CavityCharPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (  # noqa: E501
    resolve_cavity_selection,
)
from sc_linac_physics.utils.sc_linac.linac import Machine

# The steps Start Test runs.
#
# Deliberately not CavityCharPhase.get_phase_steps(). That list continues
# "push_results", "record_results", and push_results puts PUSH_QLOADED.PROC
# and PUSH_CAV_SCALE.PROC — so running it whole commits the measurement to
# the cavity the instant it is read, with nothing for the operator to review.
#
# The backend splits reading from pushing on purpose (see
# CavityCharPhase._read_results) but does not enforce the gap; its
# _push_results docstring says the step is "reached only once the operator
# has confirmed". Enforcing that is this controller's job. The push runs from
# its own button, and the phase is finalized after it, not here.
MEASURE_STEPS = (
    "verify_initial_state",
    "set_drive_level",
    "start_characterization",
    "wait_for_completion",
    "read_results",
)

# How many times a step may come back RETRY before the run gives up.
#
# _verify_initial_state turns any exception reading the cavity into a RETRY,
# and _read_results does the same while the values settle. Retrying without a
# cap spins every few seconds forever: no failure, no progress, and nothing
# written to the machine — which looks from the outside like the button did
# nothing. ssa_char_controller uses the same limit.
MAX_STEP_ATTEMPTS = 3


class CavityCharController(QObject):
    """Owns CavityCharPhase execution for the Cavity Characterization display."""

    # Emitted once the phase has advanced, which happens after the push, not
    # after the measurement.
    phase_completed = pyqtSignal(object)
    phase_run_finished = pyqtSignal(bool, str)
    # The measurement is read and on the record, awaiting operator review.
    measurement_finished = pyqtSignal()
    # Seconds since the characterization started. Emitted from the poll
    # thread so the elapsed label updates on the GUI thread.
    elapsed_updated = pyqtSignal(float)
    # Everything the worker thread wants to show goes through these. The
    # steps run on a daemon thread, and calling view.log_message() or
    # view.set_char_status() from there would mutate Qt widgets off the GUI
    # thread. Emitting lets Qt marshal the call. Same arrangement as
    # ssa_char_controller._log_signal.
    _log_signal = pyqtSignal(str)
    _status_signal = pyqtSignal(str)

    def __init__(self, view, session: CommissioningSession) -> None:
        super().__init__()
        self.view = view
        self.session = session
        self.limits = CavityCharLimits()

        self.context: PhaseContext | None = None
        self.phase: CavityCharPhase | None = None
        self.machine: Machine | None = None
        self._cavity = None
        self._paused = False
        self._running = False
        self._active_phase_instance_id: int | None = None
        self._steps: list[str] = list(MEASURE_STEPS)

        self.phase_run_finished.connect(self._on_phase_run_finished)
        # Queued: measurement_finished is emitted from the worker thread and
        # this slot lives on the controller, whose affinity is the GUI thread.
        self.measurement_finished.connect(self._on_measurement_finished)
        if hasattr(self.view, "log_message"):
            self._log_signal.connect(self.view.log_message)
        if hasattr(self.view, "set_char_status"):
            self._status_signal.connect(self.view.set_char_status)

    # ------------------------------------------------------------------
    # Operator input
    # ------------------------------------------------------------------

    def _get_drive_level(self) -> float | None:
        """Read the spinbox and apply CavityCharLimits' bounds.

        CavityCharPhase._set_drive_level re-validates before writing SEL_ASET.
        Checking here as well means the operator is told before a phase
        instance is opened against the record.
        """
        drive = float(self.view.drive_level_spinbox.value())
        if not 0 < drive <= self.limits.max_drive_level:
            self.view.show_error(
                f"Drive level must be in (0, "
                f"{self.limits.max_drive_level:.0f}]"
            )
            return None
        return drive

    # ------------------------------------------------------------------
    # PV wiring
    # ------------------------------------------------------------------

    def setup_pv_connections(self) -> None:
        if self.session is not None and self.session.has_active_record():
            self.update_pv_addresses()

    def update_pv_addresses(
        self,
        cryomodule: str | None = None,
        cavity_number: str | None = None,
    ) -> None:
        """Cache the selected cavity and publish its loaded-Q window.

        The window differs between harmonic-linearizer, LCLS-II-HE and
        standard cavities, so the panel reads it off the cavity rather than
        hard-coding a pair.
        """
        cryomodule, cavity_number = resolve_cavity_selection(
            self.view, cryomodule, cavity_number
        )
        if cryomodule is None or cavity_number is None:
            return
        try:
            cavity = self._get_machine_cavity(
                int(cryomodule), int(cavity_number)
            )
            self._cavity = cavity
            self.view.cavity_loaded_q_window = (
                cavity.loaded_q_lower_limit,
                cavity.loaded_q_upper_limit,
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _get_machine_cavity(self, cm: int, cav: int):
        if not self.machine:
            self.machine = Machine()
        return self.machine.cryomodules[f"{cm:02d}"].cavities[cav]

    # ------------------------------------------------------------------
    # Abort and pause
    # ------------------------------------------------------------------

    def on_abort(self) -> None:
        """Abort the run, both between steps and during the wait.

        context.request_abort() stops the step loop at the next step
        boundary. cavity.request_abort() sets abort_flag, which check_abort()
        reads each poll inside Cavity.wait_for_characterization(); there it
        calls turn_off(), which writes RFCTRL = 0, and raises
        CavityAbortError. CavityCharPhase._wait_for_completion asks its
        controller for both.

        Outside the wait no PV is written: the run stops before its next step.
        """
        if self.context is not None:
            self.context.request_abort()
        if self._cavity is not None:
            self._cavity.request_abort()
        self.view.log_message(
            "Abort requested. If the run is waiting for the result, RF is "
            "turned off (RFCTRL = 0); otherwise the run stops before its "
            "next step."
        )

    def on_pause_test(self) -> None:
        self._paused = not self._paused

    def _set_running_ui_state(self, running: bool) -> None:
        """Lock the toolbar for the duration of a run.

        Without this, Start Test stays clickable and every click starts
        another daemon thread driving the same cavity, interleaving SEL_ASET
        and PROBECALSTRT writes.
        """
        self.view.run_button.setEnabled(not running)
        self.view.pause_button.setEnabled(running)
        self.view.abort_button.setEnabled(running)

    def _on_measurement_finished(self) -> None:
        """Persist the measurement. The phase instance stays open.

        The checkpoints and measured values are on the in-memory record
        until save_active_record() writes them, so without this a completed
        run leaves nothing in the commissioning database.

        complete_active_phase_instance() is deliberately not called: the
        phase is not complete until the values are pushed, which happens
        from the push button.
        """
        self._running = False
        self._paused = False
        self._set_running_ui_state(False)
        try:
            if self.session.save_active_record():
                self._log_signal.emit(
                    "Measurement saved to the record "
                    f"(ID: {self.session.get_active_record_id()})"
                )
            else:
                self._log_signal.emit(
                    "Warning: failed to save the measurement to the database"
                )
        except Exception as exc:
            self._log_signal.emit(f"Warning: failed to save: {exc}")
        self._refresh_stored_data()

    def _refresh_stored_data(self) -> None:
        """Show this run's values in Stored Data.

        The panel is filled when a record loads. A run changes
        record.cavity_char (CavityCharPhase._store_phase_fields, or
        _clear_measured_fields on a new start), and without this the panel
        keeps showing the values it loaded.
        """
        record = self.session.get_active_record()
        if record is not None:
            self.view.refresh_from_record(record)

    def _on_phase_run_finished(self, success: bool, error_msg: str) -> None:
        if success and self.context is not None:
            self.phase_completed.emit(self.context.record)
            return

        if success:
            return

        self._running = False
        self._paused = False
        self._set_running_ui_state(False)
        try:
            # Partial results are worth keeping: the operator needs to see
            # how far the run got.
            self.session.save_active_record()
            if self._active_phase_instance_id is not None:
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.CAVITY_CHAR,
                    error_message=error_msg,
                )
        except Exception as exc:
            self._log_signal.emit(
                f"Warning: failed to save partial results: {exc}"
            )
        finally:
            self._active_phase_instance_id = None
        self._refresh_stored_data()
        self.view.show_error(error_msg)

    # ------------------------------------------------------------------
    # Phase execution
    # ------------------------------------------------------------------

    def on_run_characterization(self) -> None:
        """Validate, open a phase instance, then run on a thread."""
        if self._running:
            return

        drive_level = self._get_drive_level()
        if drive_level is None:
            return

        operator = self.view.get_current_operator()
        if not operator:
            self.view.show_error("Select an operator before running")
            return

        if self._cavity is None:
            self.view.show_error("No cavity selected")
            return

        # A flag left from an Abort pressed after the last wait would make
        # this run's wait call turn_off() straight away.
        self._cavity.abort_flag = False

        if not self._prepare_phase_context(self._cavity, operator, drive_level):
            return

        self._running = True
        self._set_running_ui_state(True)
        self._execute_phase_async()

    def _prepare_phase_context(
        self, cavity, operator: str, drive_level: float
    ) -> bool:
        record = self.session.get_active_record()
        record_id = self.session.get_active_record_id()

        can_run, reason = self.session.can_run_phase(
            CommissioningPhase.CAVITY_CHAR
        )
        if not can_run:
            self.view.show_error(f"Cannot run CAVITY_CHAR phase: {reason}")
            return False

        if record_id is not None:
            phase_start = self.session.start_active_phase_instance(
                CommissioningPhase.CAVITY_CHAR, operator=operator
            )
            self._active_phase_instance_id = (
                phase_start.phase_instance_id if phase_start else None
            )

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": cavity, "drive_level": drive_level},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        self.phase = CavityCharPhase(self.context, self.limits)

        is_valid, message = self.phase.validate_prerequisites()
        if not is_valid:
            self.view.show_error(f"Prerequisites not met: {message}")
            return False
        return True

    def _execute_phase_async(self) -> None:
        if not self.context or not self.phase:
            return
        self._steps = list(MEASURE_STEPS)
        # Drives the container's current-step label and progress bar through
        # PhaseDisplayBase.step_progress_signal.
        self.context.progress_callback = (
            lambda step, prog: self.view.step_progress_signal.emit(step, prog)
        )
        QTimer.singleShot(100, self._run_phase_in_background)

    def _run_phase_in_background(self) -> None:
        def worker() -> None:
            try:
                self.phase._mark_phase_started()
                for step_name in MEASURE_STEPS:
                    if not self._check_pause_and_abort():
                        self.phase_run_finished.emit(False, "Aborted")
                        return
                    if not self._execute_single_step(step_name):
                        self.phase_run_finished.emit(
                            False, f"Step failed: {step_name}"
                        )
                        return
                self._finish_measurement()
            except Exception as exc:
                self.phase_run_finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _check_pause_and_abort(self) -> bool:
        """Block while paused; report whether the run should continue.

        on_abort() sets the cavity's abort_flag, which only check_abort()
        inside _wait_for_completion reads. Between steps the loop has to ask
        the context, or Abort does nothing until the next long wait.
        """
        while self._paused:
            time.sleep(0.1)
            if self.context and self.context.is_abort_requested():
                return False
        return not (self.context and self.context.is_abort_requested())

    def _report(self, log_line: str, status: str) -> None:
        """Send text to the panel from whichever thread is running.

        Both are signals so the widget mutation happens on the GUI thread.
        """
        self._log_signal.emit(log_line)
        self._status_signal.emit(status)

    def _execute_single_step(self, step_name: str) -> bool:
        """Run one step, retrying for as long as the backend asks.

        RETRY is not a failure on its own: _read_results returns it while the
        measured values are still settling. It becomes one after
        MAX_STEP_ATTEMPTS, so a cavity that cannot be read fails the run
        instead of retrying out of sight.
        """
        for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
            result = self.phase.execute_step(step_name)
            self._create_step_checkpoint(step_name, result)

            if result.result is PhaseResult.RETRY:
                self._report(
                    f"{step_name}: {result.message} "
                    f"(attempt {attempt}/{MAX_STEP_ATTEMPTS})",
                    result.message,
                )
                if attempt == MAX_STEP_ATTEMPTS:
                    give_up = (
                        f"{step_name} gave up after {MAX_STEP_ATTEMPTS} "
                        f"attempts: {result.message}"
                    )
                    self._report(give_up, give_up)
                    return False
                time.sleep(result.retry_delay_seconds or 1.0)
                continue

            if result.result is PhaseResult.SUCCESS:
                self._report(f"{step_name}: {result.message}", result.message)
                return True

            # A crash and a timeout both arrive as FAILED with different
            # messages. Passing the message straight through keeps them
            # distinguishable in the panel.
            self._report(
                f"{step_name} failed: {result.message}", result.message
            )
            return False

        # Unreachable: the RETRY branch returns on the final attempt. Explicit
        # so the function never falls out with an implicit None.
        return False

    def _create_step_checkpoint(self, step_name: str, result) -> None:
        """Append the step to record.phase_history.

        This is what makes a run visible afterwards; without it the phase
        leaves no trace on the commissioning record.
        """
        if self.context is None or self.context.record is None:
            return
        measurements = dict(result.data or {})
        if self.context.phase_instance_id is not None:
            measurements.setdefault(
                "phase_instance_id", self.context.phase_instance_id
            )
        self.context.record.phase_history.append(
            PhaseCheckpoint(
                phase=self.phase.phase_type,
                timestamp=datetime.now(),
                operator=self.context.operator,
                step_name=step_name,
                success=result.result
                in (PhaseResult.SUCCESS, PhaseResult.SKIP),
                notes=result.message,
                measurements=measurements,
            )
        )

    def _finish_measurement(self) -> None:
        """The measurement is read and on the record. The phase is not done.

        finalize_phase() and the workflow advance both wait for the push, so
        neither happens here — a characterization whose values never reached
        the cavity has not completed.
        """
        self._status_signal.emit(
            "Measurement complete — review the values before pushing"
        )
        self.measurement_finished.emit()

    def _emit_elapsed_until_done(self, started_at: float) -> None:
        """Emit elapsed seconds while the characterization runs.

        PROBECALSTS reports running or crashed and nothing in between, so
        elapsed time against the timeout is the only progress the panel can
        honestly show.
        """
        while (
            self._cavity is not None and self._cavity.characterization_running
        ):
            self.elapsed_updated.emit(time.monotonic() - started_at)
            time.sleep(self.limits.status_poll_interval)
