"""
Setup steps shared by commissioning phases.

A phase runs the setup its measurement depends on before it measures, even when
an earlier phase already did it (Lisa Zacarias, 2026-10-14). The calls and
their order are the ones auto setup makes in `SetupCavity.setup()`
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
`SSA.run_calibration()` does not check abort while it waits on CALSTS, so an
abort during the calibration scan takes effect when the scan ends.
"""

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
    try:
        if rack_check is not None:
            ok, reason = rack_check(rack)
        else:
            on = [
                str(other)
                for other in rack.cavities.values()
                if other.number != cavity.number and other.is_on
            ]
            ok = not on
            reason = f"RF is on for {', '.join(on)}"
    except Exception as exc:
        return PhaseStepResult(
            result=PhaseResult.RETRY,
            message=f"Could not check the rest of rack {rack.rack_name}: {exc}",
            retry_delay_seconds=5.0,
        )
    if not ok:
        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=(
                f"Not zeroing DAC_AMPLITUDE: another cavity in rack "
                f"{rack.rack_name} is in use. {reason}"
            ),
        )
    return None


def turn_off_and_zero_dac(cavity) -> None:
    """RF off, then DAC_AMPLITUDE 0 on both of the rack's RF stations.

    What `SetupCavity.request_ssa_cal()` does before calibrating; its
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
