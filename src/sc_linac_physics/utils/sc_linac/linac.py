################################################################################
# Utility classes for superconducting linac
# NOTE: For some reason, using python 3 style type annotations causes circular
#       import issues, so leaving as python 2 style for now
################################################################################
from typing import Dict, List, Type

from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.magnet import Magnet
from sc_linac_physics.utils.sc_linac.piezo import Piezo
from sc_linac_physics.utils.sc_linac.rack import Rack
from sc_linac_physics.utils.sc_linac.ssa import SSA
from sc_linac_physics.utils.sc_linac.stepper import StepperTuner


class Linac:
    """
    Python representation of LCLS II linac sections. This class functions mostly
    as a container for cryomodules and linac-level vacuum PVs

    """

    def __init__(
        self,
        linac_section,
        beamline_vacuum_infixes,
        insulating_vacuum_cryomodules,
        machine,
    ):
        # type: (int, List[str], List[str], Machine) -> None
        """
        @param linac_section: int of Linac index i.e. "L0B" -> 0
        @param beamline_vacuum_infixes: str list of vacuum infixes for that
                                        section as found in
                                        linac_utils.BEAMLINE_VACUUM_INFIXES
        @param insulating_vacuum_cryomodules: str list of cryomodules with
                                              insulated vacuum readback in that
                                              section as found in
                                              linac_utils.INSULATING_VACUUM_CRYOMODULES
        @param machine: Machine object that this linac belongs to
        """

        self.cryomodule_class: Type[Cryomodule] = machine.cryomodule_class
        self.cavity_class = machine.cavity_class
        self.rack_class = machine.rack_class
        self.magnet_class = machine.magnet_class
        self.ssa_class = machine.ssa_class
        self.stepper_class = machine.stepper_class
        self.piezo_class = machine.piezo_class
        self.machine = machine

        self.name = f"L{linac_section}B"
        self.cryomodules: Dict[str, Cryomodule] = {}
        self.vacuum_prefix = f"VGXX:{self.name}:"

        self.beamline_vacuum_pvs: List[str] = [
            f"{self.vacuum_prefix}{infix}:COMBO_P" for infix in beamline_vacuum_infixes
        ]
        self.insulating_vacuum_pvs: List[str] = [
            f"{self.vacuum_prefix}{cm}96:COMBO_P" for cm in insulating_vacuum_cryomodules
        ]

        for cm_name in linac_utils.LINAC_CM_MAP[linac_section]:
            self.cryomodules[cm_name] = self.cryomodule_class(cryo_name=cm_name, linac_object=self)

    def __str__(self):
        return self.name


class Machine:
    """
    Python representation of the entire LCLS II accelerator. This class functions
    as a generator for lower level accelerator objects, as well as a container
    for generated cryomodule objects

    """

    def __init__(
        self,
        linac_class: Type[Linac] = Linac,
        cryomodule_class: Type[Cryomodule] = Cryomodule,
        cavity_class: Type[Cavity] = Cavity,
        magnet_class: Type[Magnet] = Magnet,
        rack_class: Type[Rack] = Rack,
        stepper_class: Type[StepperTuner] = StepperTuner,
        ssa_class: Type[SSA] = SSA,
        piezo_class: Type[Piezo] = Piezo,
    ):
        """
        All inputs are optional, but allow for object customization for more
        specific use cases. Only functionality used by at least two applications
        is put in default classes

        """
        self.linac_class = linac_class
        self.cryomodule_class = cryomodule_class
        self.cavity_class = cavity_class
        self.magnet_class = magnet_class
        self.rack_class = rack_class
        self.stepper_class = stepper_class
        self.ssa_class = ssa_class
        self.piezo_class = piezo_class

        self.linacs: List[Linac] = []

        for section in range(4):
            self.linacs.append(
                linac_class(
                    linac_section=section,
                    beamline_vacuum_infixes=linac_utils.BEAMLINE_VACUUM_INFIXES[section],
                    insulating_vacuum_cryomodules=linac_utils.INSULATING_VACUUM_CRYOMODULES[section],
                    machine=self,
                )
            )

        non_hl_cavities = []
        hl_cavities = []

        self.cryomodules: Dict[str, Cryomodule] = {}
        for linac in self.linacs:
            for cm_name, cm_obj in linac.cryomodules.items():
                self.cryomodules[cm_name] = cm_obj
                for cav_ob in cm_obj.cavities.values():
                    if cm_obj.is_harmonic_linearizer:
                        hl_cavities.append(cav_ob)
                    else:
                        non_hl_cavities.append(cav_ob)

        # TODO handle hitting end of list
        self.non_hl_iterator = iter(non_hl_cavities)
        self.hl_iterator = iter(hl_cavities)
        self.all_iterator = iter(non_hl_cavities + hl_cavities)


MACHINE = Machine()
