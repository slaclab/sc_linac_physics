import dataclasses
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from edmbutton import PyDMEDMDisplayButton
from epics import camonitor
from pydm import Display
from pydm.widgets import PyDMLabel
from pydm.widgets.analog_indicator import PyDMAnalogIndicator
from pydm.widgets.display_format import DisplayFormat

from lcls_tools.common.controls.pyepics.utils import PV
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from lcls_tools.superconducting import sc_linac_utils
from setup_linac import SETUP_MACHINE, SetupCavity, SetupCryomodule, SetupLinac


@dataclasses.dataclass
class Settings:
    ssa_cal_checkbox: QCheckBox
    auto_tune_checkbox: QCheckBox
    cav_char_checkbox: QCheckBox
    rf_ramp_checkbox: QCheckBox


@dataclasses.dataclass
class GUICavity:
    number: int
    prefix: str
    cm: str
    settings: Settings
    parent: Display
    
    def __post_init__(self):
        self._cavity: Optional[SetupCavity] = None
        self.setup_button = QPushButton(f"Set Up")
        
        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.request_stop)
        self.shutdown_button: QPushButton = QPushButton(f"Turn Off")
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
        self.acon_label: PyDMLabel = PyDMLabel(init_channel=self.prefix + "ACON")
        self.acon_label.alarmSensitiveContent = True
        self.acon_label.alarmSensitiveBorder = True
        self.acon_label.showUnits = True
        self.acon_label.precisionFromPV = False
        self.acon_label.precision = 2
        
        self.status_label: PyDMLabel = PyDMLabel(init_channel=self.cavity.status_msg_pv)
        
        # status_msg_pv is an ndarray of char codes and seeing the display format
        # makes is display correctly (i.e. not as [ 1 2 3 4]
        self.status_label.displayFormat = DisplayFormat.String
        
        self.status_label.setAlignment(Qt.AlignHCenter)
        self.status_label.setWordWrap(True)
        self.status_label.alarmSensitiveBorder = True
        self.status_label.alarmSensitiveContent = True
        
        self.progress_bar: PyDMAnalogIndicator = PyDMAnalogIndicator(
                init_channel=self.cavity.progress_pv
        )
        self.progress_bar.backgroundSizeRate = 0.2
        self.progress_bar.sizePolicy().setVerticalPolicy(QSizePolicy.Maximum)
        
        self.expert_screen_button: PyDMEDMDisplayButton = PyDMEDMDisplayButton()
        self.expert_screen_button.filenames = ["$EDM/llrf/rf_srf_cavity_main.edl"]
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
        self.cavity.request_abort()
    
    @property
    def cavity(self) -> SetupCavity:
        if not self._cavity:
            self._cavity: SetupCavity = SETUP_MACHINE.cryomodules[self.cm].cavities[
                self.number
            ]
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
            self.cavity.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
            self.cavity.auto_tune_requested = (
                self.settings.auto_tune_checkbox.isChecked()
            )
            self.cavity.cav_char_requested = self.settings.cav_char_checkbox.isChecked()
            self.cavity.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
            
            self.cavity.trigger_setup()


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


@dataclasses.dataclass
class Linac:
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
        
        self.aact_pv = (
            f"ACCL:L{self.idx}B:1:AACTMEANSUM"
            if self.name != "L1BHL"
            else "ACCL:L1B:1:HL_AACTMEANSUM"
        )
        
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
        self.linac_object.request_abort()
    
    def trigger_shutdown(self):
        self.linac_object.trigger_shutdown()
    
    def trigger_setup(self):
        self.linac_object.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
        self.linac_object.auto_tune_requested = (
            self.settings.auto_tune_checkbox.isChecked()
        )
        self.linac_object.cav_char_requested = (
            self.settings.cav_char_checkbox.isChecked()
        )
        self.linac_object.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
        self.linac_object.trigger_setup()
    
    def capture_acon(self):
        for gui_cm in self.gui_cryomodules.values():
            gui_cm.capture_acon()
    
    def add_cm_tab(self, cm_name: str):
        page: QWidget = QWidget()
        vlayout: QVBoxLayout = QVBoxLayout()
        page.setLayout(vlayout)
        self.cm_tab_widget.addTab(page, f"CM{cm_name}")
        
        gui_cryomodule = GUICryomodule(
                linac_idx=self.idx, name=cm_name, settings=self.settings, parent=self.parent
        )
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
            all_cav_layout.addWidget(
                    cav_groupbox, 0 if cav_num in range(1, 5) else 1, (cav_num - 1) % 4
            )


class SetupGUI(Display):
    def ui_filename(self):
        return "setup_gui.ui"
    
    def __init__(self, parent=None, args=None):
        super(SetupGUI, self).__init__(parent=parent, args=args)
        
        self.ui.machine_abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.ui.machine_abort_button.clicked.connect(self.request_stop)
        self.ui.machine_setup_button.clicked.connect(self.trigger_setup)
        self.ui.machine_shutdown_button.clicked.connect(self.trigger_shutdown)
        
        self.settings = Settings(
                ssa_cal_checkbox=self.ui.ssa_cal_checkbox,
                auto_tune_checkbox=self.ui.autotune_checkbox,
                cav_char_checkbox=self.ui.cav_char_checkbox,
                rf_ramp_checkbox=self.ui.rf_ramp_checkbox,
        )
        self.linac_widgets: List[Linac] = []
        for linac_idx in range(0, 4):
            self.linac_widgets.append(
                    Linac(
                            f"L{linac_idx}B",
                            linac_idx,
                            sc_linac_utils.LINAC_TUPLES[linac_idx][1],
                            settings=self.settings,
                            parent=self,
                    )
            )
        
        self.linac_widgets.insert(
                2,
                Linac(
                        "L1BHL", 1, sc_linac_utils.L1BHL, settings=self.settings, parent=self
                ),
        )
        
        self.linac_aact_pvs: List[PV] = [
            PV(f"ACCL:L{i}B:1:AACTMEANSUM") for i in range(4)
        ]
        self.update_readback()
        
        linac_tab_widget: QTabWidget = self.ui.tabWidget_linac
        
        for linac in self.linac_widgets:
            page: QWidget = QWidget()
            vlayout: QVBoxLayout = QVBoxLayout()
            page.setLayout(vlayout)
            linac_tab_widget.addTab(page, linac.name)
            
            hlayout: QHBoxLayout = QHBoxLayout()
            hlayout.addStretch()
            hlayout.addWidget(QLabel(f"{linac.name} Amplitude:"))
            hlayout.addWidget(linac.readback_label)
            hlayout.addWidget(linac.setup_button)
            hlayout.addWidget(linac.abort_button)
            hlayout.addWidget(linac.acon_button)
            hlayout.addStretch()
            
            vlayout.addLayout(hlayout)
            vlayout.addWidget(linac.cm_tab_widget)
            camonitor(linac.aact_pv, callback=self.update_readback)
    
    def update_readback(self, **kwargs):
        readback = 0
        for linac_aact_pv in self.linac_aact_pvs:
            readback += linac_aact_pv.get()
        self.ui.machine_readback_label.setText(f"{readback:.2f} MV")
    
    def trigger_setup(self):
        SETUP_MACHINE.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
        SETUP_MACHINE.auto_tune_requested = self.settings.auto_tune_checkbox.isChecked()
        SETUP_MACHINE.cav_char_requested = self.settings.cav_char_checkbox.isChecked()
        SETUP_MACHINE.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
        SETUP_MACHINE.trigger_setup()
    
    @staticmethod
    def trigger_shutdown():
        SETUP_MACHINE.trigger_shutdown()
    
    @staticmethod
    def request_stop():
        SETUP_MACHINE.request_abort()
