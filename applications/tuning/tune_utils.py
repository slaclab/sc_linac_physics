from functools import partial
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QLabel, QPushButton
from lcls_tools.common.frontend.display.util import WorkerSignals

from utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityHWModeError,
    DetuneError,
    StepperAbortError,
    StepperError,
)

if TYPE_CHECKING:
    pass


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
