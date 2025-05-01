from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QGridLayout
from pydm.widgets import PyDMEnumComboBox

from applications.tuning.tune_cavity import TuneCavity
from applications.tuning.tune_utils import LabeledSpinbox


class CavitySection:
    def __init__(self, cavity: TuneCavity):
        self.cavity = cavity
        self.tune_state: PyDMEnumComboBox = PyDMEnumComboBox(
            init_channel=cavity.tune_config_pv
        )

        self.chirp_start: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.chirp_freq_start_pv
        )

        self.chirp_stop: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.chirp_freq_stop_pv
        )

        self.motor_speed: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.stepper_tuner.speed_pv
        )

        self.max_steps: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.stepper_tuner.max_steps_pv
        )

        self.groupbox = QGroupBox(f"{cavity}")
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)
        spinbox_layout = QGridLayout()
        layout.addWidget(self.tune_state)
        layout.addLayout(spinbox_layout)
        spinbox_layout.addLayout(self.chirp_start.layout, 0, 0)
        spinbox_layout.addLayout(self.chirp_stop.layout, 0, 1)
        spinbox_layout.addLayout(self.motor_speed.layout, 1, 0)
        spinbox_layout.addLayout(self.max_steps.layout, 1, 1)
