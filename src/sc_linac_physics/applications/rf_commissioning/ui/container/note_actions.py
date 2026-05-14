"""Notes interaction helpers for the multi-phase commissioning container."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)


class _NoteActionsMixin:
    def _quick_add_note(self) -> None:
        """Quick note entry without complex dialog."""
        if not self.session.has_active_record():
            QMessageBox.warning(
                self,
                "No Record",
                "Please load or create a commissioning record first.",
            )
            return

        operator = self.operator_combo.currentData()
        if not operator:
            QMessageBox.warning(
                self, "Operator Required", "Please select an operator first."
            )
            self.operator_combo.setFocus()
            return

        note, ok = QInputDialog.getMultiLineText(
            self,
            "Quick Note",
            f"Operator: {self.operator_combo.currentText()}\n\nEnter note:",
        )

        if ok and note.strip():
            try:
                if self.session.append_general_note(operator, note.strip()):
                    self._load_notes()
                    self.notes_table.scrollToTop()
            except RecordConflictError as conflict:
                self._handle_note_conflict(conflict)

    def _show_notes_context_menu(self, position) -> None:
        """Show context menu for notes table."""
        if self.notes_table.rowCount() == 0:
            return

        menu = QMenu(self)
        edit_action = menu.addAction("✏️ Edit Note")

        action = menu.exec_(self.notes_table.viewport().mapToGlobal(position))

        if action == edit_action:
            self._on_edit_note()

    def _on_edit_note(self) -> None:
        """Edit selected note."""
        note_ref = self._get_selected_note_ref()
        if not note_ref:
            return

        row = self.notes_table.currentRow()
        current_operator = self.notes_table.item(row, 2).text()
        current_note = self.notes_table.item(row, 3).text()

        operator, note = self._build_note_dialog(
            "Edit Note", current_operator, current_note
        )
        if not note:
            return

        note_type, ref_data = note_ref

        if note_type == "general":
            note_index = ref_data
            try:
                if self.session.update_general_note(note_index, operator, note):
                    self._load_notes()
            except RecordConflictError as conflict:
                self._handle_note_conflict(conflict)
        elif note_type == "measurement":
            entry_id, note_index = ref_data
            if self.session.update_measurement_note(
                entry_id, note_index, operator, note
            ):
                self._load_notes()

    def _get_selected_note_ref(self):
        """Get reference to selected note."""
        selected = self.notes_table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        return self.notes_table.item(row, 0).data(Qt.UserRole)

    def _build_note_dialog(
        self,
        title: str,
        operator_default: str,
        note_default: str = "",
    ) -> tuple[str | None, str | None]:
        """Build note editing dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Operator:"))
        operator_combo = QComboBox()
        op_row.addWidget(operator_combo)
        layout.addLayout(op_row)

        layout.addWidget(QLabel("Note:"))
        note_input = QTextEdit()
        note_input.setPlainText(note_default)
        note_input.setMinimumHeight(100)
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


# Backward-compat aliases so existing tests continue to work.
quick_add_note = _NoteActionsMixin._quick_add_note
show_notes_context_menu = _NoteActionsMixin._show_notes_context_menu
on_edit_note = _NoteActionsMixin._on_edit_note
get_selected_note_ref = _NoteActionsMixin._get_selected_note_ref
build_note_dialog = _NoteActionsMixin._build_note_dialog
