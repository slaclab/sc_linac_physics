from typing import Dict, Optional

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QColor
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
from lcls_tools.common.frontend.plotting.util import (
    WaveformPlotParams,
    TimePlotParams,
    WaveformPlotUpdater,
)
from pydm import Display
from pydm.widgets import PyDMWaveformPlot, PyDMTimePlot, PyDMLabel
from pydm.widgets.timeplot import updateMode
from qtpy.QtCore import Signal

from applications.quench_processing.quench_linac import (
    QUENCH_MACHINE,
    QuenchCavity,
    QuenchCryomodule,
)
from applications.quench_processing.quench_worker import QuenchWorker
from utils.qt import RFControls, make_rainbow
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.decarad import Decarad
from utils.sc_linac.linac_utils import ALL_CRYOMODULES


class QuenchGUI(Display):
    quench_signal = Signal(int)

    def __init__(self):
        super().__init__()
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
        self.status_label: QLabel = QLabel()

        self.start_amp_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.step_size_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.stop_amp_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.step_time_spinbox: QDoubleSpinBox = QDoubleSpinBox()

        self.decarad_on_button: QPushButton = QPushButton("Decarad On")
        self.decarad_off_button: QPushButton = QPushButton("Decarad Off")
        self.decarad_status_readback: PyDMLabel = PyDMLabel()
        self.decarad_voltage_readback: PyDMLabel = PyDMLabel()

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
        self.amp_rad_timeplot.setTimeSpan(60 * 60)
        self.amp_rad_timeplot.updateMode = updateMode.AtFixedRate

        self.timeplot_params: Dict[str, TimePlotParams] = {
            "LIVE_SIGNALS": TimePlotParams(plot=self.amp_rad_timeplot)
        }

        plot_vlayout.addWidget(self.amp_rad_timeplot)

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

        self.quench_worker: Optional[QuenchWorker] = None

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

        decarad_controls_groupbox: QGroupBox = QGroupBox("Decarad Controls")
        decarad_controls_layout: QHBoxLayout = QHBoxLayout()
        decarad_controls_groupbox.setLayout(decarad_controls_layout)
        decarad_controls_layout.addWidget(self.decarad_on_button)
        decarad_controls_layout.addWidget(self.decarad_off_button)
        decarad_controls_layout.addWidget(self.decarad_status_readback)
        decarad_controls_layout.addWidget(self.decarad_voltage_readback)

        self.controls_vlayout.addWidget(self.rf_controls.rf_control_groupbox)
        self.controls_vlayout.addWidget(decarad_controls_groupbox)
        self.controls_vlayout.addWidget(processing_controls_groupbox)
        self.controls_vlayout.addWidget(self.start_button)
        self.controls_vlayout.addWidget(self.abort_button)
        self.controls_vlayout.addWidget(self.status_label)

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
        self.start_amp_spinbox.setMaximum(22)
        self.start_amp_spinbox.setValue(5)

        self.step_size_spinbox.setMinimum(0)
        self.step_size_spinbox.setValue(0.2)

        self.stop_amp_spinbox.setMinimum(0)
        self.stop_amp_spinbox.setMaximum(22)
        self.stop_amp_spinbox.setValue(21)

        self.step_time_spinbox.setMinimum(0.1)
        self.step_time_spinbox.setValue(30)

    @pyqtSlot(str)
    def handle_status(self, message):
        self.status_label.setStyleSheet("color: blue;")
        self.status_label.setText(message)

    @pyqtSlot(str)
    def handle_error(self, message):
        self.status_label.setStyleSheet("color: red;")
        self.status_label.setText(message)
        self.start_button.setEnabled(True)

    @pyqtSlot(str)
    def handle_finished(self, message):
        self.status_label.setStyleSheet("color: green;")
        self.status_label.setText(message)
        self.start_button.setEnabled(True)

    def process(self):
        self.start_button.setEnabled(False)
        self.current_cav.decarad = self.current_decarad
        self.make_quench_worker()
        self.quench_worker.start()

    def make_quench_worker(self):
        self.quench_worker = QuenchWorker(
            cavity=self.current_cav,
            start_amp=self.start_amp_spinbox.value(),
            end_amp=self.stop_amp_spinbox.value(),
            step_time=self.step_time_spinbox.value(),
            step_size=self.step_size_spinbox.value(),
        )
        self.quench_worker.status.connect(self.handle_status)
        self.quench_worker.error.connect(self.handle_error)
        self.quench_worker.finished.connect(self.handle_finished)

    @staticmethod
    def clear_connections(signal: Signal):
        try:
            signal.disconnect()
        except TypeError:
            pass

    def clear_all_connections(self):
        for signal in [
            self.rf_controls.ssa_on_button.clicked,
            self.rf_controls.ssa_off_button.clicked,
            self.rf_controls.rf_on_button.clicked,
            self.rf_controls.rf_off_button.clicked,
            self.start_button.clicked,
            self.abort_button.clicked,
            self.decarad_on_button.clicked,
            self.decarad_off_button.clicked,
        ]:
            self.clear_connections(signal)

    def update_timeplot(self):
        self.amp_rad_timeplot.clearCurves()

        self.current_decarad = self.decarads[self.decarad_combobox.currentText()]
        self.current_cm: Cryomodule = QUENCH_MACHINE.cryomodules[
            self.cm_combobox.currentText()
        ]
        self.current_cav: QuenchCavity = self.current_cm.cavities[
            int(self.cav_combobox.currentText())
        ]

        channels = [self.current_cav.aact_pv]
        for head in self.current_decarad.heads.values():
            channels.append(head.raw_dose_rate_pv)

        colors = make_rainbow(len(channels))

        for idx, channel in enumerate(channels):
            r, g, b, alpha = colors[idx]
            rga_color = QColor(r, g, b, alpha)
            # TODO make amp line thicker
            self.amp_rad_timeplot.addYChannel(
                y_channel=channel,
                useArchiveData=True,
                color=rga_color,
                yAxisName=(
                    "Amplitude" if channel == self.current_cav.aact_pv else "Radiation"
                ),
            )

    def update_decarad(self):
        self.current_decarad = self.decarads[self.decarad_combobox.currentText()]

        self.update_timeplot()

        self.clear_connections(self.decarad_on_button.clicked)
        self.clear_connections(self.decarad_off_button.clicked)

        self.decarad_on_button.clicked.connect(self.current_decarad.turn_on)
        self.decarad_off_button.clicked.connect(self.current_decarad.turn_off)
        self.decarad_status_readback.channel = self.current_decarad.power_status_pv
        self.decarad_voltage_readback.channel = self.current_decarad.voltage_readback_pv

    def update_cm(self):
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

        self.start_button.clicked.connect(self.process)
        self.abort_button.clicked.connect(self.current_cav.request_abort)

        self.update_timeplot()
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
