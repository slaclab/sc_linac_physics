"""
SSA Calibration Phase

Runs SSA calibration: resets the SSA, powers it on, triggers the calibration
scan, validates results, and auto-pushes the new slope to the active cavity
register so the operator can review before choosing to save.
"""

import time
from dataclasses import dataclass

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseExecutionError,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.utils.sc_linac import linac_utils


@dataclass
class SSACalLimits:
    """Configurable limits for SSA calibration."""

    cal_timeout: float = 120.0
    poll_interval: float = 1.0
    post_start_delay: float = 2.0


class SSACharPhase(PhaseBase):
    """
    SSA Calibration Phase.

    Sequence:
    1. verify_initial_state  – confirm SSA is accessible and not mid-run
    2. set_drive_max         – write requested drive max to DRV_MAX_REQ
    3. reset_and_power_on    – reset faults, turn on SSA, reset cavity interlocks
    4. start_calibration     – trigger CALSTRT and wait for scan to begin
    5. wait_for_completion   – poll until CALSTS leaves Running state
    6. validate_and_push     – check results and push new slope to cavity register
    """

    def __init__(
        self, context: PhaseContext, limits: SSACalLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or SSACalLimits()
        self._history_start = len(context.record.phase_history)
        self.cavity = None

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.SSA_CHAR

    def validate_prerequisites(self) -> tuple[bool, str]:
        cavity = self.context.parameters.get("cavity")
        if cavity is None:
            return False, "No cavity specified in context"

        if not hasattr(cavity, "ssa") or cavity.ssa is None:
            return False, "Cavity has no SSA object"

        drive_max = self.context.parameters.get("drive_max")
        if drive_max is None:
            return False, "No drive_max specified in context parameters"

        if not (0.0 < drive_max <= 1.0):
            return False, f"drive_max {drive_max} out of range (0, 1]"

        self.cavity = cavity
        return True, "Prerequisites validated"

    def get_phase_steps(self) -> list[str]:
        return [
            "verify_initial_state",
            "set_drive_max",
            "reset_and_power_on",
            "start_calibration",
            "wait_for_completion",
            "validate_and_push",
        ]

    def execute_step(self, step_name: str) -> PhaseStepResult:
        if self.cavity is None:
            raise PhaseExecutionError(
                "Cavity not set — validate_prerequisites must be called first"
            )

        step_methods = {
            "verify_initial_state": self._verify_initial_state,
            "set_drive_max": self._set_drive_max,
            "reset_and_power_on": self._reset_and_power_on,
            "start_calibration": self._start_calibration,
            "wait_for_completion": self._wait_for_completion,
            "validate_and_push": self._validate_and_push,
        }

        if step_name not in step_methods:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Unknown step: {step_name}",
            )

        return step_methods[step_name]()

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _verify_initial_state(self) -> PhaseStepResult:
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: skipping initial state check",
                data={"dry_run": True},
            )

        ssa = self.cavity.ssa

        if ssa.calibration_running:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="SSA calibration already running — abort or wait",
            )

        try:
            current_slope = ssa.current_slope
            current_drive = ssa.drive_max
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read SSA state: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Initial state verified",
            data={
                "initial_current_slope": current_slope,
                "initial_drive_max": current_drive,
            },
        )

    def _set_drive_max(self) -> PhaseStepResult:
        drive_max = self.context.parameters["drive_max"]

        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message=f"Dry run: would set drive max to {drive_max:.3f}",
                data={"drive_max": drive_max, "dry_run": True},
            )

        self.cavity.ssa.drive_max = drive_max

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Drive max set to {drive_max:.3f}",
            data={"drive_max": drive_max},
        )

    def _reset_and_power_on(self) -> PhaseStepResult:
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: skipping SSA reset / power-on",
                data={"dry_run": True},
            )

        ssa = self.cavity.ssa
        try:
            ssa.reset()
            ssa.turn_on()
            self.cavity.reset_interlocks()
        except (
            linac_utils.SSAFaultError,
            linac_utils.SSACalibrationError,
        ) as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"SSA reset/power-on failed: {exc}",
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Transient error during reset/power-on: {exc}",
                retry_delay_seconds=5.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="SSA reset, powered on, and interlocks cleared",
        )

    def _start_calibration(self) -> PhaseStepResult:
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: calibration start simulated",
                data={"dry_run": True},
            )

        ssa = self.cavity.ssa
        ssa.start_calibration()
        time.sleep(self.limits.post_start_delay)

        if ssa.calibration_crashed:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Calibration crashed immediately after start",
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Calibration scan started",
        )

    def _wait_for_completion(self) -> PhaseStepResult:
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: calibration completion simulated",
                data={
                    "dry_run": True,
                    "slope_new": 1.02345,
                    "max_fwd_pwr": 4500.0,
                },
            )

        ssa = self.cavity.ssa
        elapsed = 0.0

        while ssa.calibration_running:
            if self.context.is_abort_requested():
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message="Abort requested during calibration",
                )
            if elapsed >= self.limits.cal_timeout:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=f"Calibration timed out after {self.limits.cal_timeout:.0f}s",
                )
            time.sleep(self.limits.poll_interval)
            elapsed += self.limits.poll_interval

        time.sleep(self.limits.post_start_delay)

        try:
            slope_new = ssa.measured_slope
            max_fwd_pwr = ssa.max_fwd_pwr
        except Exception:
            slope_new = None
            max_fwd_pwr = None

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Calibration scan complete",
            data={"slope_new": slope_new, "max_fwd_pwr": max_fwd_pwr},
        )

    def _validate_and_push(self) -> PhaseStepResult:
        drive_max = self.context.parameters["drive_max"]

        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: validation passed, slope push simulated",
                data={
                    "slope_new": 1.02345,
                    "slope_current": 1.02345,
                    "max_fwd_pwr": 4500.0,
                    "max_drive": drive_max,
                    "calibration_passed": True,
                    "dry_run": True,
                },
            )

        ssa = self.cavity.ssa

        if ssa.calibration_crashed:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Calibration status shows crashed",
            )

        if not ssa.calibration_result_good:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Calibration result not good (CALSTAT)",
            )

        max_fwd_pwr = ssa.max_fwd_pwr
        if max_fwd_pwr < ssa.fwd_power_lower_limit:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Measured forward power {max_fwd_pwr:.0f} W is below "
                    f"the minimum limit of {ssa.fwd_power_lower_limit} W"
                ),
            )

        if not ssa.measured_slope_in_tolerance:
            slope = ssa.measured_slope
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Slope {slope:.5f} out of tolerance "
                    f"[{linac_utils.SSA_SLOPE_LOWER_LIMIT}, "
                    f"{linac_utils.SSA_SLOPE_UPPER_LIMIT}]"
                ),
            )

        slope_new = ssa.measured_slope

        self.cavity.push_ssa_slope()
        time.sleep(0.5)

        try:
            slope_current = ssa.current_slope
        except Exception:
            slope_current = slope_new

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Validation passed, slope {slope_new:.5f} pushed to cavity",
            data={
                "slope_new": slope_new,
                "slope_current": slope_current,
                "max_fwd_pwr": max_fwd_pwr,
                "max_drive": drive_max,
                "calibration_passed": True,
            },
        )

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize_phase(self) -> None:
        validate_checkpoint = next(
            (
                cp
                for cp in reversed(
                    self.context.record.phase_history[self._history_start :]
                )
                if cp.phase == self.phase_type
                and cp.step_name == "validate_and_push"
            ),
            None,
        )

        data = validate_checkpoint.measurements if validate_checkpoint else {}

        self.context.record.ssa_char = SSACharacterization(
            max_drive=data.get("max_drive"),
            slope_new=data.get("slope_new"),
            max_fwd_pwr=data.get("max_fwd_pwr"),
            calibration_passed=data.get("calibration_passed", False),
        )
