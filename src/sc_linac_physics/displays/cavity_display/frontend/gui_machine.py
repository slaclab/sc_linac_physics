from PyQt5.QtWidgets import QHBoxLayout

from sc_linac_physics.displays.cavity_display.frontend.gui_cavity import GUICavity
from sc_linac_physics.displays.cavity_display.frontend.gui_cryomodule import (
    GUICryomodule,
)
from sc_linac_physics.displays.cavity_display.frontend.utils import make_line
from sc_linac_physics.utils.sc_linac.linac import Machine


class GUIMachine(Machine):
    def __init__(self, lazy_fault_pvs=True):
        self.lazy_fault_pvs = lazy_fault_pvs
        super().__init__(cavity_class=GUICavity, cryomodule_class=GUICryomodule)
        self.top_half = QHBoxLayout()
        self.bottom_half = QHBoxLayout()

        for i in range(0, 3):
            gui_linac = self.linacs[i]
            for gui_cm in gui_linac.cryomodules.values():
                self.top_half.addLayout(gui_cm.vlayout)

            if i != 2:
                self.top_half.addWidget(make_line())

        l3b = self.linacs[3]
        for gui_cm in l3b.cryomodules.values():
            self.bottom_half.addLayout(gui_cm.vlayout)
