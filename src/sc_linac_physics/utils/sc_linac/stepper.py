import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from numpy import sign

from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac import linac_utils

if TYPE_CHECKING:
    from cavity import Cavity


class StepperTuner(linac_utils.SCLinacObject):
    """
    Python representation of LCLS II stepper tuners. This class provides wrappers
    for common stepper controls including sending move commands, checking movement
    status, and retrieving stored movement parameters
    """

    def __init__(self, cavity: "Cavity"):
        """
        @param cavity: the cavity object tuned by this stepper
        """

        self.cavity: "Cavity" = cavity
        self._pv_prefix: str = self.cavity.pv_addr("STEP:")

        self.move_pos_pv: str = self.pv_addr("MOV_REQ_POS")
        self._move_pos_pv_obj: Optional[PV] = None

        self.move_neg_pv: str = self.pv_addr("MOV_REQ_NEG")
        self._move_neg_pv_obj: Optional[PV] = None

        self.abort_pv: str = self.pv_addr("ABORT_REQ")
        self._abort_pv_obj: Optional[PV] = None

        self.step_des_pv: str = self.pv_addr("NSTEPS")
        self._step_des_pv_obj: Optional[PV] = None

        self.max_steps_pv: str = self.pv_addr("NSTEPS.DRVH")
        self._max_steps_pv_obj: Optional[PV] = None

        self.speed_pv: str = self.pv_addr("VELO")
        self._speed_pv_obj: Optional[PV] = None

        self.step_tot_pv: str = self.pv_addr("REG_TOTABS")
        self.step_signed_pv: str = self.pv_addr("REG_TOTSGN")
        self.reset_tot_pv: str = self.pv_addr("TOTABS_RESET")

        self.reset_signed_pv: str = self.pv_addr("TOTSGN_RESET")
        self._reset_signed_pv_obj: Optional[PV] = None

        self.steps_cold_landing_pv: str = self.pv_addr("NSTEPS_COLD")
        self.push_signed_cold_pv: str = self.pv_addr("PUSH_NSTEPS_COLD.PROC")
        self.push_signed_park_pv: str = self.pv_addr("PUSH_NSTEPS_PARK.PROC")

        self.motor_moving_pv: str = self.pv_addr("STAT_MOV")
        self._motor_moving_pv_obj: Optional[PV] = None

        self.motor_done_pv: str = self.pv_addr("STAT_DONE")

        self.limit_switch_a_pv: str = self.pv_addr("STAT_LIMA")
        self._limit_switch_a_pv_obj: Optional[PV] = None

        self.limit_switch_b_pv: str = self.pv_addr("STAT_LIMB")
        self._limit_switch_b_pv_obj: Optional[PV] = None

        self.hz_per_microstep_pv: str = self.pv_addr("SCALE")
        self._hz_per_microstep_pv_obj: Optional[PV] = None

        self.abort_flag: bool = False

    def __str__(self):
        return f"{self.cavity} Stepper Tuner"

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def hz_per_microstep_pv_obj(self) -> PV:
        if not self._hz_per_microstep_pv_obj:
            self._hz_per_microstep_pv_obj = PV(self.hz_per_microstep_pv)
        return self._hz_per_microstep_pv_obj

    @property
    def hz_per_microstep(self):
        return abs(self.hz_per_microstep_pv_obj.get())

    def check_abort(self):
        """
        This function raises an error if either a stepper abort or a cavity abort
        has been requested.
        @return: None
        """
        self.cavity.check_abort()
        if self.abort_flag:
            self.cavity.logger.warning("Stepper abort requested")
            self.abort()
            self.abort_flag = False
            raise linac_utils.StepperAbortError(f"Abort requested for {self}")

    def abort(self):
        self.cavity.logger.info("Aborting stepper movement")
        if not self._abort_pv_obj:
            self._abort_pv_obj = PV(self.abort_pv)
        self._abort_pv_obj.put(1)

    def move_positive(self):
        if not self._move_pos_pv_obj:
            self._move_pos_pv_obj = PV(self.move_pos_pv)
        self._move_pos_pv_obj.put(1)

    def move_negative(self):
        if not self._move_neg_pv_obj:
            self._move_neg_pv_obj = PV(self.move_neg_pv)
        self._move_neg_pv_obj.put(1)

    @property
    def step_des_pv_obj(self):
        if not self._step_des_pv_obj:
            self._step_des_pv_obj = PV(self.step_des_pv)
        return self._step_des_pv_obj

    @property
    def step_des(self):
        return self.step_des_pv_obj.get()

    @step_des.setter
    def step_des(self, value: int):
        self.step_des_pv_obj.put(value)

    @property
    def motor_moving(self) -> bool:
        if not self._motor_moving_pv_obj:
            self._motor_moving_pv_obj = PV(self.motor_moving_pv)
        return self._motor_moving_pv_obj.get() == 1

    def reset_signed_steps(self):
        self.cavity.logger.debug("Resetting stepper signed steps counter")
        if not self._reset_signed_pv_obj:
            self._reset_signed_pv_obj = PV(self.reset_signed_pv)
        self._reset_signed_pv_obj.put(0)

    @property
    def limit_switch_a_pv_obj(self):
        if not self._limit_switch_a_pv_obj:
            self._limit_switch_a_pv_obj = PV(self.limit_switch_a_pv)
        return self._limit_switch_a_pv_obj

    @property
    def limit_switch_b_pv_obj(self):
        if not self._limit_switch_b_pv_obj:
            self._limit_switch_b_pv_obj = PV(self.limit_switch_b_pv)
        return self._limit_switch_b_pv_obj

    @property
    def on_limit_switch(self) -> bool:
        return (
            self.limit_switch_a_pv_obj.get()
            == linac_utils.STEPPER_ON_LIMIT_SWITCH_VALUE
            or self.limit_switch_b_pv_obj.get()
            == linac_utils.STEPPER_ON_LIMIT_SWITCH_VALUE
        )

    @property
    def max_steps_pv_obj(self) -> PV:
        if not self._max_steps_pv_obj:
            self._max_steps_pv_obj = PV(self.max_steps_pv)
        return self._max_steps_pv_obj

    @property
    def max_steps(self):
        return self.max_steps_pv_obj.get()

    @max_steps.setter
    def max_steps(self, value: int):
        self.max_steps_pv_obj.put(value)

    @property
    def speed_pv_obj(self):
        if not self._speed_pv_obj:
            self._speed_pv_obj = PV(self.speed_pv)
        return self._speed_pv_obj

    @property
    def speed(self):
        return self.speed_pv_obj.get()

    @speed.setter
    def speed(self, value: int):
        self.speed_pv_obj.put(value)

    def restore_defaults(self):
        self.cavity.logger.debug(
            "Restoring stepper default settings",
            extra={
                "extra_data": {
                    "default_max_steps": linac_utils.DEFAULT_STEPPER_MAX_STEPS,
                    "default_speed": linac_utils.DEFAULT_STEPPER_SPEED,
                    "stepper": str(self),
                }
            },
        )
        self.max_steps = linac_utils.DEFAULT_STEPPER_MAX_STEPS
        self.speed = linac_utils.DEFAULT_STEPPER_SPEED

    def move(
        self,
        num_steps: int,
        max_steps: int = linac_utils.DEFAULT_STEPPER_MAX_STEPS,
        speed: int = linac_utils.DEFAULT_STEPPER_SPEED,
        change_limits: bool = True,
        check_detune: bool = True,
    ):
        """
        :param num_steps: positive for increasing cavity length, negative for decreasing
        :param max_steps: the maximum number of steps allowed at once
        :param speed: the speed of the motor in steps/second
        :param change_limits: whether to change the speed and steps
        :param check_detune: whether to check for valid detune after each move
        :return: None
        """

        self.check_abort()
        max_steps = abs(max_steps)

        if change_limits:
            # on the off chance that someone tries to write a negative maximum
            self.max_steps = max_steps

            # make sure that we don't exceed the speed limit as defined by the tuner experts
            requested_speed = (
                speed
                if speed < linac_utils.MAX_STEPPER_SPEED
                else linac_utils.MAX_STEPPER_SPEED
            )

            if requested_speed != speed:
                self.cavity.logger.warning(
                    "Requested speed exceeds maximum, limiting to %d steps/s",
                    linac_utils.MAX_STEPPER_SPEED,
                    extra={
                        "extra_data": {
                            "requested_speed": speed,
                            "max_speed": linac_utils.MAX_STEPPER_SPEED,
                            "stepper": str(self),
                        }
                    },
                )

            self.speed = requested_speed

        if abs(num_steps) <= max_steps:
            self.cavity.logger.info(
                "Moving stepper %d steps (within max %d)",
                abs(num_steps),
                max_steps,
                extra={
                    "extra_data": {
                        "num_steps": num_steps,
                        "max_steps": max_steps,
                        "speed": self.speed,
                        "check_detune": check_detune,
                        "stepper": str(self),
                    }
                },
            )
            self.step_des = abs(num_steps)
            self.issue_move_command(num_steps, check_detune=check_detune)
            self.restore_defaults()
        else:
            self.cavity.logger.info(
                "Moving stepper %d steps (exceeds max %d, splitting move)",
                abs(num_steps),
                max_steps,
                extra={
                    "extra_data": {
                        "total_steps": num_steps,
                        "max_steps": max_steps,
                        "first_move_steps": max_steps,
                        "remaining_steps": abs(num_steps) - max_steps,
                        "stepper": str(self),
                    }
                },
            )
            self.step_des = max_steps
            self.issue_move_command(num_steps, check_detune=check_detune)

            remaining_steps = num_steps - (sign(num_steps) * max_steps)
            self.cavity.logger.debug(
                "Continuing with remaining %d steps", remaining_steps
            )

            self.move(
                remaining_steps,
                max_steps,
                speed,
                change_limits=False,
                check_detune=check_detune,
            )

    def issue_move_command(self, num_steps: int, check_detune: bool = True):
        """
        Determine whether to move positive or negative depending on the requested
        number of steps
        @param num_steps: Signed number of steps to move the stepper
        @param check_detune: Whether to check for a valid detune during move
                             (this should only be false when we cannot see
                             cavity frequency, i.e. when we are not at 2 K)
        @return: None
        """

        # this is necessary because the tuners for the HLs move the other direction
        original_steps = num_steps
        if self.cavity.cryomodule.is_harmonic_linearizer:
            num_steps *= -1
            self.cavity.logger.debug(
                "Harmonic linearizer detected, inverting step direction (%d -> %d)",
                original_steps,
                num_steps,
            )

        direction = "positive" if sign(num_steps) == 1 else "negative"
        self.cavity.logger.info(
            "Issuing stepper move command: %d steps %s",
            abs(num_steps),
            direction,
            extra={
                "extra_data": {
                    "num_steps": num_steps,
                    "direction": direction,
                    "check_detune": check_detune,
                    "is_harmonic_linearizer": self.cavity.cryomodule.is_harmonic_linearizer,
                    "stepper": str(self),
                }
            },
        )

        if sign(num_steps) == 1:
            self.move_positive()
        else:
            self.move_negative()

        self.cavity.logger.debug("Waiting 5s for motor to start moving")
        time.sleep(5)

        move_start_time = datetime.now()
        while self.motor_moving:
            self.check_abort()
            if check_detune:
                self.cavity.check_detune()

            elapsed = (datetime.now() - move_start_time).total_seconds()
            self.cavity.logger.debug(
                "Motor still moving (%.0fs elapsed)",
                elapsed,
                extra={
                    "extra_data": {
                        "elapsed_seconds": elapsed,
                        "stepper": str(self),
                    }
                },
            )
            time.sleep(5)

        total_move_time = (datetime.now() - move_start_time).total_seconds()
        self.cavity.logger.info(
            "Stepper motor completed move (%.1fs total)",
            total_move_time,
            extra={
                "extra_data": {
                    "total_move_time_seconds": total_move_time,
                    "stepper": str(self),
                }
            },
        )

        # the motor can be done moving for good OR bad reasons
        if self.on_limit_switch:
            self.cavity.logger.error(
                "Stepper motor hit limit switch",
                extra={
                    "extra_data": {
                        "limit_switch_a": self.limit_switch_a_pv_obj.get(),
                        "limit_switch_b": self.limit_switch_b_pv_obj.get(),
                        "stepper": str(self),
                    }
                },
            )
            raise linac_utils.StepperError(
                f"{self.cavity} stepper motor on limit switch"
            )
