"""Piezo Pre-RF commissioning display."""

from PyQt5.QtCore import pyqtSlot

from sc_linac_physics.applications.rf_commissioning.controllers.piezo_pre_rf_controller import (
    PiezoPreRFController,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    LOCAL_CAP_STYLE,
    LOCAL_LABEL_STYLE,
    PiezoPreRFUI,
)

from .base_placeholder import BasePlaceholderDisplay


class PiezoPreRFDisplay(BasePlaceholderDisplay):
    """Display for Piezo Pre-RF phase (fully implemented)."""

    UI_CLASS = PiezoPreRFUI
    PHASE_NAME = "Piezo Pre-RF"
    DATA_ATTR = "piezo_pre_rf"
    DATA_MODEL = PiezoPreRFCheck

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle("Piezo Pre-RF Test - PyDM")

        self.controller = PiezoPreRFController(self, self.session)
        if hasattr(self.controller, "phase_completed"):
            self.controller.phase_completed.connect(
                self._on_controller_phase_completed
            )
        if hasattr(self.controller, "setup_pv_connections"):
            self.controller.setup_pv_connections()

    def setup_ui(self):
        """Create the main UI layout."""
        callbacks = {
            "toggle_piezo_enable": self.toggle_piezo_enable,
            "toggle_manual_mode": self.toggle_manual_mode,
            "on_run_automated_test": self.on_run_automated_test,
            "on_abort_test": self.on_abort,
            "on_pause_test": self.on_pause_test,
            "on_toggle_step_mode": self.on_toggle_step_mode,
            "on_next_step": self.on_next_step,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Refresh display when active record changes."""
        result = record.piezo_pre_rf
        if result:
            self._update_local_results(result)
        else:
            self.clear_results()

        self._update_stored_readout(result)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Update display when a record is loaded."""
        if hasattr(self.controller, "update_pv_addresses"):
            self.controller.update_pv_addresses(
                record.cryomodule, str(record.cavity_number)
            )
        self.refresh_from_record(record)

    def _on_controller_phase_completed(self, record):
        """Handle phase completion from controller - notify parent container."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

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

        if hasattr(self, "local_cha_result"):
            self.local_cha_result.setText(
                "PASS" if result.channel_a_passed else "FAIL"
            )
            self.local_cha_result.setStyleSheet(
                pass_style if result.channel_a_passed else fail_style
            )

        if hasattr(self, "local_chb_result"):
            self.local_chb_result.setText(
                "PASS" if result.channel_b_passed else "FAIL"
            )
            self.local_chb_result.setStyleSheet(
                pass_style if result.channel_b_passed else fail_style
            )

        if hasattr(self, "local_overall_result"):
            self.local_overall_result.setText(
                "PASS" if result.passed else "FAIL"
            )
            overall_style = (
                pass_style if result.passed else fail_style
            ) + "font-weight: bold;"
            self.local_overall_result.setStyleSheet(overall_style)

        if hasattr(self, "local_phase_status"):
            self.local_phase_status.setText(
                "Complete" if result.passed else "Incomplete"
            )

    def _update_stored_readout(self, result: PiezoPreRFCheck | None) -> None:
        """Update stored-data labels from the record dataclass."""
        if result is None:
            self._clear_phase_specific_readouts()
            return

        self._set_generic_stored_data(result)
        self._apply_phase_specific_readouts(result)

    def clear_results(self):
        """Clear all result displays."""
        super().clear_results()

        if hasattr(self, "local_cha_result"):
            self.local_cha_result.setText("-")
            self.local_cha_result.setStyleSheet(LOCAL_LABEL_STYLE)
        if hasattr(self, "local_chb_result"):
            self.local_chb_result.setText("-")
            self.local_chb_result.setStyleSheet(LOCAL_LABEL_STYLE)
        if hasattr(self, "local_cha_cap"):
            self.local_cha_cap.setText("-")
            self.local_cha_cap.setStyleSheet(LOCAL_CAP_STYLE)
        if hasattr(self, "local_chb_cap"):
            self.local_chb_cap.setText("-")
            self.local_chb_cap.setStyleSheet(LOCAL_CAP_STYLE)
        if hasattr(self, "local_overall_result"):
            self.local_overall_result.setText("-")
            self.local_overall_result.setStyleSheet(
                LOCAL_LABEL_STYLE + "font-weight: bold;"
            )

        self._clear_generic_stored_data()
        if hasattr(self, "local_stored_cap_a"):
            self.local_stored_cap_a.setText("-")
        if hasattr(self, "local_stored_cap_b"):
            self.local_stored_cap_b.setText("-")

    def update_piezo_readbacks(self, piezo) -> None:
        """No-op: PyDM widgets are the source of truth for readbacks."""
        return

    @pyqtSlot()
    def toggle_piezo_enable(self):
        """Toggle piezo enable/disable state."""
        self.log_message("Use the PyDM enable control for PV writes")

    @pyqtSlot()
    def toggle_manual_mode(self):
        """Toggle manual/feedback mode."""
        self.log_message("Use the PyDM mode control for PV writes")

    @pyqtSlot()
    def on_run_automated_test(self):
        """Handle Run Automated Test button click."""
        self.controller.on_run_automated_test()

    @pyqtSlot()
    def on_abort(self):
        """Handle abort button click."""
        self.controller.on_abort()

    @pyqtSlot()
    def on_pause_test(self):
        """Handle pause button click."""
        self.controller.on_pause_test()

    @pyqtSlot()
    def on_toggle_step_mode(self):
        """Handle step mode toggle."""
        self.controller.on_toggle_step_mode()

    @pyqtSlot()
    def on_next_step(self):
        """Handle next step button click."""
        self.controller.on_next_step()
