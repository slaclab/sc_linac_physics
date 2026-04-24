"""Magnet checkout display for use as a phase tab in the commissioning UI."""

from pydm.display import PyDMDisplay

from sc_linac_physics.applications.rf_commissioning.models import (
    CommissioningDatabase,
    CryomoduleCheckoutRecord,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.ui.cm_checkout_widget import (
    MagnetCheckoutWidget,
)


class CMCheckoutDisplay(PyDMDisplay):
    """Display for CM magnet checkout as optional first phase tab.

    Shows the MagnetCheckoutWidget and integrates with the cavity
    commissioning workflow. Can be auto-skipped if magnet is already complete.
    """

    def __init__(self, parent=None):
        """Initialize CM checkout display."""
        super().__init__(parent)
        self.db: CommissioningDatabase | None = None
        self.record: CommissioningRecord | None = None
        self.cm_record: CryomoduleCheckoutRecord | None = None
        self.cm_widget: MagnetCheckoutWidget | None = None

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        """Called when a new cavity record is loaded.

        Args:
            record: The CommissioningRecord that was loaded
            record_id: Database ID of the record
        """
        self.record = record

        # Load or create CM record
        if self.db and self.record:
            self.cm_record = self.db.get_cryomodule_record(
                self.record.linac, self.record.cryomodule
            )

            # Create or update widget if needed
            if not self.cm_widget:
                self.cm_widget = MagnetCheckoutWidget(
                    self.record.linac, self.record.cryomodule, self.db
                )
                self.setCentralWidget(self.cm_widget)

            self.cm_widget.load_record()

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        """Refresh display from cavity record (called on reload).

        Args:
            record: The CommissioningRecord to display
        """
        self.record = record
        if self.cm_widget:
            self.cm_widget.load_record()

    def on_phase_completed(self) -> None:
        """Called when this phase is marked complete.

        Auto-advances cavities past magnet checkout if already complete.
        """
        if self.cm_record and self.cm_record.magnet_checkout:
            # Magnet checkout has been done, signal completion
            pass


def is_magnet_checkout_complete(
    db: CommissioningDatabase, linac: str, cryomodule: str
) -> bool:
    """Check if magnet checkout is complete for a CM.

    Args:
        db: CommissioningDatabase instance
        linac: Linac name
        cryomodule: CM number

    Returns:
        True if magnet checkout is done (passed or failed), False otherwise
    """
    cm_record = db.get_cryomodule_record(linac, cryomodule)
    if not cm_record or not cm_record.magnet_checkout:
        return False
    return True
