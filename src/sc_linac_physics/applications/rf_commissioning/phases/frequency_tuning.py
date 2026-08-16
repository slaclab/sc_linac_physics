"""
Frequency Tuning Phase

Tunes the cavity stepper to resonance after initial cool-down.  Cavities are
expected to start at the COLD tune config.  Before moving the stepper this
phase:
  1. Checks that the stepper is idle, then prepares the cavity for tuning —
     RF off, SSA on, reset interlocks, set up chirp (mirrors the production
     SetupCavity + Cavity.setup_tuning path); warns (but does not fail) if the
     cavity is not at the COLD tune config.
  2. Records the cold-landing detune for display; the operator pushes it to
     DF_COLD via the UI after reviewing.
  3. Runs a probe move to measure Hz/microstep; the operator confirms and the UI
     writes the value (to SCALE_CALC.B) via apply_hz_per_step.
  4. Gates on DF_COLD having been recorded, then delegates to
     Cavity._auto_tune to move to resonance (with a per-iteration stepper
     temperature guard).  There is no automatic cool-down: if the temperature
     exceeds the limit the step fails and the operator must investigate and
     re-run with a higher acknowledgement ceiling (over_temp_ack_c).  After
     converging, writes the (signed) return-trip step count to the NSTEPS_COLD
     PV and sets tune_config to RESONANCE.
  5. Runs a single-cavity FSCAN to find the 8π/9 and 7π/9 parasitic modes and
     pushes results to the cavity mode-frequency PVs.
  6. Writes a FrequencyTuningData record.
"""

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
from sc_linac_physics.utils.sc_linac import linac_utils


def _emit_status(cb, msg: str) -> None:
    """Call a status callback, swallowing any exception."""
    if cb:
        try:
            cb(msg)
        except Exception:
            pass


# Small slack on the drive-level gate so PV rounding does not trip it.
_DRIVE_TOLERANCE = 0.5


@dataclass
class FrequencyTuningLimits:
    """Configurable limits for the frequency tuning phase."""

    tolerance_hz: float = 50.0
    probe_steps: int = 50_000
    # Run commissioning moves at max speed; StepperTuner.move() restores the
    # speed to DEFAULT_STEPPER_SPEED via restore_defaults() after each move.
    move_speed: int = linac_utils.MAX_STEPPER_SPEED
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
    1. verify_initial_state    – stepper idle; prepare cavity (SSA on, reset interlocks, setup_tuning)
    2. record_cold_landing     – record cold-landing detune (operator pushes to DF_COLD via UI)
    3. probe_stepper_direction – measure Hz/microstep (operator confirms; UI writes to SCALE_CALC.B)
    4. apply_hz_per_step       – write confirmed Hz/microstep to SCALE_CALC.B
    5. tune_to_resonance       – delegate to Cavity._auto_tune (temp guard); write NSTEPS_COLD
    6. measure_pi_modes        – single-cavity FSCAN for 8π/9 and 7π/9 parasitic modes
    7. record_results          – write FrequencyTuningData to commissioning record
    """

    def __init__(
        self, context: PhaseContext, limits: FrequencyTuningLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or FrequencyTuningLimits()
        self._history_start = len(context.record.phase_history)
        self.cavity = None
        # Signed: positive means +steps increase cavity frequency (matches SCALE PV convention)
        self._hz_per_microstep: float | None = None

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
            "check_state_for_stage_2": self._check_state_for_stage_2,
            "probe_stepper_direction": self._probe_stepper_direction,
            "check_state_for_stage_3": self._check_state_for_stage_3,
            "apply_hz_per_step": self._apply_hz_per_step,
            "tune_to_resonance": self._tune_to_resonance,
            "check_state_for_stage_4": self._check_state_for_stage_4,
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
        return self.cavity.stepper_temp_pv_obj.get()

    _DF_COLD_MATCH_TOLERANCE_HZ = 1.0

    def _check_df_cold_recorded(self) -> "PhaseStepResult | None":
        """Ensure the operator pushed the cold-landing detune to DF_COLD.

        Returns a FAILED/RETRY result if DF_COLD was not recorded, else None.
        The recorded cold-landing detune (from record_cold_landing) is the
        reliable reference: DF_COLD defaults to a valid 0, so there is no
        INVALID severity to key off — we require DF_COLD to match it.
        """
        # One source: the record. _record_cold_landing writes the frequency
        # there, so this holds within a single run and equally after a relaunch.
        # Reading the step's phase_history checkpoint instead would only work
        # in-session — that list is in memory, with no table behind it.
        recorded = self._persisted_df_cold_hz()
        if recorded is None:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    "Cold landing frequency was not recorded — run "
                    "record_cold_landing before tuning"
                ),
            )
        # DF_COLD is written by the operator via the UI after reviewing the
        # cold-landing frequency; the backend reads it back to gate tuning.
        try:
            df_cold = self.cavity.df_cold_pv_obj.get()
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
                    "DF_COLD does not match the recorded cold-landing "
                    f"frequency — push {recorded:.0f} Hz to DF_COLD before "
                    f"tuning (DF_COLD currently reads {df_cold:.0f} Hz)"
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Prerequisite-check steps (read-only, no hardware mutations)
    # ------------------------------------------------------------------

    def _check_motor_and_cavity(self) -> "PhaseStepResult | None":
        """Blockers that no amount of re-preparation can clear.

        Returns a FAILED result if the stepper cannot safely move, or None.
        Conditions the phase can fix itself live in _check_tuning_setup().
        """
        try:
            motor_moving = self.cavity.stepper_tuner.motor_moving
            on_limit_switch = self.cavity.stepper_tuner.on_limit_switch
            is_online = self.cavity.is_online
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read stepper/cavity state: {exc}",
                retry_delay_seconds=3.0,
            )

        if motor_moving:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor already moving — abort or wait for it to stop",
            )
        if on_limit_switch:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor is on a limit switch — manual intervention required",
            )
        if not is_online:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Cavity is not online — run Stage 1 to prepare it for tuning",
            )
        return None

    def _check_tuning_setup(self) -> str | None:
        """Return why the cavity is not set up for tuning, or None if it is.

        Everything setup_tuning() establishes: RF on in chirp mode with a valid
        detune, piezo enabled and in Manual, drive clamped to the safe pulsed
        level. is_online is hw_mode ("in service") and notices none of this, so
        without this check a cavity switched off after Stage 1 sailed through
        and Stage 2 moved the stepper against a detune that was not tracking.

        Returns a reason string rather than a PhaseStepResult because the
        caller re-prepares the cavity and retries before surfacing anything.
        """
        try:
            if not self.cavity.is_on:
                return "RF is off"
            # detune_invalid branches on rf_mode: outside chirp mode it inspects
            # DFBEST rather than the CHIRP:DF the tuning stages read, so treat
            # it as a strong signal rather than a complete one.
            if self.cavity.detune_invalid:
                return "detune readback is invalid"
            if not self.cavity.piezo.is_enabled:
                return "piezo is disabled"
            # Feedback actively counteracts the stepper rather than merely
            # invalidating a reading, so it matters even though tuning could
            # technically proceed.
            if not self.cavity.piezo.in_manual:
                return "piezo is in Feedback mode and would fight the stepper"
            drive = float(self.cavity.drive_level)
        except Exception as exc:
            return f"could not read cavity setup state ({exc})"

        # Only an over-drive is unsafe; running below the safe level is a
        # legitimate operator choice and must not trigger a re-prepare.
        if drive > linac_utils.SAFE_PULSED_DRIVE_LEVEL + _DRIVE_TOLERANCE:
            return (
                f"drive level is {drive:.1f}, above the "
                f"{linac_utils.SAFE_PULSED_DRIVE_LEVEL} used for chirp tuning"
            )
        return None

    def _ensure_tuning_setup(self) -> "PhaseStepResult | None":
        """Re-apply setup_tuning() if the cavity drifted out of tuning state.

        Stage 1 is the only stage that prepares the cavity, and its Run button
        is disabled once it succeeds — so an operator who turns the cavity off
        mid-workflow has no way back. Rather than failing with an instruction
        they cannot follow, stages 2 and 3 re-prepare and carry on. Safe to
        repeat: setup_tuning() does not touch the recorded cold landing, which
        is the one thing in Stage 1 that must not run twice.
        """
        reason = self._check_tuning_setup()
        if reason is None:
            return None

        status_cb = self.context.parameters.get("status_update_callback")
        _emit_status(
            status_cb, f"Cavity not set up for tuning ({reason}) — re-preparing"
        )
        prepared = self._prepare_and_read(status_cb)
        if isinstance(prepared, PhaseStepResult):
            return prepared

        reason = self._check_tuning_setup()
        if reason is not None:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Cavity is still not ready for tuning after re-preparing: "
                    f"{reason}"
                ),
            )
        _emit_status(status_cb, "✓ Cavity re-prepared for tuning")
        return None

    def _check_state_for_stage_2(self) -> PhaseStepResult:
        """Verify hardware is ready for stepper probing (Stage 2).

        Checks motor idle, not on limit switch, cavity online, re-applies
        setup_tuning() if the cavity drifted out of tuning state, and requires
        the cold landing to be committed to DF_COLD first.
        """
        bad = self._check_motor_and_cavity()
        if bad is not None:
            return bad

        not_ready = self._ensure_tuning_setup()
        if not_ready is not None:
            return not_ready

        # Stage 2 is the first step that moves the stepper, and moving it
        # destroys the ability to measure the cold landing: once the cavity has
        # been tuned away, the resting frequency is gone from the hardware.
        # DF_COLD must therefore hold the agreed value before any motion, not
        # merely before Stage 3. Deliberately a gate and not an automatic write
        # — which value belongs in DF_COLD is an operator judgment, and may be a
        # number from a partner lab rather than the one measured here.
        df_cold_bad = self._check_df_cold_recorded()
        if df_cold_bad is not None:
            return df_cold_bad

        try:
            temp = self._read_temp()
            detune = self.cavity.detune_chirp
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read cavity detune/temperature: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Cavity ready for probing — temp {temp:.1f} °C, "
                f"detune {detune:.0f} Hz"
            ),
        )

    def _check_state_for_stage_3(self) -> PhaseStepResult:
        """Verify hardware and data are ready for tune-to-resonance (Stage 3).

        In addition to the motor/online checks, confirms that the operator
        has pushed DF_COLD so the tuning target is set.
        """
        bad = self._check_motor_and_cavity()
        if bad is not None:
            return bad

        not_ready = self._ensure_tuning_setup()
        if not_ready is not None:
            return not_ready

        df_cold_bad = self._check_df_cold_recorded()
        if df_cold_bad is not None:
            return df_cold_bad

        try:
            temp = self._read_temp()
            detune = self.cavity.detune_chirp
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read cavity detune/temperature: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Cavity ready for tuning — temp {temp:.1f} °C, "
                f"detune {detune:.0f} Hz"
            ),
        )

    def _check_state_for_stage_4(self) -> PhaseStepResult:
        """Verify the cavity is online before running FSCAN (Stage 4).

        FSCAN does not require chirp mode, so only basic online/motor
        checks are needed.
        """
        try:
            motor_moving = self.cavity.stepper_tuner.motor_moving
            is_online = self.cavity.is_online
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read cavity state: {exc}",
                retry_delay_seconds=3.0,
            )

        if motor_moving:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor still moving — wait for it to stop before scanning",
            )
        if not is_online:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Cavity is not online — cannot run FSCAN",
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Cavity online and stepper idle — ready for FSCAN",
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

        status_cb = self.context.parameters.get("status_update_callback")
        _emit_status(status_cb, "Reading stepper and cavity state...")
        try:
            motor_moving = self.cavity.stepper_tuner.motor_moving
            on_limit_switch = self.cavity.stepper_tuner.on_limit_switch
            is_online = self.cavity.is_online
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read initial stepper/cavity state: {exc}",
                retry_delay_seconds=3.0,
            )

        if motor_moving:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor already moving — abort or wait for it to stop",
            )

        if on_limit_switch:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Stepper motor is on a limit switch — manual intervention required",
            )

        if not is_online:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Cavity is not online — cannot prepare it for tuning",
            )

        _emit_status(
            status_cb, "✓ Stepper idle, cavity online — preparing cavity..."
        )
        prepared = self._prepare_and_read(status_cb)
        if isinstance(prepared, PhaseStepResult):
            return prepared
        temp, detune = prepared

        tune_config_warning = self._tune_config_warning()

        message = (
            "Cavity prepared for tuning (SSA on, interlocks reset, chirp valid). "
            f"Temp {temp:.1f} °C, detune {detune:.0f} Hz"
        )
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

    def _prepare_and_read(
        self, status_cb=None
    ) -> "PhaseStepResult | tuple[float, float]":
        """Read temp, prepare the cavity, read detune.

        Returns (temp_c, detune_hz) on success, or a FAILED/RETRY
        PhaseStepResult if preparation could not complete.
        """
        try:
            temp = self._read_temp()
            self._prepare_cavity_for_tuning(status_cb)
            return temp, self.cavity.detune_chirp
        except linac_utils.DetuneError as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    "Could not establish a valid chirp detune "
                    f"(find_chirp_range exhausted its range): {exc}"
                ),
            )
        except linac_utils.CavityFaultError as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Cavity still faulted after interlock resets: {exc}",
            )
        except (
            linac_utils.StepperAbortError,
            linac_utils.CavityAbortError,
        ) as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Aborted during cavity setup: {exc}",
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not prepare cavity / read state: {exc}",
                retry_delay_seconds=3.0,
            )

    def _prepare_cavity_for_tuning(self, status_cb=None) -> None:
        """Prepare the cavity for chirp tuning, mirroring the production path.

        RF off first so a latched interlock clears even if RF was requested on,
        then SSA on, reset interlocks, and set up chirp tuning — the same
        sequence as SetupCavity.setup + Cavity.setup_tuning.
        """

        _emit_status(status_cb, "Turning RF off...")
        self.cavity.turn_off()
        _emit_status(status_cb, "Turning SSA on...")
        self.cavity.ssa.turn_on()
        _emit_status(status_cb, "Resetting interlocks...")
        self.cavity.reset_interlocks()
        # setup_tuning(use_sela=False) puts the cavity in chirp mode (piezo
        # feedback off, RF driven by the chirp generator rather than SELA)
        # so detune can be read via CHIRP:DF while the stepper is moved.
        _emit_status(status_cb, "Setting up chirp mode...")
        self.cavity.setup_tuning()

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

        # Record it on the record, not only in the step's returned data. The
        # record is the one copy that outlives both the step's checkpoint (in
        # memory) and the session, so it is what later steps and later launches
        # both read. See _check_df_cold_recorded.
        initial_timestamp = datetime.now()
        self._store_phase_fields(
            df_cold_hz=df_cold_hz, initial_timestamp=initial_timestamp
        )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Cold landing frequency recorded: detune={df_cold_hz:.0f} Hz. "
            "Push to DF_COLD when satisfied.",
            data={
                "df_cold_hz": df_cold_hz,
                "initial_timestamp": initial_timestamp.isoformat(),
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
        """Execute the forward+back probe move; return (detune0_hz, detune1_hz)."""
        self.cavity.stepper_tuner.reset_signed_steps()
        detune0_hz = self.cavity.detune_chirp
        try:
            if probe_cb:
                probe_cb(0, detune0_hz)
        except Exception:
            pass
        self.cavity.stepper_tuner.move(probe, speed=speed, check_detune=False)
        detune1_hz = self.cavity.detune_chirp
        try:
            if probe_cb:
                probe_cb(probe, detune1_hz)
        except Exception:
            pass
        self.cavity.stepper_tuner.move(-probe, speed=speed, check_detune=False)
        return detune0_hz, detune1_hz

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
            detune0_hz, detune1_hz = self._do_probe_move(
                probe, probe_cb, speed=speed
            )
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

        delta = detune1_hz - detune0_hz

        if abs(delta) < self.limits.min_probe_delta_hz:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Probe move of {probe} steps produced only {abs(delta):.1f} Hz change "
                    f"(minimum {self.limits.min_probe_delta_hz:.1f} Hz required). "
                    "Check that the stepper is mechanically connected and the cavity is at 2 K."
                ),
            )

        # SCALE is defined as the cavity frequency change per microstep
        # (d(cavity_freq)/d(microstep), i.e. Hz/microstep; probe is in
        # microsteps). A positive number of microsteps decreases CHIRP:DF —
        # this is the same relationship Cavity._auto_tune relies on (a
        # positive detune drives a positive step estimate that reduces it) —
        # so d(CHIRP:DF)/d(microstep) = -SCALE. We measured
        # delta = d(CHIRP:DF) for +probe microsteps, so SCALE = -delta/probe.
        signed_hz_per_microstep = -delta / probe
        self._hz_per_microstep = signed_hz_per_microstep
        self._store_phase_fields(hz_per_microstep=signed_hz_per_microstep)

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Direction probe: Δdetune={delta:+.0f} Hz for +{probe} microsteps. "
                f"Measured {abs(self._hz_per_microstep):.4f} Hz/microstep (confirm to write to SCALE PV). "
                f"move(+N) "
                f"{'increases' if signed_hz_per_microstep > 0 else 'decreases'} frequency."
            ),
            data={
                "d0_hz": detune0_hz,
                "d1_hz": detune1_hz,
                "s_d0": 0,
                "s_d1": probe,
                "delta_hz": delta,
                "hz_per_microstep": self._hz_per_microstep,
                "probe_steps": probe,
            },
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

    def _tuning_iteration_hook(self) -> None:
        """Per-iteration hook passed to Cavity._auto_tune.

        Surfaces the phase-level abort flag as an exception (so _auto_tune's
        loop unwinds) and feeds the live tuning plot.  Signed step count comes
        straight from the REG_TOTSGN hardware register that _auto_tune's moves
        accumulate — no parallel bookkeeping needed.
        """
        if self.context.is_abort_requested():
            raise linac_utils.CavityAbortError("Abort requested during tuning")
        self._emit_tuning_point(
            self.context.parameters.get("tuning_update_callback")
        )

    def _tune_to_resonance(self) -> PhaseStepResult:
        if self.context.dry_run:
            return self._tuning_dry_run_result()

        if not self._hz_per_microstep:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="hz_per_microstep not set — probe_stepper_direction must run first",
            )

        df_cold_err = self._check_df_cold_recorded()
        if df_cold_err is not None:
            return df_cold_err

        # Operator-authorized over-temp ceiling (re-run raises it); default is
        # the plain temperature limit.  _auto_tune fails hard on a breach.
        ack_ceiling = self.context.parameters.get("over_temp_ack_c")
        max_temp = (
            ack_ceiling if ack_ceiling is not None else self.limits.temp_limit_c
        )

        # Pre-seed the plot with the current state before the tuning loop
        # starts.  The 500 ms live-refresh timer requires _live_steps to be
        # non-empty before it will emit a cursor update; without this, the
        # timer bails on every tick during the first (often large) stepper
        # move and the live detune appears frozen until the second iteration
        # hook fires.
        self._emit_tuning_point(
            self.context.parameters.get("tuning_update_callback")
        )

        bridged = self._run_auto_tune(max_temp)
        if bridged is not None:
            return bridged

        return self._finalize_after_auto_tune(ack_ceiling)

    def _emit_tuning_point(
        self, callback, step_count: int | None = None
    ) -> None:
        """Emit one (signed_steps, detune) plot point via the tuning callback.

        Reads the step register from hardware when step_count is None.
        Silently ignores all errors so a plot glitch never stops tuning.
        """
        if callback is None:
            return
        try:
            steps = (
                step_count
                if step_count is not None
                else round(
                    self.cavity.stepper_tuner.step_signed_pv_obj.get() or 0
                )
            )
            callback(steps, self.cavity.detune_chirp)
        except Exception:
            pass

    def _finalize_after_auto_tune(
        self, ack_ceiling: float | None
    ) -> PhaseStepResult:
        """Read final step count, emit the at-resonance plot point, persist results."""
        # Read the accumulated signed step count once, from the hardware
        # register _auto_tune drove. This is the outbound trip; the negation
        # into NSTEPS_COLD happens in _write_cold_landing_steps().
        try:
            signed_total = round(
                self.cavity.stepper_tuner.step_signed_pv_obj.get() or 0
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read signed step count after tuning: {exc}",
                retry_delay_seconds=3.0,
            )

        # Emit the final at-resonance data point. The iteration hook fires
        # before each move, so the last move's post-state is never
        # automatically emitted — this fills that gap.
        self._emit_tuning_point(
            self.context.parameters.get("tuning_update_callback"), signed_total
        )

        err = self._write_cold_landing_steps(signed_total)
        if err is not None:
            return err

        err = self._write_tune_config_resonance()
        if err is not None:
            return err

        return self._tuning_success_result(signed_total, ack_ceiling)

    def _run_auto_tune(self, max_temp: float) -> "PhaseStepResult | None":
        """Delegate the tuning loop to Cavity._auto_tune.

        Returns a FAILED/RETRY PhaseStepResult on failure, or None on success.
        """
        try:
            self.cavity._auto_tune(
                delta_hz_func=lambda: self.cavity.detune_chirp,
                tolerance=self.limits.tolerance_hz,
                iteration_callback=self._tuning_iteration_hook,
                max_stepper_temp=max_temp,
            )
        except linac_utils.StepperTempError as exc:
            temp = self._safe_read_temp()
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"{exc}. Investigate; to proceed, acknowledge and re-run "
                    "with a higher over_temp_ack_c."
                ),
                data={
                    "stepper_temp_c": temp,
                    "temp_limit_c": self.limits.temp_limit_c,
                    "requires_over_temp_ack": True,
                },
            )
        except (
            linac_utils.DetuneError,
            linac_utils.StepperError,
            linac_utils.StepperAbortError,
            linac_utils.CavityAbortError,
        ) as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Tuning to resonance failed: {exc}",
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Transient error during tuning: {exc}",
                retry_delay_seconds=3.0,
            )
        return None

    def _safe_read_temp(self) -> float | None:
        try:
            return self._read_temp()
        except Exception:
            return None

    def _tuning_success_result(
        self, signed_total: int, ack_ceiling: float | None
    ) -> PhaseStepResult:
        final_timestamp = datetime.now()
        data = {
            "total_steps": abs(signed_total),
            "cold_landing_steps": -signed_total,
            "final_timestamp": final_timestamp.isoformat(),
        }
        self._store_phase_fields(
            steps_to_resonance=abs(signed_total),
            cold_landing_steps=-signed_total,
            final_timestamp=final_timestamp,
        )
        # Audit trail: if the operator authorized proceeding over the temp
        # limit, record the ceiling and who authorized it.
        if ack_ceiling is not None and ack_ceiling > self.limits.temp_limit_c:
            data["over_temp_acknowledged_c"] = ack_ceiling
            data["over_temp_acknowledged_by"] = self.context.operator

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"Reached resonance. NSTEPS_COLD set to {-signed_total}. "
                "tune_config set to RESONANCE."
            ),
            data=data,
        )

    def _write_cold_landing_steps(
        self, signed_total: int
    ) -> "PhaseStepResult | None":
        # NSTEPS_COLD stores the return-trip step count (from resonance to cold
        # landing), which is the negation of the steps we just took.
        try:
            self.cavity.stepper_tuner.steps_cold_landing_pv_obj.put(
                -signed_total
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not write NSTEPS_COLD after tuning: {exc}",
                retry_delay_seconds=3.0,
            )
        return None

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
        """Run a single-cavity FSCAN via Rack.run_fscan and read back results.

        Checks rack exclusivity (commissioning policy), delegates the scan
        sequence to the rack, then reads back the 8π/9 and 7π/9 frequencies.
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

        try:
            rack.run_fscan(
                [self.cavity],
                freq_start=self.limits.pi_scan_freq_start,
                freq_stop=self.limits.pi_scan_freq_stop,
                rms_thresh=self.limits.pi_scan_rms_thresh,
                mode_overlap=self.limits.pi_scan_mode_overlap,
                poll_interval=self.limits.pi_scan_poll_interval,
                timeout_seconds=self.limits.pi_scan_timeout_seconds,
                status_callback=self.context.parameters.get(
                    "status_update_callback"
                ),
                should_abort=self.context.is_abort_requested,
            )
        except (linac_utils.FSCANError, linac_utils.CavityAbortError) as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"FSCAN failed: {exc}",
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Transient error during FSCAN: {exc}",
                retry_delay_seconds=3.0,
            )

        return self._read_mode_frequencies()

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

    def _read_mode_frequencies(self) -> PhaseStepResult:
        results: dict = {}
        for key, pv_obj, label in (
            (
                "mode_8pi_9_hz",
                self.cavity.fscan_8pi9_mode_pv_obj,
                "FSCAN:8PI9MODE",
            ),
            (
                "mode_7pi_9_hz",
                self.cavity.fscan_7pi9_mode_pv_obj,
                "FSCAN:7PI9MODE",
            ),
        ):
            try:
                results[key] = float(pv_obj.get())
            except Exception as exc:
                return PhaseStepResult(
                    result=PhaseResult.RETRY,
                    message=f"Could not read {label}: {exc}",
                    retry_delay_seconds=3.0,
                )
        results["timestamp"] = datetime.now().isoformat()
        self._store_phase_fields(
            mode_8pi_9_frequency=results["mode_8pi_9_hz"],
            mode_7pi_9_frequency=results["mode_7pi_9_hz"],
        )
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
            message="Results collected; ready to finalize",
        )

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _persisted_df_cold_hz(self) -> float | None:
        """Return the cold-landing detune stored on the record, if any."""
        record = getattr(self.context, "record", None)
        data = getattr(record, "frequency_tuning", None) if record else None
        return getattr(data, "df_cold_hz", None) if data else None

    def _store_phase_fields(self, **fields) -> None:
        """Merge step results onto the record as each step produces them.

        Each step stores its own contribution so the record is complete even
        when the phase is run across more than one launch. Without this, the
        only copy of a step's result is its phase_history checkpoint, which is
        in-memory — so finalize_phase() would write None for every stage
        completed in an earlier session and mark the phase not-complete.

        Only the named fields are touched, so a later stage cannot wipe an
        earlier one. Persisting to the database is the session's job; the phase
        layer deliberately has no database dependency.
        """
        record = getattr(self.context, "record", None)
        if record is None:
            return
        data = record.frequency_tuning or FrequencyTuningData()
        for name, value in fields.items():
            if value is not None:
                setattr(data, name, value)
        record.frequency_tuning = data

    def _store_df_cold_hz(self, df_cold_hz: float) -> None:
        """Store the cold-landing detune on the record."""
        self._store_phase_fields(df_cold_hz=df_cold_hz)

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

        # When a single stage is re-run (e.g. Stage 4 only), checkpoints for
        # earlier stages won't appear in this phase's history window.  Fall
        # back to whatever was already stored on the record so those fields
        # are preserved rather than overwritten with None.
        prev = self.context.record.frequency_tuning

        def _fallback(new_val, attr: str):
            if new_val is not None:
                return new_val
            return getattr(prev, attr, None) if prev else None

        initial_ts_raw = cold.get("initial_timestamp")
        initial_ts = (
            datetime.fromisoformat(initial_ts_raw) if initial_ts_raw else None
        )
        final_ts_raw = tune.get("final_timestamp")
        final_ts = (
            datetime.fromisoformat(final_ts_raw) if final_ts_raw else None
        )

        self.context.record.frequency_tuning = FrequencyTuningData(
            df_cold_hz=_fallback(cold.get("df_cold_hz"), "df_cold_hz"),
            initial_timestamp=_fallback(initial_ts, "initial_timestamp"),
            steps_to_resonance=_fallback(
                tune.get("total_steps"), "steps_to_resonance"
            ),
            final_timestamp=_fallback(final_ts, "final_timestamp"),
            hz_per_microstep=_fallback(
                probe.get("hz_per_microstep"), "hz_per_microstep"
            ),
            cold_landing_steps=_fallback(
                tune.get("cold_landing_steps"), "cold_landing_steps"
            ),
            mode_8pi_9_frequency=_fallback(
                pi.get("mode_8pi_9_hz"), "mode_8pi_9_frequency"
            ),
            mode_7pi_9_frequency=_fallback(
                pi.get("mode_7pi_9_hz"), "mode_7pi_9_frequency"
            ),
        )
