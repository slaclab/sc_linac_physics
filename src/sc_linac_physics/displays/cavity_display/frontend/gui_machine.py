from PyQt5.QtWidgets import QHBoxLayout

from sc_linac_physics.displays.cavity_display.frontend.gui_cavity import (
    GUICavity,
)
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

    def set_zoom_level(self, zoom_percent):
        """Apply zoom scaling to all elements."""
        scale = zoom_percent / 100.0

        # Scale all cavities
        self._scale_cavities(scale)

        # Scale spacing
        self._scale_spacing(scale)

    def _scale_cavities(self, scale):
        """Scale all cavity widgets."""
        linacs = (
            self.linacs
            if isinstance(self.linacs, list)
            else list(self.linacs.values())
        )

        for linac in linacs:
            cryomodules = linac.cryomodules
            if isinstance(cryomodules, dict):
                cryomodules = cryomodules.values()

            for cm in cryomodules:
                cavities = cm.cavities
                if isinstance(cavities, dict):
                    cavities = cavities.values()

                for cavity in cavities:
                    cavity.set_scale(scale)

    def _scale_spacing(self, scale):
        """Scale spacing between elements."""
        spacing = max(2, int(8 * scale))

        # Scale the existing top_half and bottom_half layouts
        if hasattr(self, "top_half"):
            self.top_half.setSpacing(spacing)
        if hasattr(self, "bottom_half"):
            self.bottom_half.setSpacing(spacing)
