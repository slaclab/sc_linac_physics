from typing import List

from PyQt5.QtCore import QThreadPool
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QTabWidget,
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from edmbutton import PyDMEDMDisplayButton
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display
from pydm.widgets import PyDMTimePlot, PyDMSpinbox, PyDMEnumComboBox
from pydm.widgets.timeplot import updateMode
from qtpy import QtCore

from applications.tuning.tune_cavity import TuneCavity
from applications.tuning.tune_stepper import TuneStepper
from applications.tuning.tune_utils import ColdWorker
from utils.qt import make_rainbow, CollapsibleGroupBox
from utils.sc_linac.linac import Machine
from utils.sc_linac.linac_utils import ALL_CRYOMODULES
from utils.sc_linac.rack import Rack


class LabeledSpinbox:
    def __init__(self, init_channel: str):
        self.spinbox: PyDMSpinbox = PyDMSpinbox(init_channel=init_channel)
        self.spinbox.showStepExponent = False
        self.label = QLabel(init_channel.split(":")[-1])
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.spinbox)


class CavitySection:
    def __init__(self, cavity: TuneCavity, parent=None):
        self.parent = parent
        self.cavity: TuneCavity = cavity
        self.tune_state: PyDMEnumComboBox = PyDMEnumComboBox(
            init_channel=cavity.tune_config_pv
        )

        self.chirp_start: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.chirp_freq_start_pv
        )

        self.chirp_stop: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.chirp_freq_stop_pv
        )

        self.motor_speed: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.stepper_tuner.speed_pv
        )

        self.max_steps: LabeledSpinbox = LabeledSpinbox(
            init_channel=cavity.stepper_tuner.max_steps_pv
        )

        self.groupbox = QGroupBox(cavity.__str__().split()[-2] + " " + cavity.__str__().split()[-1])
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)
        spinbox_layout = QGridLayout()
        layout.addWidget(self.tune_state)

        spinbox_layout.addLayout(self.chirp_start.layout, 0, 0)
        spinbox_layout.addLayout(self.chirp_stop.layout, 0, 1)
        spinbox_layout.addLayout(self.motor_speed.layout, 1, 0)
        spinbox_layout.addLayout(self.max_steps.layout, 1, 1)

        expert_options = CollapsibleGroupBox(
            f"Show {cavity} expert options", spinbox_layout
        )
        layout.addWidget(expert_options)

        button_layout = QHBoxLayout()

        self.cold_button: QPushButton = QPushButton("Move to Cold Landing")
        self.cold_button.clicked.connect(self.move_to_cold_landing)
        self.status_label = QLabel("Ready")
        self.cold_worker: ColdWorker = ColdWorker(
            cavity=self.cavity,
            cold_button=self.cold_button,
            status_label=self.status_label,
        )
        button_layout.addWidget(self.cold_button)
        layout.addWidget(self.status_label)

        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.clicked.connect(self.abort)
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        button_layout.addWidget(self.abort_button)
        layout.addLayout(button_layout)

    def abort(self):
        print("Aborting stepper move request")
        self.cavity.stepper_tuner.abort()
        self.cavity.stepper_tuner.abort_flag = True
        self.cavity.abort_flag = True

    def move_to_cold_landing(self):
        self.parent.threadpool.start(self.cold_worker)


class RackScreen:
    def __init__(self, rack: Rack, parent=None):
        self.detune_plot: PyDMTimePlot = PyDMTimePlot()
        self.detune_plot.setTimeSpan(3600)
        self.detune_plot.updateMode = updateMode.AtFixedRate
        self.detune_plot.setPlotTitle("Cavity Detunes")
        self.rack = rack
        self.populate_detune_plot()
        self.detune_plot.showLegend = True
        rack_file = f"/usr/local/lcls/tools/edm/display/llrf/rf_srf_freq_scan_rack{rack.rack_name}.edl"
        self.edm_screen: PyDMEDMDisplayButton = PyDMEDMDisplayButton(filename=rack_file)
        self.edm_screen.setText("EDM Rack Screen")
        self.edm_screen.macros = list(rack.cavities.values())[0].edm_macro_string
        self.groupbox = QGroupBox(f"{rack}")
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)

        cav_layout = QGridLayout()
        self.cav_sections: List[CavitySection] = []

        for idx, cavity in enumerate(list(rack.cavities.values())):
            cav_section = CavitySection(cavity, parent=parent)
            self.cav_sections.append(cav_section)
            cav_layout.addWidget(cav_section.groupbox, int(idx / 2), idx % 2)

        layout.addLayout(cav_layout)

        button_layout = QHBoxLayout()

        button_layout.addWidget(self.edm_screen)

        self.cold_button: QPushButton = QPushButton("Move Cavities to Cold Landing")
        self.cold_button.clicked.connect(self.move_cavities_to_cold)
        button_layout.addWidget(self.cold_button)

        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.abort)
        button_layout.addWidget(self.abort_button)

        layout.addLayout(button_layout)
        layout.addWidget(self.detune_plot)

    def move_cavities_to_cold(self):
        for cav_section in self.cav_sections:
            cav_section.move_to_cold_landing()

    def abort(self):
        for cav_section in self.cav_sections:
            cav_section.abort()

    def populate_detune_plot(self):
        detune_pvs = []
        cold_pvs = []
        for cavity in self.rack.cavities.values():
            detune_pvs.append(cavity.detune_best_pv)
            cold_pvs.append(cavity.df_cold_pv)
        colors = make_rainbow(len(detune_pvs) * 2)
        for idx, (detune_pv, cold_pv) in enumerate(zip(detune_pvs, cold_pvs)):
            if self.rack.rack_name == "A":
                r, g, b, alpha = colors[idx]
            else:
                r, g, b, alpha = colors[idx + int(len(detune_pvs) / 2)]
            rga_color = QColor(r, g, b, alpha)
            self.detune_plot.addYChannel(
                y_channel=detune_pv,
                useArchiveData=True,
                color=rga_color,
                yAxisName="Detune (Hz)",
            )
            rga_color.setAlpha(127)
            self.detune_plot.addYChannel(
                y_channel=cold_pv,
                useArchiveData=True,
                color=rga_color,
                yAxisName="Detune (Hz)",
                lineStyle=QtCore.Qt.DashLine,
            )


class Tuner(Display):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRF Tuner")
        self.tab_widget: QTabWidget = QTabWidget()
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.tab_widget)
        self.machine = Machine(cavity_class=TuneCavity, stepper_class=TuneStepper)

        self.threadpool: QThreadPool = QThreadPool()

        for cm_name in ALL_CRYOMODULES:
            cm = self.machine.cryomodules[cm_name]
            page = QWidget()
            page_layout = QHBoxLayout()
            page.setLayout(page_layout)
            page_layout.addWidget(RackScreen(cm.rack_a, parent=self).groupbox)
            page_layout.addWidget(RackScreen(cm.rack_b, parent=self).groupbox)
            self.tab_widget.addTab(page, cm_name)
