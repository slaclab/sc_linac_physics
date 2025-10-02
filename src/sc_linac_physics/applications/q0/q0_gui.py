from functools import partial
from typing import Dict, Optional

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QMessageBox
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pyqtgraph import PlotWidget, plot

from sc_linac_physics.applications.q0 import q0_gui_utils
from sc_linac_physics.applications.q0.q0_cavity import Q0Cavity
from sc_linac_physics.applications.q0.q0_cryomodule import Q0Cryomodule
from sc_linac_physics.applications.q0.q0_gui_utils import CalibrationWorker
from sc_linac_physics.applications.q0.q0_measurement_widget import Q0MeasurementWidget
from sc_linac_physics.applications.q0.q0_utils import ValveParams
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

Q0_CRYOMODULES: Dict[str, Q0Cryomodule] = Machine(cryomodule_class=Q0Cryomodule, cavity_class=Q0Cavity).cryomodules


def make_non_blocking_error_popup(title, message: str):
    """Non-blocking error popup for GUI applications."""
    popup = QMessageBox()
    popup.setIcon(QMessageBox.Critical)
    popup.setWindowTitle(title)
    popup.setText(message)
    popup.show()  # Use show() instead of exec() to avoid blocking
    return popup


class Q0GUI(Display):
    calibration_error_signal = pyqtSignal(str)
    calibration_status_signal = pyqtSignal(str)

    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        self._ramp_remaining = None
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

        self.q0_data_plot: Optional[PlotWidget] = None
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

    def _require_cm(self) -> bool:
        """Check if a cryomodule is selected. Show non-blocking error if not."""
        if not self.selected_cm:
            make_non_blocking_error_popup("No Cryomodule Selected", "Please select a cryomodule first.")
            return False
        return True

    @pyqtSlot()
    def restore_cryo(self):
        """Restore cryogenic conditions."""
        if not self._require_cm():
            return

        try:
            self.selected_cm.restore_cryo()
        except Exception as e:
            make_non_blocking_error_popup("Restore Cryo Error", f"Failed to restore cryo: {str(e)}")

    @pyqtSlot()
    def kill_rf(self):
        """Kill all RF-related processes."""
        if self.q0_setup_worker and self.q0_setup_worker.cryomodule:
            self.q0_setup_worker.cryomodule.abort_flag = True

        for worker in self.q0_ramp_workers.values():
            if worker and worker.cavity:
                worker.cavity.abort_flag = True

        if self.q0_meas_worker and self.q0_meas_worker.cryomodule:
            self.q0_meas_worker.cryomodule.abort_flag = True

    @pyqtSlot()
    def kill_calibration(self):
        """Kill calibration process."""
        if self.calibration_worker and self.calibration_worker.cryomodule:
            self.calibration_worker.cryomodule.abort_flag = True

    @pyqtSlot(str)
    def update_cm(self, current_text):
        """Update selected cryomodule."""
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
        """Show Q0 measurement data plots."""
        if not self._require_cm():
            return

        if not self.selected_cm.q0_measurement:
            make_non_blocking_error_popup("No Q0 Data", "No Q0 measurement data available.")
            return

        try:
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
        except Exception as e:
            make_non_blocking_error_popup("Plot Error", f"Failed to show Q0 data: {str(e)}")

    @pyqtSlot()
    def show_calibration_data(self):
        """Show calibration data plots."""
        if not self._require_cm():
            return

        if not self.selected_cm.calibration:
            make_non_blocking_error_popup("No Calibration Data", "No calibration data available.")
            return

        try:
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
        except Exception as e:
            make_non_blocking_error_popup("Plot Error", f"Failed to show calibration data: {str(e)}")

    @pyqtSlot(str)
    def handle_cal_status(self, message):
        """Handle calibration status messages."""
        self.main_widget.cal_status_label.setStyleSheet("color: blue;")
        self.main_widget.cal_status_label.setText(message)

    @pyqtSlot(str)
    def handle_cal_error(self, message):
        """Handle calibration error messages."""
        self.main_widget.cal_status_label.setStyleSheet("color: red;")
        self.main_widget.cal_status_label.setText(message)

    @pyqtSlot()
    def load_calibration(self):
        """Load existing calibration data."""
        if not self._require_cm():
            return

        try:
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
        except Exception as e:
            make_non_blocking_error_popup("Load Calibration Error", f"Failed to load calibration: {str(e)}")

    @pyqtSlot(str)
    def handle_rf_status(self, message):
        """Handle RF status messages."""
        self.main_widget.rf_status_label.setStyleSheet("color: blue;")
        self.main_widget.rf_status_label.setText(message)

    @pyqtSlot(str)
    def handle_rf_error(self, message):
        """Handle RF error messages."""
        self.main_widget.rf_status_label.setStyleSheet("color: red;")
        self.main_widget.rf_status_label.setText(message)

    @pyqtSlot()
    def load_q0(self):
        """Load existing Q0 measurement data."""
        if not self._require_cm():
            return

        try:
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
        except Exception as e:
            make_non_blocking_error_popup("Load Q0 Error", f"Failed to load Q0 data: {str(e)}")

    @pyqtSlot(int)
    def update_ll_buffer(self, value):
        """Update liquid level buffer size."""
        if self.selected_cm:
            self.selected_cm.ll_buffer_size = value

    @pyqtSlot()
    def update_cryo_params(self):
        """Update cryogenic parameters display."""
        if self.selected_cm and self.selected_cm.valveParams:
            self.main_widget.ref_heat_spinbox.setValue(self.selected_cm.valveParams.refHeatLoadDes)
            self.main_widget.jt_pos_spinbox.setValue(self.selected_cm.valveParams.refValvePos)

    @pyqtSlot()
    def setup_for_cryo_params(self):
        """Setup cryogenic parameters."""
        if not self._require_cm():
            return

        try:
            self.cryo_param_setup_worker = q0_gui_utils.CryoParamSetupWorker(
                self.selected_cm,
                heater_setpoint=self.main_widget.ref_heat_spinbox.value(),
                jt_setpoint=self.main_widget.jt_pos_spinbox.value(),
            )
            self.cryo_param_setup_worker.error.connect(
                lambda msg: make_non_blocking_error_popup("Cryo Setup Error", msg)
            )
            self.cryo_param_setup_worker.start()
        except Exception as e:
            make_non_blocking_error_popup("Setup Error", f"Failed to setup cryo params: {str(e)}")

    @pyqtSlot()
    def takeNewCalibration(self):
        """Take a new calibration measurement."""
        if not self._require_cm():
            return

        try:
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
        except Exception as e:
            make_non_blocking_error_popup("Calibration Error", f"Failed to start calibration: {str(e)}")

    @property
    def desiredCavityAmplitudes(self):
        """Get desired cavity amplitudes from UI controls."""
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
        """Ramp cavities to desired amplitudes."""
        if not self._require_cm():
            return

        try:
            des_amps = self.desiredCavityAmplitudes

            self._ramp_remaining = sum(1 for a in des_amps.values() if a > 0)
            if self._ramp_remaining == 0:
                self._start_q0_worker()
                return

            for cav_num, des_amp in des_amps.items():
                if des_amp <= 0:
                    continue
                cavity = self.selected_cm.cavities[cav_num]
                ramp_worker = q0_gui_utils.CavityRampWorker(cavity, des_amp)
                self.q0_ramp_workers[cav_num] = ramp_worker
                ramp_worker.finished.connect(cavity.mark_ready)
                ramp_worker.finished.connect(self._on_ramp_finished)
                ramp_worker.error.connect(
                    lambda msg, num=cav_num: make_non_blocking_error_popup(f"Cavity {num} Ramp Error", msg)
                )
                ramp_worker.finished.connect(partial(self._clear_ramp_worker, cav_num))
                ramp_worker.start()
        except Exception as e:
            make_non_blocking_error_popup("Ramp Error", f"Failed to ramp cavities: {str(e)}")

    @pyqtSlot()
    def _on_ramp_finished(self):
        """Handle ramp completion."""
        self._ramp_remaining -= 1
        if self._ramp_remaining <= 0:
            self._start_q0_worker()

    def _start_q0_worker(self):
        """Start Q0 measurement worker."""
        try:
            self.q0_meas_worker = q0_gui_utils.Q0Worker(
                cryomodule=self.selected_cm,
                jt_search_start=None,
                jt_search_end=None,
                desired_ll=self.main_widget.ll_start_spinbox.value(),
                ll_drop=self.main_widget.ll_drop_spinbox.value(),
                desired_amplitudes=self.desiredCavityAmplitudes,
            )
            self.q0_meas_worker.error.connect(lambda msg: make_non_blocking_error_popup("Q0 Measurement Error", msg))
            self.q0_meas_worker.error.connect(self.selected_cm.shut_off)
            self.q0_meas_worker.status.connect(self.handle_rf_status)
            self.q0_meas_worker.finished.connect(self.handle_rf_status)
            self.q0_meas_worker.finished.connect(self._clear_q0_meas_worker)
            self.q0_meas_worker.start()
        except Exception as e:
            make_non_blocking_error_popup("Q0 Worker Error", f"Failed to start Q0 measurement: {str(e)}")

    def _clear_ramp_worker(self, cav_num):
        """Clear ramp worker reference."""
        self.q0_ramp_workers[cav_num] = None

    def _clear_q0_meas_worker(self, *_):
        """Clear Q0 measurement worker reference."""
        self.q0_meas_worker = None

    @pyqtSlot()
    def take_new_q0_measurement(self):
        """Take a new Q0 measurement."""
        if not self._require_cm():
            return

        try:
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
        except Exception as e:
            make_non_blocking_error_popup("Q0 Setup Error", f"Failed to setup Q0 measurement: {str(e)}")
