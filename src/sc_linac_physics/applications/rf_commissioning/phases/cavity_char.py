"""
Cavity Characterization Phase

Calibrates the cavity's RF probe and measures the loaded Q of the power coupler,
then lets the operator review the results before they are pushed to the cavity.

Almost none of the measurement lives here. `Cavity` already implements the whole
sequence — `start_characterization()`, the `characterization_running` /
`characterization_crashed` status predicates, `calculate_probe_q()`,
`push_loaded_q()`, `push_scale_factor()`, and the per-cavity-class tolerance
check `measured_loaded_q_in_tolerance`. Auto setup's `request_characterization()`
is a twelve-line wrapper over the same code. This phase is deliberately a
similarly thin wrapper: if a step body here grows past a few lines of
orchestration, something is being duplicated.

The one deliberate divergence from `Cavity.characterize()`: that method bundles
start, wait and push into a single blocking call, which suits unattended setup.
Commissioning needs an operator to see the loaded Q, scale factor and probe Q
*before* anything is written to the cavity, so this phase drives the same code at
a lower level and stops between measuring and pushing.

Known gap: probe Q. QPROBE_CALC1.PROC triggers the calculation and is the only
probe-Q PV that exists — there is no value record to read the result from and no
push PV for it. Ryan's outline asks for probe Q to be displayed and pushed, so
those PVs presumably exist on the machine and are missing from the model. Until
they are added, probe_q stays None on the record rather than being invented.

Sequence:
  1. verify_initial_state    – stepper idle, cavity online, RF/SSA ready; warn if
                               SSA calibration or tuning are stale
  2. set_drive_level         – clamp drive for characterization (operator may
                               override the default)
  3. start_characterization  – kick off PROBECALSTRT
  4. wait_for_completion     – poll the status until it settles or crashes
  5. read_results            – read loaded Q and scale factor, trigger the
                               probe-Q calculation, flag out-of-tolerance loaded
                               Q. Nothing is pushed.
  6. push_results            – operator-confirmed: push loaded Q and scale
                               factor to the cavity
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
        self._loaded_q_in_tolerance: bool | None = None

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
        # The status PV does not go busy instantly; without this the wait step
        # can see the previous run's COMPLETE and return immediately.
        time.sleep(self.limits.status_settle_delay)
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Characterization started",
        )

    def _wait_for_completion(self) -> PhaseStepResult:
        """Poll until the characterization settles, crashes, or times out."""
        if self.context.dry_run:
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Dry run: characterization completion simulated",
                data={"dry_run": True},
            )

        deadline = time.monotonic() + (
            self.limits.characterization_timeout_seconds
        )
        while time.monotonic() < deadline:
            self.cavity.check_abort()
            try:
                if self.cavity.characterization_crashed:
                    return PhaseStepResult(
                        result=PhaseResult.FAILED,
                        message=(
                            "Characterization crashed — check the cavity's "
                            "PROBECALSTS and the RF interlocks"
                        ),
                    )
                if not self.cavity.characterization_running:
                    return PhaseStepResult(
                        result=PhaseResult.SUCCESS,
                        message="Characterization complete",
                    )
            except Exception as exc:
                return PhaseStepResult(
                    result=PhaseResult.RETRY,
                    message=f"Could not read characterization status: {exc}",
                    retry_delay_seconds=3.0,
                )
            time.sleep(self.limits.status_poll_interval)

        return PhaseStepResult(
            result=PhaseResult.FAILED,
            message=(
                "Characterization did not finish within "
                f"{self.limits.characterization_timeout_seconds:.0f} s"
            ),
        )

    def _read_results(self) -> PhaseStepResult:
        """Read the measured values and flag loaded Q. Pushes nothing.

        Separating read from push is the point of this phase: the operator sees
        loaded Q, scale factor and probe Q before any of them reach the cavity.
        """
        try:
            self._loaded_q = float(self.cavity.measured_loaded_q)
            self._scale_factor = float(self.cavity.measured_scale_factor)
            self._loaded_q_in_tolerance = bool(
                self.cavity.measured_loaded_q_in_tolerance
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
        )

        summary = (
            f"Loaded Q {self._loaded_q:.3e}, scale factor "
            f"{self._scale_factor:.1f}"
        )
        if self._probe_q is not None:
            summary += f", probe Q {self._probe_q:.3e}"

        if not self._loaded_q_in_tolerance:
            # Not a step failure: the measurement succeeded and the operator
            # needs to see it. Whether to push it is their decision, and the
            # record carries the flag either way.
            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message=(
                    f"{summary} — loaded Q is OUTSIDE the expected range "
                    f"[{self.cavity.loaded_q_lower_limit:.2e}, "
                    f"{self.cavity.loaded_q_upper_limit:.2e}]"
                ),
                data=self._result_data(),
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"{summary} — loaded Q in tolerance",
            data=self._result_data(),
        )

    def _read_probe_q(self) -> float | None:
        """Always None today: there is no probe-Q readback PV.

        `calculate_probe_q()` processes QPROBE_CALC1.PROC, which triggers the
        calculation, and that is the only probe-Q PV in the codebase — there is
        no value record to read the result from, and no PUSH_QPROBE to push it
        with (only PUSH_QLOADED and PUSH_CAV_SCALE exist).

        Ryan's outline asks for probe Q to be displayed and pushed, so the PV
        names are presumably known to the SRF group and simply absent from the
        hardware model. Returning None keeps the record honest until they are
        added: better an empty field than a fabricated number.
        """
        return None

    def _push_results(self) -> PhaseStepResult:
        """Push the reviewed values to the cavity.

        Reached only once the operator has confirmed, which is why this is its
        own step rather than part of reading. Cavity.finish_characterization()
        would push loaded Q and scale factor automatically based on tolerance;
        this phase keeps that decision with the operator.
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

        try:
            self.cavity.push_loaded_q()
            self.cavity.push_scale_factor()
        except Exception as exc:
            return PhaseStepResult(
                result=PhaseResult.RETRY,
                message=f"Could not push characterization results: {exc}",
                retry_delay_seconds=3.0,
            )

        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Loaded Q and cavity scale factor pushed",
            data=self._result_data(),
        )

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
            "drive_level": self._drive_level,
        }

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
        data.timestamp = datetime.now()
        record.cavity_char = data
