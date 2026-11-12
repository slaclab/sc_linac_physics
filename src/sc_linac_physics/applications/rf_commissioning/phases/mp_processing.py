"""MP processing phase.

Raises the cavity amplitude in SELA and processes each quench on the way up.
The ramp and the processing are one phase. The spec is the 2026-10-27 design
meeting (Lisa Zacarias and Sebastian Aderhold).

What it does to the machine, in order:

1. setup_rf: Cavity.setup_rf(start_amplitude_mv, ...). That turns RF off,
   moves to resonance, turns on in SELA and walks ADES up to the start
   amplitude. It re-runs the SSA calibration and the characterization only
   when the last one is stale, as the piezo with RF phase does (see
   _setup_rf).
2. process: writes ADES (MV) up by step_mv every step_seconds, up to
   ADES_MAX. When the quench latch is set, it records the quench, waits
   quench_settle_seconds, writes the interlock reset (Cavity.
   reset_interlocks) and holds the same ADES. It keeps doing that until
   stable_seconds pass with no quench, then goes on walking up. Once ADES
   is at ADES_MAX it needs one stable_seconds hold with no quench to finish.

It resets every quench, real or not: resetting after a quench is the
processing. quench_processing's reset_quench() refuses real quenches and is
not used. No retry cap: the operator aborts. Field emission, hard quench
and pause-and-inspect are later PRs.

The steps that wait call cavity.check_abort(), which on abort turns RF off
and raises CavityAbortError, as in the piezo with RF phase. The phase leaves
RF on in SELA at ADES_MAX when it completes.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    MPProcessingData,
)
from sc_linac_physics.applications.rf_commissioning.phases.cavity_setup import (
    RECENT_RESULT_SECONDS,
    LastSetupResult,
    last_characterization,
    last_ssa_calibration,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseExecutionError,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    CavityFaultError,
)


@dataclass
class MPProcessingLimits:
    """Configurable settings for MP processing. Amplitudes are ADES, in MV."""

    # CHECK: where should the ramp start? 5 MV is quench_processing's
    # default start_amp; the 2026-10-27 spec doesn't say.
    start_amplitude_mv: float = 5.0
    # 0.2 MV every 30 s, kept from quench_processing (2026-10-27 spec).
    step_mv: float = 0.2
    step_seconds: float = 30.0
    # An amplitude counts as stable after this long with no quench. 5 min
    # per the 2026-10-27 spec (quench_processing used 30 min).
    stable_seconds: float = 300.0
    # Wait between seeing the quench and writing the reset.
    # quench_cavity.wait_for_quench waits 1 s "just in case".
    quench_settle_seconds: float = 1.0
    poll_interval: float = 1.0
    # setup_rf keeps an SSA calibration or characterization younger than
    # this. Same one hour as the piezo with RF phase.
    recent_result_seconds: float = RECENT_RESULT_SECONDS


class MPProcessingPhase(PhaseBase):
    """MP processing: walk ADES up to ADES_MAX, resetting every quench."""

    def __init__(
        self, context: PhaseContext, limits: MPProcessingLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or MPProcessingLimits()
        self.cavity = None

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.MP_PROCESSING

    def validate_prerequisites(self) -> tuple[bool, str]:
        cavity = self.context.parameters.get("cavity")
        if cavity is None:
            return False, "No cavity specified in context"
        self.cavity = cavity
        return True, "Prerequisites validated"

    def _steps(self) -> dict[str, Callable[[], PhaseStepResult]]:
        return {
            "verify_initial_state": self._verify_initial_state,
            "setup_rf": self._setup_rf,
            "process": self._process,
            "record_results": self._record_results,
        }

    def get_phase_steps(self) -> list[str]:
        return list(self._steps())

    def execute_step(self, step_name: str) -> PhaseStepResult:
        if self.cavity is None:
            raise PhaseExecutionError(
                "Cavity not set — validate_prerequisites must be called first"
            )
        step = self._steps().get(step_name)
        if step is None:
            return self._failed(f"Unknown step: {step_name}")
        return step()

    def finalize_phase(self) -> None:
        """Writes no PVs. The steps put their results on the record."""

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _verify_initial_state(self) -> PhaseStepResult:
        """Check the cavity is online, and start a fresh result.

        A rerun replaces the last run's quenches and max amplitude. Reads
        PVs only. A dry run clears nothing.

        Its data says whether the SSA calibration (CALTS, CALSTAT) and the
        characterization (PROBECALTS, PROBECALSTS) are recent enough for
        setup_rf to keep. The controller asks the operator Rerun or Skip for
        each one that is not, as for piezo with RF.
        """
        if self.context.dry_run:
            return self._dry_run_result("cavity state check")
        try:
            if not self.cavity.is_online:
                return self._failed("Cavity is not online — cannot process")
            ssa_cal = last_ssa_calibration(self.cavity)
            char = last_characterization(self.cavity)
        except Exception as exc:
            return self._retry(f"Could not read cavity state: {exc}")
        max_age = self.limits.recent_result_seconds
        self.context.record.mp_processing = MPProcessingData()
        return self._success(
            "Cavity ready for MP processing",
            data={
                "ssa_calibration_time": ssa_cal.timestamp,
                "ssa_calibration_good": bool(ssa_cal.good),
                "ssa_calibration_recent": ssa_cal.is_recent(max_age),
                "characterization_time": char.timestamp,
                "characterization_complete": char.good,
                "characterization_recent": char.is_recent(max_age),
            },
        )

    def _setup_rf(self) -> PhaseStepResult:
        """Turn on in SELA at start_amplitude_mv with Cavity.setup_rf.

        Cavity.setup_rf caps the amplitude at ADES_MAX. It re-runs the SSA
        calibration when CALTS is older than recent_result_seconds (1 h) or
        CALSTAT is not Good. It re-runs the characterization (which pushes
        loaded Q and scale factor) when PROBECALTS is older than 1 h or
        PROBECALSTS is not Complete. Otherwise it keeps what is on the
        machine. Same rule as the piezo with RF phase.

        The operator can keep a stale result: context.parameters
        ["rerun_ssa_calibration"] or ["rerun_characterization"] set to
        False. A missing answer means re-run. True does not re-run a recent
        result. What was kept or re-run goes in record.mp_processing.notes.

        A failed read of the timestamps retries, since nothing has been
        written yet. Any error after that fails the step without a retry,
        since a retry could repeat an SSA calibration and a
        characterization.
        """
        if self.context.dry_run:
            return self._dry_run_result("RF setup")
        start = self.limits.start_amplitude_mv
        params = self.context.parameters
        try:
            ssa_cal = last_ssa_calibration(self.cavity)
            char = last_characterization(self.cavity)
        except Exception as exc:
            return self._retry(f"Could not read the last calibration: {exc}")
        max_age = self.limits.recent_result_seconds
        ssa_stale = not ssa_cal.is_recent(max_age)
        char_stale = not char.is_recent(max_age)
        calibrate_ssa = ssa_stale and bool(
            params.get("rerun_ssa_calibration", True)
        )
        characterize = char_stale and bool(
            params.get("rerun_characterization", True)
        )
        try:
            self.cavity.setup_rf(
                start, calibrate_ssa=calibrate_ssa, characterize=characterize
            )
        except CavityAbortError as exc:
            return self._failed(f"Aborted during RF setup — RF is off: {exc}")
        except Exception as exc:
            return self._failed(f"RF setup failed: {exc}")
        ssa_note = (
            "re-ran SSA calibration"
            if calibrate_ssa
            else self._kept_note("SSA calibration", ssa_stale, "CALTS", ssa_cal)
        )
        char_note = (
            "re-ran characterization (pushed, not reviewed)"
            if characterize
            else self._kept_note(
                "characterization", char_stale, "PROBECALTS", char
            )
        )
        note = f"setup_rf() {ssa_note} and {char_note}"
        self._append_note(note)
        return self._success(
            f"RF on in SELA at {self.cavity.ades:.2f} MV. {note}",
            data={
                "calibrated_ssa": calibrate_ssa,
                "characterized": characterize,
            },
        )

    def _process(self) -> PhaseStepResult:
        """Walk ADES to ADES_MAX, processing each quench until stable."""
        if self.context.dry_run:
            return self._dry_run_result("MP processing")
        if self.context.record.mp_processing is None:
            self.context.record.mp_processing = MPProcessingData()
        try:
            amplitude = self._walk_to_ades_max()
        except CavityAbortError as exc:
            return self._failed(
                f"Aborted during MP processing — RF is off: {exc}"
            )
        except CavityFaultError as exc:
            # An abort requested while reset_interlocks was retrying has
            # not turned RF off yet. check_abort does that, and raises.
            try:
                self.cavity.check_abort()
            except CavityAbortError as abort:
                return self._failed(
                    f"Aborted during MP processing — RF is off: {abort}"
                )
            return self._failed(f"Interlock reset failed: {exc}")
        data = self.context.record.mp_processing
        return self._success(
            f"Stable at {amplitude:.2f} MV for "
            f"{self.limits.stable_seconds:.0f} s; "
            f"{data.quench_count} quench(es)",
            data={
                "max_amplitude_reached": amplitude,
                "quench_count": data.quench_count,
            },
        )

    def _record_results(self) -> PhaseStepResult:
        """No PV access; _process put the results on the record."""
        return self._success("Results collected; ready to finalize")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _walk_to_ades_max(self) -> float:
        """The loop in _process. Returns the final ADES, in MV.

        Raises CavityAbortError on abort, CavityFaultError if a reset fails.
        """
        end = float(self.cavity.ades_max)
        amplitude = float(self.cavity.ades)
        self._note_amplitude(amplitude)
        while True:
            at_end = amplitude >= end
            hold = (
                self.limits.stable_seconds
                if at_end
                else self.limits.step_seconds
            )
            if self._quenched_within(hold):
                self._process_until_stable(amplitude)
            if at_end:
                return amplitude
            # Round the step, then cap. Rounding after the cap could land
            # just under an ADES_MAX like 16.600000381 every time, and the
            # walk would never reach the final hold.
            amplitude = min(round(amplitude + self.limits.step_mv, 3), end)
            # PV write: ADES, in MV.
            self.cavity.ades = amplitude
            self._note_amplitude(amplitude)

    def _process_until_stable(self, amplitude: float) -> None:
        """Record and reset each quench until stable_seconds pass without one.

        PV write: the interlock reset (Cavity.reset_interlocks, which raises
        CavityFaultError if the cavity stays faulted). ADES is not changed.
        CHECK: after the reset, does the LLRF bring the field back to the
        same ADES in SELA on its own? quench_processing assumed so.

        Abort is checked before the reset is written. Cavity.reset_interlocks
        itself does not check abort: if the cavity stays faulted it retries
        up to INTERLOCK_RESET_ATTEMPTS times, waiting 3, 5, 7... s, about
        48 s in all, before raising CavityFaultError.
        """
        while True:
            self.context.record.mp_processing.add_quench(amplitude=amplitude)
            time.sleep(self.limits.quench_settle_seconds)
            self.cavity.check_abort()
            self.cavity.reset_interlocks()
            if not self._quenched_within(self.limits.stable_seconds):
                return

    def _quenched_within(self, seconds: float) -> bool:
        """Poll the quench latch for up to seconds. True on a quench.

        Same timing as PiezoWithRFPhase._poll_until: elapsed time on
        time.monotonic(), each sleep capped at what remains.
        """
        deadline = time.monotonic() + seconds
        while True:
            self.cavity.check_abort()
            if self.cavity.is_quenched:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(self.limits.poll_interval, remaining))

    def _note_amplitude(self, amplitude: float) -> None:
        """Keep the highest ADES written on the record."""
        data = self.context.record.mp_processing
        if (
            data.max_amplitude_reached is None
            or amplitude > data.max_amplitude_reached
        ):
            data.max_amplitude_reached = amplitude

    @staticmethod
    def _kept_note(
        what: str, stale: bool, pv: str, last: LastSetupResult
    ) -> str:
        """setup_rf's note for a result it did not re-run.

        Same wording as PiezoWithRFPhase._kept_note.
        """
        if stale:
            return (
                f"kept a stale {what} ({pv} {last.timestamp:%Y-%m-%d %H:%M}; "
                "operator chose Skip)"
            )
        return f"kept the {what} from the last hour"

    def _append_note(self, note: str) -> None:
        """Append a line to record.mp_processing.notes."""
        record = self.context.record
        data = record.mp_processing or MPProcessingData()
        data.notes = f"{data.notes}\n{note}" if data.notes else note
        record.mp_processing = data

    def _dry_run_result(self, what: str) -> PhaseStepResult:
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Dry run: {what} simulated",
            data={"dry_run": True},
        )

    @staticmethod
    def _success(message: str, data: dict | None = None) -> PhaseStepResult:
        return PhaseStepResult(
            result=PhaseResult.SUCCESS, message=message, data=data
        )

    @staticmethod
    def _failed(message: str) -> PhaseStepResult:
        return PhaseStepResult(result=PhaseResult.FAILED, message=message)

    @staticmethod
    def _retry(message: str) -> PhaseStepResult:
        return PhaseStepResult(
            result=PhaseResult.RETRY,
            message=message,
            retry_delay_seconds=3.0,
        )
