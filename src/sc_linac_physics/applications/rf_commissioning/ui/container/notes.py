"""Notes panel helpers for the multi-phase commissioning container."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)


def build_enhanced_notes_panel(host) -> QWidget:
    """Build always-accessible notes panel with better UX."""
    widget = QWidget()
    widget.setStyleSheet("""
                            QWidget {
                                background-color: #2a2a2a;
                                border-top: 1px solid #444;
                            }
                        """)

    layout = QVBoxLayout()
    layout.setContentsMargins(10, 10, 10, 10)

    # Header with add button
    header = QHBoxLayout()
    title = QLabel("📝 Notes")
    title.setStyleSheet("font-weight: bold; font-size: 14px; color: #ddd;")
    header.addWidget(title)
    header.addStretch()

    quick_add = QPushButton("+ Quick Note")
    quick_add.setStyleSheet("""
                            QPushButton {
                                background-color: #4CAF50;
                                color: white;
                                border-radius: 3px;
                                padding: 5px 15px;
                                font-weight: bold;
                            }
                            QPushButton:hover {
                                background-color: #45a049;
                            }
                        """)
    quick_add.clicked.connect(host._quick_add_note)
    header.addWidget(quick_add)

    layout.addLayout(header)

    # Filter row
    filter_row = QHBoxLayout()
    filter_row.addWidget(QLabel("Filter:"))
    host.notes_phase_filter = QComboBox()
    host.notes_phase_filter.addItem("All", None)
    host.notes_phase_filter.addItem("Current Phase", "current")
    for phase in CommissioningPhase:
        host.notes_phase_filter.addItem(phase.value, phase)
    host.notes_phase_filter.currentIndexChanged.connect(host._load_notes)
    filter_row.addWidget(host.notes_phase_filter)
    filter_row.addStretch()

    refresh_btn = QPushButton("🔄")
    refresh_btn.setToolTip("Refresh notes")
    refresh_btn.setFixedWidth(30)
    refresh_btn.clicked.connect(host._load_notes)
    filter_row.addWidget(refresh_btn)

    layout.addLayout(filter_row)

    # Notes table
    host.notes_table = QTableWidget()
    host.notes_table.setColumnCount(4)
    host.notes_table.setHorizontalHeaderLabels(
        ["Time", "Phase", "Operator", "Note"]
    )
    host.notes_table.horizontalHeader().setStretchLastSection(True)
    host.notes_table.setSelectionBehavior(QTableWidget.SelectRows)
    host.notes_table.setAlternatingRowColors(True)
    host.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

    # Column widths
    host.notes_table.setColumnWidth(0, 130)
    host.notes_table.setColumnWidth(1, 100)
    host.notes_table.setColumnWidth(2, 100)
    host.notes_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # Enable right-click context menu
    host.notes_table.setContextMenuPolicy(Qt.CustomContextMenu)
    host.notes_table.customContextMenuRequested.connect(
        host._show_notes_context_menu
    )

    layout.addWidget(host.notes_table)

    widget.setLayout(layout)
    return widget


def load_notes(host) -> None:
    """Load and display all notes for the active record."""
    if not host.session.has_active_record():
        host.notes_table.setRowCount(0)
        return

    phase_filter = host.notes_phase_filter.currentData()

    # Handle "current phase" filter
    if phase_filter == "current":
        record = host.session.get_active_record()
        phase_filter = record.current_phase

    # Get both general notes and measurement notes
    measurement_notes = host.session.get_measurement_notes(phase_filter)
    general_notes = host.session.get_general_notes()

    # Combine all notes
    all_notes = []

    # General notes don't have phase or measurement time
    for note_index, note in enumerate(general_notes):
        all_notes.append(
            {
                "type": "General",
                "phase": "",
                "measurement_timestamp": "",
                "timestamp": note.get("timestamp"),
                "operator": note.get("operator"),
                "note": note.get("note"),
                "note_ref": ("general", note_index),
            }
        )

    # Measurement notes have phase and measurement time
    for note in measurement_notes:
        if phase_filter and note.get("phase") != phase_filter.value:
            continue
        all_notes.append(
            {
                "type": "Measurement",
                "phase": note.get("phase", ""),
                "measurement_timestamp": note.get("measurement_timestamp", ""),
                "timestamp": note.get("timestamp"),
                "operator": note.get("operator"),
                "note": note.get("note"),
                "note_ref": (
                    "measurement",
                    (note.get("entry_id"), note.get("note_index")),
                ),
            }
        )

    # Sort by timestamp (most recent first)
    all_notes.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    host.notes_table.setRowCount(len(all_notes))

    for row, item in enumerate(all_notes):
        # Time column
        time_str = item["timestamp"] or item["measurement_timestamp"] or "-"
        time_item = QTableWidgetItem(time_str)
        time_item.setData(Qt.UserRole, item["note_ref"])
        host.notes_table.setItem(row, 0, time_item)

        # Phase column
        phase_str = item["phase"] or "General"
        phase_item = QTableWidgetItem(phase_str)
        host.notes_table.setItem(row, 1, phase_item)

        # Operator column
        operator_item = QTableWidgetItem(item["operator"] or "Unknown")
        host.notes_table.setItem(row, 2, operator_item)

        # Note column
        note_item = QTableWidgetItem(item["note"] or "")
        host.notes_table.setItem(row, 3, note_item)
