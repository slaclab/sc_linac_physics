from typing import Dict, Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QComboBox,
    QVBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QGridLayout,
    QDoubleSpinBox,
)
from epics import camonitor, camonitor_clear
from lcls_tools.common.frontend.plotting.util import (
    WaveformPlotParams,
    TimePlotParams,
    TimePlotUpdater,
    WaveformPlotUpdater,
)
from pydm import Display
from pydm.widgets import PyDMWaveformPlot, PyDMTimePlot
from qtpy.QtCore import Signal

from applications.quench_processing.quench_linac import (
    QUENCH_MACHINE,
    QuenchCavity,
    QuenchCryomodule,
)
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.decarad import Decarad
from utils.sc_linac.linac_utils import ALL_CRYOMODULES
from utils.widgets.rf_controls import RFControls


class QuenchGUI(Display):
    quench_signal = Signal(int)

    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        self.setWindowTitle("Quench Processing")
        self.main_vlayout: QVBoxLayout = QVBoxLayout()
        self.setLayout(self.main_vlayout)

        self.cm_combobox: QComboBox = QComboBox()
        self.cav_combobox: QComboBox = QComboBox()
        self.decarad_combobox: QComboBox = QComboBox()

        self.add_selectors()

        self.cm_combobox.addItems(ALL_CRYOMODULES)
        self.cav_combobox.addItems(map(str, range(1, 9)))
        self.decarad_combobox.addItems(["1", "2"])

        widget_hlayout: QHBoxLayout = QHBoxLayout()
        self.controls_vlayout: QVBoxLayout = QVBoxLayout()
        plot_vlayout: QVBoxLayout = QVBoxLayout()

        widget_hlayout.addLayout(self.controls_vlayout)
        widget_hlayout.addLayout(plot_vlayout)

        self.main_vlayout.addLayout(widget_hlayout)

        self.rf_controls = RFControls()
        self.start_button: QPushButton = QPushButton("Start Processing")
        self.abort_button: QPushButton = QPushButton("Abort Processing")

        self.start_amp_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.step_size_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.stop_amp_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.step_time_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.create_processing_spinboxes()

        self.add_controls()

        self.current_cm: Optional[QuenchCryomodule] = None
        self.current_cav: Optional[QuenchCavity] = None

        self.cav_waveform_plot = PyDMWaveformPlot()
        self.cav_waveform_plot.title = "Most Recent Fault Waveform (Not Real Time)"
        self.cav_waveform_plot.showLegend = True

        self.waveform_plot_params: Dict[str, WaveformPlotParams] = {
            "FAULT_WAVEFORMS": WaveformPlotParams(plot=self.cav_waveform_plot)
        }

        plot_vlayout.addWidget(self.cav_waveform_plot)

        self.amp_rad_timeplot = PyDMTimePlot()
        self.amp_rad_timeplot.title = "Amplitude & Radiation"
        self.amp_rad_timeplot.showLegend = True

        self.timeplot_params: Dict[str, TimePlotParams] = {
            "LIVE_SIGNALS": TimePlotParams(plot=self.amp_rad_timeplot)
        }

        plot_vlayout.addWidget(self.amp_rad_timeplot)

        self.timeplot_updater: TimePlotUpdater = TimePlotUpdater(self.timeplot_params)
        self.waveform_updater: WaveformPlotUpdater = WaveformPlotUpdater(
            self.waveform_plot_params
        )

        self.cm_combobox.currentIndexChanged.connect(self.update_cm)
        self.cav_combobox.currentIndexChanged.connect(self.update_cm)
        self.decarad_combobox.currentIndexChanged.connect(self.update_decarad)

        self.decarads: Dict[str, Decarad] = {"1": Decarad(1), "2": Decarad(2)}
        self.current_decarad: Optional[Decarad] = None

        self.update_cm()
        self.update_decarad()

    def add_controls(self):
        processing_controls_groupbox: QGroupBox = QGroupBox("Processing Controls")
        processing_controls_layout: QGridLayout = QGridLayout()
        processing_controls_groupbox.setLayout(processing_controls_layout)
        start_amp_row = 0
        processing_controls_layout.addWidget(
            QLabel("Starting Amplitude (MV):"), start_amp_row, 0
        )
        processing_controls_layout.addWidget(self.start_amp_spinbox, start_amp_row, 1)
        stop_amp_row = 1
        processing_controls_layout.addWidget(
            QLabel("Ending Amplitude (MV):"), stop_amp_row, 0
        )
        processing_controls_layout.addWidget(self.stop_amp_spinbox, stop_amp_row, 1)
        step_row = 2
        processing_controls_layout.addWidget(QLabel("Step Size (MV):"))
        processing_controls_layout.addWidget(self.step_size_spinbox, step_row, 1)
        time_row = 3
        processing_controls_layout.addWidget(
            QLabel("Time Between Steps (s):"), time_row, 0
        )
        processing_controls_layout.addWidget(self.step_time_spinbox, time_row, 1)
        self.controls_vlayout.addWidget(self.rf_controls.rf_control_groupbox)
        self.controls_vlayout.addWidget(processing_controls_groupbox)
        self.controls_vlayout.addWidget(self.start_button)
        self.controls_vlayout.addWidget(self.abort_button)

    def add_selectors(self):
        input_groupbox: QGroupBox = QGroupBox()
        input_hlayout: QHBoxLayout = QHBoxLayout()
        input_groupbox.setLayout(input_hlayout)
        input_hlayout.addStretch()
        input_hlayout.addWidget(QLabel("Cryomodule:"))
        input_hlayout.addWidget(self.cm_combobox)
        input_hlayout.addWidget(QLabel("Cavity:"))
        input_hlayout.addWidget(self.cav_combobox)
        input_hlayout.addWidget(QLabel("Decarad:"))
        input_hlayout.addWidget(self.decarad_combobox)
        input_hlayout.addStretch()
        self.main_vlayout.addWidget(input_groupbox)

    def create_processing_spinboxes(self):
        self.start_amp_spinbox.setMinimum(0)
        self.start_amp_spinbox.setMaximum(21)
        self.start_amp_spinbox.setValue(5)

        self.step_size_spinbox.setMinimum(0)
        self.step_size_spinbox.setValue(0.2)

        self.stop_amp_spinbox.setMinimum(0)
        self.stop_amp_spinbox.setMaximum(21)
        self.stop_amp_spinbox.setValue(21)

        self.step_time_spinbox.setMinimum(0.1)
        self.step_time_spinbox.setValue(30)

    @staticmethod
    def clear_connections(signal: Signal):
        try:
            signal.disconnect()
        except TypeError:
            print(f"No connections to remove for {signal}")
            pass

    def clear_all_connections(self):
        for signal in [
            self.rf_controls.ssa_on_button.clicked,
            self.rf_controls.ssa_off_button.clicked,
            self.rf_controls.rf_on_button.clicked,
            self.rf_controls.rf_off_button.clicked,
            self.start_button.clicked,
            self.abort_button.clicked,
        ]:
            self.clear_connections(signal)

    def update_decarad(self):
        self.current_decarad = self.decarads[self.decarad_combobox.currentText()]
        channels = [(self.current_cav.aact_pv, None)]
        for head in self.current_decarad.heads.values():
            channels.append((head.dose_rate_pv, None))
        self.timeplot_updater.updatePlot("LIVE_SIGNALS", channels)

    def update_cm(self):
        if self.current_cav:
            camonitor_clear(self.current_cav.quench_latch_pv)

        self.clear_all_connections()

        self.current_cm: Cryomodule = QUENCH_MACHINE.cryomodules[
            self.cm_combobox.currentText()
        ]
        self.current_cav: QuenchCavity = self.current_cm.cavities[
            int(self.cav_combobox.currentText())
        ]

        self.rf_controls.ssa_on_button.clicked.connect(self.current_cav.ssa.turn_on)
        self.rf_controls.ssa_off_button.clicked.connect(self.current_cav.ssa.turn_off)
        self.rf_controls.ssa_readback_label.channel = self.current_cav.ssa.status_pv

        self.rf_controls.rf_mode_combobox.channel = self.current_cav.rf_mode_ctrl_pv
        self.rf_controls.rf_mode_readback_label.channel = self.current_cav.rf_mode_pv
        self.rf_controls.rf_on_button.clicked.connect(self.current_cav.turn_on)
        self.rf_controls.rf_off_button.clicked.connect(self.current_cav.turn_off)
        self.rf_controls.rf_status_readback_label.channel = self.current_cav.rf_state_pv

        self.rf_controls.ades_spinbox.channel = self.current_cav.ades_pv
        self.rf_controls.aact_readback_label.channel = self.current_cav.aact_pv
        self.rf_controls.srf_max_spinbox.channel = self.current_cav.srf_max_pv
        self.rf_controls.srf_max_readback_label.channel = self.current_cav.srf_max_pv

        self.start_button.clicked.connect(self.current_cav.quench_process)
        self.abort_button.clicked.connect(self.current_cav.request_abort)

        self.timeplot_updater.updatePlot(
            "LIVE_SIGNALS", [(self.current_cav.aact_pv, None)]
        )
        self.waveform_updater.updatePlot(
            "FAULT_WAVEFORMS",
            [
                (
                    self.current_cav.fault_time_waveform_pv,
                    self.current_cav.decay_ref_pv,
                ),
                (
                    self.current_cav.fault_time_waveform_pv,
                    self.current_cav.fault_waveform_pv,
                ),
            ],
        )

        camonitor(
            self.current_cav.quench_latch_pv,
            callback=self.quench_callback,
            writer=print,
        )

    def quench_callback(self, value, **kwargs):
        self.quench_signal.emit(value)
