"""Base display interface for commissioning phases."""

from typing import Optional

from pydm import Display

from sc_linac_physics.applications.rf_commissioning import CommissioningRecord
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)


class PhaseDisplayBase(Display):
    """Common interface for phase displays used in multi-phase container."""

    def __init__(
        self, parent=None, session: Optional[CommissioningSession] = None
    ):
        super().__init__(parent)
        self.session = session

    def set_session(self, session: CommissioningSession) -> None:
        """Set shared session after construction."""
        self.session = session

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Update display when a record is loaded."""
        raise NotImplementedError

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Refresh display when active record changes."""
        return

    def on_phase_completed(self) -> None:
        """Hook for phase completion notifications."""
        return
