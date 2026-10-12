"""
Cavity Characterization Phase

Calibrates the cavity's RF probe and measures the loaded Q of the power coupler.
This module has steps 1-4: check the cavity, set drive, start the run and wait
for it. Reading, pushing and recording the results (steps 5-7) come next, and
until then nothing constructs this phase.

Almost none of the measurement lives here. `Cavity` already implements the whole
sequence — `start_characterization()`, the `characterization_running` /
`characterization_crashed` status predicates, `calculate_probe_q()`,
`push_loaded_q()`, `push_scale_factor()`, `wait_for_characterization()`, and the
tolerance checks `measured_loaded_q_in_tolerance` and
`measured_scale_factor_in_tolerance`. Auto setup's `request_characterization()`
is a twelve-line wrapper over the same code. This phase is deliberately a
similarly thin wrapper: if a step body here grows past a few lines of
orchestration, something is being duplicated.

Deliberate divergence from `Cavity.characterize()`: it always starts a fresh
run (`_start_characterization`). `characterize()` reuses a COMPLETE result under
60 s old.

Sequence:
  1. verify_initial_state    – cavity online, stepper idle, SSA on and not
                               calibrating; warn if SSA calibration or tuning
                               are stale
  2. set_drive_level         – clamp drive for characterization (operator may
                               override the default)
  3. start_characterization  – kick off PROBECALSTRT; clear the previous
                               run's results from the record
  4. wait_for_completion     – poll PROBECALSTS until it settles, then reject a
                               crash or a PROBECALTS too old to be this run
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
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
    # There is no SSA power rating anywhere in the hardware model — no rated
    # power PV, and fwd_power_lower_limit is a calibration floor rather than a
    # rating — so the per-SSA default cannot be derived yet. Until that question
    # is answered the phase starts from the existing safe pulsed level and the
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
        # previous run's probe Q (or loaded Q). A session resumed past this
        # step does not come back through here, so its values survive.
        self._clear_measured_fields()

        # The status PV does not go busy instantly; without this the wait step
        # can see the previous run's COMPLETE and return immediately.
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

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Characterization complete",
        )

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def _clear_measured_fields(self) -> None:
        """Blank this phase's measured values, in memory and on the record."""
        self._loaded_q = None
        self._scale_factor = None
        self._probe_q = None
        record = getattr(self.context, "record", None)
        if record is None or record.cavity_char is None:
            return
        record.cavity_char.loaded_q = None
        record.cavity_char.scale_factor = None
        record.cavity_char.probe_q = None

    def finalize_phase(self) -> None:
        """Nothing to record yet: steps 5-7 read and store the results."""
