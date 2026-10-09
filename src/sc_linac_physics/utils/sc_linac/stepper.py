import time
from datetime import datetime
from typing import TYPE_CHECKING

from numpy import sign

from sc_linac_physics.utils.epics import LazyPV
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

        self.move_neg_pv: str = self.pv_addr("MOV_REQ_NEG")

        self.abort_pv: str = self.pv_addr("ABORT_REQ")

        self.step_des_pv: str = self.pv_addr("NSTEPS")

        self.max_steps_pv: str = self.pv_addr("NSTEPS.DRVH")

        self.speed_pv: str = self.pv_addr("VELO")

        self.step_tot_pv: str = self.pv_addr("REG_TOTABS")
        self.step_signed_pv: str = self.pv_addr("REG_TOTSGN")
        self.reset_tot_pv: str = self.pv_addr("TOTABS_RESET")

        self.reset_signed_pv: str = self.pv_addr("TOTSGN_RESET")

        self.steps_cold_landing_pv: str = self.pv_addr("NSTEPS_COLD")
        self.push_signed_cold_pv: str = self.pv_addr("PUSH_NSTEPS_COLD.PROC")
        self.push_signed_park_pv: str = self.pv_addr("PUSH_NSTEPS_PARK.PROC")

        self.motor_moving_pv: str = self.pv_addr("STAT_MOV")

        self.motor_done_pv: str = self.pv_addr("STAT_DONE")

        self.limit_switch_a_pv: str = self.pv_addr("STAT_LIMA")

        self.limit_switch_b_pv: str = self.pv_addr("STAT_LIMB")

        self.hz_per_microstep_pv: str = self.pv_addr("SCALE")

        # SCALE is a derived, read-only calc-record output (SCALE = SCALE_CALC.B / 256).
        # To persist a measured scale we write the Hz-per-full-step field and let the
        # IOC recompute SCALE. See set_hz_per_microstep().
        self.hz_per_step_calc_pv: str = self.pv_addr("SCALE_CALC.B")

        # Stepper-only abort: writes ABORT_REQ and leaves RF as it is.
        # Cavity.abort_flag also stops the motor, but turns RF off too.
        # Kept separate on purpose (decided 2026-10-08). Dropping RF does
        # not help stop the motor, and leaving it on makes retuning after
        # the abort easier. The RF commissioning frequency-tuning Abort
        # button uses this flag.
        self.abort_flag: bool = False
        # Per move(): whether ABORT_REQ was written, and whether move()
        # changed NSTEPS.DRVH / VELO. Read by _clean_up_failed_move().
        self._abort_written: bool = False
        self._limits_changed: bool = False

    def __str__(self):
        return f"{self.cavity} Stepper Tuner"

    @property
    def pv_prefix(self):
        return self._pv_prefix

    hz_per_microstep_pv_obj = LazyPV("hz_per_microstep_pv")

    @property
    def hz_per_microstep(self):
        return abs(self.hz_per_microstep_pv_obj.get())

    hz_per_step_calc_pv_obj = LazyPV("hz_per_step_calc_pv")

    def set_hz_per_microstep(self, hz_per_microstep: float) -> None:
        """Persist a measured stepper scale.

        STEP:SCALE is a derived, read-only calc-record output
        (SCALE = SCALE_CALC.B / 256), so writing SCALE directly is silently
        reverted by the IOC. Instead we write the Hz-per-full-step field
        (SCALE_CALC.B) and let the IOC recompute SCALE.
        """
        self.hz_per_step_calc_pv_obj.put(
            hz_per_microstep * linac_utils.MICROSTEPS_PER_STEP
        )

    step_signed_pv_obj = LazyPV("step_signed_pv")

    steps_cold_landing_pv_obj = LazyPV("steps_cold_landing_pv")

    def check_abort(self):
        """
        This function raises an error if either a stepper abort or a cavity abort
        has been requested.

        A pending cavity abort_flag writes the stepper ABORT_REQ first.
        Cavity.check_abort() runs turn_off() and waits for RF off before it
        raises, so without this the motor would keep moving through that
        wait. TuneCavity.check_abort already writes ABORT_REQ first in the
        same way.
        @return: None
        """
        if self.cavity.abort_flag:
            # A failed ABORT_REQ must not skip the cavity abort below, which
            # turns RF off. Log it and carry on.
            try:
                self.abort()
            except Exception as e:
                self.cavity.logger.error(
                    "Failed to write stepper ABORT_REQ before cavity abort: %s",
                    e,
                )
        self.cavity.check_abort()
        if self.abort_flag:
            self.cavity.logger.warning("Stepper abort requested")
            self.abort()
            self.abort_flag = False
            raise linac_utils.StepperAbortError(f"Abort requested for {self}")

    abort_pv_obj = LazyPV("abort_pv")

    def abort(self):
        self.cavity.logger.info("Aborting stepper movement")
        self.abort_pv_obj.put(1)
        self._abort_written = True

    move_pos_pv_obj = LazyPV("move_pos_pv")

    def move_positive(self):
        self.move_pos_pv_obj.put(1, wait=False)

    move_neg_pv_obj = LazyPV("move_neg_pv")

    def move_negative(self):
        self.move_neg_pv_obj.put(1, wait=False)

    step_des_pv_obj = LazyPV("step_des_pv")

    @property
    def step_des(self):
        return self.step_des_pv_obj.get()

    @step_des.setter
    def step_des(self, value: int):
        self.step_des_pv_obj.put(value)

    motor_moving_pv_obj = LazyPV("motor_moving_pv")

    @property
    def motor_moving(self) -> bool:
        return self.motor_moving_pv_obj.get() == 1

    reset_signed_pv_obj = LazyPV("reset_signed_pv")

    def reset_signed_steps(self):
        self.cavity.logger.debug("Resetting stepper signed steps counter")
        self.reset_signed_pv_obj.put(0)

    limit_switch_a_pv_obj = LazyPV("limit_switch_a_pv")

    limit_switch_b_pv_obj = LazyPV("limit_switch_b_pv")

    @property
    def on_limit_switch(self) -> bool:
        return (
            self.limit_switch_a_pv_obj.get()
            == linac_utils.STEPPER_ON_LIMIT_SWITCH_VALUE
            or self.limit_switch_b_pv_obj.get()
            == linac_utils.STEPPER_ON_LIMIT_SWITCH_VALUE
        )

    max_steps_pv_obj = LazyPV("max_steps_pv")

    @property
    def max_steps(self):
        return self.max_steps_pv_obj.get()

    @max_steps.setter
    def max_steps(self, value: int):
        self.max_steps_pv_obj.put(value)

    speed_pv_obj = LazyPV("speed_pv")

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

        If the move raises for any reason (abort, DetuneError, limit switch,
        PV error), _clean_up_failed_move() first writes ABORT_REQ if the
        motor is still moving, then restores NSTEPS.DRVH and VELO if this
        move changed them. The original exception is then re-raised.
        """
        self._abort_written = False
        self._limits_changed = False
        try:
            self._move(num_steps, max_steps, speed, change_limits, check_detune)
        except BaseException:
            self._clean_up_failed_move()
            raise

    def _clean_up_failed_move(self):
        """Stop a still-moving motor and undo limit changes after a failure.

        Never raises: a failure here is logged so the original exception
        from the move is the one the caller sees.
        """
        if not self._abort_written:
            self._abort_if_maybe_moving()
        if self._limits_changed:
            self._restore_limits_one_by_one()

    def _abort_if_maybe_moving(self):
        try:
            moving = self.motor_moving
        except Exception:
            # Can't read MOTOR_MOVING: write ABORT_REQ anyway. Not knowing
            # whether the motor is moving is itself an unsafe state.
            moving = True
        if not moving:
            return
        try:
            self.abort()
        except Exception as e:
            self.cavity.logger.error(
                "Failed to abort stepper after failed move: %s", e
            )

    def _restore_limits_one_by_one(self):
        # Each write on its own, so a failed NSTEPS.DRVH still restores VELO.
        for pv_field, attr, value in (
            ("NSTEPS.DRVH", "max_steps", linac_utils.DEFAULT_STEPPER_MAX_STEPS),
            ("VELO", "speed", linac_utils.DEFAULT_STEPPER_SPEED),
        ):
            try:
                setattr(self, attr, value)
            except Exception as e:
                self.cavity.logger.error(
                    "Failed to restore stepper %s after failed move: %s",
                    pv_field,
                    e,
                )

    def _move(
        self,
        num_steps: int,
        max_steps: int,
        speed: int,
        change_limits: bool,
        check_detune: bool,
    ):
        """Body of move(). Recurses for moves larger than max_steps."""
        self.check_abort()
        max_steps = abs(max_steps)

        if change_limits:
            # Set before the first write, so a failure partway still restores.
            self._limits_changed = True
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

            self._move(
                remaining_steps,
                max_steps,
                speed,
                change_limits=False,
                check_detune=check_detune,
            )

    def _move_timeout(self, num_steps: int) -> float:
        """Seconds to allow a move: FACTOR x steps / VELO + MARGIN.

        num_steps can exceed the steps this move covers (move() splits
        moves larger than max_steps), which only lengthens the timeout.
        """
        speed = self.speed
        timeout = linac_utils.STEPPER_MOVE_TIMEOUT_MARGIN_S
        if speed > 0:
            timeout += (
                linac_utils.STEPPER_MOVE_TIMEOUT_FACTOR * abs(num_steps) / speed
            )
        return timeout

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

        def check_abort_and_detune():
            self.check_abort()
            if check_detune:
                self.cavity.check_detune()

        def log_progress():
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

        # CHECK: on timeout this raises StepperError without writing ABORT_REQ,
        # so the motor may still be moving. Should it abort the motor first?
        linac_utils.wait_until(
            lambda: not self.motor_moving,
            timeout=self._move_timeout(num_steps),
            description=f"{self} to stop moving",
            error_class=linac_utils.StepperError,
            poll_interval=5,
            check_abort=check_abort_and_detune,
            on_poll=log_progress,
        )

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
