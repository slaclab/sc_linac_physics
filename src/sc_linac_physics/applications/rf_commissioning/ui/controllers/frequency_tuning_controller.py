"""Controller for the Frequency Tuning display."""

from datetime import datetime
from threading import Thread

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
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


class FrequencyTuningController(QObject):
    """Owns phase execution and plot wiring for the Frequency Tuning display."""

    phase_completed = pyqtSignal(object)
    phase_run_finished = pyqtSignal(bool, str)
    _log_signal = pyqtSignal(str)

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
        self._initial_detune_hz: float | None = None
        self._active_phase_instance_id: int | None = None

        self.phase_run_finished.connect(self._on_phase_run_finished)

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
            apply_pv_mapping({})
            self.view.log_message(
                format_pv_update_message(cryomodule, cavity_number, cm, cav)
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _get_machine_cavity(self, cm: int, cav: int):
        if not self.machine:
            self.machine = Machine()
        return self.machine.cryomodules[f"{cm:02d}"].cavities[cav]

    # ------------------------------------------------------------------
    # Phase execution
    # ------------------------------------------------------------------

    def on_run_automated_test(self) -> None:
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator in the header before running."
            )
            return

        if not self.session.has_active_record():
            if not self._auto_create_record():
                return

        cavity_info = self.view.get_current_cavity()
        if not cavity_info:
            self.view.show_error(
                "Unable to determine cavity. Select a cavity and try again."
            )
            return

        cavity_name, cryomodule = cavity_info
        try:
            parts = cavity_name.split("_")
            cav = int(parts[2].replace("CAV", "")) if len(parts) >= 3 else 1
            cm = int(cryomodule)
        except (ValueError, IndexError):
            self.view.show_error(f"Invalid cavity name format: {cavity_name}")
            return

        self.view.log_message(f"Starting frequency tuning for {cavity_name}")
        self.view.clear_results()
        self.view.reset_plot()
        self._initial_detune_hz = None

        try:
            self._start_run(cm=cm, cav=cav, operator=operator)
        except Exception as exc:
            import traceback

            self.view.show_error(f"Failed to start frequency tuning: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

    def _start_run(self, cm: int, cav: int, operator: str) -> None:
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

        is_valid, message = self.phase.validate_prerequisites()
        if not is_valid:
            self.view.show_error(f"Prerequisites not met: {message}")
            return

        self._set_running_ui_state()
        QTimer.singleShot(100, self._run_phase_in_background)

    def _set_running_ui_state(self) -> None:
        self.view.run_button.setEnabled(False)
        self.view.pause_button.setEnabled(True)
        self.view.abort_button.setEnabled(True)
        self.view.local_phase_status.setText("RUNNING")

    def _run_phase_in_background(self) -> None:
        if not self.context or not self.phase:
            return

        self.context.progress_callback = (
            lambda step, prog: self.view.step_progress_signal.emit(step, prog)
        )
        self.context.parameters["tuning_update_callback"] = (
            lambda steps, detune: self.view.tuning_data_signal.emit(
                steps, detune
            )
        )
        self._steps = self.phase.get_phase_steps()

        def worker() -> None:
            try:
                self.phase._mark_phase_started()
                for step_name in self._steps:
                    if not self._check_pause_and_abort():
                        return

                    success = self._execute_single_step(step_name)
                    if not success:
                        self.phase_run_finished.emit(
                            False, f"Step failed: {step_name}"
                        )
                        return

                self._finalize_background_phase()
            except Exception as exc:
                self.phase_run_finished.emit(False, str(exc))

        Thread(target=worker, daemon=True).start()

    def _execute_single_step(self, step_name: str) -> bool:
        import time

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
        import time

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
        """Wire up plot elements as each step completes."""
        if step_name == "record_cold_landing":
            self._initial_detune_hz = data.get("initial_detune_hz")

        elif step_name == "probe_stepper_direction":
            hz_per_step = data.get("hz_per_microstep")
            if hz_per_step and self._initial_detune_hz is not None:
                # set_projection runs on the GUI thread via a queued connection
                # because tuning_data_signal is cross-thread; we use the same
                # mechanism here by scheduling via singleShot from the worker.
                initial = self._initial_detune_hz
                hps = hz_per_step
                QTimer.singleShot(
                    0, lambda: self.view.set_projection(initial, hps)
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
        import time

        while self._paused:
            time.sleep(0.1)
            if self.context and self.context.is_abort_requested():
                self.phase_run_finished.emit(False, "Aborted")
                return False

        if self.context and self.context.is_abort_requested():
            self.phase_run_finished.emit(False, "Aborted")
            return False

        return True

    def _on_phase_run_finished(self, success: bool, error_msg: str) -> None:
        if success:
            self.on_phase_completed()
        else:
            self.on_phase_failed(error_msg or "Phase execution failed")

    def on_phase_completed(self) -> None:
        self._paused = False
        self.view.log_message("Frequency tuning completed successfully")
        self.view.local_phase_status.setText("COMPLETED")
        self.view.local_progress_bar.setValue(100)
        self._update_toolbar_state("complete")

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

        self.view.run_button.setEnabled(True)
        self.view.pause_button.setEnabled(False)
        self.view.abort_button.setEnabled(False)

    def on_phase_failed(self, error_msg: str) -> None:
        self._paused = False
        self.view.log_message(f"Frequency tuning failed: {error_msg}")
        self.view.local_phase_status.setText("FAILED")
        self._update_toolbar_state("error")

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

        self.view.run_button.setEnabled(True)
        self.view.pause_button.setEnabled(False)
        self.view.abort_button.setEnabled(False)
        self.view.show_error(f"Frequency tuning failed: {error_msg}")

    # ------------------------------------------------------------------
    # Pause / Abort
    # ------------------------------------------------------------------

    def on_abort(self) -> None:
        if self.context:
            self.context.request_abort()
            self.view.log_message("Abort requested...")
            self.view.abort_button.setEnabled(False)

    def on_pause_test(self) -> None:
        if self._paused:
            self._paused = False
            self.view.log_message("Test resumed...")
            self.view.pause_button.setText("⏸ Pause")
            self._update_toolbar_state("running")
        else:
            self._paused = True
            self.view.log_message("Test paused...")
            self.view.pause_button.setText("▶ Resume")
            self._update_toolbar_state("paused")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_operator(self) -> str:
        if hasattr(self.view, "get_current_operator"):
            return self.view.get_current_operator() or ""
        return ""

    def _update_toolbar_state(self, state: str) -> None:
        if hasattr(self.view, "ui") and hasattr(
            self.view.ui, "update_toolbar_state"
        ):
            self.view.ui.update_toolbar_state(state)

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
