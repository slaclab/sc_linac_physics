from typing import TYPE_CHECKING, Optional

from lcls_tools.common.controls.pyepics.utils import PV

from utils.sc_linac.rack import Rack

if TYPE_CHECKING:
    from utils.sc_linac.cryomodule import Cryomodule


class TuneRack(Rack):
    def __init__(self, rack_name: str, cryomodule_object: "Cryomodule"):
        super().__init__(rack_name, cryomodule_object)
        self.freq_offset_pv = self.pv_addr("FSCAN:FDES")
        self._freq_offset_pv_obj: Optional[PV] = None
        self.go_button_pv = self.pv_addr("FSCAN:START")
        self._go_button_pv_obj: Optional[PV] = None

    @property
    def freq_offset_pv_obj(self) -> PV:
        if not self._freq_offset_pv_obj:
            self._freq_offset_pv_obj = PV(self.freq_offset_pv)
        return self._freq_offset_pv_obj

    @property
    def freq_offset(self):
        return self.freq_offset_pv_obj.get()

    @freq_offset.setter
    def freq_offset(self, freq: int):
        self.freq_offset_pv_obj.put(freq)

    @property
    def go_button_pv_obj(self) -> PV:
        if not self._go_button_pv_obj:
            self._go_button_pv_obj = PV(self.go_button_pv)
        return self._go_button_pv_obj

    def push_go_button(self):
        # TODO confirm that this is the correct value to write
        self.go_button_pv_obj.put(1)

    def move_to_cold_landing(self):
        # TODO introduce logic that handles rack frequency shift
        pass

    def move_to_resonance(self):
        # TODO introduce logic that handles rack frequency shift
        pass

    def park(self):
        # TODO introduce logic that handles rack frequency shift
        pass

    def shift_frequency(self, offset: int):
        self.freq_offset = offset
        self.push_go_button()
