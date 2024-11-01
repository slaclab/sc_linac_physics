from typing import List

from PyQt5.QtWidgets import QVBoxLayout, QTabWidget, QWidget, QGridLayout, QCheckBox
from pydm import Display

from utils.qt import get_dimensions
from utils.sc_linac.decarad import Decarad
from utils.sc_linac.linac import MACHINE
from utils.sc_linac.linac_utils import SCLinacObject


def get_pvs(sc_linac_object: SCLinacObject):
    linac_pvs = []
    for attr in sc_linac_object.__dict__.keys():
        if attr.endswith("pv") or attr.endswith("pvs"):
            linac_pvs.append(attr)
    return sorted(linac_pvs)


class AutoPlot(Display):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRF Auto Plot")
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        self.tab_widget = QTabWidget()
        l0b = MACHINE.linacs[0]
        self.make_page("Linac PVs", get_pvs(l0b))
        cm01 = l0b.cryomodules["01"]
        self.make_page("Cryomodule PVs", get_pvs(cm01))
        self.make_page("Quad PVs", get_pvs(cm01.quad))
        self.make_page("XCOR PVs", get_pvs(cm01.xcor))
        self.make_page("YCOR PVs", get_pvs(cm01.ycor))
        self.make_page("Rack PVs", get_pvs(cm01.rack_a))
        cavity1 = cm01.cavities[1]
        self.make_page("Cavity PVs", get_pvs(cavity1))
        self.make_page("SSA PVs", get_pvs(cavity1.ssa))
        self.make_page("Piezo PVs", get_pvs(cavity1.piezo))
        self.make_page("Stepper PVs", get_pvs(cavity1.stepper_tuner))
        self.make_page("Decarad PVs", get_pvs(Decarad(1)))

        main_layout.addWidget(self.tab_widget)

    def make_page(self, name: str, options: List[str]):
        page: QWidget = QWidget()
        page_layout = QGridLayout()
        page.setLayout(page_layout)
        self.tab_widget.addTab(page, name)
        col_count = get_dimensions(options)
        for idx, option in enumerate(options):
            parsed_name = (
                option.replace("_", " ").replace("pvs", "").replace("pv", "").title()
            )

            checkbox: QCheckBox = QCheckBox(parsed_name)
            checkbox.setAccessibleName(option)
            page_layout.addWidget(checkbox, int(idx / col_count), idx % col_count)
