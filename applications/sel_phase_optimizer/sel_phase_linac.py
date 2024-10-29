import logging
import os
from typing import Optional

import numpy as np
from lcls_tools.common.controls.pyepics.utils import PV
from lcls_tools.common.logger.logger import custom_logger, FORMAT_STRING
from scipy import stats

from utils.sc_linac.cavity import Cavity
from utils.sc_linac.linac import Machine
from utils.sc_linac.linac_utils import RF_MODE_SELAP

MAX_STEP = 5
MULT = -51.0471


class SELCavity(Cavity):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        super().__init__(cavity_num=cavity_num, rack_object=rack_object)
        self._q_waveform_pv: Optional[PV] = None
        self._i_waveform_pv: Optional[PV] = None
        self._sel_poff_pv: Optional[PV] = None

        self.logger = custom_logger(f"{self} SEL Phase Opt Logger")
        self.logfile = (
            f"logfiles/cm{self.cryomodule.name}/{self.number}_sel_phase_opt.log"
        )
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)

        self.file_handler = logging.FileHandler(self.logfile, mode="a")
        self.file_handler.setFormatter(logging.Formatter(FORMAT_STRING))
        self.logger.addHandler(self.file_handler)

    @property
    def sel_poff_pv(self) -> PV:
        if not self._sel_poff_pv:
            self._sel_poff_pv = PV(self.pv_addr("SEL_POFF"))
        return self._sel_poff_pv

    @property
    def sel_phase_offset(self):
        return self.sel_poff_pv.get()

    @property
    def i_waveform(self):
        if not self._i_waveform_pv:
            self._i_waveform_pv = PV(self.pv_addr("CTRL:IWF"))
        return self._i_waveform_pv.get()

    @property
    def q_waveform(self):
        if not self._q_waveform_pv:
            self._q_waveform_pv = PV(self.pv_addr("CTRL:QWF"))
        return self._q_waveform_pv.get()

    def can_be_straightened(self) -> bool:
        return (
            self.is_online
            and self.is_on
            and self.rf_mode == RF_MODE_SELAP
            and self.aact > 1
        )

    def straighten_iq_plot(self) -> float:
        """
        TODO make the return value more intuitive
        :return: change in SEL phase offset
        """

        if not self.can_be_straightened():
            return 0

        start_val = self.sel_phase_offset
        iwf = self.i_waveform
        qwf = self.q_waveform

        [slop, inter] = stats.siegelslopes(iwf, qwf)

        if not np.isnan(slop):
            chisum = 0
            for nn, yy in enumerate(qwf):
                chisum += (yy - (slop * iwf[nn] + inter)) ** 2 / (
                    slop * iwf[nn] + inter
                )

            step = slop * MULT
            if abs(step) > MAX_STEP:
                step = MAX_STEP * np.sign(step)
                self.logger.warning(
                    f"Desired SEL Phase Offset change too large, moving by {step} instead"
                )

            if start_val + step < -180:
                step = step + 360
            elif start_val + step > 180:
                step = step - 360

            self.sel_poff_pv.put(start_val + step)
            self.logger.info(
                f"Changed SEL Phase Offset by {step:5.2f} with chi^2 {chisum:.2g}"
            )
            return step

        else:
            self.logger.warning("IQ slope is NaN, not changing SEL Phase Offset")
            return 0


SEL_MACHINE: Machine = Machine(cavity_class=SELCavity)
