from functools import partial
from typing import Dict, Optional

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pyqtgraph import PlotWidget, plot

from sc_linac_physics.applications.q0 import q0_gui_utils
from sc_linac_physics.applications.q0.q0_cavity import Q0Cavity
from sc_linac_physics.applications.q0.q0_cryomodule import Q0Cryomodule
from sc_linac_physics.applications.q0.q0_gui_utils import CalibrationWorker
from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget
from sc_linac_physics.applications.q0.q0_utils import ValveParams
from sc_linac_physics.utils.qt import make_error_popup
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

Q0_CRYOMODULES: Dict[str, Q0Cryomodule] = Machine(cryomodule_class=Q0Cryomodule, cavity_class=Q0Cavity).cryomodules


class Q0GUI(Display):
    calibration_error_signal = pyqtSignal(str)
    calibration_status_signal = pyqtSignal(str)

    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        self.setWindowTitle("Q0 Measurement")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_widget = Q0MeasurementWidget()
        main_layout.addWidget(self.main_widget)

        self.selected_cm: Optional[Q0Cryomodule] = None
        self.main_widget.cm_combobox.addItems([""] + ALL_CRYOMODULES)
        self.main_widget.cm_combobox.currentTextChanged.connect(self.update_cm)

        self.main_widget.ll_avg_spinbox.valueChanged.connect(self.update_ll_buffer)

        self.main_widget.new_cal_button.clicked.connect(self.takeNewCalibration)
        self.main_widget.load_cal_button.clicked.connect(self.load_calibration)
        self.cal_option_windows: Dict[str, Display] = {}
        self.main_widget.show_cal_data_button.clicked.connect(self.show_calibration_data)

        self.main_widget.new_rf_button.clicked.connect(self.take_new_q0_measurement)
        self.main_widget.load_rf_button.clicked.connect(self.load_q0)
        self.rf_option_windows: Dict[str, Display] = {}
        self.main_widget.show_rf_button.clicked.connect(self.show_q0_data)

        self.calibration_worker: Optional[CalibrationWorker] = None
        self.q0_setup_worker: Optional[q0_gui_utils.Q0SetupWorker] = None
        self.q0_ramp_workers: Dict[int, q0_gui_utils.CavityRampWorker] = {i: None for i in range(1, 9)}
        self.q0_meas_worker: Optional[q0_gui_utils.Q0Worker] = None
        self.cryo_param_setup_worker: Optional[q0_gui_utils.CryoParamSetupWorker] = None

        self.main_widget.setup_param_button.clicked.connect(self.setup_for_cryo_params)

        self.calibration_data_plot: Optional[PlotWidget] = None
        self.calibration_data_plot_items = []
        self.calibration_fit_plot: Optional[PlotWidget] = None
        self.calibration_fit_plot_items = []

        self.q0_data_plot: PlotWidget = Optional[None]
        self.q0_data_plot_items = []
        self.q0_fit_plot: Optional[PlotWidget] = None
        self.q0_fit_plot_items = []

        self.calibration_window: Optional[Display] = None
        self.q0_window: Optional[Display] = None

        self.cav_amp_controls: Dict[int, q0_gui_utils.CavAmpControl] = {}

        for i in range(8):
            cav_amp_control = q0_gui_utils.CavAmpControl()
            self.cav_amp_controls[i + 1] = cav_amp_control
            self.main_widget.cavity_layout.addWidget(cav_amp_control.groupbox, int(i / 4), int(i % 4))

        self.main_widget.heater_setpoint_spinbox.ctrl_limit_changed = lambda *args: None
        self.main_widget.jt_setpoint_spinbox.ctrl_limit_changed = lambda *args: None

        self.main_widget.abort_rf_button.clicked.connect(self.kill_rf)
        self.main_widget.abort_cal_button.clicked.connect(self.kill_calibration)

        self.main_widget.restore_cryo_button.clicked.connect(self.restore_cryo)

    @pyqtSlot()
    def restore_cryo(self):
        self.selected_cm.restore_cryo()

    @pyqtSlot()
    def kill_rf(self):
        if self.q0_setup_worker:
            self.q0_setup_worker.cryomodule.abort_flag = True

        for worker in self.q0_ramp_workers.values():
            if worker:
                worker.cavity.abort_flag = True

        if self.q0_meas_worker:
            self.q0_meas_worker.cryomodule.abort_flag = True

    @pyqtSlot()
    def kill_calibration(self):
        if self.calibration_worker:
            self.calibration_worker.cryomodule.abort_flag = True

    @pyqtSlot(str)
    def update_cm(self, current_text):
        if not current_text:
            self.selected_cm = None
        else:
            self.selected_cm = Q0_CRYOMODULES[current_text]
            self.main_widget.perm_byte.channel = self.selected_cm.cryo_access_pv
            self.main_widget.perm_label.channel = self.selected_cm.cryo_access_pv

            self.main_widget.jt_man_button.channel = self.selected_cm.jt_manual_select_pv
            self.main_widget.jt_auto_button.channel = self.selected_cm.jt_auto_select_pv
            self.main_widget.jt_mode_label.channel = self.selected_cm.jt_mode_str_pv
            self.main_widget.jt_setpoint_spinbox.channel = self.selected_cm.jt_man_pos_setpoint_pv
            self.main_widget.jt_setpoint_readback.channel = self.selected_cm.jt_valve_readback_pv

            self.main_widget.heater_man_button.channel = self.selected_cm.heater_manual_pv
            self.main_widget.heater_seq_button.channel = self.selected_cm.heater_sequencer_pv
            self.main_widget.heater_mode_label.channel = self.selected_cm.heater_mode_string_pv
            self.main_widget.heater_setpoint_spinbox.channel = self.selected_cm.heater_setpoint_pv
            self.main_widget.heater_readback_label.channel = self.selected_cm.heater_readback_pv

            for cavity in self.selected_cm.cavities.values():
                self.cav_amp_controls[cavity.number].connect(cavity)

    @pyqtSlot()
    def show_q0_data(self):
        if not self.q0_window:
            self.q0_window = Display()
            self.q0_window.setWindowTitle("Q0 Plots")
            layout: QHBoxLayout = QHBoxLayout()
            self.q0_data_plot: PlotWidget = plot()
            self.q0_data_plot.setTitle("Q0 Data")
            self.q0_fit_plot: PlotWidget = plot()
            self.q0_fit_plot.setTitle("Heat On Calibration Curve (with adjustments)")
            layout.addWidget(self.q0_data_plot)
            layout.addWidget(self.q0_fit_plot)
            self.q0_window.setLayout(layout)

        while self.q0_data_plot_items:
            self.q0_data_plot.removeItem(self.q0_data_plot_items.pop())

        while self.q0_fit_plot_items:
            self.q0_fit_plot.removeItem(self.q0_fit_plot_items.pop())

        measurement = self.selected_cm.q0_measurement
        self.q0_data_plot_items.append(
            self.q0_data_plot.plot(
                list(measurement.rf_run.ll_data.keys()),
                list(measurement.rf_run.ll_data.values()),
            )
        )
        self.q0_data_plot_items.append(
            self.q0_data_plot.plot(
                list(measurement.heater_run.ll_data.keys()),
                list(measurement.heater_run.ll_data.values()),
            )
        )

        dll_dts = [measurement.rf_run.dll_dt, measurement.heater_run.dll_dt]
        self.q0_fit_plot_items.append(
            self.q0_fit_plot.plot(
                [measurement.heat_load, measurement.heater_run_heatload],
                dll_dts,
                pen=None,
                symbol="o",
            )
        )

        self.q0_fit_plot_items.append(
            self.q0_fit_plot.plot(
                [self.selected_cm.calibration.get_heat(dll_dt) for dll_dt in dll_dts],
                dll_dts,
            )
        )

        showDisplay(self.q0_window)

    @pyqtSlot()
    def show_calibration_data(self):
        if not self.calibration_window:
            self.calibration_window = Display()
            self.calibration_window.setWindowTitle("Calibration Plots")
            layout: QHBoxLayout = QHBoxLayout()
            self.calibration_data_plot: PlotWidget = plot()
            self.calibration_data_plot.setTitle("Calibration Data")
            self.calibration_fit_plot: PlotWidget = plot()
            self.calibration_fit_plot.setTitle("Heat vs dll/dt")
            layout.addWidget(self.calibration_data_plot)
            layout.addWidget(self.calibration_fit_plot)
            self.calibration_window.setLayout(layout)

        while self.calibration_data_plot_items:
            self.calibration_data_plot.removeItem(self.calibration_data_plot_items.pop())

        while self.calibration_fit_plot_items:
            self.calibration_fit_plot.removeItem(self.calibration_fit_plot_items.pop())

        dll_dts = []

        for heater_run in self.selected_cm.calibration.heater_runs:
            self.calibration_data_plot_items.append(
                self.calibration_data_plot.plot(list(heater_run.ll_data.keys()), list(heater_run.ll_data.values()))
            )
            dll_dts.append(heater_run.dll_dt)
            self.calibration_fit_plot_items.append(
                self.calibration_fit_plot.plot([heater_run.average_heat], [heater_run.dll_dt], pen=None, symbol="o")
            )

        heat_loads = [self.selected_cm.calibration.get_heat(dll_dt) for dll_dt in dll_dts]

        self.calibration_fit_plot_items.append(self.calibration_fit_plot.plot(heat_loads, dll_dts))

        showDisplay(self.calibration_window)

    @pyqtSlot(str)
    def handle_cal_status(self, message):
        self.main_widget.cal_status_label.setStyleSheet("color: blue;")
        self.main_widget.cal_status_label.setText(message)

    @pyqtSlot(str)
    def handle_cal_error(self, message):
        self.main_widget.cal_status_label.setStyleSheet("color: red;")
        self.main_widget.cal_status_label.setText(message)

    @pyqtSlot()
    def load_calibration(self):
        if self.selected_cm.name not in self.cal_option_windows:
            option_window: Display = Display()
            option_window.setWindowTitle(f"CM {self.selected_cm.name} Calibration Options")
            cal_options = q0_gui_utils.CalibrationOptions(self.selected_cm)
            cal_options.cal_loaded_signal.connect(self.handle_cal_status)
            cal_options.cal_loaded_signal.connect(partial(self.main_widget.rf_groupbox.setEnabled, True))
            cal_options.cal_loaded_signal.connect(partial(self.main_widget.show_cal_data_button.setEnabled, True))
            cal_options.cal_loaded_signal.connect(self.show_calibration_data)
            cal_options.cal_loaded_signal.connect(self.update_cryo_params)
            window_layout = QVBoxLayout()
            window_layout.addWidget(cal_options.main_groupbox)
            option_window.setLayout(window_layout)
            self.cal_option_windows[self.selected_cm.name] = option_window
        showDisplay(self.cal_option_windows[self.selected_cm.name])

    @pyqtSlot(str)
    def handle_rf_status(self, message):
        self.main_widget.rf_status_label.setStyleSheet("color: blue;")
        self.main_widget.rf_status_label.setText(message)

    @pyqtSlot(str)
    def handle_rf_error(self, message):
        self.main_widget.rf_status_label.setStyleSheet("color: red;")
        self.main_widget.rf_status_label.setText(message)

    @pyqtSlot()
    def load_q0(self):
        if self.selected_cm.name not in self.rf_option_windows:
            option_window: Display = Display()
            option_window.setWindowTitle(f"CM {self.selected_cm.name} RF Measurement Options")
            rf_options = q0_gui_utils.Q0Options(self.selected_cm)
            rf_options.q0_loaded_signal.connect(self.handle_rf_status)
            rf_options.q0_loaded_signal.connect(self.show_q0_data)
            window_layout = QVBoxLayout()
            window_layout.addWidget(rf_options.main_groupbox)
            option_window.setLayout(window_layout)
            self.rf_option_windows[self.selected_cm.name] = option_window
        showDisplay(self.rf_option_windows[self.selected_cm.name])

    @pyqtSlot(int)
    def update_ll_buffer(self, value):
        if self.selected_cm:
            self.selected_cm.ll_buffer_size = value

    @pyqtSlot()
    def update_cryo_params(self):
        self.main_widget.ref_heat_spinbox.setValue(self.selected_cm.valveParams.refHeatLoadDes)
        self.main_widget.jt_pos_spinbox.setValue(self.selected_cm.valveParams.refValvePos)

    @pyqtSlot()
    def setup_for_cryo_params(self):
        self.cryo_param_setup_worker = q0_gui_utils.CryoParamSetupWorker(
            self.selected_cm,
            heater_setpoint=self.main_widget.ref_heat_spinbox.value(),
            jt_setpoint=self.main_widget.jt_pos_spinbox.value(),
        )
        self.cryo_param_setup_worker.error.connect(partial(make_error_popup, "Cryo Setup Error"))
        self.cryo_param_setup_worker.start()

    @pyqtSlot()
    def takeNewCalibration(self):
        self.selected_cm.valveParams = ValveParams(
            refHeatLoadDes=self.main_widget.ref_heat_spinbox.value(),
            refValvePos=self.main_widget.jt_pos_spinbox.value(),
            refHeatLoadAct=self.main_widget.ref_heat_spinbox.value(),
        )

        self.calibration_worker = CalibrationWorker(
            cryomodule=self.selected_cm,
            jt_search_start=None,
            jt_search_end=None,
            desired_ll=self.main_widget.ll_start_spinbox.value(),
            heat_start=self.main_widget.start_heat_spinbox.value(),
            heat_end=self.main_widget.end_heat_spinbox.value(),
            num_cal_steps=self.main_widget.num_cal_points_spinbox.value(),
            ll_drop=self.main_widget.ll_drop_spinbox.value(),
        )
        self.calibration_worker.status.connect(self.handle_cal_status)
        self.calibration_worker.finished.connect(self.handle_cal_status)
        self.calibration_worker.error.connect(self.handle_cal_error)
        self.calibration_worker.finished.connect(partial(self.main_widget.rf_groupbox.setEnabled, True))
        self.calibration_worker.finished.connect(partial(self.main_widget.show_cal_data_button.setEnabled, True))
        self.calibration_worker.start()

    @property
    def desiredCavityAmplitudes(self):
        amplitudes = {}
        for cav_num, cav_amp_control in self.cav_amp_controls.items():
            if cav_amp_control.groupbox.isChecked():
                amplitudes[cav_num] = cav_amp_control.desAmpSpinbox.value()
            else:
                amplitudes[cav_num] = 0
        print(f"Cavity amplitudes: {amplitudes}")
        return amplitudes

    @pyqtSlot()
    def ramp_cavities(self):
        des_amps = self.desiredCavityAmplitudes

        for cav_num, des_amp in des_amps.items():
            cavity = self.selected_cm.cavities[cav_num]
            ramp_worker = q0_gui_utils.CavityRampWorker(cavity, des_amp)
            self.q0_ramp_workers[cav_num] = ramp_worker
            ramp_worker.finished.connect(cavity.mark_ready)
            ramp_worker.start()

        self.q0_meas_worker = q0_gui_utils.Q0Worker(
            cryomodule=self.selected_cm,
            jt_search_start=None,
            jt_search_end=None,
            desired_ll=self.main_widget.ll_start_spinbox.value(),
            ll_drop=self.main_widget.ll_drop_spinbox.value(),
            desired_amplitudes=self.desiredCavityAmplitudes,
        )
        self.q0_meas_worker.error.connect(partial(make_error_popup, "Q0 Measurement Error"))
        self.q0_meas_worker.error.connect(self.selected_cm.shut_off)
        self.q0_meas_worker.finished.connect(self.handle_rf_status)
        self.q0_meas_worker.status.connect(self.handle_rf_status)
        self.q0_meas_worker.start()

    @pyqtSlot()
    def take_new_q0_measurement(self):
        self.selected_cm.valveParams = ValveParams(
            refHeatLoadDes=self.main_widget.ref_heat_spinbox.value(),
            refValvePos=self.main_widget.jt_pos_spinbox.value(),
            refHeatLoadAct=self.main_widget.ref_heat_spinbox.value(),
        )

        self.q0_setup_worker = q0_gui_utils.Q0SetupWorker(
            cryomodule=self.selected_cm,
            jt_search_start=None,
            jt_search_end=None,
            desired_ll=self.main_widget.ll_start_spinbox.value(),
            ll_drop=self.main_widget.ll_drop_spinbox.value(),
            desired_amplitudes=self.desiredCavityAmplitudes,
        )
        self.q0_setup_worker.status.connect(self.handle_rf_status)
        self.q0_setup_worker.finished.connect(self.handle_rf_status)
        self.q0_setup_worker.finished.connect(self.ramp_cavities)
        self.q0_setup_worker.error.connect(self.handle_rf_error)
        self.q0_setup_worker.start()
