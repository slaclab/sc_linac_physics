from sc_linac_physics.applications.auto_setup.backend.setup_linac_object import (
    SetupLinacObject,
)
from sc_linac_physics.utils import Cryomodule


class SetupCryomodule(Cryomodule, SetupLinacObject):
    def __init__(
        self,
        cryo_name,
        linac_object,
    ):
        Cryomodule.__init__(
            self,
            cryo_name=cryo_name,
            linac_object=linac_object,
        )
        SetupLinacObject.__init__(self)

    def clear_abort(self):
        for cavity in self.cavities.values():
            cavity.clear_abort()
