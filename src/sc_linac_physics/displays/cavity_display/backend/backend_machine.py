from time import time

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.displays.cavity_display.utils.utils import (
    cavity_fault_logger,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class BackendMachine(Machine):
    def __init__(self, lazy_fault_pvs=True):
        self.lazy_fault_pvs = lazy_fault_pvs
        start = time()
        super().__init__(cavity_class=BackendCavity)
        # One line for the whole machine, not one per cavity at startup
        num_cavities = sum(len(cm.cavities) for cm in self.cryomodules.values())
        cavity_fault_logger.info(
            "%d cavities initialized (%s mode) in %.1f s",
            num_cavities,
            "lazy" if lazy_fault_pvs else "batch PV",
            time() - start,
        )
