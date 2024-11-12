import dataclasses
from typing import Optional, Dict

from PyQt5.QtWidgets import QPushButton
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display
from pydm.widgets import PyDMLabel

from applications.auto_setup.backend.setup_cryomodule import SetupCryomodule
from applications.auto_setup.backend.setup_machine import SETUP_MACHINE
from applications.auto_setup.frontend.gui_cavity import GUICavity
from applications.auto_setup.frontend.utils import Settings


@dataclasses.dataclass
class GUICryomodule:
    linac_idx: int
    name: str
    settings: Settings
    parent: Display

    def __post_init__(self):
        self._cryomodule: Optional[SetupCryomodule] = None

        self.readback_label: PyDMLabel = PyDMLabel(
            init_channel=f"ACCL:L{self.linac_idx}B:{self.name}00:AACTMEANSUM"
        )
        self.readback_label.alarmSensitiveBorder = True
        self.readback_label.alarmSensitiveContent = True
        self.readback_label.showUnits = True

        self.setup_button: QPushButton = QPushButton(f"Set Up CM{self.name}")
        self.setup_button.clicked.connect(self.trigger_setup)

        self.abort_button: QPushButton = QPushButton(f"Abort Action for CM{self.name}")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.request_stop)
        self.turn_off_button: QPushButton = QPushButton(f"Turn off CM{self.name}")
        self.turn_off_button.clicked.connect(self.trigger_shutdown)

        self.acon_button: QPushButton = QPushButton(
            f"Push all CM{self.name} ADES to ACON"
        )
        self.acon_button.clicked.connect(self.capture_acon)

        self.gui_cavities: Dict[int, GUICavity] = {}

        for cav_num in range(1, 9):
            gui_cavity = GUICavity(
                cav_num,
                f"ACCL:L{self.linac_idx}B:{self.name}{cav_num}0:",
                self.name,
                settings=self.settings,
                parent=self.parent,
            )
            self.gui_cavities[cav_num] = gui_cavity

    def capture_acon(self):
        for cavity_widget in self.gui_cavities.values():
            cavity_widget.cavity.capture_acon()

    def trigger_shutdown(self):
        self.cryomodule_object.trigger_shutdown()

    def request_stop(self):
        self.cryomodule_object.request_abort()

    @property
    def cryomodule_object(self) -> SetupCryomodule:
        if not self._cryomodule:
            self._cryomodule: SetupCryomodule = SETUP_MACHINE.cryomodules[self.name]
        return self._cryomodule

    def trigger_setup(self):
        self.cryomodule_object.ssa_cal_requested = (
            self.settings.ssa_cal_checkbox.isChecked()
        )
        self.cryomodule_object.auto_tune_requested = (
            self.settings.auto_tune_checkbox.isChecked()
        )
        self.cryomodule_object.cav_char_requested = (
            self.settings.cav_char_checkbox.isChecked()
        )
        self.cryomodule_object.rf_ramp_requested = (
            self.settings.rf_ramp_checkbox.isChecked()
        )

        self.cryomodule_object.trigger_setup()
