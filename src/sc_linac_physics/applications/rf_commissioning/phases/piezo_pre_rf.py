"""
Piezo Pre-RF Test Phase

Validates piezo functionality before applying RF power by testing capacitance
and frequency response of both piezo channels.
"""

import time
from dataclasses import dataclass
from typing import Optional, List, Tuple

from sc_linac_physics.applications.rf_commissioning.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.data_models import (
    CommissioningPhase,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
    PhaseExecutionError,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    PIEZO_PRE_RF_CHECKOUT_PASS_VALUE,
    PIEZO_SCRIPT_RUNNING_VALUE,
)


@dataclass
class PiezoTestLimits:
    """Configurable limits for piezo testing."""

    # Test timeout (seconds)
    test_timeout: float = 30.0

    # Polling interval (seconds)
    poll_interval: float = 0.5


class PiezoPreRFPhase(PhaseBase):
    """
    Piezo Pre-RF Test Phase.

    Tests piezo functionality without RF by:
    1. Triggering automated capacitance/frequency tests
    2. Monitoring test completion
    3. Validating results against specifications

    This phase runs the EPICS-based pre-RF checkout script and validates
    that both piezo channels pass their tests.
    """

    def __init__(
        self, context: PhaseContext, limits: Optional[PiezoTestLimits] = None
    ):
        super().__init__(context)
        self.limits = limits or PiezoTestLimits()

        # Get cavity from context
        self.cavity = None  # Will be set during prerequisite validation

    @property
    def phase_type(self) -> CommissioningPhase:
        """Return the phase type."""
        return CommissioningPhase.PIEZO_PRE_RF

    def validate_prerequisites(self) -> Tuple[bool, str]:
        """
        Validate that prerequisites are met before starting phase.

        Returns:
            Tuple of (is_valid, message)
        """
        # Get cavity from context parameters
        cavity = self.context.parameters.get("cavity")

        if cavity is None:
            return False, "No cavity specified in context"

        if not isinstance(cavity.piezo, CommissioningPiezo):
            return False, (
                f"Cavity must use CommissioningPiezo for pre-RF testing. "
                f"Current type: {type(cavity.piezo).__name__}"
            )

        self.cavity = cavity
        return True, "Prerequisites validated"

    def get_phase_steps(self) -> List[str]:
        """Return list of step names in execution order."""
        return [
            "verify_initial_state",
            "trigger_prerf_test",
            "wait_for_completion",
            "validate_results",
        ]

    def execute_step(self, step_name: str) -> PhaseStepResult:
        """
        Execute a single phase step.

        Args:
            step_name: Name of step to execute

        Returns:
            Result of step execution
        """
        if self.cavity is None:
            raise PhaseExecutionError(
                "Cavity not set - validate_prerequisites must be called first"
            )

        piezo = self.cavity.piezo

        step_methods = {
            "verify_initial_state": lambda: self._verify_initial_state(piezo),
            "trigger_prerf_test": lambda: self._trigger_prerf_test(piezo),
            "wait_for_completion": lambda: self._wait_for_completion(piezo),
            "validate_results": lambda: self._validate_results(piezo),
        }

        if step_name not in step_methods:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Unknown step: {step_name}",
            )

        return step_methods[step_name]()

    def finalize_phase(self) -> None:
        """
        Finalize phase and save results to commissioning record.
        """
        # Get the validation checkpoint data
        validation_checkpoint = next(
            (
                cp
                for cp in reversed(self.context.record.phase_history)
                if cp.phase == self.phase_type
                and cp.step_name == "validate_results"
            ),
            None,
        )

        if validation_checkpoint and validation_checkpoint.measurements:
            data = validation_checkpoint.measurements

            # Create PiezoPreRFCheck result
            self.context.record.piezo_pre_rf = PiezoPreRFCheck(
                capacitance_a=data.get("capacitance_a_nf", 0)
                * 1e-9,  # Convert nF to F
                capacitance_b=data.get("capacitance_b_nf", 0) * 1e-9,
                channel_a_passed=data.get("channel_a_status")
                == PIEZO_PRE_RF_CHECKOUT_PASS_VALUE,
                channel_b_passed=data.get("channel_b_status")
                == PIEZO_PRE_RF_CHECKOUT_PASS_VALUE,
                notes=f"Ch A: {data.get('channel_a_message', '')}, Ch B: {data.get('channel_b_message', '')}",
            )

    # =========================================================================
    # Phase Steps
    # =========================================================================

    def _verify_initial_state(
        self, piezo: CommissioningPiezo
    ) -> PhaseStepResult:
        """Verify piezo is ready for testing."""
        try:
            # Check if test is already running
            test_status = piezo.prerf_test_status_pv_obj.get()

            if test_status == PIEZO_SCRIPT_RUNNING_VALUE:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message="Piezo test already in progress",
                    data={"test_status": test_status},
                )

            # Check both channels are accessible
            cha_status = piezo.prerf_cha_status_pv_obj.get()
            chb_status = piezo.prerf_chb_status_pv_obj.get()

            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Piezo ready for testing",
                data={
                    "test_status": test_status,
                    "channel_a_status": cha_status,
                    "channel_b_status": chb_status,
                },
            )

        except Exception as e:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Failed to verify initial state: {e}",
            )

    def _trigger_prerf_test(self, piezo: CommissioningPiezo) -> PhaseStepResult:
        """Trigger the automated pre-RF test."""
        try:
            if self.context.dry_run:
                return PhaseStepResult(
                    result=PhaseResult.SUCCESS,
                    message="[DRY RUN] Would trigger pre-RF test",
                )

            # Start the test
            piezo.prerf_test_start_pv_obj.put(1)
            time.sleep(1)  # Wait for test to start

            # Verify test started
            test_status = piezo.prerf_test_status_pv_obj.get()

            if test_status != PIEZO_SCRIPT_RUNNING_VALUE:
                return PhaseStepResult(
                    result=PhaseResult.FAILED,
                    message=f"Test failed to start (status={test_status})",
                    data={"test_status": test_status},
                )

            return PhaseStepResult(
                result=PhaseResult.SUCCESS,
                message="Pre-RF test started successfully",
                data={"test_status": test_status},
            )

        except Exception as e:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Failed to trigger test: {e}",
            )

    def _wait_for_completion(
        self, piezo: CommissioningPiezo
    ) -> PhaseStepResult:
        """Wait for pre-RF test to complete."""
        start_time = time.time()
        timeout = self.limits.test_timeout
        poll_interval = self.limits.poll_interval

        try:
            while True:
                elapsed = time.time() - start_time

                # Check for abort
                if self.context.is_abort_requested():
                    return PhaseStepResult(
                        result=PhaseResult.FAILED,
                        message="Test aborted by user",
                        data={"elapsed_time": elapsed},
                    )

                if elapsed > timeout:
                    return PhaseStepResult(
                        result=PhaseResult.FAILED,
                        message=f"Test timeout after {timeout}s",
                        data={"elapsed_time": elapsed},
                    )

                # Check test status
                test_status = piezo.prerf_test_status_pv_obj.get()

                # Wait while running
                if test_status != PIEZO_SCRIPT_RUNNING_VALUE:
                    return PhaseStepResult(
                        result=PhaseResult.SUCCESS,
                        message=f"Test completed in {elapsed:.1f}s",
                        data={
                            "elapsed_time": elapsed,
                            "final_status": test_status,
                        },
                    )

                # Still running, keep waiting
                time.sleep(poll_interval)

        except Exception as e:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Error while waiting: {e}",
            )

    def _validate_results(self, piezo: CommissioningPiezo) -> PhaseStepResult:
        """
        Validate the test results.

        Matches the logic from the worker function:
        - Both channels must have PIEZO_PRE_RF_CHECKOUT_PASS_VALUE status
        - Capacitance values are recorded but not validated
        """
        try:
            # Get channel statuses
            cha_status = piezo.prerf_cha_status_pv_obj.get()
            chb_status = piezo.prerf_chb_status_pv_obj.get()

            # Get messages for diagnostics
            cha_msg = piezo.prerf_cha_testmsg_pv_obj.get()
            chb_msg = piezo.prerf_chb_testmsg_pv_obj.get()

            # Get capacitance values for recording (not validation)
            cap_a = piezo.capacitance_a_pv_obj.get()
            cap_b = piezo.capacitance_b_pv_obj.get()

            # Check if both channels passed (0 = pass)
            both_passed = (
                cha_status == PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
                and chb_status == PIEZO_PRE_RF_CHECKOUT_PASS_VALUE
            )

            # Build detailed message
            if not both_passed:
                messages = []
                if cha_status != PIEZO_PRE_RF_CHECKOUT_PASS_VALUE:
                    messages.append(
                        f"Channel A failed (status={cha_status}): {cha_msg}"
                    )
                if chb_status != PIEZO_PRE_RF_CHECKOUT_PASS_VALUE:
                    messages.append(
                        f"Channel B failed (status={chb_status}): {chb_msg}"
                    )
                message = "; ".join(messages)
                result = PhaseResult.FAILED
            else:
                message = f"All tests passed (Cap A={cap_a:.1f}nF, Cap B={cap_b:.1f}nF)"
                result = PhaseResult.SUCCESS

            return PhaseStepResult(
                result=result,
                message=message,
                data={
                    "channel_a_status": cha_status,
                    "channel_b_status": chb_status,
                    "channel_a_message": cha_msg,
                    "channel_b_message": chb_msg,
                    "capacitance_a_nf": cap_a,
                    "capacitance_b_nf": cap_b,
                },
            )

        except Exception as e:
            return PhaseStepResult(
                result=PhaseResult.FAILED,
                message=f"Failed to validate results: {e}",
            )
