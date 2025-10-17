import dataclasses
from typing import List, Optional, Dict

from PyQt5.QtWidgets import (
    QPushButton,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QGridLayout,
)
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display
from pydm.widgets import PyDMLabel

from sc_linac_physics.applications.auto_setup.backend.setup_linac import SetupLinac
from sc_linac_physics.applications.auto_setup.backend.setup_machine import SETUP_MACHINE
from sc_linac_physics.applications.auto_setup.frontend.gui_cryomodule import (
    GUICryomodule,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings


@dataclasses.dataclass
class GUILinac:
    name: str
    idx: int
    cryomodule_names: List[str]
    settings: Settings
    parent: Display

    def __post_init__(self):
        self._linac_object: Optional[SetupLinac] = None

        self.setup_button: QPushButton = QPushButton(f"Set Up {self.name}")
        self.setup_button.clicked.connect(self.trigger_setup)

        self.abort_button: QPushButton = QPushButton(f"Abort Action for {self.name}")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.request_stop)

        self.acon_button: QPushButton = QPushButton(f"Capture all {self.name} ACON")
        self.acon_button.clicked.connect(self.capture_acon)

        self.aact_pv = f"ACCL:L{self.idx}B:1:AACTMEANSUM" if self.name != "L1BHL" else "ACCL:L1B:1:HL_AACTMEANSUM"

        self.readback_label: PyDMLabel = PyDMLabel(init_channel=self.aact_pv)
        self.readback_label.alarmSensitiveBorder = True
        self.readback_label.alarmSensitiveContent = True
        self.readback_label.showUnits = True

        self.cryomodules: List[GUICryomodule] = []
        self.cm_tab_widget: QTabWidget = QTabWidget()
        self.gui_cryomodules: Dict[str, GUICryomodule] = {}

        for cm_name in self.cryomodule_names:
            self.add_cm_tab(cm_name)

    @property
    def linac_object(self):
        if not self._linac_object:
            self._linac_object: SetupLinac = SETUP_MACHINE.linacs[self.idx]
        return self._linac_object

    def request_stop(self):
        self.linac_object.trigger_abort()

    def trigger_shutdown(self):
        self.linac_object.trigger_shutdown()

    def trigger_setup(self):
        self.linac_object.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
        self.linac_object.auto_tune_requested = self.settings.auto_tune_checkbox.isChecked()
        self.linac_object.cav_char_requested = self.settings.cav_char_checkbox.isChecked()
        self.linac_object.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
        self.linac_object.trigger_start()

    def capture_acon(self):
        for gui_cm in self.gui_cryomodules.values():
            gui_cm.capture_acon()

    def add_cm_tab(self, cm_name: str):
        page: QWidget = QWidget()
        vlayout: QVBoxLayout = QVBoxLayout()
        page.setLayout(vlayout)
        self.cm_tab_widget.addTab(page, f"CM{cm_name}")

        gui_cryomodule = GUICryomodule(linac_idx=self.idx, name=cm_name, settings=self.settings, parent=self.parent)
        self.gui_cryomodules[cm_name] = gui_cryomodule
        hlayout: QHBoxLayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(QLabel(f"CM{cm_name} Amplitude:"))
        hlayout.addWidget(gui_cryomodule.readback_label)
        hlayout.addWidget(gui_cryomodule.setup_button)
        hlayout.addWidget(gui_cryomodule.turn_off_button)
        hlayout.addWidget(gui_cryomodule.abort_button)
        hlayout.addWidget(gui_cryomodule.acon_button)
        hlayout.addStretch()

        vlayout.addLayout(hlayout)

        groupbox: QGroupBox = QGroupBox()
        all_cav_layout: QGridLayout = QGridLayout()
        groupbox.setLayout(all_cav_layout)
        vlayout.addWidget(groupbox)
        for cav_num in range(1, 9):
            cav_groupbox: QGroupBox = QGroupBox(f"CM{cm_name} Cavity {cav_num}")
            cav_groupbox.setStyleSheet("QGroupBox { font-weight: bold; } ")

            cav_vlayout: QVBoxLayout = QVBoxLayout()
            cav_groupbox.setLayout(cav_vlayout)
            cav_widgets = gui_cryomodule.gui_cavities[cav_num]
            cav_amp_hlayout: QHBoxLayout = QHBoxLayout()
            cav_amp_hlayout.addStretch()
            cav_amp_hlayout.addWidget(QLabel("ACON: "))
            cav_amp_hlayout.addWidget(cav_widgets.acon_label)
            cav_amp_hlayout.addWidget(QLabel("AACT: "))
            cav_amp_hlayout.addWidget(cav_widgets.aact_readback_label)
            cav_amp_hlayout.addStretch()
            cav_button_hlayout: QHBoxLayout = QHBoxLayout()
            cav_button_hlayout.addStretch()
            cav_button_hlayout.addWidget(cav_widgets.setup_button)
            cav_button_hlayout.addWidget(cav_widgets.shutdown_button)
            cav_button_hlayout.addWidget(cav_widgets.abort_button)
            cav_button_hlayout.addWidget(cav_widgets.expert_screen_button)
            cav_button_hlayout.addStretch()

            cav_vlayout.addLayout(cav_amp_hlayout)
            cav_vlayout.addLayout(cav_button_hlayout)
            cav_vlayout.addWidget(cav_widgets.status_label)
            cav_vlayout.addWidget(cav_widgets.progress_bar)
            cav_vlayout.addWidget(cav_widgets.note_label)
            all_cav_layout.addWidget(cav_groupbox, 0 if cav_num in range(1, 5) else 1, (cav_num - 1) % 4)
