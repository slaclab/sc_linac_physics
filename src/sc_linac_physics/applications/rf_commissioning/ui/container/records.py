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

from sc_linac_physics.applications.rf_commissioning.models.database import (
    RecordConflictError,
)
from sc_linac_physics.utils.sc_linac.linac_utils import get_linac_for_cryomodule


def on_load_or_start(host) -> None:
    """Intelligent load/start with validation and recent records."""
    operator = host.operator_combo.currentData()
    if not operator:
        QMessageBox.warning(
            host,
            "Operator Required",
            "Please select an operator before loading/starting a record.",
        )
        host.operator_combo.setFocus()
        return

    cryomodule = host.cryomodule_combo.currentText()
    cavity = host.cavity_combo.currentText()

    # Validate selections (check if placeholder still selected)
    if cryomodule == "Select CM..." or not cryomodule:
        QMessageBox.warning(
            host, "Cryomodule Required", "Please select a cryomodule."
        )
        host.cryomodule_combo.setFocus()
        return

    if cavity == "Select Cav..." or not cavity:
        QMessageBox.warning(
            host, "Cavity Required", "Please select a cavity number."
        )
        host.cavity_combo.setFocus()
        return

    cavity_number = cavity

    linac = get_linac_for_cryomodule(cryomodule)
    if not linac:
        QMessageBox.warning(
            host, "Invalid Cryomodule", f"Unknown cryomodule: {cryomodule}"
        )
        return

    existing_records = host.session.db.find_records_for_cavity(
        linac, cryomodule, cavity_number
    )

    cavity_display_name = f"{cryomodule}_CAV{cavity}"

    if existing_records:
        show_record_selector(
            host,
            cavity_display_name,
            linac,
            cryomodule,
            cavity_number,
            existing_records,
        )
    else:
        confirm_and_start_new(
            host, cavity_display_name, linac, cryomodule, cavity_number
        )


def show_record_selector(
    host,
    cavity_display_name: str,
    linac: str,
    cryomodule: str,
    cavity_number: str,
    records: list,
) -> None:
    """Show dialog to select existing record or start new."""
    dialog = QDialog(host)
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

    # Table of existing records
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

        # Status with color
        status = record_data.get("overall_status", "in_progress")
        status_item = QTableWidgetItem(status.replace("_", " ").title())
        if status == "completed":
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

    # Instructions
    info = QLabel(
        "💡 <i>Double-click a record to load it.<br>"
        "You can view records without selecting an operator. "
        "An operator is only required when running tests or making changes.</i>"
    )
    info.setStyleSheet("color: #888; padding: 5px;")
    info.setWordWrap(True)
    layout.addWidget(info)

    # Buttons
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
    load_btn.clicked.connect(lambda: load_selected_record(host, table, dialog))
    load_btn.setEnabled(False)

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dialog.reject)

    button_layout.addWidget(load_btn)
    button_layout.addStretch()
    button_layout.addWidget(cancel_btn)

    layout.addLayout(button_layout)

    # Enable load button when row selected
    table.itemSelectionChanged.connect(
        lambda: load_btn.setEnabled(len(table.selectedItems()) > 0)
    )

    # Double-click to load
    table.cellDoubleClicked.connect(
        lambda: load_selected_record(host, table, dialog)
    )

    dialog.setLayout(layout)
    dialog.exec_()


def load_selected_record(host, table: QTableWidget, dialog: QDialog) -> None:
    """Load the selected record from the table."""
    selected_rows = set(item.row() for item in table.selectedItems())
    if not selected_rows:
        return

    row = list(selected_rows)[0]
    record_id = int(table.item(row, 0).text())

    if host.load_record(record_id):
        dialog.accept()
        host._update_sync_status(True, "Record loaded")

        # Save to settings for next launch
        settings = QSettings("SLAC", "RFCommissioning")
        settings.setValue("last_record_id", record_id)
    else:
        QMessageBox.critical(
            dialog, "Load Failed", f"Failed to load record {record_id}"
        )


def start_new_from_dialog(
    host,
    cavity_display_name: str,
    linac: str,
    cryomodule: str,
    cavity_number: str,
    dialog: QDialog,
) -> None:
    """Start new record from the selection dialog."""
    dialog.accept()
    confirm_and_start_new(
        host, cavity_display_name, linac, cryomodule, cavity_number
    )


def confirm_and_start_new(
    host,
    cavity_display_name: str,
    linac: str,
    cryomodule: str,
    cavity_number: str,
) -> None:
    """Confirm and start a new commissioning record."""
    reply = QMessageBox.question(
        host,
        "Start New Record",
        f"Start new commissioning record for {cavity_display_name}?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )

    if reply == QMessageBox.Yes:
        try:
            created = host.start_new_record(cryomodule, cavity_number)
            if created:
                host._update_sync_status(True, "New record started")
            else:
                host._update_sync_status(True, "Record loaded")

            if created:
                # Log the start
                operator = host.operator_combo.currentText()
                try:
                    host.session.append_general_note(
                        operator,
                        f"Started commissioning for {cavity_display_name}",
                    )
                except RecordConflictError as conflict:
                    host._handle_note_conflict(conflict)

        except Exception as e:
            QMessageBox.critical(
                host, "Error", f"Failed to start new record: {e}"
            )
