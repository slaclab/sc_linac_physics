"""Controller for the Piezo with RF display.

Runs PiezoWithRFPhase through PhaseRun and RunnerBridge in four segments,
each started from the GUI thread:

  1. Start Test: verify_initial_state. Its data says whether the SSA
     calibration and the characterization are stale; the display asks the
     operator Rerun or Skip for each, and the answers go in
     context.parameters["rerun_ssa_calibration"] / ["rerun_characterization"].
  2. setup_rf through read_results. Nothing is pushed. The record is saved
     and the phase instance stays open for review.
  3a. Push to IOC (after the display's confirm): sets
     context.parameters["confirmed_detune_gain"] to read_results'
     data["detune_gain"], then push_detune_gain and record_results, then
     complete. push_detune_gain processes PUSH_DFGAIN, then SAVE_DFGAIN.
  3b. Don't Push: PhaseRun.skip_step("push_detune_gain") with the operator and
     a justification, then record_results and complete.
     record.piezo_with_rf.detune_gain_pushed stays False.

Abort goes through cavity_abort_hook: PhaseRun.request_abort() sets
context.abort_requested and calls cavity.request_abort(). The phase's waits
call cavity.check_abort(), which turns RF off and raises. RunnerBridge clears
both before each segment.
"""

from PyQt5.QtCore import QObject, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (  # noqa: E501
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_with_rf import (  # noqa: E501
    PiezoWithRFPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    HOLD_STEP_MODE,
    PhaseRun,
    SegmentOutcome,
    SegmentResult,
    cavity_abort_hook,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (  # noqa: E501
    apply_pv_mapping,
    resolve_cavity_selection,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.runner_bridge import (  # noqa: E501
    RunnerBridge,
)
from sc_linac_physics.utils.sc_linac.linac import Machine

PHASE = CommissioningPhase.PIEZO_WITH_RF
ALL_STEPS = (
    "verify_initial_state",
    "setup_rf",
    "setup_piezo",
    "check_detune",
    "start_test",
    "wait_for_completion",
    "read_results",
    "push_detune_gain",
    "record_results",
)
CHECK_STEPS = ALL_STEPS[:1]
MEASURE_STEPS = ALL_STEPS[1:7]
PUSH_STEPS = ALL_STEPS[7:]

# Stale results setup_rf would re-run: data key prefix, parameter, label, PV.
STALE_PROMPTS = (
    ("ssa_calibration", "rerun_ssa_calibration", "SSA calibration", "CALTS"),
    (
        "characterization",
        "rerun_characterization",
        "characterization",
        "PROBECALTS",
    ),
)


def live_pv_addresses(cavity) -> dict[str, str]:
    """Widget name -> PV address for the Live PVs box. Read-only."""
    piezo = cavity.piezo
    return {
        "pydm_test_run": piezo.withrf_check_status_pv,  # RFTESTSTS
        "pydm_test_status": piezo.withrf_status_pv,  # RFTESTSTAT
        "pydm_gain_a": piezo.amplifiergain_a_pv,  # CHA_AMPGAIN
        "pydm_gain_b": piezo.amplifiergain_b_pv,  # CHB_AMPGAIN
        "pydm_dfgain_new": piezo.detunegain_new_pv,  # DFGAIN_NEW
        # The hardware model has no attribute for the live gain.
        "pydm_dfgain_current": piezo.pv_addr("DFGAIN"),
        "pydm_rf_state": cavity.rf_state_pv,  # RFSTATE
    }


class PiezoWithRFController(QObject):
    """Owns PiezoWithRFPhase execution for the Piezo with RF display."""

    phase_completed = pyqtSignal(object)

    def __init__(self, view, session) -> None:
        super().__init__()
        self.view = view
        self.session = session
        self.machine: Machine | None = None
        self._cavity = None
        self.context: PhaseContext | None = None
        self.phase: PiezoWithRFPhase | None = None
        self.run: PhaseRun | None = None
        # Which segment is running or was last run: "check", "measure",
        # "review" (measured, waiting for Push or Don't Push) or "finish".
        self.stage: str | None = None
        self.review_data: dict | None = None
        self._step_mode = False
        self._active_phase_instance_id: int | None = None

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
        return self.bridge.running

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
                self.drop_review()
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
        """The phase needs CommissioningPiezo for the with-RF PVs."""
        if not self.machine:
            self.machine = Machine(piezo_class=CommissioningPiezo)
        key = f"{int(cm):02d}" if str(cm).isdigit() else str(cm)
        return self.machine.cryomodules[key].cavities[cav]

    def drop_review(self) -> None:
        """Forget an unpushed measurement. Its instance is left open."""
        if self.running:
            return
        if self.stage == "review":
            self.stage = None
        self.review_data = None
        self.phase = self.context = self.run = None
        self._active_phase_instance_id = None
        self.view.set_review_enabled(False)

    # ------------------------------------------------------------------
    # Segment 1: Start Test
    # ------------------------------------------------------------------

    def on_start_test(self) -> None:
        if self.running:
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
            self.view.show_error(f"Cannot run Piezo with RF: {reason}")
            return

        # An unpushed measurement leaves its instance open; a new test
        # continues that attempt, as cavity char does.
        record_id = self.session.get_active_record_id()
        if record_id is not None and self._active_phase_instance_id is None:
            started = self.session.start_active_phase_instance(
                PHASE, operator=operator
            )
            self._active_phase_instance_id = (
                started.phase_instance_id if started else None
            )
        self.context = PhaseContext(
            record=self.session.get_active_record(),
            operator=operator,
            parameters={"cavity": self._cavity},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        self.phase = PiezoWithRFPhase(self.context)
        ok, message = self.phase.validate_prerequisites()
        if not ok:
            self.view.show_error(f"Prerequisites not met: {message}")
            return
        self.run = PhaseRun(
            self.phase, abort_hooks=(cavity_abort_hook(self._cavity),)
        )
        self.run.set_step_mode(self._step_mode)
        self.review_data = None
        self.view.clear_review()
        self._start("check", CHECK_STEPS, offset=0)

    def _start(self, stage: str, steps, offset: int, complete=False) -> None:
        """Start a segment; progress is reported across all nine steps."""
        self.stage = stage
        started = self.bridge.start_segment(
            self.run,
            steps,
            progress_offset=offset,
            progress_total=len(ALL_STEPS),
            then_complete=complete,
        )
        if not started:
            self.view.show_error("A Piezo with RF segment is already running")
            return
        self.view.set_running(True)

    # ------------------------------------------------------------------
    # Segment 2: setup_rf .. read_results, after the stale prompts
    # ------------------------------------------------------------------

    def _ask_about_stale_results(self, data: dict) -> bool:
        """One popup per stale result. False if the operator cancelled."""
        for key, param, label, pv in STALE_PROMPTS:
            if data.get(f"{key}_recent", True):
                continue
            good = data.get(f"{key}_good", data.get(f"{key}_complete"))
            answer = self.view.ask_rerun(
                label, pv, data.get(f"{key}_time"), good
            )
            if answer is None:
                return False
            self.context.parameters[param] = answer
            self.view.log_message(
                f"{label}: operator chose {'Rerun' if answer else 'Skip'}"
            )
        return True

    # ------------------------------------------------------------------
    # Segment 3: Push to IOC, or Don't Push
    # ------------------------------------------------------------------

    def on_push(self) -> None:
        """Push the detune gain the operator just confirmed in the display.

        confirmed_detune_gain is the float read_results returned, never the
        text on screen. PiezoWithRFPhase._push_detune_gain refuses unless it
        equals the DFGAIN_NEW it read and DFGAIN_NEW is unchanged on the IOC.
        """
        if self.running or self.stage != "review" or not self.review_data:
            return
        gain = self.review_data["detune_gain"]
        self.context.parameters["confirmed_detune_gain"] = gain
        self.view.log_message(f"Pushing detune gain {gain:.6f} to the IOC")
        self._start("finish", PUSH_STEPS, offset=7, complete=True)

    def on_decline_push(self, justification: str) -> None:
        """Complete the phase without pushing. No PV is written."""
        if self.running or self.stage != "review":
            return
        try:
            self.run.skip_step(
                "push_detune_gain", self.context.operator, justification
            )
        except ValueError as exc:
            self.view.show_error(str(exc))
            return
        self.view.log_message(
            f"⊘ push_detune_gain skipped by {self.context.operator}: "
            f"{justification.strip()}"
        )
        self._start("finish", PUSH_STEPS[1:], offset=8, complete=True)

    # ------------------------------------------------------------------
    # Segment results
    # ------------------------------------------------------------------

    def _on_segment_finished(self, result: SegmentResult) -> None:
        self.view.set_running(False)
        if result.outcome is not SegmentOutcome.COMPLETED:
            self._on_failed(result.message or "Phase execution failed")
            return
        if self.stage == "check":
            data = result.results["verify_initial_state"].data or {}
            if not self._ask_about_stale_results(data):
                self.run.fail(
                    "Cancelled at the stale-result prompt; nothing written",
                    step="setup_rf",
                )
                self._on_failed("Cancelled before setup_rf; nothing written")
                return
            self._start("measure", MEASURE_STEPS, offset=1)
        elif self.stage == "measure":
            self._on_measured(result.results["read_results"].data or {})
        elif self.stage == "finish":
            self._on_finished()

    def _on_measured(self, data: dict) -> None:
        """Save the measurement. The phase instance stays open for review."""
        self.stage = "review"
        self.review_data = data
        self._save("Measurement saved; review it, then Push or Don't Push")
        self.view.show_review(data)

    def _on_finished(self) -> None:
        """Push or Don't Push completed: close the instance and save."""
        self.stage = None
        self.review_data = None
        record = self.context.record
        data = record.piezo_with_rf
        try:
            if self._active_phase_instance_id is not None:
                self.session.complete_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=PHASE,
                    artifact_payload=data.to_dict() if data else None,
                )
            if data is not None:
                self.session.add_measurement_to_history(
                    PHASE,
                    data,
                    operator=self.context.operator,
                    phase_instance_id=self._active_phase_instance_id,
                )
        except Exception as exc:
            self.view.log_message(f"Warning: closing the phase failed: {exc}")
        self._active_phase_instance_id = None
        self._save("Piezo with RF complete")
        self.view.on_phase_finished("COMPLETED")
        self.phase_completed.emit(record)

    def _on_failed(self, message: str) -> None:
        """The runner has marked the phase FAILED; record that and say so."""
        self.stage = None
        self.review_data = None
        snapshot = None
        if self.context is not None and self.context.record.piezo_with_rf:
            snapshot = self.context.record.piezo_with_rf.to_dict()
        self._save("Partial results saved")
        if self._active_phase_instance_id is not None:
            try:
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=PHASE,
                    error_message=message,
                    artifact_payload=snapshot,
                )
            except Exception as exc:
                self.view.log_message(f"Warning: {exc}")
        self._active_phase_instance_id = None
        self.view.on_phase_finished("FAILED")
        self.view.show_error(message)

    def _save(self, success_line: str) -> None:
        try:
            saved = self.session.save_active_record()
        except Exception as exc:
            saved = False
            self.view.log_message(f"Warning: save failed: {exc}")
        self.view.log_message(
            success_line if saved else "Warning: not saved to the database"
        )
        record = self.session.get_active_record()
        if record is not None:
            self.view.refresh_from_record(record)

    # ------------------------------------------------------------------
    # Abort, pause, step mode
    # ------------------------------------------------------------------

    def on_abort(self) -> None:
        """Abort through PhaseRun: the context and cavity.request_abort().

        During wait_for_completion, cavity.check_abort() then calls
        turn_off() and raises. Between steps the run stops before the next
        one and writes nothing.
        CHECK: does the with-RF script keep running once RF is off?
        """
        if self.run is not None and self.running:
            self.run.request_abort()
            self.view.log_message(
                "Abort requested. If the test is running, RF is turned off; "
                "otherwise the run stops before its next step."
            )

    def on_pause_test(self) -> None:
        if self.run is None or not self.running:
            return
        if self.run.paused:
            self.run.resume()
            self.view.log_message("Resumed")
        else:
            self.run.pause()
            self.view.log_message("Paused before the next step")
        self.view.set_paused(self.run.paused)

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
        self.view.set_step(f"{step} ({ALL_STEPS.index(step) + 1} of 9)")

    def _on_holding(self, step: str, reason: str) -> None:
        if reason == HOLD_STEP_MODE:
            self.view.log_message(f"Step mode: press Next to run {step}")
            self.view.set_next_enabled(True)
