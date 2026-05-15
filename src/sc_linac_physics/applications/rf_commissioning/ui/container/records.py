"""Record selection/start helpers for the multi-phase commissioning container."""

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)
from sc_linac_physics.utils.sc_linac.linac_utils import get_linac_for_cryomodule


class _RecordSelectorMixin:
    def _on_load_or_start(self) -> None:
        """Intelligent load/start with validation and recent records."""
        operator = self.operator_combo.currentData()
        if not operator:
            QMessageBox.warning(
                self,
                "Operator Required",
                "Please select an operator before loading/starting a record.",
            )
            self.operator_combo.setFocus()
            return

        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        if cryomodule == "CM..." or not cryomodule:
            QMessageBox.warning(
                self, "Cryomodule Required", "Please select a cryomodule."
            )
            self.cryomodule_combo.setFocus()
            return

        if cavity == "Cav..." or not cavity:
            QMessageBox.warning(
                self, "Cavity Required", "Please select a cavity number."
            )
            self.cavity_combo.setFocus()
            return

        try:
            cavity_number = int(cavity)
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Cavity",
                f"Could not parse cavity number from '{cavity}'",
            )
            return

        linac_name = get_linac_for_cryomodule(cryomodule)
        if not linac_name:
            QMessageBox.warning(
                self, "Invalid Cryomodule", f"Unknown cryomodule: {cryomodule}"
            )
            return

        try:
            linac = int(linac_name[1])
        except (IndexError, ValueError):
            QMessageBox.warning(
                self,
                "Invalid Linac",
                f"Could not parse linac index from '{linac_name}'",
            )
            return

        existing_records = self.session.find_records_for_cavity(
            linac, cryomodule, cavity_number
        )

        cavity_display_name = f"{cryomodule}-{cavity}"

        if existing_records:
            self._show_record_selector(
                cavity_display_name,
                linac,
                cryomodule,
                cavity_number,
                existing_records,
            )
        else:
            self._confirm_and_start_new(
                cavity_display_name, linac, cryomodule, cavity_number
            )

    def _show_record_selector(
        self,
        cavity_display_name: str,
        linac: int,
        cryomodule: str,
        cavity_number: int,
        records: list,
    ) -> None:
        """Show dialog to select existing record or start new."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Records for {cavity_display_name}")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout()

        header_label = QLabel(
            f"<b>Found {len(records)} existing record(s) for {cavity_display_name}</b><br>"
            f"<small>Select a record to view or continue working on it</small>"
        )
        header_label.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(header_label)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["ID", "Started", "Status", "Current Phase", "Last Modified"]
        )
        table.setRowCount(len(records))
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)

        for row, record_data in enumerate(records):
            table.setItem(row, 0, QTableWidgetItem(str(record_data["id"])))
            table.setItem(
                row, 1, QTableWidgetItem(record_data.get("start_time", "")[:16])
            )

            status = record_data.get("overall_status", "in_progress")
            status_item = QTableWidgetItem(status.replace("_", " ").title())
            if status == "complete":
                status_item.setForeground(Qt.darkGreen)
            elif status == "in_progress":
                status_item.setForeground(Qt.blue)
            table.setItem(row, 2, status_item)

            table.setItem(
                row,
                3,
                QTableWidgetItem(record_data.get("current_phase", "Unknown")),
            )
            table.setItem(
                row,
                4,
                QTableWidgetItem(record_data.get("updated_at", "Unknown")[:16]),
            )

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)

        info = QLabel(
            "💡 <i>Double-click a record to load it.<br>"
            "Select an operator before loading or starting a record.</i>"
        )
        info.setStyleSheet("color: #888; padding: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        button_layout = QHBoxLayout()

        load_btn = QPushButton("📂 Load Selected")
        load_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 8px 16px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #ccc;
                    color: #666;
                }
            """)
        load_btn.clicked.connect(
            lambda: self._load_selected_record(table, dialog)
        )
        load_btn.setEnabled(False)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(load_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        table.itemSelectionChanged.connect(
            lambda: load_btn.setEnabled(len(table.selectedItems()) > 0)
        )
        table.cellDoubleClicked.connect(
            lambda: self._load_selected_record(table, dialog)
        )

        dialog.setLayout(layout)
        dialog.exec_()

    def _load_selected_record(
        self, table: QTableWidget, dialog: QDialog
    ) -> None:
        """Load the selected record from the table."""
        selected_rows = set(item.row() for item in table.selectedItems())
        if not selected_rows:
            return

        row = list(selected_rows)[0]
        record_id = int(table.item(row, 0).text())

        if self.load_record(record_id):
            dialog.accept()
            self._update_sync_status(True, "Record loaded")

            settings = QSettings("SLAC", "RFCommissioning")
            settings.setValue("last_record_id", record_id)
        else:
            QMessageBox.critical(
                dialog, "Load Failed", f"Failed to load record {record_id}"
            )

    def _start_new_from_dialog(
        self,
        cavity_display_name: str,
        linac: int,
        cryomodule: str,
        cavity_number: int,
        dialog: QDialog,
    ) -> None:
        """Start new record from the selection dialog."""
        dialog.accept()
        self._confirm_and_start_new(
            cavity_display_name, linac, cryomodule, cavity_number
        )

    def _confirm_and_start_new(
        self,
        cavity_display_name: str,
        linac: int,
        cryomodule: str,
        cavity_number: int,
    ) -> None:
        """Confirm and start a new commissioning record."""
        reply = QMessageBox.question(
            self,
            "Start New Record",
            f"Start new commissioning record for {cavity_display_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            try:
                created = self.start_new_record(cryomodule, cavity_number)
                if created:
                    self._update_sync_status(True, "New record started")
                else:
                    self._update_sync_status(True, "Record loaded")

                if created:
                    operator = self.operator_combo.currentText()
                    try:
                        self.session.append_general_note(
                            operator,
                            f"Started commissioning for {cavity_display_name}",
                        )
                    except RecordConflictError as conflict:
                        self._handle_note_conflict(conflict)

            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to start new record: {e}"
                )


# Backward-compat aliases so existing tests continue to work.
on_load_or_start = _RecordSelectorMixin._on_load_or_start
show_record_selector = _RecordSelectorMixin._show_record_selector
load_selected_record = _RecordSelectorMixin._load_selected_record
start_new_from_dialog = _RecordSelectorMixin._start_new_from_dialog
confirm_and_start_new = _RecordSelectorMixin._confirm_and_start_new
