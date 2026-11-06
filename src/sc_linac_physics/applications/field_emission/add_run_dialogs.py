"""The "Add New Data" dialogs: add one run from a form, or many from a CSV.

The work runs in gui_updater.UpdateWorker on a daemon thread; see
field_emission_gui.FieldEmission.open_update_dialog for where they open.
"""

import threading

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from sc_linac_physics.applications.field_emission.gui_updater import (
    UpdateWorker,
    validate_emission_data,
)


class UpdateButtons(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(195, 125)
        layout = QVBoxLayout(self)

        self.single_btn = QPushButton("Single CM")
        self.single_btn.clicked.connect(self.update_in_single_mode)
        layout.addWidget(self.single_btn)

        self.multi_btn = QPushButton("Multi CMs from CSV")
        self.multi_btn.clicked.connect(self.update_in_multi_mode)
        layout.addWidget(self.multi_btn)

    def update_in_single_mode(self):
        dialog = SingleInputDialog()
        if dialog.exec():
            input_row = dialog.get_inputs()
            try:
                valid = validate_emission_data(input_row)
            except ValueError as e:
                QMessageBox.warning(self, "Invalid input", str(e))
                return
            self._do_background_task("single", valid, input_row)

    def update_in_multi_mode(self):
        dialog = MultiInputDialog()
        if dialog.exec():
            input_csv = dialog.get_input()
            self._do_background_task("multi", input_csv)

    def _do_background_task(self, mode, *args):
        # The worker stays on the main thread; its signals, emitted from the
        # daemon thread, are delivered here on the main thread.
        self.worker = UpdateWorker(mode, *args)
        self.progress_dialog = self._build_progress_dialog()
        self.worker.error.connect(self._on_worker_error)
        self.worker.progress.connect(self.progress_dialog.setLabelText)
        self.worker.finished.connect(self._on_worker_finished)
        self._run_in_background(self.worker.run)

    @staticmethod
    def _run_in_background(target):
        # Daemon, so a hung archiver request can't keep the app open
        threading.Thread(target=target, daemon=True).start()

    def _build_progress_dialog(self):
        self.progress_dialog = QProgressDialog(
            "Working on it...", None, 0, 0, self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setWindowTitle("Updating")
        self.progress_dialog.show()
        return self.progress_dialog

    def _on_worker_error(self, message):
        self.progress_dialog.close()
        QMessageBox.warning(self, "Update failed", message)

    def _on_worker_finished(self, message):
        QMessageBox.information(self, "Update Complete", message)
        self.progress_dialog.close()
        self.accept()


class SingleInputDialog(QDialog):
    FIELDS = [
        ("cryo", "Cryomodule #"),
        ("date_s", "Start Date (mm/dd/yy)"),
        ("time_s", "Start Time (24 hr hh:mm)"),
        ("date_e", "End Date (optional)"),
        ("time_e", "End Time (24 hr hh:mm)"),
        ("decarad", "Decarad"),
        ("elog", "eLog link"),
        ("notes", "Notes"),
        ("filter_r", "Recharacterization (Y/N)"),
        ("filter_m", "Multipacting (Y/N)"),
        ("filter_c", "Commissioning (Y/N)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.lines = {}
        layout = QFormLayout(self)
        for label, field in self.FIELDS:
            self.lines[label] = QLineEdit(self)
            layout.addRow(field, self.lines[label])
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_inputs(self):
        return tuple(self.lines[label].text() for label, _ in self.FIELDS)


class MultiInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.line_csv = QLineEdit(self)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )

        layout = QFormLayout(self)
        layout.addRow("CSV path", self.line_csv)
        layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_input(self):
        return self.line_csv.text()
