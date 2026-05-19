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


class _NotesPanelMixin:
    def _build_enhanced_notes_panel(self) -> QWidget:
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
        quick_add.clicked.connect(self._quick_add_note)
        header.addWidget(quick_add)

        layout.addLayout(header)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.notes_phase_filter = QComboBox()
        self.notes_phase_filter.addItem("All", None)
        self.notes_phase_filter.addItem("Current Phase", "current")
        for phase in CommissioningPhase:
            self.notes_phase_filter.addItem(phase.value, phase)
        self.notes_phase_filter.currentIndexChanged.connect(self._load_notes)
        filter_row.addWidget(self.notes_phase_filter)
        filter_row.addStretch()

        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh notes")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(self._load_notes)
        filter_row.addWidget(refresh_btn)

        layout.addLayout(filter_row)

        self.notes_table = QTableWidget()
        self.notes_table.setColumnCount(4)
        self.notes_table.setHorizontalHeaderLabels(
            ["Time", "Phase", "Operator", "Note"]
        )
        self.notes_table.horizontalHeader().setStretchLastSection(True)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notes_table.setAlternatingRowColors(True)
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.notes_table.setColumnWidth(0, 130)
        self.notes_table.setColumnWidth(1, 100)
        self.notes_table.setColumnWidth(2, 100)
        self.notes_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        self.notes_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.notes_table.customContextMenuRequested.connect(
            self._show_notes_context_menu
        )

        layout.addWidget(self.notes_table)

        widget.setLayout(layout)
        return widget

    def _load_notes(self) -> None:
        """Load and display all notes for the active record."""
        if not self.session.has_active_record():
            self.notes_table.setRowCount(0)
            return

        phase_filter = self.notes_phase_filter.currentData()

        if phase_filter == "current":
            record = self.session.get_active_record()
            phase_filter = record.current_phase

        measurement_notes = self.session.get_measurement_notes(phase_filter)
        general_notes = self.session.get_general_notes()

        all_notes = []

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

        for note in measurement_notes:
            if phase_filter and note.get("phase") != phase_filter.value:
                continue
            all_notes.append(
                {
                    "type": "Measurement",
                    "phase": note.get("phase", ""),
                    "measurement_timestamp": note.get(
                        "measurement_timestamp", ""
                    ),
                    "timestamp": note.get("timestamp"),
                    "operator": note.get("operator"),
                    "note": note.get("note"),
                    "note_ref": (
                        "measurement",
                        (note.get("entry_id"), note.get("note_index")),
                    ),
                }
            )

        all_notes.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        self.notes_table.setRowCount(len(all_notes))

        for row, item in enumerate(all_notes):
            time_str = item["timestamp"] or item["measurement_timestamp"] or "-"
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, item["note_ref"])
            self.notes_table.setItem(row, 0, time_item)

            phase_str = item["phase"] or "General"
            self.notes_table.setItem(row, 1, QTableWidgetItem(phase_str))
            self.notes_table.setItem(
                row, 2, QTableWidgetItem(item["operator"] or "Unknown")
            )
            self.notes_table.setItem(
                row, 3, QTableWidgetItem(item["note"] or "")
            )


# Backward-compat aliases so existing tests continue to work.
build_enhanced_notes_panel = _NotesPanelMixin._build_enhanced_notes_panel
load_notes = _NotesPanelMixin._load_notes
