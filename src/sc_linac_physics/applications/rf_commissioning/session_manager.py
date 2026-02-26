"""Session manager for multi-phase commissioning workflow.

Coordinates database access and record management across all commissioning phases.
"""

from typing import Optional

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningDatabase,
    CommissioningPhase,
    PhaseStatus,
)


class CommissioningSession:
    """Manages database and active record across all commissioning phases.

    This singleton-like class ensures:
    - Single database instance shared across all phase controllers
    - Active record persistence across phase transitions
    - Consistent record state management

    Usage:
        # In main application initialization
        session = CommissioningSession(db_path="commissioning.db")

        # Pass session to each phase controller
        piezo_controller = PiezoPreRFController(view, session)
        cold_landing_controller = ColdLandingController(view, session)
        # ... etc.

        # Controllers use session methods:
        session.start_new_record(cavity_name, cryomodule)
        record = session.get_active_record()
        session.save_active_record()
        session.load_record(record_id)
    """

    def __init__(self, db_path: str = "commissioning.db"):
        """Initialize session with database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db = CommissioningDatabase(db_path)
        self.db.initialize()

        self._active_record: Optional[CommissioningRecord] = None
        self._active_record_id: Optional[int] = None

    @property
    def database(self) -> CommissioningDatabase:
        """Get the shared database instance."""
        return self.db

    def start_new_record(
        self, cavity_name: str, cryomodule: str
    ) -> tuple[CommissioningRecord, int]:
        """Create a new commissioning record and save to database.

        Args:
            cavity_name: Name of the cavity (e.g., "L1B_CM02_CAV3")
            cryomodule: Cryomodule identifier (e.g., "02")

        Returns:
            Tuple of (new_record, record_id)
        """
        self._active_record = CommissioningRecord(
            cavity_name=cavity_name,
            cryomodule=cryomodule,
        )

        self._active_record_id = self.db.save_record(self._active_record)
        return self._active_record, self._active_record_id

    def get_active_record(self) -> Optional[CommissioningRecord]:
        """Get the currently active commissioning record.

        Returns:
            Active record or None if no record is active
        """
        return self._active_record

    def get_active_record_id(self) -> Optional[int]:
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

    def save_active_record(self) -> bool:
        """Save the active record to database.

        Returns:
            True if saved successfully, False otherwise
        """
        if not self._active_record or self._active_record_id is None:
            return False

        try:
            self.db.save_record(self._active_record, self._active_record_id)
            return True
        except Exception as e:
            print(f"Failed to save active record: {e}")
            return False

    def load_record(self, record_id: int) -> Optional[CommissioningRecord]:
        """Load a record from database and set as active.

        Args:
            record_id: Database ID of record to load

        Returns:
            Loaded record or None if not found
        """
        record = self.db.load_record(record_id)

        if record:
            self._active_record = record
            self._active_record_id = record_id

        return record

    def clear_active_record(self) -> None:
        """Clear the active record (e.g., when starting fresh)."""
        self._active_record = None
        self._active_record_id = None

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

    def get_active_phase(self) -> Optional[CommissioningPhase]:
        """Get the current phase of the active record.

        Returns:
            Current phase or None if no active record
        """
        if not self._active_record:
            return None
        return self._active_record.current_phase

    def get_phase_status(
        self, phase: CommissioningPhase
    ) -> Optional[PhaseStatus]:
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
        return {
            "has_active_record": self.has_active_record(),
            "active_record_id": self._active_record_id,
            "cavity_name": (
                self._active_record.cavity_name if self._active_record else None
            ),
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
