from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QTabWidget,
    QGroupBox,
    QVBoxLayout,
    QGridLayout,
    QWidget,
    QHBoxLayout,
    QLabel,
)
from edmbutton import PyDMEDMDisplayButton
from pydm import Display
from pydm.widgets import PyDMTimePlot, PyDMSpinbox, PyDMEnumComboBox
from pydm.widgets.timeplot import updateMode

from utils.qt import make_rainbow
from utils.sc_linac.cavity import Cavity
from utils.sc_linac.linac import MACHINE
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
    def __init__(self, cavity: Cavity):
        self.cavity = cavity
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

        self.groupbox = QGroupBox(f"{cavity}")
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)
        spinbox_layout = QGridLayout()
        layout.addWidget(self.tune_state)
        layout.addLayout(spinbox_layout)
        spinbox_layout.addLayout(self.chirp_start.layout, 0, 0)
        spinbox_layout.addLayout(self.chirp_stop.layout, 0, 1)
        spinbox_layout.addLayout(self.motor_speed.layout, 1, 0)
        spinbox_layout.addLayout(self.max_steps.layout, 1, 1)


class RackScreen:
    def __init__(self, rack: Rack):
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

        for idx, cavity in enumerate(list(rack.cavities.values())):
            cav_layout.addWidget(CavitySection(cavity).groupbox, int(idx / 2), idx % 2)

        layout.addLayout(cav_layout)

        layout.addWidget(self.edm_screen)
        layout.addWidget(self.detune_plot)

    def populate_detune_plot(self):
        detune_pvs = []
        for cavity in self.rack.cavities.values():
            detune_pvs.append(cavity.detune_chirp_pv)
        colors = make_rainbow(len(detune_pvs))
        for idx, detune_pv in enumerate(detune_pvs):
            r, g, b, alpha = colors[idx]
            rga_color = QColor(r, g, b, alpha)
            self.detune_plot.addYChannel(
                y_channel=detune_pv,
                useArchiveData=True,
                color=rga_color,
                yAxisName="Detune (Hz)",
            )


class HLTuner(Display):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRF HL Tuner")
        self.tab_widget: QTabWidget = QTabWidget()
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.tab_widget)

        for cm_name in ["H1", "H2"]:
            cm = MACHINE.cryomodules[cm_name]
            page = QWidget()
            page_layout = QHBoxLayout()
            page.setLayout(page_layout)
            page_layout.addWidget(RackScreen(cm.rack_a).groupbox)
            page_layout.addWidget(RackScreen(cm.rack_b).groupbox)
            self.tab_widget.addTab(page, cm_name)
