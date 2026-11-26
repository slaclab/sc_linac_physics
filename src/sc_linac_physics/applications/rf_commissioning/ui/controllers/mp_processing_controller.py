"""Controller for the MP Processing display.

Runs MPProcessingPhase through PhaseRun and RunnerBridge in two segments,
each started from the GUI thread:

  1. Start Test: verify_initial_state. Reads PVs only. Its data says
     whether the SSA calibration and the characterization are stale; the
     display asks Rerun or Skip for each (stale_result_prompt), and the
     answers go in context.parameters["rerun_ssa_calibration"] /
     ["rerun_characterization"].
  2. setup_rf, process, record_results, then complete. setup_rf turns RF on
     in SELA at the start ADES. process writes ADES up by the step until
     ADES_MAX and resets the interlocks after every quench (see
     phases/mp_processing.py). There is no review: the phase completes when
     process returns, with RF left on in SELA at ADES_MAX.

The Settings box fills MPProcessingLimits when Start Test is pressed.

Abort goes through step_runner.cavity_abort_hook. The phase's waits call
cavity.check_abort(), which turns RF off and raises. An abort between steps
(a Step Mode hold after setup_rf) reaches no check_abort, so the controller
turns RF off itself before it releases the cavity (_turn_rf_off).

Pause goes to the phase, not to PhaseRun. PhaseRun.pause() only holds
between steps, and process is one step that runs until ADES_MAX is stable.
MPProcessingPhase.request_pause() stops the walk inside process instead and
leaves RF on (see phases/mp_processing.py). The tab offers Pause only during
process.
"""

import threading

from PyQt5.QtCore import QObject, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.commissioning_machine import (  # noqa: E501
    get_commissioning_machine,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.mp_processing import (  # noqa: E501
    MPProcessingLimits,
    MPProcessingPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    HOLD_STEP_MODE,
    PhaseRun,
    SegmentOutcome,
    SegmentResult,
    cavity_abort_hook,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_hold import (  # noqa: E501
    CavityHold,
    refusal_message,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.phase_persistence import (  # noqa: E501
    FINISH_WRITES,
    persist_finished_phase,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (  # noqa: E501
    apply_pv_mapping,
    resolve_cavity_selection,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.runner_bridge import (  # noqa: E501
    RunnerBridge,
)
from sc_linac_physics.applications.rf_commissioning.ui.stale_result_prompt import (  # noqa: E501
    ask_about_stale_results,
)
from sc_linac_physics.utils.sc_linac.decarad import Decarad

PHASE = CommissioningPhase.MP_PROCESSING
ALL_STEPS = ("verify_initial_state", "setup_rf", "process", "record_results")
CHECK_STEPS = ALL_STEPS[:1]
RUN_STEPS = ALL_STEPS[1:]


def live_pv_addresses(cavity) -> dict[str, str]:
    """Widget name -> PV address for the Live PVs box. Read-only."""
    return {
        "pydm_ades": cavity.ades_pv,  # ADES
        "pydm_aact": cavity.aact_pv,  # AACTMEAN
        "pydm_ades_max": cavity.ades_max_pv,  # ADES_MAX
        "pydm_quench_latch": cavity.quench_latch_pv,  # QUENCH_LTCH
        "pydm_rf_mode": cavity.rf_mode_pv,  # RFMODE
        "pydm_rf_state": cavity.rf_state_pv,  # RFSTATE
    }


def live_decarad_addresses(number: int) -> dict[str, str]:
    """Widget name -> GAMMA_DOSE_RATE address, for decarad 1 or 2. Read-only.

    From the Decarad class, so the PV names match the FE pause's reads.
    """
    return {
        f"pydm_decarad_head_{head.number}": head.raw_dose_rate_pv
        for head in Decarad(number).heads.values()
    }


class MPProcessingController(QObject):
    """Owns MPProcessingPhase execution for the MP Processing display."""

    phase_completed = pyqtSignal(object)
    # From the RF-off worker: the abort's message, then an error or "".
    _rf_off_finished = pyqtSignal(str, str)

    def __init__(self, view, session) -> None:
        super().__init__()
        self.view = view
        self.session = session
        self.machine = None
        self._cavity = None
        # Held from Start Test until the phase completes or fails, so no
        # other tab starts on this cavity between the two segments.
        self._cavity_hold = CavityHold("the MP Processing tab")
        self.context: PhaseContext | None = None
        self.phase: MPProcessingPhase | None = None
        self.run: PhaseRun | None = None
        # "check", "run", "rf_off" (turning RF off after an abort),
        # "unsaved" (finished, a database write failed) or "unsaved_failure"
        # (failed, and recording the failure did too).
        self.stage: str | None = None
        self._step_mode = False
        self._active_phase_instance_id: int | None = None
        # Database writes still owed after a finished run (FINISH_WRITES),
        # or after a failed one ("save", "fail").
        self._unsaved: set[str] = set()
        # A failed run's message and artifact, kept while its writes are owed.
        self._failure: tuple[str, dict | None] | None = None
        # record.mp_processing before this attempt. verify_initial_state
        # replaces it, so a failure that still holds it ran no processing.
        self._prior_data = None
        self._rf_off_finished.connect(self._on_rf_off_finished)

        self.bridge = RunnerBridge(self)
        self.bridge.log.connect(self.view.log_message)
        self.bridge.progress.connect(
            lambda step, pct: self.view.step_progress_signal.emit(step, pct)
        )
        self.bridge.step_started.connect(self._on_step_started)
        self.bridge.holding.connect(self._on_holding)
        self.bridge.segment_finished.connect(self._on_segment_finished)

    @property
    def running(self) -> bool:
        """A segment is running, or RF is being turned off after an abort."""
        return self.bridge.running or self.stage == "rf_off"

    @property
    def pause_state(self) -> str:
        """MPProcessingPhase.pause_state, or "running" with no phase."""
        return "running" if self.phase is None else self.phase.pause_state

    @property
    def radiation_text(self) -> str:
        """The status box's "Decarad max" readout."""
        phase = self.phase
        if phase is None or phase.limits.decarad is None:
            return "off"
        if phase.radiation_overridden:
            return "not checked (I'm watching)"
        if phase.radiation is None:
            return "-"
        return f"{phase.radiation:.1f} over background"

    @property
    def radiation_check_on(self) -> bool:
        """A decarad is chosen and nobody has pressed I'm watching."""
        phase = self.phase
        return (
            phase is not None
            and phase.limits.decarad is not None
            and not phase.radiation_overridden
        )

    def on_override_radiation(self) -> None:
        """I'm watching: no radiation pauses for the rest of this run.

        Writes no PVs. Recorded in notes with the current operator.
        """
        if self.phase is None or self.stage != "run" or not self.running:
            return
        operator = self.view.get_current_operator() or self.context.operator
        self.phase.override_radiation(operator)
        self.view.log_message(
            f"Radiation pauses off for this run ({operator} is watching the "
            "decarad)."
        )

    @property
    def resumed_at(self):
        """When this run's last pause ended, or None."""
        return None if self.phase is None else self.phase.resumed_at

    @property
    def mp_data(self):
        """This run's record.mp_processing, or None outside a run.

        The phase appends quenches to it on the worker thread. The display
        only reads it, once a second.
        """
        if self.context is None:
            return None
        return self.context.record.mp_processing

    # ------------------------------------------------------------------
    # Cavity and PVs
    # ------------------------------------------------------------------

    def setup_pv_connections(self) -> None:
        if self.session is not None and self.session.has_active_record():
            self.update_pv_addresses()

    def update_pv_addresses(
        self, cryomodule: str | None = None, cavity_number: str | None = None
    ) -> None:
        """Cache the selected cavity and point Live PVs at it."""
        if self.running:
            self.view.log_message(
                f"Cavity selection changed during a run; this panel stays on "
                f"{self._cavity} until the run ends"
            )
            return
        cryomodule, cavity_number = resolve_cavity_selection(
            self.view, cryomodule, cavity_number
        )
        if cryomodule is None or cavity_number is None:
            return
        try:
            cavity = self._get_machine_cavity(cryomodule, int(cavity_number))
            if self._cavity is not None and cavity is not self._cavity:
                self.forget_run()
            self._cavity = cavity
            apply_pv_mapping(
                {
                    getattr(self.view, widget): address
                    for widget, address in live_pv_addresses(cavity).items()
                    if hasattr(self.view, widget)
                }
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")
            self._cavity = None

    def _get_machine_cavity(self, cm: str, cav: int):
        if not self.machine:
            self.machine = get_commissioning_machine()
        key = f"{int(cm):02d}" if str(cm).isdigit() else str(cm)
        return self.machine.cryomodules[key].cavities[cav]

    def forget_run(self) -> None:
        """Drop a finished or unsaved run, e.g. when the cavity changes."""
        if self.running:
            return
        self._cavity_hold.release()
        self.stage = None
        self._unsaved = set()
        self._failure = None
        self._prior_data = None
        self.phase = self.context = self.run = None
        self._active_phase_instance_id = None
        self.view.clear_run()

    # ------------------------------------------------------------------
    # Segment 1: Start Test
    # ------------------------------------------------------------------

    def on_start_test(self) -> None:
        if self.running:
            return
        if self.stage == "unsaved":
            # Retries the database writes only; nothing goes to the cavity.
            self._persist_finish()
            return
        if self.stage == "unsaved_failure":
            self._persist_failure()
            return
        operator = self.view.get_current_operator()
        if not operator:
            self.view.show_error("Select an operator before running")
            return
        if self._cavity is None:
            self.view.show_error("No cavity selected")
            return
        can_run, reason = self.session.can_run_phase(PHASE)
        if not can_run:
            self.view.show_error(f"Cannot run MP processing: {reason}")
            return
        if not self._cavity_hold.take(self._cavity):
            self.view.show_error(refusal_message(self._cavity))
            return
        if not self._open_attempt(operator):
            self._cavity_hold.release()
            return
        self.run = PhaseRun(
            self.phase, abort_hooks=(cavity_abort_hook(self._cavity),)
        )
        self.run.set_step_mode(self._step_mode)
        self.view.clear_run()
        self._start("check", CHECK_STEPS, offset=0)

    def _open_attempt(self, operator: str) -> bool:
        """Start the phase instance and build the phase.

        False, with an error shown, if nothing can run. Writes only to the
        commissioning database.
        """
        if self.session.get_active_record_id() is not None:
            started = self.session.start_active_phase_instance(
                PHASE, operator=operator
            )
            if started is None:
                self.view.show_error(
                    "Could not start an MP processing attempt in the "
                    "database; nothing was run"
                )
                return False
            self._active_phase_instance_id = started.phase_instance_id
        record = self.session.get_active_record()
        self._prior_data = record.mp_processing if record else None
        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": self._cavity},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        limits = MPProcessingLimits(**self.view.read_settings())
        self.phase = MPProcessingPhase(self.context, limits)
        ok, message = self.phase.validate_prerequisites()
        if not ok:
            self.view.show_error(f"Prerequisites not met: {message}")
            return False
        self.view.log_message(
            f"MP processing {self._cavity}: start {limits.start_amplitude_mv}"
            f" MV, +{limits.step_mv} MV every {limits.step_seconds:.0f} s, "
            f"hold {limits.quench_hold_seconds:.0f} s after a quench, "
            f"{limits.stable_seconds:.0f} s at ADES_MAX"
        )
        return True

    def _start(self, stage: str, steps, offset: int, complete=False) -> None:
        self.stage = stage
        started = self.bridge.start_segment(
            self.run,
            steps,
            progress_offset=offset,
            progress_total=len(ALL_STEPS),
            then_complete=complete,
            # setup_rf and the ADES walk show their cavity status lines.
            forward_logs=(self._cavity.logger,),
        )
        if not started:
            self.view.show_error("An MP processing segment is already running")
            return
        self.view.set_running(True)

    # ------------------------------------------------------------------
    # Segment results
    # ------------------------------------------------------------------

    def _on_segment_finished(self, result: SegmentResult) -> None:
        self.view.set_running(False)
        message = result.message or "Phase execution failed"
        if result.outcome is SegmentOutcome.ABORTED and self._rf_may_be_on():
            self._turn_rf_off(message)
            return
        if result.outcome is not SegmentOutcome.COMPLETED:
            self._on_failed(message)
            return
        if self.stage == "check":
            data = result.results["verify_initial_state"].data or {}
            if not ask_about_stale_results(
                self.view.ask_rerun,
                self.context.parameters,
                data,
                self.view.log_message,
            ):
                self.run.fail(
                    "Cancelled at the stale-result prompt; nothing written",
                    step="setup_rf",
                )
                self._on_failed("Cancelled before setup_rf; nothing written")
                return
            self._start("run", RUN_STEPS, offset=1, complete=True)
        elif self.stage == "run":
            # The Field Emission box, as it reads now. verify_initial_state
            # starts a fresh MPProcessingData, so values typed before or
            # during the run are only applied here. Once: Retry save
            # repeats only the failed writes, with the same run data.
            self.apply_fe_fields(self.context.record.mp_processing)
            self._unsaved = set(FINISH_WRITES)
            self._persist_finish()

    def _persist_finish(self) -> None:
        """Complete the instance, save the record and add the history entry.

        Whatever fails stays in _unsaved, with the instance id, and the
        phase is not reported complete. Start Test then retries only those
        writes.
        """
        record = self.context.record
        self._unsaved = persist_finished_phase(
            self.session,
            PHASE,
            self._active_phase_instance_id,
            record.mp_processing,
            self.context.operator,
            self._unsaved,
            self.view.log_message,
        )
        current = self.session.get_active_record()
        if current is not None:
            self.view.refresh_from_record(current)
        if self._unsaved:
            self.stage = "unsaved"
            self.view.set_retry_save()
            self.view.show_error(
                "MP processing finished but was not saved "
                f"({', '.join(sorted(self._unsaved))} failed). Press Retry "
                "save to try again. It writes nothing to the cavity."
            )
            return
        self._cavity_hold.release()
        self.stage = None
        self._active_phase_instance_id = None
        self.view.log_message("MP processing complete; RF left on in SELA")
        self.view.on_phase_finished("COMPLETED")
        self.phase_completed.emit(record)

    def _on_failed(self, message: str) -> None:
        """The runner has marked the phase FAILED; record that and say so.

        The artifact is this attempt's record.mp_processing. A failure
        before verify_initial_state replaced it sends none, so the last
        run's quenches are not attached to an attempt that ran nothing.
        They stay on the record.
        """
        self._cavity_hold.release()
        data = self.mp_data
        fresh = data is not None and data is not self._prior_data
        if fresh:
            # An aborted or failed run keeps what the operator saw. A
            # failure before verify_initial_state leaves the last run alone.
            self.apply_fe_fields(data)
        self._failure = (message, data.to_dict() if fresh else None)
        self._unsaved = {"save", "fail"}
        self._persist_failure()

    def _persist_failure(self) -> None:
        """Save the record and fail the instance; keep what fails.

        Whatever fails stays in _unsaved with the instance id, and Retry
        save repeats only that. It writes nothing to the cavity.
        """
        message, snapshot = self._failure
        if "save" in self._unsaved and self._save("Partial results saved"):
            self._unsaved.discard("save")
        if "fail" in self._unsaved:
            try:
                ok = (
                    self._active_phase_instance_id is None
                    or self.session.fail_active_phase_instance(
                        phase_instance_id=self._active_phase_instance_id,
                        phase=PHASE,
                        error_message=message,
                        artifact_payload=snapshot,
                    )
                )
            except Exception as exc:
                self.view.log_message(f"Warning: {exc}")
                ok = False
            if ok:
                self._unsaved.discard("fail")
        if self._unsaved:
            self.stage = "unsaved_failure"
            self.view.on_phase_finished("FAILED")
            self.view.set_retry_save()
            self.view.show_error(
                f"{message}\n\nThe failure was not saved "
                f"({', '.join(sorted(self._unsaved))} failed). Press Retry "
                "save to try again. It writes nothing to the cavity."
            )
            return
        self.stage = None
        self._failure = None
        self._active_phase_instance_id = None
        self.view.on_phase_finished("FAILED")
        self.view.show_error(message)

    def apply_fe_fields(self, data) -> None:
        """Copy the Field Emission box onto data (MPProcessingData).

        field_emission_onset and fe_50_mr_h_amplitude, ADES in MV, or None
        for "not seen". Operator-entered: nothing reads them from a PV.
        """
        for field, value in self.view.read_fe_fields().items():
            setattr(data, field, value)

    def save_fe_fields(self) -> None:
        """Save FE: the Field Emission box onto the record's last run.

        Database only. Not during a run, which saves them when it finishes.
        The finished run's measurement history entry keeps the values it
        was saved with.
        """
        if self.running or self.stage in ("unsaved", "unsaved_failure"):
            self.view.show_error(
                "The run saves the field emission values when it finishes"
            )
            return
        record = self.session.get_active_record()
        if record is None or record.mp_processing is None:
            self.view.show_error(
                "No MP processing run on this record to save the field "
                "emission values to"
            )
            return
        self.apply_fe_fields(record.mp_processing)
        self._save("Field emission values saved")

    def _save(self, success_line: str) -> bool:
        try:
            saved = bool(self.session.save_active_record())
        except Exception as exc:
            saved = False
            self.view.log_message(f"Warning: save failed: {exc}")
        self.view.log_message(
            success_line if saved else "Warning: not saved to the database"
        )
        record = self.session.get_active_record()
        if record is not None:
            self.view.refresh_from_record(record)
        return saved

    # ------------------------------------------------------------------
    # RF off after an abort between steps
    # ------------------------------------------------------------------

    def _rf_may_be_on(self) -> bool:
        """True if an abort in the run segment reached no check_abort.

        Inside setup_rf or process, cavity.check_abort() turns RF off and
        clears abort_flag. A flag still set after the run segment means the
        abort came between steps, where nothing checked it, so RF is as the
        last step left it.
        """
        return self.stage == "run" and bool(self._cavity.abort_flag)

    def _turn_rf_off(self, message: str) -> None:
        """Turn RF off on a daemon thread, then fail the attempt.

        PV write: Cavity.turn_off() (RFCTRL off), which waits for RF to
        read off. abort_flag is cleared first: turn_off's wait calls
        check_abort, which would otherwise call turn_off again and raise.
        The cavity stays held until this finishes.
        """
        cavity = self._cavity
        self.stage = "rf_off"
        self.view.set_running(True)
        self.view.log_message("Aborted between steps: turning RF off")

        def work() -> None:
            error = ""
            try:
                cavity.abort_flag = False
                cavity.turn_off()
            except Exception as exc:
                error = str(exc) or type(exc).__name__
            self._rf_off_finished.emit(message, error)

        threading.Thread(target=work, daemon=True).start()

    def _on_rf_off_finished(self, message: str, error: str) -> None:
        self.stage = None
        self.view.set_running(False)
        if error:
            message = f"{message}. Turning RF off failed: {error}"
        else:
            message = f"{message}. RF is off."
        self._on_failed(message)

    # ------------------------------------------------------------------
    # Abort and step mode
    # ------------------------------------------------------------------

    def on_abort(self) -> None:
        """Abort through PhaseRun and cavity_abort_hook.

        Inside setup_rf or process, cavity.check_abort() turns RF off and
        raises. Between steps the run stops before the next one.
        """
        if self.stage == "rf_off":
            # Already turning RF off. Setting abort_flag again would make
            # turn_off's own wait call turn_off and raise.
            return
        if self.run is not None and self.running:
            self.run.request_abort()
            # Within poll_interval (1 s) while ADES is held. If
            # Cavity.reset_interlocks is retrying a reset, which does not
            # check abort, up to about 48 s (see MPProcessingPhase).
            self.view.log_message(
                "Abort requested. RF is turned off at the next abort check: "
                "within a second while ADES is held, or up to about 48 s if "
                "an interlock reset is retrying."
            )

    def on_pause(self) -> None:
        """Pause or resume the walk inside process. Writes no PVs.

        Paused, the phase writes no ADES and resets no interlocks; the
        operator has the amplitude. Resume goes on from the ADES read back
        then. The phase refuses a resume while QUENCH_LTCH is set.
        """
        if self.phase is None or self.stage != "run" or not self.running:
            return
        state = self.phase.pause_state
        if state == "paused":
            self.phase.request_resume()
            self.view.log_message(
                "Resume requested: the walk goes on from the ADES on the "
                "machine now."
            )
        elif state == "running":
            self.phase.request_pause()
            self.view.log_message(
                "Pause requested. The tab shows Paused once ADES writes and "
                "interlock resets have stopped: within a second, or after "
                "an interlock reset that is retrying (up to about 48 s). RF "
                "stays on. Then set ADES by hand and press Resume. Abort "
                "still turns RF off."
            )
        # "pausing" / "resuming": the phase hasn't acted on the last press.

    def on_toggle_step_mode(self) -> None:
        self._step_mode = not self._step_mode
        if self.run is not None:
            self.run.set_step_mode(self._step_mode)
        if not self._step_mode:
            self.view.set_next_enabled(False)

    def on_next_step(self) -> None:
        if self.run is not None and self._step_mode:
            self.view.set_next_enabled(False)
            self.run.next_step()

    def _on_step_started(self, step: str, index: int, total: int) -> None:
        self.view.set_next_enabled(False)
        number = ALL_STEPS.index(step) + 1
        self.view.set_step(f"{step} ({number} of {len(ALL_STEPS)})")
        self.view.on_step_started(step)

    def _on_holding(self, step: str, reason: str) -> None:
        if reason == HOLD_STEP_MODE:
            self.view.log_message(f"Step mode: press Next to run {step}")
            self.view.set_next_enabled(True)
