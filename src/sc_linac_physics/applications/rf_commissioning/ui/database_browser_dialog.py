"""
Database browser dialog for selecting and loading commissioning records.
"""

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QHeaderView,
    QAbstractItemView,
)


class DatabaseBrowserDialog(QDialog):
    """Dialog for browsing and selecting commissioning records."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_record_id = None
        self.selected_record = None

        self.setWindowTitle("Load Commissioning Record")
        self.setModal(True)
        self.resize(900, 600)

        self._setup_ui()
        self._load_records()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Select a Commissioning Record to Load")
        title.setStyleSheet(
            "font-size: 14pt; font-weight: bold; padding: 10px;"
        )
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Cavity",
                "Start Time",
                "End Time",
                "Phase",
                "Status",
                "Result",
            ]
        )

        # Table settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        # Adjust column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )  # Cryomodule
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Start Time
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # End Time
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Phase
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Result

        # Double-click to load
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # Info label
        self.info_label = QLabel(
            "Select a record and click 'Load' or double-click a row"
        )
        self.info_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.info_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.load_button = QPushButton("Load Selected")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self.accept)
        self.load_button.setMinimumWidth(120)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setMinimumWidth(120)

        button_layout.addWidget(self.load_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format ISO timestamp string for display."""
        if not timestamp_str or timestamp_str == "N/A":
            return "N/A"
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return timestamp_str

    def _create_status_item(self, status: str) -> QTableWidgetItem:
        """Create a color-coded status table item."""
        status_item = QTableWidgetItem(status.upper())
        status_item.setTextAlignment(Qt.AlignCenter)

        if status == "complete":
            status_item.setBackground(QColor(45, 80, 22))
            status_item.setForeground(QColor(144, 238, 144))
        elif status == "failed":
            status_item.setBackground(QColor(92, 26, 26))
            status_item.setForeground(QColor(255, 107, 107))
        elif status == "in_progress":
            status_item.setBackground(QColor(80, 60, 20))
            status_item.setForeground(QColor(255, 165, 0))

        return status_item

    def _create_result_item(self, phase: str, record: dict) -> QTableWidgetItem:
        """Create a color-coded result table item."""
        result = "N/A"
        if phase == "piezo_pre_rf" and "piezo_pre_rf" in record:
            piezo_data = record["piezo_pre_rf"]
            if isinstance(piezo_data, dict):
                ch_a = piezo_data.get("channel_a_passed", False)
                ch_b = piezo_data.get("channel_b_passed", False)
                result = "PASS" if (ch_a and ch_b) else "FAIL"

        result_item = QTableWidgetItem(result)
        result_item.setTextAlignment(Qt.AlignCenter)

        if result == "PASS":
            result_item.setBackground(QColor(45, 80, 22))
            result_item.setForeground(QColor(144, 238, 144))
        elif result == "FAIL":
            result_item.setBackground(QColor(92, 26, 26))
            result_item.setForeground(QColor(255, 107, 107))

        return result_item

    def _populate_table_row(self, row: int, record: dict) -> None:
        """Populate a single table row with record data."""
        # ID
        id_item = QTableWidgetItem(str(record["id"]))
        id_item.setTextAlignment(Qt.AlignCenter)
        id_item.setData(Qt.UserRole, record)
        self.table.setItem(row, 0, id_item)

        # Cavity (formatted as Linac_CM_CAV)
        linac = record.get("linac", "?")
        cryo = record.get("cryomodule", "?")
        cavity = record.get("cavity_number", "?")
        cavity_display = f"{linac}_CM{cryo}_CAV{cavity}"
        cryo_item = QTableWidgetItem(cavity_display)
        self.table.setItem(row, 1, cryo_item)

        # Start Time
        start_time_str = record.get("start_time")
        start_time = (
            self._format_timestamp(start_time_str) if start_time_str else "N/A"
        )
        self.table.setItem(row, 2, QTableWidgetItem(start_time))

        # End Time
        end_time_str = record.get("end_time")
        end_time = (
            self._format_timestamp(end_time_str)
            if end_time_str
            else "Not completed"
        )
        self.table.setItem(row, 3, QTableWidgetItem(end_time))

        # Phase
        phase = record.get("current_phase", "N/A")
        self.table.setItem(row, 4, QTableWidgetItem(phase))

        # Status
        status = record.get("overall_status", "N/A")
        status_item = self._create_status_item(status)
        self.table.setItem(row, 5, status_item)

        # Result
        result_item = self._create_result_item(phase, record)
        self.table.setItem(row, 6, result_item)

    def _load_records(self):
        """Load all records from database and populate table."""
        try:
            all_records = self.db.get_all_records()
            all_records.sort(
                key=lambda x: x.get("start_time", ""), reverse=True
            )

            self.table.setRowCount(len(all_records))

            for row, record in enumerate(all_records):
                self._populate_table_row(row, record)

        except Exception as e:
            self.info_label.setText(f"Error loading records: {e}")
            self.info_label.setStyleSheet("color: red; padding: 5px;")

    def _on_selection_changed(self):
        """Handle row selection change."""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            id_item = self.table.item(row, 0)
            self.selected_record_id = int(id_item.text())
            self.selected_record = id_item.data(Qt.UserRole)
            self.load_button.setEnabled(True)

            # Update info label
            cryo = self.table.item(row, 1).text()
            phase = self.table.item(row, 4).text()
            status = self.table.item(row, 5).text()
            self.info_label.setText(f"Selected: {cryo} - {phase} - {status}")
            self.info_label.setStyleSheet("color: #4a9eff; padding: 5px;")
        else:
            self.selected_record_id = None
            self.selected_record = None
            self.load_button.setEnabled(False)
            self.info_label.setText(
                "Select a record and click 'Load' or double-click a row"
            )
            self.info_label.setStyleSheet("color: #888; padding: 5px;")

    def _on_double_click(self, index):
        """Handle double-click on a row."""
        if self.selected_record_id:
            self.accept()

    def get_selected_record(self):
        """Return the selected record ID and data."""
        return self.selected_record_id, self.selected_record
