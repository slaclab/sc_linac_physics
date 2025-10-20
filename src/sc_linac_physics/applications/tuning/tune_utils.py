from typing import TYPE_CHECKING

from sc_linac_physics.utils.sc_linac.linac_utils import LauncherLinacObject

if TYPE_CHECKING:
    pass


class ColdLinacObject(LauncherLinacObject):
    def __init__(self):
        super().__init__(name="COLD")
