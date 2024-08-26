from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QGroupBox, QGridLayout, QLabel
from pydm.widgets import PyDMEnumComboBox, PyDMSpinbox, PyDMLabel
from pydm.widgets.enum_button import PyDMEnumButton


class RFControls:
    def __init__(self):
        self.ssa_on_button: QPushButton = QPushButton("SSA On")
        self.ssa_off_button: QPushButton = QPushButton("SSA Off")
        self.ssa_readback_label: PyDMLabel = PyDMLabel()

        self.rf_mode_combobox: PyDMEnumComboBox = PyDMEnumComboBox()
        self.rf_mode_readback_label: PyDMLabel = PyDMLabel()

        self.rf_on_button: QPushButton = QPushButton("RF On")
        self.rf_off_button: QPushButton = QPushButton("RF Off")
        self.rf_status_readback_label: PyDMLabel = PyDMLabel()

        self.ades_spinbox: PyDMSpinbox = PyDMSpinbox()
        self.aact_readback_label: PyDMLabel = PyDMLabel()

        self.srf_max_spinbox: PyDMSpinbox = PyDMSpinbox()
        self.srf_max_readback_label: PyDMLabel = PyDMLabel()

        self.rf_control_groupbox: QGroupBox = QGroupBox("RF Controls")
        control_groupbox_layout = QGridLayout()
        self.rf_control_groupbox.setLayout(control_groupbox_layout)
        ssa_row = 0
        control_groupbox_layout.addWidget(self.ssa_on_button, ssa_row, 0)
        control_groupbox_layout.addWidget(self.ssa_off_button, ssa_row, 1)
        control_groupbox_layout.addWidget(self.ssa_readback_label, ssa_row, 2)

        rf_row = 1
        control_groupbox_layout.addWidget(self.rf_on_button, rf_row, 0)
        control_groupbox_layout.addWidget(self.rf_off_button, rf_row, 1)
        control_groupbox_layout.addWidget(self.rf_status_readback_label, rf_row, 2)

        mode_row = 2
        control_groupbox_layout.addWidget(self.rf_mode_combobox, mode_row, 0, 1, 3)

        amp_row = 3
        control_groupbox_layout.addWidget(QLabel("Amplitude:"), amp_row, 0)
        control_groupbox_layout.addWidget(self.ades_spinbox, amp_row, 1)
        control_groupbox_layout.addWidget(self.aact_readback_label, amp_row, 2)

        max_row = 4
        control_groupbox_layout.addWidget(QLabel("SRF Max"), max_row, 0)
        control_groupbox_layout.addWidget(self.srf_max_spinbox, max_row, 1)
        control_groupbox_layout.addWidget(self.srf_max_readback_label, max_row, 2)

