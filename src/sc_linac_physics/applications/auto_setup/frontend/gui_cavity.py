import dataclasses
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton, QSizePolicy
from edmbutton import PyDMEDMDisplayButton
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display
from pydm.widgets import PyDMLabel, analog_indicator
from pydm.widgets.display_format import DisplayFormat

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings


@dataclasses.dataclass
class GUICavity:
    number: int
    prefix: str
    cm: str
    settings: Settings
    parent: Display

    def __post_init__(self):
        self._cavity: Optional[SetupCavity] = None
        self.setup_button = QPushButton("Set Up")

        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.request_stop)
        self.shutdown_button: QPushButton = QPushButton("Turn Off")
        self.shutdown_button.clicked.connect(self.trigger_shutdown)

        self.setup_button.clicked.connect(self.trigger_setup)
        self.aact_readback_label: PyDMLabel = PyDMLabel(
            init_channel=self.prefix + "AACTMEAN"
        )
        self.aact_readback_label.alarmSensitiveBorder = True
        self.aact_readback_label.alarmSensitiveContent = True
        self.aact_readback_label.showUnits = True
        self.aact_readback_label.precisionFromPV = False
        self.aact_readback_label.precision = 2

        # Putting this here because it otherwise gets garbage collected (?!)
        self.acon_label: PyDMLabel = PyDMLabel(
            init_channel=self.prefix + "ACON"
        )
        self.acon_label.alarmSensitiveContent = True
        self.acon_label.alarmSensitiveBorder = True
        self.acon_label.showUnits = True
        self.acon_label.precisionFromPV = False
        self.acon_label.precision = 2

        self.status_label: PyDMLabel = PyDMLabel(
            init_channel=self.cavity.status_msg_pv
        )

        # status_msg_pv is an ndarray of char codes and seeing the display format
        # makes is display correctly (i.e. not as [ 1 2 3 4]
        self.status_label.displayFormat = DisplayFormat.String

        self.status_label.setAlignment(Qt.AlignHCenter)
        self.status_label.setWordWrap(True)
        self.status_label.alarmSensitiveBorder = True
        self.status_label.alarmSensitiveContent = True

        self.progress_bar: analog_indicator.PyDMAnalogIndicator = (
            analog_indicator.PyDMAnalogIndicator(
                init_channel=self.cavity.progress_pv
            )
        )
        self.progress_bar.backgroundSizeRate = 0.2
        self.progress_bar.sizePolicy().setVerticalPolicy(QSizePolicy.Maximum)

        self.expert_screen_button: PyDMEDMDisplayButton = PyDMEDMDisplayButton()
        self.expert_screen_button.filenames = [
            "$EDM/llrf/rf_srf_cavity_main.edl"
        ]
        self.expert_screen_button.macros = self.cavity.edm_macro_string + (
            "," + "SELTAB=0,SELCHAR=3"
        )
        self.expert_screen_button.setToolTip("EDM expert screens")

        self.note_label: PyDMLabel = PyDMLabel(init_channel=self.cavity.note_pv)
        self.note_label.displayFormat = DisplayFormat.String
        self.note_label.setWordWrap(True)
        self.note_label.alarmSensitiveBorder = True
        self.note_label.alarmSensitiveContent = True

    def request_stop(self):
        self.cavity.trigger_abort()

    @property
    def cavity(self) -> SetupCavity:
        if not self._cavity:
            self._cavity: SetupCavity = SETUP_MACHINE.cryomodules[
                self.cm
            ].cavities[self.number]
        return self._cavity

    def trigger_shutdown(self):
        if self.cavity.script_is_running:
            self.cavity.status_message = f"{self.cavity} script already running"
            return
        self.cavity.trigger_shutdown()

    def trigger_setup(self):
        if self.cavity.script_is_running:
            self.cavity.status_message = f"{self.cavity} script already running"
            return
        elif not self.cavity.is_online:
            self.cavity.status_message = f"{self.cavity} not online, skipping"
            return
        else:
            self.cavity.ssa_cal_requested = (
                self.settings.ssa_cal_checkbox.isChecked()
            )
            self.cavity.auto_tune_requested = (
                self.settings.auto_tune_checkbox.isChecked()
            )
            self.cavity.cav_char_requested = (
                self.settings.cav_char_checkbox.isChecked()
            )
            self.cavity.rf_ramp_requested = (
                self.settings.rf_ramp_checkbox.isChecked()
            )

            self.cavity.trigger_setup()
