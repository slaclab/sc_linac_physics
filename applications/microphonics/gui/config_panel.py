from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QCheckBox, QSpinBox,
    QPushButton, QGridLayout, QScrollArea, QTabWidget, QMessageBox
)


class ConfigPanel(QWidget):
    """Config panel for Microphonics GUI.

    This providess the controls for:
    - Linac and CM selection
    - Cavity selection (Rack A/B)
    - Acquisition settings
    - Measurement control
    """
    # Signals
    configChanged = pyqtSignal(dict)  # Emitted when any configuration changes
    measurementStarted = pyqtSignal()  # Emitted when start button clicked
    measurementStopped = pyqtSignal()  # Emitted when stop button clicked

    # Constants
    VALID_LINACS = {
        "L0B": ["01"],
        "L1B": ["02", "03", "H1", "H2"],
        "L2B": [f"{i:02d}" for i in range(4, 16)],
        "L3B": [f"{i:02d}" for i in range(16, 36)]
    }
    VALID_DECIMATION = {1, 2, 4, 8}
    DEFAULT_BUFFER_COUNT = 65

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_linac = None
        self.selected_modules = set()
        self.is_updating = False  # I added this flag to prevent recursive updates (check)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # This creates a scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)

        # Adding config sections
        content_layout.addWidget(self.create_linac_section())
        content_layout.addWidget(self.create_cavity_section())
        content_layout.addWidget(self.create_settings_section())
        content_layout.addWidget(self.create_control_section())
        content_layout.addStretch()

        layout.addWidget(scroll)

    def create_linac_section(self) -> QGroupBox:
        """Create linac and CM selection group"""
        group = QGroupBox("Linac Configuration")
        layout = QVBoxLayout()

        # Linac selection buttons
        linac_layout = QHBoxLayout()
        self.linac_buttons = {}
        for linac in self.VALID_LINACS:
            btn = QPushButton(linac)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, l=linac: self._on_linac_selected(l))
            self.linac_buttons[linac] = btn
            linac_layout.addWidget(btn)
        layout.addLayout(linac_layout)

        # CM selection grid
        self.cryo_group = QGroupBox("Cryomodule Selection")
        self.cryo_layout = QGridLayout()
        self.cryo_buttons = {}
        self.cryo_group.setLayout(self.cryo_layout)
        layout.addWidget(self.cryo_group)

        group.setLayout(layout)
        return group

    def create_cavity_section(self):
        """Create cavity selection section w/ tabs and Select All button"""
        group = QGroupBox("Cavity Selection")
        layout = QVBoxLayout()

        # THis creates tab widget for Rack A/B
        tabs = QTabWidget()

        # Rack A (Cavities 1-4)
        rack_a = QWidget()
        rack_a_layout = QGridLayout()
        self.cavity_checks_a = {}
        for i in range(1, 5):
            cb = QCheckBox(f"Cavity {i}")
            self.cavity_checks_a[i] = cb
            rack_a_layout.addWidget(cb, 0, i - 1)

        # Select All button for Rack A
        self.select_all_a = QPushButton("Select All")
        self.select_all_a.clicked.connect(lambda: self._select_all_cavities('A'))
        rack_a_layout.addWidget(self.select_all_a, 1, 0, 1, 4)  # Spans all columns

        rack_a.setLayout(rack_a_layout)
        tabs.addTab(rack_a, "Rack A (1-4)")

        # Rack B
        rack_b = QWidget()
        rack_b_layout = QGridLayout()
        self.cavity_checks_b = {}
        for i in range(5, 9):
            cb = QCheckBox(f"Cavity {i}")
            self.cavity_checks_b[i] = cb
            rack_b_layout.addWidget(cb, 0, i - 5)

        # Select All button for Rack B
        self.select_all_b = QPushButton("Select All")
        self.select_all_b.clicked.connect(lambda: self._select_all_cavities('B'))
        rack_b_layout.addWidget(self.select_all_b, 1, 0, 1, 4)

        rack_b.setLayout(rack_b_layout)
        tabs.addTab(rack_b, "Rack B (5-8)")

        layout.addWidget(tabs)
        group.setLayout(layout)
        return group

    def _select_all_cavities(self, rack: str):
        """Select and/or deselect all cavities in specified rack
        """
        if self.is_updating:
            return

        self.is_updating = True
        try:
            # This gets the relevant checkboxes and button
            checks = self.cavity_checks_a if rack == 'A' else self.cavity_checks_b
            button = self.select_all_a if rack == 'A' else self.select_all_b

            # Determine the current state (use 1st checkbox as reference)
            first_cavity = min(checks.keys())
            current_state = checks[first_cavity].isChecked()

            # Toggles all checkboxes to the opp state
            new_state = not current_state
            for cb in checks.values():
                cb.setChecked(new_state)

            # Update button text
            button.setText("Deselect All" if new_state else "Select All")

            # Validate w/ is_bulk_action=True to skip the "at least one cavity" check
            if error_msg := self.validate_cavity_selection(is_bulk_action=True):
                # Reset checkboxes if validation fails
                for cb in checks.values():
                    cb.setChecked(current_state)
                button.setText("Deselect All" if current_state else "Select All")
                QMessageBox.warning(self, "Invalid Selection", error_msg)
            else:
                # For config emission after bulk action, still use standard validation
                config = self.get_config()
                self.configChanged.emit(config)


        finally:
            self.is_updating = False

    def create_settings_section(self):
        """Create acquisition settings section"""
        group = QGroupBox("Acquisition Settings")
        layout = QGridLayout()

        # Decimation
        layout.addWidget(QLabel("Decimation:"), 0, 0)
        self.decim_combo = QComboBox()
        self.decim_combo.addItems([str(x) for x in [1, 2, 4, 8]])
        layout.addWidget(self.decim_combo, 0, 1)

        # Buffer count
        layout.addWidget(QLabel("Buffer Count:"), 1, 0)
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1, 1000)
        self.buffer_spin.setValue(65)
        layout.addWidget(self.buffer_spin, 1, 1)

        group.setLayout(layout)
        return group

    def create_control_section(self):
        """Create measurement control section"""
        group = QGroupBox("Measurement Control")
        layout = QHBoxLayout()

        self.start_button = QPushButton("Start Measurement")
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        group.setLayout(layout)
        return group

    def _on_linac_selected(self, linac):
        """Handle linac selection"""
        if self.is_updating:
            return

        self.is_updating = True
        try:
            # This updates button states
            for l, btn in self.linac_buttons.items():
                btn.setChecked(l == linac)

            self.selected_linac = linac
            self._update_cryomodule_buttons()
            self._emit_config_if_valid()
        finally:
            self.is_updating = False

    def _update_cryomodule_buttons(self):
        """Update cryomodule buttons based on selected linac"""
        # This clears existing buttons
        for btn in self.cryo_buttons.values():
            self.cryo_layout.removeWidget(btn)
            btn.deleteLater()
        self.cryo_buttons.clear()

        if not self.selected_linac:
            return

        # Add new buttons
        modules = self.VALID_LINACS[self.selected_linac]
        row = col = 0
        max_cols = 6

        for module in modules:
            # Store full ACCL name pattern but display simple number
            accl_name = f"ACCL:{self.selected_linac}:{module}00"

            # Create button w/ simple display text
            display_text = module  # Just show "01", "02", "H1" etc.
            btn = QPushButton(display_text)
            btn.setCheckable(True)
            btn.clicked.connect(self._emit_config_if_valid)

            # Store full ACCL name and module ID as properties
            btn.setProperty('accl_name', accl_name)
            btn.setProperty('module_id', module)

            self.cryo_buttons[module] = btn
            self.cryo_layout.addWidget(btn, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def validate_cavity_selection(self, is_bulk_action: bool = False) -> Optional[str]:
        """Validate cavity selection


        Args:
            is_bulk_action: If True, skip the "at least one cavity" check for bulk operations


        Returns:
            Error message string if validation fails, None if validation passes
        """
        # Only perform validation for cavity related actions, not for initial setup
        sender = self.sender()
        if isinstance(sender, QCheckBox) or isinstance(sender, QPushButton) and sender in [self.select_all_a,
                                                                                           self.select_all_b]:
            # Get selected cavities
            selected_a = [num for num, cb in self.cavity_checks_a.items() if cb.isChecked()]
            selected_b = [num for num, cb in self.cavity_checks_b.items() if cb.isChecked()]

            # For individual selections check if any cavities are selected
            if not is_bulk_action and not selected_a and not selected_b:
                return "Please select at least one cavity"

            # This prevents cross rack selection
            if selected_a and selected_b:
                return "Cannot measure cavities from both racks simultaneously"

        return None

    def _config_changed(self):
        """Emit configuration changed signal w/ validation"""
        # For normal config changes, use standard validation 
        if error_msg := self.validate_cavity_selection(is_bulk_action=False):
            QMessageBox.warning(self, "Invalid Selection", error_msg)
            return

        config = self.get_config()
        self.configChanged.emit(config)

    def _emit_config_if_valid(self):
        """Emit configuration only if valid """
        if not self.is_updating:
            # For normal config changes, use standard validation
            if error_msg := self.validate_cavity_selection(is_bulk_action=False):
                QMessageBox.warning(self, "Invalid Selection", error_msg)
                return
            config = self.get_config()
            self.configChanged.emit(config)

    def connect_signals(self):
        # Connect cavity checkboxes -> single validation point
        for checks in [self.cavity_checks_a, self.cavity_checks_b]:
            for cb in checks.values():
                cb.stateChanged.connect(self._on_cavity_selection_changed)

        # This connects module buttons
        for btn in self.cryo_buttons.values():
            btn.clicked.connect(self._emit_config_if_valid)

        # This connects start/stop buttons
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self.measurementStopped.emit)

    def _on_start_clicked(self):
        """Handle start button click w/ validation"""
        error_msg = self.validate_cavity_selection(is_bulk_action=False)
        if error_msg:
            QMessageBox.warning(self, "Invalid Selection", error_msg)
            return
        self.measurementStarted.emit()

    def _on_cavity_selection_changed(self):
        """Handle cavity selection changes w/ button text updates"""
        if self.is_updating:
            return

        self.is_updating = True
        try:
            # Update Rack A button text
            all_a_selected = all(cb.isChecked() for cb in self.cavity_checks_a.values())
            self.select_all_a.setText("Deselect All" if all_a_selected else "Select All")

            # Update Rack B button text
            all_b_selected = all(cb.isChecked() for cb in self.cavity_checks_b.values())
            self.select_all_b.setText("Deselect All" if all_b_selected else "Select All")

            # For individual cavity selection, use normal validation
            error_msg = self.validate_cavity_selection(is_bulk_action=False)
            if error_msg:
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(error_msg)
                msg_box.setWindowTitle("Invalid Selection")
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.setModal(False)
                msg_box.show()

                # Reset the checkbox that was just changed
                sender = self.sender()
                if isinstance(sender, QCheckBox):
                    sender.setChecked(False)
            else:
                self._emit_config_if_valid()
        finally:
            self.is_updating = False

    def get_config(self):
        """Get current configuration"""
        selected_modules = []
        for mod, btn in self.cryo_buttons.items():
            if btn.isChecked():
                base_accl = f"ACCL:{self.selected_linac}:{mod}00"
                module_config = {
                    'id': mod,
                    'name': base_accl,
                    'base_channel': base_accl,
                    'channel_access': {
                        'rack_a': [],
                        'rack_b': []
                    }
                }

                for cav_num, cb in self.cavity_checks_a.items():
                    if cb.isChecked():
                        module_config['channel_access']['rack_a'].append(
                            f"ca://{base_accl}:RESA:{cav_num}"
                        )

                for cav_num, cb in self.cavity_checks_b.items():
                    if cb.isChecked():
                        module_config['channel_access']['rack_b'].append(
                            f"ca://{base_accl}:RESB:{cav_num}"
                        )

                selected_modules.append(module_config)

        return {
            'linac': self.selected_linac,
            'modules': selected_modules,
            'cavities': {
                **{num: cb.isChecked() for num, cb in self.cavity_checks_a.items()},
                **{num: cb.isChecked() for num, cb in self.cavity_checks_b.items()}
            },
            'decimation': int(self.decim_combo.currentText()),
            'buffer_count': self.buffer_spin.value()
        }

    def set_measurement_running(self, running: bool):
        """Update UI state for measurement status"""
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
