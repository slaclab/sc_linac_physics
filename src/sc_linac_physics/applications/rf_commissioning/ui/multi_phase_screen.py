"""Multi-phase commissioning container display."""

import signal
import sys

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QComboBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from pydm import Display as PyDMDisplay, PyDMApplication

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CryomoduleCheckoutRecord,
    CryomodulePhase,
    CryomodulePhaseStatus,
    MagnetCheckoutData,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    get_linac_for_cryomodule,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)

from sc_linac_physics.applications.rf_commissioning.ui.container import (
    PhaseTabSpec,
    build_note_dialog,
    build_default_phase_specs,
    build_enhanced_notes_panel,
    build_header_panel,
    build_progress_phases,
    check_for_external_changes,
    confirm_and_start_new,
    dismiss_banner,
    handle_note_conflict,
    load_selected_record,
    load_notes,
    on_load_or_start,
    on_edit_note,
    quick_add_note,
    reload_from_banner,
    get_selected_note_ref,
    handle_save_conflict,
    load_record,
    save_active_record,
    on_phase_advanced,
    on_tab_changed,
    start_new_record,
    show_database_browser,
    show_measurement_history,
    show_update_banner,
    show_notes_context_menu,
    show_record_selector,
    sync_cavity_selection_from_record,
    init_tabs,
    start_new_from_dialog,
    get_phase_icon,
    update_sync_status,
    update_tab_states,
)


class MultiPhaseCommissioningDisplay(PyDMDisplay):
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
        self.phase_specs = phase_specs or self._default_phase_specs()

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

        self._phase_displays: list[PhaseDisplayBase] = []
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

    def _default_phase_specs(self) -> list[PhaseTabSpec]:
        """Build default phase tabs for the container display."""
        return build_default_phase_specs()

    # =============================================================================
    # HEADER PANEL - Always visible operator/cavity selection
    # =============================================================================
    def _build_header_panel(self) -> QWidget:
        """Build persistent header with operator and cavity selection."""
        return build_header_panel(self)

    def _on_cavity_selection_changed(self) -> None:
        """Update CM status on CM change; load cavity record only when cavity is selected."""
        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        # CM-level status is independent of cavity selection
        if cryomodule and cryomodule != "Select CM...":
            linac = get_linac_for_cryomodule(cryomodule)
            if linac:
                self._refresh_magnet_badge(cryomodule, linac)
                self._refresh_cavity_completion_label(cryomodule)
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

        cm_record = self.session.db.get_cryomodule_record(
            effective_linac, cryomodule
        )
        if cm_record is None or cm_record.magnet_checkout is None:
            self.magnet_status_badge.set_status("PENDING")
        elif cm_record.magnet_checkout.passed:
            self.magnet_status_badge.set_status("PASS")
        else:
            self.magnet_status_badge.set_status("FAIL")

    def _refresh_cavity_completion_label(self, cryomodule: str) -> None:
        """Update header cavity completion counter for the selected cryomodule."""
        if not cryomodule or cryomodule == "Select CM...":
            self.cavity_completion_label.setText("0/8 Complete")
            return

        cavity_records = self.session.db.get_records_by_cryomodule(
            cryomodule, active_only=False
        )
        completed = sum(
            1
            for record in cavity_records
            if (
                record.current_phase.value == "complete"
                or record.overall_status == "in_progress"
                and record.current_phase.get_next_phase() is None
            )
        )
        self.cavity_completion_label.setText(f"{completed}/8 Complete")

    def _open_magnet_checkout_screen(self) -> None:  # noqa: C901
        """Open modal screen for CM magnet checkout status and notes."""
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

        loaded = self.session.db.get_cryomodule_record_with_version(
            linac, cryomodule
        )
        if loaded is None:
            cm_record = CryomoduleCheckoutRecord(
                linac=linac, cryomodule=cryomodule
            )
            cm_record_id = None
            cm_record_version = None
        else:
            cm_record, cm_record_version = loaded
            cm_record_id = self.session.db.get_cryomodule_record_id(
                linac, cryomodule
            )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Magnet Checkout - {linac}_CM{cryomodule}")
        dialog_layout = QVBoxLayout()

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        status_combo = QComboBox()
        status_combo.addItems(["PENDING", "PASS", "FAIL"])
        status_row.addWidget(status_combo)
        dialog_layout.addLayout(status_row)

        # Operator selection (required for PASS/FAIL)
        operator_row = QHBoxLayout()
        operator_row.addWidget(QLabel("Operator:"))
        operator_combo = QComboBox()
        operator_combo.addItem("👤 Select operator...", "")
        for op in self.session.get_operators():
            operator_combo.addItem(f"👤 {op}", op)
        operator_combo.setMinimumWidth(200)
        operator_row.addWidget(operator_combo)
        dialog_layout.addLayout(operator_row)

        dialog_layout.addWidget(QLabel("Notes:"))
        notes_input = QTextEdit()
        notes_input.setPlaceholderText(
            "Optional notes for magnet checkout result"
        )
        notes_input.setMinimumHeight(120)
        dialog_layout.addWidget(notes_input)

        if cm_record.magnet_checkout is None:
            status_combo.setCurrentText("PENDING")
            notes_input.setPlainText(cm_record.notes or "")
        else:
            status_combo.setCurrentText(
                "PASS" if cm_record.magnet_checkout.passed else "FAIL"
            )
            notes_input.setPlainText(cm_record.magnet_checkout.notes or "")
            # Pre-populate operator if exists
            if cm_record.magnet_checkout.operator:
                idx = operator_combo.findData(
                    cm_record.magnet_checkout.operator
                )
                if idx >= 0:
                    operator_combo.setCurrentIndex(idx)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)

        dialog.setLayout(dialog_layout)

        if dialog.exec_() != QDialog.Accepted:
            return

        selected_status = status_combo.currentText().upper()
        selected_operator = operator_combo.currentData() or ""

        # Validate operator is selected for PASS/FAIL
        if selected_status != "PENDING" and not selected_operator:
            QMessageBox.warning(
                self,
                "Operator Required",
                "An operator must be selected for PASS/FAIL checkout results.",
            )
            return

        notes = notes_input.toPlainText().strip()

        if selected_status == "PENDING":
            cm_record.magnet_checkout = None
            cm_record.set_phase_status(
                CryomodulePhase.MAGNET_CHECKOUT,
                CryomodulePhaseStatus.NOT_STARTED,
            )
        else:
            cm_record.magnet_checkout = MagnetCheckoutData(
                passed=(selected_status == "PASS"),
                operator=selected_operator,
                notes=notes,
            )
            cm_record.set_phase_status(
                CryomodulePhase.MAGNET_CHECKOUT,
                (
                    CryomodulePhaseStatus.COMPLETE
                    if selected_status == "PASS"
                    else CryomodulePhaseStatus.FAILED
                ),
            )

        cm_record.notes = notes

        try:
            self.session.db.save_cryomodule_record(
                cm_record,
                record_id=cm_record_id,
                expected_version=cm_record_version,
            )
        except RecordConflictError as conflict:
            QMessageBox.warning(
                self,
                "Save Conflict",
                (
                    "Magnet checkout was updated by another user. "
                    f"Expected version {conflict.expected_version}, "
                    f"database has version {conflict.current_version}."
                ),
            )
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
            # Add all operators
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

        layout.addWidget(QLabel("Initials (optional):"))
        initials_input = QLineEdit()
        initials_input.setPlaceholderText("FL")
        initials_input.setMaxLength(4)
        layout.addWidget(initials_input)

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

    # =============================================================================
    # PROGRESS BAR - Compact horizontal phase indicator
    # =============================================================================

    def _build_compact_progress_bar(self) -> QWidget:
        """Build a compact horizontal progress indicator."""
        widget = QWidget()
        widget.setMaximumHeight(100)
        widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-bottom: 1px solid #333;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        title = QLabel("Commissioning Progress")
        title.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        main_layout.addWidget(title)

        # Container for the progress tracker
        progress_container = QWidget()
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(0)
        progress_layout.setContentsMargins(20, 0, 20, 0)

        phases = build_progress_phases()

        self.phase_indicators = {}
        self.phase_connectors = []

        for i, (label, phase) in enumerate(phases):
            # Create a container for each phase node
            node_container = QWidget()
            node_layout = QVBoxLayout()
            node_layout.setSpacing(4)
            node_layout.setContentsMargins(0, 0, 0, 0)
            node_layout.setAlignment(Qt.AlignCenter)

            # Phase circle - REMOVED setFixedSize, using minimumSize instead
            circle = QLabel("●")
            circle.setAlignment(Qt.AlignCenter)
            circle.setMinimumSize(32, 32)  # Changed from setFixedSize
            circle.setStyleSheet("""
                font-size: 28px;
                color: #444;
                background-color: transparent;
            """)
            self.phase_indicators[phase] = circle

            # Label
            text = QLabel(label)
            text.setAlignment(Qt.AlignCenter)
            text.setStyleSheet(
                "font-size: 9px; color: #888; background-color: transparent;"
            )
            text.setWordWrap(True)
            text.setFixedWidth(60)

            node_layout.addWidget(circle)
            node_layout.addWidget(text)
            node_container.setLayout(node_layout)

            progress_layout.addWidget(node_container)

            # Add connector line (skip after last phase)
            if i < len(phases) - 1:
                connector = QLabel("━━━━")
                connector.setAlignment(Qt.AlignCenter)
                connector.setStyleSheet("""
                    color: #444;
                    font-size: 16px;
                    padding: 0px;
                    margin: 0px 4px 24px 4px;
                    background-color: transparent;
                """)
                connector.setFixedHeight(32)
                self.phase_connectors.append(connector)
                progress_layout.addWidget(connector)

        progress_container.setLayout(progress_layout)
        main_layout.addWidget(progress_container)

        widget.setLayout(main_layout)
        return widget

    def update_progress_indicator(self, record) -> None:
        """Update the compact progress bar."""
        projection = self.session.get_active_phase_projection() or {}
        current_phase = projection.get("current_phase", record.current_phase)
        phase_status = projection.get("phase_status", record.phase_status)

        phase_order = CommissioningPhase.get_phase_order()
        current_idx = phase_order.index(current_phase)

        for phase, indicator in self.phase_indicators.items():
            idx = phase_order.index(phase)
            status = phase_status.get(phase)
            if status is not None and status.value in {"complete", "skipped"}:
                # Completed - green checkmark (using more compatible character)
                indicator.setText("✔")  # Alternative: "☑" or "●"
                indicator.setStyleSheet("""
                    font-size: 28px;
                    color: #4CAF50;
                    font-weight: bold;
                    background-color: rgba(76, 175, 80, 0.2);
                    border-radius: 16px;
                    border: 2px solid #4CAF50;
                """)
            elif status is not None and status.value == "failed":
                indicator.setText("✖")
                indicator.setStyleSheet("""
                    font-size: 24px;
                    color: #ef5350;
                    font-weight: bold;
                    background-color: rgba(239, 83, 80, 0.2);
                    border-radius: 16px;
                    border: 2px solid #ef5350;
                """)
            elif idx == current_idx:
                # Active - blue with pulse effect
                indicator.setText("▶")
                indicator.setStyleSheet("""
                    font-size: 24px;
                    color: #2196F3;
                    font-weight: bold;
                    background-color: rgba(33, 150, 243, 0.3);
                    border-radius: 16px;
                    border: 2px solid #2196F3;
                """)
            else:
                # Pending - gray circle
                indicator.setText("○")
                indicator.setStyleSheet("""
                    font-size: 28px;
                    color: #444;
                    background-color: transparent;
                    border-radius: 16px;
                """)

        # Update connector lines
        for i, connector in enumerate(self.phase_connectors):
            if i < current_idx:
                # Completed path - green
                connector.setStyleSheet("""
                    color: #4CAF50;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0px;
                    margin: 0px 4px 24px 4px;
                    background-color: transparent;
                """)
            else:
                # Pending path - gray
                connector.setStyleSheet("""
                    color: #444;
                    font-size: 16px;
                    padding: 0px;
                    margin: 0px 4px 24px 4px;
                    background-color: transparent;
                """)

    def _on_load_or_start(self) -> None:
        """Intelligent load/start with validation and recent records."""
        on_load_or_start(self)

    def _show_record_selector(
        self,
        cavity_display_name: str,
        linac: str,
        cryomodule: str,
        cavity_number: str,
        records: list,
    ) -> None:
        """Show dialog to select existing record or start new."""
        show_record_selector(
            self,
            cavity_display_name,
            linac,
            cryomodule,
            cavity_number,
            records,
        )

    def _load_selected_record(
        self, table: QTableWidget, dialog: QDialog
    ) -> None:
        """Load the selected record from the table."""
        load_selected_record(self, table, dialog)

    def _start_new_from_dialog(
        self,
        cavity_display_name: str,
        linac: str,
        cryomodule: str,
        cavity_number: str,
        dialog: QDialog,
    ) -> None:
        """Start new record from the selection dialog."""
        start_new_from_dialog(
            self,
            cavity_display_name,
            linac,
            cryomodule,
            cavity_number,
            dialog,
        )

    def _confirm_and_start_new(
        self,
        cavity_display_name: str,
        linac: str,
        cryomodule: str,
        cavity_number: str,
    ) -> None:
        """Confirm and start a new commissioning record."""
        confirm_and_start_new(
            self,
            cavity_display_name,
            linac,
            cryomodule,
            cavity_number,
        )

        # =============================================================================
        # TABS - Phase navigation with visual feedback
        # =============================================================================

    def _init_tabs(self) -> None:
        init_tabs(self)

    def _get_phase_icon(self, phase: CommissioningPhase | None) -> str:
        return get_phase_icon(self, phase)

    def _update_tab_states(self) -> None:
        update_tab_states(self)

    def _on_tab_changed(self, index: int) -> None:
        on_tab_changed(self, index)

        # =============================================================================
        # NOTES PANEL - Always accessible note taking
        # =============================================================================

    def _build_enhanced_notes_panel(self) -> QWidget:
        """Build always-accessible notes panel with better UX."""
        return build_enhanced_notes_panel(self)

    def _load_notes(self) -> None:
        """Load and display all notes for the active record."""
        load_notes(self)

    def _quick_add_note(self) -> None:
        quick_add_note(self)

    def _show_notes_context_menu(self, position) -> None:
        show_notes_context_menu(self, position)

    def _on_edit_note(self) -> None:
        on_edit_note(self)

    def _get_selected_note_ref(self):
        return get_selected_note_ref(self)

    def _build_note_dialog(
        self,
        title: str,
        operator_default: str,
        note_default: str = "",
    ) -> tuple[str | None, str | None]:
        return build_note_dialog(
            self,
            title,
            operator_default,
            note_default,
        )

        # =============================================================================
        # SYNC STATUS - External change detection and notification
        # =============================================================================

    def _update_sync_status(self, is_synced: bool, message: str = "") -> None:
        update_sync_status(self, is_synced, message)

    def _check_for_external_changes(self) -> None:
        check_for_external_changes(self)

    def _show_update_banner(self, db_version: int, local_version: int) -> None:
        show_update_banner(self, db_version, local_version)

    def _reload_from_banner(self) -> None:
        reload_from_banner(self)

    def _dismiss_banner(self) -> None:
        dismiss_banner(self)

    def _handle_note_conflict(self, conflict: RecordConflictError) -> None:
        handle_note_conflict(self, conflict)

        # =============================================================================
        # RECORD MANAGEMENT
        # =============================================================================

    def start_new_record(self, cryomodule: str, cavity_number: str) -> bool:
        return start_new_record(self, cryomodule, cavity_number)

    def load_record(self, record_id: int) -> bool:
        return load_record(self, record_id)

    def _update_cm_status_panel(self, record: CommissioningRecord) -> None:
        """Update CM-level header info when record is loaded or changed."""
        if record is None:
            return

        self._refresh_magnet_badge(record.cryomodule, record.linac)
        self._refresh_cavity_completion_label(record.cryomodule)

    def _sync_cavity_selection_from_record(
        self, record: CommissioningRecord
    ) -> None:
        sync_cavity_selection_from_record(self, record)

    def on_phase_advanced(self, record: CommissioningRecord) -> None:
        on_phase_advanced(self, record)

    def save_active_record(self) -> bool:
        return save_active_record(self)

    def _handle_save_conflict(self, conflict: RecordConflictError) -> bool:
        return handle_save_conflict(self, conflict)

    # =============================================================================
    # MEASUREMENT HISTORY
    # =============================================================================

    def _show_measurement_history(self):
        show_measurement_history(self)

    def _show_database_browser(self) -> None:
        show_database_browser(self)


def main() -> int:
    """Run the multi-phase commissioning display standalone via PyDM."""
    app = PyDMApplication(
        ui_file=None, command_line_args=sys.argv, use_main_window=False
    )
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = MultiPhaseCommissioningDisplay()
    window.show()
    return app.exec_()


class Display(MultiPhaseCommissioningDisplay):
    """PyDM compatibility entrypoint class.

    When launching this file directly via `pydm path/to/multi_phase_screen.py`,
    PyDM expects a class named `Display` in the module.
    """


intelclass = MultiPhaseCommissioningDisplay


if __name__ == "__main__":
    sys.exit(main())
