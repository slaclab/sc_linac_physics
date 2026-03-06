"""Dialog for viewing measurement history."""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QDialogButtonBox,
)
from PyQt5.QtCore import Qt

from sc_linac_physics.applications.rf_commissioning import CommissioningPhase
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)


class MeasurementHistoryDialog(QDialog):
    """Dialog showing all measurement attempts for a record.

    Displays a chronological list of all measurements taken,
    including who took them and when. This helps track retries
    and collaborative work.
    """

    def __init__(
        self,
        session: CommissioningSession,
        phase: Optional[CommissioningPhase] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Measurement History - All Attempts")
        self.setModal(False)
        self.resize(900, 500)

        self.session = session
        self.current_phase = phase

        self._init_ui()
        self._load_history()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header with phase filter
        header_layout = QHBoxLayout()

        header_layout.addWidget(QLabel("Phase filter (shows attempts):"))

        self.phase_filter = QComboBox()
        self.phase_filter.addItem("All Phases", None)
        for phase in CommissioningPhase:
            self.phase_filter.addItem(phase.value, phase)

        if self.current_phase:
            idx = self.phase_filter.findData(self.current_phase)
            if idx >= 0:
                self.phase_filter.setCurrentIndex(idx)

        self.phase_filter.currentIndexChanged.connect(self._on_phase_changed)
        header_layout.addWidget(self.phase_filter)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        tip_label = QLabel(
            "Tip: Select a phase to see all previous attempts for that phase."
        )
        tip_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(tip_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "Phase", "Operator", "Notes", "Data Summary"]
        )

        # Make columns resize appropriately
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        self.count_label = QLabel()
        button_layout.addWidget(self.count_label)

        button_layout.addStretch()

        add_note_btn = QPushButton("Add Note")
        add_note_btn.clicked.connect(self._add_note_to_selected_entry)
        button_layout.addWidget(add_note_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_history)
        button_layout.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_phase_changed(self, index: int):
        """Handle phase filter change."""
        self.current_phase = self.phase_filter.currentData()
        self._load_history()

    def _load_history(self):
        """Load and display measurement history."""
        if not self.session.has_active_record():
            self.table.setRowCount(0)
            self.count_label.setText("No active record")
            return

        history = self.session.get_measurement_history(self.current_phase)

        self.table.setRowCount(len(history))

        for row, entry in enumerate(history):
            # Timestamp
            timestamp_item = QTableWidgetItem(entry["timestamp"])
            timestamp_item.setFlags(timestamp_item.flags() & ~Qt.ItemIsEditable)
            timestamp_item.setData(Qt.UserRole, entry["id"])
            self.table.setItem(row, 0, timestamp_item)

            # Phase
            phase_item = QTableWidgetItem(entry["phase"])
            phase_item.setFlags(phase_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, phase_item)

            # Operator
            operator = entry.get("operator") or "Unknown"
            operator_item = QTableWidgetItem(operator)
            operator_item.setFlags(operator_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, operator_item)

            # Notes
            notes_list = entry.get("notes") or []
            notes_item = QTableWidgetItem(self._format_notes(notes_list))
            notes_item.setFlags(notes_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, notes_item)

            # Data summary
            data_summary = self._summarize_measurement_data(
                entry["measurement_data"]
            )
            data_item = QTableWidgetItem(data_summary)
            data_item.setFlags(data_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 4, data_item)

        # Update count
        phase_name = (
            self.current_phase.value if self.current_phase else "all phases"
        )
        self.count_label.setText(
            f"{len(history)} measurement(s) for {phase_name}"
        )

    def _add_note_to_selected_entry(self):
        """Append a note to the selected measurement entry."""
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        entry_id = self.table.item(row, 0).data(Qt.UserRole)
        current_operator = self.table.item(row, 2).text()

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Measurement Note")
        dialog_layout = QVBoxLayout(dialog)

        operator_layout = QHBoxLayout()
        operator_layout.addWidget(QLabel("Operator:"))
        operator_input = QLineEdit(current_operator)
        operator_layout.addWidget(operator_input)
        dialog_layout.addLayout(operator_layout)

        dialog_layout.addWidget(QLabel("Notes:"))
        notes_input = QTextEdit()
        notes_input.setFixedHeight(100)
        dialog_layout.addWidget(notes_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        if dialog.exec_() != QDialog.Accepted:
            return

        operator = operator_input.text().strip() or None
        note = notes_input.toPlainText().strip()
        if not note:
            return

        if self.session.append_measurement_note(entry_id, operator, note):
            self._load_history()

    def _format_notes(self, notes_list: list[dict]) -> str:
        if not notes_list:
            return ""

        lines = []
        for item in notes_list:
            note = item.get("note", "")
            operator = item.get("operator") or "Unknown"
            timestamp = item.get("timestamp") or ""
            prefix = (
                f"{timestamp} - {operator}: " if timestamp else f"{operator}: "
            )
            lines.append(prefix + note)

        return "\n".join(lines)

    def _summarize_measurement_data(self, data: dict) -> str:
        """Create a brief summary of measurement data."""
        if not data:
            return "No data"

        # Show first few key-value pairs
        summary_parts = []
        for key, value in list(data.items())[:3]:
            if isinstance(value, (int, float)):
                summary_parts.append(f"{key}={value:.3g}")
            elif isinstance(value, bool):
                summary_parts.append(f"{key}={value}")
            elif isinstance(value, str) and len(value) < 20:
                summary_parts.append(f"{key}={value}")

        summary = ", ".join(summary_parts)
        if len(data) > 3:
            summary += f" ... ({len(data)} fields total)"

        return summary or "Complex data"
