from typing import Dict

from PyQt5.QtCore import QObject, QThreadPool, pyqtSlot
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from lcls_tools.common.frontend.display.util import WorkerSignals
from lcls_tools.superconducting.sc_linac_utils import ALL_CRYOMODULES, StepperAbortError
from pydm import Display
from pydm.widgets import PyDMLabel

from park_linac import ParkCavity
from park_utils import ColdWorker


class CavityObject:
    def __init__(self, cavity: ParkCavity):
        self.cavity: ParkCavity = cavity

        self.label = QLabel("Ready")
        self.signals = WorkerSignals(self.label)

        readbacks: QFormLayout = QFormLayout()

        self.detune_readback: PyDMLabel = PyDMLabel(
            init_channel=self.cavity.detune_best_pv
        )
        self.detune_readback.alarmSensitiveContent = True
        self.detune_readback.showUnits = True

        cold_steps: PyDMLabel = PyDMLabel(
            init_channel=self.cavity.stepper_tuner.nsteps_cold_pv
        )
        cold_steps.alarmSensitiveContent = True
        cold_steps.showUnits = True

        park_steps: PyDMLabel = PyDMLabel(
            init_channel=self.cavity.stepper_tuner.nsteps_park_pv
        )
        park_steps.alarmSensitiveContent = True
        park_steps.showUnits = True

        freq_cold: PyDMLabel = PyDMLabel(init_channel=self.cavity.df_cold_pv)
        freq_cold.alarmSensitiveContent = True
        freq_cold.showUnits = True

        step_readback: PyDMLabel = PyDMLabel(
            init_channel=self.cavity.stepper_tuner.step_signed_pv
        )
        step_readback.alarmSensitiveContent = True
        step_readback.showUnits = True

        config_label = PyDMLabel(init_channel=self.cavity.tune_config_pv)
        config_label.alarmSensitiveContent = True
        config_label.showUnits = True

        readbacks.addRow("Live Detune", self.detune_readback)
        readbacks.addRow("Steps to Cold Landing", cold_steps)

        # TODO reintroduce when parking is necessary
        # readbacks.addRow("Steps to Park", park_steps)

        readbacks.addRow("Cold Landing Detune", freq_cold)
        readbacks.addRow("Live Total Step Count", step_readback)
        readbacks.addRow("Tune Config", config_label)

        self.cold_button: QPushButton = QPushButton("Move to Cold Landing")
        self.cold_button.clicked.connect(self.move_to_cold_landing)
        self.cold_button.setToolTip(
            "If 'Cold Landing Detune' is nonzero,"
            " it will autotune to that frequency. "
            "Else, it will blindly move 'Steps to Park' steps"
        )

        self.park_button: QPushButton = QPushButton("Park")
        self.park_button.clicked.connect(self.park)
        self.park_button.setToolTip(
            "This will move the tuner until the detune is 10kHz"
        )

        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.clicked.connect(self.kill_worker)

        self.count_signed_steps: QCheckBox = QCheckBox(
            "Continue (don't reset signed steps)"
        )
        self.count_signed_steps.setChecked(False)
        self.count_signed_steps.setToolTip(
            "If checked, program will not reset "
            "the step count and will instead "
            "subtract 'Live Total Step Count' from 'Steps to Park'"
        )

        self.groupbox = QGroupBox(f"Cavity {num}")
        self.vlayout = QVBoxLayout()
        self.vlayout.addWidget(self.count_signed_steps)
        self.vlayout.addWidget(self.cold_button)

        # TODO reintroduce when parking is necessary
        # self.vlayout.addWidget(self.park_button)

        self.vlayout.addLayout(readbacks)
        self.vlayout.addWidget(self.label)
        self.vlayout.addWidget(self.abort_button)

        self.groupbox.setLayout(self.vlayout)

        self.cold_worker: ColdWorker = ColdWorker(
            cavity=self.cavity,
            status_label=self.label,
            park_button=self.park_button,
            cold_button=self.cold_button,
            count_signed_steps=self.count_signed_steps,
            freq_radiobutton=self.parent.ui.freq_radiobutton,
        )

    def disable_buttons(self):
        self.park_button.setEnabled(False)
        self.cold_button.setEnabled(False)

    def enable_buttons(self):
        self.park_button.setEnabled(True)
        self.cold_button.setEnabled(True)

    def kill_worker(self):
        print("Aborting stepper move request")
        self.cavity.stepper_tuner.abort()
        self.cavity.stepper_tuner.abort_flag = True
        self.cavity.abort_flag = True

    @pyqtSlot()
    def move_to_cold_landing(self):
        self.parent.threadpool.start(self.cold_worker)

    @pyqtSlot()
    def park(self):
        self.disable_buttons()
        self.signals.status.emit("Parking")
        try:
            self.cavity.park(self.count_signed_steps.isChecked())
            self.signals.finished.emit("Cavity Parked")
            self.enable_buttons()
        except StepperAbortError as e:
            self.cavity.stepper_tuner.abort_flag = False
            self.signals.error.emit(str(e))
            self.enable_buttons()


class CryomoduleObject(QObject):
    def __init__(self, name: str, parent):
        super().__init__(parent=parent)
        self.cav_objects: Dict[int, CavityObject] = {}

        self.go_button: QPushButton = QPushButton(
            f"Move all CM{name} cavities to Cold Landing"
        )
        self.go_button.clicked.connect(self.move_cavities_to_cold)

        self.page: QWidget = QWidget()
        self.groupbox: QGroupBox = QGroupBox()
        all_cav_layout: QGridLayout = QGridLayout()
        self.groupbox.setLayout(all_cav_layout)

        for i in range(1, 9):
            cav_obj = CavityObject(cm=name, num=i, parent=parent)
            self.cav_objects[i] = cav_obj
            all_cav_layout.addWidget(
                cav_obj.groupbox, 0 if i in range(1, 5) else 1, (i - 1) % 4
            )

        vlayout: QVBoxLayout = QVBoxLayout()
        vlayout.addWidget(self.go_button)
        vlayout.addWidget(self.groupbox)

        self.page.setLayout(vlayout)

    @pyqtSlot()
    def move_cavities_to_cold(self):
        for cav_obj in self.cav_objects.values():
            cav_obj.move_to_cold_landing()


class ParkGUI(Display):
    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        self.threadpool: QThreadPool = QThreadPool()

        for cm_name in ALL_CRYOMODULES:
            print(f"Creating {cm_name} tab")
            cm_obj = CryomoduleObject(name=cm_name, parent=self)
            self.ui.tabWidget.addTab(cm_obj.page, cm_name)

    def ui_filename(self):
        return "park_gui.ui"
