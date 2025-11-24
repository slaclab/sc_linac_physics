from typing import Dict, Optional

from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac.linac_utils import (
    SCLinacObject,
    DECARAD_BACKGROUND_READING_AVG,
    DECARAD_BACKGROUND_READING_RAW,
)


class DecaradHead(SCLinacObject):
    def __init__(self, number: int, decarad: "Decarad"):
        if number not in range(1, 11):
            raise AttributeError(
                "Decarad Head number need to be between 1 and 10"
            )

        self.decarad: Decarad = decarad
        self.number: int = number

        # Adds leading 0 to numbers with less than 2 digits
        self._pv_prefix = self.decarad.pv_addr("{:02d}:".format(self.number))

        self.avg_dose_rate_pv: str = self.pv_addr("GAMMAAVE")
        self.raw_dose_rate_pv: str = self.pv_addr("GAMMA_DOSE_RATE")
        self._avg_dose_rate_pv_obj: Optional[PV] = None
        self._raw_dose_rate_pv_obj: Optional[PV] = None

        self.counter = 0

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def avg_dose_rate_pv_obj(self) -> PV:
        if not self._avg_dose_rate_pv_obj:
            self._avg_dose_rate_pv_obj = PV(self.avg_dose_rate_pv)
        return self._avg_dose_rate_pv_obj

    @property
    def raw_dose_rate_pv_obj(self) -> PV:
        if not self._raw_dose_rate_pv_obj:
            self._raw_dose_rate_pv_obj = PV(self.raw_dose_rate_pv)
        return self._raw_dose_rate_pv_obj

    @property
    def normalized_avg_dose(self) -> float:
        return max(
            self.avg_dose_rate_pv_obj.get() - DECARAD_BACKGROUND_READING_AVG, 0
        )

    @property
    def normalized_raw_dose(self) -> float:
        return max(
            self.raw_dose_rate_pv_obj.get() - DECARAD_BACKGROUND_READING_RAW, 0
        )


class Decarad(SCLinacObject):
    def __init__(self, number: int):
        if number not in [1, 2]:
            raise AttributeError("Decarad needs to be 1 or 2")
        self.number = number
        self._pv_prefix = "RADM:SYS0:{num}00:".format(num=self.number)
        self.power_control_pv = self.pv_addr("HVCTRL")
        self._power_control_pv_obj: Optional[PV] = None

        self.power_status_pv = self.pv_addr("HVSTATUS")
        self.voltage_readback_pv = self.pv_addr("HVMON")

        self.heads: Dict[int, DecaradHead] = {
            head: DecaradHead(number=head, decarad=self)
            for head in range(1, 11)
        }

    def __eq__(self, other):
        return isinstance(other, Decarad) and other.number == self.number

    @property
    def power_control_pv_obj(self) -> PV:
        if not self._power_control_pv_obj:
            self._power_control_pv_obj = PV(self.power_control_pv)
        return self._power_control_pv_obj

    def turn_on(self):
        self.power_control_pv_obj.put(0)

    def turn_off(self):
        self.power_control_pv_obj.put(1)

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def max_avg_dose(self) -> float:
        return max([head.normalized_avg_dose for head in self.heads.values()])

    @property
    def max_raw_dose(self) -> float:
        return max([head.normalized_raw_dose for head in self.heads.values()])
