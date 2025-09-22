import json
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, Optional

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
)
from epics import caget, caput
from pydm.widgets import PyDMLabel
from requests import ConnectTimeout
from urllib3.exceptions import ConnectTimeoutError

from sc_linac_physics.applications.q0 import q0_utils
from sc_linac_physics.applications.q0.q0_cavity import Q0Cavity
from sc_linac_physics.applications.q0.q0_cryomodule import Q0Cryomodule
from sc_linac_physics.utils.qt import Worker, get_dimensions
from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError

DEFAULT_LL_DROP = 4
MIN_STARTING_LL = 93
DEFAULT_START_HEAT = 40
DEFAULT_END_HEAT = 112
DEFAULT_NUM_CAL_POINTS = 5
DEFAULT_POST_RF_HEAT = 24
DEFAULT_JT_START_DELTA = timedelta(hours=24)
DEFAULT_LL_BUFFER_SIZE = 10


class CryoParamSetupWorker(Worker):
    def __init__(
        self,
        cryomodule: Q0Cryomodule,
        heater_setpoint=q0_utils.MINIMUM_HEATLOAD,
        jt_setpoint=35,
    ):
        super().__init__()
        self.cryomodule = cryomodule
        self.heater_setpoint = heater_setpoint
        self.jt_setpoint = jt_setpoint

    def run(self) -> None:
        self.status.emit("Checking for required cryo permissions")
        if caget(self.cryomodule.cryo_access_pv) != q0_utils.CRYO_ACCESS_VALUE:
            self.error.emit("Required cryo permissions not granted - call cryo ops")
            return

        self.cryomodule.heater_power = self.heater_setpoint
        self.cryomodule.jt_position = self.jt_setpoint
        caput(self.cryomodule.jt_auto_select_pv, 1, wait=True)
        self.finished.emit("Cryo setup for new reference parameters in ~1 hour")


class CryoParamWorker(Worker):
    def __init__(
        self, cryomodule: Q0Cryomodule, start_time: datetime, end_time: datetime
    ):
        super().__init__()
        self.cryomodule: Q0Cryomodule = cryomodule
        self.start_time: datetime = start_time
        self.end_time: datetime = end_time

    def run(self) -> None:
        try:
            self.status.emit("Getting new reference cryo parameters")
            self.cryomodule.getRefValveParams(
                start_time=self.start_time, end_time=self.end_time
            )
            self.finished.emit("New reference cryo params loaded")
        except (CavityAbortError, q0_utils.Q0AbortError) as e:
            self.error.emit(str(e))


class RFWorker(Worker):
    def __init__(
        self,
        cryomodule: Q0Cryomodule,
        jt_search_start: Optional[datetime],
        jt_search_end: Optional[datetime],
        desired_ll,
        ll_drop,
        desired_amplitudes,
    ):
        super().__init__()
        self.cryomodule = cryomodule
        self.jt_search_end = jt_search_end
        self.jt_search_start = jt_search_start
        self.desired_ll = desired_ll
        self.ll_drop = ll_drop
        self.desired_amplitudes = desired_amplitudes


class Q0Worker(RFWorker):
    def run(self) -> None:
        if caget(self.cryomodule.cryo_access_pv) != q0_utils.CRYO_ACCESS_VALUE:
            self.error.emit("Required cryo permissions not granted - call cryo ops")
            return

        try:
            self.status.emit("Taking new Q0 Measurement")
            self.cryomodule.takeNewQ0Measurement(
                desiredAmplitudes=self.desired_amplitudes,
                desired_ll=self.desired_ll,
                ll_drop=self.ll_drop,
            )
            self.finished.emit(f"Recorded Q0: {self.cryomodule.q0_measurement.q0:.2e}")
        except (TypeError, CavityAbortError, q0_utils.Q0AbortError) as e:
            self.error.emit(str(e))


class Q0SetupWorker(RFWorker):
    def run(self) -> None:
        if caget(self.cryomodule.cryo_access_pv) != q0_utils.CRYO_ACCESS_VALUE:
            self.error.emit("Required cryo permissions not granted - call cryo ops")
            return

        try:
            self.status.emit(f"CM{self.cryomodule.name} setting up for RF measurement")
            self.cryomodule.setup_for_q0(
                desiredAmplitudes=self.desired_amplitudes,
                desired_ll=self.desired_ll,
                jt_search_start=self.jt_search_start,
                jt_search_end=self.jt_search_end,
            )
            self.finished.emit(f"CM{self.cryomodule.name} ready for cavity ramp up")
        except (CavityAbortError, q0_utils.Q0AbortError) as e:
            self.error.emit(str(e))


class CavityRampWorker(Worker):
    def __init__(self, cavity: Q0Cavity, des_amp: float):
        super().__init__()
        self.cavity: Q0Cavity = cavity
        self.des_amp = des_amp

    def run(self) -> None:
        try:
            self.status.emit(f"Ramping Cavity {self.cavity.number} to {self.des_amp}")
            self.cavity.setup_rf(self.des_amp)
            self.finished.emit(
                f"Cavity {self.cavity.number} ramped up to {self.des_amp}"
            )
        except (CavityAbortError, q0_utils.Q0AbortError) as e:
            self.error.emit(str(e))


class CalibrationWorker(Worker):
    def __init__(
        self,
        cryomodule: Q0Cryomodule,
        jt_search_start: Optional[datetime],
        jt_search_end: Optional[datetime],
        desired_ll,
        num_cal_steps,
        ll_drop,
        heat_start,
        heat_end,
    ):
        super().__init__()
        self.cryomodule = cryomodule
        self.jt_search_end = jt_search_end
        self.jt_search_start = jt_search_start
        self.desired_ll = desired_ll
        self.heat_start = heat_start
        self.heat_end = heat_end
        self.num_cal_steps = num_cal_steps
        self.ll_drop = ll_drop

    def run(self) -> None:
        if caget(self.cryomodule.cryo_access_pv) != q0_utils.CRYO_ACCESS_VALUE:
            self.error.emit("Required cryo permissions not granted - call cryo ops")
            return
        try:
            self.status.emit("Taking new calibration")
            self.cryomodule.take_new_calibration(
                jt_search_start=self.jt_search_start,
                jt_search_end=self.jt_search_end,
                desired_ll=self.desired_ll,
                num_cal_steps=self.num_cal_steps,
                ll_drop=self.ll_drop,
                heat_start=self.heat_start,
                heat_end=self.heat_end,
            )
            self.finished.emit("Calibration Loaded")
        except (
            ConnectTimeoutError,
            ConnectTimeout,
            q0_utils.CryoError,
            q0_utils.Q0AbortError,
        ) as e:
            self.error.emit(str(e))


class CavAmpControl:
    def __init__(self):
        self.groupbox: QGroupBox = QGroupBox()
        self.groupbox.setCheckable(True)
        horLayout: QHBoxLayout = QHBoxLayout()
        horLayout.addStretch()

        self.desAmpSpinbox: QDoubleSpinBox = QDoubleSpinBox()

        horLayout.addWidget(self.desAmpSpinbox)
        horLayout.addWidget(QLabel("MV"))
        self.aact_label: PyDMLabel = PyDMLabel()
        self.aact_label.showUnits = True
        self.aact_label.alarmSensitiveContent = True
        self.aact_label.alarmSensitiveBorder = True
        horLayout.addWidget(self.aact_label)
        horLayout.addStretch()

        self.groupbox.setLayout(horLayout)

    def connect(self, cavity: Q0Cavity):
        self.groupbox.setTitle(f"Cavity {cavity.number}")
        if not cavity.is_online:
            self.groupbox.setChecked(False)
            self.desAmpSpinbox.setRange(0, 0)
        else:
            self.groupbox.setChecked(True)
            self.desAmpSpinbox.setValue(min(16.6, cavity.ades_max))
            self.desAmpSpinbox.setRange(0, cavity.ades_max)
        self.aact_label.channel = cavity.aact_pv


class Q0Options(QObject):
    q0_loaded_signal = pyqtSignal(str)

    def __init__(self, cryomodule: Q0Cryomodule):
        super().__init__()
        self.cryomodule = cryomodule
        self.main_groupbox: QGroupBox = QGroupBox(
            f"Q0 Measurements for CM{cryomodule.name}"
        )
        grid_layout: QGridLayout = QGridLayout()
        self.main_groupbox.setLayout(grid_layout)

        with open(cryomodule.q0_idx_file, "r+") as f:
            q0_measurements: Dict = json.load(f)
            timestamps = list(q0_measurements.keys())
            col_count = get_dimensions(timestamps)
            for idx, time_stamp in enumerate(timestamps):
                cav_amps = q0_measurements[time_stamp]["Cavity Amplitudes"]
                radio_button: QRadioButton = QRadioButton(
                    f"{time_stamp}: \n{json.dumps(cav_amps, indent=4)}"
                )
                grid_layout.addWidget(
                    radio_button, int(idx / col_count), idx % col_count
                )
                radio_button.clicked.connect(partial(self.load_q0, time_stamp))

    @pyqtSlot()
    def load_q0(self, timestamp: str):
        self.cryomodule.load_q0_measurement(time_stamp=timestamp)
        self.q0_loaded_signal.emit(
            f"Loaded q0 measurement for"
            f" CM{self.cryomodule.name} from {timestamp}"
            f" with q0 {self.cryomodule.q0_measurement.q0:.2e}"
        )


class CalibrationOptions(QObject):
    cal_loaded_signal = pyqtSignal(str)

    def __init__(self, cryomodule: Q0Cryomodule):
        super().__init__()
        self.cryomodule = cryomodule
        self.main_groupbox: QGroupBox = QGroupBox(
            f"Calibrations for CM{cryomodule.name}"
        )
        grid_layout: QGridLayout = QGridLayout()
        self.main_groupbox.setLayout(grid_layout)

        with open(cryomodule.calib_idx_file, "r+") as f:
            calibrations: Dict = json.load(f)
            col_count = get_dimensions(calibrations)

            for idx, time_stamp in enumerate(calibrations.keys()):
                radio_button: QRadioButton = QRadioButton(time_stamp)
                grid_layout.addWidget(
                    radio_button, int(idx / col_count), idx % col_count
                )
                radio_button.clicked.connect(partial(self.load_calibration, time_stamp))

    @pyqtSlot()
    def load_calibration(self, timestamp: str):
        self.cryomodule.load_calibration(time_stamp=timestamp)
        self.cal_loaded_signal.emit(
            f"Loaded calibration for"
            f" CM{self.cryomodule.name} from {timestamp}"
            f" with slope {self.cryomodule.calibration.dLLdt_dheat:.2e}"
        )
