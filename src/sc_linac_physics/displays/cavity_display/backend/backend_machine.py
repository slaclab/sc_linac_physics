from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class BackendMachine(Machine):
    def __init__(self, lazy_fault_pvs=True):
        self.lazy_fault_pvs = lazy_fault_pvs
        super().__init__(cavity_class=BackendCavity)
