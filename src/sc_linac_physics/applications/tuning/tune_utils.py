from typing import TYPE_CHECKING

from sc_linac_physics.utils.logger import BASE_LOG_DIR
from sc_linac_physics.utils.sc_linac.linac_utils import LauncherLinacObject

if TYPE_CHECKING:
    pass


class ColdLinacObject(LauncherLinacObject):
    def __init__(self):
        super().__init__(name="COLD")


TUNE_LOG_DIR = BASE_LOG_DIR / "tuning"
