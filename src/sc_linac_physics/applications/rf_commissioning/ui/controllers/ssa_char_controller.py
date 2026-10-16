"""Controller for SSA Calibration display logic."""

from threading import Thread

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QDoubleSpinBox

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)
from sc_linac_physics.applications.rf_commissioning.phases.ssa_char import (
    SSACharPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    HOLD_STEP_MODE,
    PhaseRun,
    SegmentOutcome,
    SegmentResult,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (
    apply_pv_mapping,
    format_pv_update_message,
    resolve_cavity_selection,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.runner_bridge import (
    RunnerBridge,
)
from sc_linac_physics.utils.platform_paths import get_ssa_cal_base_dir
from sc_linac_physics.utils.sc_linac.linac import Machine


class SSACharController(QObject):
    """Owns phase execution and PV wiring for the SSA Calibration display."""

    phase_completed = pyqtSignal(object)
    # Thread-safe logging: emit from any thread; slot runs on the GUI thread.
    _log_signal = pyqtSignal(str)

    def __init__(self, view, session: CommissioningSession) -> None:
        super().__init__()
        self.view = view
        self.session = session
        self.bridge = RunnerBridge(self)
        if hasattr(self.view, "log_message"):
            self._log_signal.connect(self.view.log_message)
            self.bridge.log.connect(self.view.log_message)
        if hasattr(self.view, "step_progress_signal"):
            self.bridge.progress.connect(
                lambda step, pct: self.view.step_progress_signal.emit(step, pct)
            )
        self.bridge.holding.connect(self._on_holding)
        self.bridge.step_started.connect(
            lambda *_: self._set_next_button_enabled(False)
        )
        self.bridge.segment_finished.connect(self._on_segment_finished)

        self.context: PhaseContext | None = None
        self.phase: SSACharPhase | None = None
        self.machine: Machine | None = None
        self._cavity = None
        self.run: PhaseRun | None = None

        # Step mode is chosen before Run and copied onto each new PhaseRun.
        self._step_mode = False
        self._active_phase_instance_id: int | None = None

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
            self.view.log_message("No cavity selected")
            return

        try:
            cav_int = int(cavity_number)
            cm_int = int(cryomodule)
        except ValueError as exc:
            self.view.log_message(f"Invalid cavity/CM value: {exc}")
            return

        try:
            cavity = self._get_machine_cavity(cm_int, cav_int)
            self._cavity = cavity
            ssa = cavity.ssa
            self._apply_ssa_pv_mapping(ssa, cavity)
            self.view.log_message(
                format_pv_update_message(
                    cryomodule, cavity_number, cm_int, cav_int
                )
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _apply_ssa_pv_mapping(self, ssa, cavity) -> None:
        pv_map = {}

        optional = [
            ("pydm_cal_status", ssa.calibration_status_pv),
            ("pydm_max_fwd_pwr", ssa.max_fwd_pwr_pv),
            ("pydm_slope_new", ssa.measured_slope_pv),
            ("pydm_slope_current", ssa.current_slope_pv),
            ("drive_max_spinbox", ssa.drive_max_setpoint_pv),
            ("pydm_drive_max_new", ssa.drive_max_new_pv),
            ("pydm_drive_max_current", ssa.drive_max_current_pv),
        ]
        for widget_name, pv_addr in optional:
            if hasattr(self.view, widget_name):
                pv_map[getattr(self.view, widget_name)] = pv_addr

        apply_pv_mapping(pv_map)

    def _get_machine_cavity(self, cm: int, cav: int):
        if not self.machine:
            self.machine = Machine()
        return self.machine.cryomodules[f"{cm:02d}"].cavities[cav]

    # ------------------------------------------------------------------
    # Phase execution
    # ------------------------------------------------------------------

    def on_run_calibration(self) -> None:
        operator = self._validate_operator_for_run()
        if operator is None:
            return

        if not self._ensure_active_record_for_run():
            return

        run_target = self._resolve_run_target()
        if run_target is None:
            return

        cavity_name, cm, cav = run_target
        self.view.log_message(f"Starting SSA calibration for {cavity_name}")
        self.view.clear_results()

        try:
            self._start_run_for_target(cm=cm, cav=cav, operator=operator)
        except Exception as exc:
            import traceback

            self.view.show_error(f"Failed to start calibration: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

    def _validate_operator_for_run(self) -> str | None:
        operator = self._get_operator()
        if operator:
            return operator
        self.view.show_error(
            "Please select an operator in the header before running."
        )
        return None

    def _ensure_active_record_for_run(self) -> bool:
        if self.session.has_active_record():
            return True
        return self._auto_create_record()

    def _resolve_run_target(self) -> tuple[str, int, int] | None:
        cavity_info = self.view.get_current_cavity()
        if not cavity_info:
            self.view.show_error(
                "Unable to determine cavity. Select a cavity and try again."
            )
            return None

        cavity_name, cryomodule = cavity_info
        try:
            cm, cav = self._parse_cavity_from_record(cavity_name, cryomodule)
        except (ValueError, IndexError):
            self.view.show_error(f"Invalid cavity name format: {cavity_name}")
            return None

        return cavity_name, cm, cav

    def _start_run_for_target(self, cm: int, cav: int, operator: str) -> None:
        self.update_pv_addresses(f"{cm:02d}", str(cav))
        cavity = self._get_machine_cavity(cm, cav)
        self._cavity = cavity

        drive_max = self._get_drive_max()
        if drive_max is None:
            self.view.show_error(
                "Unable to read the SSA drive max from the PV."
            )
            return

        if not self._prepare_phase_context(cavity, operator, drive_max):
            return

        self._set_running_ui_state()
        self._execute_phase_async()

    def _get_drive_max(self) -> float | None:
        spinbox = getattr(self.view, "drive_max_spinbox", None)
        if spinbox is None:
            return None

        try:
            if isinstance(spinbox, QDoubleSpinBox):
                return float(QDoubleSpinBox.value(spinbox))
        except (AttributeError, TypeError, ValueError):
            return None

        return None

    def _prepare_phase_context(
        self, cavity, operator: str, drive_max: float
    ) -> bool:
        record = self.session.get_active_record()
        record_id = self.session.get_active_record_id()
        self.view.log_message(f"Using record ID: {record_id}")

        can_run, reason = self.session.can_run_phase(
            CommissioningPhase.SSA_CHAR
        )
        if not can_run:
            self.view.show_error(f"Cannot run SSA_CHAR phase: {reason}")
            return False

        if record_id is not None:
            phase_start = self.session.start_active_phase_instance(
                CommissioningPhase.SSA_CHAR, operator=operator
            )
            self._active_phase_instance_id = (
                phase_start.phase_instance_id if phase_start else None
            )

        if self._active_phase_instance_id is not None:
            self.view.log_message(
                f"Tracking phase instance ID: {self._active_phase_instance_id}"
            )

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": cavity, "drive_max": drive_max},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        self.phase = SSACharPhase(self.context)

        is_valid, message = self.phase.validate_prerequisites()
        if not is_valid:
            self.view.show_error(f"Prerequisites not met: {message}")
            return False

        return True

    def _set_running_ui_state(self) -> None:
        self.view.run_button.setEnabled(False)
        self.view.pause_button.setEnabled(True)
        self.view.abort_button.setEnabled(True)
        self.view.local_phase_status.setText("RUNNING")

    def _execute_phase_async(self) -> None:
        if not self.context or not self.phase:
            return

        # No AbortHook, the same as before this controller used PhaseRun.
        # Abort only sets context.abort_requested, which SSACharPhase reads in
        # wait_for_completion. It doesn't call cavity.request_abort().
        self.run = PhaseRun(self.phase)
        self.run.set_step_mode(self._step_mode)
        if not self.bridge.start_segment(
            self.run, self.phase.get_phase_steps(), then_complete=True
        ):
            self.view.show_error("A calibration is already running.")

    def _on_segment_finished(self, result: SegmentResult) -> None:
        if result.outcome is SegmentOutcome.COMPLETED:
            self.on_phase_completed()
        else:
            self.on_phase_failed(result.message or "Phase execution failed")

    def _on_holding(self, step: str, reason: str) -> None:
        if reason == HOLD_STEP_MODE:
            self.view.log_message(f"Step mode: press Next to run {step}")
            self._set_next_button_enabled(True)

    def on_phase_completed(self) -> None:
        self._reset_run_controls()

        self.view.log_message("SSA calibration completed successfully")
        self.view.local_phase_status.setText("COMPLETED")
        self.view.local_progress_bar.setValue(100)
        self._update_toolbar_state("complete")

        try:
            if self.context and self.context.record.ssa_char:
                if self._active_phase_instance_id is not None:
                    self.session.complete_active_phase_instance(
                        phase_instance_id=self._active_phase_instance_id,
                        phase=CommissioningPhase.SSA_CHAR,
                        artifact_payload=self.context.record.ssa_char.to_dict(),
                    )

                if self.session.save_active_record():
                    self.view.log_message(
                        f"Results saved (ID: {self.session.get_active_record_id()})"
                    )
                    self.phase_completed.emit(self.session.get_active_record())
                else:
                    self.view.log_message("Warning: failed to save to database")

                self._append_measurement_history()
                self.view._update_local_results(self.context.record.ssa_char)
                self.view._update_stored_readout(self.context.record.ssa_char)
            else:
                self.view.log_message("Warning: no ssa_char data to display")

        except Exception as exc:
            import traceback

            self.view.log_message(f"Warning: failed to save results: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            if self._active_phase_instance_id is not None:
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.SSA_CHAR,
                    error_message=str(exc),
                )
        finally:
            self._active_phase_instance_id = None

        self.view.run_button.setEnabled(True)
        self.view.pause_button.setEnabled(False)
        self.view.abort_button.setEnabled(False)

    def on_phase_failed(self, error_msg: str) -> None:
        self._reset_run_controls()

        self.view.log_message(f"SSA calibration failed: {error_msg}")
        self.view.local_phase_status.setText("FAILED")
        self._update_toolbar_state("error")

        try:
            if self.phase:
                self.phase.finalize_phase()

            if self.session.save_active_record():
                self.view.log_message("Partial results saved")

            if self._active_phase_instance_id is not None:
                snapshot = None
                if self.context and self.context.record.ssa_char:
                    snapshot = self.context.record.ssa_char.to_dict()
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.SSA_CHAR,
                    error_message=error_msg,
                    artifact_payload=snapshot,
                )

            if self.context and self.context.record.ssa_char:
                self._append_measurement_history(error_msg=error_msg)
                self.view._update_local_results(self.context.record.ssa_char)
                self.view._update_stored_readout(self.context.record.ssa_char)

        except Exception as exc:
            import traceback

            self.view.log_message(
                f"Warning: failed to save partial results: {exc}"
            )
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            if self._active_phase_instance_id is not None:
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.SSA_CHAR,
                    error_message=str(exc),
                )
        finally:
            self._active_phase_instance_id = None

        self.view.run_button.setEnabled(True)
        self.view.pause_button.setEnabled(False)
        self.view.abort_button.setEnabled(False)
        self.view.show_error(f"Calibration failed: {error_msg}")

    # ------------------------------------------------------------------
    # Manual Push / Save
    # ------------------------------------------------------------------

    def on_push_slope(self) -> None:
        cavity = self._resolve_cavity()
        if cavity is None:
            return

        def _push():
            try:
                cavity.push_ssa_slope()
                self._log_signal.emit("✓ SSA slope pushed to cavity register")
            except Exception as exc:
                self._log_signal.emit(f"Push failed: {exc}")

        Thread(target=_push, daemon=True).start()

    def on_plot(self) -> None:
        cavity = self._resolve_cavity()
        if cavity is None:
            return

        pv_base = cavity.pv_prefix.rstrip(":")
        cavity_dir_name = pv_base.replace(":", "_")
        base = get_ssa_cal_base_dir() / cavity_dir_name

        if not base.is_dir():
            self.view.log_message(f"No SSA cal directory found: {base}")
            return

        for subdir in sorted(base.iterdir(), reverse=True):
            if not subdir.is_dir():
                continue
            png = subdir / "ssa_cal.png"
            if png.exists():
                self._show_plot(png)
                return

        self.view.log_message(f"No ssa_cal.png found under {base}")

    def _show_plot(self, png_path) -> None:
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout

        dlg = QDialog(self.view)
        dlg.setWindowTitle(f"SSA Cal Plot — {png_path.parent.name}")

        label = QLabel()
        label.setPixmap(QPixmap(str(png_path)))

        scroll = QScrollArea()
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        dlg.setLayout(layout)
        dlg.resize(800, 600)
        dlg.show()

    def _resolve_cavity(self):
        if self._cavity is not None:
            return self._cavity

        cavity_info = self.view.get_current_cavity()
        if not cavity_info:
            self.view.log_message("No cavity selected")
            return None

        cavity_name, cryomodule = cavity_info
        try:
            cm, cav = self._parse_cavity_from_record(cavity_name, cryomodule)
            cavity = self._get_machine_cavity(cm, cav)
            self._cavity = cavity
            return cavity
        except Exception as exc:
            self.view.log_message(f"Could not resolve cavity: {exc}")
            return None

    # ------------------------------------------------------------------
    # Pause / Abort
    # ------------------------------------------------------------------

    def on_abort(self) -> None:
        # request_abort also ends a retry delay or a pause at once.
        if self.run:
            self.run.request_abort()
            self.view.log_message("Abort requested...")
            self.view.abort_button.setEnabled(False)

    def on_pause_test(self) -> None:
        if not self.run:
            return
        if self.run.paused:
            self.run.resume()
            self.view.log_message("Test resumed...")
            self.view.pause_button.setText("⏸ Pause")
            self._update_toolbar_state("running")
        else:
            self.run.pause()
            self.view.log_message("Test paused...")
            self.view.pause_button.setText("▶ Resume")
            self._update_toolbar_state("paused")

    def on_toggle_step_mode(self) -> None:
        self._step_mode = not self._step_mode
        if self.run:
            self.run.set_step_mode(self._step_mode)
        if self._step_mode:
            self.view.log_message("Step mode on: press Next before each step")
        else:
            self.view.log_message("Step mode off")
            self._set_next_button_enabled(False)

    def on_next_step(self) -> None:
        if self.run and self._step_mode:
            self._set_next_button_enabled(False)
            self.run.next_step()

    def _reset_run_controls(self) -> None:
        self._set_next_button_enabled(False)
        if hasattr(self.view, "pause_button"):
            self.view.pause_button.setText("⏸ Pause")

    def _set_next_button_enabled(self, enabled: bool) -> None:
        if hasattr(self.view, "next_step_btn"):
            self.view.next_step_btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _get_operator(self) -> str:
        if hasattr(self.view, "get_current_operator"):
            return self.view.get_current_operator() or ""
        return ""

    def _parse_cavity_from_record(
        self, cavity_name: str, cryomodule: str
    ) -> tuple[int, int]:
        parts = cavity_name.split("_")
        cav_part = parts[2] if len(parts) >= 3 else "CAV1"
        cav = int(cav_part.replace("CAV", ""))
        cm = int(cryomodule)
        return cm, cav

    def _update_toolbar_state(self, state: str) -> None:
        if hasattr(self.view, "ui") and hasattr(
            self.view.ui, "update_toolbar_state"
        ):
            self.view.ui.update_toolbar_state(state)

    def _append_measurement_history(self, error_msg: str | None = None) -> None:
        if not (self.context and self.context.record.ssa_char):
            return
        notes = f"Phase failed: {error_msg}" if error_msg else None
        self.session.add_measurement_to_history(
            CommissioningPhase.SSA_CHAR,
            self.context.record.ssa_char,
            operator=self.context.operator or self._get_operator(),
            notes=notes,
            phase_instance_id=self._active_phase_instance_id,
        )

    def _auto_create_record(self) -> bool:
        cryomodule, cavity_number = self._get_cavity_from_parent()
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

    def _get_cavity_from_parent(self) -> tuple[str | None, str | None]:
        parent = self.view.parent()
        while parent:
            if hasattr(parent, "cryomodule_combo") and hasattr(
                parent, "cavity_combo"
            ):
                try:
                    cm = parent.cryomodule_combo.currentText()
                    cav = parent.cavity_combo.currentText()
                    if not cm or not cav:
                        return None, None
                    return cm, str(cav)
                except Exception:
                    return None, None
            parent = parent.parent()
        return None, None
