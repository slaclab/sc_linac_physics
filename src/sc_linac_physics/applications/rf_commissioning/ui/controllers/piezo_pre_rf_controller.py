"""Controller for Piezo Pre-RF display logic."""

from datetime import datetime
from threading import Thread


from PyQt5.QtCore import QTimer, pyqtSignal, QObject

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_pre_rf import (
    PiezoPreRFPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (
    apply_pv_mapping,
    build_pv_mapping,
    format_pv_update_message,
    get_piezo_from_selection,
    resolve_cavity_selection,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class PiezoPreRFController(QObject):
    """Owns phase execution and PV wiring for the display."""

    phase_completed = pyqtSignal(object)  # Emits the updated record
    phase_run_finished = pyqtSignal(bool, str)

    def __init__(self, view, session: CommissioningSession) -> None:
        super().__init__()  # Initialize QObject
        self.view = view
        self.session = session

        self.context: PhaseContext | None = None
        self.phase: PiezoPreRFPhase | None = None
        self.machine: Machine | None = None

        # Pause and step mode state
        self._paused = False
        self._step_mode = False
        self._step_executing = False
        self._current_step_index = 0
        self._total_steps = 0
        self._steps: list[str] = []
        self._active_phase_instance_id: int | None = None

        self.phase_run_finished.connect(self._on_phase_run_finished)

    def setup_pv_connections(self) -> None:
        """Connect to PVs based on active record's cavity.

        PVs are updated when a record is loaded/started.
        """
        # Initial update if there's an active record
        if self.session.has_active_record():
            self.update_pv_addresses()

    def _resolve_cavity_selection(
        self, cryomodule: str | None, cavity_number: str | None
    ) -> tuple[str | None, str | None]:
        """Resolve cavity selection from arguments or parent dropdowns."""
        return resolve_cavity_selection(self.view, cryomodule, cavity_number)

    def _get_piezo_from_selection(
        self, cryomodule: str, cavity_number: str
    ) -> tuple[CommissioningPiezo, int, int]:
        """Return piezo object and parsed CM/CAV numbers from selection."""
        piezo, cm, cav, machine = get_piezo_from_selection(
            self.machine,
            cryomodule,
            cavity_number,
        )
        self.machine = machine
        return piezo, cm, cav

    def update_pv_addresses(
        self,
        cryomodule: str | None = None,
        cavity_number: str | None = None,
    ) -> None:
        """Update PV addresses based on selected cavity from dropdowns.

        Args:
            cryomodule: Cryomodule identifier (e.g., "02"). If None, gets from UI dropdowns via parent.
            cavity_number: Cavity number (e.g., "1"). If None, gets from UI dropdowns via parent.
        """
        cryomodule, cavity_number = self._resolve_cavity_selection(
            cryomodule, cavity_number
        )
        if cryomodule is None or cavity_number is None:
            self.view.log_message("No cavity selected")
            return

        try:
            piezo, cm, cav = self._get_piezo_from_selection(
                cryomodule, cavity_number
            )
        except (ValueError, AttributeError) as exc:
            self.view.log_message(f"Error parsing cavity info: {exc}")
            return
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")
            return

        try:
            pv_mapping = self._build_pv_mapping(piezo)
            self._apply_pv_mapping(pv_mapping)
            self._log_pv_update(cryomodule, cavity_number, cm, cav)
            self._sync_piezo_readbacks(piezo)
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _build_pv_mapping(self, piezo: CommissioningPiezo) -> dict:
        """Build PV mapping dictionary for widgets."""
        return build_pv_mapping(self.view, piezo)

    def _apply_pv_mapping(self, pv_mapping: dict) -> None:
        """Apply PV addresses to widgets."""
        apply_pv_mapping(pv_mapping)

    def _log_pv_update(
        self, cryomodule: str, cavity_number: str, cm: int, cav: int
    ) -> None:
        """Log PV update with formatted cavity name."""
        self.view.log_message(
            format_pv_update_message(cryomodule, cavity_number, cm, cav)
        )

    def _sync_piezo_readbacks(
        self, piezo: CommissioningPiezo | None = None
    ) -> None:
        """Sync piezo enable/manual UI from actual readback values."""
        if not hasattr(self.view, "update_piezo_readbacks"):
            return

        try:
            if piezo is None:
                cryomodule, cavity_number = self._resolve_cavity_selection(
                    None, None
                )
                if cryomodule is None or cavity_number is None:
                    return
                piezo, _, _ = self._get_piezo_from_selection(
                    cryomodule, cavity_number
                )

            self.view.update_piezo_readbacks(piezo)
        except Exception as exc:
            self.view.log_message(f"Readback sync failed: {exc}")

    def _parse_cavity_from_record(
        self, cavity_name: str, cryomodule: str
    ) -> tuple[int, int]:
        """Parse cavity label and cryomodule into integer CM/CAV values."""
        parts = cavity_name.split("_")
        cav_part = parts[2] if len(parts) >= 3 else "CAV1"
        cav = int(cav_part.replace("CAV", ""))
        cm = int(cryomodule)
        return cm, cav

    def _prepare_phase_context(self, cavity, operator: str) -> bool:
        """Build phase context and validate run prerequisites."""
        record = self.session.get_active_record()
        record_id = self.session.get_active_record_id()
        self.view.log_message(f"Using record ID: {record_id}")

        can_run, reason = self.session.can_run_phase(
            CommissioningPhase.PIEZO_PRE_RF
        )
        if not can_run:
            self.view.show_error(f"Cannot run PIEZO_PRE_RF phase: {reason}")
            self.view.log_message(f"ERROR: {reason}")
            return False

        if record_id is not None:
            phase_start = self.session.start_active_phase_instance(
                CommissioningPhase.PIEZO_PRE_RF,
                operator=operator,
            )
            self._active_phase_instance_id = (
                phase_start.phase_instance_id
                if phase_start is not None
                else None
            )

        if self._active_phase_instance_id is not None:
            self.view.log_message(
                f"Tracking phase instance ID: {self._active_phase_instance_id}"
            )

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": cavity},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        self.phase = PiezoPreRFPhase(self.context)

        is_valid, message = self.phase.validate_prerequisites()
        if not is_valid:
            self.view.show_error(f"Prerequisites not met: {message}")
            self.view.log_message(f"ERROR: {message}")
            return False

        return True

    def _set_running_ui_state(self) -> None:
        """Set UI widgets for an active test run."""
        self.view.run_button.setEnabled(False)
        self.view.pause_button.setEnabled(True)
        self.view.abort_button.setEnabled(True)
        self.view.local_phase_status.setText("RUNNING")

    def _get_selected_cavity_info(self) -> tuple[str, int, int] | None:
        """Get and validate selected cavity information.

        Returns:
            Tuple of (cavity_name, cm, cav) or None if invalid.
        """
        cavity_info = self.view.get_current_cavity()
        if not cavity_info:
            self.view.show_error(
                "Unable to determine cavity information from active record."
            )
            return None

        cavity_name, cryomodule = cavity_info
        try:
            cm, cav = self._parse_cavity_from_record(cavity_name, cryomodule)
        except (ValueError, IndexError):
            self.view.show_error(f"Invalid cavity name format: {cavity_name}")
            return None

        return cavity_name, cm, cav

    def _get_machine_cavity(self, cm: int, cav: int):
        """Resolve and return machine cavity object."""
        if not self.machine:
            self.machine = Machine(piezo_class=CommissioningPiezo)
        return self.machine.cryomodules[f"{cm:02d}"].cavities[cav]

    def on_run_automated_test(self) -> None:
        """Handle Run Automated Test button click.

        Auto-creates a record if needed based on parent's cavity selection.
        """
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator in the header before running the test."
            )
            self._focus_parent_widget("operator_combo")
            return

        if not self.session.has_active_record():
            if not self._auto_create_record():
                return

        cavity_data = self._get_selected_cavity_info()
        if not cavity_data:
            return

        cavity_name, cm, cav = cavity_data

        self.view.log_message(f"Starting automated test for {cavity_name}")
        self.view.clear_results()

        try:
            self.update_pv_addresses(f"{cm:02d}", str(cav))
            cavity = self._get_machine_cavity(cm, cav)

            if not self._prepare_phase_context(cavity, operator):
                return

            self._set_running_ui_state()

            self.execute_phase_steps()

        except Exception as exc:
            import traceback

            self.view.show_error(f"Failed to start test: {exc}")
            self.view.log_message(f"Error: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

    def _auto_create_record(self) -> bool:
        """Auto-create a commissioning record based on parent's cavity selection.

        Returns:
            True if record created successfully, False otherwise
        """
        # Get cavity selection from parent
        cryomodule, cavity_number = self._get_cavity_from_parent()

        if not cryomodule or not cavity_number:
            self.view.show_error(
                "Please select a cavity in the header.\n\n"
                "Use the CM and Cavity dropdowns in the header, then try again."
            )
            self._focus_parent_widget("cryomodule_combo")
            return False

        try:
            cavity_display_name = f"{cryomodule}_CAV{cavity_number}"
            self.view.log_message(
                f"Auto-creating commissioning record for {cavity_display_name}..."
            )

            record, record_id, created = self.session.start_new_record(
                cryomodule=cryomodule,
                cavity_number=cavity_number,
            )

            status = "Created" if created else "Loaded"
            self.view.log_message(
                f"✓ {status} record ID: {record_id} for {cavity_display_name}"
            )

            # Notify parent container to update its UI
            self._notify_parent_record_created(record, record_id)

            # Update PVs for the new cavity
            self.update_pv_addresses()

            return True

        except Exception as e:
            import traceback

            self.view.show_error(
                f"Failed to create commissioning record:\n\n{e}"
            )
            self.view.log_message(f"ERROR: {e}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            return False

    def _get_cavity_from_parent(self) -> tuple[str | None, str | None]:
        """Get cavity selection from parent container.

        Returns:
            Tuple of (cryomodule, cavity_number) or (None, None)
        """
        parent = self.view.parent()
        while parent:
            if hasattr(parent, "cryomodule_combo") and hasattr(
                parent, "cavity_combo"
            ):
                try:
                    cm = parent.cryomodule_combo.currentText()
                    cav = parent.cavity_combo.currentText()

                    if not cm or not cav:
                        return (None, None)

                    # cm is already just the identifier like "02" or "H1"
                    cryomodule = cm
                    cavity_number = str(cav)

                    return (cryomodule, cavity_number)

                except Exception as e:
                    self.view.log_message(
                        f"Error getting cavity from parent: {e}"
                    )
                    return (None, None)
            parent = parent.parent()

        return (None, None)

    def _focus_parent_widget(self, widget_name: str) -> None:
        """Try to focus a widget in the parent container.

        Args:
            widget_name: Name of the widget to focus (e.g., 'operator_combo')
        """
        parent = self.view.parent()
        while parent:
            if hasattr(parent, widget_name):
                widget = getattr(parent, widget_name)
                widget.setFocus()
                return
            parent = parent.parent()

    def execute_phase_steps(self) -> None:
        """Execute phase steps using the controller-managed step loop."""
        if not self.context or not self.phase:
            self.view.show_error("No phase context available to run")
            return

        self.context.progress_callback = (
            lambda step, prog: self.view.step_progress_signal.emit(step, prog)
        )

        # Get the steps and store for step mode
        self._steps = self.phase.get_phase_steps()
        self._total_steps = len(self._steps)
        self._current_step_index = 0

        def run_phase():
            try:
                if self._step_mode:
                    # In step mode, show first step and wait for click
                    self.view.log_message(
                        f"Step mode: Ready for step 1/{self._total_steps}: {self._steps[0]}"
                    )
                    self._set_next_button_enabled(True)
                else:
                    self._run_phase_in_background()
            except Exception as exc:
                import traceback

                self.view.log_message(
                    f"Exception: {exc}\n{traceback.format_exc()}"
                )
                self.on_phase_failed(str(exc))

        QTimer.singleShot(100, run_phase)

    def _run_phase_in_background(self) -> None:
        """Run blocking phase execution in a worker thread."""

        def worker() -> None:
            try:
                steps = self.phase.get_phase_steps()
                for step_name in steps:
                    if not self._check_pause_and_abort():
                        return

                    # Execute the step
                    success = self.phase._execute_step_with_retry(step_name)
                    if not success:
                        self.phase_run_finished.emit(
                            False, f"Step failed: {step_name}"
                        )
                        return

                self._finalize_background_phase()

            except Exception as exc:
                self.phase_run_finished.emit(False, str(exc))

        Thread(target=worker, daemon=True).start()

    def _check_pause_and_abort(self) -> bool:
        """Check for pause/abort requests. Returns False if aborted."""
        import time

        # Wait while paused
        while self._paused:
            time.sleep(0.1)
            if self.context and self.context.is_abort_requested():
                self.phase_run_finished.emit(False, "Aborted")
                return False

        # Check for abort
        if self.context and self.context.is_abort_requested():
            self.phase_run_finished.emit(False, "Aborted")
            return False

        return True

    def _finalize_background_phase(self) -> None:
        """Finalize phase after all steps complete in background worker."""
        try:
            self.phase.finalize_phase()
            self.phase._mark_phase_completed()
            self.phase_run_finished.emit(True, "")
        except Exception as e:
            self.phase._handle_exception(e)
            self.phase_run_finished.emit(False, str(e))

    def _on_phase_run_finished(self, success: bool, error_msg: str) -> None:
        """Handle worker-thread phase completion on UI thread."""
        self._sync_piezo_readbacks()

        if success:
            self.on_phase_completed()
            return

        self.on_phase_failed(error_msg or "Phase execution failed")

    def _execute_single_step(self, step_name: str) -> bool:
        """Execute a single step with retry logic and checkpoint creation.

        Args:
            step_name: Name of the step to execute

        Returns:
            True if step succeeded, False otherwise
        """
        # Check for pause/abort before executing
        if not self._wait_for_unpause():
            return False

        if self.context and self.context.is_abort_requested():
            self.view.log_message(f"Abort during step: {step_name}")
            return False

        self._notify_step_progress(step_name)

        # Execute with retry logic
        return self._execute_step_with_retries(step_name, max_retries=3)

    def _wait_for_unpause(self) -> bool:
        """Wait while paused. Returns False if should abort."""
        import time

        while self._paused:
            QTimer.singleShot(100, lambda: None)  # Process events while paused
            time.sleep(0.1)
        return True

    def _notify_step_progress(self, step_name: str) -> None:
        """Notify progress callback of current step."""
        if self.context.progress_callback:
            idx = (
                self._steps.index(step_name) if step_name in self._steps else 0
            )
            progress = int((idx / len(self._steps)) * 100)
            self.context.progress_callback(step_name, progress)

    def _execute_step_with_retries(
        self, step_name: str, max_retries: int
    ) -> bool:
        """Execute a step with retry logic."""
        from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
            PhaseResult,
        )

        retry_count = 0
        while retry_count < max_retries:
            try:
                result = self.phase.execute_step(step_name)
                self._create_step_checkpoint(step_name, result)

                # Handle result
                if result.result in (PhaseResult.SUCCESS, PhaseResult.SKIP):
                    return self._handle_step_success(step_name, result)

                if result.result == PhaseResult.RETRY:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.view.log_message(
                            f"Retrying {retry_count}/{max_retries}: {result.message}"
                        )
                        continue
                    self.view.log_message(f"Failed after {max_retries} retries")
                    return False

                # PhaseResult.FAILED
                self.view.log_message(f"✗ {step_name} failed: {result.message}")
                return False

            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    self.view.log_message(
                        f"Exception on retry {retry_count}: {str(e)}"
                    )
                    continue
                self.view.log_message(
                    f"Exception after {max_retries} retries: {str(e)}"
                )
                return False

        return False

    def _create_step_checkpoint(self, step_name: str, result) -> None:
        """Create checkpoint for step execution."""
        from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
            PhaseResult,
        )
        from sc_linac_physics.applications.rf_commissioning.models.data_models import (
            PhaseCheckpoint,
        )

        checkpoint = PhaseCheckpoint(
            phase=self.phase.phase_type,
            timestamp=datetime.now(),
            operator=self.context.operator,
            step_name=step_name,
            success=result.result in (PhaseResult.SUCCESS, PhaseResult.SKIP),
            notes=result.message,
            measurements=result.data,
        )
        self.context.record.phase_history.append(checkpoint)

    def _handle_step_success(self, step_name: str, result) -> bool:
        """Handle successful step execution."""
        from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
            PhaseResult,
        )

        if result.result == PhaseResult.SUCCESS:
            self.view.log_message(f"✓ {step_name} completed")
            if step_name == "setup_piezo":
                self._sync_piezo_readbacks()
        else:  # SKIP
            self.view.log_message(f"⊘ {step_name} skipped")
        return True

    def _finalize_phase_execution(self) -> None:
        """Finalize phase after all steps complete in step mode."""
        try:
            self.phase.finalize_phase()

            # Log what data was populated
            if self.context and self.context.record.piezo_pre_rf:
                self.view.log_message(
                    f"Phase data populated: Cap A={self.context.record.piezo_pre_rf.capacitance_a}, "
                    f"Cap B={self.context.record.piezo_pre_rf.capacitance_b}, "
                    f"Passed={self.context.record.piezo_pre_rf.passed}"
                )
            else:
                self.view.log_message(
                    "Warning: piezo_pre_rf data was not populated after finalize_phase()"
                )

            self.on_phase_completed()
        except Exception as e:
            import traceback

            self.view.log_message(f"Error finalizing phase: {str(e)}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            self.on_phase_failed(str(e))

    def on_phase_completed(self) -> None:
        """Handle phase completion."""
        # Reset pause and step mode state
        self._paused = False
        self._step_mode = False
        self._step_executing = False
        self._current_step_index = 0

        self.view.log_message("Phase completed successfully")
        self.view.local_phase_status.setText("COMPLETED")
        self.view.local_progress_bar.setValue(100)
        self._update_toolbar_state("complete")

        try:
            if self.context and self.context.record.piezo_pre_rf:
                if self._active_phase_instance_id is not None:
                    success = self.session.complete_active_phase_instance(
                        phase_instance_id=self._active_phase_instance_id,
                        phase=CommissioningPhase.PIEZO_PRE_RF,
                        artifact_payload=self.context.record.piezo_pre_rf.to_dict(),
                    )
                    if success and self.session.has_active_record():
                        self.view.log_message(
                            f"✓ Advanced to {self.session.get_active_record().current_phase.value}"
                        )
                    elif not success:
                        self.view.log_message(
                            "Warning: Failed to advance phase lifecycle"
                        )

                # Save after lifecycle completion so current_phase/status are persisted.
                if self.session.save_active_record():
                    record_id = self.session.get_active_record_id()
                    self.view.log_message(
                        f"Results saved to database (ID: {record_id})"
                    )
                    # Emit signal with updated record after progression/save.
                    self.phase_completed.emit(self.session.get_active_record())
                else:
                    self.view.log_message("Warning: Failed to save to database")

                self.view.log_message("Updating UI with phase results...")
                self._append_measurement_history()
                self.view._update_local_results(
                    self.context.record.piezo_pre_rf
                )
                self.view._update_stored_readout(
                    self.context.record.piezo_pre_rf
                )
                self.view.log_message("UI updated with stored data")
            else:
                self.view.log_message(
                    "Warning: No piezo_pre_rf data to display"
                )

        except Exception as exc:
            import traceback

            self.view.log_message(f"Warning: Failed to save results: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            if self._active_phase_instance_id is not None:
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.PIEZO_PRE_RF,
                    error_message=str(exc),
                )
        finally:
            self._active_phase_instance_id = None

        self.view.run_button.setEnabled(True)
        self.view.pause_button.setEnabled(False)
        self.view.abort_button.setEnabled(False)
        self._set_next_button_enabled(False)

    def on_phase_failed(self, error_msg: str) -> None:
        """Handle phase failure."""
        # Reset pause and step mode state
        self._paused = False
        self._step_mode = False
        self._step_executing = False
        self._current_step_index = 0

        self.view.log_message(f"Phase failed: {error_msg}")
        self.view.local_phase_status.setText("FAILED")
        self._update_toolbar_state("error")

        try:
            if self.phase:
                self.phase.finalize_phase()

            if self.session.save_active_record():
                self.view.log_message("Partial results saved to database")

            if self._active_phase_instance_id is not None:
                snapshot = None
                if self.context and self.context.record.piezo_pre_rf:
                    snapshot = self.context.record.piezo_pre_rf.to_dict()

                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.PIEZO_PRE_RF,
                    error_message=error_msg,
                    artifact_payload=snapshot,
                )

            if self.context and self.context.record.piezo_pre_rf:
                self._append_measurement_history(error_msg=error_msg)
                self.view._update_local_results(
                    self.context.record.piezo_pre_rf
                )
                self.view._update_stored_readout(
                    self.context.record.piezo_pre_rf
                )

        except Exception as exc:
            import traceback

            self.view.log_message(
                f"Warning: Failed to save partial results: {exc}"
            )
            self.view.log_message(f"Traceback: {traceback.format_exc()}")
            if self._active_phase_instance_id is not None:
                self.session.fail_active_phase_instance(
                    phase_instance_id=self._active_phase_instance_id,
                    phase=CommissioningPhase.PIEZO_PRE_RF,
                    error_message=str(exc),
                )
        finally:
            self._active_phase_instance_id = None

        self.view.run_button.setEnabled(True)
        self.view.pause_button.setEnabled(False)
        self.view.abort_button.setEnabled(False)
        self._set_next_button_enabled(False)
        self.view.show_error(f"Test failed: {error_msg}")

    def _get_operator(self) -> str:
        """Get the currently selected operator from the view or parent."""
        if hasattr(self.view, "get_current_operator"):
            operator = self.view.get_current_operator()
            if operator:
                return operator

        return ""

    def _append_measurement_history(self, error_msg: str | None = None) -> None:
        """Add measurement to history.

        Notes are added manually by users via the UI, not automatically.
        Only error messages are auto-added as notes.
        """
        if not (self.context and self.context.record.piezo_pre_rf):
            return

        # Only auto-add notes for errors
        notes = f"Phase failed: {error_msg}" if error_msg else None

        self.session.add_measurement_to_history(
            CommissioningPhase.PIEZO_PRE_RF,
            self.context.record.piezo_pre_rf,
            operator=self._get_operator(),
            notes=notes,
            phase_instance_id=self._active_phase_instance_id,
        )

    def on_abort(self) -> None:
        """Handle abort button click."""
        if self.context:
            self.context.request_abort()
            self.view.log_message("Abort requested...")
            self.view.abort_button.setEnabled(False)

    def _set_next_button_enabled(self, enabled: bool) -> None:
        """Safely enable/disable next step button."""
        if hasattr(self.view, "next_step_btn"):
            self.view.next_step_btn.setEnabled(enabled)

    def _update_toolbar_state(self, state: str) -> None:
        """Safely update toolbar state."""
        if hasattr(self.view, "ui") and hasattr(
            self.view.ui, "update_toolbar_state"
        ):
            self.view.ui.update_toolbar_state(state)

    def on_pause_test(self) -> None:
        """Handle pause button click."""
        if self._paused:
            # Resume
            self._paused = False
            self.view.log_message("Test resumed...")
            self.view.pause_button.setText("⏸ Pause")
            self._update_toolbar_state("running")
        else:
            # Pause
            self._paused = True
            self.view.log_message("Test paused...")
            self.view.pause_button.setText("▶ Resume")
            self._update_toolbar_state("paused")

    def on_toggle_step_mode(self) -> None:
        """Handle step mode toggle."""
        self._step_mode = not self._step_mode
        if self._step_mode:
            self.view.log_message(
                "✓ Step mode enabled - Start Test, then use 'Next' to execute steps"
            )
            # Next button will be enabled when test starts
        else:
            self.view.log_message("Step mode disabled")
            self._set_next_button_enabled(False)
            self._step_executing = False

    def on_next_step(self) -> None:
        """Handle next step button click."""
        if not self._step_mode or self._step_executing:
            return

        if self._current_step_index >= len(self._steps):
            self.view.log_message("All steps completed!")
            return

        step_name = self._steps[self._current_step_index]
        self._step_executing = True
        self._set_next_button_enabled(False)

        def execute_step():
            try:
                success = self._execute_single_step(step_name)
                self._current_step_index += 1

                if success and self._current_step_index < len(self._steps):
                    # More steps to execute
                    next_step = self._steps[self._current_step_index]
                    self.view.log_message(
                        f"Ready for step {self._current_step_index + 1}/{len(self._steps)}: {next_step}"
                    )
                    self._set_next_button_enabled(True)
                elif success:
                    # All steps done
                    self.view.log_message("All steps completed. Finalizing...")
                    self._finalize_phase_execution()
                else:
                    # Step failed
                    self.on_phase_failed("Step execution failed")
            except Exception as exc:
                import traceback

                self.view.log_message(f"Error: {exc}\n{traceback.format_exc()}")
                self.on_phase_failed(str(exc))
            finally:
                self._step_executing = False

        QTimer.singleShot(100, execute_step)

    def _notify_parent_record_created(self, record, record_id: int) -> None:
        """Notify parent container that a record was created."""
        self.view._notify_parent_of_record_update(record, "Record created")
        self.view.log_message("Notified parent container of new record")
