"""Session manager for multi-phase commissioning workflow.

Coordinates database access and record management across all commissioning phases.
"""

import logging
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningDatabase,
    CommissioningPhase,
    PhaseStatus,
)
from sc_linac_physics.applications.rf_commissioning.models.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.services.workflow_service import (
    PhaseStartResult,
    WorkflowService,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhaseCommandHandle:
    """Tracks normalized lifecycle identity for one phase command."""

    phase: CommissioningPhase
    phase_instance_id: int | None


def get_default_db_path() -> str:
    """Get the default database path based on operating system.

    Returns:
        str: Full path to the database file
            - Production (Rocky Linux): /home/physics/srf/commissioning.db
            - macOS: ~/databases/commissioning.db
    """
    # Detect OS - Rocky Linux will report as 'Linux'
    if platform.system() == "Linux":
        # Production environment
        db_dir = Path("/home/physics/srf")
    else:
        # Development (macOS) or other OS
        db_dir = Path.home() / "databases"

    # Create directory if it doesn't exist
    db_dir.mkdir(parents=True, exist_ok=True)

    return str(db_dir / "commissioning.db")


class CommissioningSession:
    """Manages database and active record across all commissioning phases.

    This singleton-like class ensures:
    - Single database instance shared across all phase controllers
    - Active record persistence across phase transitions
    - Consistent record state management

    Usage:
        # In main application initialization (uses OS-specific default path)
        session = CommissioningSession()

        # Or specify a custom path
        session = CommissioningSession(db_path="/custom/path/commissioning.db")

        # Pass session to each phase controller
        piezo_controller = PiezoPreRFController(view, session)
        cold_landing_controller = ColdLandingController(view, session)
        # ... etc.

        # Controllers use session methods:
        record, record_id, created = session.start_new_record(
            cryomodule="02", cavity_number="3"
        )
        record = session.get_active_record()
        session.save_active_record()
        session.load_record(record_id)
    """

    def __init__(self, db_path: str | None = None):
        """Initialize session with database.

        Args:
            db_path: Path to SQLite database file. If None, uses OS-specific default:
                - Production (Rocky Linux): /home/physics/srf/commissioning.db
                - macOS: ~/databases/commissioning.db
        """
        if db_path is None:
            db_path = get_default_db_path()

        self.db = CommissioningDatabase(db_path)
        self.db.initialize()
        self.workflow = WorkflowService(self.db)

        self._active_record: CommissioningRecord | None = None
        self._active_record_id: int | None = None
        self._active_record_version: int | None = None

    def start_active_phase_instance(
        self,
        phase: CommissioningPhase,
        operator: str,
    ) -> PhaseStartResult | None:
        """Start a normalized phase-instance attempt for the active record."""
        if self._active_record is None or self._active_record_id is None:
            return None

        try:
            return self.workflow.start_phase_for_record(
                record_id=self._active_record_id,
                record=self._active_record,
                phase=phase,
                operator=operator,
            )
        except Exception as e:
            logger.exception("Failed to start active phase instance: %s", e)
            return None

    def complete_active_phase_instance(
        self,
        *,
        phase_instance_id: int,
        phase: CommissioningPhase,
        artifact_payload: dict | None = None,
        artifact_type: str = "phase_result",
    ) -> bool:
        """Complete a normalized phase instance for the active record."""
        if self._active_record_id is None:
            return False

        try:
            self.workflow.complete_phase_instance(
                record_id=self._active_record_id,
                phase_instance_id=phase_instance_id,
                phase=phase,
                artifact_payload=artifact_payload,
                artifact_type=artifact_type,
            )

            # Keep active legacy record projection in sync during migration.
            if self._active_record is not None:
                if (
                    self._active_record.current_phase == phase
                    and self._active_record.get_phase_status(phase)
                    != PhaseStatus.COMPLETE
                ):
                    self._active_record.set_phase_status(
                        phase, PhaseStatus.COMPLETE
                    )
                    self._active_record.advance_to_next_phase()

            return True
        except Exception as e:
            logger.exception("Failed to complete active phase instance: %s", e)
            return False

    def fail_active_phase_instance(
        self,
        *,
        phase_instance_id: int,
        phase: CommissioningPhase,
        error_message: str,
        artifact_payload: dict | None = None,
        artifact_type: str = "phase_failure_snapshot",
    ) -> bool:
        """Fail a normalized phase instance for the active record."""
        if self._active_record_id is None:
            return False

        try:
            self.workflow.fail_phase_instance(
                record_id=self._active_record_id,
                phase_instance_id=phase_instance_id,
                phase=phase,
                error_message=error_message,
                artifact_payload=artifact_payload,
                artifact_type=artifact_type,
            )

            # Keep active legacy record projection in sync during migration.
            if self._active_record is not None:
                self._active_record.set_phase_status(phase, PhaseStatus.FAILED)
                self._active_record.overall_status = "failed"
                self._active_record.end_time = datetime.now()

            return True
        except Exception as e:
            logger.exception("Failed to fail active phase instance: %s", e)
            return False

    def get_active_workflow_run_v2(self) -> dict | None:
        """Return normalized workflow run metadata for the active record."""
        if self._active_record_id is None:
            return None
        return self.db.get_workflow_run_v2(self._active_record_id)

    def get_active_phase_instances_v2(self) -> list[dict]:
        """Return normalized phase instances for the active record."""
        if self._active_record_id is None:
            return []
        return self.db.get_phase_instances_v2(self._active_record_id)

    def _base_phase_status_projection(
        self,
    ) -> dict[CommissioningPhase, PhaseStatus]:
        """Build phase status projection from the active record snapshot."""
        assert self._active_record is not None
        return {
            phase: self._active_record.get_phase_status(phase)
            for phase in CommissioningPhase.get_phase_order()
        }

    def _project_current_phase_from_run(
        self,
        run: dict | None,
    ) -> CommissioningPhase:
        """Resolve current phase, preferring normalized run data."""
        assert self._active_record is not None
        if not run:
            return self._active_record.current_phase

        try:
            return CommissioningPhase(run["current_phase"])
        except ValueError:
            return self._active_record.current_phase

    def _apply_instance_statuses(
        self,
        phase_status: dict[CommissioningPhase, PhaseStatus],
        instances: list[dict],
    ) -> None:
        """Overlay latest normalized phase-instance statuses onto projection."""
        if not instances:
            return

        latest_by_phase: dict[CommissioningPhase, dict] = {}
        for instance in instances:
            try:
                phase = CommissioningPhase(instance["phase"])
            except ValueError:
                continue

            prev = latest_by_phase.get(phase)
            if prev is None or int(instance["attempt_number"]) >= int(
                prev["attempt_number"]
            ):
                latest_by_phase[phase] = instance

        status_map = {
            "not_started": PhaseStatus.NOT_STARTED,
            "in_progress": PhaseStatus.IN_PROGRESS,
            "complete": PhaseStatus.COMPLETE,
            "failed": PhaseStatus.FAILED,
            "skipped": PhaseStatus.SKIPPED,
        }
        for phase, instance in latest_by_phase.items():
            phase_status[phase] = status_map.get(
                instance["status"], PhaseStatus.NOT_STARTED
            )

    def get_active_phase_projection(self) -> dict | None:
        """Return phase projection used by UI state components.

        During migration this prefers normalized v2 data when available and
        falls back to the active legacy record representation otherwise.
        """
        if self._active_record is None:
            return None

        phase_status = self._base_phase_status_projection()

        run = self.get_active_workflow_run_v2()
        instances = self.get_active_phase_instances_v2()
        current_phase = self._project_current_phase_from_run(run)
        self._apply_instance_statuses(phase_status, instances)

        return {
            "current_phase": current_phase,
            "phase_status": phase_status,
            "run": run,
            "instances": instances,
        }

    def begin_phase_command(
        self,
        *,
        phase: CommissioningPhase,
        operator: str,
        run_mode: str = "individual",
        run_intent: str = "commissioning",
        notes: str | None = None,
    ) -> PhaseCommandHandle | None:
        """Start a phase command and return linked lifecycle IDs.

        This is the preferred API for phase controllers: it encapsulates
        normalized v2 phase-instance startup.
        """
        if self._active_record_id is None:
            return None

        phase_start = self.start_active_phase_instance(
            phase=phase,
            operator=operator,
        )
        phase_instance_id = (
            phase_start.phase_instance_id if phase_start is not None else None
        )

        if phase_instance_id is None:
            return None

        return PhaseCommandHandle(
            phase=phase,
            phase_instance_id=phase_instance_id,
        )

    def complete_phase_command(
        self,
        *,
        handle: PhaseCommandHandle,
        phase_data_snapshot: dict | None = None,
        artifact_payload: dict | None = None,
        artifact_type: str = "phase_result",
    ) -> bool:
        """Complete a phase command using normalized v2 lifecycle tracking."""
        success = True

        if handle.phase_instance_id is not None:
            success = (
                self.complete_active_phase_instance(
                    phase_instance_id=handle.phase_instance_id,
                    phase=handle.phase,
                    artifact_payload=artifact_payload,
                    artifact_type=artifact_type,
                )
                and success
            )

        # Snapshot is retained for forward compatibility with callers.  The
        # normalized v2 lifecycle persists the artifact payload.
        _ = phase_data_snapshot

        return success

    def fail_phase_command(
        self,
        *,
        handle: PhaseCommandHandle,
        error_message: str,
        phase_data_snapshot: dict | None = None,
        artifact_payload: dict | None = None,
        artifact_type: str = "phase_failure_snapshot",
    ) -> bool:
        """Fail a phase command using normalized v2 lifecycle tracking."""
        success = True

        if handle.phase_instance_id is not None:
            success = (
                self.fail_active_phase_instance(
                    phase_instance_id=handle.phase_instance_id,
                    phase=handle.phase,
                    error_message=error_message,
                    artifact_payload=artifact_payload,
                    artifact_type=artifact_type,
                )
                and success
            )

        # Snapshot is retained for forward compatibility with callers.  The
        # normalized v2 lifecycle persists the artifact payload.
        _ = phase_data_snapshot

        return success

    @property
    def database(self) -> CommissioningDatabase:
        """Get the shared database instance."""
        return self.db

    def start_new_record(
        self,
        cryomodule: str,
        cavity_number: str | int,
        linac: int | None = None,
    ) -> tuple[CommissioningRecord, int, bool]:
        """Create a new commissioning record and save to database.

        Args:
            cryomodule: Cryomodule identifier (e.g., "02", "H1")
            cavity_number: Cavity number (e.g., "1", "3")
            linac: Linac index (0-4). If None, derived from cryomodule.

        Returns:
            Tuple of (record, record_id, created_new)
        """
        from sc_linac_physics.utils.sc_linac.linac_utils import (
            get_linac_for_cryomodule,
        )

        if linac is None:
            linac_name = get_linac_for_cryomodule(cryomodule)
            if not linac_name:
                raise ValueError(
                    f"Cannot determine linac for cryomodule '{cryomodule}'"
                )
            try:
                linac = int(linac_name[1])
            except (IndexError, ValueError) as exc:
                raise ValueError(
                    f"Cannot parse linac index from '{linac_name}'"
                ) from exc

        existing_id = self.db.get_record_id_for_cavity(
            linac, cryomodule, cavity_number
        )
        if existing_id is not None:
            record = self.load_record(existing_id)
            if record:
                return record, existing_id, False

        self._active_record = CommissioningRecord(
            linac=linac,
            cryomodule=cryomodule,
            cavity_number=int(cavity_number),
        )

        self._active_record_id = self.db.save_record(self._active_record)
        self._active_record_version = 1  # New records start at version 1
        return self._active_record, self._active_record_id, True

    def get_active_record(self) -> CommissioningRecord | None:
        """Get the currently active commissioning record.

        Returns:
            Active record or None if no record is active
        """
        return self._active_record

    def get_active_record_id(self) -> int | None:
        """Get the database ID of the active record.

        Returns:
            Active record ID or None
        """
        return self._active_record_id

    def has_active_record(self) -> bool:
        """Check if there's an active record.

        Returns:
            True if an active record exists
        """
        return self._active_record is not None

    def get_operators(self) -> list[str]:
        """Get approved operator list."""
        return self.db.get_operators()

    def add_operator(self, name: str) -> bool:
        """Add operator to approved list."""
        return self.db.add_operator(name)

    def save_active_record(self) -> bool:
        """Save the active record to database with optimistic locking.

        Returns:
            True if saved successfully, False otherwise

        Raises:
            RecordConflictError: If another user modified the record since it was loaded
        """
        if not self._active_record or self._active_record_id is None:
            return False

        try:
            self.db.save_record(
                self._active_record,
                self._active_record_id,
                expected_version=self._active_record_version,
            )
            # Increment local version on successful save
            if self._active_record_version is not None:
                self._active_record_version += 1
            return True
        except RecordConflictError:
            # Re-raise conflict errors for UI to handle
            raise
        except Exception as e:
            logger.exception("Failed to save active record: %s", e)
            return False

    def load_record(self, record_id: int) -> CommissioningRecord | None:
        """Load a record from database and set as active.

        Args:
            record_id: Database ID of record to load

        Returns:
            Loaded record or None if not found
        """
        result = self.db.load_record_with_version(record_id)

        if result:
            record, version = result
            self._active_record = record
            self._active_record_id = record_id
            self._active_record_version = version
            return record

        return None

    def clear_active_record(self) -> None:
        """Clear the active record (e.g., when starting fresh)."""
        self._active_record = None
        self._active_record_id = None
        self._active_record_version = None

    def can_run_phase(self, phase: CommissioningPhase) -> tuple[bool, str]:
        """Check if a phase can be run on the active record.

        Args:
            phase: The phase to check

        Returns:
            Tuple of (can_run, reason)
        """
        if not self._active_record:
            return False, "No active commissioning record"

        # Check phase ordering
        can_start, reason = self._active_record.can_start_phase(phase)
        return can_start, reason

    def get_active_phase(self) -> CommissioningPhase | None:
        """Get the current phase of the active record.

        Returns:
            Current phase or None if no active record
        """
        if not self._active_record:
            return None
        return self._active_record.current_phase

    def get_phase_status(self, phase: CommissioningPhase) -> PhaseStatus | None:
        """Get the status of a specific phase.

        Args:
            phase: The phase to check

        Returns:
            Phase status or None if no active record
        """
        if not self._active_record:
            return None
        return self._active_record.get_phase_status(phase)

    def advance_to_next_phase(self) -> tuple[bool, str]:
        """Advance the active record to the next phase.

        Returns:
            Tuple of (success, message)
        """
        if not self._active_record:
            return False, "No active record"

        success, message = self._active_record.advance_to_next_phase()

        if success:
            self.save_active_record()

        return success, message

    def get_all_records_summary(self) -> list[dict]:
        """Get summary of all commissioning records.

        Returns:
            List of record dictionaries
        """
        return self.db.get_all_records()

    def get_active_sessions(self) -> list[CommissioningRecord]:
        """Get all in-progress commissioning sessions.

        Returns:
            List of incomplete commissioning records
        """
        return self.db.get_active_records()

    def get_session_summary(self) -> dict:
        """Get summary of current session state.

        Returns:
            Dictionary with session information
        """
        cavity_name = None
        if self._active_record:
            cavity_name = (
                f"L{self._active_record.linac}B_CM{self._active_record.cryomodule}"
                f"_CAV{self._active_record.cavity_number}"
            )

        return {
            "has_active_record": self.has_active_record(),
            "active_record_id": self._active_record_id,
            "linac": (
                self._active_record.linac if self._active_record else None
            ),
            "cryomodule": (
                self._active_record.cryomodule if self._active_record else None
            ),
            "cavity_number": (
                self._active_record.cavity_number
                if self._active_record
                else None
            ),
            "cavity_name": cavity_name,  # Formatted for display
            "current_phase": (
                self._active_record.current_phase.value
                if self._active_record
                else None
            ),
            "is_complete": (
                self._active_record.is_complete
                if self._active_record
                else False
            ),
        }

    def add_measurement_to_history(
        self,
        phase: CommissioningPhase,
        measurement_data,
        operator: str | None = None,
        notes: str | None = None,
        phase_instance_id: int | None = None,
    ) -> bool:
        """Add a measurement to history for the active record.

        This is the recommended way to record measurements as multiple users
        can add measurements concurrently without conflicts.

        Args:
            phase: Which phase the measurement is for
            measurement_data: The phase-specific data object
            operator: Who took the measurement
            notes: Optional notes

        Returns:
            True if added successfully, False if no active record

        Example:
            >>> # Take a piezo measurement and record it
            >>> piezo_data = PiezoPreRFCheck(...)
            >>> session.add_measurement_to_history(
            ...     CommissioningPhase.PIEZO_PRE_RF,
            ...     piezo_data,
            ...     operator="John Doe"
            ... )
            >>>
            >>> # Optionally also update the main record's current measurement
            >>> record = session.get_active_record()
            >>> record.piezo_pre_rf = piezo_data
            >>> session.save_active_record()
        """
        if not self._active_record or self._active_record_id is None:
            return False

        try:
            self.db.add_measurement_history(
                self._active_record_id,
                phase,
                measurement_data,
                operator,
                notes,
                phase_instance_id,
            )
            return True
        except Exception as e:
            logger.exception("Failed to add measurement to history: %s", e)
            return False

    def get_measurement_history(
        self, phase: CommissioningPhase | None = None
    ) -> list[dict]:
        """Get measurement history for the active record.

        Args:
            phase: Optional - filter to specific phase

        Returns:
            List of measurement history entries
        """
        if self._active_record_id is None:
            return []

        return self.db.get_measurement_history(self._active_record_id, phase)

    def get_measurement_notes(
        self, phase: CommissioningPhase | None = None
    ) -> list[dict]:
        """Get flattened measurement notes for the active record."""
        if self._active_record_id is None:
            return []

        return self.db.get_measurement_notes(self._active_record_id, phase)

    def append_measurement_note(
        self,
        entry_id: int,
        operator: str | None,
        note: str,
    ) -> bool:
        """Append a note to a measurement history entry."""
        try:
            return self.db.append_measurement_note(entry_id, operator, note)
        except Exception as e:
            logger.exception("Failed to append measurement note: %s", e)
            return False

    def update_measurement_note(
        self,
        entry_id: int,
        note_index: int,
        operator: str | None,
        note: str,
    ) -> bool:
        """Update a specific measurement note by index."""
        try:
            return self.db.update_measurement_note(
                entry_id, note_index, operator, note
            )
        except Exception as e:
            logger.exception("Failed to update measurement note: %s", e)
            return False

    # ==================== GENERAL NOTES METHODS ====================

    def get_general_notes(self) -> list[dict]:
        """Get all general notes for the active record."""
        if self._active_record_id is None:
            return []
        return self.db.get_general_notes(self._active_record_id)

    def append_general_note(
        self,
        operator: str | None,
        note: str,
    ) -> bool:
        """Append a general note to the active commissioning record."""
        if self._active_record_id is None:
            return False
        try:
            success = self.db.append_general_note(
                self._active_record_id,
                operator,
                note,
                expected_version=self._active_record_version,
            )
            if success and self._active_record_version is not None:
                self._active_record_version += 1
            return success
        except RecordConflictError:
            # Re-raise conflict errors for UI to handle
            raise
        except Exception as e:
            logger.exception("Failed to append general note: %s", e)
            return False

    def update_general_note(
        self,
        note_index: int,
        operator: str | None,
        note: str,
    ) -> bool:
        """Update a specific general note by index."""
        if self._active_record_id is None:
            return False
        try:
            success = self.db.update_general_note(
                self._active_record_id,
                note_index,
                operator,
                note,
                expected_version=self._active_record_version,
            )
            if success and self._active_record_version is not None:
                self._active_record_version += 1
            return success
        except RecordConflictError:
            # Re-raise conflict errors for UI to handle
            raise
        except Exception as e:
            logger.exception("Failed to update general note: %s", e)
            return False
