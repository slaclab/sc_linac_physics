import logging
import os
import pathlib
from typing import Optional, Dict

import numpy as np
from lcls_tools.common.controls.pyepics.utils import PV
from lcls_tools.common.logger import logger
from scipy import stats

from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import RF_MODE_SELAP

MAX_STEP = 5
MULT = -51.0471


class SELCavity(Cavity):
    # Cache file handlers by absolute logfile path so we don't open the same file multiple times
    _HANDLERS: Dict[str, logging.FileHandler] = {}

    def __init__(
        self,
        cavity_num,
        rack_object,
        enable_file_logging: Optional[
            bool
        ] = None,  # allow callers/tests to override
    ):
        super().__init__(cavity_num=cavity_num, rack_object=rack_object)
        self._q_waveform_pv: Optional[PV] = None
        self._i_waveform_pv: Optional[PV] = None
        self._sel_poff_pv_obj: Optional[PV] = None
        self._fit_chisquare_pv_obj: Optional[PV] = None
        self._fit_slope_pv_obj: Optional[PV] = None
        self._fit_intercept_pv_obj: Optional[PV] = None

        # logger instance (don’t rely on root)
        self.logger = logger.custom_logger(f"{self} SEL Phase Opt Logger")
        self.logger.propagate = False  # prevent duplicate emissions to parents

        # Decide if we should log to file
        if enable_file_logging is None:
            # Disable file logs if env var is set
            disable = os.getenv("SC_LINAC_DISABLE_FILE_LOGS", "").lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            enable_file_logging = not disable

        self.file_handler: Optional[logging.FileHandler] = None

        if enable_file_logging:
            file_directory = pathlib.Path(__file__).parent.resolve()
            self.logfile = str(
                file_directory
                / f"logfiles/cm{self.cryomodule.name}/{self.number}_sel_phase_opt.log"
            )
            os.makedirs(os.path.dirname(self.logfile), exist_ok=True)

            # Reuse a shared handler per logfile (avoid opening the same file repeatedly)
            key = os.path.abspath(self.logfile)
            handler = self._HANDLERS.get(key)
            if handler is None:
                # delay=True defers opening the file until the first emit
                handler = logging.FileHandler(
                    self.logfile, mode="a", delay=True
                )
                handler.setFormatter(logging.Formatter(logger.FORMAT_STRING))
                self._HANDLERS[key] = handler

            # Attach the handler to this logger only if not already attached
            if handler not in self.logger.handlers:
                self.logger.addHandler(handler)
            self.file_handler = handler
        else:
            # If not logging to file, we still allow console or external config
            self.logfile = None

    # Optional: allow detaching this instance from its handler (does not close shared handler)
    def detach_file_handler(self):
        if self.file_handler and self.file_handler in self.logger.handlers:
            self.logger.removeHandler(self.file_handler)

    # Optional: close all shared handlers (e.g., test session teardown)
    @classmethod
    def close_all_file_handlers(cls):
        for h in cls._HANDLERS.values():
            try:
                h.close()
            except Exception:
                pass
        cls._HANDLERS.clear()

    @property
    def sel_poff_pv_obj(self) -> PV:
        if not self._sel_poff_pv_obj:
            self._sel_poff_pv_obj = PV(self.pv_addr("SEL_POFF"))
        return self._sel_poff_pv_obj

    @property
    def sel_phase_offset(self):
        return self.sel_poff_pv_obj.get()

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

    @property
    def fit_chisquare_pv_obj(self) -> PV:
        if not self._fit_chisquare_pv_obj:
            self._fit_chisquare_pv_obj = PV(self.pv_addr("CTRL:FIT_CHISQUARE"))
        return self._fit_chisquare_pv_obj

    @property
    def fit_slope_pv_obj(self) -> PV:
        if not self._fit_slope_pv_obj:
            self._fit_slope_pv_obj = PV(self.pv_addr("CTRL:FIT_SLOPE"))
        return self._fit_slope_pv_obj

    @property
    def fit_intercept_pv_obj(self) -> PV:
        if not self._fit_intercept_pv_obj:
            self._fit_intercept_pv_obj = PV(self.pv_addr("CTRL:FIT_INTERCEPT"))
        return self._fit_intercept_pv_obj

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

        # siegelslopes is called with y then (optional) x
        [slop, inter] = stats.siegelslopes(iwf, qwf)

        if not np.isnan(slop):
            chisum = 0
            for nn, yy in enumerate(iwf):
                denom = slop * qwf[nn] + inter
                # Avoid division by zero in chi^2 (very unlikely but cheap safeguard)
                if denom == 0:
                    continue
                chisum += (yy - denom) ** 2 / denom

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

            self.sel_poff_pv_obj.put(start_val + step)
            self.fit_chisquare_pv_obj.put(chisum)
            self.fit_slope_pv_obj.put(slop)
            self.fit_intercept_pv_obj.put(inter)

            self.logger.info(
                f"Changed SEL Phase Offset by {step:5.2f} with chi^2 {chisum:.2g}"
            )
            return step

        else:
            self.logger.warning(
                "IQ slope is NaN, not changing SEL Phase Offset"
            )
            return 0


SEL_MACHINE: Machine = Machine(cavity_class=SELCavity)
