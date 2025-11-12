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
from sc_linac_physics.utils.sc_linac.linac_utils import (
    QuenchError,
    RF_MODE_SELA,
)


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
    def logger(self):
        """Convenience property to access cryomodule logger."""
        return self.cryomodule.logger

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

    def reset_interlocks(
        self, wait: int = 0, attempt: int = 0, time_after_reset=1
    ):
        """Overwriting base function to skip wait/reset cycle."""
        self.logger.info(f"Resetting interlocks for cavity {self.number}")

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
        """Walk cavity amplitude until quench or end_amp reached."""
        self.logger.debug(
            f"Cavity {self.number}: Walking to quench "
            f"(end_amp={end_amp}, step={step_size}, time={step_time}s)"
        )
        self.reset_interlocks()

        steps = 0
        while not self.is_quenched and self.ades < end_amp:
            self.check_abort()
            old_ades = self.ades
            self.ades = min(self.ades + step_size, end_amp)
            steps += 1

            if steps % 10 == 0:  # Log every 10 steps
                self.logger.debug(
                    f"Cavity {self.number}: Step {steps}, "
                    f"ADES: {old_ades:.2f} → {self.ades:.2f} MV"
                )

            self.wait(step_time - DECARAD_SETTLE_TIME)
            self.wait_for_decarads()

        if self.is_quenched:
            self.logger.info(
                f"Cavity {self.number}: Quench detected at {self.ades:.2f} MV "
                f"after {steps} steps"
            )
        else:
            self.logger.info(
                f"Cavity {self.number}: Reached end amplitude {self.ades:.2f} MV "
                f"without quench"
            )

    def wait(self, seconds: float):
        """Wait for specified seconds, checking for quench."""
        for _ in range(int(seconds)):
            self.check_abort()
            time.sleep(1)
            if self.is_quenched:
                return
        time.sleep(seconds - int(seconds))

    def wait_for_quench(
        self, time_to_wait=MAX_WAIT_TIME_FOR_QUENCH
    ) -> Optional[float]:
        """
        Wait for cavity to quench.

        Args:
            time_to_wait: Maximum time to wait in seconds

        Returns:
            Time elapsed in seconds
        """
        # Wait 1s before resetting just in case
        time.sleep(1)
        self.reset_interlocks()
        time_start = datetime.datetime.now()

        self.logger.debug(
            f"Cavity {self.number}: Waiting up to {time_to_wait}s for quench"
        )

        while (
            not self.is_quenched
            and (datetime.datetime.now() - time_start).total_seconds()
            < time_to_wait
        ):
            self.check_abort()
            time.sleep(1)

        time_done = datetime.datetime.now()
        elapsed = (time_done - time_start).total_seconds()

        if self.is_quenched:
            self.logger.info(
                f"Cavity {self.number}: Quenched after {elapsed:.1f}s"
            )
        else:
            self.logger.debug(
                f"Cavity {self.number}: No quench after {elapsed:.1f}s"
            )

        return elapsed

    def wait_for_decarads(self):
        """Wait for decarad sensors to settle after quench."""
        if self.is_quenched:
            self.logger.debug(
                f"Cavity {self.number}: Waiting {DECARAD_SETTLE_TIME}s "
                f"for decarads to settle"
            )
            start = datetime.datetime.now()
            while (
                datetime.datetime.now() - start
            ).total_seconds() < DECARAD_SETTLE_TIME:
                super().check_abort()
                time.sleep(1)

    def check_abort(self):
        """Check abort conditions including radiation and uncaught quench."""
        super().check_abort()

        if self.decarad.max_raw_dose > RADIATION_LIMIT:
            self.logger.error(
                f"Cavity {self.number}: Max radiation dose exceeded "
                f"({self.decarad.max_raw_dose:.2e} > {RADIATION_LIMIT:.2e})"
            )
            raise QuenchError("Max Radiation Dose Exceeded")

        if self.has_uncaught_quench():
            self.logger.error(
                f"Cavity {self.number}: Potential uncaught quench detected "
                f"(AACT={self.aact:.2f}, threshold={QUENCH_AMP_THRESHOLD * self.ades:.2f})"
            )
            raise QuenchError("Potential uncaught quench detected")

    def has_uncaught_quench(self) -> bool:
        """Check if cavity has an uncaught quench condition."""
        return (
            self.is_on
            and self.rf_mode == RF_MODE_SELA
            and self.aact <= QUENCH_AMP_THRESHOLD * self.ades
        )

    def quench_process(
        self,
        start_amp: float = 5,
        end_amp: float = 21,
        step_size: float = 0.2,
        step_time: float = 30,
    ):
        """
        Process cavity through quench cycling.

        Args:
            start_amp: Starting amplitude in MV
            end_amp: Target end amplitude in MV
            step_size: Amplitude step size in MV
            step_time: Time per step in seconds
        """
        self.logger.info("=" * 60)
        self.logger.info(
            f"Cavity {self.number}: Starting quench process "
            f"({start_amp} → {end_amp} MV, step={step_size} MV, time={step_time}s)"
        )
        self.logger.info("=" * 60)

        self.turn_off()
        self.set_sela_mode()
        self.ades = min(5.0, start_amp)
        self.turn_on()
        self.walk_amp(des_amp=start_amp, step_size=0.2)

        if end_amp > self.ades_max:
            self.logger.warning(
                f"Cavity {self.number}: Requested end_amp {end_amp} > ADES_MAX "
                f"{self.ades_max}, using {self.ades_max} instead"
            )
            end_amp = self.ades_max

        quenched = False

        while self.ades < end_amp:
            self.check_abort()

            self.logger.info(
                f"Cavity {self.number}: Walking to quench at {self.ades:.2f} MV"
            )
            self.walk_to_quench(
                end_amp=end_amp,
                step_size=step_size,
                step_time=step_time if not quenched else 3 * 60,
            )

            if self.is_quenched:
                quenched = True
                self.logger.info(
                    f"Cavity {self.number}: Quench detected, entering retry loop"
                )
                attempt = 0
                running_times = []
                time_to_quench = self.wait_for_quench()
                running_times.append(time_to_quench)

                # If time_to_quench >= MAX_WAIT_TIME_FOR_QUENCH, cavity was stable
                while (
                    time_to_quench < MAX_WAIT_TIME_FOR_QUENCH
                    and attempt < MAX_QUENCH_RETRIES
                ):
                    super().check_abort()
                    self.logger.debug(
                        f"Cavity {self.number}: Retry attempt {attempt + 1}/"
                        f"{MAX_QUENCH_RETRIES}"
                    )
                    time_to_quench = self.wait_for_quench()
                    running_times.append(time_to_quench)
                    attempt += 1

                if attempt >= MAX_QUENCH_RETRIES:
                    self.logger.error(
                        f"Cavity {self.number}: Failed after {attempt} attempts. "
                        f"Running times: {[f'{t:.1f}s' for t in running_times]}"
                    )
                    raise QuenchError("Quench processing failed")

                self.logger.info(
                    f"Cavity {self.number}: Passed retry loop after {attempt} "
                    f"attempts (times: {[f'{t:.1f}s' for t in running_times]})"
                )

        # Final stability check
        self.logger.info(
            f"Cavity {self.number}: Reached target {end_amp} MV, "
            f"proving {QUENCH_STABLE_TIME}s stability"
        )
        while (
            self.wait_for_quench(time_to_wait=QUENCH_STABLE_TIME)
            < QUENCH_STABLE_TIME
        ):
            self.logger.warning(
                f"Cavity {self.number}: Quenched during stability check, retrying"
            )
            super().check_abort()

        self.logger.info("=" * 60)
        self.logger.info(
            f"Cavity {self.number}: Quench processing completed successfully"
        )
        self.logger.info("=" * 60)

    def validate_quench(self, wait_for_update: bool = False) -> bool:
        """
        Parse fault waveforms to calculate loaded Q and determine if quench was real.

        Uses exponential decay analysis to calculate loaded Q from fault data.
        A real quench shows a significant decrease in loaded Q.

        DERIVATION NOTES:
        A(t) = A0 * e^((-π * f * t)/Q_loaded)
        ln(A0/A(t)) = (π * f * t)/Q_loaded
        slope = polyfit(t, ln(A0/A(t)), 1)[0] = (π * f)/Q_loaded
        Q_loaded = (π * f) / slope

        Args:
            wait_for_update: If True, wait 0.1s for waveforms to update

        Returns:
            True if quench appears real, False if likely spurious
        """
        if wait_for_update:
            self.logger.debug(
                f"Cavity {self.number}: Waiting 0.1s for waveform update"
            )
            time.sleep(0.1)

        time_data = self.fault_time_waveform_pv_obj.get()
        fault_data = self.fault_waveform_pv_obj.get()
        time_0 = 0

        # Look for time 0 (quench). These waveforms capture data before quench
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

        try:
            exponential_term = np.polyfit(
                time_data, np.log(self.pre_quench_amp / fault_data), 1
            )[0]
            loaded_q = (np.pi * self.frequency) / exponential_term
        except (ValueError, RuntimeWarning) as e:
            self.logger.error(
                f"Cavity {self.number}: Error calculating loaded Q: {e}"
            )
            # Conservative: assume real quench if we can't calculate
            return True

        thresh_for_quench = LOADED_Q_CHANGE_FOR_QUENCH * saved_loaded_q
        is_real = loaded_q < thresh_for_quench

        # Combined validation log entry
        validation_msg = (
            f"Cavity {self.number} Quench Validation:\n"
            f"  Saved Loaded Q:      {saved_loaded_q:.2e}\n"
            f"  Calculated Loaded Q: {loaded_q:.2e}\n"
            f"  Threshold:           {thresh_for_quench:.2e}\n"
            f"  Pre-quench Amp:      {self.pre_quench_amp:.4f} MV\n"
            f"  Decay samples:       {len(fault_data)}\n"
            f"  Result:              {'REAL' if is_real else 'FAKE'}"
        )
        self.logger.info(validation_msg)

        return is_real

    def reset_quench(self) -> bool:
        """
        Validate and potentially reset a quench.

        Returns:
            True if reset was issued (fake quench), False otherwise (real quench)
        """
        self.logger.info(f"Cavity {self.number}: Validating quench...")

        is_real = self.validate_quench(wait_for_update=True)

        if not is_real:
            self.logger.info(
                f"Cavity {self.number}: FAKE quench detected, issuing reset"
            )
            super().reset_interlocks()
            return True
        else:
            self.logger.warning(
                f"Cavity {self.number}: REAL quench detected, NOT resetting"
            )
            return False
