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

        self.rfs1_dac_amp_pv: str = self.pv_addr("DAC_AMPLITUDE")
        self._rfs1_dac_amp_pv_obj: Optional[PV] = None

        self.rfs2_dac_amp_pv: str = self.pv_addr("DAC_AMPLITUDE")
        self._rfs2_dac_amp_pv_obj: Optional[PV] = None

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def rfs1_dac_amp_pv_obj(self) -> PV:
        if not self._rfs1_dac_amp_pv_obj:
            self._rfs1_dac_amp_pv_obj = PV(self.rfs1_dac_amp_pv)
        return self._rfs1_dac_amp_pv_obj

    @property
    def rfs1_dac_amp(self) -> float:
        return self.rfs1_dac_amp_pv_obj.get()

    @rfs1_dac_amp.setter
    def rfs1_dac_amp(self, value: float):
        self.rfs1_dac_amp_pv_obj.put(value)

    @property
    def rfs2_dac_amp_pv_obj(self) -> PV:
        if not self._rfs2_dac_amp_pv_obj:
            self._rfs2_dac_amp_pv_obj = PV(self.rfs2_dac_amp_pv)
        return self._rfs2_dac_amp_pv_obj

    @property
    def rfs2_dac_amp(self) -> float:
        return self.rfs2_dac_amp_pv_obj.get()

    @rfs2_dac_amp.setter
    def rfs2_dac_amp(self, value: float):
        self.rfs2_dac_amp_pv_obj.put(value)
