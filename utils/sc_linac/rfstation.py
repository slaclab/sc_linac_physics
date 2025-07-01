from typing import TYPE_CHECKING
from utils.sc_linac.linac_utils import SCLinacObject

if TYPE_CHECKING:
    from rack import Rack


class RFStation(SCLinacObject):
    def __init__(
            self,
            num: int,
            rack_object: "Rack",
    ):
        self.rack: "Rack" = rack_object
        self.num = num

        self._pv_prefix = self.rack.cryomodule.pv_addr(
            "RFS{self.num} {self.rack.rack_name}:")

    @property
    def pv_prefix(self):
        return self._pv_prefix
