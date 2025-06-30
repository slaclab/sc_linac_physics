import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from lcls_tools.common.controls.pyepics.utils import PV

from utils.sc_linac.linac_utils import SCLinacObject

if TYPE_CHECKING:
    from rack import Rack
    

class RFStation(SCLinacObject):
    def __init__(
            self,
            rack_number: int,
            rack_object: "Rack",
    ):
        self.rack: "Rack" = rack_object
        self.rack_number = rack_number

        self._pv_prefix = self.cryomodule.pv_addr(
            "RFS{self.number} {self.rack.name}:")

    @property
    def pv_prefix(self):
        return self._pv_prefix
