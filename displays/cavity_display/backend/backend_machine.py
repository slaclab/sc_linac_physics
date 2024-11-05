from displays.cavity_display.backend.backend_cavity import BackendCavity
from utils.sc_linac.linac import Machine


class BackendMachine(Machine):
    def __init__(self, lazy_fault_pvs=False):
        self.lazy_fault_pvs = lazy_fault_pvs
        super().__init__(cavity_class=BackendCavity)
