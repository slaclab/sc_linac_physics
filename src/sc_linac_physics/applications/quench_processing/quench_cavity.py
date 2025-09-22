import datetime
import time
from typing import Optional

import numpy as np
from lcls_tools.common.controls.pyepics.utils import PV, EPICS_INVALID_VAL

from sc_linac_physics.applications.quench_processing.quench_utils import (
    QUENCH_AMP_THRESHOLD,
    LOADED_Q_CHANGE_FOR_QUENCH,
    MAX_WAIT_TIME_FOR_QUENCH,
    QUENCH_STABLE_TIME,
    MAX_QUENCH_RETRIES,
    DECARAD_SETTLE_TIME,
    RADIATION_LIMIT,
)
from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.decarad import Decarad
from sc_linac_physics.utils.sc_linac.linac_utils import QuenchError, RF_MODE_SELA


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

    def reset_interlocks(self, wait: int = 0, attempt: int = 0, time_after_reset=1):
        """Overwriting base function to skip wait/reset cycle"""
        print(f"Resetting interlocks for {self}")

        if not self._interlock_reset_pv_obj:
            self._interlock_reset_pv_obj = PV(self.interlock_reset_pv)

        self._interlock_reset_pv_obj.put(1)
        self.wait_for_decarads()

    def walk_to_quench(
        self,
        end_amp: float = 21,
        step_size: float = 0.2,
        step_time: float = 30,
    ):
        self.reset_interlocks()
        while not self.is_quenched and self.ades < end_amp:
            self.check_abort()
            self.ades = min(self.ades + step_size, end_amp)
            self.wait(step_time - DECARAD_SETTLE_TIME)
            self.wait_for_decarads()

    def wait(self, seconds: float):
        for _ in range(int(seconds)):
            self.check_abort()
            time.sleep(1)
            if self.is_quenched:
                return
        time.sleep(seconds - int(seconds))

    def wait_for_quench(self, time_to_wait=MAX_WAIT_TIME_FOR_QUENCH) -> Optional[float]:
        # wait 1s before resetting just in case
        time.sleep(1)
        self.reset_interlocks()
        time_start = datetime.datetime.now()
        print(f"{datetime.datetime.now()} Waiting {time_to_wait}s for {self} to quench")

        while not self.is_quenched and (datetime.datetime.now() - time_start).total_seconds() < time_to_wait:
            self.check_abort()
            time.sleep(1)

        time_done = datetime.datetime.now()

        return (time_done - time_start).total_seconds()

    def wait_for_decarads(self):
        if self.is_quenched:
            print(f"Detected {self} quench, waiting {DECARAD_SETTLE_TIME}s for decarads to settle")
            start = datetime.datetime.now()
            while (datetime.datetime.now() - start).total_seconds() < DECARAD_SETTLE_TIME:
                super().check_abort()
                time.sleep(1)

    def check_abort(self):
        super().check_abort()
        if self.decarad.max_raw_dose > RADIATION_LIMIT:
            raise QuenchError("Max Radiation Dose Exceeded")
        if self.has_uncaught_quench():
            raise QuenchError("Potential uncaught quench detected")

    def has_uncaught_quench(self) -> bool:
        return self.is_on and self.rf_mode == RF_MODE_SELA and self.aact <= QUENCH_AMP_THRESHOLD * self.ades

    def quench_process(
        self,
        start_amp: float = 5,
        end_amp: float = 21,
        step_size: float = 0.2,
        step_time: float = 30,
    ):
        self.turn_off()
        self.set_sela_mode()
        self.ades = min(5.0, start_amp)
        self.turn_on()
        self.walk_amp(des_amp=start_amp, step_size=0.2)

        if end_amp > self.ades_max:
            print(f"{end_amp} above AMAX, ramping to {self.ades_max} instead")
            end_amp = self.ades_max

        quenched = False

        while self.ades < end_amp:
            self.check_abort()

            print(f"Walking {self} to quench")
            self.walk_to_quench(
                end_amp=end_amp,
                step_size=step_size,
                step_time=step_time if not quenched else 3 * 60,
            )

            if self.is_quenched:
                quenched = True
                print(f"{datetime.datetime.now()} Detected quench for {self}")
                attempt = 0
                running_times = []
                time_to_quench = self.wait_for_quench()
                running_times.append(time_to_quench)

                # if time_to_quench >= MAX_WAIT_TIME_FOR_QUENCH, the cavity was
                # stable
                while time_to_quench < MAX_WAIT_TIME_FOR_QUENCH and attempt < MAX_QUENCH_RETRIES:
                    super().check_abort()
                    time_to_quench = self.wait_for_quench()
                    running_times.append(time_to_quench)
                    attempt += 1

                if (
                    attempt
                    >= MAX_QUENCH_RETRIES
                    # and not running_times[-1] > running_times[0]
                ):
                    print(f"Attempt: {attempt}")
                    print(f"Running times: {running_times}")
                    raise QuenchError("Quench processing failed")

        while self.wait_for_quench(time_to_wait=QUENCH_STABLE_TIME) < QUENCH_STABLE_TIME:
            print(
                f"{datetime.datetime.now()}{self} made it to target amplitude, "
                f"waiting {QUENCH_STABLE_TIME}s to prove stability"
            )
            super().check_abort()

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
            time.sleep(0.1)

        time_data = self.fault_time_waveform_pv_obj.get()
        fault_data = self.fault_waveform_pv_obj.get()
        time_0 = 0

        # Look for time 0 (quench). These waveforms capture data beforehand
        for time_0, timestamp in enumerate(time_data):
            if timestamp >= 0:
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

        exponential_term = np.polyfit(time_data, np.log(self.pre_quench_amp / fault_data), 1)[0]
        loaded_q = (np.pi * self.frequency) / exponential_term

        thresh_for_quench = LOADED_Q_CHANGE_FOR_QUENCH * saved_loaded_q
        self.cryomodule.logger.info(f"{self} Saved Loaded Q: {saved_loaded_q:.2e}")
        self.cryomodule.logger.info(f"{self} Last recorded amplitude: {fault_data[0]}")
        self.cryomodule.logger.info(f"{self} Threshold: {thresh_for_quench:.2e}")
        self.cryomodule.logger.info(f"{self} Calculated Loaded Q: {loaded_q:.2e}")

        is_real = loaded_q < thresh_for_quench
        print("Validation: ", is_real)

        return is_real

    def reset_quench(self) -> bool:
        is_real = self.validate_quench(wait_for_update=True)
        if not is_real:
            self.cryomodule.logger.info(f"{self} FAKE quench detected, resetting")
            super().reset_interlocks()
            return True

        else:
            self.cryomodule.logger.warning(f"{self} REAL quench detected, not resetting")
            return False
