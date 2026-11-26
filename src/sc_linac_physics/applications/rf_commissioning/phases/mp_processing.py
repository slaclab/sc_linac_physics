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
   quench_hold_seconds pass with no quench, then goes on walking up. Once
   ADES is at ADES_MAX it needs one stable_seconds hold with no quench to
   finish.

It resets every quench, real or not: resetting after a quench is the
processing. quench_processing's reset_quench() refuses real quenches and is
not used. No retry cap: the operator aborts. Hard quench is a later PR.

Field-emission pause (2026-11-24 meeting): with a decarad chosen, each
latch poll also reads GAMMA_DOSE_RATE on its 10 heads. Radiation above
fe_pause_above (over background) with no quench just before, an INVALID
head, or a failed read pauses the walk the same way Pause does, RF on.
override_radiation() turns that off for the rest of the run. The check
does not run during setup_rf's walk to the start ADES.

Pause and inspect (2026-10-27 spec): request_pause() from the GUI thread
stops process at its next latch poll (within poll_interval). While paused
it writes nothing: no ADES and no interlock reset, so the operator has the
amplitude. Quenches while paused are not recorded. request_resume() goes on
from the ADES the operator left, read back from the PV, starting a fresh
step_seconds hold there. Resume is refused while the quench latch is set.
Each pause goes in notes, and the first quench after a resume is flagged
after_pause, since the time across a pause means nothing.

The steps that wait call cavity.check_abort(), which on abort turns RF off
and raises CavityAbortError, as in the piezo with RF phase. The phase leaves
RF on in SELA at ADES_MAX when it completes.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

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
from sc_linac_physics.utils.epics import EPICS_INVALID_VAL
from sc_linac_physics.utils.sc_linac.decarad import Decarad
from sc_linac_physics.utils.sc_linac.linac_utils import (
    DECARAD_BACKGROUND_READING_RAW,
    CavityAbortError,
    CavityFaultError,
)


@dataclass
class MPProcessingLimits:
    """Configurable settings for MP processing. Amplitudes are ADES, in MV."""

    # CHECK: start at 5 or 10 MV? 2026-11-24 leaned to 10, pending Ryan's
    # check that RF checks get enough signal on HE modules and a look at
    # partner lab FE onsets. 5 MV is quench_processing's start_amp.
    start_amplitude_mv: float = 5.0
    # 0.1 MV every 1 s (2026-11-24 meeting). The 2026-10-27 spec kept
    # quench_processing's 0.2 MV every 30 s, about 47 min from 5 to 21.8 MV.
    step_mv: float = 0.1
    step_seconds: float = 1.0
    # After a quench below ADES_MAX, hold the same ADES until this long
    # passes with no quench, then walk on. 30 s per the 2026-11-24 meeting
    # (was stable_seconds, 5 min).
    quench_hold_seconds: float = 30.0
    # At ADES_MAX, finish after this long with no quench. 5 min per the
    # 2026-10-27 spec (quench_processing used 30 min).
    # CHECK: does the final hold stay 5 min? 2026-11-24 only shortened the
    # hold after a quench.
    stable_seconds: float = 300.0
    # Wait between seeing the quench and writing the reset.
    # quench_cavity.wait_for_quench waits 1 s "just in case".
    quench_settle_seconds: float = 1.0
    poll_interval: float = 1.0
    # setup_rf keeps an SSA calibration or characterization younger than
    # this. Same one hour as the piezo with RF phase.
    recent_result_seconds: float = RECENT_RESULT_SECONDS
    # Field-emission pause (2026-11-24 meeting). Decarad 1 or 2, chosen on
    # the tab, or None for no radiation check. The check reads
    # GAMMA_DOSE_RATE on all 10 heads of that decarad, as quench_processing
    # does (Decarad.max_raw_dose), not the 10 s GAMMAAVE average.
    decarad: int | None = None
    # Pause when the highest head reads more than this above
    # DECARAD_BACKGROUND_READING_RAW (8) with no quench just before.
    # CHECK: default threshold. Ryan, 2026-11-24: "above ~8 instantaneous",
    # "10 or 20 might be enough"; his decarad look is due. Is "8" raw or
    # above background? quench_processing aborts at 2 above background.
    # CHECK: GAMMA_DOSE_RATE units, mR/h?
    fe_pause_above: float = 10.0
    # Radiation is ignored for this long after an interlock reset, since a
    # quench brings its own radiation (multipacting, not FE). 3 s is
    # quench_processing's DECARAD_SETTLE_TIME.
    radiation_settle_seconds: float = 3.0


class _Seen(Enum):
    """What a watch of the quench latch ended on."""

    QUIET = "quiet"  # the whole wait passed with no quench
    QUENCH = "quench"
    PAUSE = "pause"  # the operator pressed Pause


class MPProcessingPhase(PhaseBase):
    """MP processing: walk ADES up to ADES_MAX, resetting every quench."""

    def __init__(
        self, context: PhaseContext, limits: MPProcessingLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or MPProcessingLimits()
        self.cavity = None
        # Pause and Resume are separate requests from the GUI thread. Only
        # the worker moves between running and paused (_paused), so the tab
        # shows Paused only once the phase has stopped writing.
        self._pause_requested = threading.Event()
        self._resume_requested = threading.Event()
        self._paused = False
        # The next recorded quench is the first since a resume.
        self._after_pause = False
        # When the last pause ended. The tab counts "since last quench"
        # from here when it is later than the last quench.
        self.resumed_at: datetime | None = None
        # Built in _process from limits.decarad. Tests set a fake first.
        self.decarad = None
        # Why the walk paused itself; None for the operator's Pause.
        self._auto_pause_reason: str | None = None
        # Set from the GUI thread by override_radiation(): no radiation
        # pauses for the rest of this run.
        self._radiation_overridden = threading.Event()
        self._radiation_quiet_until = 0.0
        # Last radiation reading, for the tab: above background, or None.
        self.radiation: float | None = None

    # ------------------------------------------------------------------
    # Pause and resume, called from the GUI thread
    # ------------------------------------------------------------------

    def request_pause(self) -> None:
        """Stop the walk at the next latch poll. Writes no PVs."""
        self._pause_requested.set()

    def request_resume(self) -> None:
        """Go on from the operator's ADES. Refused while QUENCH_LTCH is set.

        Ignored until the phase is actually paused: a Resume while the
        pause is still pending would leave the walk on its old ADES.
        """
        if self._paused:
            self._resume_requested.set()

    def override_radiation(self, operator: str) -> None:
        """Stop radiation pauses for the rest of this run. Writes no PVs.

        For an operator watching the decarad by hand, since a Resume while
        radiation stays high would pause again at once (Ryan, 2026-11-24).
        Noted with the operator's name and time.
        CHECK: rest of the run, or until the operator turns the check back
        on? The meeting didn't say.
        """
        if self._radiation_overridden.is_set():
            return
        self._radiation_overridden.set()
        self._append_note(
            f"radiation pause overridden by {operator} at "
            f"{datetime.now():%H:%M:%S}"
        )

    @property
    def radiation_overridden(self) -> bool:
        return self._radiation_overridden.is_set()

    @property
    def pause_state(self) -> str:
        """ "running", "pausing", "paused" or "resuming".

        "pausing": Pause pressed, but the phase may still be writing, e.g.
        while Cavity.reset_interlocks retries. "resuming": Resume pressed,
        not yet accepted. Only "paused" means the phase writes nothing.
        """
        if self._paused:
            return "resuming" if self._resume_requested.is_set() else "paused"
        return "pausing" if self._pause_requested.is_set() else "running"

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
        """Check the cavity is free to set up, and start a fresh result.

        Fails if the cavity is offline, an SSA calibration is running or the
        stepper is moving.

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
            # setup_rf turns RF off and may calibrate or tune, so it must not
            # start under either. Same checks as PiezoWithRFPhase.
            if self.cavity.ssa.calibration_running:
                return self._failed(
                    "SSA calibration is running — wait for it to finish"
                )
            if self.cavity.stepper_tuner.motor_moving:
                return self._failed(
                    "Stepper motor is moving — wait for it to stop"
                )
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
        self._start_radiation_check()
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
            seen = self._watch(hold)
            if seen is _Seen.QUENCH:
                seen = self._process_until_stable(
                    amplitude,
                    hold_seconds=(
                        self.limits.stable_seconds
                        if at_end
                        else self.limits.quench_hold_seconds
                    ),
                )
            if seen is _Seen.PAUSE:
                # Start the hold over at the operator's ADES.
                amplitude = self._hold_while_paused(amplitude)
                continue
            if at_end:
                return amplitude
            # Round the step, then cap. Rounding after the cap could land
            # just under an ADES_MAX like 16.600000381 every time, and the
            # walk would never reach the final hold.
            amplitude = min(round(amplitude + self.limits.step_mv, 3), end)
            # PV write: ADES, in MV.
            self.cavity.ades = amplitude
            self._note_amplitude(amplitude)

    def _process_until_stable(
        self, amplitude: float, hold_seconds: float
    ) -> _Seen:
        """Record and reset each quench until hold_seconds pass without one.

        hold_seconds is quench_hold_seconds below ADES_MAX and
        stable_seconds at ADES_MAX. Returns QUIET, or PAUSE if the operator
        paused during the hold.

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
            self.context.record.mp_processing.add_quench(
                amplitude=amplitude, after_pause=self._after_pause
            )
            self._after_pause = False
            time.sleep(self.limits.quench_settle_seconds)
            self.cavity.check_abort()
            self.cavity.reset_interlocks()
            self._radiation_quiet_until = (
                time.monotonic() + self.limits.radiation_settle_seconds
            )
            # A Pause pressed during the reset goes first. Watching first
            # would let back-to-back quenches put it off indefinitely.
            if self._pause_requested.is_set():
                return _Seen.PAUSE
            seen = self._watch(hold_seconds)
            if seen is not _Seen.QUENCH:
                return seen

    def _hold_while_paused(self, amplitude: float) -> float:
        """Write nothing until the operator resumes. Returns ADES then, in MV.

        Reads the quench latch and ADES only. Abort still works:
        check_abort turns RF off and raises. A resume while QUENCH_LTCH is
        set is refused and the phase stays paused, so a quench the operator
        has not reset is not counted as the first quench after the pause.
        CHECK: should the program keep resetting quenches while paused?
        The 2026-10-27 spec gives the operator the amplitude; it doesn't
        say who resets.
        """
        self._paused = True
        reason = self._auto_pause_reason
        self._auto_pause_reason = None
        # Noted now, so an abort while paused still leaves the pause on the
        # record.
        what = f"auto-paused ({reason})" if reason else "paused"
        self._append_note(
            f"{what} {datetime.now():%H:%M:%S} at {amplitude:.2f} MV"
        )
        if reason:
            self.cavity.logger.warning(
                "MP processing paused itself at %.2f MV: %s. RF stays on. "
                "Check the radiation, then Resume, or press I'm watching "
                "to stop radiation pauses for this run.",
                amplitude,
                reason,
            )
        self.cavity.logger.info(
            "MP processing paused at %.2f MV. No ADES writes or interlock "
            "resets until Resume.",
            amplitude,
        )
        while True:
            self.cavity.check_abort()
            if self._resume_requested.is_set():
                self._resume_requested.clear()
                if not self.cavity.is_quenched:
                    break
                self.cavity.logger.warning(
                    "Resume refused: the quench latch is set. Reset the "
                    "interlocks, then press Resume."
                )
            time.sleep(self.limits.poll_interval)
        resumed = float(self.cavity.ades)
        self.resumed_at = datetime.now()
        self._after_pause = True
        self._note_amplitude(resumed)
        self._append_note(
            f"resumed {self.resumed_at:%H:%M:%S} at {resumed:.2f} MV"
        )
        self._pause_requested.clear()
        self._paused = False
        self.cavity.logger.info(
            "MP processing resumed at %.2f MV (ADES read back).", resumed
        )
        return resumed

    def _watch(self, seconds: float) -> _Seen:
        """Poll the quench latch for up to seconds.

        QUENCH if the latch is set, PAUSE if the operator paused, QUIET if
        neither happened in time. A quench is seen before a pause, so a
        quench latched as Pause is pressed is still recorded and reset.

        Same timing as PiezoWithRFPhase._poll_until: elapsed time on
        time.monotonic(), each sleep capped at what remains.
        """
        deadline = time.monotonic() + seconds
        while True:
            self.cavity.check_abort()
            if self.cavity.is_quenched:
                return _Seen.QUENCH
            if self._pause_requested.is_set():
                return _Seen.PAUSE
            reason = self._radiation_pause_reason()
            if reason is not None:
                self._auto_pause_reason = reason
                self._pause_requested.set()
                return _Seen.PAUSE
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return _Seen.QUIET
            time.sleep(min(self.limits.poll_interval, remaining))

    def _start_radiation_check(self) -> None:
        """Set up the decarad from limits.decarad, and note which one."""
        if self.decarad is None and self.limits.decarad is not None:
            self.decarad = Decarad(self.limits.decarad)
        data = self.context.record.mp_processing
        data.decarad = self.limits.decarad
        if self.decarad is None:
            self.cavity.logger.warning(
                "No decarad selected: MP processing will not pause on "
                "radiation. Watch the decarad by hand."
            )

    def _radiation_pause_reason(self) -> str | None:
        """Why radiation should pause the walk now, or None.

        Reads GAMMA_DOSE_RATE and its severity on every head of the chosen
        decarad. Pauses when:
        - any head is INVALID, or the read fails: a dead decarad reads 0,
          which would look like no radiation (2026-11-24 agenda);
        - the highest head is more than fe_pause_above over background.
        Not checked with no decarad, after override_radiation(), or within
        radiation_settle_seconds of an interlock reset.
        """
        if self.decarad is None or self._radiation_overridden.is_set():
            return None
        if time.monotonic() < self._radiation_quiet_until:
            return None
        heads = self.decarad.heads.values()
        try:
            invalid = [
                head.number
                for head in heads
                if head.raw_dose_rate_pv_obj.severity == EPICS_INVALID_VAL
            ]
            dose = float(self.decarad.max_raw_dose)
        except Exception as exc:
            self.radiation = None
            return f"decarad {self.decarad.number} read failed: {exc}"
        if invalid:
            self.radiation = None
            return (
                f"decarad {self.decarad.number} head(s) "
                f"{', '.join(map(str, invalid))} INVALID"
            )
        self.radiation = dose
        if dose > self.limits.fe_pause_above:
            return (
                f"radiation {dose:.1f} over background "
                f"({DECARAD_BACKGROUND_READING_RAW}) on decarad "
                f"{self.decarad.number}, above {self.limits.fe_pause_above:g}"
                ", no quench"
            )
        return None

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
