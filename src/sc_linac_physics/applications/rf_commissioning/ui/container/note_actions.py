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

from sc_linac_physics.applications.rf_commissioning.models.database import (
    RecordConflictError,
)


def quick_add_note(host) -> None:
    """Quick note entry without complex dialog."""
    if not host.session.has_active_record():
        QMessageBox.warning(
            host,
            "No Record",
            "Please load or create a commissioning record first.",
        )
        return

    operator = host.operator_combo.currentData()
    if not operator:
        QMessageBox.warning(
            host, "Operator Required", "Please select an operator first."
        )
        host.operator_combo.setFocus()
        return

    note, ok = QInputDialog.getMultiLineText(
        host,
        "Quick Note",
        f"Operator: {host.operator_combo.currentText()}\n\nEnter note:",
    )

    if ok and note.strip():
        try:
            if host.session.append_general_note(operator, note.strip()):
                host._load_notes()
                host.notes_table.scrollToTop()
        except RecordConflictError as conflict:
            host._handle_note_conflict(conflict)


def show_notes_context_menu(host, position) -> None:
    """Show context menu for notes table."""
    if host.notes_table.rowCount() == 0:
        return

    menu = QMenu(host)
    edit_action = menu.addAction("✏️ Edit Note")

    action = menu.exec_(host.notes_table.viewport().mapToGlobal(position))

    if action == edit_action:
        host._on_edit_note()


def on_edit_note(host) -> None:
    """Edit selected note."""
    note_ref = get_selected_note_ref(host)
    if not note_ref:
        return

    row = host.notes_table.currentRow()
    current_operator = host.notes_table.item(row, 2).text()
    current_note = host.notes_table.item(row, 3).text()

    operator, note = build_note_dialog(
        host, "Edit Note", current_operator, current_note
    )
    if not note:
        return

    note_type, ref_data = note_ref

    if note_type == "general":
        note_index = ref_data
        try:
            if host.session.update_general_note(note_index, operator, note):
                host._load_notes()
        except RecordConflictError as conflict:
            host._handle_note_conflict(conflict)
    elif note_type == "measurement":
        entry_id, note_index = ref_data
        if host.session.update_measurement_note(
            entry_id, note_index, operator, note
        ):
            host._load_notes()


def get_selected_note_ref(host):
    """Get reference to selected note."""
    selected = host.notes_table.selectedItems()
    if not selected:
        return None

    row = selected[0].row()
    return host.notes_table.item(row, 0).data(Qt.UserRole)


def build_note_dialog(
    host,
    title: str,
    operator_default: str,
    note_default: str = "",
) -> tuple[str | None, str | None]:
    """Build note editing dialog."""
    dialog = QDialog(host)
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
        for name in host.session.get_operators():
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
            host, "Add Operator", "Enter your name:"
        )
        clean_name = name.strip()
        if not ok or not clean_name:
            operator_combo.setCurrentIndex(0)
            return

        host.session.add_operator(clean_name)
        populate_operator_combo(clean_name)

    operator_combo.currentIndexChanged.connect(on_operator_selected)
    populate_operator_combo(operator_default)

    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec_() != QDialog.Accepted:
        return None, None

    operator = operator_combo.currentData() or None
    note_text = note_input.toPlainText().strip() or None
    return operator, note_text
