from typing import List

from PyQt5.QtCore import QObject
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
from pydm.widgets import PyDMTimePlot, PyDMSpinbox, PyDMEnumComboBox, PyDMLabel
from pydm.widgets.timeplot import updateMode
from qtpy import QtCore

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_rack import TuneRack
from sc_linac_physics.applications.tuning.tune_stepper import TuneStepper
from sc_linac_physics.utils.qt import make_rainbow, CollapsibleGroupBox
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES
from sc_linac_physics.utils.sc_linac.rack import Rack

TUNE_MACHINE = Machine(cavity_class=TuneCavity, rack_class=TuneRack, stepper_class=TuneStepper)


class LabeledSpinbox:
    """A labeled spinbox widget combining a PyDMSpinbox with a descriptive label.

    Attributes:
        spinbox: The PyDMSpinbox widget for numerical input
        label: QLabel showing the channel name
        layout: Horizontal layout containing the label and spinbox
    """

    def __init__(self, init_channel: str) -> None:
        """Initialize a new labeled spinbox.

        Args:
            init_channel: The PV channel to connect to
        """
        self.spinbox: PyDMSpinbox = PyDMSpinbox(init_channel=init_channel)
        self.spinbox.showStepExponent = False
        self.label: QLabel = QLabel(init_channel.split(":")[-1])
        self.layout: QHBoxLayout = QHBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.spinbox)


class CavitySection(QObject):
    """GUI section for controlling and monitoring a single cavity.

    This class provides controls for cavity tuning, including chirp frequency settings,
    motor control, and cold landing functionality.

    Attributes:
        cavity: The cavity being controlled
        tune_state: Combo box for selecting tuning configuration
        chirp_start: Start frequency control for chirp
        chirp_stop: Stop frequency control for chirp
        motor_speed: Stepper motor speed control
        max_steps: Maximum steps control
        status_label: Label showing current operation status
    """

    def __init__(self, cavity: TuneCavity, parent: QObject | None = None) -> None:
        """Initialize a new cavity control section.

        Args:
            cavity: The cavity to control
            parent: Parent QObject for Qt ownership
        """
        super().__init__(parent)
        self.parent: QObject = parent
        self.cavity: TuneCavity = cavity
        self.tune_state: PyDMEnumComboBox = PyDMEnumComboBox(init_channel=cavity.tune_config_pv)

        self.chirp_start: LabeledSpinbox = LabeledSpinbox(init_channel=cavity.chirp_freq_start_pv)

        self.chirp_stop: LabeledSpinbox = LabeledSpinbox(init_channel=cavity.chirp_freq_stop_pv)

        self.motor_speed: LabeledSpinbox = LabeledSpinbox(init_channel=cavity.stepper_tuner.speed_pv)

        self.max_steps: LabeledSpinbox = LabeledSpinbox(init_channel=cavity.stepper_tuner.max_steps_pv)

        self.groupbox = QGroupBox(f"Cavity {cavity.number}")
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)
        spinbox_layout = QGridLayout()
        layout.addWidget(self.tune_state)

        spinbox_layout.addLayout(self.chirp_start.layout, 0, 0)
        spinbox_layout.addLayout(self.chirp_stop.layout, 0, 1)
        spinbox_layout.addLayout(self.motor_speed.layout, 1, 0)
        spinbox_layout.addLayout(self.max_steps.layout, 1, 1)

        expert_options = CollapsibleGroupBox(f"Show {cavity} expert options", spinbox_layout)
        layout.addWidget(expert_options)

        button_layout = QHBoxLayout()

        self.cold_button: QPushButton = QPushButton("Move to Cold Landing")
        self.cold_button.clicked.connect(self.cavity.trigger_start)
        self.status_label = PyDMLabel(init_channel=cavity.status_msg_pv)

        button_layout.addWidget(self.cold_button)
        layout.addWidget(self.status_label)

        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.clicked.connect(self.cavity.trigger_abort)
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        button_layout.addWidget(self.abort_button)
        layout.addLayout(button_layout)


class RackScreen(QObject):
    def __init__(self, rack: Rack, parent=None):
        super().__init__(parent)
        self.detune_plot: PyDMTimePlot = PyDMTimePlot()
        self.detune_plot.setTimeSpan(3600)
        self.detune_plot.updateMode = updateMode.AtFixedRate
        self.detune_plot.setPlotTitle("Cavity Detunes")
        self.rack: TuneRack = rack
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
        self.cold_button.clicked.connect(self.rack.trigger_start)
        button_layout.addWidget(self.cold_button)

        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.abort_button.clicked.connect(self.rack.trigger_abort)
        button_layout.addWidget(self.abort_button)

        layout.addLayout(button_layout)
        layout.addWidget(self.detune_plot)

    def populate_detune_plot(self):
        detune_pvs = []
        cold_pvs = []
        for cavity in self.rack.cavities.values():
            detune_pvs.append(cavity.detune_best_pv)
            cold_pvs.append(cavity.df_cold_pv)
        colors = make_rainbow(len(detune_pvs))

        for idx, (detune_pv, cold_pv) in enumerate(zip(detune_pvs, cold_pvs)):
            r, g, b, a = colors[idx]
            rga_color = QColor(r, g, b, a)

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
    """Main display for the SRF Tuner application.

    This is the top-level window that contains tabs for each cryomodule
    and their associated cavity tuning controls.

    Attributes:
        tab_widget: Widget containing tabs for each cryomodule
        machine: The machine instance containing all cavities
    """

    def __init__(self) -> None:
        """Initialize the tuner display."""
        super().__init__()
        self.setWindowTitle("SRF Tuner")
        self.tab_widget: QTabWidget = QTabWidget()
        layout: QVBoxLayout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.tab_widget)
        self.machine: Machine = Machine(cavity_class=TuneCavity, stepper_class=TuneStepper, rack_class=TuneRack)

        for cm_name in ALL_CRYOMODULES:
            cm = self.machine.cryomodules[cm_name]
            page = QWidget()
            page_layout = QHBoxLayout()
            page.setLayout(page_layout)
            page_layout.addWidget(RackScreen(cm.rack_a, parent=self).groupbox)
            page_layout.addWidget(RackScreen(cm.rack_b, parent=self).groupbox)
            self.tab_widget.addTab(page, cm_name)
