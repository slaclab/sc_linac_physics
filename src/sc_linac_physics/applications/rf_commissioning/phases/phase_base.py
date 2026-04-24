"""Base class and interfaces for commissioning phase execution.

This module provides the abstract base class that all commissioning phases
inherit from, defining the common interface for phase execution, validation,
and state management.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    CommissioningPhase,
    PHASE_REGISTRY,
    PhaseCheckpoint,
    PhaseStatus,
)


class PhaseResult(Enum):
    """Result of a phase execution step."""

    SUCCESS = "success"
    RETRY = "retry"
    FAILED = "failed"
    SKIP = "skip"


@dataclass
class PhaseContext:
    """Context information available to all phases during execution.

    Attributes:
        record: The commissioning record being worked on
        operator: Name of the operator running the commissioning
        dry_run: If True, don't actually execute EPICS commands
        parameters: Phase-specific configuration parameters
        abort_requested: Set to True to request graceful abort
    """

    record: CommissioningRecord
    operator: str
    dry_run: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    abort_requested: bool = False
    progress_callback: Callable[[str, int], None] | None = None
    phase_instance_id: int | None = None
    run_intent: str = "commissioning"

    def request_abort(self) -> None:
        """Request graceful abort of current phase."""
        self.abort_requested = True

    def is_abort_requested(self) -> bool:
        """Check if abort has been requested."""
        return self.abort_requested


@dataclass
class PhaseStepResult:
    """Result from executing a single phase step.

    Attributes:
        result: The outcome of the step
        message: Human-readable description of what happened
        data: Optional data to store (will be added to checkpoint)
        retry_delay_seconds: If RETRY, how long to wait before retrying
    """

    result: PhaseResult
    message: str
    data: dict[str, Any] | None = None
    retry_delay_seconds: float = 5.0


class PhaseExecutionError(Exception):
    """Raised when a phase encounters an unrecoverable error."""

    pass


class PhaseBase(ABC):
    """Abstract base class for all commissioning phases.

    Each commissioning phase (cold landing, SSA characterization, etc.)
    inherits from this class and implements the required methods.

    The base class provides:
    - Common phase lifecycle management (start, execute, complete, abort)
    - Checkpoint creation and error handling
    - Retry logic and timeout handling
    - Integration with CommissioningRecord for data persistence

    Subclasses must implement:
    - phase_type: Property returning the CommissioningPhase enum
    - validate_prerequisites: Check if phase can run
    - get_phase_steps: Return list of steps to execute
    - execute_step: Execute a single step
    - finalize_phase: Clean up and save final data
    """

    def __init__(self, context: PhaseContext):
        """Initialize phase with execution context.

        Args:
            context: The execution context for this phase
        """
        self.context = context
        self._current_step_index: int = 0
        self._max_retries_per_step: int = 3
        self._retry_count: int = 0

    @property
    @abstractmethod
    def phase_type(self) -> CommissioningPhase:
        """Return the phase type this class implements."""
        pass

    @property
    def phase_name(self) -> str:
        """Human-readable phase name."""
        return self.phase_type.value.replace("_", " ").title()

    @abstractmethod
    def validate_prerequisites(self) -> tuple[bool, str]:
        """Validate that prerequisites for this phase are met.

        Returns:
            Tuple of (is_valid, message)
            - is_valid: True if phase can proceed
            - message: Description of validation result
        """
        pass

    @abstractmethod
    def get_phase_steps(self) -> list[str]:
        """Get list of step names for this phase.

        Returns:
            List of step names in execution order
        """
        pass

    @abstractmethod
    def execute_step(self, step_name: str) -> PhaseStepResult:
        """Execute a single step of the phase.

        Args:
            step_name: Name of the step to execute

        Returns:
            Result of the step execution
        """
        pass

    @abstractmethod
    def finalize_phase(self) -> None:
        """Finalize phase data and update the commissioning record.

        This is called after all steps complete successfully.
        Subclasses should update the appropriate phase data in
        self.context.record.
        """
        pass

    def run(self) -> bool:
        """Execute the complete phase.

        This is the main entry point for phase execution. It:
        1. Validates phase ordering (previous phase complete)
        2. Validates phase-specific prerequisites
        3. Marks phase as started
        4. Executes each step with retry logic
        5. Handles errors and creates checkpoints
        6. Finalizes phase on success OR failure

        Returns:
            True if phase completed successfully, False otherwise
        """
        # First check phase ordering
        can_start, ordering_message = self.context.record.can_start_phase(
            self.phase_type
        )
        if not can_start:
            self._create_checkpoint(
                step_name="phase_ordering_check",
                success=False,
                notes=f"Phase ordering violation: {ordering_message}",
            )
            return False

        # Then validate phase-specific prerequisites
        is_valid, message = self.validate_prerequisites()
        if not is_valid:
            self._create_checkpoint(
                step_name="prerequisite_check",
                success=False,
                notes=f"Prerequisites not met: {message}",
            )
            return False

        # Mark phase as started
        self._mark_phase_started()

        try:
            # Execute each step
            steps = self.get_phase_steps()
            for i, step_name in enumerate(steps):
                self._current_step_index = i
                self._retry_count = 0

                # Check for abort request
                if self.context.is_abort_requested():
                    self._handle_abort(step_name)
                    return False

                # Execute step with retry logic
                success = self._execute_step_with_retry(step_name)
                if not success:
                    return False

            # All steps completed successfully
            try:
                self.finalize_phase()
            except Exception as e:
                self._handle_exception(e)
                return False

            self._mark_phase_completed()
            return True

        except Exception as e:
            self._handle_exception(e)
            return False

    def _execute_step_with_retry(self, step_name: str) -> bool:
        """Execute a step with retry logic.

        Args:
            step_name: Name of the step to execute

        Returns:
            True if step succeeded, False if it failed after retries
        """

        # Notify progress callback
        if self.context.progress_callback:
            steps = self.get_phase_steps()
            current_index = steps.index(step_name) if step_name in steps else 0
            progress = int((current_index / len(steps)) * 100)
            self.context.progress_callback(step_name, progress)

        while self._retry_count < self._max_retries_per_step:
            try:
                result = self.execute_step(step_name)

                if result.result == PhaseResult.SUCCESS:
                    self._create_checkpoint(
                        step_name=step_name,
                        success=True,
                        notes=result.message,
                        measurements=result.data,
                    )
                    return True

                elif result.result == PhaseResult.SKIP:
                    self._create_checkpoint(
                        step_name=step_name,
                        success=True,
                        notes=f"Skipped: {result.message}",
                        measurements=result.data,
                    )
                    return True

                elif result.result == PhaseResult.RETRY:
                    self._retry_count += 1
                    if self._retry_count < self._max_retries_per_step:
                        self._create_checkpoint(
                            step_name=step_name,
                            success=False,
                            notes=f"Retry {self._retry_count}/{self._max_retries_per_step}: {result.message}",
                            measurements=result.data,
                        )
                        # Wait before retry (could use result.retry_delay_seconds)
                        continue
                    else:
                        self.context.record.set_phase_status(
                            self.phase_type, PhaseStatus.FAILED
                        )
                        self._create_checkpoint(
                            step_name=step_name,
                            success=False,
                            notes=f"Failed after {self._max_retries_per_step} retries: {result.message}",
                            measurements=result.data,
                        )
                        return False

                else:  # PhaseResult.FAILED
                    self.context.record.set_phase_status(
                        self.phase_type, PhaseStatus.FAILED
                    )
                    self._create_checkpoint(
                        step_name=step_name,
                        success=False,
                        notes=f"Failed: {result.message}",
                        measurements=result.data,
                        error_message=result.message,
                    )
                    return False

            except Exception as e:
                self._retry_count += 1
                if self._retry_count < self._max_retries_per_step:
                    self._create_checkpoint(
                        step_name=step_name,
                        success=False,
                        notes=f"Exception on retry {self._retry_count}: {str(e)}",
                        error_message=str(e),
                    )
                    continue
                else:
                    raise

        return False

    def _create_checkpoint(
        self,
        step_name: str,
        success: bool,
        notes: str = "",
        measurements: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Create a checkpoint in the phase history.

        Args:
            step_name: Name of the step
            success: Whether the step succeeded
            notes: Human-readable notes
            measurements: Optional measurement data
            error_message: Optional error message
        """
        checkpoint_measurements = dict(measurements or {})
        if self.context.phase_instance_id is not None:
            checkpoint_measurements.setdefault(
                "phase_instance_id", self.context.phase_instance_id
            )

        checkpoint = PhaseCheckpoint(
            phase=self.phase_type,
            timestamp=datetime.now(),
            operator=self.context.operator,
            step_name=step_name,
            success=success,
            notes=notes,
            measurements=checkpoint_measurements,
            error_message=error_message,
        )
        self.context.record.phase_history.append(checkpoint)

    def _mark_phase_started(self) -> None:
        """Mark phase as started in the record."""
        self.context.record.set_phase_status(
            self.phase_type, PhaseStatus.IN_PROGRESS
        )
        self.context.record.current_phase = self.phase_type
        self._create_checkpoint(
            step_name="phase_start",
            success=True,
            notes=f"Started {self.phase_name}",
        )

    def _mark_phase_completed(self) -> None:
        """Mark phase as completed in the record."""
        self.context.record.set_phase_status(
            self.phase_type, PhaseStatus.COMPLETE
        )
        phase_snapshot = self._get_phase_data_snapshot()
        self._create_checkpoint(
            step_name="phase_complete",
            success=True,
            notes=f"Completed {self.phase_name}",
            measurements=(
                {"phase_data": phase_snapshot} if phase_snapshot else None
            ),
        )

    def _get_phase_data_snapshot(self) -> dict[str, Any] | None:
        """Return serialized phase dataclass data for the current phase.

        This is used to persist per-run phase results into phase history
        checkpoints so reruns retain a historical snapshot.
        """
        registration = PHASE_REGISTRY.get(self.phase_type)
        if not registration or not registration.record_attr:
            return None

        phase_data = getattr(
            self.context.record, registration.record_attr, None
        )
        if phase_data is None or not hasattr(phase_data, "to_dict"):
            return None

        return phase_data.to_dict()

    def _handle_abort(self, current_step: str) -> None:
        """Handle abort request.

        Args:
            current_step: The step that was running when abort was requested
        """
        self.context.record.set_phase_status(
            self.phase_type, PhaseStatus.FAILED
        )
        self._create_checkpoint(
            step_name=current_step,
            success=False,
            notes="Phase aborted by user request",
            error_message="User requested abort",
        )

    def _handle_exception(self, exception: Exception) -> None:
        """Handle unexpected exception during phase execution.

        Args:
            exception: The exception that was raised
        """

        self.context.record.set_phase_status(
            self.phase_type, PhaseStatus.FAILED
        )
        self._create_checkpoint(
            step_name=f"step_{self._current_step_index}",
            success=False,
            notes=f"Unhandled exception: {type(exception).__name__}",
            error_message=str(exception),
        )
