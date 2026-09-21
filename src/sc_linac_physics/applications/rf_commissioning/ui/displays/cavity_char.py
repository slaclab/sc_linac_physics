"""Cavity Characterization commissioning display."""

from PyQt5.QtCore import pyqtSlot

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    CavityCharController,
)

from .base_placeholder import BasePlaceholderDisplay


class CavityCharDisplay(BasePlaceholderDisplay):
    """Display for the Cavity Characterization phase."""

    UI_CLASS = CavityCharUI
    PHASE_NAME = "Cavity Characterization"
    DATA_ATTR = "cavity_char"
    DATA_MODEL = CavityCharacterization

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle("Cavity Characterization - PyDM")

        # Set by the controller when a record loads. The panel renders the
        # measured loaded Q against this rather than a hard-coded pair,
        # because the window differs by cavity class.
        self.cavity_loaded_q_window: tuple[float, float] | None = None

        self.controller = CavityCharController(self, self.session)
        self.controller.elapsed_updated.connect(self._on_elapsed)
        self.controller.phase_completed.connect(
            self._on_controller_phase_completed
        )

        # BasePlaceholderDisplay.__init__ calls setup_ui() before this point,
        # so the controller does not exist while the widgets are built. The
        # 15% cap lives in CavityCharLimits, which the builder cannot see, so
        # it is applied here.
        self._apply_drive_level_limits()

        self.controller.setup_pv_connections()

    # Probe Q is declared on CavityCharacterization as a phase_display_field,
    # so the generic Stored Data section renders a row for it. The phase never
    # fills it: QPROBE_CALC1.PROC triggers the calculation and there is no
    # readback PV to read the answer from, and no PUSH_QPROBE to push it with
    # (see CavityCharPhase._read_probe_q). A row that can never fill reads as
    # missing data an operator should chase, so it is dropped here rather than
    # by changing the record model — the field stays, ready for the PVs.
    _OMITTED_STORED_FIELDS = ("cavity_probe_q",)

    @classmethod
    def get_phase_stored_field_specs(cls):
        return [
            spec
            for spec in super().get_phase_stored_field_specs()
            if spec.widget_name not in cls._OMITTED_STORED_FIELDS
        ]

    def _apply_drive_level_limits(self) -> None:
        limits = self.controller.limits
        self.drive_level_spinbox.setMaximum(limits.max_drive_level)
        self.drive_level_spinbox.setValue(limits.default_drive_level)

    def setup_ui(self):
        callbacks = {
            "on_run_automated_test": self.on_run_characterization,
            "on_pause_test": self.on_pause_test,
            "on_abort_test": self.on_abort,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        self._update_stored_readout(record.cavity_char)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        self.controller.update_pv_addresses(
            record.cryomodule, str(record.cavity_number)
        )
        self.refresh_from_record(record)

    def _update_stored_readout(self, result) -> None:
        if result is None:
            self._clear_phase_specific_readouts()
            return
        self._set_generic_stored_data(result)
        self._apply_phase_specific_readouts(result)

    def _on_controller_phase_completed(self, record):
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

    # ------------------------------------------------------------------
    # Live status
    # ------------------------------------------------------------------

    def set_char_status(self, text: str) -> None:
        """Show the backend's message unmodified.

        A crash and a timeout both arrive as FAILED and are told apart only
        by this text, so it is not reworded here.
        """
        if hasattr(self, "char_status_label"):
            self.char_status_label.setText(text)

    def _on_elapsed(self, seconds: float) -> None:
        """Elapsed against the timeout — not a fraction of the work done.

        PROBECALSTS reports running or crashed and nothing in between.
        """
        limit = self.controller.limits.characterization_timeout_seconds
        if hasattr(self, "elapsed_label"):
            self.elapsed_label.setText(f"{seconds:.0f} s / {limit:.0f} s")

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    @pyqtSlot()
    def on_run_characterization(self):
        self.controller.on_run_characterization()

    @pyqtSlot()
    def on_abort(self):
        self.controller.on_abort()

    @pyqtSlot()
    def on_pause_test(self):
        self.controller.on_pause_test()
