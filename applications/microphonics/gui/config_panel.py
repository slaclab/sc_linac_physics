"""Configuration panel for the Microphonics GUI"""

from typing import Dict, List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QCheckBox, QSpinBox,
    QPushButton
)


class ConfigPanel(QWidget):
    # Signals
    configChanged = pyqtSignal(dict)  # Emitted when any configuration changes
    measurementStarted = pyqtSignal()  # Emitted when start button clicked
    measurementStopped = pyqtSignal()  # Emitted when stop button clicked

    # Constants
    VALID_LINACS = {"L0B", "L1B", "L2B", "L3B"}
    VALID_DECIMATION = {1, 2, 4, 8}
    DEFAULT_BUFFER_COUNT = 65

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)

        # Create configuration sections
        linac_group = self.create_linac_group()
        cavity_group = self.create_cavity_group()
        settings_group = self.create_settings_group()
        control_group = self.create_control_group()

        # Add to main layout
        layout.addWidget(linac_group)
        layout.addWidget(cavity_group)
        layout.addWidget(settings_group)
        layout.addWidget(control_group)
        layout.addStretch()

    def create_linac_group(self) -> QGroupBox:
        """Create linac and cryomodule selection group"""
        group = QGroupBox("Linac Configuration")
        layout = QVBoxLayout()

        # Linac selection
        linac_layout = QHBoxLayout()
        linac_label = QLabel("Linac:")
        self.linac_combo = QComboBox()
        self.linac_combo.addItems(sorted(self.VALID_LINACS))
        linac_layout.addWidget(linac_label)
        linac_layout.addWidget(self.linac_combo)
        linac_layout.addStretch()
        layout.addLayout(linac_layout)

        # Cryomodule selection
        cryo_layout = QHBoxLayout()
        cryo_label = QLabel("Cryomodule:")
        self.cryo_combo = QComboBox()
        cryo_layout.addWidget(cryo_label)
        cryo_layout.addWidget(self.cryo_combo)
        cryo_layout.addStretch()
        layout.addLayout(cryo_layout)

        group.setLayout(layout)
        return group

    def create_cavity_group(self) -> QGroupBox:
        """Create cavity selection group"""
        group = QGroupBox("Cavity Selection")
        layout = QVBoxLayout()

        # Rack A (Cavities 1-4)
        rack_a = QGroupBox("Rack A (Cavities 1-4)")
        rack_a_layout = QHBoxLayout()
        self.cavity_checks = {}
        for i in range(1, 5):
            cb = QCheckBox(str(i))
            self.cavity_checks[i] = cb
            rack_a_layout.addWidget(cb)
        rack_a.setLayout(rack_a_layout)
        layout.addWidget(rack_a)

        # Rack B (Cavities 5-8)
        rack_b = QGroupBox("Rack B (Cavities 5-8)")
        rack_b_layout = QHBoxLayout()
        for i in range(5, 9):
            cb = QCheckBox(str(i))
            self.cavity_checks[i] = cb
            rack_b_layout.addWidget(cb)
        rack_b.setLayout(rack_b_layout)
        layout.addWidget(rack_b)

        group.setLayout(layout)
        return group

    def create_settings_group(self) -> QGroupBox:
        """Create acquisition settings group"""
        group = QGroupBox("Acquisition Settings")
        layout = QHBoxLayout()

        # Decimation
        decim_label = QLabel("Decimation:")
        self.decim_combo = QComboBox()
        self.decim_combo.addItems([str(x) for x in sorted(self.VALID_DECIMATION)])
        layout.addWidget(decim_label)
        layout.addWidget(self.decim_combo)

        # Buffer count
        buffer_label = QLabel("Buffer Count:")
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1, 1000)
        self.buffer_spin.setValue(self.DEFAULT_BUFFER_COUNT)
        layout.addWidget(buffer_label)
        layout.addWidget(self.buffer_spin)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def create_control_group(self) -> QGroupBox:
        """Create measurement control group"""
        group = QGroupBox("Measurement Control")
        layout = QHBoxLayout()

        self.start_button = QPushButton("Start Measurement")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addStretch()

        group.setLayout(layout)
        return group

    def connect_signals(self):
        """Connect internal signals"""
        # Linac/Cryo signals
        self.linac_combo.currentTextChanged.connect(self._on_linac_changed)
        self.cryo_combo.currentTextChanged.connect(self._config_changed)

        # Cavity checkboxes
        for cb in self.cavity_checks.values():
            cb.stateChanged.connect(self._cavity_selection_changed)

        # Settings signals
        self.decim_combo.currentTextChanged.connect(self._config_changed)
        self.buffer_spin.valueChanged.connect(self._config_changed)

        # Control signals
        self.start_button.clicked.connect(self._on_start)
        self.stop_button.clicked.connect(self._on_stop)

    def _on_linac_changed(self, linac: str):
        """Handle linac selection changes"""
        self.cryo_combo.clear()

        # Add standard modules (01-35)
        for i in range(1, 36):
            self.cryo_combo.addItem(f"{i:02d}")

        # Add harmonic modules for L1B
        if linac == "L1B":
            self.cryo_combo.addItems(["H1", "H2"])

        self._config_changed()

    def _cavity_selection_changed(self):
        """Handle cavity selection changes"""
        selected = self.get_selected_cavities()

        # Check for cross-rack selection
        rack_a = [c for c in selected if c <= 4]
        rack_b = [c for c in selected if c > 4]

        # Disable start if cross-rack selection
        self.start_button.setEnabled(not (rack_a and rack_b))

        self._config_changed()

    def _config_changed(self):
        """Emit configuration changed signal"""
        self.configChanged.emit(self.get_config())

    def _on_start(self):
        """Handle measurement start"""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.measurementStarted.emit()

    def _on_stop(self):
        """Handle measurement stop"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.measurementStopped.emit()

    def get_selected_cavities(self) -> List[int]:
        """Get list of selected cavity numbers"""
        return [
            num for num, cb in self.cavity_checks.items()
            if cb.isChecked()
        ]

    def get_config(self) -> Dict:
        """Get current configuration"""
        return {
            'linac': self.linac_combo.currentText(),
            'cryomodule': self.cryo_combo.currentText(),
            'cavities': self.get_selected_cavities(),
            'decimation': int(self.decim_combo.currentText()),
            'buffer_count': self.buffer_spin.value()
        }

    def set_enabled(self, enabled: bool):
        """Enable/disable all controls"""
        self.linac_combo.setEnabled(enabled)
        self.cryo_combo.setEnabled(enabled)
        for cb in self.cavity_checks.values():
            cb.setEnabled(enabled)
        self.decim_combo.setEnabled(enabled)
        self.buffer_spin.setEnabled(enabled)
