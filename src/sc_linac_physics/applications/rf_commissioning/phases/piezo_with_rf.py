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
        self._gain_a: float | None = None
        self._gain_b: float | None = None
        self._detune_gain: float | None = None
        self._rf_test_status: str | None = None

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
            "read_results": self._read_results,
            "push_detune_gain": self._push_detune_gain,
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
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Unknown step: {step_name}",
            )
        return step()

    def finalize_phase(self) -> None:
        """Write this run's results onto the record. Writes no PVs.

        The cavity is left as the test left it: RF on in SEL, piezo enabled
        in manual.
        """
        self._store_phase_fields(**self._result_data())

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

    _TEST_STATUS_LABELS = {
        linac_utils.PIEZO_WITH_RF_PASS_VALUE: "Pass",
        linac_utils.PIEZO_WITH_RF_WARNING_VALUE: "Warning",
    }

    def _read_results(self) -> PhaseStepResult:
        """Judge RFTESTSTS and RFTESTSTAT, then read the gains. Pushes nothing.

        RFTESTSTS must read Complete (1); Crash (0) fails. RFTESTSTAT Pass (0)
        and Warning (1) store CHA_AMPGAIN, CHB_AMPGAIN and DFGAIN_NEW with
        the status; a Warning is recorded as complete but not passed. Fail (2)
        clears earlier results and stores nothing.

        Review-before-push works because PUSH_DFGAIN does not compute the
        gain: its DOL reads DFGAIN_NEW (an ai record) with NPP, and it copies
        that value to DFGAIN (as ACCL:L1B:0210:PZT served them on
        2026-10-20). So DFGAIN_NEW already holds the value that will be
        pushed when this step reads it.
        """
        if self.context.dry_run:
            return self._dry_run_result("result read")
        self._clear_measured_fields()
        piezo = self.cavity.piezo
        try:
            run_status = self._test_run_status()
            test_status = int(piezo.withrf_status_pv_obj.get())
        except Exception as exc:
            return self._retry(f"Could not read the test status: {exc}")

        if run_status != linac_utils.PIEZO_SCRIPT_COMPLETE_VALUE:
            name = (
                "Crash"
                if run_status == linac_utils.PIEZO_SCRIPT_CRASH_VALUE
                else str(run_status)
            )
            return self._failed(
                f"RFTESTSTS reads {name}, not Complete — the with-RF script "
                "did not finish"
            )
        label = self._TEST_STATUS_LABELS.get(test_status)
        if label is None:
            return self._failed(
                f"RFTESTSTAT reads {test_status} (Fail is 2) — the with-RF "
                "test failed"
            )

        try:
            self._gain_a = float(piezo.amplifiergain_a_pv_obj.get())
            self._gain_b = float(piezo.amplifiergain_b_pv_obj.get())
            self._detune_gain = float(piezo.detunegain_new_pv_obj.get())
        except Exception as exc:
            return self._retry(f"Could not read the gains: {exc}")
        self._rf_test_status = label
        self._store_phase_fields(
            amplifier_gain_a=self._gain_a,
            amplifier_gain_b=self._gain_b,
            detune_gain=self._detune_gain,
            rf_test_status=label,
            # A rerun reuses the record's PiezoWithRFTest; stamp this read so
            # the gains carry this run's time, not the first run's.
            timestamp=datetime.now(),
        )

        verdict = (
            "passed"
            if label == "Pass"
            else "ended in Warning — recorded as not passed"
        )
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=(
                f"With-RF test {verdict}. Review detune gain "
                f"{self._detune_gain:.6f} before pushing"
            ),
            data=self._result_data(),
        )

    def _push_detune_gain(self) -> PhaseStepResult:
        """Push the reviewed detune gain, if the operator confirmed it.

        PhaseBase.run() goes straight from read_results to here, so the gate
        is in this step: it refuses unless
        context.parameters["confirmed_detune_gain"] equals the DFGAIN_NEW that
        read_results stored. Just before pushing it re-reads DFGAIN_NEW and
        RFTESTSTS from the IOC, and refuses unless the gain is unchanged and
        RFTESTSTS still reads Complete.

        It writes PUSH_DFGAIN.PROC = 1, then SAVE_DFGAIN.PROC = 1, each with
        wait=True: PV.put returns once the IOC confirms the record processed,
        and raises PVPutError if it isn't confirmed within put_timeout. It
        never resends. Both are ao records whose DESC reads 'Push calc-ed to
        live PV' (as ACCL:L1B:0210:PZT served them on 2026-10-14).
        detune_gain_pushed is stored only after PUSH is confirmed, and before
        SAVE is written. A PUSH error fails without retry and notes that the
        push outcome is unknown: the put may have reached the IOC, and a
        retry would trigger it again. A SAVE error fails without retry too,
        because a retry would re-run the gate after the gain is live. A
        Warning still lets the operator push; passed stays False.

        CHECK: does processing PUSH_DFGAIN and SAVE_DFGAIN complete promptly?
        If either starts something slow, the confirmed put times out and the
        step reports the push as unknown.

        PUSH_DFGAIN is closed_loop: DOL reads DFGAIN_NEW (NPP) and OUT writes
        DFGAIN (PP), the live detune gain (as ACCL:L1B:0210:PZT served them
        on 2026-10-20).

        CHECK: where does SAVE_DFGAIN write (.DOL, .OMSL, .OUT)? If it only
        keeps a copy for a human, as the cavity char SAVE PVs do (see
        CavityCharPhase._push_results), drop the SAVE write.
        """
        if self.context.dry_run:
            return self._dry_run_result("detune gain push")
        if self._detune_gain is None:
            return self._failed("Nothing read yet — run the with-RF test first")
        confirmed = self.context.parameters.get("confirmed_detune_gain")
        if confirmed != self._detune_gain:
            return self._failed(
                "Push not confirmed for this result — review detune gain "
                f"{self._detune_gain:.6f} and confirm before pushing"
            )

        refusal = self._check_before_push()
        if refusal is not None:
            return refusal

        piezo = self.cavity.piezo
        try:
            piezo.withrf_push_dfgain_pv_obj.put(1)
        except Exception as exc:
            # Not a RETRY: the put may have reached the IOC, and a retry would
            # trigger PUSH_DFGAIN again before anyone has checked.
            note = (
                f"PUSH_DFGAIN put of detune gain {self._detune_gain:.6f} not "
                f"confirmed ({exc}); whether it reached the machine is unknown"
            )
            self._append_note(note)
            return self._failed(f"{note} — check DFGAIN before pushing again")
        # PUSH_DFGAIN confirmed processed: the gain is live. Record that before
        # SAVE, so a failed SAVE still leaves detune_gain_pushed True.
        self._store_phase_fields(detune_gain_pushed=True)
        try:
            piezo.withrf_save_dfgain_pv_obj.put(1)
        except Exception as exc:
            # Not a RETRY: a retry re-runs the gate, which could refuse now
            # that the gain is already live.
            return self._failed(
                f"PUSH_DFGAIN processed but SAVE_DFGAIN failed: {exc} — the "
                "gain is live; check SAVE_DFGAIN by hand"
            )
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message=f"Detune gain {self._detune_gain:.6f} pushed",
            data=self._result_data(),
        )

    def _check_before_push(self) -> PhaseStepResult | None:
        """Re-read DFGAIN_NEW and RFTESTSTS just before pushing.

        Both reads pass use_monitor=False, so they ask the IOC now rather than
        return the last monitor update. RFTESTSTS must still read Complete:
        Running or Crash means another test has run since review.

        Returns a result that stops the push, or None if it can go ahead.
        """
        piezo = self.cavity.piezo
        try:
            now_gain = float(piezo.detunegain_new_pv_obj.get(use_monitor=False))
            now_status = int(
                piezo.withrf_check_status_pv_obj.get(use_monitor=False)
            )
        except Exception as exc:
            return self._retry(f"Could not re-read before pushing: {exc}")
        if now_status != linac_utils.PIEZO_SCRIPT_COMPLETE_VALUE:
            name = {
                linac_utils.PIEZO_SCRIPT_CRASH_VALUE: "Crash",
                linac_utils.PIEZO_SCRIPT_RUNNING_VALUE: "Running",
            }.get(now_status, str(now_status))
            return self._failed(
                f"RFTESTSTS reads {name}, not Complete — another with-RF test "
                "has run since review; nothing pushed. Rerun the test."
            )
        if now_gain != self._detune_gain:
            return self._failed(
                f"DFGAIN_NEW changed from {self._detune_gain:.6f} to "
                f"{now_gain:.6f} since review — nothing pushed. Rerun the test."
            )
        return None

    def _record_results(self) -> PhaseStepResult:
        """No PV access; finalize_phase() writes the record."""
        return PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Results collected; ready to finalize",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _result_data(self) -> dict:
        return {
            "amplifier_gain_a": self._gain_a,
            "amplifier_gain_b": self._gain_b,
            "detune_gain": self._detune_gain,
            "rf_test_status": self._rf_test_status,
        }

    def _clear_measured_fields(self) -> None:
        """Blank this phase's results, in memory and on the record.

        If an earlier run pushed a detune gain, the gain is still live on the
        machine. A note keeps that on the record after the fields are blank.
        """
        self._gain_a = self._gain_b = self._detune_gain = None
        self._rf_test_status = None
        record = getattr(self.context, "record", None)
        if record is None or record.piezo_with_rf is None:
            return
        data = record.piezo_with_rf
        if data.detune_gain_pushed and data.detune_gain is not None:
            self._append_note(
                f"Earlier run pushed detune gain {data.detune_gain:.6f} "
                f"({data.rf_test_status}); its results were cleared by a rerun"
            )
        data.amplifier_gain_a = data.amplifier_gain_b = None
        data.detune_gain = None
        data.rf_test_status = None
        data.detune_gain_pushed = False

    def _store_phase_fields(self, **fields) -> None:
        """Merge step results onto record.piezo_with_rf; None is skipped.

        Same pattern as CavityCharPhase: record.phase_history is in memory
        only, so results go on the record as each step produces them.
        """
        record = getattr(self.context, "record", None)
        if record is None:
            return
        data = record.piezo_with_rf or PiezoWithRFTest()
        for name, value in fields.items():
            if value is not None:
                setattr(data, name, value)
        record.piezo_with_rf = data

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
