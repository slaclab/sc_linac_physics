"""Controller for Piezo Pre-RF display logic."""

from datetime import datetime
from typing import Optional

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    PhaseStatus,
    PhaseContext,
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_pre_rf import (
    PiezoPreRFPhase,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.database_browser_dialog import (
    DatabaseBrowserDialog,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class PiezoPreRFController:
    """Owns phase execution and PV wiring for the display."""

    def __init__(self, view, session: CommissioningSession) -> None:
        self.view = view
        self.session = session

        self.context: Optional[PhaseContext] = None
        self.phase: Optional[PiezoPreRFPhase] = None
        self.machine: Optional[Machine] = None

    def setup_pv_connections(self) -> None:
        """Connect to PVs based on active record's cavity.

        PVs are updated when a record is loaded/started.
        """
        # Initial update if there's an active record
        if self.session.has_active_record():
            self.update_pv_addresses()

    def _resolve_cavity_selection(
        self, cryomodule: Optional[str], cavity_number: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Resolve cavity selection from arguments or parent dropdowns."""
        if cryomodule is not None and cavity_number is not None:
            return cryomodule, cavity_number

        parent = self.view.parent()
        while parent:
            if hasattr(parent, "cryomodule_combo") and hasattr(
                parent, "cavity_combo"
            ):
                selected_cm = parent.cryomodule_combo.currentText()
                selected_cavity = parent.cavity_combo.currentText()
                if (
                    selected_cm == "Select CM..."
                    or selected_cavity == "Select Cav..."
                ):
                    return None, None
                return selected_cm, selected_cavity
            parent = parent.parent()

        return None, None

    def _get_piezo_from_selection(
        self, cryomodule: str, cavity_number: str
    ) -> tuple[CommissioningPiezo, int, int]:
        """Return piezo object and parsed CM/CAV numbers from selection."""
        cav = int(cavity_number)
        cm = int(cryomodule)

        if not self.machine:
            self.machine = Machine(piezo_class=CommissioningPiezo)

        cm_str = f"{cm:02d}"
        cryomodule_obj = self.machine.cryomodules[cm_str]
        cavity = cryomodule_obj.cavities[cav]
        return cavity.piezo, cm, cav

    def update_pv_addresses(
        self, cryomodule: str = None, cavity_number: str = None
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

            pv_mapping = {
                self.view.pv_overall: piezo.prerf_test_status_pv,
                self.view.pv_cha_status: piezo.prerf_cha_status_pv,
                self.view.pv_chb_status: piezo.prerf_chb_status_pv,
                self.view.pv_cha_cap: piezo.capacitance_a_pv,
                self.view.pv_chb_cap: piezo.capacitance_b_pv,
            }

            for widget, pv_addr in pv_mapping.items():
                widget.channel = f"ca://{pv_addr}"

            # Log with formatted cavity name
            from sc_linac_physics.utils.sc_linac.linac_utils import (
                get_linac_for_cryomodule,
            )

            linac = get_linac_for_cryomodule(cryomodule)
            cavity_display_name = (
                f"{linac}_CM{cryomodule}_CAV{cavity_number}"
                if linac
                else f"CM{cryomodule}_CAV{cavity_number}"
            )

            self.view.log_message(
                f"PVs updated for {cavity_display_name} (CM{cm:02d} Cav{cav})"
            )

        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

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

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": cavity},
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
        self.view.abort_button.setEnabled(True)
        self.view.local_phase_status.setText("RUNNING")

    def _get_selected_cavity_info(self) -> Optional[tuple[str, int, int]]:
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
            self.machine = Machine(linac_section="L1B")
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

    def _get_cavity_from_parent(self) -> tuple[Optional[str], Optional[str]]:
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
        """Execute the phase through PhaseBase.run()."""
        if not self.context or not self.phase:
            self.view.show_error("No phase context available to run")
            return

        self.context.progress_callback = (
            lambda step, prog: self.view.step_progress_signal.emit(step, prog)
        )

        def run_phase():
            try:
                success = self.phase.run()
                if success:
                    self.on_phase_completed()
                else:
                    self.on_phase_failed("Phase execution failed")
            except Exception as exc:
                import traceback

                self.view.log_message(
                    f"Exception: {exc}\n{traceback.format_exc()}"
                )
                self.on_phase_failed(str(exc))

        QTimer.singleShot(100, run_phase)

    def on_phase_completed(self) -> None:
        """Handle phase completion."""
        self.view.log_message("Phase completed successfully")
        self.view.local_phase_status.setText("COMPLETED")
        self.view.local_progress_bar.setValue(100)

        try:
            if self.session.save_active_record():
                record_id = self.session.get_active_record_id()
                self.view.log_message(
                    f"Results saved to database (ID: {record_id})"
                )
            else:
                self.view.log_message("Warning: Failed to save to database")

            if self.context and self.context.record.piezo_pre_rf:
                self._append_measurement_history()
                self.view._update_local_results(
                    self.context.record.piezo_pre_rf
                )
            else:
                self.view.log_message(
                    "Warning: No piezo_pre_rf results available"
                )

            # Notify display to propagate phase completion to parent
            self.view.on_phase_completed()

        except Exception as exc:
            import traceback

            self.view.log_message(f"Warning: Failed to save results: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

        self.view.run_button.setEnabled(True)
        self.view.abort_button.setEnabled(False)

    def on_phase_failed(self, error_msg: str) -> None:
        """Handle phase failure."""
        self.view.log_message(f"Phase failed: {error_msg}")
        self.view.local_phase_status.setText("FAILED")

        if self.context:
            self.context.record.overall_status = "failed"
            self.context.record.end_time = datetime.now()
            self.context.record.set_phase_status(
                CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.FAILED
            )

        try:
            if self.phase:
                self.phase.finalize_phase()

            if self.session.save_active_record():
                self.view.log_message("Partial results saved to database")

            if self.context and self.context.record.piezo_pre_rf:
                self._append_measurement_history(error_msg=error_msg)
                self.view._update_local_results(
                    self.context.record.piezo_pre_rf
                )

        except Exception as exc:
            import traceback

            self.view.log_message(
                f"Warning: Failed to save partial results: {exc}"
            )
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

        self.view.run_button.setEnabled(True)
        self.view.abort_button.setEnabled(False)
        self.view.show_error(f"Test failed: {error_msg}")

    def _get_operator(self) -> str:
        """Get the currently selected operator from the view or parent."""
        # Try new method first (gets from parent container)
        if hasattr(self.view, "get_current_operator"):
            operator = self.view.get_current_operator()
            if operator:
                return operator

        # Fallback to old method for backward compatibility
        if hasattr(self.view, "get_selected_operator"):
            operator = self.view.get_selected_operator()
            if operator:
                return operator

        return ""

    def _append_measurement_history(
        self, error_msg: Optional[str] = None
    ) -> None:
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
        )

    def on_abort(self) -> None:
        """Handle abort button click."""
        if self.context:
            self.context.request_abort()
            self.view.log_message("Abort requested...")
            self.view.abort_button.setEnabled(False)

    def on_save_report(self) -> None:
        """Display saved results from database."""
        record = self.session.get_active_record()
        if not record:
            self.view.show_info(
                "No Results", "No test results available to display."
            )
            return

        record_id = self.session.get_active_record_id()
        msg = "Test results saved to database\n\n"
        msg += f"Record ID: {record_id}\n"
        msg += f"Cavity: {record.full_cavity_name}\n"
        msg += f"Status: {record.overall_status}\n"

        if record.piezo_pre_rf:
            result = record.piezo_pre_rf
            msg += "\nResults:\n"
            msg += (
                f"  Channel A: {'PASS' if result.channel_a_passed else 'FAIL'}"
            )
            if result.capacitance_a:
                msg += f" ({result.capacitance_a * 1e9:.1f} nF)\n"
            else:
                msg += "\n"
            msg += (
                f"  Channel B: {'PASS' if result.channel_b_passed else 'FAIL'}"
            )
            if result.capacitance_b:
                msg += f" ({result.capacitance_b * 1e9:.1f} nF)\n"
            else:
                msg += "\n"

        self.view.show_info("Test Results", msg)

    def on_view_database(self) -> None:
        """Open database browser to select and load a record."""
        dialog = DatabaseBrowserDialog(self.session.database, self.view)

        if dialog.exec_() == QDialog.Accepted:
            record_id, record_data = dialog.get_selected_record()

            if record_id and record_data:
                try:
                    full_record = self.session.load_record(record_id)

                    if full_record:
                        self.view._display_loaded_record(full_record, record_id)
                        self.view.log_message(
                            f"Loaded record ID {record_id} from database"
                        )
                        # Update PVs for the loaded cavity
                        self.update_pv_addresses()

                        # Notify parent container
                        self._notify_parent_record_loaded(
                            full_record, record_id
                        )
                    else:
                        self.view.show_error(
                            f"Failed to load record {record_id}"
                        )

                except Exception as exc:
                    import traceback

                    self.view.show_error(f"Error loading record: {exc}")
                    self.view.log_message(
                        f"Traceback: {traceback.format_exc()}"
                    )

    def _notify_parent_record_created(self, record, record_id: int) -> None:
        """Notify parent container that a record was created.

        This updates the parent's UI to reflect the new active record.
        """
        parent = self.view.parent()
        while parent:
            class_name = parent.__class__.__name__

            # Update parent's UI elements
            if hasattr(parent, "update_progress_indicator"):
                parent.update_progress_indicator(record)

            if hasattr(parent, "_update_tab_states"):
                parent._update_tab_states()

            if hasattr(parent, "_load_notes"):
                parent._load_notes()

            if hasattr(parent, "_update_sync_status"):
                parent._update_sync_status(True, "Record created")

            # REMOVED: Settings save - no auto-restore on next launch

            # Only notify the immediate multi-phase container
            if class_name == "MultiPhaseCommissioningDisplay":
                self.view.log_message("Notified parent container of new record")
                break

            parent = parent.parent()

    def _notify_parent_record_loaded(self, record, record_id: int) -> None:
        """Notify parent container that a record was loaded.

        This updates the parent's UI to reflect the loaded record.
        """
        parent = self.view.parent()
        while parent:
            class_name = parent.__class__.__name__

            # Update parent's UI elements
            if hasattr(parent, "update_progress_indicator"):
                parent.update_progress_indicator(record)

            if hasattr(parent, "_update_tab_states"):
                parent._update_tab_states()

            if hasattr(parent, "_load_notes"):
                parent._load_notes()

            if hasattr(parent, "_update_sync_status"):
                parent._update_sync_status(True, "Record loaded")

            # REMOVED: Settings save - no auto-restore

            # Only notify the immediate multi-phase container
            if class_name == "MultiPhaseCommissioningDisplay":
                self.view.log_message(
                    "Notified parent container of loaded record"
                )
                break

            parent = parent.parent()
