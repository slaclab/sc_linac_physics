"""Multi-phase commissioning container display."""

import signal
import sys

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
)
from pydm import Display, PyDMApplication

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.container import (
    PhaseTabSpec,
    build_default_phase_specs,
    _HeaderMixin,
    _ProgressMixin,
    _RecordSelectorMixin,
    _TabsMixin,
    _NotesPanelMixin,
    _NoteActionsMixin,
    _SyncMixin,
    _PersistenceMixin,
    _RecordLifecycleMixin,
)
from sc_linac_physics.applications.rf_commissioning.ui.magnet_checkout_dialog import (
    MagnetCheckoutDialog,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    get_linac_for_cryomodule,
)


class MultiPhaseCommissioningDisplay(
    _TabsMixin,
    _SyncMixin,
    _PersistenceMixin,
    _RecordLifecycleMixin,
    _RecordSelectorMixin,
    _NotesPanelMixin,
    _NoteActionsMixin,
    _ProgressMixin,
    _HeaderMixin,
    Display,
):
    """Container window that hosts multiple phase displays.

    This redesigned display keeps critical information always visible:
    - Operator selection
    - Cavity/cryomodule selection
    - Progress indicator
    - Sync status
    - Notes panel

    External updates are prominently displayed with reload options.
    """

    def __init__(
        self,
        parent=None,
        session: CommissioningSession | None = None,
        phase_specs: list[PhaseTabSpec] | None = None,
        refresh_interval_ms: int = 5000,
    ):
        super().__init__(parent)
        self.setWindowTitle("RF Commissioning")
        self.setMinimumSize(1200, 800)

        self.session = session or CommissioningSession()
        self.phase_specs = phase_specs or build_default_phase_specs()

        # Track update banner state
        self._update_banner = None

        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Store for later access (CM panel insertion)
        self._main_layout = main_layout

        # 1. PERSISTENT HEADER (always visible)
        header = self._build_header_panel()
        main_layout.addWidget(header)

        # Banner will be inserted at position 1 when needed

        # 2. COMPACT CAVITY PHASE PROGRESS (always visible)
        progress = self._build_compact_progress_bar()
        main_layout.addWidget(progress)

        # 4. MAIN CONTENT AREA (scrollable)
        content_splitter = QSplitter(Qt.Vertical)

        # Phase tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        content_splitter.addWidget(self.tabs)

        # Notes panel (collapsible but always accessible)
        notes_panel = self._build_enhanced_notes_panel()
        content_splitter.addWidget(notes_panel)

        # Initial sizes: 70% tabs, 30% notes
        content_splitter.setSizes([700, 300])
        content_splitter.setCollapsible(0, False)  # Tabs can't collapse
        content_splitter.setCollapsible(1, True)  # Notes can collapse

        main_layout.addWidget(content_splitter)

        self.setLayout(main_layout)

        self._phase_displays: list = []
        self._init_tabs()
        self._update_tab_states()
        self._load_notes()

        # Setup periodic refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._check_for_external_changes)
        if refresh_interval_ms > 0:
            self._refresh_timer.start(refresh_interval_ms)

        # REMOVED: self._restore_last_session()
        # Operator must explicitly select operator and cavity each time

    def _on_cavity_selection_changed(self) -> None:
        """Update CM status on CM change; load cavity record only when cavity is selected."""
        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        # CM-level status is independent of cavity selection
        if cryomodule and cryomodule != "Select CM...":
            linac = get_linac_for_cryomodule(cryomodule)
            if linac:
                self._refresh_magnet_badge(cryomodule, linac)
                self._refresh_cavity_completion_label(cryomodule, linac)
        else:
            self._refresh_magnet_badge("Select CM...")
            self._refresh_cavity_completion_label("Select CM...")

        # Skip if no valid selection
        if (
            cryomodule == "Select CM..."
            or cavity == "Select Cav..."
            or not cryomodule
            or not cavity
        ):
            return

        created = self.start_new_record(cryomodule, cavity)
        self._update_sync_status(
            True, "New record started" if created else "Record loaded"
        )

    def _refresh_magnet_badge(
        self, cryomodule: str, linac: str | None = None
    ) -> None:
        """Refresh header magnet badge for the selected cryomodule."""
        if not cryomodule or cryomodule == "Select CM...":
            self.magnet_status_badge.set_status("PENDING")
            return

        effective_linac = linac or get_linac_for_cryomodule(cryomodule)
        if not effective_linac:
            self.magnet_status_badge.set_status("PENDING")
            return

        cm_record = self.session.get_cryomodule_record(
            effective_linac, cryomodule
        )
        if cm_record is None or cm_record.magnet_checkout is None:
            self.magnet_status_badge.set_status("PENDING")
        elif cm_record.magnet_checkout.passed:
            self.magnet_status_badge.set_status("PASS")
        else:
            self.magnet_status_badge.set_status("FAIL")

    def _refresh_cavity_completion_label(
        self, cryomodule: str, linac: str | None = None
    ) -> None:
        """Update header cavity completion counter for the selected cryomodule."""
        if not cryomodule or cryomodule == "Select CM...":
            self.cavity_completion_label.setText("0/8 Complete")
            return

        effective_linac = linac or get_linac_for_cryomodule(cryomodule)
        if not effective_linac:
            self.cavity_completion_label.setText("0/8 Complete")
            return

        linac_index = int(effective_linac[1])
        cavity_records = self.session.get_records_by_cryomodule(
            linac_index, cryomodule, active_only=False
        )
        completed = sum(
            1
            for record in cavity_records
            if record.current_phase and record.current_phase.value == "complete"
        )
        self.cavity_completion_label.setText(f"{completed}/8 Complete")

    def _open_magnet_checkout_screen(self) -> None:
        """Open modal dialog for CM magnet checkout status and notes."""
        cryomodule = self.cryomodule_combo.currentText()
        if not cryomodule or cryomodule == "Select CM...":
            QMessageBox.information(
                self,
                "Select Cryomodule",
                "Select a cryomodule first to edit magnet checkout.",
            )
            return

        linac = get_linac_for_cryomodule(cryomodule)
        if not linac:
            QMessageBox.warning(
                self,
                "Invalid Cryomodule",
                f"Could not determine linac for cryomodule {cryomodule}.",
            )
            return

        dialog = MagnetCheckoutDialog(
            self.session, linac, cryomodule, parent=self
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        if not dialog.save():
            return

        self._refresh_magnet_badge(cryomodule, linac)
        self._refresh_cavity_completion_label(cryomodule)
        self._update_sync_status(True, "Magnet checkout updated")

    def _populate_operator_combo(self, restore_selection: str = None) -> None:
        """Populate operator dropdown - no default selection for safety."""
        self.operator_combo.blockSignals(True)
        self.operator_combo.clear()

        operators = self.session.get_operators()

        # Always start with placeholder - no default
        self.operator_combo.addItem("👤 Select operator...", "")

        if operators:
            for op in operators:
                self.operator_combo.addItem(f"👤 {op}", op)

        self.operator_combo.insertSeparator(self.operator_combo.count())
        self.operator_combo.addItem("➕ Add new operator...", "__add__")

        # Only restore if explicitly requested (e.g., after adding new operator)
        if restore_selection:
            idx = self.operator_combo.findData(restore_selection)
            if idx >= 0:
                self.operator_combo.setCurrentIndex(idx)
        # REMOVED: else block that auto-restored from settings

        self.operator_combo.blockSignals(False)

    def _on_operator_changed(self, index: int) -> None:
        """Handle operator selection change."""
        selection = self.operator_combo.currentData()

        if selection == "__add__":
            self._add_new_operator()

    def _add_new_operator(self) -> None:
        """Add a new operator with validation."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Operator")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Enter your full name:"))

        name_input = QLineEdit()
        name_input.setPlaceholderText("First Last")
        layout.addWidget(name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            name = name_input.text().strip()
            if name:
                self.session.add_operator(name)
                self._populate_operator_combo(restore_selection=name)
                return

        # Reset to previous selection if cancelled
        self.operator_combo.setCurrentIndex(0)

    @staticmethod
    def _linac_str(linac: int) -> str:
        return f"L{linac}B"

    def _update_cm_status_panel(self, record: CommissioningRecord) -> None:
        """Update CM-level header info when record is loaded or changed."""
        if record is None:
            return

        linac_str = self._linac_str(record.linac)
        self._refresh_magnet_badge(record.cryomodule, linac_str)
        self._refresh_cavity_completion_label(record.cryomodule, linac_str)

    def _open_batch_pre_rf_window(self) -> None:
        """Open (or raise) the floating batch Piezo Pre-RF window."""
        from sc_linac_physics.applications.rf_commissioning.ui.displays.batch_piezo_pre_rf import (
            BatchPiezoPreRFWindow,
        )

        if not hasattr(self, "_batch_window") or self._batch_window is None:
            self._batch_window = BatchPiezoPreRFWindow(
                parent=self, session=self.session
            )
        self._batch_window.show()
        self._batch_window.raise_()


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
