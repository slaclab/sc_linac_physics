from applications.auto_setup.backend.setup_cavity import SetupCavity
from applications.auto_setup.backend.setup_cryomodule import SetupCryomodule
from applications.auto_setup.backend.setup_linac import SetupLinac
from applications.auto_setup.backend.setup_linac_object import SetupLinacObject
from utils.sc_linac.linac import Machine


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
