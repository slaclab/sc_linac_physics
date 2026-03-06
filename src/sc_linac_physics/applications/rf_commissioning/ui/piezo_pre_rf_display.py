"""
Piezo Pre-RF Test Display for LCLS-II SC Linac
PyDM-compatible display for running piezo pre-RF tests with live PV readouts
"""

from datetime import datetime
from typing import Optional

from PyQt5.QtCore import pyqtSlot, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QMessageBox,
)

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.controllers.piezo_pre_rf_controller import (
    PiezoPreRFController,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)
from sc_linac_physics.applications.rf_commissioning.ui.ui_builder import (
    PiezoPreRFUI,
    LOCAL_CAP_STYLE,
    LOCAL_LABEL_STYLE,
)


class PiezoPreRFDisplay(PhaseDisplayBase):
    """PyDM Display for Piezo Pre-RF Testing."""

    step_progress_signal = pyqtSignal(str, int)  # (step_name, progress)

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle("Piezo Pre-RF Test - PyDM")

        self.session = session or CommissioningSession()
        self.controller = PiezoPreRFController(self, self.session)

        self.step_progress_signal.connect(self._on_step_progress)

        self.setup_ui()
        self.controller.setup_pv_connections()

    def setup_ui(self):
        """Create the main UI layout."""
        callbacks = {
            "toggle_piezo_enable": self.toggle_piezo_enable,
            "toggle_manual_mode": self.toggle_manual_mode,
            "on_run_automated_test": self.on_run_automated_test,
            "on_view_database": self.on_view_database,
        }
        self.ui = PiezoPreRFUI(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    def _bind_ui_widgets(self) -> None:
        for name, widget in self.ui.widgets.items():
            setattr(self, name, widget)

    def get_current_operator(self) -> Optional[str]:
        """Get the current operator from parent container."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "operator_combo"):
                operator = parent.operator_combo.currentData()
                if operator and operator != "__add__":
                    return operator
            parent = parent.parent()
        return None

    def get_current_cavity(self) -> Optional[tuple[str, str]]:
        """Get current cavity info from active record.

        Returns:
            Tuple of (cavity_name, cryomodule) or None
        """
        if self.session.has_active_record():
            record = self.session.get_active_record()
            return (record.short_cavity_name, record.cryomodule)
        return None

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Refresh display when active record changes.

        Note: PV connections are handled separately by cavity selection dropdowns,
        not by the active record.
        """
        pass

    def _on_step_progress(self, step_name: str, progress: int):
        """Handle step progress updates."""
        self.local_current_step.setText(step_name)
        self.local_progress_bar.setValue(progress)
        self.log_message(f"Executing step: {step_name}")

    def _update_local_results(self, result: PiezoPreRFCheck):
        """Update local result displays (orange-bordered widgets on right panel)."""
        pass_style = (
            LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
            + "color: #90ee90; font-weight: bold;"
        )
        fail_style = (
            LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c1a1a")
            + "color: #ff6b6b; font-weight: bold;"
        )

        # Channel A
        self.local_cha_result.setText(
            "PASS" if result.channel_a_passed else "FAIL"
        )
        self.local_cha_result.setStyleSheet(
            pass_style if result.channel_a_passed else fail_style
        )

        if result.capacitance_a:
            self.local_cha_cap.setText(f"{result.capacitance_a * 1e9:.1f} nF")

        # Channel B
        self.local_chb_result.setText(
            "PASS" if result.channel_b_passed else "FAIL"
        )
        self.local_chb_result.setStyleSheet(
            pass_style if result.channel_b_passed else fail_style
        )

        if result.capacitance_b:
            self.local_chb_cap.setText(f"{result.capacitance_b * 1e9:.1f} nF")

        # Overall
        self.local_overall_result.setText("PASS" if result.passed else "FAIL")
        overall_style = (
            pass_style if result.passed else fail_style
        ) + "font-weight: bold;"
        self.local_overall_result.setStyleSheet(overall_style)

    def clear_results(self):
        """Clear all result displays."""
        self.local_cha_result.setText("-")
        self.local_chb_result.setText("-")
        self.local_cha_cap.setText("-")
        self.local_chb_cap.setText("-")
        self.local_overall_result.setText("-")

        self.local_cha_result.setStyleSheet(LOCAL_LABEL_STYLE)
        self.local_chb_result.setStyleSheet(LOCAL_LABEL_STYLE)
        self.local_overall_result.setStyleSheet(
            LOCAL_LABEL_STYLE + "font-weight: bold;"
        )
        self.local_cha_cap.setStyleSheet(LOCAL_CAP_STYLE)
        self.local_chb_cap.setStyleSheet(LOCAL_CAP_STYLE)

        self.history_text.clear()
        self.local_progress_bar.setValue(0)
        self.local_current_step.setText("-")
        self.local_phase_status.setText("-")

    def log_message(self, message):
        """Add a message to the history log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history_text.append(f"[{timestamp}] {message}")

    def show_error(self, message):
        """Show error message dialog."""
        QMessageBox.critical(self, "Error", message)

    def show_info(self, title: str, message: str) -> None:
        """Show info message dialog."""
        QMessageBox.information(self, title, message)

    # ==================== SLOT METHODS ====================

    @pyqtSlot()
    def toggle_piezo_enable(self):
        """Toggle piezo enable/disable state."""
        if self.enable_disable_btn.isChecked():
            self.enable_disable_btn.setText("Enable")
            self.piezo_status_label.setText("Enabled")
            self.piezo_status_label.setStyleSheet(
                "QLabel { background-color: #2d5016; color: #90ee90; "
                "padding: 5px; border-radius: 3px; font-weight: bold; }"
            )
            self.log_message("Piezo enabled")
        else:
            self.enable_disable_btn.setText("Disable")
            self.piezo_status_label.setText("Disabled")
            self.piezo_status_label.setStyleSheet(
                "QLabel { background-color: #3a3a3a; color: #cccccc; "
                "padding: 5px; border-radius: 3px; }"
            )
            self.log_message("Piezo disabled")

    @pyqtSlot()
    def toggle_manual_mode(self):
        """Toggle manual/feedback mode."""
        if self.manual_feedback_btn.isChecked():
            self.manual_feedback_btn.setText("Feedback")
            self.mode_status_label.setText("Manual")
            self.mode_status_label.setStyleSheet(
                "QLabel { background-color: #5c4d1a; color: #ffd700; "
                "padding: 5px; border-radius: 3px; font-weight: bold; }"
            )
            self.log_message("Manual mode activated")
        else:
            self.manual_feedback_btn.setText("Manual")
            self.mode_status_label.setText("Feedback")
            self.mode_status_label.setStyleSheet(
                "QLabel { background-color: #3a3a3a; color: #cccccc; "
                "padding: 5px; border-radius: 3px; }"
            )
            self.log_message("Feedback mode activated")

    def update_timestamp(self):
        """Update the timestamp label with current time."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_label.setText(current_time)
        self.timestamp_label.setStyleSheet("color: #888888; font-size: 9pt;")

        # Update every second
        QTimer.singleShot(1000, self.update_timestamp)

    @pyqtSlot()
    def on_run_automated_test(self):
        """Handle Run Automated Test button click."""
        self.controller.on_run_automated_test()

    @pyqtSlot()
    def on_abort(self):
        """Handle abort button click."""
        self.controller.on_abort()

    def on_phase_completed(self) -> None:
        """Notify parent container to update phase tracker."""
        # Walk up the parent hierarchy to find MultiPhaseCommissioningDisplay
        parent = self.parent()
        while parent:
            if hasattr(parent, "phase_tracker") and hasattr(
                parent.phase_tracker, "update_from_record"
            ):
                # Found the multi-phase display container
                if (
                    hasattr(parent, "session")
                    and parent.session.has_active_record()
                ):
                    record = parent.session.get_active_record()
                    parent.phase_tracker.update_from_record(record)
                    parent._update_tab_states()
                    break
            parent = parent.parent()

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Display a loaded record from database in the left panel (DB results)."""
        # Note: We're NOT updating the local (orange-bordered) results,
        # only showing what was saved in the database
        # Note: PV connections are managed separately by cavity selection dropdowns

        self.log_message(f"Displaying record for {record.full_cavity_name}")

        # Update history
        self.history_text.clear()
        self.history_text.append(
            f"=== LOADED FROM DATABASE (ID: {record_id}) ==="
        )
        self.history_text.append(f"Cavity: {record.full_cavity_name}")
        self.history_text.append(f"Cryomodule: {record.cryomodule}")
        self.history_text.append(
            f"Started: {record.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if record.end_time:
            self.history_text.append(
                f"Ended: {record.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        self.history_text.append(
            f"Overall Status: {record.overall_status.upper()}"
        )
        self.history_text.append(f"Phase: {record.current_phase.value}")

        # Show phase history
        if record.phase_history:
            self.history_text.append("\n=== PHASE HISTORY ===")
            for checkpoint in record.phase_history:
                self.history_text.append(
                    f"[{checkpoint.timestamp.strftime('%H:%M:%S')}] "
                    f"{checkpoint.phase.value}: {checkpoint.step_name}"
                )
                if checkpoint.measurements:
                    for key, value in checkpoint.measurements.items():
                        self.history_text.append(f"  {key}: {value}")

        # Show results if available
        if record.piezo_pre_rf:
            result = record.piezo_pre_rf
            self.history_text.append("\n=== PIEZO PRE-RF RESULTS ===")
            self.history_text.append(
                f"Channel A: {'PASS' if result.channel_a_passed else 'FAIL'}"
            )
            if result.capacitance_a:
                self.history_text.append(
                    f"  Capacitance: {result.capacitance_a * 1e9:.1f} nF"
                )

            self.history_text.append(
                f"Channel B: {'PASS' if result.channel_b_passed else 'FAIL'}"
            )
            if result.capacitance_b:
                self.history_text.append(
                    f"  Capacitance: {result.capacitance_b * 1e9:.1f} nF"
                )

            self.history_text.append(
                f"Overall: {'PASS' if result.passed else 'FAIL'}"
            )

            if result.notes:
                self.history_text.append(f"Notes: {result.notes}")

        self.history_text.append("\n=== END OF RECORD ===")

    def _display_loaded_record(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Backward-compatible wrapper for controller calls."""
        self.on_record_loaded(record, record_id)

    @pyqtSlot()
    def on_view_database(self):
        """Open database browser to select and load a record."""
        self.controller.on_view_database()


def main():
    """Main entry point for running the display standalone."""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PiezoPreRFDisplay()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
