from functools import partial

from PyQt5.QtCore import QRunnable
from PyQt5.QtWidgets import QCheckBox, QLabel, QPushButton, QRadioButton
from epics.ca import withInitialContext
from lcls_tools.common.frontend.display.util import WorkerSignals
from lcls_tools.superconducting.sc_linac_utils import (
    CavityAbortError,
    CavityHWModeError,
    DetuneError,
    StepperAbortError,
    StepperError,
)

from park_linac import ParkCavity


class ParkSignals(WorkerSignals):
    def __init__(
        self, status_label: QLabel, cold_button: QPushButton, park_button: QPushButton
    ):
        super().__init__(status_label)
        self.status.connect(partial(cold_button.setEnabled, False))
        self.finished.connect(partial(cold_button.setEnabled, True))
        self.error.connect(partial(cold_button.setEnabled, True))

        self.status.connect(partial(park_button.setEnabled, False))
        self.finished.connect(partial(park_button.setEnabled, True))
        self.error.connect(partial(park_button.setEnabled, True))


class ColdWorker(QRunnable):
    def __init__(
        self,
        cavity: ParkCavity,
        status_label: QLabel,
        park_button: QPushButton,
        cold_button: QPushButton,
        count_signed_steps: QCheckBox,
        freq_radiobutton: QRadioButton,
    ):
        super().__init__()
        self.setAutoDelete(False)
        self.signals = ParkSignals(
            status_label=status_label, park_button=park_button, cold_button=cold_button
        )
        self.cavity: ParkCavity = cavity
        self.count_signed_steps: QCheckBox = count_signed_steps
        self.freq_radiobutton: QRadioButton = freq_radiobutton

    @withInitialContext
    def run(self):
        self.signals.status.emit("Moving to cold landing")
        try:
            self.cavity.move_to_cold_landing(
                count_current=self.count_signed_steps.isChecked(),
                use_freq=self.freq_radiobutton.isChecked(),
            )
            self.signals.finished.emit("Cavity at cold landing")
        except (
            StepperAbortError,
            StepperError,
            CavityAbortError,
            DetuneError,
            CavityHWModeError,
        ) as e:
            self.cavity.stepper_tuner.abort_flag = False
            self.cavity.abort_flag = False
            self.signals.error.emit(str(e))
