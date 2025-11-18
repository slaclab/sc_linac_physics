from typing import Type, Dict, List, TYPE_CHECKING, Optional

from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac.linac_utils import (
    SCLinacObject,
    L1BHL,
    CRYO_NAME_MAP,
)

if TYPE_CHECKING:
    from cavity import Cavity
    from linac import Linac
    from magnet import Magnet
    from piezo import Piezo
    from rack import Rack
    from ssa import SSA
    from stepper import StepperTuner


class Cryomodule(SCLinacObject):
    """
    Python representation of an LCLS II cryomodule. This class functions mostly
    as a container for racks and cryo-level PVs

    """

    def __init__(
        self,
        cryo_name: str,
        linac_object: "Linac",
    ):
        """
        @param cryo_name: str name of Cryomodule i.e. "02", "03", "H1", "H2"
        @param linac_object: the linac object this cryomodule belongs to i.e.
                             CM02 is in linac L1B
        """

        self.name: str = cryo_name
        self.linac: "Linac" = linac_object

        self.magnet_class: Type["Magnet"] = self.linac.magnet_class
        self.rack_class: Type["Rack"] = self.linac.rack_class
        self.cavity_class: Type["Cavity"] = self.linac.cavity_class
        self.ssa_class: Type["SSA"] = self.linac.ssa_class
        self.stepper_class: Type["StepperTuner"] = self.linac.stepper_class
        self.piezo_class: Type["Piezo"] = self.linac.piezo_class

        if not self.is_harmonic_linearizer:
            self.quad: "Magnet" = self.magnet_class(
                magnet_type="QUAD", cryomodule=self
            )
            self.xcor: "Magnet" = self.magnet_class(
                magnet_type="XCOR", cryomodule=self
            )
            self.ycor: "Magnet" = self.magnet_class(
                magnet_type="YCOR", cryomodule=self
            )

        self._pv_prefix = f"ACCL:{self.linac.name}:{self.name}00:"

        self.cte_prefix = f"CTE:CM{self.name}:"
        self.cvt_prefix = f"CVT:CM{self.name}:"
        self.cpv_prefix = f"CPV:CM{self.name}:"

        if self.is_harmonic_linearizer:
            self.cryo_name = CRYO_NAME_MAP[self.name]
        else:
            self.cryo_name = f"CM{self.name}"

        self.jt_prefix = f"CLIC:{self.cryo_name}:3001:PVJT:"
        self.heater_prefix = f"CPIC:{self.cryo_name}:0000:EHCV:"

        self.ds_level_pv: str = f"CLL:CM{self.name}:2301:DS:LVL"
        self._ds_level_pv_obj: Optional[PV] = None

        self.us_level_pv: str = f"CLL:CM{self.name}:2601:US:LVL"
        self.ds_pressure_pv: str = f"CPT:CM{self.name}:2302:DS:PRESS"

        self.jt_valve_readback_pv: str = self.make_jt_pv("ORBV")
        self.heater_readback_pv: str = self.make_heater_pv("ORBV")

        self.aact_mean_sum_pv: str = self.pv_addr("AACTMEANSUM")

        self.rack_a: "Rack" = self.rack_class(
            rack_name="A", cryomodule_object=self
        )
        self.rack_b: "Rack" = self.rack_class(
            rack_name="B", cryomodule_object=self
        )

        self.cavities: Dict[int, "Cavity"] = {}
        self.cavities.update(self.rack_a.cavities)
        self.cavities.update(self.rack_b.cavities)

        if self.is_harmonic_linearizer:
            self.coupler_vacuum_pvs: List[str] = [
                self.linac.vacuum_prefix
                + "{cm}09:COMBO_P".format(cm=self.name),
                self.linac.vacuum_prefix
                + "{cm}19:COMBO_P".format(cm=self.name),
            ]
        else:
            self.coupler_vacuum_pvs: List[str] = [
                self.linac.vacuum_prefix + "{cm}14:COMBO_P".format(cm=self.name)
            ]

        self.vacuum_pvs: List[str] = (
            self.coupler_vacuum_pvs
            + self.linac.beamline_vacuum_pvs
            + self.linac.insulating_vacuum_pvs
        )

    def __str__(self):
        return f"{self.linac.name} CM{self.name}"

    def make_heater_pv(self, suffix: str) -> str:
        return self.heater_prefix + suffix

    def make_jt_pv(self, suffix: str) -> str:
        return self.jt_prefix + suffix

    @property
    def ds_level_pv_obj(self) -> PV:
        if not self._ds_level_pv_obj:
            self._ds_level_pv_obj = PV(self.ds_level_pv)
        return self._ds_level_pv_obj

    @property
    def ds_level(self):
        return self.ds_level_pv_obj.get()

    @property
    def is_harmonic_linearizer(self):
        return self.name in L1BHL

    @property
    def pv_prefix(self):
        return self._pv_prefix
