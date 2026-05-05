"""Batch Piezo Pre-RF execution window.

Launched from the main commissioning screen via a header button. Allows
operators to select any combination of cavities (from a single cavity up to
the full machine) and run the Piezo Pre-RF test using the trigger-then-collect
approach.
"""

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sc_linac_physics.applications.rf_commissioning.ui.controllers.batch_piezo_pre_rf_controller import (
    BatchPiezoPreRFController,
    CavitySpec,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_MAP

_LINAC_NAMES = ["L0B", "L1B", "L2B", "L3B", "L4B"]

_STATUS_COLORS: dict[str, str] = {
    "PENDING": "#888888",
    "TRIGGERING": "#4fc3f7",
    "TRIGGERED": "#29b6f6",
    "COLLECTING": "#ffa726",
    "PASSED": "#66bb6a",
    "FAILED": "#ef5350",
    "ERROR": "#ab47bc",
    "SKIPPED": "#78909c",
}

_TABLE_COLS = [
    "Linac",
    "CM",
    "Cav",
    "Status",
    "Ch A",
    "Ch B",
    "Cap A (nF)",
    "Cap B (nF)",
    "Overall",
]
(
    _COL_LINAC,
    _COL_CM,
    _COL_CAV,
    _COL_STATUS,
    _COL_CHA,
    _COL_CHB,
    _COL_CAPA,
    _COL_CAPB,
    _COL_OVERALL,
) = range(9)


class BatchPiezoPreRFWindow(QWidget):
    """Non-modal window for running Piezo Pre-RF tests across multiple cavities.

    Can be instantiated as ``BatchPiezoPreRFWindow(parent, session)`` so it
    integrates with the container's ``init_tabs`` machinery if ever needed,
    but it is designed to be shown as a floating window launched from the
    header button.
    """

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ) -> None:
        super().__init__(parent, Qt.Window)
        self.session = session or CommissioningSession()
        self.setWindowTitle("Batch Piezo Pre-RF")
        self.setMinimumSize(1000, 700)

        self._controller = BatchPiezoPreRFController(self.session)
        self._controller.cavity_status_changed.connect(self._on_cavity_status)
        self._controller.cavity_result_ready.connect(self._on_cavity_result)
        self._controller.batch_progress.connect(self._on_batch_progress)
        self._controller.batch_finished.connect(self._on_batch_finished)
        self._controller.log_message.connect(self._append_log)

        # cavity_key → table row index
        self._row_by_key: dict[str, int] = {}

        self._build_ui()
        self._populate_tree()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_tree_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setSizes([280, 720])
        root.addWidget(splitter, stretch=1)

        root.addWidget(self._build_log_panel())

        self.setLayout(root)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self._operator_label = QLabel("Operator: —")
        self._operator_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._operator_label)

        layout.addStretch()

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._select_all)
        layout.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.clicked.connect(self._deselect_all)
        layout.addWidget(self._deselect_all_btn)

        layout.addSpacing(16)

        self._run_btn = QPushButton("▶  Run Selected")
        self._run_btn.setStyleSheet("font-weight: bold; padding: 4px 12px;")
        self._run_btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(self._run_btn)

        self._abort_btn = QPushButton("■  Abort")
        self._abort_btn.setEnabled(False)
        self._abort_btn.clicked.connect(self._on_abort_clicked)
        layout.addWidget(self._abort_btn)

        layout.addSpacing(16)

        self._progress_label = QLabel("0 / 0")
        layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(1)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(160)
        layout.addWidget(self._progress_bar)

        bar.setLayout(layout)
        return bar

    def _build_tree_panel(self) -> QWidget:
        group = QGroupBox("Cavity Selection")
        layout = QVBoxLayout()

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Linac / CM / Cavity")
        self._tree.setSelectionMode(QAbstractItemView.NoSelection)
        self._tree.itemChanged.connect(self._on_tree_item_changed)
        layout.addWidget(self._tree)

        self._selection_count_label = QLabel("0 cavities selected")
        self._selection_count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._selection_count_label)

        group.setLayout(layout)
        return group

    def _build_results_panel(self) -> QWidget:
        group = QGroupBox("Results")
        layout = QVBoxLayout()

        self._table = QTableWidget(0, len(_TABLE_COLS))
        self._table.setHorizontalHeaderLabels(_TABLE_COLS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_LINAC, QHeaderView.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_CM, QHeaderView.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_CAV, QHeaderView.ResizeToContents
        )
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        layout.addWidget(self._table)

        group.setLayout(layout)
        return group

    def _build_log_panel(self) -> QWidget:
        group = QGroupBox("Log")
        group.setMaximumHeight(160)
        layout = QVBoxLayout()

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self._log)

        group.setLayout(layout)
        return group

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()

        for linac_name, cm_list in zip(_LINAC_NAMES, LINAC_CM_MAP):
            linac_item = QTreeWidgetItem(self._tree, [linac_name])
            linac_item.setFlags(
                linac_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsTristate
            )
            linac_item.setCheckState(0, Qt.Unchecked)

            for cm in cm_list:
                cm_item = QTreeWidgetItem(linac_item, [f"CM {cm}"])
                cm_item.setFlags(
                    cm_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsTristate
                )
                cm_item.setCheckState(0, Qt.Unchecked)
                cm_item.setData(0, Qt.UserRole, ("cm", cm))

                for cav_num in range(1, 9):
                    cav_item = QTreeWidgetItem(cm_item, [f"Cav {cav_num}"])
                    cav_item.setFlags(cav_item.flags() | Qt.ItemIsUserCheckable)
                    cav_item.setCheckState(0, Qt.Unchecked)
                    cav_item.setData(0, Qt.UserRole, ("cav", cm, cav_num))

        self._tree.blockSignals(False)
        self._update_selection_count()

    # ------------------------------------------------------------------
    # Tree helpers
    # ------------------------------------------------------------------

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        self._update_selection_count()

    def _select_all(self) -> None:
        self._set_all_check_state(Qt.Checked)

    def _deselect_all(self) -> None:
        self._set_all_check_state(Qt.Unchecked)

    def _set_all_check_state(self, state: Qt.CheckState) -> None:
        self._tree.blockSignals(True)
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            linac_item = root.child(i)
            linac_item.setCheckState(0, state)
            for j in range(linac_item.childCount()):
                cm_item = linac_item.child(j)
                cm_item.setCheckState(0, state)
                for k in range(cm_item.childCount()):
                    cm_item.child(k).setCheckState(0, state)
        self._tree.blockSignals(False)
        self._update_selection_count()

    def _get_selected_cavities(self) -> list[CavitySpec]:
        selected: list[CavitySpec] = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            linac_item = root.child(i)
            for j in range(linac_item.childCount()):
                cm_item = linac_item.child(j)
                for k in range(cm_item.childCount()):
                    cav_item = cm_item.child(k)
                    if cav_item.checkState(0) == Qt.Checked:
                        data = cav_item.data(0, Qt.UserRole)
                        if data and data[0] == "cav":
                            _, cm, cav_num = data
                            selected.append(
                                CavitySpec(cryomodule=cm, cavity_number=cav_num)
                            )
        return selected

    def _update_selection_count(self) -> None:
        count = len(self._get_selected_cavities())
        self._selection_count_label.setText(
            f"{count} {'cavity' if count == 1 else 'cavities'} selected"
        )

    # ------------------------------------------------------------------
    # Run / Abort
    # ------------------------------------------------------------------

    def _on_run_clicked(self) -> None:
        operator = self._get_operator()
        if not operator:
            self._append_log(
                "ERROR: No operator selected. Choose an operator in the main window header."
            )
            return

        cavities = self._get_selected_cavities()
        if not cavities:
            self._append_log("No cavities selected.")
            return

        self._operator_label.setText(f"Operator: {operator}")
        self._setup_results_table(cavities)
        self._run_btn.setEnabled(False)
        self._abort_btn.setEnabled(True)
        self._progress_bar.setMaximum(len(cavities))
        self._progress_bar.setValue(0)
        self._progress_label.setText(f"0 / {len(cavities)}")

        self._append_log(
            f"Starting batch run: {len(cavities)} cavities, operator={operator}"
        )
        self._controller.run_batch(cavities, operator)

    def _on_abort_clicked(self) -> None:
        self._controller.abort()
        self._abort_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Results table
    # ------------------------------------------------------------------

    def _setup_results_table(self, cavities: list[CavitySpec]) -> None:
        self._table.setRowCount(0)
        self._row_by_key.clear()

        for spec in cavities:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._row_by_key[spec.key] = row

            linac_name = spec.linac_name or "?"
            self._set_cell(row, _COL_LINAC, linac_name)
            self._set_cell(row, _COL_CM, spec.cryomodule)
            self._set_cell(row, _COL_CAV, str(spec.cavity_number))
            self._set_cell(
                row, _COL_STATUS, "PENDING", color=_STATUS_COLORS["PENDING"]
            )
            for col in (_COL_CHA, _COL_CHB, _COL_CAPA, _COL_CAPB, _COL_OVERALL):
                self._set_cell(row, col, "—")

    def _set_cell(
        self, row: int, col: int, text: str, color: str | None = None
    ) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        if color:
            item.setForeground(QColor(color))
        self._table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Controller signal handlers
    # ------------------------------------------------------------------

    @pyqtSlot(str, str)
    def _on_cavity_status(self, key: str, status: str) -> None:
        row = self._row_by_key.get(key)
        if row is None:
            return
        color = _STATUS_COLORS.get(status, "#ffffff")
        self._set_cell(row, _COL_STATUS, status, color=color)

    @pyqtSlot(str, object)
    def _on_cavity_result(self, key: str, result) -> None:
        row = self._row_by_key.get(key)
        if row is None or result is None:
            return

        def bool_text(v: bool) -> str:
            return "PASS" if v else "FAIL"

        def bool_color(v: bool) -> str:
            return _STATUS_COLORS["PASSED"] if v else _STATUS_COLORS["FAILED"]

        cha_pass = result.channel_a_passed
        chb_pass = result.channel_b_passed
        overall = result.passed

        self._set_cell(
            row, _COL_CHA, bool_text(cha_pass), color=bool_color(cha_pass)
        )
        self._set_cell(
            row, _COL_CHB, bool_text(chb_pass), color=bool_color(chb_pass)
        )
        self._set_cell(row, _COL_CAPA, f"{result.capacitance_a * 1e9:.2f}")
        self._set_cell(row, _COL_CAPB, f"{result.capacitance_b * 1e9:.2f}")
        self._set_cell(
            row, _COL_OVERALL, bool_text(overall), color=bool_color(overall)
        )

    @pyqtSlot(int, int)
    def _on_batch_progress(self, completed: int, total: int) -> None:
        self._progress_bar.setValue(completed)
        self._progress_label.setText(f"{completed} / {total}")

    @pyqtSlot()
    def _on_batch_finished(self) -> None:
        self._run_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._append_log("Batch run complete.")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def _append_log(self, message: str) -> None:
        self._log.append(message)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    # ------------------------------------------------------------------
    # Operator resolution
    # ------------------------------------------------------------------

    def _get_operator(self) -> str:
        """Read the operator from the parent commissioning window."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "operator_combo"):
                data = parent.operator_combo.currentData()
                if data and data != "__add__":
                    return data
                text = parent.operator_combo.currentText()
                if text and not text.startswith("👤 Select"):
                    return text.replace("👤 ", "").strip()
            parent = parent.parent() if hasattr(parent, "parent") else None
        return ""
