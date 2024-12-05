from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QTabWidget
from edmbutton import PyDMEDMDisplayButton
from pydm import Display
from pydm.widgets import PyDMTimePlot, PyDMSpinbox
from pydm.widgets.enum_button import PyDMEnumButton

from utils.qt import make_rainbow
from utils.sc_linac.cavity import Cavity
from utils.sc_linac.rack import Rack


class CavitySection:
    def __init__(self, cavity: Cavity):
        self.cavity = cavity
        self.tune_state: PyDMEnumButton = PyDMEnumButton(
            init_channel=cavity.tune_config_pv
        )
        self.chirp_start: PyDMSpinbox = PyDMSpinbox(
            init_channel=cavity.chirp_freq_start_pv
        )
        self.chirp_stop: PyDMSpinbox = PyDMSpinbox(
            init_channel=cavity.chirp_freq_stop_pv
        )
        self.motor_speed: PyDMSpinbox = PyDMSpinbox(
            init_channel=cavity.stepper_tuner.speed_pv
        )
        self.max_steps: PyDMSpinbox = PyDMSpinbox(
            init_channel=cavity.stepper_tuner.max_steps_pv
        )


class RackScreen:
    def __init__(self, rack: Rack):
        self.detune_plot: PyDMTimePlot = PyDMTimePlot()
        self.rack = rack
        self.populate_detune_plot()
        rack_file = f"/usr/local/lcls/tools/edm/display/llrf/rf_srf_freq_scan_rack{rack.rack_name}.edl"
        self.edm_screen: PyDMEDMDisplayButton = PyDMEDMDisplayButton(filename=rack_file)
        self.edm_screen.macros = list(rack.cavities.values())[0].edm_macro_string

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
