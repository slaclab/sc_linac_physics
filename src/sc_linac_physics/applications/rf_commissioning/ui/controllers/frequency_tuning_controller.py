"""Controller for the Frequency Tuning display."""

import time
from datetime import datetime
from threading import Thread

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    FrequencyTuningData,
    PhaseCheckpoint,
)
from sc_linac_physics.applications.rf_commissioning.phases.frequency_tuning import (
    FrequencyTuningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.stage_status import (
    STAGE_CARD_STYLE_IDLE,
    STAGE_CARD_STYLE_RUNNING,
    STAGE_STATUS_DONE,
    STAGE_STATUS_FAILED,
    STAGE_STATUS_NOT_STARTED,
    STAGE_STATUS_RUNNING,
    STAGE_STATUS_STYLE_DONE,
    STAGE_STATUS_STYLE_FAILED,
    STAGE_STATUS_STYLE_NOT_STARTED,
    STAGE_STATUS_STYLE_RUNNING,
)
from sc_linac_physics.applications.rf_commissioning.ui.step_labels import (
    step_label,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (
    apply_pv_mapping,
    format_pv_update_message,
    resolve_cavity_selection,
)
from sc_linac_physics.utils.sc_linac.linac import Machine

_STAGE_COLD_LANDING = "cold_landing"
_STAGE_PROBE_DIRECTION = "probe_direction"
_STAGE_TUNE_TO_RESONANCE = "tune_to_resonance"
_STAGE_PI_MODES = "pi_modes"

# Kept as a module-level alias so existing call sites read unchanged; the
# table itself lives in ui.step_labels so non-controller callers can format
# a label without importing this module (and therefore linac.MACHINE).
_step_label = step_label


_STAGE1_STEPS = ["verify_initial_state", "record_cold_landing"]
_STAGE2_STEPS = ["check_state_for_stage_2", "probe_stepper_direction"]
_STAGE3_STEPS = [
    "check_state_for_stage_3",
    "apply_hz_per_step",
    "tune_to_resonance",
]
_STAGE4_STEPS = ["check_state_for_stage_4", "measure_pi_modes"]
_STAGE4_FINALIZE_STEPS = ["record_results"]

# Cumulative step offset for each stage, used to compute overall progress.
_TOTAL_COMMISSIONING_STEPS = sum(
    len(s) for s in (_STAGE1_STEPS, _STAGE2_STEPS, _STAGE3_STEPS, _STAGE4_STEPS)
)
_STAGE_STEP_OFFSETS = {
    1: 0,
    2: len(_STAGE1_STEPS),
    3: len(_STAGE1_STEPS) + len(_STAGE2_STEPS),
    4: len(_STAGE1_STEPS) + len(_STAGE2_STEPS) + len(_STAGE3_STEPS),
    5: _TOTAL_COMMISSIONING_STEPS,  # confirm & save — clamps at 100%
}


class FrequencyTuningController(QObject):
    """Owns phase execution and plot wiring for the Frequency Tuning display."""

    phase_completed = pyqtSignal(object)
    phase_run_finished = pyqtSignal(bool, str)
    _log_signal = pyqtSignal(str)
    # (key, message, entry_type) — resolves the step's in-progress feed row.
    _resolve_log_signal = pyqtSignal(str, str, str)
    hz_per_step_updated = pyqtSignal(float)
    _stage_done = pyqtSignal(int)  # 1, 2, 3, or 4 (=finalize)

    def __init__(self, view, session: CommissioningSession) -> None:
        super().__init__()
        self.view = view
        self.session = session
        if hasattr(self.view, "log_message"):
            self._log_signal.connect(self.view.log_message)
        if hasattr(self.view, "resolve_log_message"):
            self._resolve_log_signal.connect(self.view.resolve_log_message)

        self.context: PhaseContext | None = None
        self.phase: FrequencyTuningPhase | None = None
        self.machine: Machine | None = None
        self._cavity = None

        self._paused = False
        self._steps: list[str] = []
        self._finalize_after_run: bool = False
        self._phase_started: bool = False
        self._df_cold_hz: float | None = None
        self._active_phase_instance_id: int | None = None

        self._current_stage: int = 0
        self._stage_running: bool = False
        self._hz_est_total_steps: float = 0.0
        self._hz_est_total_hz: float = 0.0
        self._net_steps: int = 0
        self._tune_step_data: dict = {}
        self._probe_stage_confirmed: bool = False
        self._step_signed_pv_obj = None
        self._pending_stage2_data: dict = {}
        self._probe_s_d0: int | None = None
        self._probe_s_d1: int | None = None
        self._probe_d0_hz: float | None = None
        self._probe_d1_hz: float | None = None
        self._pi_mode_data: dict = {}

        self.phase_run_finished.connect(self._on_phase_run_finished)
        self._stage_done.connect(self._on_stage_done)

    # ------------------------------------------------------------------
    # PV wiring
    # ------------------------------------------------------------------

    def setup_pv_connections(self) -> None:
        if self.session.has_active_record():
            self.update_pv_addresses()

    def update_pv_addresses(
        self,
        cryomodule: str | None = None,
        cavity_number: str | None = None,
    ) -> None:
        cryomodule, cavity_number = resolve_cavity_selection(
            self.view, cryomodule, cavity_number
        )
        if cryomodule is None or cavity_number is None:
            return

        try:
            cm, cav = int(cryomodule), int(cavity_number)
            cavity = self._get_machine_cavity(cm, cav)
            self._cavity = cavity
            self._step_signed_pv_obj = None
            self._apply_stepper_pv_mapping(cavity)
            self.view.log_message(
                format_pv_update_message(cryomodule, cavity_number, cm, cav)
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _apply_stepper_pv_mapping(self, cavity) -> None:
        stepper = cavity.stepper_tuner
        piezo = cavity.piezo
        pv_map = {}
        for widget_name, pv_addr in (
            ("steps_spinbox", stepper.step_des_pv),
            ("max_steps_spinbox", stepper.max_steps_pv),
            ("detune_chirp_readback", cavity.detune_chirp_pv),
            ("df_cold_readback", cavity.pv_addr("DF_COLD")),
            ("scale_readback", stepper.hz_per_microstep_pv),
            ("net_steps_label", stepper.step_signed_pv),
            ("fscan_stat_readback", cavity.rack.pv_prefix + "FSCAN:STAT"),
            ("stage4_8pi9_label", cavity.pv_addr("FSCAN:8PI9MODE")),
            ("stage4_7pi9_label", cavity.pv_addr("FSCAN:7PI9MODE")),
            # Piezo state and RF drive level — visible during tuning so that
            # piezo feedback fighting the stepper is diagnosable, and
            # correctable, without leaving this tab.
            ("piezo_enable_stat_readback", piezo.enable_stat_pv),
            ("piezo_enable_ctrl", piezo.enable_pv),
            ("piezo_mode_stat_readback", piezo.feedback_stat_pv),
            ("piezo_mode_ctrl", piezo.feedback_control_pv),
            ("drive_level_readback", cavity.drive_level_pv),
        ):
            if hasattr(self.view, widget_name):
                pv_map[getattr(self.view, widget_name)] = pv_addr
        apply_pv_mapping(pv_map)

    def _get_machine_cavity(self, cm: int, cav: int):
        if not self.machine:
            self.machine = Machine()
        return self.machine.cryomodules[f"{cm:02d}"].cavities[cav]

    # ------------------------------------------------------------------
    # Public stage entry points
    # ------------------------------------------------------------------

    def on_run_automated_test(self) -> None:
        """Backward-compat alias → run_stage_1."""
        self.run_stage_1()

    def run_stage_1(self) -> None:
        """Verify initial state and record cold landing frequency."""
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator in the header before running."
            )
            return

        # Flip the stage card to "Running" on the button press itself, before
        # _resolve_target() touches the database. Operator feedback on PR #270
        # was that the status change was easy to miss because it landed after
        # record creation and prerequisite validation, by which time the Run
        # button had already greyed out and nothing else had visibly changed.
        # Reverted below if we never actually get the stage started.
        self._set_stage_status_running(1)

        target = self._resolve_target()
        if target is None:
            self._set_stage_status_not_started(1)
            return

        cavity_name, cm, cav = target
        self.view.log_message(
            f"Stage 1: Setup & Cold Landing for {cavity_name}"
        )
        self.view.clear_results()
        self.view.reset_plot()
        self._df_cold_hz = None
        self._hz_est_total_steps = 0.0
        self._hz_est_total_hz = 0.0
        self._net_steps = 0

        try:
            self._start_stage(
                stage=1,
                steps=_STAGE1_STEPS,
                finalize=False,
                cm=cm,
                cav=cav,
                operator=operator,
            )
        except Exception as exc:
            import traceback

            self._set_stage_status_not_started(1)
            self.view.show_error(f"Failed to start Stage 1: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

    def run_stage_2(self) -> None:
        """Probe stepper direction to measure Hz/step."""
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator in the header before running."
            )
            return

        if not self.phase or not self.context:
            self.view.show_error("Run Stage 1 first.")
            return

        if not self._check_data_prerequisites(2):
            return

        self.view.log_message("Stage 2: Probing stepper direction...")
        self._probe_stage_confirmed = False
        self._pending_stage2_data = {}
        if hasattr(self.view, "reset_plot"):
            self.view.reset_plot()
        confirm_probe_btn = getattr(self.view, "confirm_probe_fit_button", None)
        if confirm_probe_btn is not None:
            confirm_probe_btn.setEnabled(False)
        self._current_stage = 2
        self._steps = list(_STAGE2_STEPS)
        self._finalize_after_run = False
        self._set_stage_running_ui(2)
        QTimer.singleShot(100, self._run_phase_in_background)

    def run_stage_3(self) -> None:
        """Apply Hz/step to SCALE PV and tune to resonance."""
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator in the header before running."
            )
            return

        if not self.phase or not self.context:
            self.view.show_error("Run Stage 2 first.")
            return

        if not self._check_data_prerequisites(3):
            return

        hz = self._get_hz_per_step_from_view()
        if hz and hz != 0 and self.phase._hz_per_microstep is not None:
            self.phase._hz_per_microstep = hz

        self.view.log_message("Stage 3: Tuning to resonance...")
        if hasattr(self.view, "reset_plot"):
            self.view.reset_plot()
        self._current_stage = 3
        self._steps = list(_STAGE3_STEPS)
        self._finalize_after_run = False
        self._set_stage_running_ui(3)
        QTimer.singleShot(100, self._run_phase_in_background)

    def run_stage_4(self) -> None:
        """Run the rack FSCAN to measure 8π/9 and 7π/9 pi modes."""
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator in the header before running."
            )
            return

        if not self.phase or not self.context:
            self.view.show_error("Run Stage 3 first.")
            return

        if not self._check_data_prerequisites(4):
            return

        self.view.log_message("Stage 4: Measuring pi modes...")
        self._current_stage = 4
        self._steps = list(_STAGE4_STEPS)
        self._finalize_after_run = False
        self._set_stage_running_ui(4)
        QTimer.singleShot(100, self._run_phase_in_background)

    def confirm_and_save(self) -> None:
        """Finalize results and save to database."""
        if not self.phase or not self.context:
            self.view.show_error("Complete Stage 4 first.")
            return

        self.view.log_message("Confirming and saving results...")
        self._current_stage = 5
        self._steps = list(_STAGE4_FINALIZE_STEPS)
        self._finalize_after_run = True
        self._set_stage_running_ui(None)
        QTimer.singleShot(100, self._run_phase_in_background)

    def on_confirm_and_tune(self) -> None:
        """Backward-compat alias → run_stage_3."""
        self.run_stage_3()

    def _check_data_prerequisites(self, stage: int) -> bool:
        """Check that data recorded by previous stages is available.

        Returns True if the stage can proceed, False if prerequisite data
        is missing.  Results are logged to the activity feed.  These checks
        run on the main thread (Python-only, no EPICS reads) before the
        background worker is scheduled.
        """
        if stage == 2:
            if self._df_cold_hz is None:
                self.view.log_message(
                    "✗ Cold landing not recorded — run Stage 1 first"
                )
                return False
            self.view.log_message(
                f"✓ Cold landing data ready ({self._df_cold_hz:.0f} Hz)"
            )
        elif stage == 3:
            if not self._probe_stage_confirmed:
                self.view.log_message(
                    "✗ Hz/step not measured — run Stage 2 first"
                )
                return False
            self.view.log_message("✓ Hz/step data ready")
        return True

    # ------------------------------------------------------------------
    # Phase setup
    # ------------------------------------------------------------------

    def _resolve_target(self) -> tuple[str, int, int] | None:
        cryomodule, cavity_number = resolve_cavity_selection(
            self.view, None, None
        )
        if cryomodule is None or cavity_number is None:
            self.view.show_error(
                "Unable to determine cavity. Select a cavity and try again."
            )
            return None

        try:
            cm, cav = int(cryomodule), int(cavity_number)
        except ValueError:
            self.view.show_error(
                f"Invalid cavity selection: CM={cryomodule} Cav={cavity_number}"
            )
            return None

        try:
            record, record_id, created = self.session.start_new_record(
                cryomodule=cryomodule, cavity_number=cavity_number
            )
            status = "Created" if created else "Loaded"
            self.view.log_message(
                f"✓ {status} record for CM{cryomodule} Cav{cavity_number} (ID: {record_id})"
            )
            self.view._notify_parent_of_record_update(record, "Record ready")
        except Exception as exc:
            import traceback

            self.view.show_error(f"Failed to get/create record:\n\n{exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            return None

        return f"CM{cm:02d}_CAV{cav}", cm, cav

    def _start_stage(
        self,
        stage: int,
        steps: list[str],
        finalize: bool,
        cm: int,
        cav: int,
        operator: str,
    ) -> None:
        self.update_pv_addresses(f"{cm:02d}", str(cav))
        cavity = self._get_machine_cavity(cm, cav)
        self._cavity = cavity

        record = self.session.get_active_record()
        record_id = self.session.get_active_record_id()
        self.view.log_message(f"Using record ID: {record_id}")

        can_run, reason = self.session.can_run_phase(
            CommissioningPhase.FREQUENCY_TUNING
        )
        if not can_run:
            self.view.show_error(f"Cannot run frequency tuning phase: {reason}")
            return

        if record_id is not None:
            phase_start = self.session.start_active_phase_instance(
                CommissioningPhase.FREQUENCY_TUNING, operator=operator
            )
            self._active_phase_instance_id = (
                phase_start.phase_instance_id if phase_start else None
            )

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": cavity},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        self.phase = FrequencyTuningPhase(self.context)
        self._phase_started = False
        self._current_stage = stage

        is_valid, message = self.phase.validate_prerequisites()
        if not is_valid:
            self.view.show_error(f"Prerequisites not met: {message}")
            return

        self._steps = list(steps)
        self._finalize_after_run = finalize
        self._set_stage_running_ui(stage)
        QTimer.singleShot(100, self._run_phase_in_background)

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _set_stage_status(self, stage: int, text: str, style: str) -> None:
        """Set one stage card's status label text and style together."""
        status_lbl = getattr(self.view, f"stage{stage}_status_label", None)
        if status_lbl is not None:
            status_lbl.setText(text)
            status_lbl.setStyleSheet(style)

    def _set_stage_status_running(self, stage: int) -> None:
        """Mark a stage card as running and highlight the card itself."""
        self._set_stage_status(
            stage, STAGE_STATUS_RUNNING, STAGE_STATUS_STYLE_RUNNING
        )
        self._highlight_stage_card(stage, running=True)

    def _set_stage_status_not_started(self, stage: int) -> None:
        """Return a stage card to its resting state."""
        self._set_stage_status(
            stage, STAGE_STATUS_NOT_STARTED, STAGE_STATUS_STYLE_NOT_STARTED
        )
        self._highlight_stage_card(stage, running=False)

    def _highlight_stage_card(self, stage: int, running: bool) -> None:
        """Swap a stage card's frame styling to mark it as the active stage.

        The Run button greys out while a stage executes, so the card border and
        tint are what keep the running stage identifiable (operator feedback on
        PR #270).
        """
        card = getattr(self.view, f"stage{stage}_card", None)
        if card is None:
            return
        card.setStyleSheet(
            STAGE_CARD_STYLE_RUNNING if running else STAGE_CARD_STYLE_IDLE
        )

    def _clear_all_stage_highlights(self) -> None:
        for stage in (1, 2, 3, 4):
            self._highlight_stage_card(stage, running=False)

    def _show_stage_description(self, stage: int, visible: bool) -> None:
        """Show or hide a stage card's instructional description.

        Hidden once the stage is Done — the text explains what the stage is
        about to do, so afterwards it is just occupying vertical space that the
        remaining stages need.
        """
        desc = getattr(self.view, f"stage{stage}_description", None)
        if desc is not None:
            desc.setVisible(visible)

    def _set_stage_running_ui(self, stage: int | None) -> None:
        self._stage_running = True
        if stage is not None:
            btn = getattr(self.view, f"stage{stage}_run_btn", None)
            if btn is not None:
                btn.setEnabled(False)
            self._set_stage_status_running(stage)

        pause_btn = getattr(self.view, "pause_button", None)
        if pause_btn:
            pause_btn.setEnabled(True)
        abort_btn = getattr(self.view, "abort_button", None)
        if abort_btn:
            abort_btn.setEnabled(True)
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("RUNNING")
        self._update_toolbar_state("running")

    def _set_stage_done_ui(self, stage: int, success: bool) -> None:
        if success:
            self._set_stage_status(
                stage, STAGE_STATUS_DONE, STAGE_STATUS_STYLE_DONE
            )
        else:
            self._set_stage_status(
                stage, STAGE_STATUS_FAILED, STAGE_STATUS_STYLE_FAILED
            )
        self._highlight_stage_card(stage, running=False)
        # A finished stage no longer needs its "here is what this does" blurb;
        # a failed one still does, since the operator is about to retry it.
        self._show_stage_description(stage, visible=not success)
        btn = getattr(self.view, f"stage{stage}_run_btn", None)
        if btn is not None:
            btn.setEnabled(not success)

    def _enable_stage_btn(self, stage: int) -> None:
        btn = getattr(self.view, f"stage{stage}_run_btn", None)
        if btn is not None:
            btn.setEnabled(True)

    def _clear_running_ui(self) -> None:
        self._stage_running = False
        self._clear_all_stage_highlights()
        pause_btn = getattr(self.view, "pause_button", None)
        if pause_btn:
            pause_btn.setEnabled(False)
            pause_btn.setText("⏸ Pause")
        abort_btn = getattr(self.view, "abort_button", None)
        if abort_btn:
            abort_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    def _reset_abort_and_speed(self) -> None:
        self.context.abort_requested = False
        if self._cavity is not None:
            try:
                self._cavity.stepper_tuner.abort_flag = False
            except Exception:
                pass
        speed_spinbox = getattr(self.view, "speed_spinbox", None)
        if speed_spinbox is not None and self.phase is not None:
            self.phase.limits.move_speed = speed_spinbox.value()

    def _run_phase_in_background(self) -> None:
        if not self.context or not self.phase:
            return

        self._reset_abort_and_speed()

        self.context.progress_callback = (
            lambda step, prog: self.view.step_progress_signal.emit(step, prog)
        )
        self.context.parameters["tuning_update_callback"] = (
            lambda signed_steps, detune: self.view.tuning_data_signal.emit(
                float(signed_steps), detune
            )
        )
        self.context.parameters["probe_update_callback"] = (
            lambda signed_steps, detune: self.view.tuning_data_signal.emit(
                float(signed_steps), detune
            )
        )
        self.context.parameters["status_update_callback"] = (
            lambda msg: self._log_signal.emit(msg)
        )
        finalize = self._finalize_after_run
        steps = list(self._steps)
        current_stage = self._current_stage

        def worker() -> None:
            try:
                if not self._phase_started:
                    self.phase._mark_phase_started()
                    self._phase_started = True

                for step_name in steps:
                    if not self._check_pause_and_abort():
                        return

                    success = self._execute_single_step(step_name)
                    if not success:
                        self.phase_run_finished.emit(
                            False, f"Step failed: {_step_label(step_name)}"
                        )
                        return

                if finalize:
                    self._finalize_background_phase()
                else:
                    self._stage_done.emit(current_stage)
            except Exception as exc:
                self.phase_run_finished.emit(False, str(exc))

        Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Stage completion handlers (GUI thread via Qt signal)
    # ------------------------------------------------------------------

    def _on_stage_done(self, stage: int) -> None:
        self._clear_running_ui()
        self._update_toolbar_state("idle")
        if stage == 1:
            self._on_stage1_done()
        elif stage == 2:
            self._on_stage2_done()
        elif stage == 3:
            self._on_stage3_done()
        elif stage == 4:
            self._on_stage4_done()

    def _on_stage1_done(self) -> None:
        # Stage 1 exists to capture the cold landing frequency, so completing
        # the steps without one is a failure, not a success. Reporting it as
        # Done is what persisted records that unlock stage 2 and then fail on it.
        if self._df_cold_hz is None:
            self._set_stage_done_ui(1, success=False)
            self.view.log_message(
                "✗ Stage 1 finished without recording a cold landing "
                "frequency — check the cavity detune readback and re-run."
            )
            return

        saved = self._save_stage_to_history(
            _STAGE_COLD_LANDING,
            {"df_cold_hz": self._df_cold_hz},
        )
        self._persist_df_cold_to_record()
        self._set_stage_done_ui(1, success=saved)
        if not saved:
            return

        self._enable_stage_btn(2)
        self._update_partial_results()
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("Stage 1 Done")
        self._log_signal.emit(
            "Stage 1 complete. Review cold landing, then run Stage 2."
        )

    def _on_stage2_done(self) -> None:
        signed_hz = self.phase._hz_per_microstep or 0.0

        probe_steps = float(getattr(self.phase.limits, "probe_steps", 0))
        if probe_steps > 0 and abs(signed_hz) > 0:
            self._hz_est_total_steps = probe_steps
            self._hz_est_total_hz = abs(signed_hz) * probe_steps

        self._pending_stage2_data = {
            "hz_per_microstep": signed_hz,
        }

        self.hz_per_step_updated.emit(signed_hz)
        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None:
            spinbox.setEnabled(True)

        if (
            hasattr(self.view, "show_probe_fit")
            and self._probe_s_d0 is not None
            and self._probe_s_d1 is not None
            and self._probe_d0_hz is not None
            and self._probe_d1_hz is not None
        ):
            self.view.show_probe_fit(
                self._probe_s_d0,
                self._probe_d0_hz,
                self._probe_s_d1,
                self._probe_d1_hz,
            )

        status_lbl = getattr(self.view, "stage2_status_label", None)
        if status_lbl is not None:
            status_lbl.setText("⟳ Confirm fit")
            status_lbl.setStyleSheet(
                "QLabel { color: #f59e0b; font-weight: bold; }"
            )
        confirm_probe_btn = getattr(self.view, "confirm_probe_fit_button", None)
        if confirm_probe_btn is not None:
            confirm_probe_btn.setEnabled(True)

        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("Stage 2 — Awaiting Confirm")
        # Not idle — the run is blocked on the operator confirming the fit.
        self._update_toolbar_state("awaiting")
        self._log_signal.emit(
            f"Stage 2 complete: {abs(signed_hz):.4f} Hz/step measured. "
            "Review the fit on the plot, adjust Hz/step if needed, "
            "then click 'Confirm Fit'."
        )

    def confirm_probe_fit(self) -> None:
        """Save Stage 2 result after the operator reviews and confirms the fit."""
        if not self._pending_stage2_data:
            self.view.show_error("No probe data to confirm. Run Stage 2 first.")
            return

        # Use the current (possibly operator-edited) spinbox value as the confirmed Hz/step.
        current_hz = self._get_hz_per_step_from_view()
        if current_hz is not None and current_hz != 0:
            self._pending_stage2_data["hz_per_microstep"] = current_hz
            if self.phase is not None:
                self.phase._hz_per_microstep = current_hz

        saved = self._save_stage_to_history(
            _STAGE_PROBE_DIRECTION,
            self._pending_stage2_data,
        )
        self._set_stage_done_ui(2, success=saved)
        if not saved:
            return

        signed_hz = self._pending_stage2_data.get("hz_per_microstep", 0.0)
        self._probe_stage_confirmed = True
        self._update_partial_results()

        confirm_probe_btn = getattr(self.view, "confirm_probe_fit_button", None)
        if confirm_probe_btn is not None:
            confirm_probe_btn.setEnabled(False)

        # Projection belongs to Stage 3; don't draw it here so the Stage 2
        # probe-fit plot stays at the narrow probe-step scale.

        self.push_hz_per_step_to_scale()
        self._enable_stage_btn(3)
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("Stage 2 Done")
        self._log_signal.emit(
            f"Stage 2 confirmed: {abs(signed_hz):.4f} Hz/step saved. "
            "Run Stage 3 to tune to resonance."
        )

    def _on_stage3_done(self) -> None:
        saved = self._save_stage_to_history(
            _STAGE_TUNE_TO_RESONANCE,
            {
                "net_steps": self._net_steps,
                "cold_landing_steps": self._tune_step_data.get(
                    "cold_landing_steps"
                ),
                "steps_to_resonance": self._tune_step_data.get("total_steps"),
            },
        )
        self._set_stage_done_ui(3, success=saved)
        if not saved:
            return

        self._enable_stage_btn(4)
        self._update_partial_results()
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("AT RESONANCE")
        self._log_signal.emit(
            f"Stage 3 complete: at resonance. Net steps: {self._net_steps:+d}. "
            "Run Stage 4 to measure pi modes."
        )

    def _on_stage4_done(self) -> None:
        saved = self._save_stage_to_history(_STAGE_PI_MODES, self._pi_mode_data)
        self._set_stage_done_ui(4, success=saved)
        if not saved:
            return

        # Stage 4 (FSCAN) is repeatable — re-enable so the operator can re-scan
        # if the first result looked noisy or failed partway through.
        self._enable_stage_btn(4)

        self._update_partial_results()
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("PI MODES DONE")
        hz_8 = self._pi_mode_data.get("mode_8pi_9_hz")
        hz_7 = self._pi_mode_data.get("mode_7pi_9_hz")

        def _fmt(v):
            return f"{v:.0f} Hz" if v is not None else "N/A"

        self._log_signal.emit(
            f"Stage 4 complete: 8π/9={_fmt(hz_8)}, 7π/9={_fmt(hz_7)}. Saving results..."
        )
        # Auto-save: no confirmation step needed — Stage 4 is repeatable if
        # the operator wants to re-scan with different results.
        self.confirm_and_save()

    def _persist_df_cold_to_record(self) -> None:
        """Write the cold-landing detune onto the record and save it.

        measurement_history alone is not enough: the phase gates stage 2 on
        FrequencyTuningPhase._check_df_cold_recorded(), which can only see the
        record (phase_history checkpoints are in-memory and do not survive a
        restart). Without this, quitting between stage 1 and stage 2 left the
        frequency recorded in history but invisible to the phase, and stage 2
        failed with "Cold landing frequency was not recorded".
        """
        if self._df_cold_hz is None:
            return
        record = self.session.get_active_record()
        if record is None:
            return
        existing = getattr(record.frequency_tuning, "df_cold_hz", None)
        if existing == self._df_cold_hz:
            return  # already durable; don't bump the record version for nothing
        try:
            data = record.frequency_tuning or FrequencyTuningData()
            data.df_cold_hz = self._df_cold_hz
            record.frequency_tuning = data
            self.session.save_active_record()
        except Exception as exc:
            self._log_signal.emit(
                f"Warning: could not persist cold landing to record: {exc}"
            )

    def _update_partial_results(self) -> None:
        """Populate Stored Data panel with whatever fields are known so far."""
        partial = FrequencyTuningData(
            df_cold_hz=self._df_cold_hz,
            hz_per_microstep=self._pending_stage2_data.get("hz_per_microstep"),
            cold_landing_steps=self._tune_step_data.get("cold_landing_steps"),
            steps_to_resonance=self._tune_step_data.get("total_steps"),
            mode_8pi_9_frequency=self._pi_mode_data.get("mode_8pi_9_hz"),
            mode_7pi_9_frequency=self._pi_mode_data.get("mode_7pi_9_hz"),
        )
        if hasattr(self.view, "_update_local_results"):
            self.view._update_local_results(partial)

    def _on_hz_chunk_update(self, steps: int, hz_delta: float) -> None:
        """Called from background thread after each tuning move."""
        if steps > 0 and hz_delta > 0:
            self._hz_est_total_steps += steps
            self._hz_est_total_hz += hz_delta
            new_est = self._hz_est_total_hz / self._hz_est_total_steps
            self.hz_per_step_updated.emit(new_est)

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _execute_single_step(self, step_name: str) -> bool:
        while self._paused:
            time.sleep(0.1)
            if self.context and self.context.is_abort_requested():
                return False

        if self.context and self.context.is_abort_requested():
            return False

        if self.context and self.context.progress_callback:
            stage_offset = _STAGE_STEP_OFFSETS.get(self._current_stage, 0)
            idx = (
                self._steps.index(step_name) if step_name in self._steps else 0
            )
            overall = int(
                (stage_offset + idx) / _TOTAL_COMMISSIONING_STEPS * 100
            )
            self.context.progress_callback(step_name, overall)

        return self._execute_step_with_retries(step_name, max_retries=3)

    def _execute_step_with_retries(
        self, step_name: str, max_retries: int
    ) -> bool:
        retry_count = 0
        while retry_count < max_retries:
            try:
                result = self.phase.execute_step(step_name)
                self._create_step_checkpoint(step_name, result)

                if result.result in (PhaseResult.SUCCESS, PhaseResult.SKIP):
                    self._resolve_log_signal.emit(
                        step_name, f"✓ {_step_label(step_name)}", "success"
                    )
                    self._on_step_succeeded(step_name, result.data or {})
                    return True

                if result.result == PhaseResult.RETRY:
                    retry_count += 1
                    if retry_count < max_retries:
                        delay = max(0.0, float(result.retry_delay_seconds))
                        self._log_signal.emit(
                            f"Retrying {retry_count}/{max_retries} in {delay:.1f}s: "
                            f"{result.message}"
                        )
                        time.sleep(delay)
                        continue
                    self._log_signal.emit(
                        f"Failed after {max_retries} retries: {result.message}"
                    )
                    return False

                self._resolve_log_signal.emit(
                    step_name,
                    f"✗ {_step_label(step_name)}: {result.message}",
                    "error",
                )
                return False

            except Exception as exc:
                retry_count += 1
                if retry_count < max_retries:
                    self._log_signal.emit(
                        f"Exception on retry {retry_count}: {exc}"
                    )
                    continue
                self._log_signal.emit(
                    f"Exception after {max_retries} retries: {exc}"
                )
                return False

        return False

    def _on_step_succeeded(self, step_name: str, data: dict) -> None:
        if step_name == "record_cold_landing":
            self._df_cold_hz = data.get("df_cold_hz")

        elif step_name == "probe_stepper_direction":
            self._probe_d0_hz = data.get("d0_hz")
            self._probe_d1_hz = data.get("d1_hz")
            self._probe_s_d0 = data.get("s_d0", 0)
            self._probe_s_d1 = data.get("s_d1", data.get("probe_steps", 0))

        elif step_name == "tune_to_resonance":
            cold_landing_steps = data.get("cold_landing_steps", 0)
            self._net_steps = (
                -cold_landing_steps if cold_landing_steps is not None else 0
            )
            self._tune_step_data = dict(data)

        elif step_name == "measure_pi_modes":
            self._pi_mode_data = dict(data)

    def _save_stage_to_history(self, step: str, data: dict) -> bool:
        """Persist a stage completion to measurement_history.

        Returns True on success so callers can gate UI updates on a confirmed save.
        """
        try:
            return self.session.add_measurement_to_history(
                CommissioningPhase.FREQUENCY_TUNING,
                {"step": step, **data},
                self._get_operator(),
                phase_instance_id=self._active_phase_instance_id,
            )
        except Exception as exc:
            self._log_signal.emit(
                f"Warning: could not save stage history: {exc}"
            )
            return False

    def _create_step_checkpoint(self, step_name: str, result) -> None:
        measurements = dict(result.data or {})
        if self.context.phase_instance_id is not None:
            measurements.setdefault(
                "phase_instance_id", self.context.phase_instance_id
            )

        checkpoint = PhaseCheckpoint(
            phase=self.phase.phase_type,
            timestamp=datetime.now(),
            operator=self.context.operator,
            step_name=step_name,
            success=result.result in (PhaseResult.SUCCESS, PhaseResult.SKIP),
            notes=result.message,
            measurements=measurements,
        )
        self.context.record.phase_history.append(checkpoint)

    def _finalize_background_phase(self) -> None:
        try:
            self.phase.finalize_phase()
            self.phase._mark_phase_completed()
            self.phase_run_finished.emit(True, "")
        except Exception as exc:
            self.phase._handle_exception(exc)
            self.phase_run_finished.emit(False, str(exc))

    def _check_pause_and_abort(self) -> bool:
        while self._paused:
            time.sleep(0.1)
            if self.context and self.context.is_abort_requested():
                self.phase_run_finished.emit(False, "Aborted")
                return False

        if self.context and self.context.is_abort_requested():
            self.phase_run_finished.emit(False, "Aborted")
            return False

        return True

    # ------------------------------------------------------------------
    # Phase completion
    # ------------------------------------------------------------------

    def _on_phase_run_finished(self, success: bool, error_msg: str) -> None:
        if success:
            self.on_phase_completed()
        else:
            self.on_phase_failed(error_msg or "Phase execution failed")

    def _find_open_phase_instance_id(self) -> int | None:
        """Return the still-running frequency tuning instance for this record.

        Only Stage 1 opens a phase instance, so a session that resumes an
        existing record has no _active_phase_instance_id — finishing the phase
        would then leave the instance stuck at in_progress. The tab row is
        derived from instance status, not from record.set_phase_status, so a
        stuck instance means the tab keeps reading "In progress" after Stage 4.
        """
        try:
            instances = self.session.get_active_phase_instances()
        except Exception:
            return None
        for instance in reversed(instances or []):
            if (
                instance.get("phase")
                == CommissioningPhase.FREQUENCY_TUNING.value
                and instance.get("status") == "in_progress"
            ):
                return instance.get("id")
        return None

    def on_phase_completed(self) -> None:
        self._paused = False
        self._clear_running_ui()
        self.view.log_message("Frequency tuning completed and saved")
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("COMPLETED")
        if hasattr(self.view, "local_progress_bar"):
            self.view.local_progress_bar.setValue(100)
        self._update_toolbar_state("complete")

        try:
            if self.context and self.context.record.frequency_tuning:
                instance_id = (
                    self._active_phase_instance_id
                    or self._find_open_phase_instance_id()
                )
                if instance_id is not None:
                    self.session.complete_active_phase_instance(
                        phase_instance_id=instance_id,
                        phase=CommissioningPhase.FREQUENCY_TUNING,
                        artifact_payload=self.context.record.frequency_tuning.to_dict(),
                    )

                if self.session.save_active_record():
                    self.view.log_message(
                        f"Results saved (ID: {self.session.get_active_record_id()})"
                    )
                    self.phase_completed.emit(self.session.get_active_record())
                else:
                    self.view.log_message("Warning: failed to save to database")

                self.view._update_local_results(
                    self.context.record.frequency_tuning
                )
                self.view._update_stored_readout(
                    self.context.record.frequency_tuning
                )
        except Exception as exc:
            import traceback

            self.view.log_message(f"Warning: failed to save results: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
        finally:
            self._active_phase_instance_id = None

    def on_phase_failed(self, error_msg: str) -> None:
        self._paused = False
        self._clear_running_ui()
        self.view.log_message(f"✗ Stage failed — {error_msg}")
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("FAILED")
        self._update_toolbar_state("error")

        if self._current_stage in (1, 2, 3):
            self._set_stage_done_ui(self._current_stage, success=False)

        try:
            if self.phase:
                self.phase.finalize_phase()
            if self.session.save_active_record():
                self.view.log_message("Partial results saved")
            if self._active_phase_instance_id is not None:
                snapshot = None
                if self.context and self.context.record.frequency_tuning:
                    snapshot = self.context.record.frequency_tuning.to_dict()
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.FREQUENCY_TUNING,
                    error_message=error_msg,
                    artifact_payload=snapshot,
                )
        except Exception as exc:
            import traceback

            self.view.log_message(
                f"Warning: failed to save partial results: {exc}"
            )
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
        finally:
            self._active_phase_instance_id = None

        _check_state_failures = {
            f"Step failed: {_step_label('check_state_for_stage_2')}",
            f"Step failed: {_step_label('check_state_for_stage_3')}",
            f"Step failed: {_step_label('check_state_for_stage_4')}",
        }
        if error_msg not in _check_state_failures:
            self.view.show_error(f"Frequency tuning failed: {error_msg}")

    # ------------------------------------------------------------------
    # Pause / Abort
    # ------------------------------------------------------------------

    def on_abort(self) -> None:
        if self.context:
            self.context.request_abort()
            self.view.log_message("Abort requested...")
            abort_btn = getattr(self.view, "abort_button", None)
            if abort_btn:
                abort_btn.setEnabled(False)
        if self._cavity is not None:
            try:
                self._cavity.stepper_tuner.abort_flag = True
            except Exception:
                pass

    def on_pause_test(self) -> None:
        pause_btn = getattr(self.view, "pause_button", None)
        if self._paused:
            self._paused = False
            self.view.log_message("Test resumed...")
            if pause_btn:
                pause_btn.setText("⏸ Pause")
            self._update_toolbar_state("running")
        else:
            self._paused = True
            self.view.log_message("Test paused...")
            if pause_btn:
                pause_btn.setText("▶ Resume")
            self._update_toolbar_state("paused")

    # ------------------------------------------------------------------
    # Manual stepper controls
    # ------------------------------------------------------------------

    def get_live_detune(self) -> float | None:
        if self._cavity is None:
            return None
        try:
            return float(self._cavity.detune_chirp)
        except Exception:
            return None

    def get_live_steps(self) -> int | None:
        if self._cavity is None:
            return None
        try:
            from sc_linac_physics.utils.epics import PV

            if self._step_signed_pv_obj is None:
                self._step_signed_pv_obj = PV(
                    self._cavity.stepper_tuner.step_signed_pv
                )
            val = self._step_signed_pv_obj.get()
            return int(val) if val is not None else None
        except Exception:
            return None

    def get_signed_hz_per_step(self) -> float | None:
        """Return signed Hz/step from the active phase (sign encodes motor direction)."""
        if self.phase is not None:
            return getattr(self.phase, "_hz_per_microstep", None)
        return None

    def get_probe_anchor(self) -> tuple[int, float, int] | None:
        """Return (s_d0, d0_hz, s_d1) anchor points for recalculating the probe fit.

        Returns None if probe data is not yet available.
        """
        if (
            self._probe_s_d0 is not None
            and self._probe_d0_hz is not None
            and self._probe_s_d1 is not None
        ):
            return self._probe_s_d0, self._probe_d0_hz, self._probe_s_d1
        return None

    def push_hz_per_step_to_scale(self) -> None:
        """Persist the current Hz/microstep estimate (signed).

        STEP:SCALE is a derived, read-only calc-record output
        (SCALE = SCALE_CALC.B / 256), so we write the Hz-per-full-step field
        via StepperTuner.set_hz_per_microstep and let the IOC recompute SCALE.
        """
        if self._cavity is None:
            self.view.log_message("No cavity selected — cannot push to SCALE.")
            return

        signed_hz = self._get_hz_per_step_from_view()
        if not signed_hz or signed_hz == 0:
            self.view.log_message("No Hz/step value to push.")
            return

        def _do_push() -> None:
            try:
                self._cavity.stepper_tuner.set_hz_per_microstep(signed_hz)
                self._log_signal.emit(
                    f"Pushed {signed_hz:.4f} Hz/microstep "
                    "(via SCALE_CALC.B; IOC recomputes STEP:SCALE)."
                )
            except Exception as exc:
                self._log_signal.emit(f"Failed to push Hz/microstep: {exc}")

        Thread(target=_do_push, daemon=True).start()

    def push_detune_to_df_cold(self) -> None:
        """Write the current live detune reading to the DF_COLD PV."""
        if self._cavity is None:
            self.view.log_message(
                "No cavity selected — cannot push to DF_COLD."
            )
            return
        detune = self.get_live_detune()
        if detune is None:
            self.view.log_message("Could not read current detune.")
            return

        def _do_push() -> None:
            try:
                from sc_linac_physics.utils.epics import PV

                pv = PV(self._cavity.pv_addr("DF_COLD"))
                pv.put(detune)
                self._log_signal.emit(f"Pushed {detune:.0f} Hz to DF_COLD.")
            except Exception as exc:
                self._log_signal.emit(f"Failed to push to DF_COLD: {exc}")

        Thread(target=_do_push, daemon=True).start()

    def on_move_left(self) -> None:
        if self._cavity is None:
            self.view.log_message("No cavity selected — cannot move stepper.")
            return
        Thread(
            target=self._do_stepper_move,
            args=(self._cavity, False),
            daemon=True,
        ).start()

    def on_move_right(self) -> None:
        if self._cavity is None:
            self.view.log_message("No cavity selected — cannot move stepper.")
            return
        Thread(
            target=self._do_stepper_move, args=(self._cavity, True), daemon=True
        ).start()

    def _do_stepper_move(self, cavity, positive: bool) -> None:
        try:
            stepper = cavity.stepper_tuner
            if positive:
                stepper.move_positive()
                self._log_signal.emit("Stepper: issuing move right (positive)")
            else:
                stepper.move_negative()
                self._log_signal.emit("Stepper: issuing move left (negative)")
        except Exception as exc:
            self._log_signal.emit(f"Stepper move error: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_operator(self) -> str:
        if hasattr(self.view, "get_current_operator"):
            return self.view.get_current_operator() or ""
        return ""

    def _get_hz_per_step_from_view(self) -> float | None:
        if hasattr(self.view, "get_current_hz_per_step"):
            return self.view.get_current_hz_per_step()
        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None:
            return float(spinbox.value())
        return None

    def _update_toolbar_state(self, state: str) -> None:
        if hasattr(self.view, "ui") and hasattr(
            self.view.ui, "update_toolbar_state"
        ):
            self.view.ui.update_toolbar_state(state)

    # ------------------------------------------------------------------
    # Record restore
    # ------------------------------------------------------------------

    def restore_from_record(self, record) -> None:
        """Restore stage UI state from an already-saved record."""
        if record is None:
            return

        self._reset_all_stages()

        history = self._load_stage_history(record)
        stage1 = history.get(_STAGE_COLD_LANDING)
        stage2 = history.get(_STAGE_PROBE_DIRECTION)
        stage3 = history.get(_STAGE_TUNE_TO_RESONANCE)
        stage4 = history.get(_STAGE_PI_MODES)

        if stage1:
            self._restore_stage1(stage1, record, has_probe=stage2 is not None)
        if stage2:
            self._restore_stage2(stage2, has_tune=stage3 is not None)
        if stage3:
            self._restore_stage3(stage3)
            if stage4:
                self._restore_stage4(stage4)
            else:
                self._enable_stage_btn(4)

    def _load_stage_history(self, record) -> dict[str, dict]:
        """Return the latest measurement_history payload for each stage step.

        Falls back to synthesizing from the FrequencyTuningData blob for
        records created before stage history was persisted.
        """
        rows = self.session.get_measurement_history(
            CommissioningPhase.FREQUENCY_TUNING
        )
        latest: dict[str, dict] = {}
        _known_steps = {
            _STAGE_COLD_LANDING,
            _STAGE_PROBE_DIRECTION,
            _STAGE_TUNE_TO_RESONANCE,
            _STAGE_PI_MODES,
        }
        for row in rows:  # already DESC by timestamp
            data = row.get("measurement_data", {})
            step = data.get("step")
            if step and step in _known_steps and step not in latest:
                latest[step] = data

        if not latest:
            latest = self._synthesize_history_from_blob(record)

        return latest

    def _synthesize_history_from_blob(self, record) -> dict[str, dict]:
        """Build a stage-history dict from the FrequencyTuningData blob.

        Used as a fallback for records that predate per-stage history rows.
        """
        ft = record.frequency_tuning if record else None
        if ft is None:
            return {}

        result: dict[str, dict] = {}
        if ft.df_cold_hz is not None:
            result[_STAGE_COLD_LANDING] = {
                "step": _STAGE_COLD_LANDING,
                "df_cold_hz": ft.df_cold_hz,
            }
        if ft.hz_per_microstep is not None:
            result[_STAGE_PROBE_DIRECTION] = {
                "step": _STAGE_PROBE_DIRECTION,
                "hz_per_microstep": ft.hz_per_microstep,
            }
        if ft.steps_to_resonance is not None:
            result[_STAGE_TUNE_TO_RESONANCE] = {
                "step": _STAGE_TUNE_TO_RESONANCE,
                "cold_landing_steps": ft.cold_landing_steps,
                "steps_to_resonance": ft.steps_to_resonance,
                "net_steps": -(ft.cold_landing_steps or 0),
            }
        return result

    def _reset_all_stages(self) -> None:
        """Return all stage widgets to their initial 'Not started' state."""
        for stage in (1, 2, 3, 4):
            self._set_stage_status_not_started(stage)
            self._show_stage_description(stage, visible=True)
            btn = getattr(self.view, f"stage{stage}_run_btn", None)
            if btn is not None:
                btn.setEnabled(stage == 1)

        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None:
            spinbox.blockSignals(True)
            spinbox.setValue(0.0)
            spinbox.blockSignals(False)
            spinbox.setEnabled(False)

        confirm_probe_btn = getattr(self.view, "confirm_probe_fit_button", None)
        if confirm_probe_btn is not None:
            confirm_probe_btn.setEnabled(False)

        self.phase = None
        self.context = None
        self._phase_started = False
        self._df_cold_hz = None
        self._hz_est_total_steps = 0.0
        self._hz_est_total_hz = 0.0
        self._net_steps = 0
        self._tune_step_data = {}
        self._probe_stage_confirmed = False
        self._pending_stage2_data = {}
        self._probe_s_d0 = None
        self._probe_s_d1 = None
        self._probe_d0_hz = None
        self._probe_d1_hz = None
        self._pi_mode_data = {}

        if hasattr(self.view, "reset_plot"):
            self.view.reset_plot()
        if hasattr(self.view, "clear_results"):
            self.view.clear_results()
        self._update_toolbar_state("idle")

    def _restore_stage1(self, data: dict, record, has_probe: bool) -> None:
        # The stage-1 history row can exist while carrying a null df_cold_hz,
        # so the row's presence alone is not proof the cold landing was
        # recorded. Fall back to the record blob, and if the frequency is
        # genuinely absent leave stage 1 runnable rather than marking it Done —
        # otherwise reopening the cavity unlocks stage 2, which then fails
        # immediately with "Cold landing not recorded" and no way forward.
        df_cold_hz = data.get("df_cold_hz")
        if df_cold_hz is None:
            ft = getattr(record, "frequency_tuning", None)
            df_cold_hz = getattr(ft, "df_cold_hz", None) if ft else None

        if df_cold_hz is None:
            self._df_cold_hz = None
            self._set_stage_status_not_started(1)
            self._enable_stage_btn(1)
            self.view.log_message(
                "Stage 1 was recorded without a cold landing frequency — "
                "re-run Stage 1 before probing the stepper."
            )
            return

        self._set_stage_done_ui(1, success=True)
        btn = getattr(self.view, "stage1_run_btn", None)
        if btn is not None:
            btn.setEnabled(False)

        self._df_cold_hz = df_cold_hz
        # Backfill records written before the frequency was persisted onto the
        # record itself. Without this, a record whose cold landing only ever
        # reached measurement_history still fails the phase's stage-2 gate.
        self._persist_df_cold_to_record()
        self._rebuild_phase_context(record)

        if not has_probe:
            self._enable_stage_btn(2)

    def _rebuild_phase_context(self, record) -> None:
        """Reconstruct phase + context from record so stages 2/3 can run."""
        try:
            cm = int(record.cryomodule)
            cav = int(record.cavity_number)
            cavity = self._get_machine_cavity(cm, cav)
            self._cavity = cavity
            self._apply_stepper_pv_mapping(cavity)
            self.context = PhaseContext(
                record=record,
                operator=self._get_operator(),
                parameters={"cavity": cavity},
                phase_instance_id=None,
                run_intent="commissioning",
            )
            self.phase = FrequencyTuningPhase(self.context)
            self.phase.validate_prerequisites()
            self._phase_started = True
        except Exception as exc:
            self.view.log_message(
                f"Note: could not rebuild phase context from record: {exc}"
            )

    def _restore_stage2(self, data: dict, has_tune: bool) -> None:
        self._set_stage_done_ui(2, success=True)

        signed_hz = float(data.get("hz_per_microstep") or 0.0)

        if self.phase is not None and signed_hz:
            self.phase._hz_per_microstep = signed_hz

        if abs(signed_hz) > 0 and self.phase is not None:
            probe_steps = float(getattr(self.phase.limits, "probe_steps", 0))
            if probe_steps > 0:
                self._hz_est_total_steps = probe_steps
                self._hz_est_total_hz = abs(signed_hz) * probe_steps

        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None and signed_hz:
            spinbox.blockSignals(True)
            spinbox.setValue(signed_hz)
            spinbox.blockSignals(False)
            spinbox.setEnabled(True)

        if signed_hz:
            self._probe_stage_confirmed = True
            self.hz_per_step_updated.emit(signed_hz)

        if not has_tune:
            self._enable_stage_btn(3)

    def _restore_stage3(self, data: dict) -> None:
        self._set_stage_done_ui(3, success=True)

        self._net_steps = data.get("net_steps") or -(
            data.get("cold_landing_steps") or 0
        )

        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("AT RESONANCE")

    def _restore_stage4(self, data: dict) -> None:
        self._pi_mode_data = {
            "mode_8pi_9_hz": data.get("mode_8pi_9_hz"),
            "mode_7pi_9_hz": data.get("mode_7pi_9_hz"),
        }
        self._set_stage_done_ui(4, success=True)
        self._enable_stage_btn(4)

        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("PI MODES DONE")

    def _auto_create_record(self) -> bool:
        parent = self.view.parent()
        cryomodule, cavity_number = None, None
        while parent:
            if hasattr(parent, "cryomodule_combo") and hasattr(
                parent, "cavity_combo"
            ):
                try:
                    cryomodule = parent.cryomodule_combo.currentText()
                    cavity_number = str(parent.cavity_combo.currentText())
                except Exception:
                    pass
                break
            parent = parent.parent()

        if not cryomodule or not cavity_number:
            self.view.show_error(
                "Please select a cavity in the header.\n\n"
                "Use the CM and Cavity dropdowns, then try again."
            )
            return False

        try:
            record, record_id, created = self.session.start_new_record(
                cryomodule=cryomodule, cavity_number=cavity_number
            )
            status = "Created" if created else "Loaded"
            self.view.log_message(
                f"✓ {status} record ID: {record_id} for CM{cryomodule} Cav{cavity_number}"
            )
            self.view._notify_parent_of_record_update(record, "Record created")
            self.update_pv_addresses()
            return True
        except Exception as exc:
            import traceback

            self.view.show_error(f"Failed to create record:\n\n{exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            return False
