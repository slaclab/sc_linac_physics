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
        """Connect spinbox changes to PV updates."""
        # QComboBox uses currentIndexChanged instead of valueChanged
        self.view.cm_spinbox.currentIndexChanged.connect(
            self.update_pv_addresses
        )
        self.view.cav_spinbox.currentIndexChanged.connect(
            self.update_pv_addresses
        )
        self.update_pv_addresses()

    def update_pv_addresses(self) -> None:
        """Update PV addresses based on current cavity selection."""
        # Get values from QComboBox (using currentText() instead of value())
        cm = int(self.view.cm_spinbox.currentText())
        cav = int(self.view.cav_spinbox.currentText())

        try:
            if not self.machine:
                self.machine = Machine(piezo_class=CommissioningPiezo)

            cm_str = f"{cm:02d}"
            cryomodule = self.machine.cryomodules[cm_str]
            cavity = cryomodule.cavities[cav]
            piezo = cavity.piezo

            pv_mapping = {
                self.view.pv_overall: piezo.prerf_test_status_pv,
                self.view.pv_cha_status: piezo.prerf_cha_status_pv,
                self.view.pv_chb_status: piezo.prerf_chb_status_pv,
                self.view.pv_cha_cap: piezo.capacitance_a_pv,
                self.view.pv_chb_cap: piezo.capacitance_b_pv,
                self.view.go_button: piezo.prerf_test_start_pv,
            }

            for widget, pv_addr in pv_mapping.items():
                widget.channel = f"ca://{pv_addr}"

        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def on_run_automated_test(self) -> None:
        """Handle Run Automated Test button click."""
        operator = self._get_operator()
        if not operator:
            self.view.show_error(
                "Please select an operator before running the test."
            )
            return

        # Get values from QComboBox
        cm = int(self.view.cm_spinbox.currentText())
        cav = int(self.view.cav_spinbox.currentText())

        cavity_name = f"L1B_CM{cm:02d}_CAV{cav}"
        self.view.log_message(f"Starting automated test for {cavity_name}")
        self.view.clear_results()

        try:
            if not self.machine:
                self.machine = Machine(linac_section="L1B")

            cavity = self.machine.cryomodules[f"{cm:02d}"].cavities[cav]

            if not self.session.has_active_record():
                record, record_id = self.session.start_new_record(
                    cavity_name=cavity_name,
                    cryomodule=f"{cm:02d}",
                )
                self.view.log_message(
                    f"Created database record ID: {record_id}"
                )
            else:
                record = self.session.get_active_record()
                record_id = self.session.get_active_record_id()
                self.view.log_message(f"Using existing record ID: {record_id}")

            can_run, reason = self.session.can_run_phase(
                CommissioningPhase.PIEZO_PRE_RF
            )
            if not can_run:
                self.view.show_error(f"Cannot run PIEZO_PRE_RF phase: {reason}")
                self.view.log_message(f"ERROR: {reason}")
                return

            self.context = PhaseContext(
                record=record,
                operator=operator,
                dry_run=self.view.dry_run_checkbox.isChecked(),
                parameters={"cavity": cavity},
            )

            self.phase = PiezoPreRFPhase(self.context)

            is_valid, message = self.phase.validate_prerequisites()
            if not is_valid:
                self.view.show_error(f"Prerequisites not met: {message}")
                self.view.log_message(f"ERROR: {message}")
                return

            self.view.run_button.setEnabled(False)
            self.view.abort_button.setEnabled(True)
            self.view.save_button.setEnabled(False)
            self.view.local_phase_status.setText("RUNNING")

            self.execute_phase_steps()

        except Exception as exc:
            import traceback

            self.view.show_error(f"Failed to start test: {exc}")
            self.view.log_message(f"Error: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

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

        except Exception as exc:
            import traceback

            self.view.log_message(f"Warning: Failed to save results: {exc}")
            self.view.log_message(f"Traceback: {traceback.format_exc()}")

        self.view.run_button.setEnabled(True)
        self.view.abort_button.setEnabled(False)
        self.view.save_button.setEnabled(True)

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
        self.view.save_button.setEnabled(True)
        self.view.show_error(f"Test failed: {error_msg}")

    def _get_operator(self) -> str:
        if hasattr(self.view, "get_selected_operator"):
            operator = self.view.get_selected_operator()
            if operator:
                return operator
        return ""

    def _get_notes(self) -> Optional[str]:
        notes = self.view.notes_input.toPlainText().strip()
        return notes or None

    def _append_measurement_history(
        self, error_msg: Optional[str] = None
    ) -> None:
        if not (self.context and self.context.record.piezo_pre_rf):
            return

        notes = self._get_notes()
        if error_msg:
            notes = (
                f"{notes}\nPhase failed: {error_msg}"
                if notes
                else f"Phase failed: {error_msg}"
            )

        self.session.add_measurement_to_history(
            CommissioningPhase.PIEZO_PRE_RF,
            self.context.record.piezo_pre_rf,
            operator=self._get_operator(),
            notes=notes,
        )

        if hasattr(self.view, "refresh_notes"):
            self.view.refresh_notes()

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
        msg += f"Cavity: {record.cavity_name}\n"
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
