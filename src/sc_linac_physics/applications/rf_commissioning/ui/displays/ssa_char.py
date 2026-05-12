"""SSA Calibration commissioning display."""

from PyQt5.QtCore import pyqtSlot

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    LOCAL_LABEL_STYLE,
    SSACharUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.ssa_char_controller import (
    SSACharController,
)

from .base_placeholder import BasePlaceholderDisplay


class SSACharDisplay(BasePlaceholderDisplay):
    """Display for SSA Calibration phase (fully implemented)."""

    UI_CLASS = SSACharUI
    PHASE_NAME = "SSA Calibration"
    DATA_ATTR = "ssa_char"
    DATA_MODEL = SSACharacterization

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle("SSA Calibration - PyDM")

        self.controller = SSACharController(self, self.session)
        if hasattr(self.controller, "phase_completed"):
            self.controller.phase_completed.connect(
                self._on_controller_phase_completed
            )
        if hasattr(self.controller, "setup_pv_connections"):
            self.controller.setup_pv_connections()

    def setup_ui(self):
        callbacks = {
            "on_run_automated_test": self.on_run_calibration,
            "on_pause_test": self.on_pause_test,
            "on_abort_test": self.on_abort,
            "on_push_slope": self.on_push_slope,
            "on_plot": self.on_plot,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        result = record.ssa_char
        if result:
            self._update_local_results(result)
        else:
            self.clear_results()
        self._update_stored_readout(result)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        if hasattr(self.controller, "update_pv_addresses"):
            self.controller.update_pv_addresses(
                record.cryomodule, str(record.cavity_number)
            )
        self.refresh_from_record(record)

    def _on_controller_phase_completed(self, record):
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

    def _update_local_results(self, result: SSACharacterization) -> None:
        pass_style = (
            LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
            + "color: #90ee90; font-weight: bold;"
        )
        fail_style = (
            LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c1a1a")
            + "color: #ff6b6b; font-weight: bold;"
        )

        if hasattr(self, "local_phase_status"):
            passed = result.calibration_passed
            self.local_phase_status.setText("PASS" if passed else "FAIL")
            self.local_phase_status.setStyleSheet(
                pass_style if passed else fail_style
            )

    def _update_stored_readout(
        self, result: SSACharacterization | None
    ) -> None:
        if result is None:
            self._clear_phase_specific_readouts()
            return
        self._set_generic_stored_data(result)
        self._apply_phase_specific_readouts(result)

    def clear_results(self):
        super().clear_results()
        if hasattr(self, "local_phase_status"):
            self.local_phase_status.setText("-")
            self.local_phase_status.setStyleSheet(LOCAL_LABEL_STYLE)
        self._clear_generic_stored_data()

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    @pyqtSlot()
    def on_run_calibration(self):
        self.controller.on_run_calibration()

    @pyqtSlot()
    def on_abort(self):
        self.controller.on_abort()

    @pyqtSlot()
    def on_pause_test(self):
        self.controller.on_pause_test()

    @pyqtSlot()
    def on_push_slope(self):
        self.controller.on_push_slope()

    @pyqtSlot()
    def on_plot(self):
        self.controller.on_plot()
