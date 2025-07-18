from typing import Type, Dict, TYPE_CHECKING

from utils.sc_linac.linac_utils import SCLinacObject
from utils.sc_linac.rfstation import RFStation

if TYPE_CHECKING:
    from cavity import Cavity
    from cryomodule import Cryomodule


class Rack(SCLinacObject):
    """
    Python representation of LCLS II RF Racks. This class functions mostly as a
    container for cavities.
    Rack A has cavities 1 through 4, Rack B has cavities 5 through 8.
    """

    def __init__(
            self,
            rack_name: str,
            cryomodule_object: "Cryomodule",
    ):
        """
        Parameters
        ----------
        rack_name: str name of rack (always either "A" or "B")
        cryomodule_object: the cryomodule object this rack belongs to
        """

        self.cryomodule: "Cryomodule" = cryomodule_object
        self.rack_name = rack_name

        self.cavity_class: Type["Cavity"] = self.cryomodule.cavity_class
        self.ssa_class = self.cryomodule.ssa_class
        self.stepper_class = self.cryomodule.stepper_class
        self.piezo_class = self.cryomodule.piezo_class

        self.cavities: Dict[int, "Cavity"] = {}
        self._pv_prefix = self.cryomodule.pv_addr(
            "RACK{RACK}:".format(RACK=self.rack_name)
        )
        self.rfs1 = RFStation(num=1, rack_object=self)
        self.rfs2 = RFStation(num=2, rack_object=self)

        if rack_name == "A":
            # rack A always has cavities 1 - 4
            for cavityNum in range(1, 5):
                self.cavities[cavityNum] = self.cavity_class(
                    cavity_num=cavityNum, rack_object=self
                )

        elif rack_name == "B":
            # rack B always has cavities 5 - 8
            for cavityNum in range(5, 9):
                self.cavities[cavityNum] = self.cavity_class(
                    cavity_num=cavityNum, rack_object=self
                )

        else:
            raise Exception(f"Bad rack name {rack_name}")

    @property
    def pv_prefix(self):
        return self._pv_prefix

    def __str__(self):
        return f"{self.cryomodule} Rack {self.rack_name}"
