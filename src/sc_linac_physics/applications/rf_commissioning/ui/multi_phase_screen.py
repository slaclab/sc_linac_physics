"""Multi-phase commissioning container display."""

import signal
import sys
from dataclasses import dataclass
from typing import Optional, Type

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QMessageBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QLabel,
    QTextEdit,
    QDialogButtonBox,
    QAbstractItemView,
    QInputDialog,
    QSizePolicy,
)
from pydm import Display, PyDMApplication

from sc_linac_physics.applications.rf_commissioning import CommissioningPhase
from sc_linac_physics.applications.rf_commissioning.models.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.measurement_history_dialog import (
    MeasurementHistoryDialog,
)
from sc_linac_physics.applications.rf_commissioning.ui.merge_dialog import (
    MergeDialog,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)
from sc_linac_physics.applications.rf_commissioning.ui.piezo_pre_rf_display import (
    PiezoPreRFDisplay,
)


@dataclass(frozen=True)
class PhaseTabSpec:
    """Metadata for a phase tab."""

    title: str
    display_class: Type[PhaseDisplayBase]
    phase: Optional[CommissioningPhase] = None


class MultiPhaseCommissioningDisplay(Display):
    """Container window that hosts multiple phase displays."""

    def __init__(
        self,
        parent=None,
        session: Optional[CommissioningSession] = None,
        phase_specs: Optional[list[PhaseTabSpec]] = None,
        refresh_interval_ms: int = 30000,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RF Commissioning")

        self.session = session or CommissioningSession("commissioning.db")
        self.phase_specs = phase_specs or self._default_phase_specs()

        # Create main layout with reduced margins
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Add toolbar with compact spacing
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)

        history_btn = QPushButton("View Measurement History")
        history_btn.clicked.connect(self._show_measurement_history)
        toolbar.addWidget(history_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Add tabs - give this the most space
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=3)  # Priority space allocation

        # Add collapsible notes panel
        self.notes_panel = self._build_notes_panel()
        layout.addWidget(self.notes_panel, stretch=1)  # Less priority

        self.setLayout(layout)

        self._phase_displays: list[PhaseDisplayBase] = []
        self._init_tabs()
        self._update_tab_states()
        self._load_notes()

        # Setup periodic refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._check_for_external_changes)
        if refresh_interval_ms > 0:
            self._refresh_timer.start(refresh_interval_ms)

    def _default_phase_specs(self) -> list[PhaseTabSpec]:
        return [
            PhaseTabSpec(
                title="1. Piezo Pre-RF",
                display_class=PiezoPreRFDisplay,
                phase=CommissioningPhase.PIEZO_PRE_RF,
            )
        ]

    def _init_tabs(self) -> None:
        for spec in self.phase_specs:
            display = spec.display_class(session=self.session)
            self._phase_displays.append(display)
            self.tabs.addTab(display, spec.title)

    def _build_notes_panel(self) -> QGroupBox:
        group = QGroupBox("Notes")
        group.setCheckable(True)  # Make collapsible
        group.setChecked(True)  # Start expanded

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(5)
        filter_row.addWidget(QLabel("Phase:"))
        self.notes_phase_filter = QComboBox()
        self.notes_phase_filter.addItem("All phases", None)
        for phase in CommissioningPhase:
            self.notes_phase_filter.addItem(phase.value, phase)
        self.notes_phase_filter.currentIndexChanged.connect(self._load_notes)
        filter_row.addWidget(self.notes_phase_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.notes_table = QTableWidget()
        self.notes_table.setColumnCount(6)
        self.notes_table.setHorizontalHeaderLabels(
            [
                "Type",
                "Phase",
                "Measurement Time",
                "Note Time",
                "Operator",
                "Note",
            ]
        )
        self.notes_table.setAlternatingRowColors(True)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Better space management
        self.notes_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        self.notes_table.setMinimumHeight(100)  # Show at least a few rows
        self.notes_table.setMaximumHeight(250)  # Don't dominate screen

        self.notes_table.horizontalHeader().setStretchLastSection(True)
        # Reduced column widths
        self.notes_table.setColumnWidth(0, 80)  # Type
        self.notes_table.setColumnWidth(1, 120)  # Phase
        self.notes_table.setColumnWidth(2, 140)  # Measurement Time
        self.notes_table.setColumnWidth(3, 140)  # Note Time
        self.notes_table.setColumnWidth(4, 100)  # Operator
        layout.addWidget(self.notes_table)

        button_row = QHBoxLayout()
        button_row.setSpacing(5)

        # Shortened button labels to save space
        add_general_note_btn = QPushButton("+ General Note")
        add_general_note_btn.clicked.connect(self._on_add_general_note)
        add_measurement_note_btn = QPushButton("+ Measurement Note")
        add_measurement_note_btn.clicked.connect(self._on_add_measurement_note)
        edit_note_btn = QPushButton("Edit")
        edit_note_btn.clicked.connect(self._on_edit_note)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_notes)

        button_row.addWidget(add_general_note_btn)
        button_row.addWidget(add_measurement_note_btn)
        button_row.addWidget(edit_note_btn)
        button_row.addWidget(refresh_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        group.setLayout(layout)
        return group

    def _update_tab_states(self) -> None:
        if not self.session.has_active_record():
            for i in range(1, self.tabs.count()):
                self.tabs.setTabEnabled(i, False)
            return

        record = self.session.get_active_record()
        phase_order = CommissioningPhase.get_phase_order()
        current_index = phase_order.index(record.current_phase)

        for i, spec in enumerate(self.phase_specs):
            if spec.phase is None:
                self.tabs.setTabEnabled(i, True)
                continue

            phase_index = phase_order.index(spec.phase)
            self.tabs.setTabEnabled(i, phase_index <= current_index)

    def start_new_record(self, cavity_name: str, cryomodule: str) -> None:
        record, _ = self.session.start_new_record(cavity_name, cryomodule)
        for display in self._phase_displays:
            display.refresh_from_record(record)
        self._update_tab_states()
        self.tabs.setCurrentIndex(0)
        self._load_notes()

    def load_record(self, record_id: int) -> bool:
        record = self.session.load_record(record_id)
        if not record:
            return False

        for display in self._phase_displays:
            display.on_record_loaded(record, record_id)

        self._update_tab_states()

        for i, spec in enumerate(self.phase_specs):
            if spec.phase == record.current_phase:
                self.tabs.setCurrentIndex(i)
                break

        self._load_notes()

        return True

    def save_active_record(self) -> bool:
        """Save the active record with conflict detection.

        Returns:
            True if saved successfully or user chose to continue, False otherwise
        """
        try:
            return self.session.save_active_record()
        except RecordConflictError as e:
            return self._handle_save_conflict(e)

    def _handle_save_conflict(self, conflict: RecordConflictError) -> bool:
        """Handle optimistic locking conflict with merge dialog.

        Args:
            conflict: The RecordConflictError containing conflict details

        Returns:
            True if conflict was resolved and save succeeded, False otherwise
        """
        if not self.session.has_active_record():
            return False

        record_id = self.session.get_active_record_id()
        if not record_id:
            return False

        # Load the current database version
        result = self.session.db.get_record_with_version(record_id)
        if not result:
            QMessageBox.critical(
                self, "Error", "Failed to load database version for merge."
            )
            return False

        db_record, db_version = result
        local_record = self.session.get_active_record()

        # Show merge dialog
        merge_dialog = MergeDialog(local_record, db_record, parent=self)

        if merge_dialog.exec_() != QDialog.Accepted:
            # User cancelled
            return False

        merged_record = merge_dialog.get_merged_record()
        if not merged_record:
            return False

        # Save the merged record
        try:
            # Force save the merged record (no version check since we just merged)
            self.session.db.save_record(
                merged_record, record_id, expected_version=None
            )

            # Reload to get fresh version number and update UI
            self.load_record(record_id)

            QMessageBox.information(
                self,
                "Merge Successful",
                "Your changes have been merged and saved.",
            )
            return True

        except Exception as e:
            QMessageBox.critical(
                self, "Save Failed", f"Failed to save merged record: {e}"
            )
            return False

    def _check_for_external_changes(self) -> None:
        """Periodically check if the active record was modified externally.

        If changes are detected, notify the user and offer to reload.
        """
        if not self.session.has_active_record():
            return

        record_id = self.session.get_active_record_id()
        if not record_id:
            return

        try:
            result = self.session.db.get_record_with_version(record_id)
            if not result:
                return

            _, db_version = result
            local_version = self.session._active_record_version

            if local_version is not None and db_version > local_version:
                # Record was modified externally
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("Record Updated")
                msg.setText(
                    f"This record has been updated by another user.\n\n"
                    f"Local version: {local_version}\n"
                    f"Database version: {db_version}\n\n"
                    f"Would you like to reload the record?\n"
                    f"(Your unsaved changes will be lost)"
                )
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.Yes)

                if msg.exec_() == QMessageBox.Yes:
                    self.load_record(record_id)
                    self._load_notes()

        except Exception as e:
            # Don't interrupt user with refresh errors
            print(f"Error checking for external changes: {e}")

    def _show_measurement_history(self):
        """Open dialog showing all measurement attempts."""
        if not self.session.has_active_record():
            QMessageBox.information(
                self,
                "No Active Record",
                "Please load or create a commissioning record first.",
            )
            return

        dialog = MeasurementHistoryDialog(self.session, parent=self)
        dialog.exec_()

    def _load_notes(self) -> None:
        if not self.session.has_active_record():
            self.notes_table.setRowCount(0)
            return

        phase = self.notes_phase_filter.currentData()

        # Get both general notes and measurement notes
        measurement_notes = self.session.get_measurement_notes(phase)
        general_notes = self.session.get_general_notes()

        # Combine notes with type indicator
        all_notes = []

        # Add general notes
        for note in general_notes:
            all_notes.append(
                {
                    "type": "General",
                    "phase": "",
                    "measurement_timestamp": "",
                    "timestamp": note.get("timestamp"),
                    "operator": note.get("operator"),
                    "note": note.get("note"),
                    "note_ref": ("general", general_notes.index(note)),
                }
            )

        # Add measurement notes
        for note in measurement_notes:
            # Filter by phase if selected
            if phase and note.get("phase") != phase.value:
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

        # Sort by timestamp
        all_notes.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        self.notes_table.setRowCount(len(all_notes))

        for row, item in enumerate(all_notes):
            type_item = QTableWidgetItem(item["type"])
            type_item.setData(Qt.UserRole, item["note_ref"])
            self.notes_table.setItem(row, 0, type_item)

            phase_item = QTableWidgetItem(item["phase"])
            self.notes_table.setItem(row, 1, phase_item)

            measurement_time = item["measurement_timestamp"]
            measurement_item = QTableWidgetItem(measurement_time)
            self.notes_table.setItem(row, 2, measurement_item)

            note_time = item["timestamp"] or ""
            note_time_item = QTableWidgetItem(note_time)
            self.notes_table.setItem(row, 3, note_time_item)

            operator_item = QTableWidgetItem(item["operator"] or "Unknown")
            self.notes_table.setItem(row, 4, operator_item)

            note_item = QTableWidgetItem(item["note"] or "")
            self.notes_table.setItem(row, 5, note_item)

    def _get_selected_note_ref(self):
        selected = self.notes_table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        return self.notes_table.item(row, 0).data(Qt.UserRole)

    def _resolve_note_phase(self) -> Optional[CommissioningPhase]:
        phase = self.notes_phase_filter.currentData()
        if phase:
            return phase

        current_index = self.tabs.currentIndex()
        if 0 <= current_index < len(self.phase_specs):
            spec = self.phase_specs[current_index]
            if spec.phase:
                return spec.phase

        choices = [p.value for p in CommissioningPhase]
        selection, ok = QInputDialog.getItem(
            self,
            "Select Phase",
            "Choose a phase for this note:",
            choices,
            0,
            False,
        )
        if not ok:
            return None

        return CommissioningPhase(selection)

    def _build_note_dialog(
        self,
        title: str,
        operator_default: str,
        note_default: str = "",
    ) -> tuple[Optional[str], Optional[str]]:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Operator:"))
        operator_combo = QComboBox()
        op_row.addWidget(operator_combo)
        layout.addLayout(op_row)

        layout.addWidget(QLabel("Note:"))
        note_input = QTextEdit()
        note_input.setPlainText(note_default)
        note_input.setFixedHeight(100)
        layout.addWidget(note_input)

        def populate_operator_combo(selected: str | None) -> None:
            operator_combo.blockSignals(True)
            operator_combo.clear()
            operator_combo.addItem("Select operator...", "")
            for name in self.session.get_operators():
                operator_combo.addItem(name, name)
            if selected and operator_combo.findData(selected) == -1:
                operator_combo.addItem(selected, selected)
            operator_combo.addItem("Add operator...", "__add__")
            if selected:
                idx = operator_combo.findData(selected)
                if idx >= 0:
                    operator_combo.setCurrentIndex(idx)
            operator_combo.blockSignals(False)

        def on_operator_selected() -> None:
            selection = operator_combo.currentData()
            if selection != "__add__":
                return

            name, ok = QInputDialog.getText(
                self, "Add Operator", "Enter your name:"
            )
            clean_name = name.strip()
            if not ok or not clean_name:
                operator_combo.setCurrentIndex(0)
                return

            self.session.add_operator(clean_name)
            populate_operator_combo(clean_name)

        operator_combo.currentIndexChanged.connect(on_operator_selected)
        populate_operator_combo(operator_default)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return None, None

        operator = operator_combo.currentData() or None
        note_text = note_input.toPlainText().strip() or None
        return operator, note_text

    def _on_add_general_note(self) -> None:
        if not self.session.has_active_record():
            QMessageBox.information(
                self,
                "No Active Record",
                "Please load or create a commissioning record first.",
            )
            return

        operator, note = self._build_note_dialog("Add General Note", "")
        if not note:
            return

        if self.session.append_general_note(operator, note):
            self._load_notes()

    def _on_add_measurement_note(self) -> None:
        if not self.session.has_active_record():
            QMessageBox.information(
                self,
                "No Active Record",
                "Please load or create a commissioning record first.",
            )
            return

        phase = self._resolve_note_phase()
        if not phase:
            return

        history = self.session.get_measurement_history(phase)
        if not history:
            QMessageBox.information(
                self,
                "No Measurements",
                "Run a measurement for this phase before adding notes.",
            )
            return

        entry_id = history[0]["id"]
        operator, note = self._build_note_dialog("Add Note", "")
        if not note:
            return

        if self.session.append_measurement_note(entry_id, operator, note):
            self._load_notes()

    def _on_edit_note(self) -> None:
        note_ref = self._get_selected_note_ref()
        if not note_ref:
            return

        row = self.notes_table.currentRow()
        current_operator = self.notes_table.item(row, 4).text()
        current_note = self.notes_table.item(row, 5).text()

        operator, note = self._build_note_dialog(
            "Edit Note", current_operator, current_note
        )
        if not note:
            return

        note_type, ref_data = note_ref

        if note_type == "general":
            note_index = ref_data
            if self.session.update_general_note(note_index, operator, note):
                self._load_notes()
        elif note_type == "measurement":
            entry_id, note_index = ref_data
            if self.session.update_measurement_note(
                entry_id, note_index, operator, note
            ):
                self._load_notes()


def main() -> int:
    """Run the multi-phase commissioning display standalone via PyDM."""
    app = PyDMApplication(
        ui_file=None, command_line_args=sys.argv, use_main_window=False
    )
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = MultiPhaseCommissioningDisplay()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
