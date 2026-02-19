"""Tests for phase base class and execution framework."""

from typing import List

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningPhase,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.phase_base import (
    PhaseBase,
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
)


# Test implementation of PhaseBase for testing
class TestPhase(PhaseBase):
    """Simple test phase implementation."""

    def __init__(self, context: PhaseContext):
        super().__init__(context)
        self.steps_executed = []
        self.prerequisites_valid = True
        self.prerequisites_message = "All prerequisites met"
        self.step_results = {}  # Map step_name -> PhaseStepResult
        self.finalize_called = False

    @property
    def phase_type(self) -> CommissioningPhase:
        return CommissioningPhase.COLD_LANDING

    def validate_prerequisites(self) -> tuple[bool, str]:
        return self.prerequisites_valid, self.prerequisites_message

    def get_phase_steps(self) -> List[str]:
        return ["step1", "step2", "step3"]

    def execute_step(self, step_name: str) -> PhaseStepResult:
        self.steps_executed.append(step_name)

        # Return pre-configured result if available
        if step_name in self.step_results:
            return self.step_results[step_name]

        # Default success
        return PhaseStepResult(
            result=PhaseResult.SUCCESS, message=f"Executed {step_name}"
        )

    def finalize_phase(self) -> None:
        self.finalize_called = True


class TestPhaseContext:
    """Tests for PhaseContext."""

    def test_phase_context_initialization(self):
        """Test PhaseContext initialization with defaults."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")

        assert context.record is record
        assert context.operator == "TestOperator"
        assert context.dry_run is False
        assert context.parameters == {}
        assert context.abort_requested is False

    def test_phase_context_with_parameters(self):
        """Test PhaseContext with custom parameters."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(
            record=record,
            operator="TestOperator",
            dry_run=True,
            parameters={"timeout": 30, "max_attempts": 5},
        )

        assert context.dry_run is True
        assert context.parameters["timeout"] == 30
        assert context.parameters["max_attempts"] == 5

    def test_abort_request(self):
        """Test abort request mechanism."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")

        assert not context.is_abort_requested()

        context.request_abort()

        assert context.is_abort_requested()
        assert context.abort_requested is True


class TestPhaseStepResult:
    """Tests for PhaseStepResult."""

    def test_step_result_success(self):
        """Test successful step result."""
        result = PhaseStepResult(
            result=PhaseResult.SUCCESS, message="Step completed successfully"
        )

        assert result.result == PhaseResult.SUCCESS
        assert result.message == "Step completed successfully"
        assert result.data is None
        assert result.retry_delay_seconds == 5.0

    def test_step_result_with_data(self):
        """Test step result with measurement data."""
        result = PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Measurement complete",
            data={"voltage": 12.5, "current": 2.3},
        )

        assert result.result == PhaseResult.SUCCESS
        assert result.data["voltage"] == 12.5
        assert result.data["current"] == 2.3

    def test_step_result_retry_with_delay(self):
        """Test retry result with custom delay."""
        result = PhaseStepResult(
            result=PhaseResult.RETRY,
            message="Temporary failure, retry",
            retry_delay_seconds=10.0,
        )

        assert result.result == PhaseResult.RETRY
        assert result.retry_delay_seconds == 10.0

    def test_step_result_failed(self):
        """Test failed step result."""
        result = PhaseStepResult(
            result=PhaseResult.FAILED, message="Critical error occurred"
        )

        assert result.result == PhaseResult.FAILED
        assert result.message == "Critical error occurred"

    def test_step_result_skip(self):
        """Test skipped step result."""
        result = PhaseStepResult(
            result=PhaseResult.SKIP,
            message="Step not needed",
            data={"reason": "already_calibrated"},
        )

        assert result.result == PhaseResult.SKIP
        assert result.data["reason"] == "already_calibrated"


class TestPhaseBaseInitialization:
    """Tests for PhaseBase initialization and properties."""

    def test_phase_initialization(self):
        """Test phase initialization."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")

        phase = TestPhase(context)

        assert phase.context is context
        assert phase._current_step_index == 0
        assert phase._max_retries_per_step == 3
        assert phase._retry_count == 0

    def test_phase_type_property(self):
        """Test phase_type property."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        assert phase.phase_type == CommissioningPhase.COLD_LANDING

    def test_phase_name_property(self):
        """Test phase_name property generates readable name."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        assert phase.phase_name == "Cold Landing"


class TestSuccessfulExecution:
    """Tests for successful phase execution."""

    def test_successful_execution_all_steps(self):
        """Test successful execution of all steps."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Run phase
        success = phase.run()

        assert success is True
        assert phase.steps_executed == ["step1", "step2", "step3"]
        assert phase.finalize_called is True

        # Check phase status
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.COMPLETE
        )
        assert record.current_phase == CommissioningPhase.COLD_LANDING

    def test_successful_execution_creates_checkpoints(self):
        """Test that successful execution creates appropriate checkpoints."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        success = phase.run()

        assert success is True

        # Should have: phase_start + 3 steps + phase_complete = 5 checkpoints
        assert len(record.phase_history) == 5

        # Check phase_start checkpoint
        assert record.phase_history[0].step_name == "phase_start"
        assert record.phase_history[0].success is True
        assert record.phase_history[0].operator == "TestOperator"

        # Check step checkpoints
        assert record.phase_history[1].step_name == "step1"
        assert record.phase_history[1].success is True
        assert "Executed step1" in record.phase_history[1].notes

        assert record.phase_history[2].step_name == "step2"
        assert record.phase_history[3].step_name == "step3"

        # Check phase_complete checkpoint
        assert record.phase_history[4].step_name == "phase_complete"
        assert record.phase_history[4].success is True

    def test_successful_execution_with_step_data(self):
        """Test that step measurement data is captured in checkpoints."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Configure step to return data
        phase.step_results["step2"] = PhaseStepResult(
            result=PhaseResult.SUCCESS,
            message="Measurement complete",
            data={"voltage": 12.5, "frequency_hz": 1300000000},
        )

        success = phase.run()

        assert success is True

        # Find step2 checkpoint
        step2_checkpoint = [
            cp for cp in record.phase_history if cp.step_name == "step2"
        ][0]

        assert step2_checkpoint.measurements["voltage"] == 12.5
        assert step2_checkpoint.measurements["frequency_hz"] == 1300000000


class TestPrerequisiteValidation:
    """Tests for prerequisite validation."""

    def test_invalid_prerequisites_stops_execution(self):
        """Test that invalid prerequisites prevent execution."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Set prerequisites as invalid
        phase.prerequisites_valid = False
        phase.prerequisites_message = "Cavity not at operating temperature"

        success = phase.run()

        assert success is False
        assert len(phase.steps_executed) == 0
        assert phase.finalize_called is False

        # Should have one checkpoint for failed prerequisite check
        assert len(record.phase_history) == 1
        assert record.phase_history[0].step_name == "prerequisite_check"
        assert record.phase_history[0].success is False
        assert (
            "Cavity not at operating temperature"
            in record.phase_history[0].notes
        )

    def test_valid_prerequisites_allows_execution(self):
        """Test that valid prerequisites allow execution to proceed."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        phase.prerequisites_valid = True
        phase.prerequisites_message = "All systems ready"

        success = phase.run()

        assert success is True
        assert len(phase.steps_executed) == 3


class TestStepSkipping:
    """Tests for step skipping functionality."""

    def test_skip_step_continues_execution(self):
        """Test that skipping a step continues to next step."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Configure step2 to be skipped
        phase.step_results["step2"] = PhaseStepResult(
            result=PhaseResult.SKIP,
            message="Already calibrated",
            data={"reason": "previous_calibration_valid"},
        )

        success = phase.run()

        assert success is True
        assert phase.steps_executed == ["step1", "step2", "step3"]
        assert phase.finalize_called is True

        # Find step2 checkpoint
        step2_checkpoint = [
            cp for cp in record.phase_history if cp.step_name == "step2"
        ][0]

        assert (
            step2_checkpoint.success is True
        )  # Skipped steps are marked as success
        assert "Skipped: Already calibrated" in step2_checkpoint.notes
        assert (
            step2_checkpoint.measurements["reason"]
            == "previous_calibration_valid"
        )


class TestAbortHandling:
    """Tests for abort request handling."""

    def test_abort_during_execution_stops_gracefully(self):
        """Test that abort request stops execution gracefully."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Modify execute_step to request abort after step1
        original_execute = phase.execute_step

        def execute_with_abort(step_name: str) -> PhaseStepResult:
            result = original_execute(step_name)
            if step_name == "step1":
                context.request_abort()
            return result

        phase.execute_step = execute_with_abort

        success = phase.run()

        assert success is False
        assert phase.steps_executed == ["step1"]  # Only step1 executed
        assert phase.finalize_called is False

        # Check that phase status is FAILED
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.FAILED
        )

        # Find abort checkpoint
        abort_checkpoint = [
            cp for cp in record.phase_history if "abort" in cp.notes.lower()
        ]
        assert len(abort_checkpoint) > 0
        assert abort_checkpoint[0].success is False

    def test_abort_before_execution_stops_immediately(self):
        """Test that abort requested before execution is detected."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")

        # Request abort before starting
        context.request_abort()

        phase = TestPhase(context)
        success = phase.run()

        assert success is False
        # Phase starts, but aborts at first step check
        assert len(phase.steps_executed) == 0


class TestFailedStepHandling:
    """Tests for handling failed steps."""

    def test_failed_step_stops_execution(self):
        """Test that a failed step stops execution."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Configure step2 to fail
        phase.step_results["step2"] = PhaseStepResult(
            result=PhaseResult.FAILED,
            message="Critical hardware error",
            data={"error_code": "HW_FAULT_001"},
        )

        success = phase.run()

        assert success is False
        assert phase.steps_executed == ["step1", "step2"]  # step3 not executed
        assert phase.finalize_called is False

        # Check phase status
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.FAILED
        )

        # Find step2 checkpoint
        step2_checkpoint = [
            cp for cp in record.phase_history if cp.step_name == "step2"
        ][0]

        assert step2_checkpoint.success is False
        assert "Failed: Critical hardware error" in step2_checkpoint.notes
        assert step2_checkpoint.error_message == "Critical hardware error"
        assert step2_checkpoint.measurements["error_code"] == "HW_FAULT_001"

    def test_failed_step_creates_checkpoint(self):
        """Test that failed steps create appropriate checkpoints."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        phase.step_results["step1"] = PhaseStepResult(
            result=PhaseResult.FAILED, message="Timeout waiting for response"
        )

        success = phase.run()

        assert success is False

        # Should have: phase_start + step1 (failed) = 2 checkpoints
        assert len(record.phase_history) == 2

        step1_checkpoint = record.phase_history[1]
        assert step1_checkpoint.step_name == "step1"
        assert step1_checkpoint.success is False
        assert step1_checkpoint.error_message == "Timeout waiting for response"


class TestRetryLogic:
    """Tests for automatic retry logic."""

    def test_retry_step_eventually_succeeds(self):
        """Test that a step can retry and eventually succeed."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Track how many times step2 is called
        call_count = {"step2": 0}

        def step2_with_retries(step_name: str) -> PhaseStepResult:
            if step_name == "step2":
                call_count["step2"] += 1
                if call_count["step2"] < 3:
                    # Fail first 2 attempts
                    return PhaseStepResult(
                        result=PhaseResult.RETRY,
                        message=f"Attempt {call_count['step2']} failed, retrying",
                    )
                else:
                    # Succeed on 3rd attempt
                    return PhaseStepResult(
                        result=PhaseResult.SUCCESS,
                        message="Succeeded after retries",
                    )
            else:
                return PhaseStepResult(
                    result=PhaseResult.SUCCESS, message=f"Executed {step_name}"
                )

        phase.execute_step = step2_with_retries

        success = phase.run()

        assert success is True
        assert call_count["step2"] == 3
        assert phase.finalize_called is True

        # Check checkpoints - should have retry checkpoints
        step2_checkpoints = [
            cp for cp in record.phase_history if cp.step_name == "step2"
        ]

        # Should have 3 checkpoints for step2 (2 retries + 1 success)
        assert len(step2_checkpoints) == 3

        # First two should be retries
        assert not step2_checkpoints[0].success
        assert "Retry 1/3" in step2_checkpoints[0].notes

        assert not step2_checkpoints[1].success
        assert "Retry 2/3" in step2_checkpoints[1].notes

        # Last should be success
        assert step2_checkpoints[2].success
        assert "Succeeded after retries" in step2_checkpoints[2].notes

    def test_retry_step_exceeds_max_retries(self):
        """Test that a step fails after exceeding max retries."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Configure step1 to always retry
        phase.step_results["step1"] = PhaseStepResult(
            result=PhaseResult.RETRY, message="Persistent failure"
        )

        success = phase.run()

        assert success is False
        assert phase.finalize_called is False

        # Check that step1 was attempted max_retries times
        step1_checkpoints = [
            cp for cp in record.phase_history if cp.step_name == "step1"
        ]

        # Should have max_retries (3) retry checkpoints + 1 final failure
        assert len(step1_checkpoints) == 3

        # All should be failures
        for checkpoint in step1_checkpoints:
            assert not checkpoint.success

        # Last checkpoint should indicate max retries exceeded
        assert "Failed after 3 retries" in step1_checkpoints[-1].notes

    def test_retry_count_resets_between_steps(self):
        """Test that retry count resets between steps."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        call_counts = {"step1": 0, "step2": 0}

        def execute_with_retries(step_name: str) -> PhaseStepResult:
            if step_name in call_counts:
                call_counts[step_name] += 1
                if call_counts[step_name] < 2:
                    # Fail first attempt for both steps
                    return PhaseStepResult(
                        result=PhaseResult.RETRY,
                        message=f"{step_name} attempt {call_counts[step_name]}",
                    )

            return PhaseStepResult(
                result=PhaseResult.SUCCESS, message=f"Executed {step_name}"
            )

        phase.execute_step = execute_with_retries

        success = phase.run()

        assert success is True

        # Both step1 and step2 should have been retried once
        assert call_counts["step1"] == 2
        assert call_counts["step2"] == 2


class TestExceptionHandling:
    """Tests for exception handling during phase execution."""

    def test_exception_in_step_marks_phase_failed(self):
        """Test that exceptions in steps mark phase as failed."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        def failing_execute(step_name: str) -> PhaseStepResult:
            if step_name == "step2":
                raise ValueError("Unexpected value encountered")
            return PhaseStepResult(
                result=PhaseResult.SUCCESS, message=f"Executed {step_name}"
            )

        phase.execute_step = failing_execute

        success = phase.run()

        assert success is False
        assert phase.finalize_called is False

        # Check phase status
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.FAILED
        )

        # Should have checkpoint with exception info
        exception_checkpoints = [
            cp
            for cp in record.phase_history
            if cp.error_message and "Unexpected value" in cp.error_message
        ]

        assert len(exception_checkpoints) > 0

    def test_exception_retries_before_failing(self):
        """Test that exceptions trigger retries before final failure."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        attempt_count = {"count": 0}

        def failing_execute(step_name: str) -> PhaseStepResult:
            if step_name == "step1":
                attempt_count["count"] += 1
                raise RuntimeError(f"Attempt {attempt_count['count']} failed")
            return PhaseStepResult(
                result=PhaseResult.SUCCESS, message=f"Executed {step_name}"
            )

        phase.execute_step = failing_execute

        success = phase.run()

        assert success is False

        # Should have retried 3 times (max_retries_per_step)
        assert attempt_count["count"] == 3

        # Should have checkpoints for each retry
        step1_checkpoints = [
            cp for cp in record.phase_history if "step" in cp.step_name.lower()
        ]

        # Should have retry checkpoints
        retry_checkpoints = [
            cp for cp in step1_checkpoints if "retry" in cp.notes.lower()
        ]
        assert len(retry_checkpoints) >= 2

    def test_exception_during_finalize(self):
        """Test that exceptions during finalize are handled."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        def failing_finalize():
            raise RuntimeError("Database connection lost")

        phase.finalize_phase = failing_finalize

        success = phase.run()

        assert success is False

        # All steps should have executed
        assert len(phase.steps_executed) == 3

        # Phase should be marked as failed
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.FAILED
        )


class TestPhaseStateTracking:
    """Tests for phase state tracking in the record."""

    def test_phase_status_progression(self):
        """Test that phase status progresses correctly."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Initial status should be NOT_STARTED
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.NOT_STARTED
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Capture status at different points
        statuses = []

        original_execute = phase.execute_step

        def tracking_execute(step_name: str) -> PhaseStepResult:
            statuses.append(
                record.phase_status[CommissioningPhase.COLD_LANDING]
            )
            return original_execute(step_name)

        phase.execute_step = tracking_execute

        success = phase.run()

        assert success is True

        # During execution, status should be IN_PROGRESS
        for status in statuses:
            assert status == PhaseStatus.IN_PROGRESS

        # After completion, status should be COMPLETED
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.COMPLETE
        )

    def test_current_phase_tracking(self):
        """Test that current_phase is tracked correctly."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Initially should be PIEZO_PRE_RF (first phase)
        assert record.current_phase == CommissioningPhase.PRE_CHECKS

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        phase.run()

        # After running, current_phase should be updated
        assert record.current_phase == CommissioningPhase.COLD_LANDING

    def test_failed_phase_status(self):
        """Test that failed phases update status correctly."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(record=record, operator="TestOperator")
        phase = TestPhase(context)

        # Make step2 fail
        phase.step_results["step2"] = PhaseStepResult(
            result=PhaseResult.FAILED, message="Hardware fault"
        )

        success = phase.run()

        assert success is False
        assert (
            record.phase_status[CommissioningPhase.COLD_LANDING]
            == PhaseStatus.FAILED
        )


class TestDryRunMode:
    """Tests for dry-run mode."""

    def test_dry_run_flag_accessible(self):
        """Test that dry_run flag is accessible in phase."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(
            record=record, operator="TestOperator", dry_run=True
        )

        phase = TestPhase(context)

        assert phase.context.dry_run is True

    def test_dry_run_normal_execution_flow(self):
        """Test that dry-run doesn't affect execution flow."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        context = PhaseContext(
            record=record, operator="TestOperator", dry_run=True
        )

        phase = TestPhase(context)

        success = phase.run()

        # Execution should succeed normally
        assert success is True
        assert len(phase.steps_executed) == 3
        assert phase.finalize_called is True

        # Checkpoints should still be created
        assert len(record.phase_history) > 0
