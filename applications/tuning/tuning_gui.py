from PyQt5.QtWidgets import (
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)
from pydm import Display

from applications.tuning.rack_section import RackSection
from applications.tuning.tune_cavity import TuneCavity
from applications.tuning.tune_stepper import TuneStepper
from utils.sc_linac.linac import Machine
from utils.sc_linac.linac_utils import ALL_CRYOMODULES

PARK_MACHINE = Machine(cavity_class=TuneCavity, stepper_class=TuneStepper)


class HLTuner(Display):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRF HL Tuner")
        self.tab_widget: QTabWidget = QTabWidget()
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.tab_widget)

        for cm_name in ALL_CRYOMODULES:
            cm = PARK_MACHINE.cryomodules[cm_name]
            page = QWidget()
            page_layout = QHBoxLayout()
            page.setLayout(page_layout)
            page_layout.addWidget(RackSection(cm.rack_a).groupbox)
            page_layout.addWidget(RackSection(cm.rack_b).groupbox)
            self.tab_widget.addTab(page, cm_name)
