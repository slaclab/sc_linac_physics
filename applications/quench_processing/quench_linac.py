import datetime
import logging
import os
import sys
from time import sleep
from typing import Optional

import numpy as np
from lcls_tools.common.controls.pyepics.utils import PV, EPICS_INVALID_VAL

from utils.sc_linac.cavity import Cavity
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.decarad import Decarad
from utils.sc_linac.linac import Machine
from utils.sc_linac.linac_utils import QuenchError

LOADED_Q_CHANGE_FOR_QUENCH = 0.6
MAX_WAIT_TIME_FOR_QUENCH = 20 * 60
MAX_QUENCH_RETRIES = 3


class QuenchCavity(Cavity):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        super().__init__(cavity_num=cavity_num, rack_object=rack_object)
        self.cav_power_pv = self.pv_addr("CAV:PWRMEAN")
        self.forward_power_pv = self.pv_addr("FWD:PWRMEAN")
        self.reverse_power_pv = self.pv_addr("REV:PWRMEAN")

        self.fault_waveform_pv = self.pv_addr("CAV:FLTAWF")
        self._fault_waveform_pv_obj: Optional[PV] = None

        self.decay_ref_pv = self.pv_addr("DECAYREFWF")

        self.fault_time_waveform_pv = self.pv_addr("CAV:FLTTWF")
        self._fault_time_waveform_pv_obj: Optional[PV] = None

        self.srf_max_pv = self.pv_addr("ADES_MAX_SRF")
        self.pre_quench_amp = None
        self._quench_bypass_rbck_pv: Optional[PV] = None
        self._current_q_loaded_pv_obj: Optional[PV] = None

        self.decarad: Optional[Decarad] = None

    @property
    def current_q_loaded_pv_obj(self):
        if not self._current_q_loaded_pv_obj:
            self._current_q_loaded_pv_obj = PV(self.current_q_loaded_pv)
        return self._current_q_loaded_pv_obj

    @property
    def quench_latch_pv_obj(self) -> PV:
        if not self._quench_latch_pv_obj:
            self._quench_latch_pv_obj = PV(self.quench_latch_pv)
        return self._quench_latch_pv_obj

    @property
    def quench_latch_invalid(self):
        return self.quench_latch_pv_obj.severity == EPICS_INVALID_VAL

    @property
    def quench_intlk_bypassed(self) -> bool:
        if not self._quench_bypass_rbck_pv:
            self._quench_bypass_rbck_pv = PV(self.pv_addr("QUENCH_BYP_RBV"))
        return self._quench_bypass_rbck_pv.get() == 1

    @property
    def fault_waveform_pv_obj(self) -> PV:
        if not self._fault_waveform_pv_obj:
            self._fault_waveform_pv_obj = PV(self.fault_waveform_pv)
        return self._fault_waveform_pv_obj

    @property
    def fault_time_waveform_pv_obj(self) -> PV:
        if not self._fault_time_waveform_pv_obj:
            self._fault_time_waveform_pv_obj = PV(self.fault_time_waveform_pv)
        return self._fault_time_waveform_pv_obj

    def reset_interlocks(self, wait: int = 0, attempt: int = 0):
        """Overwriting base function to skip wait/reset cycle"""
        print(f"Resetting interlocks for {self}")

        if not self._interlock_reset_pv_obj:
            self._interlock_reset_pv_obj = PV(self.interlock_reset_pv)

        self._interlock_reset_pv_obj.put(1)

    def walk_to_quench(
        self,
        end_amp: float = 21,
        step_size: float = 0.2,
        step_time: float = 30,
    ):
        self.reset_interlocks()
        while not self.is_quenched and self.ades < end_amp:
            self.check_abort()
            self.wait(step_time)
            self.ades = min(self.ades + step_size, end_amp)

    def wait(self, seconds: float):
        for _ in range(int(seconds)):
            self.check_abort()
            sleep(1)
        sleep(seconds - int(seconds))

    def wait_for_quench(self) -> Optional[float]:
        if not self.is_quenched:
            print("cannot process unquenched cavity")
            return None
        self.reset_interlocks()
        start = datetime.datetime.now()
        sleep(1)
        print(f"{datetime.datetime.now()} Waiting for {self} to quench")
        while (
            not self.is_quenched
            and (datetime.datetime.now() - start).total_seconds()
            < MAX_WAIT_TIME_FOR_QUENCH
        ):
            self.check_abort()
            sleep(1)
        return (datetime.datetime.now() - start).total_seconds()

    def check_abort(self):
        super().check_abort()
        if self.decarad.max_avg_dose > 50:
            raise QuenchError("Max Radiation Dose Exceeded")

    def quench_process(
        self,
        start_amp: float = 5,
        end_amp: float = 21,
        step_size: float = 0.2,
        step_time: float = 30,
    ):
        self.turn_off()
        self.ades = start_amp
        self.set_sela_mode()
        self.turn_on()

        if end_amp > self.ades_max:
            print(f"{end_amp} above AMAX, ramping to {self.ades_max} instead")
            end_amp = self.ades_max

        while self.ades < end_amp:
            self.check_abort()

            print(f"Walking {self} to quench")
            self.walk_to_quench(
                end_amp=end_amp,
                step_size=step_size,
                step_time=step_time,
            )

            if self.is_quenched:
                print(f"Detected quench for {self}")
                attempt = 0
                running_times = []
                time_to_quench = self.wait_for_quench()
                running_times.append(time_to_quench)

                # if time_to_quench >= MAX_WAIT_TIME_FOR_QUENCH, the cavity was
                # stable
                while (
                    time_to_quench < MAX_WAIT_TIME_FOR_QUENCH
                    and attempt < MAX_QUENCH_RETRIES
                ):
                    self.check_abort()
                    time_to_quench = self.wait_for_quench()
                    running_times.append(time_to_quench)
                    attempt += 1

                if (
                    attempt >= MAX_QUENCH_RETRIES
                    and not running_times[-1] > running_times[0]
                ):
                    print(f"Attempt: {attempt}")
                    print(f"Running times: {running_times}")
                    raise QuenchError("Quench processing failed")

    def validate_quench(self, wait_for_update: bool = False):
        """
        Parsing the fault waveforms to calculate the loaded Q to try to determine
        if a quench was real.

        DERIVATION NOTES
        A(t) = A0 * e^((-2 * pi * cav_freq * t)/(2 * loaded_Q)) = A0 * e ^ ((-pi * cav_freq * t)/loaded_Q)

        ln(A(t)) = ln(A0) + ln(e ^ ((-pi * cav_freq * t)/loaded_Q)) = ln(A0) - ((pi * cav_freq * t)/loaded_Q)
        polyfit(t, ln(A(t)), 1) = [-((pi * cav_freq)/loaded_Q), ln(A0)]
        polyfit(t, ln(A0/A(t)), 1) = [(pi * f * t)/Ql]

        https://education.molssi.org/python-data-analysis/03-data-fitting/index.html

        :param wait_for_update: bool
        :return: bool representing whether quench was real
        """

        if wait_for_update:
            print(f"Waiting 0.1s to give {self} waveforms a chance to update")
            sleep(0.1)

        time_data = self.fault_time_waveform_pv_obj.get()
        fault_data = self.fault_waveform_pv_obj.get()
        time_0 = 0

        # Look for time 0 (quench). These waveforms capture data beforehand
        for time_0, time in enumerate(time_data):
            if time >= 0:
                break

        fault_data = fault_data[time_0:]
        time_data = time_data[time_0:]

        end_decay = len(fault_data) - 1

        # Find where the amplitude decays to "zero"
        for end_decay, amp in enumerate(fault_data):
            if amp < 0.002:
                break

        fault_data = fault_data[:end_decay]
        time_data = time_data[:end_decay]

        saved_loaded_q = self.current_q_loaded_pv_obj.get()

        self.pre_quench_amp = fault_data[0]

        exponential_term = np.polyfit(
            time_data, np.log(self.pre_quench_amp / fault_data), 1
        )[0]
        loaded_q = (np.pi * self.frequency) / exponential_term

        thresh_for_quench = LOADED_Q_CHANGE_FOR_QUENCH * saved_loaded_q
        self.cryomodule.logger.info(f"{self} Saved Loaded Q: {saved_loaded_q:.2e}")
        self.cryomodule.logger.info(f"{self} Last recorded amplitude: {fault_data[0]}")
        self.cryomodule.logger.info(f"{self} Threshold: {thresh_for_quench:.2e}")
        self.cryomodule.logger.info(f"{self} Calculated Loaded Q: {loaded_q:.2e}")

        is_real = loaded_q < thresh_for_quench
        print("Validation: ", is_real)

        return is_real


class QuenchCryomodule(Cryomodule):
    def __init__(self, cryo_name, linac_object):
        super().__init__(cryo_name, linac_object)

        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setFormatter(formatter)

        self.logger = logging.getLogger(f"{self} quench resetter")
        self.logger.setLevel(logging.DEBUG)

        self.logfile = f"logfiles/cm{self.name}/cm{self.name}_quench_reset.log"
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)

        self.file_handler = logging.FileHandler(self.logfile, mode="w")
        self.file_handler.setFormatter(formatter)

        self.logger.addHandler(self.file_handler)
        self.logger.addHandler(self.console_handler)


QUENCH_MACHINE = Machine(cavity_class=QuenchCavity, cryomodule_class=QuenchCryomodule)
