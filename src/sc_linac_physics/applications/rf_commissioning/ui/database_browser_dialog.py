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
    QComboBox,
)

from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


class DatabaseBrowserDialog(QDialog):
    """Dialog for browsing and selecting commissioning records."""

    def __init__(
        self,
        db,
        parent=None,
        cryomodule_filter: str | None = None,
        cavity_filter: str | None = None,
        linac_filter: str | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self._all_records: list[dict] = []
        self._linac_filter = linac_filter
        self.selected_record_id = None
        self.selected_record = None
        self._initial_cryomodule = cryomodule_filter
        self._initial_cavity = cavity_filter

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

        # Filter row
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by cavity:"))

        self.cryomodule_combo = QComboBox()
        self.cryomodule_combo.addItem("All CM", None)
        self.cryomodule_combo.addItems(sorted(ALL_CRYOMODULES))
        filter_layout.addWidget(QLabel("CM:"))
        filter_layout.addWidget(self.cryomodule_combo)

        self.cavity_combo = QComboBox()
        self.cavity_combo.addItem("All Cav", None)
        self.cavity_combo.addItems([str(i) for i in range(1, 9)])
        filter_layout.addWidget(QLabel("Cav:"))
        filter_layout.addWidget(self.cavity_combo)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.cryomodule_combo.currentIndexChanged.connect(self._apply_filters)
        self.cavity_combo.currentIndexChanged.connect(self._apply_filters)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Linac",
                "CM",
                "Cav",
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
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Linac
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # CM
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Cav
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Start Time
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # End Time
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Phase
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Result

        # Double-click to load
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # Info label
        self.info_label = QLabel()
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

        # Linac / CM / Cav
        linac = record.get("linac", "?")
        linac_number = record.get("linac_number")
        linac_display = linac_number or linac
        cryo = record.get("cryomodule", "?")
        cavity = record.get("cavity_number", "?")
        self.table.setItem(row, 1, QTableWidgetItem(str(linac_display)))
        self.table.setItem(row, 2, QTableWidgetItem(cryo))
        self.table.setItem(row, 3, QTableWidgetItem(str(cavity)))

        # Start Time
        start_time_str = record.get("start_time")
        start_time = (
            self._format_timestamp(start_time_str) if start_time_str else "N/A"
        )
        self.table.setItem(row, 4, QTableWidgetItem(start_time))

        # End Time
        end_time_str = record.get("end_time")
        end_time = (
            self._format_timestamp(end_time_str)
            if end_time_str
            else "Not completed"
        )
        self.table.setItem(row, 5, QTableWidgetItem(end_time))

        # Phase
        phase = record.get("current_phase", "N/A")
        self.table.setItem(row, 6, QTableWidgetItem(phase))

        # Status
        status = record.get("overall_status", "N/A")
        status_item = self._create_status_item(status)
        self.table.setItem(row, 7, status_item)

        # Result
        result_item = self._create_result_item(phase, record)
        self.table.setItem(row, 8, result_item)

    def _load_records(self):
        """Load all records from database and populate table."""
        try:
            self._all_records = self.db.get_all_records()
            self._all_records.sort(
                key=lambda x: x.get("start_time", ""), reverse=True
            )

            if self._initial_cryomodule:
                idx = self.cryomodule_combo.findText(self._initial_cryomodule)
                if idx >= 0:
                    self.cryomodule_combo.setCurrentIndex(idx)

            if self._initial_cavity:
                idx = self.cavity_combo.findText(str(self._initial_cavity))
                if idx >= 0:
                    self.cavity_combo.setCurrentIndex(idx)

            self._apply_filters()

        except Exception as e:
            self.info_label.setText(f"Error loading records: {e}")
            self.info_label.setStyleSheet("color: red; padding: 5px;")

    def _clear_filters(self) -> None:
        """Reset filters to show all records."""
        self.cryomodule_combo.setCurrentIndex(0)
        self.cavity_combo.setCurrentIndex(0)
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply cavity filters to the record list."""
        cryo = self.cryomodule_combo.currentText()
        cav = self.cavity_combo.currentText()

        filtered = []
        for record in self._all_records:
            if self._linac_filter and record.get("linac") != self._linac_filter:
                continue
            if cryo != "All CM" and record.get("cryomodule") != cryo:
                continue
            if cav != "All Cav" and record.get("cavity_number") != cav:
                continue
            filtered.append(record)

        self.table.setRowCount(len(filtered))
        for row, record in enumerate(filtered):
            self._populate_table_row(row, record)

        self.table.clearSelection()
        self.selected_record_id = None
        self.selected_record = None
        self.load_button.setEnabled(False)
        self._update_info_label(len(filtered), len(self._all_records))

    def _update_info_label(self, shown: int, total: int) -> None:
        """Update info label with filter counts."""
        if total == 0:
            self.info_label.setText("No records found")
        else:
            self.info_label.setText(f"Showing {shown} of {total} records")

        self.info_label.setStyleSheet("color: #888; padding: 5px;")

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
            linac = self.table.item(row, 1).text()
            cryo = self.table.item(row, 2).text()
            cavity = self.table.item(row, 3).text()
            phase = self.table.item(row, 6).text()
            status = self.table.item(row, 7).text()
            self.info_label.setText(
                f"Selected: {linac}_CM{cryo}_CAV{cavity} - {phase} - {status}"
            )
            self.info_label.setStyleSheet("color: #4a9eff; padding: 5px;")
        else:
            self.selected_record_id = None
            self.selected_record = None
            self.load_button.setEnabled(False)
            self._update_info_label(
                self.table.rowCount(), len(self._all_records)
            )
            self.info_label.setStyleSheet("color: #888; padding: 5px;")

    def _on_double_click(self, index):
        """Handle double-click on a row."""
        if self.selected_record_id:
            self.accept()

    def get_selected_record(self):
        """Return the selected record ID and data."""
        return self.selected_record_id, self.selected_record
