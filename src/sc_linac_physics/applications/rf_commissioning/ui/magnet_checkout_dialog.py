"""Dialog for editing cryomodule magnet checkout status and notes."""

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CryomoduleCheckoutRecord,
    CryomodulePhase,
    CryomodulePhaseStatus,
    MagnetCheckoutData,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)


class MagnetCheckoutDialog(QDialog):
    """Modal dialog for recording magnet checkout pass/fail with operator and notes."""

    def __init__(
        self,
        session: CommissioningSession,
        linac: str,
        cryomodule: str,
        parent=None,
    ):
        super().__init__(parent)
        self.session = session
        self.linac = linac
        self.cryomodule = cryomodule

        self.setWindowTitle(f"Magnet Checkout - {linac}_CM{cryomodule}")

        loaded = session.get_cryomodule_record_with_version(linac, cryomodule)
        if loaded is None:
            self._cm_record = CryomoduleCheckoutRecord(
                linac=linac, cryomodule=cryomodule
            )
            self._record_id = None
            self._record_version = None
        else:
            self._cm_record, self._record_version = loaded
            self._record_id = session.get_cryomodule_record_id(
                linac, cryomodule
            )

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["PENDING", "PASS", "FAIL"])
        status_row.addWidget(self.status_combo)
        layout.addLayout(status_row)

        operator_row = QHBoxLayout()
        operator_row.addWidget(QLabel("Operator:"))
        self.operator_combo = QComboBox()
        self.operator_combo.addItem("👤 Select operator...", "")
        for op in self.session.get_operators():
            self.operator_combo.addItem(f"👤 {op}", op)
        self.operator_combo.setMinimumWidth(200)
        operator_row.addWidget(self.operator_combo)
        layout.addLayout(operator_row)

        layout.addWidget(QLabel("Notes:"))
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText(
            "Optional notes for magnet checkout result"
        )
        self.notes_input.setMinimumHeight(120)
        layout.addWidget(self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self._populate_from_record()

    def _populate_from_record(self) -> None:
        checkout = self._cm_record.magnet_checkout
        if checkout is None:
            self.status_combo.setCurrentText("PENDING")
            self.notes_input.setPlainText(self._cm_record.notes or "")
        else:
            self.status_combo.setCurrentText(
                "PASS" if checkout.passed else "FAIL"
            )
            self.notes_input.setPlainText(checkout.notes or "")
            if checkout.operator:
                idx = self.operator_combo.findData(checkout.operator)
                if idx >= 0:
                    self.operator_combo.setCurrentIndex(idx)

    def save(self) -> bool:
        """Validate and persist the checkout result. Returns True on success."""
        selected_status = self.status_combo.currentText().upper()
        selected_operator = self.operator_combo.currentData() or ""

        if selected_status != "PENDING" and not selected_operator:
            QMessageBox.warning(
                self,
                "Operator Required",
                "An operator must be selected for PASS/FAIL checkout results.",
            )
            return False

        notes = self.notes_input.toPlainText().strip()

        if selected_status == "PENDING":
            self._cm_record.magnet_checkout = None
            self._cm_record.set_phase_status(
                CryomodulePhase.MAGNET_CHECKOUT,
                CryomodulePhaseStatus.NOT_STARTED,
            )
        else:
            self._cm_record.magnet_checkout = MagnetCheckoutData(
                passed=(selected_status == "PASS"),
                operator=selected_operator,
                notes=notes,
            )
            self._cm_record.set_phase_status(
                CryomodulePhase.MAGNET_CHECKOUT,
                (
                    CryomodulePhaseStatus.COMPLETE
                    if selected_status == "PASS"
                    else CryomodulePhaseStatus.FAILED
                ),
            )

        self._cm_record.notes = notes

        try:
            self.session.save_cryomodule_record(
                self._cm_record,
                record_id=self._record_id,
                expected_version=self._record_version,
            )
        except RecordConflictError as conflict:
            QMessageBox.warning(
                self,
                "Save Conflict",
                (
                    "Magnet checkout was updated by another user. "
                    f"Expected version {conflict.expected_version}, "
                    f"database has version {conflict.current_version}."
                ),
            )
            return False

        return True
