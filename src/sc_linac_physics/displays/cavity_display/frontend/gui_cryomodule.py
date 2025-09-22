from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel

from sc_linac_physics.utils import Cryomodule

if TYPE_CHECKING:
    from sc_linac_physics.utils.sc_linac.linac import Linac


class GUICryomodule(Cryomodule):
    def __init__(self, cryo_name: str, linac_object: "Linac"):
        super().__init__(cryo_name, linac_object)
        self.vlayout = QVBoxLayout()
        self.label = QLabel(cryo_name)
        self.label.setAlignment(Qt.AlignCenter)
        self.vlayout.addWidget(self.label)
        print(f"Adding cavity widgets to cm{self.name}")
        for gui_cavity in self.cavities.values():
            self.vlayout.addLayout(gui_cavity.vert_layout)

    @property
    def pydm_macros(self):
        """
        Currenlty only used for NIRP fault, but I think we can just keep adding
        to this list
        :return:
        """
        return "AREA={linac_name},CM={cm_name},RFNAME=CM{cm_name}".format(linac_name=self.linac.name, cm_name=self.name)
