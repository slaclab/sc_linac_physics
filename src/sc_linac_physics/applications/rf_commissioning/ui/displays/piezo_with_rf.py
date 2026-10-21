"""Piezo with RF commissioning display."""

from datetime import datetime

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QInputDialog, QMessageBox

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PiezoWithRFTest,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    STATUS_LABEL_INCOMPLETE,
    STATUS_LABEL_PASS,
    PiezoWithRFUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_with_rf_controller import (  # noqa: E501
    PiezoWithRFController,
)

from .base_placeholder import BasePlaceholderDisplay


def age_text(stamp: datetime | None, now: datetime | None = None) -> str:
    """'3 h 05 min' from a timestamp; 'unknown' without one."""
    if stamp is None:
        return "unknown"
    minutes = int(((now or datetime.now()) - stamp).total_seconds() // 60)
    return f"{minutes // 60} h {minutes % 60:02d} min"


class PiezoWithRFDisplay(BasePlaceholderDisplay):
    """Display for the Piezo with RF phase."""

    UI_CLASS = PiezoWithRFUI
    PHASE_NAME = "Piezo with RF"
    DATA_ATTR = "piezo_with_rf"
    DATA_MODEL = PiezoWithRFTest

    def __init__(self, parent=None, session=None):
        super().__init__(parent, session=session)
        self.controller = PiezoWithRFController(self, self.session)
        self.controller.phase_completed.connect(self._notify_phase_advanced)
        self.controller.setup_pv_connections()

    def setup_ui(self):
        callbacks = {
            "on_run_automated_test": self.on_start_test,
            "on_pause_test": self.on_pause_test,
            "on_abort_test": self.on_abort,
            "on_toggle_step_mode": self.on_toggle_step_mode,
            "on_next_step": self.on_next_step,
            "on_push": self.on_push,
            "on_decline_push": self.on_decline_push,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()
        self.set_running(False)

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Fill Stored Data. Never enables Push: that needs a fresh read."""
        data = record.piezo_with_rf
        if data is None:
            self._clear_phase_specific_readouts()
            return
        self._set_generic_stored_data(data)
        self._apply_phase_specific_readouts(data)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        # A measurement reviewed for the previous record must not stay
        # pushable: the push would go to the cavity that phase measured.
        self.controller.drop_review()
        self.clear_review()
        self.controller.update_pv_addresses(
            record.cryomodule, str(record.cavity_number)
        )
        self.refresh_from_record(record)

    def is_running_phase(self) -> bool:
        """The container refuses to change the record while this is True."""
        return self.controller.running

    def _notify_phase_advanced(self, record) -> None:
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

    # ------------------------------------------------------------------
    # Called by the controller
    # ------------------------------------------------------------------

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.abort_button.setEnabled(running)
        if running:
            self.set_review_enabled(False)
            self.local_phase_status.setText("RUNNING")

    def set_paused(self, paused: bool) -> None:
        self.pause_button.setText("▶ Resume" if paused else "⏸ Pause")

    def set_next_enabled(self, enabled: bool) -> None:
        self.next_step_btn.setEnabled(enabled)

    def set_step(self, text: str) -> None:
        self.step_label.setText(text)

    def set_review_enabled(self, enabled: bool) -> None:
        self.push_button.setEnabled(enabled)
        self.decline_button.setEnabled(enabled)

    def show_review(self, data: dict) -> None:
        """read_results' data. A Warning is complete but not passed."""

        def fmt(key):
            value = data.get(key)
            return "-" if value is None else f"{value:.6f}"

        self.gain_a_label.setText(fmt("amplifier_gain_a"))
        self.gain_b_label.setText(fmt("amplifier_gain_b"))
        self.detune_gain_label.setText(fmt("detune_gain"))
        status = data.get("rf_test_status")
        if status == "Pass":
            text, style = "Pass", STATUS_LABEL_PASS
        else:
            text, style = f"{status} — complete, not passed", (
                STATUS_LABEL_INCOMPLETE
            )
        self.test_result_label.setText(text)
        self.test_result_label.setStyleSheet(style)
        self.local_phase_status.setText("REVIEW")
        self.set_review_enabled(data.get("detune_gain") is not None)

    def clear_review(self) -> None:
        for name in (
            "gain_a_label",
            "gain_b_label",
            "detune_gain_label",
            "test_result_label",
            "step_label",
        ):
            getattr(self, name).setText("-")
        self.test_result_label.setStyleSheet("")
        self.set_review_enabled(False)

    def on_phase_finished(self, status: str) -> None:
        self.local_phase_status.setText(status)
        self.set_review_enabled(False)
        self.set_next_enabled(False)
        self.set_paused(False)

    def ask_rerun(
        self, label: str, pv: str, stamp: datetime | None, good: bool | None
    ) -> bool | None:
        """Rerun (True), Skip (False) or closed (None) for one stale result."""
        why = (
            f"is {age_text(stamp)} old (over 1 h)"
            if good
            else "did not finish Good/Complete"
        )
        when = f"{stamp:%Y-%m-%d %H:%M}" if stamp else "unknown"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(f"{label[0].upper()}{label[1:]} is stale")
        box.setText(f"The last {label} {why}.")
        box.setInformativeText(
            f"Last run: {when} ({pv}).\n\n"
            f"Rerun: setup_rf re-runs the {label}.\n"
            "Skip: keep the values already on the machine; the record "
            "notes that you skipped it."
        )
        rerun = box.addButton("Rerun", QMessageBox.AcceptRole)
        skip = box.addButton("Skip", QMessageBox.RejectRole)
        box.addButton(QMessageBox.Cancel)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is rerun:
            return True
        if clicked is skip:
            return False
        return None

    # ------------------------------------------------------------------
    # Push / Don't Push
    # ------------------------------------------------------------------

    def _confirm_push_text(self, data: dict) -> str:
        """The gain Yes pushes, from read_results' data.

        The current gain is the Live PVs label's text (DFGAIN), shown for
        comparison only; reading the PV here would block the GUI thread.
        """
        cavity = self.controller.phase.cavity if self.controller.phase else ""
        label = self.pydm_dfgain_current
        # Unconnected, a PyDMLabel shows its channel address instead.
        current = label.text() if label._connected else "not connected"
        return (
            f"Push the new detune gain to the IOC for {cavity}?\n\n"
            f"  New detune gain: {data['detune_gain']:.6f}\n"
            f"  Detune gain in use now: {current}\n"
            f"  Test result: {data.get('rf_test_status')}"
        )

    @pyqtSlot()
    def on_push(self):
        data = self.controller.review_data
        if not data:
            return
        answer = QMessageBox.question(
            self,
            "Push detune gain",
            self._confirm_push_text(data),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.controller.on_push()

    @pyqtSlot()
    def on_decline_push(self):
        text, ok = QInputDialog.getText(
            self,
            "Don't push the detune gain",
            "Why not push? The phase completes with the gain not pushed.",
        )
        if ok and text.strip():
            self.controller.on_decline_push(text)
        elif ok:
            self.show_error("A justification is needed to skip the push")

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    @pyqtSlot()
    def on_start_test(self):
        self.controller.on_start_test()

    @pyqtSlot()
    def on_abort(self):
        self.controller.on_abort()

    @pyqtSlot()
    def on_pause_test(self):
        self.controller.on_pause_test()

    @pyqtSlot()
    def on_toggle_step_mode(self):
        self.controller.on_toggle_step_mode()

    @pyqtSlot()
    def on_next_step(self):
        self.controller.on_next_step()
