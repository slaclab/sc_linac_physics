from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QGridLayout,
    QScrollArea,
    QMessageBox,
    QTabWidget,
)

from applications.microphonics.gui.async_data_manager import BASE_HARDWARE_SAMPLE_RATE
from applications.microphonics.utils.pv_utils import format_accl_base
from applications.microphonics.utils.ui_utils import (
    create_cavity_selection_tabs,
    create_pushbuttons,
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
    decimationSettingChanged = pyqtSignal(int)

    # Constants
    VALID_LINACS = {
        "L0B": ["01"],
        "L1B": ["02", "03", "H1", "H2"],
        "L2B": [f"{i:02d}" for i in range(4, 16)],
        "L3B": [f"{i:02d}" for i in range(16, 36)],
    }
    VALID_DECIMATION = {1, 2, 4, 8}
    DEFAULT_DECIMATION_VALUE = 2
    DEFAULT_BUFFER_COUNT = 1
    BUFFER_LENGTH = 16384

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_linac = None
        self.is_updating = True

        self.cavity_checks_a = {}
        self.cavity_checks_b = {}
        self.select_all_a = None
        self.select_all_b = None
        self.linac_buttons = {}
        self.cryo_buttons = {}
        self.cryo_layout = None
        self.decim_combo = None
        self.buffer_spin = None
        self.start_button = None
        self.stop_button = None
        self.label_sampling_rate = None
        self.label_acq_time = None
        # Setup UI components
        self.setup_ui()
        self._set_default_decimation()
        self.connect_signals()

        self._update_daq_parameters()

        self.is_updating = False
        self._emit_config_changed()

    def setup_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Scrollable area
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

    def get_selected_decimation(self):
        """Returns the currently selected decimation value from the UI."""
        try:
            return int(self.decim_combo.currentText())
        except ValueError:
            print(f"Warning: Could not parse decimation from UI, defaulting to {self.DEFAULT_DECIMATION_VALUE}.")
            return self.DEFAULT_DECIMATION_VALUE

    def _set_default_decimation(self):
        """Sets the decimation combo box to the default value."""
        if str(self.DEFAULT_DECIMATION_VALUE) in [
            self.decim_combo.itemText(i) for i in range(self.decim_combo.count())
        ]:
            self.decim_combo.setCurrentText(str(self.DEFAULT_DECIMATION_VALUE))
        else:
            if self.decim_combo.count() > 0:
                self.decim_combo.setCurrentIndex(0)

    def create_linac_section(self) -> QGroupBox:
        """Create linac and CM selection group"""
        group = QGroupBox("Linac Configuration")
        layout = QVBoxLayout()

        # Linac selection buttons
        linac_layout = QHBoxLayout()
        linac_items = {linac: linac for linac in self.VALID_LINACS}

        # Make linac selection buttons
        self.linac_buttons = create_pushbuttons(
            self,
            linac_items,
            linac_layout,
            checkable=True,
            connect_to=self._on_linac_selected,
        )

        layout.addLayout(linac_layout)

        # CM selection grid
        self.cryo_group = QGroupBox("Cryomodule Selection")
        self.cryo_layout = QGridLayout()
        self.cryo_group.setLayout(self.cryo_layout)
        layout.addWidget(self.cryo_group)

        group.setLayout(layout)
        return group

    def create_cavity_section(self):
        """Create cavity selection section w/ tabs"""
        group = QGroupBox("Cavity Selection")
        layout = QVBoxLayout()

        # Rack configuration
        rack_config = {
            "A": {"title": "Rack A (1-4)", "cavities": [1, 2, 3, 4]},
            "B": {"title": "Rack B (5-8)", "cavities": [5, 6, 7, 8]},
        }
        # Create cavity selection tabs
        cavity_tabs = {}
        select_all_buttons = {}

        cavity_tabs, select_all_buttons = create_cavity_selection_tabs(self, rack_config, self._select_all_cavities)
        self.cavity_checks_a = cavity_tabs["A"]
        self.cavity_checks_b = cavity_tabs["B"]
        self.select_all_a = select_all_buttons["A"]
        self.select_all_b = select_all_buttons["B"]

        # Find tab widget
        for child in self.children():
            if isinstance(child, QTabWidget):
                layout.addWidget(child)
                break
        self.select_all_btn = QPushButton("Select All (1-8)")
        self.select_all_btn.clicked.connect(self.select_all_cavities)
        layout.addWidget(self.select_all_btn)
        group.setLayout(layout)
        return group

    def _select_all_cavities(self, rack: str):
        """Select and/or deselect all cavities in specified rack"""
        if self.is_updating:
            return

        self.is_updating = True
        try:
            # Gets relevant checkboxes and button
            checks = self.cavity_checks_a if rack == "A" else self.cavity_checks_b
            button = self.select_all_a if rack == "A" else self.select_all_b

            # Determine the current state (use 1st checkbox as reference)
            first_cavity = min(checks.keys())
            current_state = checks[first_cavity].isChecked()

            # Toggles all checkboxes to the opp state
            new_state = not current_state
            for cb in checks.values():
                cb.setChecked(new_state)

            # Update button text
            button.setText("Deselect All" if new_state else "Select All")

            self._emit_config_changed()

        finally:
            self.is_updating = False

    def select_all_cavities(self):
        """Select all cavities across both racks"""
        if self.is_updating:
            return

        self.is_updating = True
        try:
            # Check if all cavities are picked
            all_selected = all(cb.isChecked() for cb in self.cavity_checks_a.values()) and all(
                cb.isChecked() for cb in self.cavity_checks_b.values()
            )

            # Toggle to opposite state
            new_state = not all_selected

            # Apply new state to all checkboxes
            for cb in self.cavity_checks_a.values():
                cb.setChecked(new_state)
            for cb in self.cavity_checks_b.values():
                cb.setChecked(new_state)

            # Update main button text
            self.select_all_btn.setText("Deselect All (1-8)" if new_state else "Select All (1-8)")

            # Emit configuration
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
        self.decim_combo.addItems([str(x) for x in sorted(self.VALID_DECIMATION)])
        layout.addWidget(self.decim_combo, 0, 1)

        # Buffer count
        layout.addWidget(QLabel("Buffer Count:"), 1, 0)
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1, 1000)
        self.buffer_spin.setValue(self.DEFAULT_BUFFER_COUNT)
        layout.addWidget(self.buffer_spin, 1, 1)

        # Sampling Rate Display
        layout.addWidget(QLabel("Sampling Rate:"), 2, 0)
        self.label_sampling_rate = QLabel("1000.0")
        self.label_sampling_rate.setStyleSheet("font-weight: bold")
        layout.addWidget(self.label_sampling_rate, 2, 1)
        layout.addWidget(QLabel("Hz"), 2, 2)

        # Acquisition Time Display
        layout.addWidget(QLabel("Acquisition Time:"), 3, 0)
        self.label_acq_time = QLabel("16.384")
        self.label_acq_time.setStyleSheet("font-weight: bold")
        layout.addWidget(self.label_acq_time, 3, 1)
        layout.addWidget(QLabel("s"), 3, 2)

        group.setLayout(layout)
        return group

    def _update_daq_parameters(self):
        """Calculate and update sampling rate and acquisition time displays"""
        try:
            # Get current values (buffer count and the selected text from decimation combo box)
            number_of_buffers = int(self.buffer_spin.value())
            decimation_text = self.decim_combo.currentText()
            # If somehow the combo box does not have any text set displays to N/A and exit
            if not decimation_text:
                self.label_sampling_rate.setText("N/A")
                self.label_acq_time.setText("N/A")
                return
            # Converting decimation text to int ("2" -> 2)
            decimation_num = int(decimation_text)

            # Calculate sampling rate
            sampling_rate = BASE_HARDWARE_SAMPLE_RATE / decimation_num

            # Display sampling rate with right precision
            if sampling_rate >= 1000:
                # (e.g 2000)
                self.label_sampling_rate.setText(f"{sampling_rate:.0f}")
            else:
                # (e.g 500.0)
                self.label_sampling_rate.setText(f"{sampling_rate:.1f}")

            # Calculate total acquisition time
            # Formula: (BUFFER_LENGTH / effective_sample_rate) * number_of_buffers
            acquisition_time = (self.BUFFER_LENGTH * decimation_num * number_of_buffers) / BASE_HARDWARE_SAMPLE_RATE

            # Display acquisition time with right precision
            if acquisition_time < 1:
                self.label_acq_time.setText(f"{acquisition_time:.3f}")
            else:
                self.label_acq_time.setText(f"{acquisition_time:.2f}")

        except ValueError as e:
            print(f"Error parsing values in _update_daq_parameters: {e}")
            self.label_sampling_rate.setText("Error")
            self.label_acq_time.setText("Error")
        except Exception as e:
            print(f"Unexpected error in _update_daq_parameters: {e}")
            self.label_sampling_rate.setText("Error")
            self.label_acq_time.setText("Error")

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
            # Updates button states
            for linac, btn in self.linac_buttons.items():
                btn.setChecked(linac == linac)

            self.selected_linac = linac
            self._update_cryomodule_buttons()
            self._emit_config_changed()
        finally:
            self.is_updating = False

    def _update_cryomodule_buttons(self):
        """Update cryomodule buttons based on selected linac"""
        # Clears existing buttons
        for btn in self.cryo_buttons.values():
            self.cryo_layout.removeWidget(btn)
            btn.deleteLater()
        self.cryo_buttons.clear()

        if not self.selected_linac:
            return

        # Add new buttons
        modules = self.VALID_LINACS[self.selected_linac]

        # Create dictionary of button items
        button_items = {}
        custom_properties = {}

        for module in modules:
            # Use simple display text
            display_text = module  # Just show "01", "02", "H1" etc.
            button_items[module] = display_text

            # Store module ID as properties
            custom_properties[module] = {"module_id": module}

        # Create buttons
        self.cryo_buttons = create_pushbuttons(
            self,
            button_items,
            self.cryo_layout,
            checkable=True,
            connect_to=lambda _: self._emit_config_changed(),
            custom_properties=custom_properties,
            grid_layout=True,
            max_cols=6,
        )

    def validate_cavity_selection(self, is_bulk_action: bool = False) -> Optional[str]:
        """Validate cavity selection"""

        # Get selected cavities
        selected_a = [num for num, cb in self.cavity_checks_a.items() if cb.isChecked()]
        selected_b = [num for num, cb in self.cavity_checks_b.items() if cb.isChecked()]

        # For individual selections check if any cavities are selected
        if not is_bulk_action and not selected_a and not selected_b:
            return "Please select at least one cavity"

        return None

    def _emit_config_changed(self):
        """Emit configuration whenever it changes"""
        if not self.is_updating:
            config = self.get_config()
            self.configChanged.emit(config)

    def connect_signals(self):
        # Connect cavity checkboxes -> single validation point
        for checks in [self.cavity_checks_a, self.cavity_checks_b]:
            for cb in checks.values():
                cb.stateChanged.connect(self._on_cavity_selection_changed)

        # Connects start/stop buttons
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self.measurementStopped.emit)

        if hasattr(self, "decim_combo"):
            self.decim_combo.currentIndexChanged.connect(self._handle_decimation_change)
        else:
            print("WARNING (ConfigPanel): self.decim_combo not found during signal connection.")
        if hasattr(self, "buffer_spin"):
            self.buffer_spin.valueChanged.connect(self._update_daq_parameters)
            self.buffer_spin.valueChanged.connect(lambda: self._emit_config_changed() if not self.is_updating else None)
        else:
            print("WARNING (ConfigPanel): self.buffer_spin not found during signal connection.")

    def _handle_decimation_change(self):
        """Handle changes to decimation combo box"""
        # Update DAQ parameters display (to recalculate and update sampling rate and acq time displays)
        self._update_daq_parameters()

        # Emit decimation specific signal
        try:
            # Get current decimation value from combo box
            dec_value = int(self.decim_combo.currentText())
            # Emit signal w/ new decimation value
            self.decimationSettingChanged.emit(dec_value)
            print(f"DEBUG (ConfigPanel): Emitted decimationSettingChanged with value: {dec_value}")
        except ValueError:
            print(
                f"WARNING (ConfigPanel): Could not parse decimation value from "
                f"combo box: {self.decim_combo.currentText()}"
            )

        # Emit general config change if not updating
        if not self.is_updating:
            self._emit_config_changed()

    def _on_start_clicked(self):
        """Start button click w/ validation"""
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

            self._emit_config_changed()

        finally:
            self.is_updating = False

    def get_config(self):
        """Get current configuration"""
        selected_modules = []
        for mod, btn in self.cryo_buttons.items():
            if btn.isChecked():
                base_accl = format_accl_base(self.selected_linac, mod)
                module_config = {
                    "id": mod,
                    "name": base_accl,
                    "base_channel": base_accl,
                }

                selected_modules.append(module_config)

        return {
            "linac": self.selected_linac,
            "modules": selected_modules,
            "cavities": {
                **{num: cb.isChecked() for num, cb in self.cavity_checks_a.items()},
                **{num: cb.isChecked() for num, cb in self.cavity_checks_b.items()},
            },
            "decimation": int(self.decim_combo.currentText()),
            "buffer_count": self.buffer_spin.value(),
        }

    def set_measurement_running(self, running: bool):
        """Update UI state for measurement status"""
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
