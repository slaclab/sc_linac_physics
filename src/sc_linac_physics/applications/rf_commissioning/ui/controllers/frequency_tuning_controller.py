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
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (
    apply_pv_mapping,
    format_pv_update_message,
    resolve_cavity_selection,
)
from sc_linac_physics.utils.sc_linac.linac import Machine

_STAGE1_STEPS = ["verify_initial_state", "record_cold_landing"]
_STAGE2_STEPS = ["probe_stepper_direction"]
_STAGE3_STEPS = ["apply_hz_per_step", "tune_to_resonance"]
_STAGE3_FINALIZE_STEPS = ["record_results"]


class FrequencyTuningController(QObject):
    """Owns phase execution and plot wiring for the Frequency Tuning display."""

    phase_completed = pyqtSignal(object)
    phase_run_finished = pyqtSignal(bool, str)
    _log_signal = pyqtSignal(str)
    hz_per_step_updated = pyqtSignal(float)
    _stage_done = pyqtSignal(int)  # 1, 2, 3, or 4 (=finalize)

    def __init__(self, view, session: CommissioningSession) -> None:
        super().__init__()
        self.view = view
        self.session = session
        if hasattr(self.view, "log_message"):
            self._log_signal.connect(self.view.log_message)

        self.context: PhaseContext | None = None
        self.phase: FrequencyTuningPhase | None = None
        self.machine: Machine | None = None
        self._cavity = None

        self._paused = False
        self._steps: list[str] = []
        self._finalize_after_run: bool = False
        self._phase_started: bool = False
        self._initial_detune_hz: float | None = None
        self._active_phase_instance_id: int | None = None

        self._current_stage: int = 0
        self._hz_est_total_steps: float = 0.0
        self._hz_est_total_hz: float = 0.0
        self._net_steps: int = 0

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
            self._apply_stepper_pv_mapping(cavity)
            self.view.log_message(
                format_pv_update_message(cryomodule, cavity_number, cm, cav)
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _apply_stepper_pv_mapping(self, cavity) -> None:
        stepper = cavity.stepper_tuner
        pv_map = {}
        for widget_name, pv_addr in (
            ("steps_spinbox", stepper.step_des_pv),
            ("speed_spinbox", stepper.speed_pv),
            ("max_steps_spinbox", stepper.max_steps_pv),
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

        target = self._resolve_target()
        if target is None:
            return

        cavity_name, cm, cav = target
        self.view.log_message(
            f"Stage 1: Setup & Cold Landing for {cavity_name}"
        )
        self.view.clear_results()
        self.view.reset_plot()
        self._initial_detune_hz = None
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

            self.view.show_error(f"Failed to start Stage 1: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

    def run_stage_2(self) -> None:
        """Probe stepper direction to measure Hz/step."""
        if not self.phase or not self.context:
            self.view.show_error("Run Stage 1 first.")
            return

        self.view.log_message("Stage 2: Probing stepper direction...")
        self._current_stage = 2
        self._steps = list(_STAGE2_STEPS)
        self._finalize_after_run = False
        self._set_stage_running_ui(2)
        QTimer.singleShot(100, self._run_phase_in_background)

    def run_stage_3(self) -> None:
        """Apply Hz/step to SCALE PV and tune to resonance."""
        if not self.phase or not self.context:
            self.view.show_error("Run Stage 2 first.")
            return

        hz = self._get_hz_per_step_from_view()
        if hz and hz > 0 and self.phase._signed_hz_per_microstep is not None:
            sign = 1.0 if self.phase._signed_hz_per_microstep >= 0 else -1.0
            self.phase._hz_per_microstep = hz
            self.phase._signed_hz_per_microstep = hz * sign

        self.view.log_message("Stage 3: Tuning to resonance...")
        self._current_stage = 3
        self._steps = list(_STAGE3_STEPS)
        self._finalize_after_run = False
        self._set_stage_running_ui(3)
        QTimer.singleShot(100, self._run_phase_in_background)

    def confirm_and_save(self) -> None:
        """Finalize results and save to database."""
        if not self.phase or not self.context:
            self.view.show_error("Complete Stage 3 first.")
            return

        self.view.log_message("Confirming and saving results...")
        self._current_stage = 4
        self._steps = list(_STAGE3_FINALIZE_STEPS)
        self._finalize_after_run = True
        self._set_stage_running_ui(None)
        QTimer.singleShot(100, self._run_phase_in_background)

    def on_confirm_and_tune(self) -> None:
        """Backward-compat alias → run_stage_3."""
        self.run_stage_3()

    # ------------------------------------------------------------------
    # Phase setup
    # ------------------------------------------------------------------

    def _resolve_target(self) -> tuple[str, int, int] | None:
        if (
            not self.session.has_active_record()
            and not self._auto_create_record()
        ):
            return None

        cavity_info = self.view.get_current_cavity()
        if not cavity_info:
            self.view.show_error(
                "Unable to determine cavity. Select a cavity and try again."
            )
            return None

        cavity_name, cryomodule = cavity_info
        try:
            parts = cavity_name.split("_")
            cav = int(parts[2].replace("CAV", "")) if len(parts) >= 3 else 1
            cm = int(cryomodule)
        except (ValueError, IndexError):
            self.view.show_error(f"Invalid cavity name format: {cavity_name}")
            return None

        return cavity_name, cm, cav

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

    def _set_stage_running_ui(self, stage: int | None) -> None:
        if stage is not None:
            btn = getattr(self.view, f"stage{stage}_run_btn", None)
            if btn is not None:
                btn.setEnabled(False)
            status_lbl = getattr(self.view, f"stage{stage}_status_label", None)
            if status_lbl is not None:
                status_lbl.setText("⟳ Running...")
                status_lbl.setStyleSheet(
                    "QLabel { color: #3b82f6; font-weight: bold; }"
                )

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
        status_lbl = getattr(self.view, f"stage{stage}_status_label", None)
        if status_lbl is not None:
            if success:
                status_lbl.setText("✓ Done")
                status_lbl.setStyleSheet(
                    "QLabel { color: #10b981; font-weight: bold; }"
                )
            else:
                status_lbl.setText("✗ Failed")
                status_lbl.setStyleSheet(
                    "QLabel { color: #dc2626; font-weight: bold; }"
                )
        if not success:
            btn = getattr(self.view, f"stage{stage}_run_btn", None)
            if btn is not None:
                btn.setEnabled(True)

    def _enable_stage_btn(self, stage: int) -> None:
        btn = getattr(self.view, f"stage{stage}_run_btn", None)
        if btn is not None:
            btn.setEnabled(True)

    def _clear_running_ui(self) -> None:
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

    def _run_phase_in_background(self) -> None:
        if not self.context or not self.phase:
            return

        self.context.progress_callback = (
            lambda step, prog: self.view.step_progress_signal.emit(step, prog)
        )
        self.context.parameters["tuning_update_callback"] = (
            lambda steps, detune: self.view.tuning_data_signal.emit(
                time.time(), detune
            )
        )
        self.context.parameters["hz_per_step_update_callback"] = (
            self._on_hz_chunk_update
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
                            False, f"Step failed: {step_name}"
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

    def _on_stage1_done(self) -> None:
        self._set_stage_done_ui(1, success=True)
        self._persist_partial_frequency_tuning(
            initial_detune_hz=self._initial_detune_hz
        )

        lbl = getattr(self.view, "cold_landing_label", None)
        if lbl is not None and self._initial_detune_hz is not None:
            lbl.setText(f"{self._initial_detune_hz:.0f} Hz")

        self._enable_stage_btn(2)
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("Stage 1 Done")
        self._log_signal.emit(
            "Stage 1 complete. Review cold landing, then run Stage 2."
        )

    def _on_stage2_done(self) -> None:
        hz_per_step = self.phase._hz_per_microstep or 0.0
        positive = (self.phase._signed_hz_per_microstep or 0.0) >= 0
        self._set_stage_done_ui(2, success=True)

        probe_steps = float(getattr(self.phase.limits, "probe_steps", 0))
        if probe_steps > 0 and hz_per_step > 0:
            self._hz_est_total_steps = probe_steps
            self._hz_est_total_hz = hz_per_step * probe_steps

        self._persist_partial_frequency_tuning(
            hz_per_microstep=hz_per_step,
            positive_step_increases_frequency=positive,
        )
        self.hz_per_step_updated.emit(hz_per_step)

        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None:
            spinbox.setEnabled(True)

        if self._initial_detune_hz is not None:
            initial = self._initial_detune_hz
            hps = hz_per_step
            QTimer.singleShot(0, lambda: self.view.set_projection(initial, hps))

        self._enable_stage_btn(3)
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("Stage 2 Done")
        self._log_signal.emit(
            f"Stage 2 complete: {hz_per_step:.4f} Hz/step measured. "
            "Review/edit Hz/step if needed, then run Stage 3."
        )

    def _on_stage3_done(self) -> None:
        self._set_stage_done_ui(3, success=True)

        net_lbl = getattr(self.view, "net_steps_label", None)
        if net_lbl is not None:
            net_lbl.setText(f"{self._net_steps:+d} steps")

        confirm_btn = getattr(self.view, "confirm_save_button", None)
        if confirm_btn is not None:
            confirm_btn.setEnabled(True)

        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("AT RESONANCE")
        self._log_signal.emit(
            f"Stage 3 complete: at resonance. Net steps: {self._net_steps:+d}. "
            "Click 'Confirm & Save' to store results."
        )

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
            idx = (
                self._steps.index(step_name) if step_name in self._steps else 0
            )
            self.context.progress_callback(
                step_name, int((idx / len(self._steps)) * 100)
            )

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
                    self._log_signal.emit(f"✓ {step_name}")
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

                self._log_signal.emit(f"✗ {step_name}: {result.message}")
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
            self._initial_detune_hz = data.get("initial_detune_hz")

        elif step_name == "probe_stepper_direction":
            hz_per_step = data.get("hz_per_microstep")
            if hz_per_step and self._initial_detune_hz is not None:
                initial = self._initial_detune_hz
                hps = hz_per_step
                QTimer.singleShot(
                    0, lambda: self.view.set_projection(initial, hps)
                )

        elif step_name == "tune_to_resonance":
            cold_landing_steps = data.get("cold_landing_steps", 0)
            self._net_steps = (
                -cold_landing_steps if cold_landing_steps is not None else 0
            )

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

    def on_phase_completed(self) -> None:
        self._paused = False
        self._clear_running_ui()
        self.view.log_message("Frequency tuning completed and saved")
        if hasattr(self.view, "local_phase_status"):
            self.view.local_phase_status.setText("COMPLETED")
        if hasattr(self.view, "local_progress_bar"):
            self.view.local_progress_bar.setValue(100)
        self._update_toolbar_state("complete")

        confirm_btn = getattr(self.view, "confirm_save_button", None)
        if confirm_btn is not None:
            confirm_btn.setEnabled(False)

        try:
            if self.context and self.context.record.frequency_tuning:
                if self._active_phase_instance_id is not None:
                    self.session.complete_active_phase_instance(
                        phase_instance_id=self._active_phase_instance_id,
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
        self.view.log_message(f"Frequency tuning failed: {error_msg}")
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

    def _persist_partial_frequency_tuning(self, **kwargs) -> None:
        """Write partial FrequencyTuningData fields to the active record and save.

        Creates the FrequencyTuningData object if it doesn't exist yet so that
        cold landing and probe results survive an application restart even before
        the operator reaches 'Confirm & Save'.
        """
        record = self.session.get_active_record()
        if record is None:
            return
        if record.frequency_tuning is None:
            record.frequency_tuning = FrequencyTuningData()
        for key, value in kwargs.items():
            if value is not None:
                setattr(record.frequency_tuning, key, value)
        try:
            if self.session.save_active_record():
                self.view.log_message("Partial results saved to database")
        except Exception as exc:
            self.view.log_message(
                f"Warning: could not save partial results: {exc}"
            )

    def _update_toolbar_state(self, state: str) -> None:
        if hasattr(self.view, "ui") and hasattr(
            self.view.ui, "update_toolbar_state"
        ):
            self.view.ui.update_toolbar_state(state)

    # ------------------------------------------------------------------
    # Record restore
    # ------------------------------------------------------------------

    def restore_from_record(self, record) -> None:
        """Restore stage UI state from an already-saved record.

        Cold landing is a one-time measurement taken at initial cooldown.
        If it already exists in the record, Stage 1 must be locked so the
        operator cannot overwrite it.  Stage completion is inferred from the
        persisted FrequencyTuningData fields (phase_history is not persisted).
        """
        if record is None:
            return

        self._reset_all_stages()

        ft = record.frequency_tuning
        cold_done = ft is not None and ft.initial_detune_hz is not None
        probe_done = ft is not None and ft.hz_per_microstep is not None

        if cold_done:
            self._restore_stage1(ft, record, has_probe=probe_done)
        if probe_done:
            # Stage 3 is never auto-restored — cavity may have drifted since
            # the last session, so the operator must always re-run tuning.
            self._restore_stage2(ft, has_tune=False)

    def _reset_all_stages(self) -> None:
        """Return all stage widgets to their initial 'Not started' state."""
        not_started_style = "QLabel { color: #9ca3af; }"
        for stage in (1, 2, 3):
            lbl = getattr(self.view, f"stage{stage}_status_label", None)
            if lbl is not None:
                lbl.setText("Not started")
                lbl.setStyleSheet(not_started_style)
            btn = getattr(self.view, f"stage{stage}_run_btn", None)
            if btn is not None:
                btn.setEnabled(stage == 1)

        for widget_name, text in (
            ("cold_landing_label", "—"),
            ("net_steps_label", "—"),
        ):
            w = getattr(self.view, widget_name, None)
            if w is not None:
                w.setText(text)

        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None:
            spinbox.blockSignals(True)
            spinbox.setValue(0.0)
            spinbox.blockSignals(False)
            spinbox.setEnabled(False)

        confirm_btn = getattr(self.view, "confirm_save_button", None)
        if confirm_btn is not None:
            confirm_btn.setEnabled(False)

        self.phase = None
        self.context = None
        self._phase_started = False
        self._initial_detune_hz = None
        self._hz_est_total_steps = 0.0
        self._hz_est_total_hz = 0.0
        self._net_steps = 0

        if hasattr(self.view, "reset_plot"):
            self.view.reset_plot()
        if hasattr(self.view, "clear_results"):
            self.view.clear_results()
        self._update_toolbar_state("idle")

    def _restore_stage1(self, ft, record, has_probe: bool) -> None:
        self._set_stage_done_ui(1, success=True)
        btn = getattr(self.view, "stage1_run_btn", None)
        if btn is not None:
            btn.setEnabled(False)

        self._initial_detune_hz = ft.initial_detune_hz
        lbl = getattr(self.view, "cold_landing_label", None)
        if lbl is not None:
            lbl.setText(f"{self._initial_detune_hz:.0f} Hz")

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

    def _restore_stage2(self, ft, has_tune: bool) -> None:
        self._set_stage_done_ui(2, success=True)

        hz_per_step = float(ft.hz_per_microstep or 0.0)
        positive = ft.positive_step_increases_frequency
        sign = 1.0 if positive else -1.0

        if self.phase is not None and hz_per_step:
            self.phase._hz_per_microstep = hz_per_step
            self.phase._signed_hz_per_microstep = hz_per_step * sign

        if hz_per_step > 0:
            self._hz_est_total_steps = hz_per_step
            self._hz_est_total_hz = hz_per_step

        spinbox = getattr(self.view, "hz_per_step_spinbox", None)
        if spinbox is not None and hz_per_step:
            spinbox.blockSignals(True)
            spinbox.setValue(hz_per_step)
            spinbox.blockSignals(False)
            spinbox.setEnabled(True)

        if not has_tune:
            self._enable_stage_btn(3)

    def _restore_stage3(self, ft) -> None:
        self._set_stage_done_ui(3, success=True)

        cold_steps = ft.cold_landing_steps or 0
        self._net_steps = -cold_steps
        net_lbl = getattr(self.view, "net_steps_label", None)
        if net_lbl is not None:
            net_lbl.setText(f"{self._net_steps:+d} steps")

        confirm_btn = getattr(self.view, "confirm_save_button", None)
        if confirm_btn is not None:
            confirm_btn.setEnabled(True)

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
