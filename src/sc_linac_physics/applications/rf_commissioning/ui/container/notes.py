"""Notes panel helpers for the multi-phase commissioning container."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
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
    def _build_compact_notes_bar(self) -> QWidget:
        """Compact single-row footer: note count badge + Add Note + View Notes buttons."""
        bar = QWidget()
        bar.setStyleSheet("""
            QWidget {
                background-color: #1e293b;
                border-top: 1px solid #334155;
            }
        """)
        bar.setFixedHeight(42)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        title = QLabel("Notes")
        title.setStyleSheet("font-weight: bold; font-size: 11pt; color: #ddd;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("QFrame { color: #4a4a4a; }")
        layout.addWidget(sep)

        self._notes_count_badge = QLabel("No notes")
        self._notes_count_badge.setStyleSheet(
            "QLabel { color: #6b7280; font-size: 10pt; }"
        )
        layout.addWidget(self._notes_count_badge)

        layout.addStretch()

        self._view_notes_btn = QPushButton("View Notes →")
        self._view_notes_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #d1d5db;
                border-radius: 3px;
                padding: 4px 14px;
                border: 1px solid #4b5563;
            }
            QPushButton:hover { background-color: #4b5563; }
        """)
        self._view_notes_btn.setFixedHeight(28)
        self._view_notes_btn.setVisible(False)
        self._view_notes_btn.clicked.connect(self._show_notes_dialog)
        layout.addWidget(self._view_notes_btn)

        add_btn = QPushButton("+ Add Note")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border-radius: 3px;
                padding: 4px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._quick_add_note)
        layout.addWidget(add_btn)

        bar.setLayout(layout)
        return bar

    def _show_notes_dialog(self) -> None:
        """Open (or raise) the full notes dialog."""
        if not hasattr(self, "_notes_dialog") or self._notes_dialog is None:
            self._notes_dialog = self._create_notes_dialog()
        self._load_notes()
        self._notes_dialog.show()
        self._notes_dialog.raise_()
        self._notes_dialog.activateWindow()

    def _create_notes_dialog(self) -> QDialog:
        """Build the persistent notes dialog with filter and table."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Commissioning Notes")
        dialog.setMinimumSize(750, 450)
        dialog.setAttribute(Qt.WA_DeleteOnClose, False)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by phase:"))

        self.notes_phase_filter = QComboBox()
        self.notes_phase_filter.addItem("All", None)
        self.notes_phase_filter.addItem("Current Phase", "current")
        for phase in CommissioningPhase:
            self.notes_phase_filter.addItem(phase.value, phase)
        self.notes_phase_filter.currentIndexChanged.connect(self._load_notes)
        filter_row.addWidget(self.notes_phase_filter)
        filter_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(70)
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
        self.notes_table.setColumnWidth(0, 150)
        self.notes_table.setColumnWidth(1, 120)
        self.notes_table.setColumnWidth(2, 120)
        self.notes_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.notes_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.notes_table.customContextMenuRequested.connect(
            self._show_notes_context_menu
        )
        layout.addWidget(self.notes_table)

        dialog.setLayout(layout)
        return dialog

    def _update_notes_badge(self) -> None:
        """Refresh the count badge in the compact notes bar."""
        if not hasattr(self, "_notes_count_badge"):
            return

        if not self.session.has_active_record():
            count = 0
        else:
            count = len(self.session.get_general_notes()) + len(
                self.session.get_measurement_notes(None)
            )

        if count == 0:
            self._notes_count_badge.setText("No notes")
            self._notes_count_badge.setStyleSheet(
                "QLabel { color: #6b7280; font-size: 10pt; }"
            )
            if hasattr(self, "_view_notes_btn"):
                self._view_notes_btn.setVisible(False)
        else:
            noun = "note" if count == 1 else "notes"
            self._notes_count_badge.setText(f"{count} {noun}")
            self._notes_count_badge.setStyleSheet(
                "QLabel { color: #4a9eff; font-weight: bold; font-size: 10pt; }"
            )
            if hasattr(self, "_view_notes_btn"):
                self._view_notes_btn.setVisible(True)

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
        self._update_notes_badge()
        if not hasattr(self, "notes_table"):
            return
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
build_compact_notes_bar = _NotesPanelMixin._build_compact_notes_bar
load_notes = _NotesPanelMixin._load_notes
