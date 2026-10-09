import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sc_linac_physics.utils.epics import LazyPV
from sc_linac_physics.utils.sc_linac import linac_utils

if TYPE_CHECKING:
    from cavity import Cavity


class SSA(linac_utils.SCLinacObject):
    """
    Python representation of LCLS II SSAs. This class provides utility functions
    for powering off/on, resetting, and calibrating

    """

    def __init__(self, cavity: "Cavity"):
        """
        @param cavity: the cavity object powered by this SSA
        """

        self.cavity: "Cavity" = cavity
        self._pv_prefix = self.cavity.pv_addr("SSA:")

        # HL cryomodules only have 4 physical SSAs such that they each power two
        # cavities (SSA 1 powers cavities 1 and 5, SSA 2 powers cavities 2 and 6,
        # etc.) Because of that, HL cavities have a subset of shared SSA
        # controls (on/off/reset/voltage). HL SSAs also have a lower expected
        # forward power.
        if self.cavity.cryomodule.is_harmonic_linearizer:
            cavity_num = linac_utils.HL_SSA_MAP[self.cavity.number]
            self.hl_prefix = "ACCL:{LINAC}:{CRYOMODULE}{CAVITY}0:SSA:".format(
                LINAC=self.cavity.linac.name,
                CRYOMODULE=self.cavity.cryomodule.name,
                CAVITY=cavity_num,
            )
            self.fwd_power_lower_limit = 500

            self.ps_volt_setpoint1_pv: str = self.hl_prefix + "PSVoltSetpt1"

            self.ps_volt_setpoint2_pv: str = self.hl_prefix + "PSVoltSetpt2"

            self.status_pv: str = self.hl_prefix + "StatusMsg"
            self.turn_on_pv: str = self.hl_prefix + "PowerOn"
            self.turn_off_pv: str = self.hl_prefix + "PowerOff"
            self.reset_pv: str = self.hl_prefix + "FaultReset"

        else:
            self.fwd_power_lower_limit = 3000
            self.status_pv: str = self.pv_addr("StatusMsg")
            self.turn_on_pv: str = self.pv_addr("PowerOn")
            self.turn_off_pv: str = self.pv_addr("PowerOff")
            self.reset_pv: str = self.pv_addr("FaultReset")

        self.calibration_start_pv: str = self.pv_addr("CALSTRT")

        self.calibration_status_pv: str = self.pv_addr("CALSTS")

        self.cal_result_status_pv: str = self.pv_addr("CALSTAT")

        self.current_slope_pv: str = self.pv_addr("SLOPE")
        self.measured_slope_pv: str = self.pv_addr("SLOPE_NEW")
        self.saved_slope_pv: str = self.pv_addr("SLOPE_SAVE")

        self.drive_max_setpoint_pv: str = self.pv_addr("DRV_MAX_REQ")

        self.drive_max_new_pv: str = self.pv_addr("DRV_MAX_NEW")
        self.drive_max_current_pv: str = self.pv_addr("DRV_MAX")

        self.saved_drive_max_pv: str = self.pv_addr("DRV_MAX_SAVE")

        self.max_fwd_pwr_pv: str = self.pv_addr("CALPWR")

        # Shared between HL cavity pairs (see HL_SSA_SHARED_PVS)
        self.type_pv: str = self.pv_addr("Type")

    def __str__(self):
        return f"{self.cavity} SSA"

    @property
    def pv_prefix(self):
        return self._pv_prefix

    def pv_addr(self, suffix: str):
        """
        @param suffix: The specific PV signal to be appended to the appropriate
                       prefix (that will depend on if the signal is shared
                       between HL SSAs)
        @return: Full PV address of the form ACCL:L{X}B:{CM}{CAV}0:SSA:SUFFIX
        """
        if (
            self.cavity.cryomodule.is_harmonic_linearizer
            and suffix in linac_utils.HL_SSA_SHARED_PVS
        ):
            return self.hl_prefix + suffix
        else:
            return self.pv_prefix + suffix

    status_pv_obj = LazyPV("status_pv")

    @property
    def status_message(self):
        return self.status_pv_obj.get()

    type_pv_obj = LazyPV("type_pv")

    @property
    def rated_power_kw(self) -> Optional[float]:
        """Rated power in kW, from the SSA:Type enum index. Reads one PV.

        None if the index is not in linac_utils.SSA_TYPE_RATED_POWER_KW.
        """
        return linac_utils.ssa_rated_power_kw(int(self.type_pv_obj.get()))

    @property
    def is_on(self) -> bool:
        return self.status_message == linac_utils.SSA_STATUS_ON_VALUE

    @property
    def is_resetting(self) -> bool:
        return (
            self.status_message == linac_utils.SSA_STATUS_RESETTING_FAULTS_VALUE
        )

    @property
    def is_faulted(self) -> bool:
        return self.status_message in [
            linac_utils.SSA_STATUS_FAULTED_VALUE,
            linac_utils.SSA_STATUS_FAULT_RESET_FAILED_VALUE,
        ]

    max_fwd_pwr_pv_obj = LazyPV("max_fwd_pwr_pv")

    @property
    def max_fwd_pwr(self):
        return self.max_fwd_pwr_pv_obj.get()

    saved_drive_max_pv_obj = LazyPV("saved_drive_max_pv")

    @property
    def drive_max(self):
        saved_val = self.saved_drive_max_pv_obj.get()
        return (
            saved_val
            if saved_val
            else (1 if self.cavity.cryomodule.is_harmonic_linearizer else 0.8)
        )

    drive_max_setpoint_pv_obj = LazyPV("drive_max_setpoint_pv")

    @drive_max.setter
    def drive_max(self, value: float):
        self.drive_max_setpoint_pv_obj.put(value)

    def calibrate(self, drive_max, attempt=0):
        """
        @param drive_max: drive max to use for SSA calibration
        @param attempt: recursively incremented upon calibration failure
        @return: None
        """
        self.cavity.logger.info(
            "Attempting SSA calibration with drive max %.2f (attempt %d)",
            drive_max,
            attempt + 1,
            extra={
                "extra_data": {
                    "drive_max": drive_max,
                    "attempt": attempt + 1,
                    "ssa": str(self),
                    "cavity": str(self.cavity),
                }
            },
        )

        if drive_max < 0.4:
            self.cavity.logger.error(
                "Requested drive max too low",
                extra={
                    "extra_data": {
                        "requested_drive_max": drive_max,
                        "minimum_drive_max": 0.4,
                        "ssa": str(self),
                    }
                },
            )
            raise linac_utils.SSACalibrationError(
                f"Requested {self} drive max too low"
            )

        self.cavity.logger.debug("Setting SSA max drive to %.2f", drive_max)
        self.drive_max = drive_max

        try:
            self.cavity.check_abort()
            self.run_calibration()

        except (
            linac_utils.SSACalibrationToleranceError,
            linac_utils.SSACalibrationError,
        ) as e:
            if attempt < 3:
                self.cavity.logger.warning(
                    "SSA calibration failed, retrying with lower drive max",
                    extra={
                        "extra_data": {
                            "current_drive_max": drive_max,
                            "new_drive_max": drive_max - 0.01,
                            "attempt": attempt + 1,
                            "error": str(e),
                            "ssa": str(self),
                        }
                    },
                )
                self.calibrate(drive_max - 0.01, attempt + 1)
            else:
                self.cavity.logger.error(
                    "SSA calibration failed after 3 attempts",
                    extra={
                        "extra_data": {
                            "final_drive_max": drive_max,
                            "total_attempts": attempt + 1,
                            "error": str(e),
                            "ssa": str(self),
                        }
                    },
                )
                raise linac_utils.SSACalibrationError(e)

    ps_volt_setpoint2_pv_obj = LazyPV("ps_volt_setpoint2_pv")

    ps_volt_setpoint1_pv_obj = LazyPV("ps_volt_setpoint1_pv")

    turn_on_pv_obj = LazyPV("turn_on_pv")

    def turn_on(self):
        if not self.is_on:
            # Check to see if SSA is hard faulted first (cls.reset() tries a set
            # number of times before raising an error)
            self.reset()

            self.cavity.logger.info("Turning SSA on")
            self.turn_on_pv_obj.put(1)

            linac_utils.wait_until(
                lambda: self.is_on,
                timeout=linac_utils.SSA_TURN_ON_TIMEOUT_S,
                description=f"{self} to turn on",
                error_class=linac_utils.SSAFaultError,
                check_abort=self.cavity.check_abort,
                on_poll=lambda: self._log_wait("Waiting for SSA to turn on"),
            )

        if self.cavity.cryomodule.is_harmonic_linearizer:
            self.cavity.logger.debug(
                "Setting HL SSA power supply setpoints to %d",
                linac_utils.HL_SSA_PS_SETPOINT,
            )
            self.ps_volt_setpoint2_pv_obj.put(linac_utils.HL_SSA_PS_SETPOINT)
            self.ps_volt_setpoint1_pv_obj.put(linac_utils.HL_SSA_PS_SETPOINT)

        self.cavity.logger.info("SSA successfully turned on")

    def _log_wait(self, message: str):
        self.cavity.logger.debug(
            message,
            extra={
                "extra_data": {
                    "status_message": self.status_message,
                    "ssa": str(self),
                }
            },
        )

    turn_off_pv_obj = LazyPV("turn_off_pv")

    def turn_off(self):
        if self.is_on:
            self.cavity.logger.info("Turning SSA off")
            self.turn_off_pv_obj.put(1)

            linac_utils.wait_until(
                lambda: not self.is_on,
                timeout=linac_utils.SSA_TURN_OFF_TIMEOUT_S,
                description=f"{self} to turn off",
                error_class=linac_utils.SSAFaultError,
                check_abort=self.cavity.check_abort,
                on_poll=lambda: self._log_wait("Waiting for SSA to turn off"),
            )

        self.cavity.logger.info("SSA successfully turned off")

    reset_pv_obj = LazyPV("reset_pv")

    def reset(self):
        reset_attempt = 0
        while self.is_faulted:
            self.cavity.check_abort()
            self.cavity.logger.info(
                "Resetting SSA (attempt %d)",
                reset_attempt + 1,
                extra={
                    "extra_data": {
                        "attempt": reset_attempt + 1,
                        "status_message": self.status_message,
                        "ssa": str(self),
                    }
                },
            )
            self.reset_pv_obj.put(1)

            self.wait_while_resetting()

            if (
                self.is_faulted
                and reset_attempt >= linac_utils.INTERLOCK_RESET_ATTEMPTS
            ):
                self.cavity.logger.error(
                    "SSA failed to reset after %d attempts",
                    linac_utils.INTERLOCK_RESET_ATTEMPTS,
                    extra={
                        "extra_data": {
                            "total_attempts": linac_utils.INTERLOCK_RESET_ATTEMPTS,
                            "final_status": self.status_message,
                            "ssa": str(self),
                        }
                    },
                )
                raise linac_utils.SSAFaultError(
                    f"{self} failed to reset {linac_utils.INTERLOCK_RESET_ATTEMPTS}x"
                )

            reset_attempt += 1

        self.cavity.logger.info("SSA successfully reset")

    def wait_while_resetting(self):
        start = datetime.now()
        while self.is_resetting:
            self.cavity.check_abort()
            elapsed = (datetime.now() - start).total_seconds()
            self.cavity.logger.debug(
                "Waiting for SSA to finish resetting (%.0fs elapsed)",
                elapsed,
                extra={
                    "extra_data": {
                        "elapsed_seconds": elapsed,
                        "status_message": self.status_message,
                        "ssa": str(self),
                    }
                },
            )
            time.sleep(5)
            if elapsed >= 90:
                self.cavity.logger.error(
                    "SSA reset timeout",
                    extra={
                        "extra_data": {
                            "elapsed_seconds": elapsed,
                            "timeout_seconds": 90,
                            "final_status": self.status_message,
                            "ssa": str(self),
                        }
                    },
                )
                raise linac_utils.SSAFaultError(
                    f"{self} took too long to reset, inspect and try again"
                )

    calibration_start_pv_obj = LazyPV("calibration_start_pv")

    def start_calibration(self):
        self.calibration_start_pv_obj.put(1, wait=False)

    calibration_status_pv_obj = LazyPV(
        "calibration_status_pv", connection_timeout=10
    )

    @property
    def calibration_status(self):
        return self.calibration_status_pv_obj.get(timeout=10)

    @property
    def calibration_running(self) -> bool:
        return (
            self.calibration_status == linac_utils.SSA_CALIBRATION_RUNNING_VALUE
        )

    @property
    def calibration_crashed(self) -> bool:
        return (
            self.calibration_status == linac_utils.SSA_CALIBRATION_CRASHED_VALUE
        )

    cal_result_status_pv_obj = LazyPV("cal_result_status_pv")

    @property
    def calibration_result_good(self) -> bool:
        return (
            self.cal_result_status_pv_obj.get()
            == linac_utils.SSA_RESULT_GOOD_STATUS_VALUE
        )

    def run_calibration(self, save_slope: bool = False):
        """
        Runs the SSA through its range and finds the slope that describes
        the relationship between SSA drive signal and output power
        @param save_slope: Whether to update the saved slope PV with the newly
                           calculated value or not
        @return: None
        """

        self.reset()
        self.turn_on()

        self.cavity.reset_interlocks()

        self.cavity.logger.info(
            "Starting SSA calibration",
            extra={
                "extra_data": {
                    "save_slope": save_slope,
                    "drive_max": self.drive_max,
                    "ssa": str(self),
                }
            },
        )
        self.start_calibration()
        time.sleep(2)

        # CHECK: this loop had no check_abort() before. With it, an abort
        # mid-calibration runs cavity.check_abort() -> turn_off(), then
        # raises CavityAbortError. Is turning RF off mid-sweep acceptable?
        linac_utils.wait_until(
            lambda: not self.calibration_running,
            timeout=linac_utils.SSA_CALIBRATION_TIMEOUT_S,
            description=f"{self} calibration to finish",
            error_class=linac_utils.SSACalibrationError,
            check_abort=self.cavity.check_abort,
            on_poll=lambda: self.cavity.logger.debug(
                "Waiting for SSA calibration to complete",
                extra={
                    "extra_data": {
                        "calibration_status": self.calibration_status,
                        "ssa": str(self),
                    }
                },
            ),
        )
        time.sleep(2)

        if self.calibration_crashed:
            self.cavity.logger.error(
                "SSA calibration crashed",
                extra={
                    "extra_data": {
                        "calibration_status": self.calibration_status,
                        "ssa": str(self),
                    }
                },
            )
            raise linac_utils.SSACalibrationError(f"{self} calibration crashed")

        if not self.calibration_result_good:
            self.cavity.logger.error(
                "SSA calibration result not good",
                extra={
                    "extra_data": {
                        "cal_result_status": self.cal_result_status_pv_obj.get(),
                        "ssa": str(self),
                    }
                },
            )
            raise linac_utils.SSACalibrationError(
                f"{self} calibration result not good"
            )

        if self.max_fwd_pwr < self.fwd_power_lower_limit:
            self.cavity.logger.error(
                "SSA forward power too low",
                extra={
                    "extra_data": {
                        "max_fwd_pwr": self.max_fwd_pwr,
                        "lower_limit": self.fwd_power_lower_limit,
                        "ssa": str(self),
                    }
                },
            )
            raise linac_utils.SSACalibrationToleranceError(
                f"{self.cavity} SSA forward power too low"
            )

        if not self.measured_slope_in_tolerance:
            self.cavity.logger.error(
                "SSA slope out of tolerance",
                extra={
                    "extra_data": {
                        "measured_slope": self.measured_slope,
                        "lower_limit": linac_utils.SSA_SLOPE_LOWER_LIMIT,
                        "upper_limit": linac_utils.SSA_SLOPE_UPPER_LIMIT,
                        "ssa": str(self),
                    }
                },
            )
            raise linac_utils.SSACalibrationToleranceError(
                f"{self.cavity} SSA Slope out of tolerance"
            )

        self.cavity.logger.info(
            "Pushing SSA calibration results",
            extra={
                "extra_data": {
                    "measured_slope": self.measured_slope,
                    "max_fwd_pwr": self.max_fwd_pwr,
                    "ssa": str(self),
                }
            },
        )
        self.cavity.push_ssa_slope()

        if save_slope:
            self.cavity.logger.info("Saving SSA slope")
            self.cavity.save_ssa_slope()

        self.cavity.logger.info(
            "SSA calibration completed successfully",
            extra={
                "extra_data": {
                    "measured_slope": self.measured_slope,
                    "max_fwd_pwr": self.max_fwd_pwr,
                    "drive_max": self.drive_max,
                    "ssa": str(self),
                }
            },
        )

    current_slope_pv_obj = LazyPV("current_slope_pv")

    @property
    def current_slope(self):
        """Currently active SSA slope (SLOPE PV), i.e. the value in use by the cavity."""
        return self.current_slope_pv_obj.get()

    measured_slope_pv_obj = LazyPV("measured_slope_pv")

    @property
    def measured_slope(self):
        return self.measured_slope_pv_obj.get()

    @property
    def measured_slope_in_tolerance(self) -> bool:
        return (
            linac_utils.SSA_SLOPE_LOWER_LIMIT
            < self.measured_slope
            < linac_utils.SSA_SLOPE_UPPER_LIMIT
        )
