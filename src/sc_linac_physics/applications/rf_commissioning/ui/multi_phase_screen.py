"""Multi-phase commissioning container display."""

import signal
import sys
from dataclasses import dataclass
from typing import Optional, Type

from PyQt5.QtCore import QTimer, Qt, QSettings
from PyQt5.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QMessageBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QLabel,
    QDialogButtonBox,
    QAbstractItemView,
    QWidget,
    QSplitter,
    QLineEdit,
    QSizePolicy,
    QInputDialog,
    QTextEdit,
    QGroupBox,
    QFrame,
    QMenu,
)
from pydm import Display as PyDMDisplay, PyDMApplication

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.database_browser_dialog import (
    DatabaseBrowserDialog,
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
from sc_linac_physics.applications.rf_commissioning.ui.phase_displays import (
    ColdLandingDisplay,
    SSACharDisplay,
    CavityCharDisplay,
    PiezoWithRFDisplay,
    HighPowerDisplay,
    PiezoPreRFDisplay,
)
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


@dataclass(frozen=True)
class PhaseTabSpec:
    """Metadata for a phase tab."""

    title: str
    display_class: Type[PhaseDisplayBase]
    phase: Optional[CommissioningPhase] = None


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
        session: Optional[CommissioningSession] = None,
        phase_specs: Optional[list[PhaseTabSpec]] = None,
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

        # 1. PERSISTENT HEADER (always visible)
        header = self._build_header_panel()
        main_layout.addWidget(header)

        # Banner will be inserted at position 1 when needed

        # 2. COMPACT PROGRESS (always visible)
        progress = self._build_compact_progress_bar()
        main_layout.addWidget(progress)

        # 3. MAIN CONTENT AREA (scrollable)
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
        """Default phase specifications for all commissioning phases."""
        return [
            PhaseTabSpec(
                title="Piezo Pre-RF",
                display_class=PiezoPreRFDisplay,
                phase=CommissioningPhase.PIEZO_PRE_RF,
            ),
            PhaseTabSpec(
                title="Cold Landing",
                display_class=ColdLandingDisplay,
                phase=CommissioningPhase.COLD_LANDING,
            ),
            PhaseTabSpec(
                title="SSA Characterization",
                display_class=SSACharDisplay,
                phase=CommissioningPhase.SSA_CHAR,
            ),
            PhaseTabSpec(
                title="Cavity Characterization",
                display_class=CavityCharDisplay,
                phase=CommissioningPhase.CAVITY_CHAR,
            ),
            PhaseTabSpec(
                title="Piezo with RF",
                display_class=PiezoWithRFDisplay,
                phase=CommissioningPhase.PIEZO_WITH_RF,
            ),
            PhaseTabSpec(
                title="High Power",
                display_class=HighPowerDisplay,
                phase=CommissioningPhase.HIGH_POWER,
            ),
        ]

    # =============================================================================
    # HEADER PANEL - Always visible operator/cavity selection
    # =============================================================================
    def _build_header_panel(self) -> QWidget:
        """Build persistent header with operator and cavity selection."""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-bottom: 2px solid #4a4a4a;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Cavity section - comes FIRST (don't need operator to browse)
        cavity_group = QGroupBox("Cavity Selection")
        cavity_layout = QHBoxLayout()

        self.cryomodule_combo = QComboBox()
        self.cryomodule_combo.setMinimumWidth(80)
        self.cryomodule_combo.addItem("Select CM...", "")
        self.cryomodule_combo.addItems(sorted(ALL_CRYOMODULES))
        cavity_layout.addWidget(QLabel("CM:"))
        cavity_layout.addWidget(self.cryomodule_combo)

        self.cavity_combo = QComboBox()
        self.cavity_combo.setMinimumWidth(60)
        self.cavity_combo.addItem("Select Cav...", "")
        self.cavity_combo.addItems([str(i) for i in range(1, 9)])
        cavity_layout.addWidget(QLabel("Cav:"))
        cavity_layout.addWidget(self.cavity_combo)

        cavity_group.setLayout(cavity_layout)
        layout.addWidget(cavity_group)

        # Update PVs and load record when cavity selection changes
        self.cryomodule_combo.currentIndexChanged.connect(
            self._on_cavity_selection_changed
        )
        self.cavity_combo.currentIndexChanged.connect(
            self._on_cavity_selection_changed
        )

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #555;")
        layout.addWidget(separator)

        # Operator section - needed for running tests
        op_group = QGroupBox("Operator (Required for Tests)")
        op_layout = QHBoxLayout()
        self.operator_combo = QComboBox()
        self.operator_combo.setMinimumWidth(200)
        self.operator_combo.currentIndexChanged.connect(
            self._on_operator_changed
        )
        self._populate_operator_combo()
        op_layout.addWidget(self.operator_combo)
        op_group.setLayout(op_layout)
        layout.addWidget(op_group)

        # Sync status indicator
        self.sync_status = QLabel("○ No Record Loaded")
        self.sync_status.setStyleSheet("""
            QLabel {
                color: #888;
                font-weight: bold;
                padding: 5px 10px;
                background-color: rgba(100, 100, 100, 0.2);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.sync_status)

        layout.addStretch()

        # Quick actions
        history_btn = QPushButton("📊 Measurements")
        history_btn.setToolTip(
            "View all measurement attempts and filter by phase"
        )
        history_btn.clicked.connect(self._show_measurement_history)
        layout.addWidget(history_btn)

        database_btn = QPushButton("🗄️ Database")
        database_btn.setToolTip("Browse and load commissioning records")
        database_btn.clicked.connect(self._show_database_browser)
        layout.addWidget(database_btn)

        header.setLayout(layout)
        return header

    def _on_cavity_selection_changed(self) -> None:
        """Update PV addresses and load record when cavity selection changes."""
        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        # Skip if no valid selection
        if (
            cryomodule == "Select CM..."
            or cavity == "Select Cav..."
            or not cryomodule
            or not cavity
        ):
            return

        # Update PV addresses on the current phase's display controller
        current_index = self.tabs.currentIndex()
        if 0 <= current_index < len(self._phase_displays):
            display = self._phase_displays[current_index]
            if hasattr(display, "controller") and hasattr(
                display.controller, "update_pv_addresses"
            ):
                display.controller.update_pv_addresses(cryomodule, cavity)

            # Load or create record for this cavity
            record, record_id, created = self.session.start_new_record(
                cryomodule, cavity
            )

            # Update UI to reflect the loaded/created record
            if record:
                self.update_progress_indicator(record)
                self._update_tab_states()
                self._load_notes()

                # Update each phase display
                for display in self._phase_displays:
                    display.refresh_from_record(record)

                # Set appropriate tab based on current phase
                for i, spec in enumerate(self.phase_specs):
                    if spec.phase == record.current_phase:
                        self.tabs.setCurrentIndex(i)
                        break

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

        # Define phases with custom labels
        phases = [
            ("Piezo\nPre-RF", CommissioningPhase.PIEZO_PRE_RF),
            ("Cold\nLanding", CommissioningPhase.COLD_LANDING),
            ("SSA\nChar", CommissioningPhase.SSA_CHAR),
            ("Cavity\nChar", CommissioningPhase.CAVITY_CHAR),
            ("Piezo\n@ RF", CommissioningPhase.PIEZO_WITH_RF),
            ("High\nPower", CommissioningPhase.HIGH_POWER),
            ("Complete", CommissioningPhase.COMPLETE),
        ]

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
        phase_order = CommissioningPhase.get_phase_order()
        current_idx = phase_order.index(record.current_phase)

        for phase, indicator in self.phase_indicators.items():
            idx = phase_order.index(phase)
            if idx < current_idx:
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
        operator = self.operator_combo.currentData()
        if not operator:
            QMessageBox.warning(
                self,
                "Operator Required",
                "Please select an operator before loading/starting a record.",
            )
            self.operator_combo.setFocus()
            return

        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        # Validate selections (check if placeholder still selected)
        if cryomodule == "Select CM..." or not cryomodule:
            QMessageBox.warning(
                self, "Cryomodule Required", "Please select a cryomodule."
            )
            self.cryomodule_combo.setFocus()
            return

        if cavity == "Select Cav..." or not cavity:
            QMessageBox.warning(
                self, "Cavity Required", "Please select a cavity number."
            )
            self.cavity_combo.setFocus()
            return

        cavity_number = cavity

        # Check for existing records
        from sc_linac_physics.utils.sc_linac.linac_utils import (
            get_linac_for_cryomodule,
        )

        linac = get_linac_for_cryomodule(cryomodule)
        if not linac:
            QMessageBox.warning(
                self, "Invalid Cryomodule", f"Unknown cryomodule: {cryomodule}"
            )
            return

        existing_records = self.session.db.find_records_for_cavity(
            linac, cryomodule, cavity_number
        )

        cavity_display_name = f"{cryomodule}_CAV{cavity}"

        if existing_records:
            # Show selection dialog
            self._show_record_selector(
                cavity_display_name,
                linac,
                cryomodule,
                cavity_number,
                existing_records,
            )
        else:
            # Start new record
            self._confirm_and_start_new(
                cavity_display_name, linac, cryomodule, cavity_number
            )

    def _show_record_selector(
        self,
        cavity_display_name: str,
        linac: str,
        cryomodule: str,
        cavity_number: str,
        records: list,
    ) -> None:
        """Show dialog to select existing record or start new."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Records for {cavity_display_name}")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout()

        header_label = QLabel(
            f"<b>Found {len(records)} existing record(s) for {cavity_display_name}</b><br>"
            f"<small>Select a record to view or continue working on it</small>"
        )
        header_label.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(header_label)

        # Table of existing records
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["ID", "Started", "Status", "Current Phase", "Last Modified"]
        )
        table.setRowCount(len(records))
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)

        for row, record_data in enumerate(records):
            table.setItem(row, 0, QTableWidgetItem(str(record_data["id"])))
            table.setItem(
                row, 1, QTableWidgetItem(record_data.get("start_time", "")[:16])
            )

            # Status with color
            status = record_data.get("overall_status", "in_progress")
            status_item = QTableWidgetItem(status.replace("_", " ").title())
            if status == "completed":
                status_item.setForeground(Qt.darkGreen)
            elif status == "in_progress":
                status_item.setForeground(Qt.blue)
            table.setItem(row, 2, status_item)

            table.setItem(
                row,
                3,
                QTableWidgetItem(record_data.get("current_phase", "Unknown")),
            )
            table.setItem(
                row,
                4,
                QTableWidgetItem(record_data.get("updated_at", "Unknown")[:16]),
            )

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)

        # Instructions
        info = QLabel(
            "💡 <i>Double-click a record to load it.<br>"
            "You can view records without selecting an operator. "
            "An operator is only required when running tests or making changes.</i>"
        )
        info.setStyleSheet("color: #888; padding: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        button_layout = QHBoxLayout()

        load_btn = QPushButton("📂 Load Selected")
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        load_btn.clicked.connect(
            lambda: self._load_selected_record(table, dialog)
        )
        load_btn.setEnabled(False)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(load_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Enable load button when row selected
        table.itemSelectionChanged.connect(
            lambda: load_btn.setEnabled(len(table.selectedItems()) > 0)
        )

        # Double-click to load
        table.cellDoubleClicked.connect(
            lambda: self._load_selected_record(table, dialog)
        )

        dialog.setLayout(layout)
        dialog.exec_()

    def _load_selected_record(
        self, table: QTableWidget, dialog: QDialog
    ) -> None:
        """Load the selected record from the table."""
        selected_rows = set(item.row() for item in table.selectedItems())
        if not selected_rows:
            return

        row = list(selected_rows)[0]
        record_id = int(table.item(row, 0).text())

        if self.load_record(record_id):
            dialog.accept()
            self._update_sync_status(True, "Record loaded")

            # Save to settings for next launch
            settings = QSettings("SLAC", "RFCommissioning")
            settings.setValue("last_record_id", record_id)
        else:
            QMessageBox.critical(
                dialog, "Load Failed", f"Failed to load record {record_id}"
            )

    def _start_new_from_dialog(
        self,
        cavity_display_name: str,
        linac: str,
        cryomodule: str,
        cavity_number: str,
        dialog: QDialog,
    ) -> None:
        """Start new record from the selection dialog."""
        dialog.accept()
        self._confirm_and_start_new(
            cavity_display_name, linac, cryomodule, cavity_number
        )

    def _confirm_and_start_new(
        self,
        cavity_display_name: str,
        linac: str,
        cryomodule: str,
        cavity_number: str,
    ) -> None:
        """Confirm and start a new commissioning record."""
        reply = QMessageBox.question(
            self,
            "Start New Record",
            f"Start new commissioning record for {cavity_display_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            try:
                created = self.start_new_record(cryomodule, cavity_number)
                if created:
                    self._update_sync_status(True, "New record started")
                else:
                    self._update_sync_status(True, "Record loaded")

                if created:
                    # Log the start
                    operator = self.operator_combo.currentText()
                    try:
                        self.session.append_general_note(
                            operator,
                            f"Started commissioning for {cavity_display_name}",
                        )
                    except RecordConflictError as conflict:
                        self._handle_note_conflict(conflict)

            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to start new record: {e}"
                )

        # =============================================================================
        # TABS - Phase navigation with visual feedback
        # =============================================================================

    def _init_tabs(self) -> None:
        """Initialize tabs with enhanced visual feedback."""
        for i, spec in enumerate(self.phase_specs):
            # Create tab container first
            tab_widget = QWidget()
            tab_layout = QVBoxLayout()
            tab_layout.setContentsMargins(0, 0, 0, 0)

            # Create display with tab_widget as parent
            display = spec.display_class(
                parent=tab_widget, session=self.session
            )
            self._phase_displays.append(display)

            # Add display to layout
            tab_layout.addWidget(display)
            tab_widget.setLayout(tab_layout)

            # Add tab with initial icon
            self.tabs.addTab(
                tab_widget,
                self._get_phase_icon(spec.phase) + " " + spec.title,
            )

        # Connect tab change to auto-save
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _get_phase_icon(self, phase: Optional[CommissioningPhase]) -> str:
        """Get status icon for a phase."""
        if not self.session.has_active_record():
            return "○"

        record = self.session.get_active_record()

        if phase is None:
            return "●"

        phase_order = CommissioningPhase.get_phase_order()
        current_idx = phase_order.index(record.current_phase)
        phase_idx = phase_order.index(phase)

        if phase_idx < current_idx:
            return "✓"  # Completed
        elif phase_idx == current_idx:
            return "▶"  # Current
        else:
            return "○"  # Pending

    def _update_tab_states(self) -> None:
        """Update tab states and icons."""
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
            is_accessible = phase_index <= current_index

            self.tabs.setTabEnabled(i, is_accessible)

            # Update tab text with icon
            icon = self._get_phase_icon(spec.phase)
            self.tabs.setTabText(i, f"{icon} {spec.title}")

            # Style the tab based on status
            if phase_index == current_index:
                self.tabs.tabBar().setTabTextColor(i, Qt.blue)
            elif phase_index < current_index:
                self.tabs.tabBar().setTabTextColor(i, Qt.darkGreen)
            else:
                self.tabs.tabBar().setTabTextColor(i, Qt.gray)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab changes - auto-save current work."""
        if self.session.has_active_record():
            try:
                self.save_active_record()
            except RecordConflictError:
                # Don't block tab change, but notify user
                self._update_sync_status(False, "Unsaved changes")

        # =============================================================================
        # NOTES PANEL - Always accessible note taking
        # =============================================================================

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
        quick_add.clicked.connect(self._quick_add_note)
        header.addWidget(quick_add)

        layout.addLayout(header)

        # Filter row
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

        # Notes table
        self.notes_table = QTableWidget()
        self.notes_table.setColumnCount(4)
        self.notes_table.setHorizontalHeaderLabels(
            ["Time", "Phase", "Operator", "Note"]
        )
        self.notes_table.horizontalHeader().setStretchLastSection(True)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notes_table.setAlternatingRowColors(True)
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Column widths
        self.notes_table.setColumnWidth(0, 130)
        self.notes_table.setColumnWidth(1, 100)
        self.notes_table.setColumnWidth(2, 100)
        self.notes_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        # Enable right-click context menu
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

        # Handle "current phase" filter
        if phase_filter == "current":
            record = self.session.get_active_record()
            phase_filter = record.current_phase

        # Get both general notes and measurement notes
        measurement_notes = self.session.get_measurement_notes(phase_filter)
        general_notes = self.session.get_general_notes()

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

        # Sort by timestamp (most recent first)
        all_notes.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        self.notes_table.setRowCount(len(all_notes))

        for row, item in enumerate(all_notes):
            # Time column
            time_str = item["timestamp"] or item["measurement_timestamp"] or "-"
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, item["note_ref"])
            self.notes_table.setItem(row, 0, time_item)

            # Phase column
            phase_str = item["phase"] or "General"
            phase_item = QTableWidgetItem(phase_str)
            self.notes_table.setItem(row, 1, phase_item)

            # Operator column
            operator_item = QTableWidgetItem(item["operator"] or "Unknown")
            self.notes_table.setItem(row, 2, operator_item)

            # Note column
            note_item = QTableWidgetItem(item["note"] or "")
            self.notes_table.setItem(row, 3, note_item)

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

        # Simple text input
        note, ok = QInputDialog.getMultiLineText(
            self,
            "Quick Note",
            f"Operator: {self.operator_combo.currentText()}\n\nEnter note:",
        )

        if ok and note.strip():
            try:
                if self.session.append_general_note(operator, note.strip()):
                    self._load_notes()
                    # Auto-scroll to top to see new note
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
    ) -> tuple[Optional[str], Optional[str]]:
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

        # =============================================================================
        # SYNC STATUS - External change detection and notification
        # =============================================================================

    def _update_sync_status(self, is_synced: bool, message: str = "") -> None:
        """Update the global sync status indicator."""
        if is_synced:
            self.sync_status.setText("● Synced")
            self.sync_status.setStyleSheet("""
                        QLabel {
                            color: #4CAF50;
                            font-weight: bold;
                            padding: 5px 10px;
                            background-color: rgba(76, 175, 80, 0.15);
                            border-radius: 3px;
                        }
                    """)
        else:
            self.sync_status.setText(f"⚠ {message or 'Out of Sync'}")
            self.sync_status.setStyleSheet("""
                        QLabel {
                            color: #FF9800;
                            font-weight: bold;
                            padding: 5px 10px;
                            background-color: rgba(255, 152, 0, 0.15);
                            border-radius: 3px;
                            border: 1px solid #FF9800;
                        }
                    """)

    def _check_for_external_changes(self) -> None:
        """Enhanced change detection with visible notification."""
        if not self.session.has_active_record():
            return

        record_id = self.session.get_active_record_id()
        if not record_id:
            return

        try:
            result = self.session.db.get_record_with_version(record_id)
            if not result:
                return

            db_record, db_version = result
            local_version = self.session._active_record_version

            if local_version is not None and db_version > local_version:
                # Show prominent notification banner
                self._show_update_banner(db_version, local_version)

        except Exception as e:
            print(f"Error checking for external changes: {e}")

    def _show_update_banner(self, db_version: int, local_version: int) -> None:
        """Show a prominent banner when external updates are detected."""
        if hasattr(self, "_update_banner") and self._update_banner:
            return  # Banner already showing

        self._update_banner = QWidget()
        self._update_banner.setStyleSheet("""
                    QWidget {
                        background-color: #FF9800;
                        border: 2px solid #F57C00;
                        border-left: 5px solid #F57C00;
                    }
                    QLabel {
                        color: white;
                        font-weight: bold;
                        padding: 5px;
                    }
                    QPushButton {
                        background-color: white;
                        color: #F57C00;
                        font-weight: bold;
                        padding: 8px 16px;
                        border-radius: 4px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #f5f5f5;
                    }
                """)

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)

        icon = QLabel("⚠️")
        icon.setStyleSheet("font-size: 24px;")
        layout.addWidget(icon)

        message = QLabel(
            f"<b>This record was updated by another user</b><br>"
            f"<small>Your version: {local_version} → Database version: {db_version}</small>"
        )
        layout.addWidget(message)
        layout.addStretch()

        reload_btn = QPushButton("🔄 Reload Now")
        reload_btn.clicked.connect(self._reload_from_banner)
        layout.addWidget(reload_btn)

        dismiss_btn = QPushButton("✕ Dismiss")
        dismiss_btn.clicked.connect(self._dismiss_banner)
        layout.addWidget(dismiss_btn)

        self._update_banner.setLayout(layout)

        # Insert banner at position 1 (after header, before progress)
        self.layout().insertWidget(1, self._update_banner)

        # Update sync status
        self._update_sync_status(False, "Out of Sync")

    def _reload_from_banner(self) -> None:
        """Reload record from update banner."""
        record_id = self.session.get_active_record_id()
        if record_id:
            # Warn about unsaved changes
            reply = QMessageBox.question(
                self,
                "Reload Record",
                "Reloading will discard any unsaved changes. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                self.load_record(record_id)
                self._dismiss_banner()
                self._update_sync_status(True, "Reloaded")

    def _dismiss_banner(self) -> None:
        """Remove the update notification banner."""
        if hasattr(self, "_update_banner") and self._update_banner:
            self._update_banner.deleteLater()
            self._update_banner = None

    def _handle_note_conflict(self, conflict: RecordConflictError) -> None:
        """Handle note update conflicts from optimistic locking."""
        QMessageBox.warning(
            self,
            "Record Updated",
            "This record was updated by another user. "
            "Please reload before editing notes.",
        )
        self._show_update_banner(
            conflict.actual_version, conflict.expected_version
        )

        # =============================================================================
        # RECORD MANAGEMENT
        # =============================================================================

    def start_new_record(self, cryomodule: str, cavity_number: str) -> bool:
        """Start a new commissioning record.

        Returns:
            True if a new record was created, False if an existing record was loaded.
        """
        record, record_id, created = self.session.start_new_record(
            cryomodule, cavity_number
        )

        # Update UI
        self.update_progress_indicator(record)
        self._update_tab_states()
        self._load_notes()

        for display in self._phase_displays:
            display.refresh_from_record(record)

        # Set appropriate tab
        if created:
            self.tabs.setCurrentIndex(0)
        else:
            # Load existing - go to current phase
            for i, spec in enumerate(self.phase_specs):
                if spec.phase == record.current_phase:
                    self.tabs.setCurrentIndex(i)
                    break

        return created

    def load_record(self, record_id: int) -> bool:
        """Load an existing commissioning record."""
        record = self.session.load_record(record_id)
        if not record:
            return False

        self._sync_cavity_selection_from_record(record)

        self.update_progress_indicator(record)

        for display in self._phase_displays:
            display.on_record_loaded(record, record_id)

        self._update_tab_states()

        # Switch to current phase tab
        for i, spec in enumerate(self.phase_specs):
            if spec.phase == record.current_phase:
                self.tabs.setCurrentIndex(i)
                break

        self._load_notes()
        self._update_sync_status(True, "Record loaded")

        return True

    def _sync_cavity_selection_from_record(
        self, record: CommissioningRecord
    ) -> None:
        """Sync header cavity selection to a loaded record."""
        cm_index = self.cryomodule_combo.findText(record.cryomodule)
        if cm_index >= 0:
            self.cryomodule_combo.setCurrentIndex(cm_index)

        cav_index = self.cavity_combo.findText(str(record.cavity_number))
        if cav_index >= 0:
            self.cavity_combo.setCurrentIndex(cav_index)

    def on_phase_advanced(self, record: CommissioningRecord) -> None:
        """Handle notification that a phase has advanced.

        Called by child phase displays when their phase completes.
        """
        print(f"DEBUG: Phase advanced to {record.current_phase}")

        # Update all UI elements
        self.update_progress_indicator(record)
        self._update_tab_states()
        self._update_sync_status(True, "Phase completed")

        # Optionally switch to the next phase tab
        for i, spec in enumerate(self.phase_specs):
            if spec.phase == record.current_phase:
                self.tabs.setCurrentIndex(i)
                break

    def save_active_record(self) -> bool:
        """Save the active record with conflict detection.

        Returns:
            True if saved successfully or user chose to continue, False otherwise
        """
        if not self.session.has_active_record():
            return False

        # Get the old phase before saving
        old_phase = self.session.get_active_record().current_phase

        try:
            success = self.session.save_active_record()
            if success:
                self._update_sync_status(True, "Saved")

                # Check if phase changed and update UI
                new_record = self.session.get_active_record()
                if new_record and new_record.current_phase != old_phase:
                    self.update_progress_indicator(new_record)
                    self._update_tab_states()

            return success
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
            self._update_sync_status(False, "Merge cancelled")
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
            self._update_sync_status(True, "Merged and saved")
            return True

        except Exception as e:
            QMessageBox.critical(
                self, "Save Failed", f"Failed to save merged record: {e}"
            )
            self._update_sync_status(False, "Save failed")
            return False

    # =============================================================================
    # MEASUREMENT HISTORY
    # =============================================================================

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

    def _show_database_browser(self) -> None:
        """Open database browser to select and load a record."""
        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        if cryomodule == "Select CM..." or not cryomodule:
            cryomodule = None

        if cavity == "Select Cav..." or not cavity:
            cavity = None

        linac = None
        if cryomodule:
            from sc_linac_physics.utils.sc_linac.linac_utils import (
                get_linac_for_cryomodule,
            )

            linac = get_linac_for_cryomodule(cryomodule)

        dialog = DatabaseBrowserDialog(
            self.session.database,
            self,
            cryomodule_filter=cryomodule,
            cavity_filter=cavity,
            linac_filter=linac,
        )

        if dialog.exec_() != QDialog.Accepted:
            return

        record_id, record_data = dialog.get_selected_record()

        if not record_id or not record_data:
            return

        if not self.load_record(record_id):
            QMessageBox.critical(
                self, "Load Failed", f"Failed to load record {record_id}"
            )


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
