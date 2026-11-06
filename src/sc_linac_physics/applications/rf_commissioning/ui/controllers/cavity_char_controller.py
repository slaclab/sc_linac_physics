"""Controller for the Cavity Characterization display.

Drives CavityCharPhase and owns every write this phase makes to the machine.
Start Test writes INTLK_RESET_ALL and SEL_ASET (drive level), then
PROBECALSTRT. Push, after the operator confirms the values on screen,
processes PUSH_QLOADED.PROC, PUSH_CAV_SCALE.PROC and PUSH_QPROBECALC.PROC.
"""

import threading
import time
from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PhaseCheckpoint,
)
from sc_linac_physics.applications.rf_commissioning.phases import (
    cavity_setup,
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
    apply_pv_mapping,
    cryomodule_key,
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
    # SSA calibration (PUSH_SSA_SLOPE.PROC with no review) and the stepper
    # moves to resonance run here, before the measurement. See cavity_setup.
    "calibrate_ssa",
    "tune_to_resonance",
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

# Live PV readouts on the panel: widget name -> the Cavity attribute holding
# the PV address. Read-only; nothing here writes.
LIVE_PV_WIDGETS = (
    ("pydm_char_status", "characterization_status_pv"),  # PROBECALSTS
    ("pydm_char_timestamp", "char_timestamp_pv"),  # PROBECALTS
    ("pydm_loaded_q_new", "measured_loaded_q_pv"),  # QLOADED_NEW
    ("pydm_loaded_q_current", "current_q_loaded_pv"),  # QLOADED
    ("pydm_scale_new", "measured_scale_factor_pv"),  # CAV:CAL_SCALEB_NEW
    ("pydm_scale_current", "current_cavity_scale_pv"),  # CAV:SCALER_SEL.B
    ("pydm_probe_q_new", "measured_probe_q_pv"),  # QPROBE_CALC2
    ("pydm_drive_level", "drive_level_pv"),  # SEL_ASET
    ("pydm_rf_state", "rf_state_pv"),  # RFSTATE
)

# Run from the Push button, on the same CavityCharPhase that ran
# MEASURE_STEPS: _push_results compares against the values that phase read.
PUSH_STEPS = ("push_results", "record_results")


class CavityCharController(QObject):
    """Owns CavityCharPhase execution for the Cavity Characterization display."""

    # Emitted once the phase has advanced, which happens after the push, not
    # after the measurement.
    phase_completed = pyqtSignal(object)
    phase_run_finished = pyqtSignal(bool, str)
    # The measurement is read and on the record, awaiting operator review.
    measurement_finished = pyqtSignal()
    # The measured values for the review panel, as read_results stored them
    # (CavityCharPhase._result_data).
    results_ready = pyqtSignal(dict)
    # Sent when a push ends: whether it succeeded, and the step's message if
    # it failed.
    push_finished = pyqtSignal(bool, str)
    # Seconds since PROBECALSTRT was started, ticked by _elapsed_timer on
    # the GUI thread from start_characterization until the wait settles.
    elapsed_updated = pyqtSignal(float)
    # Emitted by the worker to start and stop _elapsed_timer, which has to
    # run on the GUI thread.
    _char_started = pyqtSignal()
    _char_settled = pyqtSignal()
    # Everything the worker thread wants to show goes through these. The
    # steps run on a daemon thread, and calling view.log_message() or
    # view.set_char_status() from there would mutate Qt widgets off the GUI
    # thread. Emitting a signal instead makes Qt run the call on the GUI
    # thread. ssa_char_controller does the same with its _log_signal.
    _log_signal = pyqtSignal(str)
    _status_signal = pyqtSignal(str)
    # The last SSA calibration (a LastSetupResult, or None if the read
    # failed) and the read error, emitted from the thread that reads CALTS
    # and CALSTAT so Start Test never blocks the GUI on them.
    _last_ssa_cal_read = pyqtSignal(object, str)

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
        self._last_step_message = ""
        # After a push reaches the cavity, the record still has to be marked
        # complete, saved, and given a history entry. Any of those that
        # failed is listed here ("complete", "save", "history"). Retry Save
        # runs only these, so it never writes PUSH_*.PROC a second time.
        self._unsaved_push: set[str] = set()
        self._elapsed_started_at = 0.0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        # Set by _decide_ssa_calibration before each run, read by
        # _prepare_phase_context: (kept LastSetupResult or None, the name of
        # the operator who chose Skip or None).
        self._ssa_cal_decision: tuple = (None, None)
        self._pending_start: tuple | None = None
        self._last_ssa_cal_read.connect(self._on_last_ssa_cal_read)
        self._char_started.connect(self._on_char_started)
        self._char_settled.connect(self._on_char_settled)

        self.phase_run_finished.connect(self._on_phase_run_finished)
        # measurement_finished is emitted from the worker thread. The
        # controller belongs to the GUI thread, so Qt runs this handler there.
        self.measurement_finished.connect(self._on_measurement_finished)
        self.push_finished.connect(self._on_push_finished)
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
            cavity = self._get_machine_cavity(cryomodule, int(cavity_number))
            if cavity is not self._cavity and self._cavity is not None:
                if self._running:
                    # on_abort() goes to self._cavity, so it stays the
                    # cavity being characterized until the run ends.
                    self.view.log_message(
                        f"Cavity selection changed during a run; this panel "
                        f"stays on {self._cavity} until the run ends"
                    )
                    return
                # The header switch reaches here via start_new_record, which
                # does not call on_record_loaded.
                self.drop_reviewed_measurement()
                self.view.on_cavity_changed()
            self._cavity = cavity
            apply_pv_mapping(
                {
                    getattr(self.view, widget): getattr(cavity, attr)
                    for widget, attr in LIVE_PV_WIDGETS
                    if hasattr(self.view, widget)
                }
            )
            self.view.cavity_loaded_q_window = (
                cavity.loaded_q_lower_limit,
                cavity.loaded_q_upper_limit,
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")
            if not self._running:
                # Leaving the last good cavity cached would let Start Test
                # drive it while the header names another.
                self._cavity = None

    def _get_machine_cavity(self, cm: str, cav: int):
        """Machine.cryomodules is keyed "01".."35", "H1", "H2"."""
        if not self.machine:
            self.machine = Machine()
        return self.machine.cryomodules[cryomodule_key(cm)].cavities[cav]

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
        if running:
            # Re-enabled by the display when read_results succeeds.
            self.view.push_results_button.setEnabled(False)
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

        # Locked from here, so a second click cannot start a second read.
        self._running = True
        self._set_running_ui_state(True)
        cavity = self._cavity
        self._pending_start = (cavity, operator, drive_level)
        threading.Thread(
            target=lambda: self._read_last_ssa_calibration(cavity),
            daemon=True,
        ).start()

    def _read_last_ssa_calibration(self, cavity) -> None:
        """Runs on a daemon thread: CALTS and CALSTAT are EPICS reads."""
        try:
            last = cavity_setup.last_ssa_calibration(cavity)
        except Exception as exc:
            self._last_ssa_cal_read.emit(None, str(exc))
            return
        self._last_ssa_cal_read.emit(last, "")

    def _on_last_ssa_cal_read(self, last, error: str) -> None:
        """Back on the GUI thread: decide on the SSA calibration, then run."""
        cavity, operator, drive_level = self._pending_start
        self._pending_start = None
        decision = self._decide_ssa_calibration(last, error, operator)
        if decision is None:
            self._report("Start cancelled", "Cancelled")
            self._end_run()
            return
        self._ssa_cal_decision = decision
        if not self._prepare_phase_context(cavity, operator, drive_level):
            self._end_run()
            return
        self._execute_phase_async()

    def _decide_ssa_calibration(self, last, error: str, operator: str):
        """Return (kept, skipped_by), or None if the operator cancelled.

        The rule is cavity_setup.decide_ssa_calibration: keep a good one
        under an hour old, ask about an older or bad one, calibrate if CALTS
        or CALSTAT could not be read.
        """
        if last is None:
            self._report(
                f"Could not read the last SSA calibration ({error}); "
                "calibrating",
                "Calibrating SSA",
            )
        return cavity_setup.decide_ssa_calibration(
            last,
            operator,
            lambda text: self.view.ask_rerun_ssa_calibration(text),
        )

    def _end_run(self) -> None:
        self._running = False
        self._set_running_ui_state(False)

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

        # A measurement that was never pushed leaves its instance open.
        # Measuring again continues that attempt rather than opening a second
        # one that would leave the first in_progress for good.
        if record_id is not None and self._active_phase_instance_id is None:
            phase_start = self.session.start_active_phase_instance(
                CommissioningPhase.CAVITY_CHAR, operator=operator
            )
            self._active_phase_instance_id = (
                phase_start.phase_instance_id if phase_start else None
            )

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={
                "cavity": cavity,
                "drive_level": drive_level,
                "kept_ssa_calibration": self._ssa_cal_decision[0],
                "ssa_calibration_skipped_by": self._ssa_cal_decision[1],
            },
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
                            False,
                            self._last_step_message
                            or f"Step failed: {step_name}",
                        )
                        return
                    if step_name == "start_characterization":
                        self._char_started.emit()
                    elif step_name == "wait_for_completion":
                        self._char_settled.emit()
                self._finish_measurement()
            except Exception as exc:
                self.phase_run_finished.emit(False, str(exc))
            finally:
                # Stops the timer on failure, abort or timeout too. A second
                # emit after a normal settle is harmless.
                self._char_settled.emit()

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
        self._report_progress(step_name)
        for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
            # Before every attempt, not only between steps: a retry delay
            # must not end in another SEL_ASET, PROBECALSTRT or PUSH_* write.
            if not self._check_pause_and_abort():
                self._last_step_message = f"Aborted before {step_name}"
                self._report(self._last_step_message, "Aborted")
                return False
            result = self.phase.execute_step(step_name)
            self._create_step_checkpoint(step_name, result)
            self._last_step_message = result.message

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
                if step_name == "read_results":
                    self.results_ready.emit(dict(result.data or {}))
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

    def _report_progress(self, step_name: str) -> None:
        """Drive the container's current-step label and progress bar.

        PhaseBase._execute_step_with_retry would call progress_callback, but
        this controller runs steps itself, so it reports them itself: the
        step's index in CavityCharPhase.get_phase_steps() over its length.
        """
        callback = getattr(self.context, "progress_callback", None)
        if callback is None:
            return
        steps = self.phase.get_phase_steps()
        index = steps.index(step_name) if step_name in steps else 0
        callback(step_name, int(index / len(steps) * 100))

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
            "Measurement complete — review the values, then Push to Cavity"
        )
        self.measurement_finished.emit()

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    def on_push_results(self) -> None:
        """Push the values the operator just confirmed. Runs PUSH_STEPS.

        The display calls this only after its confirm dialog. Setting
        confirmed_loaded_q to the loaded Q the phase read is what opens
        CavityCharPhase._push_results' gate. That step re-reads the result
        PVs and refuses if any changed, then processes PUSH_QLOADED.PROC,
        PUSH_CAV_SCALE.PROC and PUSH_QPROBECALC.PROC, each with 1.
        """
        if self._running:
            return
        if self._unsaved_push:
            self._persist_push()
            return
        if (
            self.phase is None
            or self.context is None
            or self.phase._loaded_q is None
        ):
            self.view.show_error(
                "Nothing measured yet — run the characterization first"
            )
            return
        self.context.parameters["confirmed_loaded_q"] = self.phase._loaded_q
        # An Abort pressed after the measurement would stop this push before
        # its first attempt.
        self.context.abort_requested = False
        self._running = True
        self._set_running_ui_state(True)
        threading.Thread(target=self._push_in_background, daemon=True).start()

    def drop_reviewed_measurement(self) -> None:
        """Forget an unpushed measurement when another record loads.

        Its phase instance belongs to the previous record. It is left as it
        is rather than failed, because the session's active record (which
        fail_active_phase_instance uses) has already changed.
        A run in progress is left alone.
        """
        if self._running:
            return
        self.phase = None
        self.context = None
        self._active_phase_instance_id = None
        self._unsaved_push = set()

    def _push_in_background(self) -> None:
        try:
            for step_name in PUSH_STEPS:
                if not self._execute_single_step(step_name):
                    self.push_finished.emit(False, self._last_step_message)
                    return
            self.phase.finalize_phase()
            self.phase._mark_phase_completed()
            self.push_finished.emit(True, "")
        except Exception as exc:
            self.push_finished.emit(False, str(exc))

    def _on_push_finished(self, success: bool, message: str) -> None:
        """Record a push that reached the cavity, or report a refusal.

        A refused push wrote nothing (the gate and the re-read come before
        the PUSH_*.PROC writes), so the instance stays open for another
        measurement and push.
        """
        self._running = False
        self._set_running_ui_state(False)
        if not success:
            self.view.show_error(message)
            return
        self._unsaved_push = {"complete", "save", "history"}
        self._persist_push()

    def _persist_push(self) -> None:
        """Complete the instance, save the record and add the history entry.

        Each call's result is checked. Whatever fails stays in _unsaved_push
        for Retry Save, along with the instance id, and the phase is not
        reported complete.
        """
        record = self.context.record
        steps = {
            "complete": lambda: (
                self._active_phase_instance_id is None
                or self.session.complete_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.CAVITY_CHAR,
                    artifact_payload=record.cavity_char.to_dict(),
                )
            ),
            "save": self.session.save_active_record,
            "history": lambda: self.session.add_measurement_to_history(
                CommissioningPhase.CAVITY_CHAR,
                record.cavity_char,
                operator=self.context.operator,
                phase_instance_id=self._active_phase_instance_id,
            ),
        }
        for name in ("complete", "save", "history"):
            if name not in self._unsaved_push:
                continue
            try:
                ok = steps[name]()
            except Exception as exc:
                self._log_signal.emit(f"Warning: {name} failed: {exc}")
                ok = False
            if ok:
                self._unsaved_push.discard(name)

        self._refresh_stored_data()
        if self._unsaved_push:
            self.view.show_error(
                "The values were pushed to the cavity but not saved "
                f"({', '.join(sorted(self._unsaved_push))} failed). "
                "Retry Save writes nothing to the cavity."
            )
            self.view.offer_save_retry()
            return
        self._active_phase_instance_id = None
        self._log_signal.emit("Pushed to the cavity; phase complete")
        self.phase_completed.emit(self.session.get_active_record())

    # ------------------------------------------------------------------
    # Elapsed
    # ------------------------------------------------------------------

    def _on_char_started(self) -> None:
        self._elapsed_started_at = time.monotonic()
        self._elapsed_timer.start()

    def _on_char_settled(self) -> None:
        self._elapsed_timer.stop()

    def _tick_elapsed(self) -> None:
        """Time since PROBECALSTRT, against the wait's timeout.

        PROBECALSTS reports running or crashed and nothing in between, so
        elapsed time is the only progress the panel can show. No PV is read
        here; it runs on the GUI thread.
        """
        self.elapsed_updated.emit(time.monotonic() - self._elapsed_started_at)
