from sc_linac_physics.applications.auto_setup.backend.setup_linac_object import (
    SetupLinacObject,
)
from sc_linac_physics.utils.sc_linac.linac import Linac


class SetupLinac(Linac, SetupLinacObject):
    @property
    def pv_prefix(self):
        return f"ACCL:{self.name}:1:"

    def __init__(
        self,
        linac_section,
        beamline_vacuum_infixes,
        insulating_vacuum_cryomodules,
        machine,
    ):
        Linac.__init__(
            self,
            linac_section=linac_section,
            beamline_vacuum_infixes=beamline_vacuum_infixes,
            insulating_vacuum_cryomodules=insulating_vacuum_cryomodules,
            machine=machine,
        )
        SetupLinacObject.__init__(self)

    def clear_abort(self):
        for cm in self.cryomodules.values():
            cm.clear_abort()
