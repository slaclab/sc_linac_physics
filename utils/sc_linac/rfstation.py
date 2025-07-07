from typing import TYPE_CHECKING, Optional

from lcls_tools.common.controls.pyepics.utils import (
    PV,
)

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
            f"RFS{self.num}{self.rack.rack_name}:")

        self.dac_amp_pv: str = self.pv_addr("DAC_AMPLITUDE")
        self._dac_amp_pv_obj: Optional[PV] = None

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def dac_amp_pv_obj(self) -> PV:
        if not self._dac_amp_pv_obj:
            self._dac_amp_pv_obj = PV(self.dac_amp_pv)
        return self._dac_amp_pv_obj

    @property
    def dac_amp(self) -> float:
        return self.dac_amp_pv_obj.get()

    @dac_amp.setter
    def dac_amp(self, value: float):
        self.dac_amp_pv_obj.put(value)
