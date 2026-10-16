"""
Cavity Characterization Phase

Calibrates the cavity's RF probe and measures the loaded Q of the power coupler,
then lets the operator review the results before they are pushed to the cavity.

Almost none of the measurement lives here. `Cavity` already implements the whole
sequence — `start_characterization()`, the `characterization_running` /
`characterization_crashed` status predicates, `calculate_probe_q()`,
`push_loaded_q()`, `push_scale_factor()`, `wait_for_characterization()`, and the
tolerance checks `measured_loaded_q_in_tolerance` and
`measured_scale_factor_in_tolerance`. Auto setup's `request_characterization()`
is a twelve-line wrapper over the same code. This phase is deliberately a
similarly thin wrapper: if a step body here grows past a few lines of
orchestration, something is being duplicated.

Deliberate divergences from `Cavity.characterize()`, each commented where it
happens:
- It stops between measuring and pushing. `characterize()` bundles start, wait
  and push into one blocking call, which suits unattended setup. Commissioning
  needs an operator to see loaded Q, scale factor and probe Q first.
- It always starts a fresh run (`_start_characterization`). `characterize()`
  reuses a COMPLETE result under 60 s old.
- An operator may push an out-of-tolerance value after confirming
  (`_push_results`). `finish_characterization()` refuses.

Sequence:
  1. verify_initial_state    – cavity online, stepper idle, SSA on and not
                               calibrating; warn if SSA calibration or tuning
                               are stale
  2. set_drive_level         – clamp drive for characterization (operator may
                               override the default)
  3. start_characterization  – kick off PROBECALSTRT; clear the previous
                               run's results from the record
  4. wait_for_completion     – poll PROBECALSTS until it settles, then reject a
                               crash, or a PROBECALTS too old or not later
                               than the one read before the start
  5. read_results            – read loaded Q and scale factor, trigger the
                               probe-Q calculation and read probe Q, flag
                               loaded Q or scale factor out of tolerance.
                               Nothing is pushed.
  6. push_results            – refused unless parameters["confirmed_loaded_q"]
                               matches the loaded Q read in step 5 and the
                               cavity's result is unchanged since; then push
                               loaded Q, scale factor and probe Q
  7. record_results          – write CavityCharacterization onto the record
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseExecutionError,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityCharacterizationError,
)


@dataclass
class CavityCharLimits:
    """Configurable limits for the cavity characterization phase."""

    # Ryan's outline calls for 10% drive on 7 kW SSAs and 15% on 3.8 kW ones.
    # SSA.rated_power_kw reads the rating from SSA:Type, but the outline gives
    # no drive level for the 4.6 kW and 1 kW SSAs. Until that is decided the
    # phase starts from the existing safe pulsed level for every SSA, and the
    # operator can change it, which the outline asks for regardless.
    default_drive_level: float = linac_utils.SAFE_PULSED_DRIVE_LEVEL
    max_drive_level: float = 15.0

    status_poll_interval: float = 1.0
    status_settle_delay: float = 2.0
    characterization_timeout_seconds: float = 300.0

    # How old an SSA calibration or frequency tuning result may be before this
    # phase warns. Best practice is to characterize against a freshly calibrated
    # and tuned cavity; stale inputs are a warning rather than a hard stop
    # because the workflow already enforces that those phases ran at all.
    prerequisite_staleness_hours: float = 24.0


class CavityCharPhase(PhaseBase):
    """Cavity Characterization: probe calibration and loaded-Q measurement."""

    def __init__(
        self, context: PhaseContext, limits: CavityCharLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or CavityCharLimits()
        self.cavity = None
        self._drive_level: float | None = None
        self._loaded_q: float | None = None
        self._scale_factor: float | None = None
        self._probe_q: float | None = None
        self._loaded_q_in_tolerance: bool | None = None
        self._scale_factor_in_tolerance: bool | None = None
        # PROBECALTS read just before this phase wrote PROBECALSTRT. None until
        # then, and after a session resumed past start_characterization.
        self._prestart_timestamp: datetime | None = None
        # PROBECALTS when read_results ran, which identifies the run the
        # operator reviewed. push_results refuses if PROBECALTS has changed,
        # since that means another run started.
        self._reviewed_run_timestamp: datetime | None = None

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.CAVITY_CHAR

    def validate_prerequisites(self) -> tuple[bool, str]:
        cavity = self.context.parameters.get("cavity")
        if cavity is None:
            return False, "No cavity specified in context"
        if not hasattr(cavity, "ssa") or cavity.ssa is None:
            return False, "Cavity has no SSA object"
        self.cavity = cavity
        return True, "Prerequisites validated"

    def get_phase_steps(self) -> list[str]:
        return [
            "verify_initial_state",
            "set_drive_level",
            "start_characterization",
            "wait_for_completion",
            "read_results",
            "push_results",
            "record_results",
        ]

    def execute_step(self, step_name: str) -> PhaseStepResult:
        if self.cavity is None:
            raise PhaseExecutionError(
                "Cavity not set — validate_prerequisites must be called first"
            )

        steps = {
            "verify_initial_state": self._verify_initial_state,
            "set_drive_level": self._set_drive_level,
            "start_characterization": self._start_characterization,
            "wait_for_completion": self._wait_for_completion,
            "read_results": self._read_results,
            "push_results": self._push_results,
            "record_results": self._record_results,
        }
        if step_name not in steps:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Unknown step: {step_name}",
            )
        return steps[step_name]()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _verify_initial_state(self) -> PhaseStepResult:
        """Check the cavity is ready, and warn about stale inputs."""
        if self.context.dry_run:
            # HW_MODE and the stepper's motor_moving are PV reads, so skip
            # them; _stale_prerequisites reads the record only, and a
            # rehearsal is exactly when its warning is worth seeing.
            stale = self._stale_prerequisites()
            message = "Dry run: cavity state check simulated"
            if stale:
                message += f" — note: {', '.join(stale)}"
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message=message,
                data={"dry_run": True},
            )
        try:
            if not self.cavity.is_online:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message="Cavity is not online — cannot characterize",
                )
            if self.cavity.stepper_tuner.motor_moving:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=(
                        "Stepper motor is moving — wait for it to stop before "
                        "characterizing"
                    ),
                )
            # Read-only checks. Cavity.characterize() makes neither, but the
            # phase sets drive and starts PROBECALSTRT next, so refuse here
            # rather than characterize against an SSA that is off or busy.
            if not self.cavity.ssa.is_on:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message="SSA is not on — cannot characterize",
                )
            if self.cavity.ssa.calibration_running:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=(
                        "SSA calibration is running — wait for it to finish "
                        "before characterizing"
                    ),
                )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read cavity state: {exc}",
                retry_delay_seconds=3.0,
            )

        stale = self._stale_prerequisites()
        message = "Cavity ready for characterization"
        if stale:
            # A warning, not a failure: the workflow already guarantees these
            # phases ran, and re-running them is the operator's call rather than
            # something to trigger from here.
            message += f" — note: {', '.join(stale)}"

        return PhaseStepResult(result=PhaseResult.SUCCESS, message=message)

    def _stale_prerequisites(self) -> list[str]:
        """Names of upstream results older than the staleness window.

        Best practice is to characterize a cavity whose SSA was recently
        calibrated and which was recently tuned to resonance. Both results carry
        a timestamp on the record, so this is a record read rather than a reason
        to re-drive hardware.
        """
        record = getattr(self.context, "record", None)
        if record is None:
            return []

        cutoff = datetime.now() - timedelta(
            hours=self.limits.prerequisite_staleness_hours
        )
        stale = []
        for attr, label in (
            ("ssa_char", "SSA calibration"),
            ("frequency_tuning", "frequency tuning"),
        ):
            data = getattr(record, attr, None)
            timestamp = getattr(data, "timestamp", None) if data else None
            if timestamp is not None and timestamp < cutoff:
                age_hours = (datetime.now() - timestamp).total_seconds() / 3600
                stale.append(f"{label} is {age_hours:.0f} h old")
        return stale

    def _set_drive_level(self) -> PhaseStepResult:
        """Clamp the drive level for characterization.

        Mirrors what Cavity.characterize() does before starting, but takes the
        value from the phase parameters so the operator can override it.
        """
        requested = self.context.parameters.get(
            "drive_level", self.limits.default_drive_level
        )
        try:
            drive = float(requested)
        except (TypeError, ValueError):
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Drive level {requested!r} is not a number",
            )

        if not 0 < drive <= self.limits.max_drive_level:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"Drive level {drive:.1f} is outside the allowed range "
                    f"(0, {self.limits.max_drive_level:.0f}]"
                ),
            )

        # Validated above, so a dry run still catches a bad parameter. Below
        # this line reset_interlocks() writes INTLK_RESET_ALL and drive_level
        # writes SEL_ASET, so a rehearsal stops here.
        if self.context.dry_run:
            self._drive_level = drive
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message=f"Dry run: drive level {drive:.1f} not written",
                data={"drive_level": drive, "dry_run": True},
            )

        try:
            self.cavity.reset_interlocks()
            self.cavity.drive_level = drive
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not set drive level: {exc}",
                retry_delay_seconds=3.0,
            )

        self._drive_level = drive
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Drive level set to {drive:.1f}",
            data={"drive_level": drive},
        )

    def _start_characterization(self) -> PhaseStepResult:
        """Kick off the probe calibration / loaded-Q measurement."""
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: characterization start simulated",
                data={"dry_run": True},
            )
        # The last result's timestamp, so the wait step can tell this run's
        # result from the previous one. Read before the start PV is written.
        try:
            prestart_timestamp = self.cavity.characterization_timestamp
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read PROBECALTS before starting: {exc}",
                retry_delay_seconds=3.0,
            )
        try:
            self.cavity.start_characterization()
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not start characterization: {exc}",
                retry_delay_seconds=3.0,
            )
        # Always a fresh run. Cavity.characterize() reuses a COMPLETE result
        # under 60 s old instead of starting one; this phase does not, because
        # the record should hold a measurement this phase started.
        #
        # A new run invalidates the last one's numbers. Clear them now so a
        # read that fails later cannot leave this run's record carrying the
        # previous run's probe Q (or loaded Q). Saving never overwrites a
        # stored value with None (_store_phase_fields, finalize_phase), so a
        # stale value would otherwise stay. A session
        # resumed past this step does not come back through here, so its
        # values survive.
        self._clear_measured_fields()
        self._prestart_timestamp = prestart_timestamp

        # The status PV does not go busy instantly, and the start put does not
        # wait for it. This sleep makes it less likely the wait step reads the
        # previous run's COMPLETE; the PROBECALTS check after the wait is what
        # rejects it if it does.
        time.sleep(self.limits.status_settle_delay)
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Characterization started",
        )

    def _wait_for_completion(self) -> PhaseStepResult:
        """Wait for the characterization via Cavity.wait_for_characterization().

        The same wait auto setup runs through Cavity.characterize(). It polls
        PROBECALSTS until it stops reading RUNNING (2), then raises
        CavityCharacterizationError on CRASH (0), on a timeout, or on a
        PROBECALTS older than 300 s (a COMPLETE (1) left over from an earlier
        run). It calls check_abort() each poll, which on a plain Cavity reads
        abort_flag: on abort it calls turn_off() and raises CavityAbortError.

        PhaseBase.run() only checks the commissioning abort between steps, so
        an abort during this wait has to reach the cavity. The controller that
        runs this phase must call cavity.request_abort() alongside
        context.request_abort(), and clear cavity.abort_flag before starting,
        as FrequencyTuningController does for the stepper.

        An abort returns FAILED rather than raising, so PhaseBase does not
        retry a step the operator asked to stop.
        """
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: characterization completion simulated",
                data={"dry_run": True},
            )

        try:
            self.cavity.wait_for_characterization(
                timeout=self.limits.characterization_timeout_seconds,
                poll_interval=self.limits.status_poll_interval,
            )
            result_timestamp = self.cavity.characterization_timestamp
        except CavityAbortError as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Aborted while waiting for characterization: {exc}",
            )
        except CavityCharacterizationError as exc:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"{exc} — check the cavity's PROBECALSTS, PROBECALTS and "
                    "the RF interlocks"
                ),
            )
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read characterization status: {exc}",
                retry_delay_seconds=3.0,
            )

        # wait_for_characterization() accepts any COMPLETE under 300 s old, so
        # a run that finished a minute before this one started would pass it.
        # Require PROBECALTS to be later than the value read before the start.
        # A session resumed past start_characterization has no pre-start value
        # and gets only the 300 s check.
        #
        # PROBECALTS is stamped when a run starts, not when it completes.
        # ACCL:L0B:0110:PROBECALTS read 2025-11-27-12:35:05 on 2026-10-14; the
        # archiver has that cavity's PROBECALSTS going to RUNNING at 12:35:05
        # and to COMPLETE at 12:35:25, its last run. PROBECALTS itself is not
        # archived, so this is one cavity's run.
        if (
            self._prestart_timestamp is not None
            and result_timestamp <= self._prestart_timestamp
        ):
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"PROBECALTS is still {result_timestamp.isoformat()}, the "
                    "result from before this run started — the status settled "
                    "without a new characterization"
                ),
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Characterization complete",
        )

    def _read_results(self) -> PhaseStepResult:
        """Read the measured values and flag both tolerances. Pushes nothing.

        Separating read from push is the point of this phase: the operator sees
        loaded Q, scale factor and probe Q before any of them reach the cavity.
        """
        if self.context.dry_run:
            # Nothing to simulate: there is no measurement to read, and
            # calculate_probe_q() below processes QPROBE_CALC1.PROC, which is
            # a write. Store nothing rather than put invented numbers on the
            # record.
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: result read simulated, nothing stored",
                data={"dry_run": True},
            )

        try:
            self._reviewed_run_timestamp = (
                self.cavity.characterization_timestamp
            )
            self._loaded_q = float(self.cavity.measured_loaded_q)
            self._scale_factor = float(self.cavity.measured_scale_factor)
            # Whether loaded Q and scale factor are in tolerance: the same two
            # checks finish_characterization() makes before pushing.
            self._loaded_q_in_tolerance = bool(
                self.cavity.measured_loaded_q_in_tolerance
            )
            self._scale_factor_in_tolerance = bool(
                self.cavity.measured_scale_factor_in_tolerance
            )
            # QPROBE_CALC1.PROC derives probe Q from the measurement just taken,
            # so it has to be triggered before the value can be read back.
            self.cavity.calculate_probe_q()
            time.sleep(self.limits.status_settle_delay)
            self._probe_q = self._read_probe_q()
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not read characterization results: {exc}",
                retry_delay_seconds=3.0,
            )

        self._store_phase_fields(
            loaded_q=self._loaded_q,
            scale_factor=self._scale_factor,
            probe_q=self._probe_q,
            loaded_q_in_tolerance=self._loaded_q_in_tolerance,
            scale_factor_in_tolerance=self._scale_factor_in_tolerance,
            # When these values were read. finalize_phase() leaves it alone,
            # so a session resumed after this step keeps the real read time.
            timestamp=datetime.now(),
        )

        summary = (
            f"Loaded Q {self._loaded_q:.3e}, scale factor "
            f"{self._scale_factor:.1f}"
        )
        if self._probe_q is not None:
            summary += f", probe Q {self._probe_q:.3e}"

        # Out of tolerance is not a step failure: the measurement succeeded
        # and the operator needs to see it. The record carries both flags.
        outside = []
        if not self._loaded_q_in_tolerance:
            outside.append(
                "loaded Q is OUTSIDE the expected range "
                f"[{self.cavity.loaded_q_lower_limit:.2e}, "
                f"{self.cavity.loaded_q_upper_limit:.2e}]"
            )
        if not self._scale_factor_in_tolerance:
            outside.append(
                "scale factor is OUTSIDE the expected range "
                f"[{self.cavity.scale_factor_lower_limit:.1f}, "
                f"{self.cavity.scale_factor_upper_limit:.1f}]"
            )
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"{summary} — "
            + ("; ".join(outside) if outside else "both in tolerance"),
            data=self._result_data(),
        )

    def _read_probe_q(self) -> float:
        """Read QPROBE_CALC2, the probe Q that QPROBE_CALC1.PROC calculates.

        PV names from Sebastian Aderhold on #372. No tolerance check: the
        Cavity model has no probe-Q limits.
        """
        return float(self.cavity.measured_probe_q)

    def _push_results(self) -> PhaseStepResult:
        """Push the reviewed values to the cavity, if the operator confirmed.

        PhaseBase.run() goes straight from read_results to here with no pause,
        so the gate has to be in this step: it refuses unless
        context.parameters["confirmed_loaded_q"] equals the loaded Q that
        read_results just stored. A confirmation of an older measurement
        does not match and is refused too. The UI sets the parameter when the
        operator confirms the values on screen.

        The push PVs process whatever the IOC's result PVs hold now, not the
        numbers this phase read. So just before pushing it re-reads PROBECALTS,
        QLOADED_NEW, CAV:CAL_SCALEB_NEW and QPROBE_CALC2, and refuses if any
        differs from what read_results stored: a run started during the review
        would otherwise push values the operator never saw.

        On success it processes PUSH_QLOADED.PROC (push_loaded_q),
        PUSH_CAV_SCALE.PROC (push_scale_factor) and PUSH_QPROBECALC.PROC
        (push_probe_q), in that order, whether or not either value is in
        tolerance. Cavity.finish_characterization() does not push probe Q;
        this phase does because Ryan's outline asks for it.

        This differs from auto setup on purpose. Cavity.finish_characterization()
        refuses to push an out-of-tolerance loaded Q or scale factor. In
        commissioning the operator has the values on screen with the flags,
        and confirms them explicitly, so pushing an out-of-tolerance value is
        their call. The record keeps both flags, and passed is False.

        No SAVE_QLOADED.PROC / SAVE_CAV_SCALE.PROC afterwards, and none is
        needed. Push writes the value to the register the hardware uses. Save
        only keeps a copy for a human, and the hardware does not read it
        (Lisa Zacarias, #285, 2026-10-02).
        """
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: push simulated",
                data={"dry_run": True},
            )
        if self._loaded_q is None:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message="Nothing measured yet — run the characterization first",
            )
        if self.context.parameters.get("confirmed_loaded_q") != self._loaded_q:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    "Push not confirmed for this measurement — review loaded "
                    f"Q {self._loaded_q:.3e} and confirm before pushing"
                ),
            )

        try:
            changed = self._results_changed_since_read()
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not re-read results before pushing: {exc}",
                retry_delay_seconds=3.0,
            )
        if changed:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=(
                    f"{', '.join(changed)} changed since the values were "
                    "reviewed — nothing pushed. Rerun the characterization."
                ),
            )

        try:
            self.cavity.push_loaded_q()
            self.cavity.push_scale_factor()
            self.cavity.push_probe_q()
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not push characterization results: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Loaded Q, cavity scale factor and probe Q pushed",
            data=self._result_data(),
        )

    def _results_changed_since_read(self) -> list[str]:
        """PV names whose current value differs from what read_results stored."""
        current = {
            "PROBECALTS": (
                self.cavity.characterization_timestamp,
                self._reviewed_run_timestamp,
            ),
            "QLOADED_NEW": (
                float(self.cavity.measured_loaded_q),
                self._loaded_q,
            ),
            "CAV:CAL_SCALEB_NEW": (
                float(self.cavity.measured_scale_factor),
                self._scale_factor,
            ),
            "QPROBE_CALC2": (self._read_probe_q(), self._probe_q),
        }
        return [name for name, (now, read) in current.items() if now != read]

    def _record_results(self) -> PhaseStepResult:
        """Placeholder step — population happens in finalize_phase()."""
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Results collected; ready to finalize",
        )

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def _result_data(self) -> dict:
        return {
            "loaded_q": self._loaded_q,
            "scale_factor": self._scale_factor,
            "probe_q": self._probe_q,
            "loaded_q_in_tolerance": self._loaded_q_in_tolerance,
            "scale_factor_in_tolerance": self._scale_factor_in_tolerance,
            "drive_level": self._drive_level,
        }

    def _clear_measured_fields(self) -> None:
        """Blank this phase's measured values, in memory and on the record."""
        self._loaded_q = None
        self._scale_factor = None
        self._probe_q = None
        self._loaded_q_in_tolerance = None
        self._scale_factor_in_tolerance = None
        record = getattr(self.context, "record", None)
        if record is None or record.cavity_char is None:
            return
        record.cavity_char.loaded_q = None
        record.cavity_char.scale_factor = None
        record.cavity_char.probe_q = None
        record.cavity_char.loaded_q_in_tolerance = None
        record.cavity_char.scale_factor_in_tolerance = None

    def _store_phase_fields(self, **fields) -> None:
        """Merge step results onto the record as each step produces them.

        Same pattern as the frequency tuning phase, and for the same reason:
        record.phase_history is in-memory only, so a phase that reads its own
        results back out of checkpoints loses them across a restart. Only the
        named fields are touched, and None is skipped, so a later step cannot
        erase an earlier one. Persisting is the session's job.
        """
        record = getattr(self.context, "record", None)
        if record is None:
            return
        data = record.cavity_char or CavityCharacterization()
        for name, value in fields.items():
            if value is not None:
                setattr(data, name, value)
        record.cavity_char = data

    def finalize_phase(self) -> None:
        """Write the characterization result onto the record."""
        record = self.context.record
        data = record.cavity_char or CavityCharacterization()
        data.loaded_q = (
            self._loaded_q if self._loaded_q is not None else data.loaded_q
        )
        data.scale_factor = (
            self._scale_factor
            if self._scale_factor is not None
            else data.scale_factor
        )
        data.probe_q = (
            self._probe_q if self._probe_q is not None else data.probe_q
        )
        record.cavity_char = data
