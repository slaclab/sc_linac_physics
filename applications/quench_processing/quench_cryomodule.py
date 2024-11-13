import logging
import os
import sys

from lcls_tools.common.logger import logger

from applications.quench_processing.quench_cavity import QuenchCavity
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.linac import Machine


class QuenchCryomodule(Cryomodule):
    def __init__(self, cryo_name, linac_object):
        super().__init__(cryo_name, linac_object)

        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setFormatter(formatter)

        self.logger = logger.custom_logger(f"{self} quench resetter")
        self.logger.setLevel(logging.DEBUG)

        self.logfile = f"logfiles/cm{self.name}/cm{self.name}_quench_reset.log"
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)

        self.file_handler = logging.FileHandler(self.logfile, mode="a")
        self.file_handler.setFormatter(formatter)

        self.logger.addHandler(self.file_handler)
        self.logger.addHandler(self.console_handler)


QUENCH_MACHINE = Machine(cavity_class=QuenchCavity, cryomodule_class=QuenchCryomodule)
