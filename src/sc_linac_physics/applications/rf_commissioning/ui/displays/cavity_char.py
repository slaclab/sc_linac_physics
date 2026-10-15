"""Cavity Characterization commissioning display."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QMessageBox

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
        self.controller.results_ready.connect(self.on_results_ready)
        self.controller.push_finished.connect(self._on_push_finished)

        # BasePlaceholderDisplay.__init__ calls setup_ui() before this point,
        # so the controller does not exist while the widgets are built. The
        # 15% cap lives in CavityCharLimits, which the builder cannot see, so
        # it is applied here.
        self._apply_drive_level_limits()

        self.controller.setup_pv_connections()

    def _apply_drive_level_limits(self) -> None:
        limits = self.controller.limits
        self.drive_level_spinbox.setMaximum(limits.max_drive_level)
        self.drive_level_spinbox.setValue(limits.default_drive_level)

    def setup_ui(self):
        callbacks = {
            "on_run_automated_test": self.on_run_characterization,
            "on_pause_test": self.on_pause_test,
            "on_abort_test": self.on_abort,
            "on_push_results": self.on_push_results,
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
        """Fill Stored Data and the review rows. Never enables Push.

        The push gate lives on the phase that read the values, so values
        loaded from the database need a fresh measurement before a push.
        """
        self._update_stored_readout(record.cavity_char)
        data = record.cavity_char
        self._render_results(
            {
                "loaded_q": getattr(data, "loaded_q", None),
                "scale_factor": getattr(data, "scale_factor", None),
                "probe_q": getattr(data, "probe_q", None),
                "loaded_q_in_tolerance": getattr(
                    data, "loaded_q_in_tolerance", None
                ),
                "scale_factor_in_tolerance": getattr(
                    data, "scale_factor_in_tolerance", None
                ),
            }
        )

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        # A measurement reviewed for the previous record must not stay
        # pushable: the push would go to the cavity that phase measured.
        self.controller.drop_reviewed_measurement()
        self._last_results = None
        self.push_results_button.setEnabled(False)
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
        self._reset_push_button()
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

    # ------------------------------------------------------------------
    # Review and push
    # ------------------------------------------------------------------

    def on_results_ready(self, data: dict) -> None:
        """A run just read its values: show them and allow a push."""
        self._render_results(data)
        self._last_results = data
        self.push_results_button.setEnabled(data.get("loaded_q") is not None)

    def _render_results(self, data: dict) -> None:
        def fmt(value, spec):
            return "-" if value is None else format(value, spec)

        self.loaded_q_label.setText(fmt(data.get("loaded_q"), ".1e"))
        self.scale_factor_label.setText(fmt(data.get("scale_factor"), ".1f"))
        self.probe_q_label.setText(fmt(data.get("probe_q"), ".1e"))
        window = self.cavity_loaded_q_window
        self.q_window_label.setText(
            "-" if window is None else f"{window[0]:.1e} – {window[1]:.1e}"
        )
        self.tolerance_label.setText(self._tolerance_text(data))

    @staticmethod
    def _tolerance_text(data: dict) -> str:
        """From the flags read_results recorded, not recomputed here."""
        flags = (
            ("loaded Q", data.get("loaded_q_in_tolerance")),
            ("scale factor", data.get("scale_factor_in_tolerance")),
        )
        if any(ok is None for _, ok in flags):
            return "-"
        outside = [name for name, ok in flags if not ok]
        if not outside:
            return "Both in tolerance"
        return f"Outside tolerance: {', '.join(outside)}"

    def _cavity_label(self) -> str:
        """The cavity the push writes to: the one the phase measured."""
        phase = self.controller.phase
        if phase is None or phase.cavity is None:
            return "the measured cavity"
        return str(phase.cavity)

    def _confirm_push_text(self, data: dict) -> str:
        """The values Yes pushes, by label.

        PV names are left out on review (#395): the operator reads this
        before saying Yes. The writes are CavityCharPhase._push_results':
        PUSH_QLOADED.PROC, PUSH_CAV_SCALE.PROC and PUSH_QPROBECALC.PROC.
        """
        text = (
            f"Push these values to {self._cavity_label()}?\n\n"
            f"  Loaded Q: {data['loaded_q']:.1e}\n"
            f"  Scale factor: {data['scale_factor']:.1f}\n"
            f"  Probe Q: {data['probe_q']:.1e}\n\n"
            "They replace the loaded Q, scale factor and probe Q the cavity "
            "uses now."
        )
        tolerance = self._tolerance_text(data)
        if tolerance.startswith("Outside"):
            text += f"\n\n{tolerance}. Pushing anyway is your call."
        return text

    def _ask_confirm(self, text: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Push characterization results",
                text,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )

    @pyqtSlot()
    def on_push_results(self):
        if self.controller._unsaved_push:
            # Retry Save: database writes only, so no confirm.
            self.controller.on_push_results()
            return
        data = getattr(self, "_last_results", None)
        if data is None:
            return
        if self._ask_confirm(self._confirm_push_text(data)):
            self.controller.on_push_results()

    def offer_save_retry(self) -> None:
        """A push reached the cavity but saving it failed."""
        self.push_results_button.setText("Retry Save")
        self.push_results_button.setEnabled(True)

    def _reset_push_button(self) -> None:
        self.push_results_button.setText("Push to Cavity…")
        self.push_results_button.setEnabled(False)

    def is_running_phase(self) -> bool:
        """True while a measurement or push is running.

        The container refuses to change the active record meanwhile: every
        save and phase-instance call goes to the session's active record.
        """
        return self.controller._running

    def on_cavity_changed(self) -> None:
        """Another cavity was selected: clear what belonged to the last one.

        Phase History is this session's log for the previous cavity, and an
        unpushed measurement is no longer pushable (the controller has
        already dropped it).
        """
        self.clear_results()
        self._last_results = None
        self.push_results_button.setEnabled(False)
        self._render_results({})
        for name in ("char_status_label", "elapsed_label"):
            getattr(self, name).setText("-")

    def _on_push_finished(self, success: bool, message: str) -> None:
        if success:
            self._last_results = None
            self.push_results_button.setEnabled(False)

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
