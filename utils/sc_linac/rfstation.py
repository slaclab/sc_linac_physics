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

        self.rfs_dac_amp_pv: str = self.pv_addr("DAC_AMPLITUDE")
        self._rfs_dac_amp_pv_obj: Optional[PV] = None

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def rfs_dac_amp_pv_obj(self) -> PV:
        if not self._rfs_dac_amp_pv_obj:
            self._rfs_dac_amp_pv_obj = PV(self.rfs_dac_amp_pv)
        return self._rfs_dac_amp_pv_obj

    @property
    def rfs_dac_amp(self) -> float:
        return self.rfs_dac_amp_pv_obj.get()

    @rfs_dac_amp.setter
    def rfs_dac_amp(self, value: float):
        self.rfs_dac_amp_pv_obj.put(value)
