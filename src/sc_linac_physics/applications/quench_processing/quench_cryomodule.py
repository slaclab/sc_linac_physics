from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.applications.quench_processing.quench_utils import (
    BASE_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac import Machine


class QuenchCryomodule(Cryomodule):
    def __init__(self, cryo_name, linac_object):
        super().__init__(cryo_name, linac_object)
        self.logger = self._setup_logger()

    def _setup_logger(self):
        log_dir = BASE_LOG_DIR / f"cm{self.name}"
        log_filename = f"cm{self.name}_quench_reset"

        return custom_logger(
            name=f"Quench {self}",
            log_dir=str(log_dir),
            log_filename=log_filename,
        )


QUENCH_MACHINE = Machine(
    cavity_class=QuenchCavity, cryomodule_class=QuenchCryomodule
)
