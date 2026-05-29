"""
Frequency Tuning Phase

Tunes the cavity stepper to resonance after initial cool-down.  Before moving
the stepper this phase:
  1. Checks that the stepper is idle and chirp detune is valid.
  2. Records the cold-landing detune and writes it to the DF_COLD PV so that
     future warm-up operations can find cold landing by frequency.
  3. Runs a probe move to measure Hz/step and write it to the SCALE PV, and
     to record whether stepper.move(+N) increases or decreases cavity frequency.
  4. Moves to resonance in small chunks, checking motor temperature before each
     chunk and pausing if the temperature exceeds the limit.  After converging,
     writes the (signed) return-trip step count to the NSTEPS_COLD PV.
  5. Writes a FrequencyTuningData record.
"""

import math
import time
from dataclasses import dataclass
from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    FrequencyTuningData,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseExecutionError,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac import linac_utils


@dataclass
class FrequencyTuningLimits:
    """Configurable limits for the frequency tuning phase."""

    tolerance_hz: float = 500.0
    probe_steps: int = 50_000
    temp_limit_c: float = linac_utils.STEPPER_TEMP_LIMIT
    max_total_steps: int = 10_000_000
    cool_down_retries: int = 6
    cool_down_interval: float = 5.0
    motor_start_wait: float = 5.0
    motor_poll_interval: float = 2.0
    min_probe_delta_hz: float = 10.0


class FrequencyTuningPhase(PhaseBase):
    """
    Frequency Tuning Phase.

    Sequence:
    1. verify_initial_state    – stepper idle, not on limit switch, chirp valid
    2. record_cold_landing     – record initial detune; write to DF_COLD PV
    3. probe_stepper_direction – measure Hz/step; write to SCALE PV
    4. tune_to_resonance       – chunked loop with temperature guard; write NSTEPS_COLD
    5. record_results          – write FrequencyTuningData to commissioning record
    """

    def __init__(
        self, context: PhaseContext, limits: FrequencyTuningLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or FrequencyTuningLimits()
        self._history_start = len(context.record.phase_history)
        self.cavity = None
        self._stepper_temp_pv_obj: PV | None = None
        self._df_cold_pv_obj: PV | None = None
        self._nsteps_cold_pv_obj: PV | None = None
        self._hz_per_microstep: float | None = None
        self._signed_hz_per_microstep: float | None = None

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.FREQUENCY_TUNING

    def validate_prerequisites(self) -> tuple[bool, str]:
        cavity = self.context.parameters.get("cavity")
        if cavity is None:
            return False, "No cavity specified in context"

        if not hasattr(cavity, "stepper_tuner") or cavity.stepper_tuner is None:
            return False, "Cavity has no stepper_tuner object"

        if not hasattr(cavity, "stepper_temp_pv") or not cavity.stepper_temp_pv:
            return False, "Cavity has no stepper_temp_pv defined"

        self.cavity = cavity
        return True, "Prerequisites validated"

    def get_phase_steps(self) -> list[str]:
        return [
            "verify_initial_state",
            "record_cold_landing",
            "probe_stepper_direction",
            "apply_hz_per_step",
            "tune_to_resonance",
            "record_results",
        ]

    def execute_step(self, step_name: str) -> PhaseStepResult:
        if self.cavity is None:
            raise PhaseExecutionError(
                "Cavity not set — validate_prerequisites must be called first"
            )

        step_methods = {
            "verify_initial_state": self._verify_initial_state,
            "record_cold_landing": self._record_cold_landing,
            "probe_stepper_direction": self._probe_stepper_direction,
            "apply_hz_per_step": self._apply_hz_per_step,
            "tune_to_resonance": self._tune_to_resonance,
            "record_results": self._record_results,
        }

        if step_name not in step_methods:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Unknown step: {step_name}",
            )

        return step_methods[step_name]()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_temp(self) -> float:
        if self._stepper_temp_pv_obj is None:
            self._stepper_temp_pv_obj = PV(self.cavity.stepper_temp_pv)
        return self._stepper_temp_pv_obj.get()

    def _write_df_cold(self, detune_hz: float) -> None:
        if self._df_cold_pv_obj is None:
            self._df_cold_pv_obj = PV(self.cavity.pv_addr("DF_COLD"))
        self._df_cold_pv_obj.put(detune_hz)

    def _write_nsteps_cold(self, steps: int) -> None:
        if self._nsteps_cold_pv_obj is None:
            self._nsteps_cold_pv_obj = PV(
                self.cavity.stepper_tuner.steps_cold_landing_pv
            )
        self._nsteps_cold_pv_obj.put(steps)

    def _wait_for_motor(self) -> None:
        """Block until motor_moving is False, checking abort each poll."""
        time.sleep(self.limits.motor_start_wait)
        while self.cavity.stepper_tuner.motor_moving:
            if self.context.is_abort_requested():
                self.cavity.stepper_tuner.abort()
                raise PhaseExecutionError("Abort requested during stepper move")
            time.sleep(self.limits.motor_poll_interval)

    def _check_temp_with_cooldown(self) -> tuple[bool, float, str]:
        """
        Read motor temperature and wait for cool-down if over the limit.

        Returns (ok, temp_c, message).
        """
        temp = self._read_temp()
        if temp <= self.limits.temp_limit_c:
            return True, temp, f"Motor temp {temp:.1f} °C OK"

        for _ in range(self.limits.cool_down_retries):
            time.sleep(self.limits.cool_down_interval)
            temp = self._read_temp()
            if temp <= self.limits.temp_limit_c:
                return True, temp, f"Motor cooled to {temp:.1f} °C"

        return (
            False,
            temp,
            f"Motor temp {temp:.1f} °C still above limit "
            f"{self.limits.temp_limit_c} °C after "
            f"{self.limits.cool_down_retries} retries",
        )

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

        if self.cavity.stepper_tuner.motor_moving:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor already moving — abort or wait for it to stop",
            )

        if self.cavity.stepper_tuner.on_limit_switch:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor is on a limit switch — manual intervention required",
            )

        if self.cavity.detune_invalid:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    "Chirp detune is invalid — ensure the chirp scan is running "
                    "and producing a valid CHIRP:DF reading before starting this phase"
                ),
            )

        try:
            temp = self._read_temp()
            detune = self.cavity.detune_chirp
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read stepper/detune state: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Stepper idle, chirp valid. Temp {temp:.1f} °C, detune {detune:.0f} Hz",
            data={"initial_temp_c": temp, "initial_detune_hz": detune},
        )

    def _record_cold_landing(self) -> PhaseStepResult:
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: cold landing snapshot simulated",
                data={
                    "initial_detune_hz": 0.0,
                    "initial_timestamp": datetime.now().isoformat(),
                    "dry_run": True,
                },
            )

        try:
            initial_detune_hz = self.cavity.detune_chirp
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read cold landing detune: {exc}",
                retry_delay_seconds=3.0,
            )

        try:
            self._write_df_cold(initial_detune_hz)
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not write cold landing frequency to DF_COLD: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Cold landing frequency recorded: detune={initial_detune_hz:.0f} Hz written to DF_COLD",
            data={
                "initial_detune_hz": initial_detune_hz,
                "initial_timestamp": datetime.now().isoformat(),
            },
        )

    def _apply_hz_per_step(self) -> PhaseStepResult:
        """Write the measured Hz/step to the SCALE PV after operator confirmation."""
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: skipping SCALE PV write",
                data={"dry_run": True},
            )

        if self._signed_hz_per_microstep is None:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Hz/step not measured — probe_stepper_direction must run first",
            )

        try:
            self.cavity.stepper_tuner.hz_per_microstep_pv_obj.put(
                self._signed_hz_per_microstep
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not write Hz/step to SCALE PV: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Wrote {self._signed_hz_per_microstep:.4f} Hz/step to SCALE PV",
        )

    def _probe_stepper_direction(self) -> PhaseStepResult:
        if self.context.dry_run:
            self._hz_per_microstep = 1.0
            self._signed_hz_per_microstep = 1.0
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: direction probe simulated",
                data={
                    "d0_hz": 0.0,
                    "d1_hz": 0.0,
                    "delta_hz": 0.0,
                    "positive_step_increases_frequency": False,
                    "hz_per_microstep": 1.0,
                    "dry_run": True,
                },
            )

        probe = self.limits.probe_steps

        try:
            d0 = self.cavity.detune_chirp
            self.cavity.stepper_tuner.move(probe, check_detune=False)
            d1 = self.cavity.detune_chirp
            self.cavity.stepper_tuner.move(-probe, check_detune=False)
        except (linac_utils.StepperError, linac_utils.StepperAbortError) as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Stepper error during direction probe: {exc}",
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Transient error during direction probe: {exc}",
                retry_delay_seconds=5.0,
            )

        delta = d1 - d0
        positive_step_increases_frequency = delta > 0

        if abs(delta) < self.limits.min_probe_delta_hz:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Probe move of {probe} steps produced only {abs(delta):.1f} Hz change "
                    f"(minimum {self.limits.min_probe_delta_hz:.1f} Hz required). "
                    "Check that the stepper is mechanically connected and the cavity is at 2 K."
                ),
            )

        # Signed value preserves direction; abs value is used in tuning calculations.
        signed_hz_per_step = delta / probe
        self._hz_per_microstep = abs(signed_hz_per_step)
        self._signed_hz_per_microstep = signed_hz_per_step

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Direction probe: Δdetune={delta:+.0f} Hz for +{probe} steps. "
                f"Measured {self._hz_per_microstep:.4f} Hz/step written to SCALE PV. "
                f"move(+N) {'increases' if positive_step_increases_frequency else 'decreases'} frequency."
            ),
            data={
                "d0_hz": d0,
                "d1_hz": d1,
                "delta_hz": delta,
                "positive_step_increases_frequency": positive_step_increases_frequency,
                "hz_per_microstep": self._hz_per_microstep,
                "probe_steps": probe,
            },
        )

    def _guard_temp(
        self, total_steps: int, peak_temp: float
    ) -> tuple[float, PhaseStepResult | None]:
        """Check motor temperature and wait for cool-down if needed.

        Returns (updated_peak_temp, error_or_None).
        """
        try:
            ok, temp, msg = self._check_temp_with_cooldown()
            peak_temp = max(peak_temp, temp)
        except Exception as exc:
            return peak_temp, PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read motor temperature: {exc}",
                retry_delay_seconds=5.0,
            )
        if not ok:
            return peak_temp, PhaseStepResult(
                result=PhaseResult.FAILED,
                message=msg,
                data={"total_steps": total_steps, "peak_temp_c": peak_temp},
            )
        return peak_temp, None

    def _guard_detune(self) -> tuple[float, PhaseStepResult | None]:
        """Read chirp detune. Returns (detune_hz, error_or_None)."""
        try:
            return self.cavity.detune_chirp, None
        except Exception as exc:
            return 0.0, PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read detune: {exc}",
                retry_delay_seconds=3.0,
            )

    def _tuning_dry_run_result(self) -> PhaseStepResult:
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Dry run: tuning to resonance simulated",
            data={
                "total_steps": 0,
                "final_timestamp": datetime.now().isoformat(),
                "dry_run": True,
            },
        )

    def _initialize_tuning_state(self, tuning_cb) -> tuple[int, int, float]:
        total_steps = 0
        signed_total = 0
        peak_temp = 0.0

        try:
            peak_temp = self._read_temp()
        except Exception:
            pass

        try:
            if tuning_cb:
                tuning_cb(0, self.cavity.detune_chirp)
        except Exception:
            pass

        return total_steps, signed_total, peak_temp

    def _emit_tuning_update(self, tuning_cb, total_steps: int) -> None:
        try:
            if tuning_cb:
                tuning_cb(total_steps, self.cavity.detune_chirp)
        except Exception:
            pass

    def _write_cold_landing_steps(
        self, signed_total: int
    ) -> PhaseStepResult | None:
        # NSTEPS_COLD stores the return-trip step count (from resonance to cold
        # landing), which is the negation of the steps we just took.
        try:
            self._write_nsteps_cold(-signed_total)
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not write NSTEPS_COLD after tuning: {exc}",
                retry_delay_seconds=3.0,
            )
        return None

    def _one_tuning_iteration(
        self,
        total_steps: int,
        signed_total: int,
        peak_temp: float,
        hz_per_step: float,
        hz_update_cb=None,
    ) -> tuple[int, int, float, bool, PhaseStepResult | None]:
        """Execute one iteration of the tuning loop.

        Returns (new_total_steps, new_signed_total, new_peak_temp, converged, error_or_None).
        signed_total accumulates the signed step count for writing to NSTEPS_COLD.
        """
        if self.context.is_abort_requested():
            return (
                total_steps,
                signed_total,
                peak_temp,
                False,
                PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=f"Abort requested after {total_steps} steps",
                ),
            )

        peak_temp, err = self._guard_temp(total_steps, peak_temp)
        if err is not None:
            return total_steps, signed_total, peak_temp, False, err

        detune, err = self._guard_detune()
        if err is not None:
            return total_steps, signed_total, peak_temp, False, err

        if abs(detune) <= self.limits.tolerance_hz:
            return total_steps, signed_total, peak_temp, True, None

        if total_steps >= self.limits.max_total_steps:
            return (
                total_steps,
                signed_total,
                peak_temp,
                False,
                PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=(
                        f"Reached max step limit ({self.limits.max_total_steps}) "
                        f"without converging; final detune {detune:.0f} Hz"
                    ),
                    data={
                        "total_steps": total_steps,
                        "final_detune_hz": detune,
                        "peak_temp_c": peak_temp,
                    },
                ),
            )

        magnitude, steps_this_move, err = self._do_move(
            total_steps, peak_temp, detune, hz_per_step, hz_update_cb
        )
        if err is not None:
            return total_steps, signed_total, peak_temp, False, err
        return (
            total_steps + magnitude,
            signed_total + steps_this_move,
            peak_temp,
            False,
            None,
        )

    def _do_move(
        self,
        total_steps: int,
        peak_temp: float,
        detune: float,
        hz_per_step: float,
        hz_update_cb,
    ) -> tuple[int, int, "PhaseStepResult | None"]:
        """Compute step size, execute stepper move, and invoke the Hz/step callback."""
        hardware_max = self.cavity.stepper_tuner.max_steps
        estimated = max(1, round(abs(detune) / hz_per_step))
        magnitude = min(hardware_max, estimated)
        steps_this_move = int(math.copysign(magnitude, detune))

        try:
            self.cavity.stepper_tuner.move(
                steps_this_move, max_steps=hardware_max, check_detune=False
            )
        except (linac_utils.StepperError, linac_utils.StepperAbortError) as exc:
            return (
                magnitude,
                steps_this_move,
                PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=f"Stepper error after {total_steps} steps: {exc}",
                    data={"total_steps": total_steps, "peak_temp_c": peak_temp},
                ),
            )

        if hz_update_cb is not None:
            try:
                hz_delta = abs(self.cavity.detune_chirp - detune)
                if hz_delta > 0:
                    hz_update_cb(magnitude, hz_delta)
            except Exception:
                pass

        return magnitude, steps_this_move, None

    def _tune_to_resonance(self) -> PhaseStepResult:
        if self.context.dry_run:
            return self._tuning_dry_run_result()

        hz_per_step = self._hz_per_microstep
        if not hz_per_step:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="hz_per_microstep not set — probe_stepper_direction must run first",
            )

        tuning_cb = self.context.parameters.get("tuning_update_callback")
        hz_update_cb = self.context.parameters.get(
            "hz_per_step_update_callback"
        )

        total_steps, signed_total, peak_temp = self._initialize_tuning_state(
            tuning_cb
        )

        while True:
            total_steps, signed_total, peak_temp, converged, err = (
                self._one_tuning_iteration(
                    total_steps,
                    signed_total,
                    peak_temp,
                    hz_per_step,
                    hz_update_cb,
                )
            )
            if err is not None:
                return err
            self._emit_tuning_update(tuning_cb, total_steps)
            if converged:
                break

        err = self._write_cold_landing_steps(signed_total)
        if err is not None:
            return err

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Reached resonance in {total_steps} steps. "
                f"NSTEPS_COLD set to {-signed_total}."
            ),
            data={
                "total_steps": total_steps,
                "cold_landing_steps": -signed_total,
                "final_timestamp": datetime.now().isoformat(),
            },
        )

    def _record_results(self) -> PhaseStepResult:
        """Placeholder step — actual population happens in finalize_phase()."""
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Results collected; ready to finalise",
        )

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _get_checkpoint_data(self, step_name: str) -> dict:
        checkpoint = next(
            (
                cp
                for cp in reversed(
                    self.context.record.phase_history[self._history_start :]
                )
                if cp.phase == self.phase_type and cp.step_name == step_name
            ),
            None,
        )
        return checkpoint.measurements if checkpoint else {}

    def finalize_phase(self) -> None:
        cold = self._get_checkpoint_data("record_cold_landing")
        probe = self._get_checkpoint_data("probe_stepper_direction")
        tune = self._get_checkpoint_data("tune_to_resonance")

        initial_ts_raw = cold.get("initial_timestamp")
        initial_ts = (
            datetime.fromisoformat(initial_ts_raw) if initial_ts_raw else None
        )
        final_ts_raw = tune.get("final_timestamp")
        final_ts = (
            datetime.fromisoformat(final_ts_raw) if final_ts_raw else None
        )

        self.context.record.frequency_tuning = FrequencyTuningData(
            initial_detune_hz=cold.get("initial_detune_hz"),
            initial_timestamp=initial_ts,
            steps_to_resonance=tune.get("total_steps"),
            final_timestamp=final_ts,
            positive_step_increases_frequency=probe.get(
                "positive_step_increases_frequency"
            ),
            hz_per_microstep=probe.get("hz_per_microstep"),
            cold_landing_steps=tune.get("cold_landing_steps"),
        )
