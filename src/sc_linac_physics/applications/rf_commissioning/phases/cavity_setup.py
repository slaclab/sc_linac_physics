"""
Setup steps shared by commissioning phases.

A phase runs the setup its measurement depends on before it measures, even when
an earlier phase already did it (Lisa Zacarias, 2026-10-14). The exception is a
recent SSA calibration: the phase's controller reads it with
`last_ssa_calibration()` and may keep it instead of calibrating again.

The calls and their order are the ones auto setup makes in `SetupCavity.setup()`
(auto_setup/backend/setup_cavity.py): RF off, SSA on, interlocks reset, then
`request_ssa_cal()`, then `request_auto_tune()`.

Why not call SetupCavity itself: its request_* methods only act when the auto
setup request PVs (ssa_cal_requested, auto_tune_requested) are set, and they
write the auto setup status and progress PVs that the auto setup display
shows. The functions below make the same Cavity/SSA calls without either.

Each function returns a PhaseStepResult, so a phase can use it as a step body.
Each one handles context.dry_run itself: a dry run returns before any PV read
or write and leaves the record alone.

Abort: the Cavity and SSA calls below check `cavity.abort_flag` through
`cavity.check_abort()`, which turns RF off and raises CavityAbortError. The
controller running the phase has to set that flag on abort; the commissioning
abort (context.request_abort) is only seen here before a call starts.
`SSA.run_calibration()` also checks it each time it reads CALSTS. It
raises SSACalibrationTimeoutError if the calibration takes longer than
SSA_CALIBRATION_TIMEOUT_S. calibrate_ssa reports that, or any other
calibration error, as FAILED.
"""

from dataclasses import dataclass
from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.utils.sc_linac import linac_utils

# The retry count auto setup passes to SSA.calibrate(): with attempt=2 a failed
# calibration is retried once, at drive max - 0.01, before it raises.
SSA_CAL_START_ATTEMPT = 2

# A Good SSA calibration or characterization younger than this counts as
# recent (LastSetupResult.is_recent). The cavity char controller keeps a
# recent SSA calibration instead of running it again. One hour is from
# Sebastian Aderhold's review of #408.
RECENT_RESULT_SECONDS = 3600.0


@dataclass(frozen=True)
class LastSetupResult:
    """When a setup step last ran on the cavity, and whether it came out good.

    Read from the IOC, so it counts runs made outside this tool (auto setup,
    the LLRF screens) as well as the commissioning phases.
    """

    name: str
    timestamp: datetime
    good: bool

    def age_hours(self, now: datetime | None = None) -> float:
        now = now or datetime.now()
        return (now - self.timestamp).total_seconds() / 3600

    def is_recent(
        self,
        max_age_seconds: float = RECENT_RESULT_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        """Good, and younger than max_age_seconds."""
        return self.good and self.age_hours(now) * 3600 < max_age_seconds

    def describe(self, now: datetime | None = None) -> str:
        """E.g. "SSA calibration from 2026-10-19 08:17, 3.2 h old".

        Past 48 h the age is given in days.
        """
        hours = self.age_hours(now)
        age = f"{hours / 24:.0f} days" if hours >= 48 else f"{hours:.1f} h"
        text = f"{self.name} from {self.timestamp:%Y-%m-%d %H:%M}, {age} old"
        if not self.good:
            text += ", result not good"
        return text


def last_ssa_calibration(cavity) -> LastSetupResult:
    """CALTS for the time, CALSTAT Good for the result. Reads only.

    CHECK: does the IOC update CALTS on a calibration whose CALSTAT is not
    Good? If it does, a recent CALTS alone does not mean a usable slope, which
    is why good also reads CALSTAT.
    """
    ssa = cavity.ssa
    return LastSetupResult(
        name="SSA calibration",
        timestamp=ssa.calibration_timestamp,
        good=ssa.calibration_result_good,
    )


def last_characterization(cavity) -> LastSetupResult:
    """PROBECALTS for the time, PROBECALSTS Complete for the result.

    Reads only. Complete does not mean in tolerance: finish_characterization()
    refuses to push an out-of-tolerance loaded Q or scale factor, so a
    Complete result may never have been pushed.
    """
    return LastSetupResult(
        name="Characterization",
        timestamp=cavity.characterization_timestamp,
        good=cavity.characterization_status
        == linac_utils.CALIBRATION_COMPLETE_VALUE,
    )


def decide_ssa_calibration(last: LastSetupResult | None, operator: str, ask):
    """Keep or rerun the last SSA calibration. Reads and writes no PVs.

    Returns (kept, skipped_by), or None if the operator cancelled. kept is
    the LastSetupResult to keep, or None to calibrate; skipped_by is the
    operator's name when they chose Skip.

    - last is None (CALTS or CALSTAT could not be read): calibrate, since
      nothing says the last one is usable.
    - Good and under RECENT_RESULT_SECONDS (1 h): keep, without asking.
    - Older or not Good: ask(last.describe()), which returns "rerun", "skip"
      or "cancel".

    Used by the cavity char and frequency tuning controllers, which pass the
    result to their phase as parameters["kept_ssa_calibration"] and
    parameters["ssa_calibration_skipped_by"].
    """
    if last is None:
        return (None, None)
    if last.is_recent():
        return (last, None)
    choice = ask(last.describe())
    if choice == "skip":
        return (last, operator)
    if choice == "rerun":
        return (None, None)
    return None


def kept_ssa_calibration_note(
    kept: LastSetupResult, skipped_by: str | None
) -> str:
    """The line a phase adds to its record notes when it keeps a calibration.

    E.g. "Kept the SSA calibration from 2026-10-19 08:17, 0.3 h old", or
    "SSA calibration skipped by <name>: ..." when the operator chose Skip.
    """
    if skipped_by:
        return f"SSA calibration skipped by {skipped_by}: {kept.describe()}"
    return f"Kept the {kept.describe()}"


def _aborted(context: PhaseContext, what: str) -> PhaseStepResult | None:
    if context.is_abort_requested():
        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=f"Abort requested before {what}",
        )
    return None


def check_rack_free(cavity, context: PhaseContext) -> PhaseStepResult | None:
    """Refuse a rack-wide write while another cavity in the rack is in use.

    Uses parameters["rack_check_callback"](rack) -> (ok, reason) when the
    controller supplies one. No controller supplies one yet, so without it this
    reads RFSTATE on the other cavities in the rack and refuses if any reads on.

    # CHECK: does zeroing RFS1/RFS2 DAC_AMPLITUDE disturb another cavity in
    # the rack that has RF on? Auto setup zeroes them while other cavities in
    # the rack run SSA cal in parallel (see the lock in RFStation), but that
    # says nothing about a cavity with RF on.
    """
    rack = cavity.rack
    rack_check = context.parameters.get("rack_check_callback")
    on: list[int] = []
    try:
        if rack_check is not None:
            ok, reason = rack_check(rack)
        else:
            on = [
                other.number
                for other in rack.cavities.values()
                if other.number != cavity.number and other.is_on
            ]
            ok = not on
    except Exception as exc:
        return PhaseStepResult(
            result=PhaseResult.RETRY,
            message=f"Could not check the rest of rack {rack.rack_name}: {exc}",
            retry_delay_seconds=5.0,
        )
    if ok:
        return None

    # The message says what is in the way, which write it protects, and what
    # the operator can do about it.
    if on:
        one = len(on) == 1
        problem = (
            f"RF is on for {_cavity_list(on)} of {rack.cryomodule}, which "
            f"{'shares' if one else 'share'} rack {rack.rack_name} with "
            f"cavity {cavity.number}"
        )
        fix = f"Turn RF off on {'that cavity' if one else 'those cavities'}"
    else:
        problem = f"another cavity in rack {rack.rack_name} is in use: {reason}"
        fix = "Wait until that cavity is free"
    return PhaseStepResult(
        result=PhaseResult.FAILED,
        message=(
            f"Can't continue: {problem}. This step sets DAC_AMPLITUDE to 0 on "
            f"rack {rack.rack_name}'s RFS1 and RFS2. {fix}, then run it again."
        ),
    )


def _cavity_list(numbers: list[int]) -> str:
    """[2] -> "cavity 2"; [1, 2, 3] -> "cavities 1, 2 and 3"."""
    if len(numbers) == 1:
        return f"cavity {numbers[0]}"
    listed = ", ".join(str(n) for n in numbers[:-1])
    return f"cavities {listed} and {numbers[-1]}"


def turn_off_and_zero_dac(cavity) -> None:
    """Turn RF off, then zero DAC_AMPLITUDE on both of the rack's RF stations.

    `SetupCavity.request_ssa_cal()` does the same before calibrating. Its
    docstring says the calibration procedure requires the DAC amplitudes at 0.
    turn_off() writes RFCTRL 0 and waits for RFSTATE to read off. Callers run
    check_rack_free() first.
    """
    cavity.turn_off()
    cavity.rack.rfs1.dac_amp = 0
    cavity.rack.rfs2.dac_amp = 0


def calibrate_ssa(
    cavity, context: PhaseContext, drive_max: float | None = None
) -> PhaseStepResult:
    """Calibrate the SSA the way auto setup does, and record the result.

    In order: the rack check, RFCTRL 0, RFS1/RFS2 DAC_AMPLITUDE 0, then
    `SSA.calibrate(drive_max, attempt=2)`. That writes DRV_MAX_REQ, resets the
    SSA if faulted, turns it on, writes INTLK_RESET_ALL and CALSTRT, and waits
    on CALSTS. If CALSTAT is good, forward power is at or above
    fwd_power_lower_limit and the slope is in tolerance, it processes
    PUSH_SSA_SLOPE.PROC. There is no operator review before that push. It does
    not save the slope. On a failed check it retries once at drive_max - 0.01.

    drive_max defaults to SSA.drive_max, which reads DRV_MAX_SAVE (auto setup
    uses the same). The record stores the drive max requested here; after a
    retry DRV_MAX_REQ holds a value 0.01 lower.

    On success record.ssa_char is replaced, so the record carries the slope
    that is now pushed.
    """
    if context.dry_run:
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Dry run: SSA calibration not run",
            data={"dry_run": True},
        )
    aborted = _aborted(context, "SSA calibration")
    if aborted is not None:
        return aborted
    busy = check_rack_free(cavity, context)
    if busy is not None:
        return busy

    ssa = cavity.ssa
    try:
        if drive_max is None:
            drive_max = ssa.drive_max
        turn_off_and_zero_dac(cavity)
        ssa.calibrate(drive_max, attempt=SSA_CAL_START_ATTEMPT)
        slope = ssa.measured_slope
        max_fwd_pwr = ssa.max_fwd_pwr
    except (
        linac_utils.SSACalibrationError,
        linac_utils.SSACalibrationToleranceError,
        linac_utils.SSAFaultError,
        linac_utils.CavityFaultError,
        linac_utils.CavityAbortError,
    ) as exc:
        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=f"SSA calibration failed: {exc}",
        )
    except Exception as exc:
        return PhaseStepResult(
            result=PhaseResult.RETRY,
            message=f"Transient error during SSA calibration: {exc}",
            retry_delay_seconds=5.0,
        )

    record = getattr(context, "record", None)
    if record is not None:
        record.ssa_char = SSACharacterization(
            max_drive=drive_max,
            slope_new=slope,
            max_fwd_pwr=max_fwd_pwr,
            calibration_passed=True,
        )
    return PhaseStepResult(
        result=PhaseResult.SUCCESS,
        message=(
            f"SSA calibrated at drive max {drive_max:.2f}: slope {slope:.5f} "
            "pushed (PUSH_SSA_SLOPE)"
        ),
        data={
            "drive_max": drive_max,
            "slope_new": slope,
            "max_fwd_pwr": max_fwd_pwr,
        },
    )


def tune_to_resonance(
    cavity, context: PhaseContext, max_stepper_temp: float
) -> PhaseStepResult:
    """Tune to resonance the way auto setup does: Cavity.move_to_resonance().

    move_to_resonance() runs setup_tuning() first: piezo enable, piezo feedback
    off, piezo DC offset 0, SEL_ASET to SAFE_PULSED_DRIVE_LEVEL, chirp mode,
    RFCTRL on, then find_chirp_range(). It writes TUNE_CONFIG OTHER, moves the
    stepper until the detune is inside 50 Hz (500 Hz on a harmonic
    linearizer), and writes TUNE_CONFIG RESONANCE. RF is left on in chirp mode.

    Compared with FrequencyTuningPhase.tune_to_resonance it has no DF_COLD
    gate, no operator-confirmed SCALE (it moves on the SCALE already set), no
    over-temperature acknowledgement, and it does not write NSTEPS_COLD. It
    keeps the stepper temperature guard: max_stepper_temp is passed through.
    """
    if context.dry_run:
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Dry run: tuning to resonance not run",
            data={"dry_run": True},
        )
    aborted = _aborted(context, "tuning")
    if aborted is not None:
        return aborted

    try:
        cavity.move_to_resonance(max_stepper_temp=max_stepper_temp)
        # move_to_resonance returns only once the detune is inside tolerance.
        # Read back what the measurement after this needs: RF on, detune valid.
        rf_on = cavity.is_on
        detune_invalid = cavity.detune_invalid
        detune = cavity.detune
    except (
        linac_utils.StepperTempError,
        linac_utils.DetuneError,
        linac_utils.StepperError,
        linac_utils.StepperAbortError,
        linac_utils.CavityAbortError,
        linac_utils.CavityFaultError,
    ) as exc:
        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=f"Tuning to resonance failed: {exc}",
        )
    except Exception as exc:
        return PhaseStepResult(
            result=PhaseResult.RETRY,
            message=f"Transient error during tuning: {exc}",
            retry_delay_seconds=5.0,
        )

    if not rf_on or detune_invalid:
        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=(
                "Tuned, but the cavity is not ready to measure: "
                + ("RF is off" if not rf_on else "detune readback is invalid")
            ),
        )
    return PhaseStepResult(
        result=PhaseResult.SUCCESS,
        message=f"Tuned to resonance, detune {detune:.0f} Hz",
        data={"detune_hz": detune},
    )
