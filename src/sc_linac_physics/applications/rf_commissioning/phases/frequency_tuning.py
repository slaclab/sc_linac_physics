"""
Frequency Tuning Phase

Tunes the cavity stepper to resonance after initial cool-down.  Cavities are
expected to start at the COLD tune config.  Before moving the stepper this
phase:
  1. Checks that the stepper is idle and chirp detune is valid; warns (but does
     not fail) if the cavity is not at the COLD tune config.
  2. Records the cold-landing detune for display; the operator pushes it to
     DF_COLD via the UI after reviewing.
  3. Runs a probe move to measure Hz/microstep; the operator confirms and the UI
     writes the value (to SCALE_CALC.B) via apply_hz_per_step.
  4. Gates on DF_COLD having been recorded, then moves to resonance in small
     chunks, checking motor temperature before each chunk.  There is no
     automatic cool-down: if the temperature exceeds the limit the step fails
     and the operator must investigate and re-run with an explicit
     acknowledgement (over_temp_ack_c).  After converging, writes the (signed)
     return-trip step count to the NSTEPS_COLD PV and sets tune_config to
     RESONANCE.
  5. Runs a single-cavity FSCAN to find the 8π/9 and 7π/9 parasitic modes and
     pushes results to the cavity mode-frequency PVs.
  6. Writes a FrequencyTuningData record.
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

_FSCAN_STAT_SCAN_DONE = 5
_FSCAN_STAT_SCAN_ABORTED = 6
_FSCAN_STAT_FREQ_RESTORE_FAIL = 7


@dataclass
class FrequencyTuningLimits:
    """Configurable limits for the frequency tuning phase."""

    tolerance_hz: float = 50.0
    probe_steps: int = 50_000
    move_speed: int = linac_utils.DEFAULT_STEPPER_SPEED
    temp_limit_c: float = linac_utils.STEPPER_TEMP_LIMIT
    max_total_steps: int = 10_000_000
    # A healthy probe move (probe_steps microsteps at ~0.005 Hz/microstep)
    # produces a few hundred Hz of detune change on real cavities; require a
    # solid fraction of that so a degraded/uncoupled stepper is caught, not
    # just a totally dead one.
    min_probe_delta_hz: float = 100.0
    pi_scan_freq_start: int = -3_500_000
    pi_scan_freq_stop: int = 50_000
    pi_scan_rms_thresh: float = 10.0
    pi_scan_mode_overlap: int = 1_000
    pi_scan_poll_interval: float = 2.0
    pi_scan_timeout_seconds: float = 300.0


class FrequencyTuningPhase(PhaseBase):
    """
    Frequency Tuning Phase.

    Sequence:
    1. verify_initial_state    – stepper idle, not on limit switch, chirp valid
    2. record_cold_landing     – record initial detune (operator pushes to DF_COLD via UI)
    3. probe_stepper_direction – measure Hz/step (operator confirms; UI writes to SCALE)
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
        # Signed: positive means +steps increase cavity frequency (matches SCALE PV convention)
        self._hz_per_microstep: float | None = None
        # Over-temperature breaches the operator acknowledged this run:
        # list of (temp_c, operator) tuples.
        self._over_temp_acks: list[tuple[float, str]] = []

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
            "measure_pi_modes",
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
            "measure_pi_modes": self._measure_pi_modes,
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

    def _read_df_cold(self) -> float:
        # DF_COLD is written by the operator via the UI after reviewing the
        # cold-landing frequency; the backend reads it back to gate tuning.
        if self._df_cold_pv_obj is None:
            self._df_cold_pv_obj = PV(self.cavity.pv_addr("DF_COLD"))
        return self._df_cold_pv_obj.get()

    _DF_COLD_MATCH_TOLERANCE_HZ = 1.0

    def _check_df_cold_recorded(self) -> "PhaseStepResult | None":
        """Ensure the operator pushed the cold-landing detune to DF_COLD.

        Returns a FAILED/RETRY result if DF_COLD was not recorded, else None.
        The recorded cold-landing detune (from record_cold_landing) is the
        reliable reference: DF_COLD defaults to a valid 0, so there is no
        INVALID severity to key off — we require DF_COLD to match it.
        """
        cold = self._get_checkpoint_data("record_cold_landing")
        recorded = cold.get("df_cold_hz")
        if recorded is None:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    "Cold landing frequency was not recorded — run "
                    "record_cold_landing before tuning"
                ),
            )
        try:
            df_cold = self._read_df_cold()
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read DF_COLD: {exc}",
                retry_delay_seconds=3.0,
            )
        if abs(df_cold - recorded) > self._DF_COLD_MATCH_TOLERANCE_HZ:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    "DF_COLD not recorded — push the cold-landing frequency "
                    f"({recorded:.0f} Hz) to DF_COLD before tuning "
                    f"(DF_COLD currently reads {df_cold:.0f} Hz)"
                ),
            )
        return None

    def _write_nsteps_cold(self, steps: int) -> None:
        self.cavity.stepper_tuner.steps_cold_landing_pv_obj.put(steps)

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

        tune_config_warning = self._tune_config_warning()

        message = f"Stepper idle, chirp valid. Temp {temp:.1f} °C, detune {detune:.0f} Hz"
        if tune_config_warning:
            message += f". WARNING: {tune_config_warning}"

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=message,
            data={
                "initial_temp_c": temp,
                "initial_detune_hz": detune,
                "tune_config_warning": tune_config_warning,
            },
        )

    def _tune_config_warning(self) -> str | None:
        """Return a warning if the cavity is not at the COLD tune config.

        Cavities are expected to start at COLD; a different state is not fatal
        (the operator may have a reason), so this only flags it.
        """
        try:
            tune_config = self.cavity.tune_config_pv_obj.get()
        except Exception:
            return None
        if tune_config == linac_utils.TUNE_CONFIG_COLD_VALUE:
            return None
        return (
            f"tune_config is {tune_config} (expected COLD="
            f"{linac_utils.TUNE_CONFIG_COLD_VALUE}); "
            "cavity may not be at cold landing"
        )

    def _record_cold_landing(self) -> PhaseStepResult:
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: cold landing snapshot simulated",
                data={
                    "df_cold_hz": 0.0,
                    "initial_timestamp": datetime.now().isoformat(),
                    "dry_run": True,
                },
            )

        try:
            df_cold_hz = self.cavity.detune_chirp
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read cold landing detune: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Cold landing frequency recorded: detune={df_cold_hz:.0f} Hz. "
            "Push to DF_COLD when satisfied.",
            data={
                "df_cold_hz": df_cold_hz,
                "initial_timestamp": datetime.now().isoformat(),
            },
        )

    def _apply_hz_per_step(self) -> PhaseStepResult:
        """Persist the measured Hz/microstep after operator confirmation.

        STEP:SCALE is a derived, read-only calc-record output
        (SCALE = SCALE_CALC.B / 256), so we write the Hz-per-full-step field
        (SCALE_CALC.B) and let the IOC recompute SCALE.
        """
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: skipping SCALE_CALC.B write",
                data={"dry_run": True},
            )

        if self._hz_per_microstep is None:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Hz/microstep not measured — probe_stepper_direction must run first",
            )

        try:
            self.cavity.stepper_tuner.set_hz_per_microstep(
                self._hz_per_microstep
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not write Hz/step to SCALE_CALC.B: {exc}",
                retry_delay_seconds=3.0,
            )

        calc_b = self._hz_per_microstep * linac_utils.MICROSTEPS_PER_STEP
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Wrote {self._hz_per_microstep:.4f} Hz/microstep "
                f"(SCALE_CALC.B={calc_b:.4f} Hz/full-step); "
                "IOC will recompute STEP:SCALE"
            ),
        )

    def _do_probe_move(
        self,
        probe: int,
        probe_cb,
        speed: int = linac_utils.DEFAULT_STEPPER_SPEED,
    ) -> tuple[float, float]:
        """Execute the forward+back probe move; return (d0_hz, d1_hz)."""
        self.cavity.stepper_tuner.reset_signed_steps()
        d0 = self.cavity.detune_chirp
        try:
            if probe_cb:
                probe_cb(0, d0)
        except Exception:
            pass
        self.cavity.stepper_tuner.move(probe, speed=speed, check_detune=False)
        d1 = self.cavity.detune_chirp
        try:
            if probe_cb:
                probe_cb(probe, d1)
        except Exception:
            pass
        self.cavity.stepper_tuner.move(-probe, speed=speed, check_detune=False)
        return d0, d1

    def _probe_stepper_direction(self) -> PhaseStepResult:
        if self.context.dry_run:
            self._hz_per_microstep = 1.0
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: direction probe simulated",
                data={
                    "d0_hz": 0.0,
                    "d1_hz": 0.0,
                    "delta_hz": 0.0,
                    "hz_per_microstep": 1.0,
                    "dry_run": True,
                },
            )

        probe = self.limits.probe_steps
        probe_cb = self.context.parameters.get("probe_update_callback")
        speed = self.limits.move_speed

        try:
            d0, d1 = self._do_probe_move(probe, probe_cb, speed=speed)
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

        if abs(delta) < self.limits.min_probe_delta_hz:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Probe move of {probe} steps produced only {abs(delta):.1f} Hz change "
                    f"(minimum {self.limits.min_probe_delta_hz:.1f} Hz required). "
                    "Check that the stepper is mechanically connected and the cavity is at 2 K."
                ),
            )

        # SCALE convention: d(cavity_freq)/d(step).
        # CHIRP:DF = ref_freq - cav_freq, so d(CHIRP:DF)/d(step) = -SCALE.
        # Positive SCALE → positive steps increase cavity frequency → CHIRP:DF decreases.
        signed_hz_per_step = -delta / probe
        self._hz_per_microstep = signed_hz_per_step

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Direction probe: Δdetune={delta:+.0f} Hz for +{probe} steps. "
                f"Measured {abs(self._hz_per_microstep):.4f} Hz/step (confirm to write to SCALE PV). "
                f"move(+N) "
                f"{'increases' if signed_hz_per_step > 0 else 'decreases'} frequency."
            ),
            data={
                "d0_hz": d0,
                "d1_hz": d1,
                "s_d0": 0,
                "s_d1": probe,
                "delta_hz": delta,
                "hz_per_microstep": self._hz_per_microstep,
                "probe_steps": probe,
            },
        )

    def _guard_temp(
        self, total_steps: int, peak_temp: float
    ) -> tuple[float, PhaseStepResult | None]:
        """Check motor temperature; fail on over-temp unless acknowledged.

        There is no automatic cool-down.  If the motor exceeds the limit the
        step fails and the operator must investigate and re-run, passing
        ``over_temp_ack_c`` (a temperature ceiling they authorize) via
        context.parameters.  A reading hotter than that ceiling re-arms the
        gate and requires a fresh acknowledgement.

        Returns (updated_peak_temp, error_or_None).
        """
        try:
            temp = self._read_temp()
        except Exception as exc:
            return peak_temp, PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read motor temperature: {exc}",
                retry_delay_seconds=5.0,
            )
        peak_temp = max(peak_temp, temp)

        if temp <= self.limits.temp_limit_c:
            return peak_temp, None

        ack_ceiling = self.context.parameters.get("over_temp_ack_c")
        if ack_ceiling is not None and temp <= ack_ceiling:
            # Operator acknowledged proceeding up to this temperature.
            self._over_temp_acks.append((temp, self.context.operator))
            return peak_temp, None

        return peak_temp, PhaseStepResult(
            result=PhaseResult.FAILED,
            message=(
                f"Stepper motor temp {temp:.1f} °C exceeds limit "
                f"{self.limits.temp_limit_c} °C after {total_steps} steps. "
                "Investigate; to proceed, acknowledge and re-run with "
                f"over_temp_ack_c ≥ {temp:.1f}."
            ),
            data={
                "total_steps": total_steps,
                "peak_temp_c": peak_temp,
                "stepper_temp_c": temp,
                "temp_limit_c": self.limits.temp_limit_c,
                "requires_over_temp_ack": True,
            },
        )

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

    def _initialize_tuning_state(
        self, tuning_cb
    ) -> tuple[int, int, float, "PhaseStepResult | None"]:
        total_steps = 0
        peak_temp = 0.0

        # Read the current signed step count rather than resetting it.
        # REG_TOTSGN was zeroed by the Stage 2 probe, so on the first run
        # signed_total starts at 0.  After an abort and restart it retains the
        # displacement already accumulated from cold landing, keeping NSTEPS_COLD
        # accurate across partial runs.  A read failure here must NOT default to
        # 0 — that would silently corrupt the NSTEPS_COLD return trip — so we
        # surface a RETRY instead.
        try:
            signed_total = round(
                self.cavity.stepper_tuner.step_signed_pv_obj.get() or 0
            )
        except Exception as exc:
            return (
                total_steps,
                0,
                peak_temp,
                PhaseStepResult(
                    result=PhaseResult.RETRY,
                    message=f"Could not read signed step count to resume tuning: {exc}",
                    retry_delay_seconds=3.0,
                ),
            )

        try:
            peak_temp = self._read_temp()
        except Exception:
            pass

        try:
            if tuning_cb:
                tuning_cb(signed_total, self.cavity.detune_chirp)
        except Exception:
            pass

        return total_steps, signed_total, peak_temp, None

    def _emit_tuning_update(self, tuning_cb, signed_total: int) -> None:
        try:
            if tuning_cb:
                tuning_cb(signed_total, self.cavity.detune_chirp)
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
        speed: int = linac_utils.DEFAULT_STEPPER_SPEED,
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
            total_steps, peak_temp, detune, hz_per_step, hz_update_cb, speed
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
        speed: int = linac_utils.DEFAULT_STEPPER_SPEED,
    ) -> tuple[int, int, "PhaseStepResult | None"]:
        """Compute step size, execute stepper move, and invoke the Hz/step callback."""
        hardware_max = int(self.cavity.stepper_tuner.max_steps)
        estimated = max(1, round(abs(detune) / abs(hz_per_step)))
        magnitude = min(hardware_max, estimated)
        # Direction: steps_to_zero = detune / SCALE, so sign = sign(detune / signed_hz).
        # This handles motors wired in either direction (positive or negative SCALE).
        signed_hz = self._hz_per_microstep
        if signed_hz:
            steps_this_move = int(math.copysign(magnitude, detune / signed_hz))
        else:
            steps_this_move = int(math.copysign(magnitude, detune))

        try:
            self.cavity.stepper_tuner.move(
                steps_this_move,
                max_steps=hardware_max,
                speed=speed,
                check_detune=False,
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

        df_cold_err = self._check_df_cold_recorded()
        if df_cold_err is not None:
            return df_cold_err

        tuning_cb = self.context.parameters.get("tuning_update_callback")
        hz_update_cb = self.context.parameters.get(
            "hz_per_step_update_callback"
        )
        speed = self.limits.move_speed

        total_steps, signed_total, peak_temp, err = (
            self._initialize_tuning_state(tuning_cb)
        )
        if err is not None:
            return err

        while True:
            total_steps, signed_total, peak_temp, converged, err = (
                self._one_tuning_iteration(
                    total_steps,
                    signed_total,
                    peak_temp,
                    hz_per_step,
                    hz_update_cb,
                    speed,
                )
            )
            if err is not None:
                return err
            self._emit_tuning_update(tuning_cb, signed_total)
            if converged:
                break

        err = self._write_cold_landing_steps(signed_total)
        if err is not None:
            return err

        err = self._write_tune_config_resonance()
        if err is not None:
            return err

        return self._tuning_success_result(total_steps, signed_total)

    def _tuning_success_result(
        self, total_steps: int, signed_total: int
    ) -> PhaseStepResult:
        data = {
            "total_steps": total_steps,
            "cold_landing_steps": -signed_total,
            "final_timestamp": datetime.now().isoformat(),
        }
        if self._over_temp_acks:
            data["over_temp_acknowledged_c"] = max(
                t for t, _ in self._over_temp_acks
            )
            data["over_temp_acknowledged_by"] = self.context.operator

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Reached resonance in {total_steps} steps. "
                f"NSTEPS_COLD set to {-signed_total}. tune_config set to RESONANCE."
            ),
            data=data,
        )

    def _write_tune_config_resonance(self) -> "PhaseStepResult | None":
        # The cavity is now on resonance; record that state (mirrors
        # Cavity.move_to_resonance).
        try:
            self.cavity.tune_config_pv_obj.put(
                linac_utils.TUNE_CONFIG_RESONANCE_VALUE
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not set tune_config to RESONANCE: {exc}",
                retry_delay_seconds=3.0,
            )
        return None

    # ------------------------------------------------------------------
    # Pi-mode scan step
    # ------------------------------------------------------------------

    def _measure_pi_modes(self) -> PhaseStepResult:
        """Run the full rack FSCAN sequence for this cavity and read back results.

        Checks rack exclusivity, selects only this cavity, configures and
        triggers the scan, waits for completion, pushes mode results, and
        reads back the 8π/9 and 7π/9 frequencies.
        """
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: pi mode scan skipped",
                data={
                    "mode_8pi_9_hz": 0.0,
                    "mode_7pi_9_hz": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "dry_run": True,
                },
            )

        rack = self.cavity.rack

        err = self._check_rack_exclusivity(rack)
        if err is not None:
            return err
        err = self._select_cavity_for_fscan(rack)
        if err is not None:
            return err
        err = self._configure_fscan_params(rack)
        if err is not None:
            return err
        err = self._trigger_fscan(rack)
        if err is not None:
            return err

        status_cb = self.context.parameters.get("status_update_callback")
        err = self._wait_for_fscan(rack, status_cb)
        if err is not None:
            return err

        err = self._push_mode_results()
        if err is not None:
            return err
        return self._read_mode_frequencies()

    def _put_pv(
        self, address: str, value, label: str
    ) -> "PhaseStepResult | None":
        """Write ``value`` to ``address``; return a RETRY result on failure."""
        try:
            PV(address).put(value)
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not write {label}: {exc}",
                retry_delay_seconds=3.0,
            )
        return None

    def _check_rack_exclusivity(self, rack) -> "PhaseStepResult | None":
        rack_check = self.context.parameters.get("rack_check_callback")
        if rack_check is None:
            return None
        try:
            ok, reason = rack_check(rack)
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Rack check callback raised an exception: {exc}",
                retry_delay_seconds=5.0,
            )
        if not ok:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Cannot run FSCAN: another cavity in rack "
                    f"{rack.rack_name} is being commissioned. {reason}"
                ),
            )
        return None

    def _select_cavity_for_fscan(self, rack) -> "PhaseStepResult | None":
        for cav_num, cav in rack.cavities.items():
            selected = 1 if cav_num == self.cavity.number else 0
            err = self._put_pv(
                cav.pv_addr("FSCAN:SEL"),
                selected,
                f"FSCAN:SEL for cavity {cav_num}",
            )
            if err is not None:
                return err
        return None

    def _configure_fscan_params(self, rack) -> "PhaseStepResult | None":
        for suffix, value in (
            ("FSCAN:FREQ_START", self.limits.pi_scan_freq_start),
            ("FSCAN:FREQ_STOP", self.limits.pi_scan_freq_stop),
            ("FSCAN:RMS_THRESH", self.limits.pi_scan_rms_thresh),
            ("FSCAN:MODE_OVERLAP", self.limits.pi_scan_mode_overlap),
        ):
            err = self._put_pv(rack.pv_prefix + suffix, value, suffix)
            if err is not None:
                return err
        return None

    def _trigger_fscan(self, rack) -> "PhaseStepResult | None":
        return self._put_pv(rack.pv_prefix + "FSCAN:START", 1, "FSCAN:START")

    _FSCAN_STATE_NAMES = {
        0: "Await request",
        1: "No cav selected",
        2: "Bad range",
        3: "Search in progress",
        4: "Shift mode",
        5: "Scan done",
        6: "Scan aborted",
        7: "Freq restore fail",
    }

    def _wait_for_fscan(self, rack, status_cb) -> "PhaseStepResult | None":
        stat_pv = PV(rack.pv_prefix + "FSCAN:STAT")
        scan_start = time.monotonic()
        deadline = scan_start + self.limits.pi_scan_timeout_seconds
        while time.monotonic() < deadline:
            if self.context.is_abort_requested():
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message="Abort requested while waiting for FSCAN",
                )
            try:
                stat = int(stat_pv.get())
            except Exception as exc:
                return PhaseStepResult(
                    result=PhaseResult.RETRY,
                    message=f"Could not read FSCAN:STAT: {exc}",
                    retry_delay_seconds=self.limits.pi_scan_poll_interval,
                )
            if stat == _FSCAN_STAT_SCAN_DONE:
                return None
            if stat in (
                _FSCAN_STAT_SCAN_ABORTED,
                _FSCAN_STAT_FREQ_RESTORE_FAIL,
            ):
                name = self._FSCAN_STATE_NAMES.get(stat, str(stat))
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=f"FSCAN failed: {name} (state {stat})",
                )
            if status_cb:
                elapsed = time.monotonic() - scan_start
                name = self._FSCAN_STATE_NAMES.get(stat, str(stat))
                status_cb(f"FSCAN: {name} ({elapsed:.0f}s elapsed)")
            time.sleep(self.limits.pi_scan_poll_interval)
        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=f"FSCAN did not complete within {self.limits.pi_scan_timeout_seconds:.0f} s",
        )

    def _push_mode_results(self) -> "PhaseStepResult | None":
        for proc_suffix in ("FSCAN:PUSH_8PI9.PROC", "FSCAN:PUSH_7PI9.PROC"):
            err = self._put_pv(self.cavity.pv_addr(proc_suffix), 1, proc_suffix)
            if err is not None:
                return err
        return None

    def _read_mode_frequencies(self) -> PhaseStepResult:
        results: dict = {}
        for key, suffix in (
            ("mode_8pi_9_hz", "FSCAN:8PI9MODE"),
            ("mode_7pi_9_hz", "FSCAN:7PI9MODE"),
        ):
            try:
                results[key] = float(PV(self.cavity.pv_addr(suffix)).get())
            except Exception as exc:
                return PhaseStepResult(
                    result=PhaseResult.RETRY,
                    message=f"Could not read {suffix}: {exc}",
                    retry_delay_seconds=3.0,
                )
        results["timestamp"] = datetime.now().isoformat()
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"8π/9 mode: {results['mode_8pi_9_hz']:.0f} Hz, "
                f"7π/9 mode: {results['mode_7pi_9_hz']:.0f} Hz"
            ),
            data=results,
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
        pi = self._get_checkpoint_data("measure_pi_modes")

        initial_ts_raw = cold.get("initial_timestamp")
        initial_ts = (
            datetime.fromisoformat(initial_ts_raw) if initial_ts_raw else None
        )
        final_ts_raw = tune.get("final_timestamp")
        final_ts = (
            datetime.fromisoformat(final_ts_raw) if final_ts_raw else None
        )

        self.context.record.frequency_tuning = FrequencyTuningData(
            df_cold_hz=cold.get("df_cold_hz"),
            initial_timestamp=initial_ts,
            steps_to_resonance=tune.get("total_steps"),
            final_timestamp=final_ts,
            hz_per_microstep=probe.get("hz_per_microstep"),
            cold_landing_steps=tune.get("cold_landing_steps"),
            mode_8pi_9_frequency=pi.get("mode_8pi_9_hz"),
            mode_7pi_9_frequency=pi.get("mode_7pi_9_hz"),
        )
