from functools import partial
from typing import TYPE_CHECKING

from PyQt5.QtCore import QRunnable
from PyQt5.QtWidgets import QLabel, QPushButton
from epics.ca import withInitialContext
from lcls_tools.common.frontend.display.util import WorkerSignals

from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityHWModeError,
    DetuneError,
    StepperAbortError,
    StepperError,
)

if TYPE_CHECKING:
    from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity


class ParkSignals(WorkerSignals):
    def __init__(
        self,
        status_label: QLabel,
        cold_button: QPushButton,
        park_button: QPushButton = None,
    ):
        super().__init__(status_label)
        self.status.connect(partial(cold_button.setEnabled, False))
        self.finished.connect(partial(cold_button.setEnabled, True))
        self.error.connect(partial(cold_button.setEnabled, True))

        if park_button:
            self.status.connect(partial(park_button.setEnabled, False))
            self.finished.connect(partial(park_button.setEnabled, True))
            self.error.connect(partial(park_button.setEnabled, True))


class ColdWorker(QRunnable):
    def __init__(
        self,
        cavity: "TuneCavity",
        status_label: QLabel,
        cold_button: QPushButton,
        park_button: QPushButton = None,
    ):
        super().__init__()
        self.setAutoDelete(False)
        self.signals = ParkSignals(status_label=status_label, park_button=park_button, cold_button=cold_button)
        self.cavity: "TuneCavity" = cavity

    @withInitialContext
    def run(self):
        self.signals.status.emit("Moving to cold landing")
        try:
            self.cavity.move_to_cold_landing(
                count_current=False,
                use_rf=True,
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
