from applications.auto_setup.setup_cavity import SetupCavity
from applications.auto_setup.setup_linac_object import SetupLinacObject
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.linac import Linac, Machine


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


class SetupMachine(Machine, SetupLinacObject):
    @property
    def pv_prefix(self):
        return "ACCL:SYS0:SC:"

    def __init__(self):
        Machine.__init__(
            self,
            cavity_class=SetupCavity,
            cryomodule_class=SetupCryomodule,
            linac_class=SetupLinac,
        )
        SetupLinacObject.__init__(self)

    def clear_abort(self):
        for cm in self.cryomodules.values():
            cm.clear_abort()


SETUP_MACHINE = SetupMachine()
