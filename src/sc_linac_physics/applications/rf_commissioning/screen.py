"""
Piezo Pre-RF Test Display for LCLS-II SC Linac
PyDM-compatible display for running piezo pre-RF tests with live PV readouts
"""

from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QTextEdit,
    QProgressBar,
    QCheckBox,
    QMessageBox,
    QGridLayout,
    QFrame,
)
from pydm import Display
from pydm.widgets import PyDMLabel

from sc_linac_physics.applications.rf_commissioning import CommissioningPiezo
from sc_linac_physics.applications.rf_commissioning.data_models import (
    CommissioningRecord,
    CommissioningPhase,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.database import (
    CommissioningDatabase,
)
from sc_linac_physics.applications.rf_commissioning.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.piezo_pre_rf import (
    PiezoTestLimits,
    PiezoPreRFPhase,
)
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
)


class PiezoPreRFDisplay(Display):
    """PyDM Display for Piezo Pre-RF Testing with live PV readouts and database persistence."""

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)

        self.phase = None
        self.context = None
        self.current_cavity = None
        self.pv_widgets = {}
        self.current_record_id = None

        # Initialize database
        self.db = CommissioningDatabase("piezo_prerf_commissioning.db")
        self.db.initialize()

        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Piezo Pre-RF Test")
        self.setMinimumSize(1200, 850)

        # Initialize history_text early so log_message works
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setMaximumHeight(150)

        # Main layout
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # Left column - Test control and results
        left_column = QVBoxLayout()
        left_column.addWidget(self._create_selection_group())
        left_column.addWidget(self._create_control_group())
        left_column.addWidget(self._create_status_group())
        left_column.addWidget(self._create_results_group())
        left_column.addWidget(self._create_history_group())

        # Right column - Live PV readouts
        right_column = QVBoxLayout()
        right_column.addWidget(self._create_pv_readouts_group())

        main_layout.addLayout(left_column, stretch=2)
        main_layout.addLayout(right_column, stretch=1)

    def _create_selection_group(self):
        """Create cavity selection group."""
        group = QGroupBox("Cavity Selection")
        layout = QVBoxLayout()

        # Cavity selector row
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Cryomodule:"))
        self.cm_combo = QComboBox()
        # Simply convert all to strings
        self.cm_combo.addItems([str(cm) for cm in ALL_CRYOMODULES])
        select_layout.addWidget(self.cm_combo)

        select_layout.addWidget(QLabel("Cavity:"))
        self.cavity_combo = QComboBox()
        select_layout.addWidget(self.cavity_combo)

        select_layout.addStretch()
        layout.addLayout(select_layout)

        # Resume session indicator
        self.resume_label = QLabel("")
        self.resume_label.setStyleSheet("color: #0066cc; font-style: italic;")
        layout.addWidget(self.resume_label)

        group.setLayout(layout)

        # Initialize cavity list FIRST
        self.on_cm_changed(self.cm_combo.currentText())

        # THEN connect signals
        self.cm_combo.currentTextChanged.connect(self.on_cm_changed)
        self.cavity_combo.currentTextChanged.connect(self.on_cavity_changed)

        # Now update PVs for initial selection
        if self.cavity_combo.count() > 0:
            self.on_cavity_changed()

        return group

    def _create_control_group(self):
        """Create control buttons group."""
        group = QGroupBox("Test Control")
        layout = QHBoxLayout()

        self.run_button = QPushButton("Run Pre-RF Test")
        self.run_button.clicked.connect(self.on_run_test)
        self.run_button.setStyleSheet(
            "QPushButton { font-weight: bold; padding: 8px; }"
        )
        layout.addWidget(self.run_button)

        self.abort_button = QPushButton("Abort")
        self.abort_button.clicked.connect(self.on_abort)
        self.abort_button.setEnabled(False)
        self.abort_button.setStyleSheet(
            "QPushButton { background-color: #ffcccc; padding: 8px; }"
        )
        layout.addWidget(self.abort_button)

        self.dry_run_checkbox = QCheckBox("Dry Run (No Hardware)")
        layout.addWidget(self.dry_run_checkbox)

        layout.addStretch()

        self.save_button = QPushButton("Save Report")
        self.save_button.clicked.connect(self.on_save_report)
        self.save_button.setEnabled(False)
        layout.addWidget(self.save_button)

        self.view_db_button = QPushButton("View Database")
        self.view_db_button.clicked.connect(self.on_view_database)
        layout.addWidget(self.view_db_button)

        group.setLayout(layout)
        return group

    def _create_status_group(self):
        """Create test status group."""
        group = QGroupBox("Test Status")
        layout = QVBoxLayout()

        # Progress bar
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # Current step
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Current Step:"))
        self.current_step_label = QLabel("-")
        self.current_step_label.setStyleSheet("font-weight: bold;")
        step_layout.addWidget(self.current_step_label)
        step_layout.addStretch()
        layout.addLayout(step_layout)

        # Phase status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Phase Status:"))
        self.phase_status_label = QLabel("-")
        self.phase_status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.phase_status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        group.setLayout(layout)
        return group

    def _create_results_group(self):
        """Create test results group."""
        group = QGroupBox("Test Results")
        layout = QVBoxLayout()

        # Channel A
        cha_layout = QHBoxLayout()
        cha_layout.addWidget(QLabel("Channel A:"))
        self.cha_status_label = QLabel("-")
        self.cha_status_label.setStyleSheet("font-weight: bold;")
        cha_layout.addWidget(self.cha_status_label)
        cha_layout.addWidget(QLabel("Capacitance:"))
        self.cha_cap_label = QLabel("-")
        cha_layout.addWidget(self.cha_cap_label)
        cha_layout.addStretch()
        layout.addLayout(cha_layout)

        # Channel B
        chb_layout = QHBoxLayout()
        chb_layout.addWidget(QLabel("Channel B:"))
        self.chb_status_label = QLabel("-")
        self.chb_status_label.setStyleSheet("font-weight: bold;")
        chb_layout.addWidget(self.chb_status_label)
        chb_layout.addWidget(QLabel("Capacitance:"))
        self.chb_cap_label = QLabel("-")
        chb_layout.addWidget(self.chb_cap_label)
        chb_layout.addStretch()
        layout.addLayout(chb_layout)

        # Overall result
        overall_layout = QHBoxLayout()
        overall_layout.addWidget(QLabel("Overall Result:"))
        self.overall_result_label = QLabel("-")
        self.overall_result_label.setStyleSheet(
            "font-weight: bold; font-size: 14pt;"
        )
        overall_layout.addWidget(self.overall_result_label)
        overall_layout.addStretch()
        layout.addLayout(overall_layout)

        group.setLayout(layout)
        return group

    def _create_history_group(self):
        """Create phase history log group."""
        group = QGroupBox("Phase History")
        layout = QVBoxLayout()

        # Use the pre-created history_text widget
        layout.addWidget(self.history_text)

        group.setLayout(layout)
        return group

    def _create_pv_readouts_group(self):
        """Create live PV readouts group."""
        group = QGroupBox("Live PV Readouts")
        layout = QVBoxLayout()

        # Piezo Test Status
        test_group = self._create_pv_section(
            "Pre-RF Test Status",
            [
                ("Overall Status:", "TEST_STATUS"),
                ("Channel A:", "CHA_STATUS"),
                ("Channel B:", "CHB_STATUS"),
            ],
        )
        layout.addWidget(test_group)

        # Test Messages
        msg_group = self._create_pv_section(
            "Test Messages",
            [
                ("Ch A:", "CHA_MSG"),
                ("Ch B:", "CHB_MSG"),
            ],
        )
        layout.addWidget(msg_group)

        # Piezo Capacitance
        cap_group = self._create_pv_section(
            "Capacitance (nF)",
            [
                ("Channel A:", "CAP_A"),
                ("Channel B:", "CAP_B"),
            ],
        )
        layout.addWidget(cap_group)

        # Piezo Control Status
        ctrl_group = self._create_pv_section(
            "Piezo Control",
            [
                ("Enabled:", "ENABLE"),
                ("Mode:", "FEEDBACK_MODE"),
                ("Bias (V):", "BIAS_VOLTAGE"),
                ("Voltage (V):", "VOLTAGE"),
            ],
        )
        layout.addWidget(ctrl_group)

        # SSA Status
        ssa_group = self._create_pv_section(
            "SSA Status",
            [
                ("Status:", "SSA_STATUS"),
                ("Cal Status:", "SSA_CAL_STATUS"),
                ("Drive Max:", "SSA_DRIVE_MAX"),
                ("Max Fwd Pwr:", "SSA_MAX_FWD_PWR"),
            ],
        )
        layout.addWidget(ssa_group)

        layout.addStretch()

        group.setLayout(layout)
        return group

    def _create_pv_section(self, title, pv_list):
        """Create a section of PV readouts.

        Args:
            title: Section title
            pv_list: List of (label, pv_suffix) tuples
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        layout = QVBoxLayout()

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-weight: bold; background-color: #e0e0e0; padding: 4px;"
        )
        layout.addWidget(title_label)

        # Grid of PVs
        grid = QGridLayout()

        for row, (label_text, pv_suffix) in enumerate(pv_list):
            # Label
            label = QLabel(label_text)
            grid.addWidget(label, row, 0)

            # PV readout widget
            pv_label = PyDMLabel()
            pv_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            pv_label.showUnits = False
            pv_label.precisionFromPV = True
            pv_label.alarmSensitiveContent = True
            pv_label.alarmSensitiveBorder = False
            pv_label.setMinimumWidth(150)

            # Store widget for later PV address updates
            self.pv_widgets[pv_suffix] = pv_label

            grid.addWidget(pv_label, row, 1)

        layout.addLayout(grid)
        frame.setLayout(layout)

        return frame

    def on_cm_changed(self, cm_name):
        """Handle cryomodule selection change."""
        self.cavity_combo.clear()

        cavities = [f"{i}" for i in range(1, 9)]
        self.cavity_combo.addItems(cavities)

    def on_cavity_changed(self):
        """Handle cavity selection change - update PV addresses and check for resume."""
        cm_name = self.cm_combo.currentText()

        if not self.cavity_combo.currentText():
            return  # No cavity selected yet

        cav_num = int(self.cavity_combo.currentText())

        try:
            machine = Machine(piezo_class=CommissioningPiezo)
            cavity = machine.cryomodules[cm_name].cavities[cav_num]
            self.current_cavity = cavity

            # Update PV addresses
            self._update_pv_addresses(cavity)

            # Check for existing active record
            cavity_name = f"{cm_name}:Cav{cav_num}"
            existing_record = self.db.get_record_by_cavity(
                cavity_name, active_only=True
            )

            if existing_record:
                self.resume_label.setText(
                    f"⚠ Active session found - Started {existing_record.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.log_message(f"Found existing session for {cavity_name}")
            else:
                self.resume_label.setText("")

        except Exception as e:
            self.log_message(f"Error: {e}")

    def _update_pv_addresses(self, cavity):
        """Update PV addresses for all readout widgets."""

        try:
            # Build PV mapping using CommissioningPiezo and base Piezo/SSA attributes
            pv_mapping = {
                # Pre-RF Test PVs (from CommissioningPiezo)
                "TEST_STATUS": cavity.piezo.prerf_test_status_pv,
                "CHA_STATUS": cavity.piezo.prerf_cha_status_pv,
                "CHB_STATUS": cavity.piezo.prerf_chb_status_pv,
                "CHA_MSG": cavity.piezo.prerf_cha_testmsg_pv,
                "CHB_MSG": cavity.piezo.prerf_chb_testmsg_pv,
                # Capacitance (from CommissioningPiezo)
                "CAP_A": cavity.piezo.capacitance_a_pv,
                "CAP_B": cavity.piezo.capacitance_b_pv,
                # Control PVs (from base Piezo class)
                "BIAS_VOLTAGE": cavity.piezo.bias_voltage_pv,
                "VOLTAGE": cavity.piezo.voltage_pv,
                "ENABLE": cavity.piezo.enable_stat_pv,
                "FEEDBACK_MODE": cavity.piezo.feedback_stat_pv,
                # SSA PVs (from SSA class)
                "SSA_STATUS": cavity.ssa.status_pv,
                "SSA_CAL_STATUS": cavity.ssa.calibration_status_pv,
                "SSA_DRIVE_MAX": cavity.ssa.saved_drive_max_pv,
                "SSA_MAX_FWD_PWR": cavity.ssa.max_fwd_pwr_pv,
            }

            # Update each widget's channel
            for suffix, pv_widget in self.pv_widgets.items():
                if suffix in pv_mapping:
                    pv_address = pv_mapping[suffix]
                    if pv_address:
                        channel_address = f"ca://{pv_address}"
                        pv_widget.channel = channel_address
                    else:
                        pv_widget.channel = None
                        pv_widget.setText("-")
                else:
                    # PV not available for this suffix
                    pv_widget.channel = None
                    pv_widget.setText("N/A")

        except Exception as e:
            self.log_message(f"Error setting up PVs: {e}")

    @pyqtSlot()
    def on_run_test(self):
        """Handle run test button click."""
        if not self.current_cavity:
            self.show_error("Please select a cavity first")
            return

        cm_name = self.cm_combo.currentText()
        cav_num = int(self.cavity_combo.currentText())
        cavity_name = f"{cm_name}:Cav{cav_num}"

        # Check for existing active record
        existing_record = self.db.get_record_by_cavity(
            cavity_name, active_only=True
        )

        if existing_record:
            reply = QMessageBox.question(
                self,
                "Resume Session?",
                f"An active session was found for {cavity_name}\n"
                f"Started: {existing_record.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Current Phase: {existing_record.current_phase.value}\n\n"
                f"Resume this session or start a new one?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Cancel:
                return
            elif reply == QMessageBox.Yes:
                # Resume existing session
                record = existing_record
                self.log_message(f"Resuming session from {record.start_time}")
            else:
                # Start new session - mark old one as complete
                existing_record.overall_status = "superseded"
                existing_record.end_time = datetime.now()
                self.db.save_record(existing_record)
                record = None
        else:
            record = None

        # Create new record if not resuming
        if record is None:
            record = CommissioningRecord(
                cavity_name=cavity_name,
                cryomodule=cm_name,
                start_time=datetime.now(),
                current_phase=CommissioningPhase.PIEZO_PRE_RF,
            )
            # Save to database
            self.current_record_id = self.db.save_record(record)
            self.log_message(
                f"Created new commissioning record (ID: {self.current_record_id})"
            )
        else:
            self.current_record_id = self.db.get_record_by_cavity(
                cavity_name, active_only=True
            )

        self.log_message(f"Starting Piezo Pre-RF test for {cavity_name}...")

        # Clear previous results
        self.clear_results()

        # Disable controls
        self.run_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.save_button.setEnabled(False)

        # Create commissioning context
        try:
            self.context = PhaseContext(
                record=record,
                dry_run=self.dry_run_checkbox.isChecked(),
                parameters={"cavity": self.current_cavity},
            )

            # Create and validate phase
            limits = PiezoTestLimits()
            self.phase = PiezoPreRFPhase(self.context, limits)

            # Validate prerequisites
            valid, msg = self.phase.validate_prerequisites()
            if not valid:
                self.show_error(f"Prerequisites not met: {msg}")
                self.run_button.setEnabled(True)
                self.abort_button.setEnabled(False)
                return

            self.log_message("Prerequisites validated")
            self.phase_status_label.setText("RUNNING")
            self.set_status_color(self.phase_status_label, "orange")

            # Execute phase steps
            self._execute_phase_steps()

        except Exception as e:
            self.show_error(f"Failed to start test: {e}")
            self.run_button.setEnabled(True)
            self.abort_button.setEnabled(False)

    def _execute_phase_steps(self):
        """Execute all phase steps sequentially."""
        from PyQt5.QtCore import QTimer

        steps = self.phase.get_phase_steps()
        total_steps = len(steps)
        current_step_index = 0

        def execute_next_step():
            nonlocal current_step_index

            # Check if aborted
            if self.context.is_abort_requested():
                self.on_phase_failed("Test aborted by user")
                return

            # Check if all steps complete
            if current_step_index >= total_steps:
                self.on_phase_completed()
                return

            # Execute current step
            step_name = steps[current_step_index]
            self.current_step_label.setText(step_name)
            progress = int((current_step_index / total_steps) * 100)
            self.progress_bar.setValue(progress)

            self.log_message(f"Executing step: {step_name}")

            try:
                result = self.phase.execute_step(step_name)

                # Log step result
                status = (
                    "SUCCESS"
                    if result.result == PhaseResult.SUCCESS
                    else "FAILED"
                )
                self.log_message(f"  {status}: {result.message}")

                if result.data:
                    for key, value in result.data.items():
                        self.log_message(f"    {key}: {value}")

                # Save progress to database after each step
                if self.current_record_id:
                    self.db.save_record(
                        self.context.record, self.current_record_id
                    )

                # Check if step failed
                if result.result == PhaseResult.FAILED:
                    self.on_phase_failed(result.message)
                    return

                # Move to next step
                current_step_index += 1

                # Schedule next step
                QTimer.singleShot(100, execute_next_step)

            except Exception as e:
                self.on_phase_failed(f"Step failed: {e}")
                return

        # Start executing steps
        QTimer.singleShot(100, execute_next_step)

    def on_phase_completed(self):
        """Handle phase completion."""
        self.log_message("Phase completed successfully")
        self.phase_status_label.setText("COMPLETED")
        self.set_status_color(self.phase_status_label, "green")
        self.progress_bar.setValue(100)

        # Finalize phase to save results
        try:
            self.phase.finalize_phase()

            # Update record status
            self.context.record.overall_status = "complete"
            self.context.record.end_time = datetime.now()
            self.context.record.set_phase_status(
                CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.COMPLETE
            )

            # Save to database
            if self.current_record_id:
                self.db.save_record(self.context.record, self.current_record_id)
                self.log_message(
                    f"Results saved to database (ID: {self.current_record_id})"
                )

            # Update results display
            if self.context.record.piezo_pre_rf:
                self.update_results(self.context.record.piezo_pre_rf)

        except Exception as e:
            self.log_message(f"Warning: Failed to finalize results: {e}")

        # Re-enable controls
        self.run_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.save_button.setEnabled(True)

    def on_phase_failed(self, error_msg):
        """Handle phase failure."""
        self.log_message(f"Phase failed: {error_msg}")
        self.phase_status_label.setText("FAILED")
        self.set_status_color(self.phase_status_label, "red")

        # Update record status
        if self.context:
            self.context.record.overall_status = "failed"
            self.context.record.end_time = datetime.now()
            self.context.record.set_phase_status(
                CommissioningPhase.PIEZO_PRE_RF, PhaseStatus.FAILED
            )

        # Try to save partial results
        try:
            if self.phase:
                self.phase.finalize_phase()

            # Save to database
            if self.current_record_id and self.context:
                self.db.save_record(self.context.record, self.current_record_id)
                self.log_message("Partial results saved to database")

            if self.context and self.context.record.piezo_pre_rf:
                self.update_results(self.context.record.piezo_pre_rf)
        except Exception as e:
            self.log_message(f"Warning: Failed to save partial results: {e}")

        # Re-enable controls
        self.run_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.save_button.setEnabled(True)

        self.show_error(f"Test failed: {error_msg}")

    def update_results(self, result):
        """Update result displays from PiezoPreRFCheck."""
        # Channel A
        if result.channel_a_passed:
            self.cha_status_label.setText("PASS")
            self.set_status_color(self.cha_status_label, "green")
        else:
            self.cha_status_label.setText("FAIL")
            self.set_status_color(self.cha_status_label, "red")

        if result.capacitance_a:
            self.cha_cap_label.setText(f"{result.capacitance_a * 1e9:.1f} nF")

        # Channel B
        if result.channel_b_passed:
            self.chb_status_label.setText("PASS")
            self.set_status_color(self.chb_status_label, "green")
        else:
            self.chb_status_label.setText("FAIL")
            self.set_status_color(self.chb_status_label, "red")

        if result.capacitance_b:
            self.chb_cap_label.setText(f"{result.capacitance_b * 1e9:.1f} nF")

        # Overall
        if result.passed:
            self.overall_result_label.setText("PASS")
            self.set_status_color(self.overall_result_label, "green")
        else:
            self.overall_result_label.setText("FAIL")
            self.set_status_color(self.overall_result_label, "red")

    def clear_results(self):
        """Clear all result displays."""
        self.cha_status_label.setText("-")
        self.chb_status_label.setText("-")
        self.cha_cap_label.setText("-")
        self.chb_cap_label.setText("-")
        self.overall_result_label.setText("-")

        # Reset colors
        self.reset_label_color(self.cha_status_label)
        self.reset_label_color(self.chb_status_label)
        self.reset_label_color(self.overall_result_label)

        self.history_text.clear()
        self.progress_bar.setValue(0)
        self.current_step_label.setText("-")

    def set_status_color(self, label, color_name):
        """Set label text color."""
        palette = label.palette()

        if color_name == "green":
            color = QColor(0, 150, 0)
        elif color_name == "red":
            color = QColor(200, 0, 0)
        elif color_name == "orange":
            color = QColor(255, 140, 0)
        else:
            color = QColor(0, 0, 0)

        palette.setColor(QPalette.WindowText, color)
        label.setPalette(palette)

    def reset_label_color(self, label):
        """Reset label to default color."""
        palette = label.palette()
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        label.setPalette(palette)

    def log_message(self, message):
        """Add a message to the history log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history_text.append(f"[{timestamp}] {message}")

    def on_abort(self):
        """Handle abort button click."""
        if self.context:
            self.context.request_abort()
            self.log_message("Abort requested...")
            self.abort_button.setEnabled(False)

    def on_save_report(self):
        """Display saved results from database."""
        if not self.context or not self.context.record:
            QMessageBox.information(
                self, "No Results", "No test results available to display."
            )
            return

        # Show database record info
        msg = "Test results saved to database\n\n"
        msg += f"Record ID: {self.current_record_id}\n"
        msg += f"Cavity: {self.context.record.cavity_name}\n"
        msg += f"Status: {self.context.record.overall_status}\n"

        if self.context.record.piezo_pre_rf:
            result = self.context.record.piezo_pre_rf
            msg += "\nResults:\n"
            msg += (
                f"  Channel A: {'PASS' if result.channel_a_passed else 'FAIL'}"
            )
            if result.capacitance_a:
                msg += f" ({result.capacitance_a * 1e9:.1f} nF)\n"
            else:
                msg += "\n"
            msg += (
                f"  Channel B: {'PASS' if result.channel_b_passed else 'FAIL'}"
            )
            if result.capacitance_b:
                msg += f" ({result.capacitance_b * 1e9:.1f} nF)\n"
            else:
                msg += "\n"

        QMessageBox.information(self, "Test Results", msg)

    def on_view_database(self):
        """Show database statistics and records."""
        stats = self.db.get_database_stats()

        msg = "COMMISSIONING DATABASE STATISTICS\n"
        msg += "=" * 50 + "\n\n"

        msg += f"Total Records: {stats['total_records']}\n\n"

        msg += "By Status:\n"
        for status, count in stats["by_status"].items():
            msg += f"  {status}: {count}\n"

        msg += "\nBy Phase:\n"
        for phase, count in stats["by_phase"].items():
            msg += f"  {phase}: {count}\n"

        msg += "\nBy Cryomodule:\n"
        for cm, count in stats["by_cryomodule"].items():
            msg += f"  CM{cm}: {count}\n"

        # Show active records
        active_records = self.db.get_active_records()
        if active_records:
            msg += "\n" + "=" * 50 + "\n"
            msg += "ACTIVE SESSIONS:\n"
            msg += "=" * 50 + "\n"
            for record in active_records:
                msg += f"\n{record.cavity_name}\n"
                msg += f"  Started: {record.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                msg += f"  Phase: {record.current_phase.value}\n"

                if record.piezo_pre_rf:
                    result = record.piezo_pre_rf
                    msg += f"  Result: {'PASS' if result.passed else 'FAIL'}\n"

        QMessageBox.information(self, "Database Statistics", msg)

    def show_error(self, message):
        """Show error message dialog."""
        QMessageBox.critical(self, "Error", message)


def main():
    """Main entry point for running the display standalone."""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PiezoPreRFDisplay()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
