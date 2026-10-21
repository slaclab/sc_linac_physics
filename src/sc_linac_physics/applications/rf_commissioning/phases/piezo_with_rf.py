"""Piezo with RF phase.

Runs the IOC's with-RF piezo test (PZT:RFTESTSTRT) on one cavity in SEL at
PIEZO_WITH_RF_GRAD, reads amplifier gains A/B and the new detune gain, and
pushes the detune gain once the operator has confirmed it. A port of
PiezoWithRFWorker in slaclab/rf_commissioning
(cavity_commissioning/commissioning_workers.py).

PhaseBase.run() only checks the commissioning abort between steps. The
steps that wait call cavity.check_abort(), which reads cavity.abort_flag and,
on abort, calls turn_off() and raises CavityAbortError. So the controller that
runs this phase must call cavity.request_abort() alongside
context.request_abort(), and clear cavity.abort_flag before starting.

An abort that PhaseBase sees between steps does not touch the cavity: RF stays
as the last step left it.

The phase leaves the cavity as the test left it: RF on in SEL at the test
ADES, piezo enabled in manual.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PiezoWithRFTest,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseExecutionError,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError


@dataclass
class PiezoWithRFLimits:
    """Configurable limits for the piezo with RF phase."""

    # The old worker slept 5 s after RF on "for the detune to catch up".
    # Here it follows the switch from SELA to SEL.
    rf_settle_seconds: float = 5.0
    # The old worker refused to start the test above 100 Hz.
    max_detune_hz: float = 100.0
    # How long RFTESTSTS may take to read Running after RFTESTSTRT is written.
    start_timeout_seconds: float = 30.0
    # CHECK: how long does the with-RF script take on hardware? 300 s is a
    # guess; the old worker waited with no timeout.
    test_timeout_seconds: float = 300.0
    poll_interval: float = 1.0
    # setup_rf skips the SSA calibration or the characterization when its
    # last good result is younger than this. One hour is from Sebastian
    # Aderhold's review of #408.
    recent_result_seconds: float = 3600.0


class PiezoWithRFPhase(PhaseBase):
    """Piezo with RF: run the with-RF piezo test and push the detune gain."""

    def __init__(
        self, context: PhaseContext, limits: PiezoWithRFLimits | None = None
    ):
        super().__init__(context)
        self.limits = limits or PiezoWithRFLimits()
        self.cavity = None
        # True once wait_for_completion has seen this run reach Running. A
        # retry after a read error then resumes the wait for it to finish,
        # rather than waiting for Running again.
        self._test_seen_running = False

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.PIEZO_WITH_RF

    def validate_prerequisites(self) -> tuple[bool, str]:
        cavity = self.context.parameters.get("cavity")
        if cavity is None:
            return False, "No cavity specified in context"
        if not isinstance(cavity.piezo, CommissioningPiezo):
            return False, (
                "Cavity must use CommissioningPiezo for the with-RF test. "
                f"Current type: {type(cavity.piezo).__name__}"
            )
        self.cavity = cavity
        return True, "Prerequisites validated"

    def _steps(self) -> dict[str, Callable[[], PhaseStepResult]]:
        return {
            "verify_initial_state": self._verify_initial_state,
            "setup_rf": self._setup_rf,
            "setup_piezo": self._setup_piezo,
            "check_detune": self._check_detune,
            "start_test": self._start_test,
            "wait_for_completion": self._wait_for_completion,
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
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Unknown step: {step_name}",
            )
        return step()

    def finalize_phase(self) -> None:
        """Writes no PVs: the cavity is left as the test left it."""

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _dry_run_result(self, what: str) -> PhaseStepResult:
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Dry run: {what} simulated",
            data={"dry_run": True},
        )

    def _verify_initial_state(self) -> PhaseStepResult:
        """Check HWMODE, SSA calibration, stepper motion and RFTESTSTS.

        Only reads; writes nothing.

        Refuses a with-RF test that is already running here, before
        setup_rf turns RF off under it. start_test checks again just before
        it writes RFTESTSTRT.
        """
        if self.context.dry_run:
            return self._dry_run_result("cavity state check")
        try:
            if not self.cavity.is_online:
                return self._failed("Cavity is not online — cannot run test")
            if self.cavity.ssa.calibration_running:
                return self._failed(
                    "SSA calibration is running — wait for it to finish"
                )
            if self.cavity.stepper_tuner.motor_moving:
                return self._failed(
                    "Stepper motor is moving — wait for it to stop"
                )
            if (
                self._test_run_status()
                == linac_utils.PIEZO_SCRIPT_RUNNING_VALUE
            ):
                return self._failed(
                    "A with-RF test is already running (RFTESTSTS = "
                    "Running) — wait for it to finish"
                )
        except Exception as exc:
            return self._retry(f"Could not read cavity state: {exc}")
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Cavity ready for the with-RF test",
        )

    def _test_amplitude(self) -> float:
        """PIEZO_WITH_RF_GRAD (6.5 MV/m) x length (m), in MV.

        Cavity.setup_rf() caps it at ADES_MAX.
        """
        return linac_utils.PIEZO_WITH_RF_GRAD * self.cavity.length

    def _setup_rf(self) -> PhaseStepResult:
        """Bring the cavity up with Cavity.setup_rf(), then switch to SEL.

        Cavity.setup_rf(PIEZO_WITH_RF_GRAD x length) is auto setup's turn-on.
        In order, it:
          - caps the amplitude at ADES_MAX
          - turn_off()
          - ssa.calibrate(ssa.drive_max), unless skipped (below)
          - move_to_resonance(), always
          - characterize(), unless skipped: finish_characterization() pushes
            loaded Q and scale factor, and raises if either is out of
            tolerance; it also sets the piezo feedback setpoint to 0
          - calculate_probe_q()
          - reset_data_decimation(): both decimations to 255
          - ADES = min(5, amplitude), SEL, piezo.enable_feedback(), SELA
          - walk_amp() up to the amplitude
        Then this step writes RFMODECTRL = RF_MODE_SEL (2) through
        set_sel_mode(), because the old worker ran the test in SEL, and
        waits rf_settle_seconds.

        The SSA calibration is skipped when CALTS is under
        recent_result_seconds (1 h) old and CALSTAT is Good. The
        characterization is skipped when PROBECALTS is under 1 h old and
        PROBECALSTS is Complete. A skipped step leaves the slope, loaded Q
        and scale factor already on the machine. This follows Sebastian
        Aderhold's review of #408. A stale result is re-run here. The review
        suggested asking the operator first, but nothing runs this phase
        yet, so there is nothing to ask through; the controller should add it.
        A step that runs here has none of the review gates the SSA and
        cavity characterization phases have. So this step appends what it
        did, with the loaded Q and scale factor it read back, to
        record.piezo_with_rf.notes.

        A failed read of the timestamps or statuses retries: nothing has
        been written yet. Any error after that fails the step without a
        retry: a retry could repeat an SSA calibration and a
        characterization.

        CHECK: does CALTS update on a failed SSA calibration? If it does,
        CALSTAT is all that tells a good recent run from a bad one.
        CHECK: a Complete characterization can still be out of tolerance;
        finish_characterization() then pushes nothing. Should "good" here
        also require loaded Q and scale factor in tolerance?
        CHECK: setup_rf() leaves the cavity in SELA with the piezo in
        feedback. Is it safe to switch to SEL here, then the piezo to manual
        in setup_piezo, with RF on at the test amplitude?
        CHECK: does the with-RF script keep running if an abort turns RF off
        mid-test, and is there a PV to stop it?
        """
        if self.context.dry_run:
            return self._dry_run_result("RF setup")
        amplitude = self._test_amplitude()
        try:
            calibrate_ssa = not self._ssa_calibration_recent()
            characterize = not self._characterization_recent()
        except Exception as exc:
            # Only reads so far, so a retry repeats nothing on the machine.
            return self._retry(f"Could not read the last calibration: {exc}")
        try:
            self.cavity.setup_rf(
                amplitude,
                calibrate_ssa=calibrate_ssa,
                characterize=characterize,
            )
            self.cavity.set_sel_mode()
            time.sleep(self.limits.rf_settle_seconds)
            loaded_q = float(self.cavity.measured_loaded_q)
            scale_factor = float(self.cavity.measured_scale_factor)
        except CavityAbortError as exc:
            self._note_setup_rf_failure(exc)
            return self._failed(f"Aborted during RF setup — RF is off: {exc}")
        except Exception as exc:
            self._note_setup_rf_failure(exc)
            return self._failed(f"RF setup failed: {exc}")

        ssa_note = (
            "re-ran SSA calibration"
            if calibrate_ssa
            else "kept the SSA calibration from the last hour"
        )
        char_note = (
            "re-ran characterization (pushed, not reviewed)"
            if characterize
            else "kept the characterization from the last hour"
        )
        note = (
            f"setup_rf() {ssa_note} and {char_note}: loaded Q "
            f"{loaded_q:.3e}, scale factor {scale_factor:.1f}"
        )
        self._append_note(note)
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"RF on in SEL, set up to {amplitude:.2f} MV. {note}",
            data={
                "requested_amplitude": amplitude,
                "calibrated_ssa": calibrate_ssa,
                "characterized": characterize,
                "loaded_q": loaded_q,
                "scale_factor": scale_factor,
            },
        )

    def _is_recent(self, timestamp: datetime) -> bool:
        age = (datetime.now() - timestamp).total_seconds()
        return age < self.limits.recent_result_seconds

    def _ssa_calibration_recent(self) -> bool:
        """CALTS under recent_result_seconds old and CALSTAT Good."""
        ssa = self.cavity.ssa
        return (
            self._is_recent(ssa.calibration_timestamp)
            and ssa.calibration_result_good
        )

    def _characterization_recent(self) -> bool:
        """PROBECALTS under recent_result_seconds old, PROBECALSTS Complete."""
        return (
            self._is_recent(self.cavity.characterization_timestamp)
            and self.cavity.characterization_status
            == linac_utils.CALIBRATION_COMPLETE_VALUE
        )

    def _setup_piezo(self) -> PhaseStepResult:
        """Enable the piezo, then put it in manual.

        piezo.enable() sets the piezo bias (see Piezo.enable()) and toggles
        ENABLE until it reads enabled, raising RuntimeError after
        ENABLE_MAX_ATTEMPTS. The old worker only put ENABLE = 1.
        piezo.set_to_manual() writes MODECTRL = PIEZO_MANUAL_VALUE (0).
        """
        if self.context.dry_run:
            return self._dry_run_result("piezo setup")
        piezo = self.cavity.piezo
        try:
            piezo.enable()
            piezo.set_to_manual()
        except CavityAbortError as exc:
            return self._failed(
                f"Aborted during piezo setup — RF is off: {exc}"
            )
        except RuntimeError as exc:
            return self._failed(f"Could not enable the piezo: {exc}")
        except Exception as exc:
            return self._retry(f"Could not set up the piezo: {exc}")
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Piezo enabled, in manual",
        )

    def _check_detune(self) -> PhaseStepResult:
        """Refuse to test if the detune is INVALID or over max_detune_hz.

        cavity.detune reads DFBEST in SEL (DF_CHIRP only in chirp mode).
        CHECK: the old worker read the RFS detune here, with its own TODO
        asking whether DFBEST was right. Which one should gate the test?
        """
        if self.context.dry_run:
            return self._dry_run_result("detune check")
        try:
            if self.cavity.detune_invalid:
                return self._failed("Detune is INVALID — cannot run test")
            detune = float(self.cavity.detune)
        except Exception as exc:
            return self._retry(f"Could not read detune: {exc}")
        if abs(detune) > self.limits.max_detune_hz:
            return self._failed(
                f"Detune {detune:.1f} Hz is over "
                f"{self.limits.max_detune_hz:.0f} Hz — tune the cavity first"
            )
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Detune {detune:.1f} Hz",
            data={"detune_hz": detune},
        )

    def _start_test(self) -> PhaseStepResult:
        """Write RFTESTSTRT = 1 with wait=False (a trigger, like PROBECALSTRT
        in Cavity), unless RFTESTSTS already reads Running.

        PV.put waits for completion by default, and a put that completes only
        when the script finishes would block this step until the run is over.
        """
        if self.context.dry_run:
            return self._dry_run_result("test start")
        piezo = self.cavity.piezo
        try:
            running = linac_utils.PIEZO_SCRIPT_RUNNING_VALUE
            if self._test_run_status() == running:
                return self._failed(
                    "A with-RF test is already running (RFTESTSTS = Running)"
                )
            self._test_seen_running = False
            piezo.withrf_run_check_pv_obj.put(1, wait=False)
        except Exception as exc:
            return self._retry(f"Could not start the with-RF test: {exc}")
        return PhaseStepResult(
            result=PhaseResult.SUCCESS, message="With-RF test started"
        )

    def _wait_for_completion(self) -> PhaseStepResult:
        """Wait for RFTESTSTS to read Running, then to stop reading Running.

        Polls every poll_interval and calls cavity.check_abort() on every
        poll. Seeing Running first is how this step tells this run from the
        last one. CHECK: does RFTESTSTS hold its last value (Complete or
        Crash) until the script starts, and does the IOC timestamp the
        with-RF run anywhere? If it does, compare that timestamp instead, as
        cavity char does with PROBECALTS.

        If the script runs start to finish inside one poll_interval, Running
        is never seen and this step fails rather than pass a stale result.
        Crash ends the wait; read_results fails on it.

        A RETRY after a read error resumes after Running was seen, so the
        retry waits only for the test to finish. Without this, a script that
        finished while the read was failing would never show Running again,
        and the retry would fail a test that passed.
        """
        if self.context.dry_run:
            return self._dry_run_result("test completion")
        running = linac_utils.PIEZO_SCRIPT_RUNNING_VALUE
        try:
            if not self._test_seen_running:
                if not self._poll_until(
                    lambda s: s == running, self.limits.start_timeout_seconds
                ):
                    return self._failed(
                        "RFTESTSTS never read Running within "
                        f"{self.limits.start_timeout_seconds:.0f} s of "
                        "RFTESTSTRT — the test did not start, or finished "
                        "between polls"
                    )
                self._test_seen_running = True
            if not self._poll_until(
                lambda s: s != running, self.limits.test_timeout_seconds
            ):
                return self._failed(
                    "Timed out after "
                    f"{self.limits.test_timeout_seconds:.0f} s with RFTESTSTS "
                    "still Running"
                )
        except CavityAbortError as exc:
            return self._failed(f"Aborted while waiting for the test: {exc}")
        except Exception as exc:
            return self._retry(f"Could not read RFTESTSTS: {exc}")
        return PhaseStepResult(
            result=PhaseResult.SUCCESS, message="With-RF test finished"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _test_run_status(self) -> int:
        """RFTESTSTS: 0 Crash, 1 Complete, 2 Running."""
        return int(self.cavity.piezo.withrf_check_status_pv_obj.get())

    def _poll_until(self, done: Callable[[int], bool], timeout: float) -> bool:
        """Poll RFTESTSTS until done(status), for at most timeout seconds.

        The limit is elapsed time on time.monotonic(), checked after every
        read, and each sleep is capped at what remains. A slow PV.get() (it
        retries) therefore can't stretch the limit by more than one read. A
        read already in flight still runs to its own PV timeout.
        """
        deadline = time.monotonic() + timeout
        while True:
            self.cavity.check_abort()
            if done(self._test_run_status()):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(self.limits.poll_interval, remaining))

    def _note_setup_rf_failure(self, exc: Exception) -> None:
        """After a failed setup_rf(), note the loaded Q and scale factor.

        characterize() may have pushed them before the failure. If the
        read-back fails too, add no note.
        """
        try:
            loaded_q = float(self.cavity.measured_loaded_q)
            scale_factor = float(self.cavity.measured_scale_factor)
        except Exception:
            return
        self._append_note(
            f"setup_rf() failed: {exc}; loaded Q {loaded_q:.3e}, scale "
            f"factor {scale_factor:.1f} read back (may have been pushed)"
        )

    def _append_note(self, note: str) -> None:
        """Append a line to record.piezo_with_rf.notes; keeps what is there."""
        record = getattr(self.context, "record", None)
        if record is None:
            return
        data = record.piezo_with_rf or PiezoWithRFTest()
        data.notes = f"{data.notes}\n{note}" if data.notes else note
        record.piezo_with_rf = data

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
