"""Base display interface for commissioning phases."""

from datetime import datetime

from PyQt5.QtWidgets import QMessageBox
from pydm import Display

from sc_linac_physics.applications.rf_commissioning import CommissioningRecord
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)


class PhaseDisplayBase(Display):
    """Common interface for phase displays used in multi-phase container."""

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
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

    def _notify_parent_of_record_update(
        self, record: CommissioningRecord, message: str = "Record updated"
    ) -> None:
        """Update parent container's UI after record change.

        Walks up parent hierarchy to find MultiPhaseCommissioningDisplay
        and calls its standard UI update sequence.

        Args:
            record: The updated record to display
            message: Status message for sync indicator
        """
        parent = self.parent()
        while parent:
            # Check if this is the multi-phase container
            if parent.__class__.__name__ == "MultiPhaseCommissioningDisplay":
                # Batch UI updates to avoid repeated redraws
                if hasattr(parent, "update_progress_indicator"):
                    parent.update_progress_indicator(record)
                if hasattr(parent, "_update_tab_states"):
                    parent._update_tab_states()
                if hasattr(parent, "_load_notes"):
                    parent._load_notes()
                if hasattr(parent, "_update_sync_status"):
                    parent._update_sync_status(True, message)
                break
            parent = parent.parent()

    # =============================================================================
    # Common Helper Methods
    # =============================================================================

    def get_current_operator(self) -> str | None:
        """Get the current operator from parent container."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "operator_combo"):
                operator = parent.operator_combo.currentData()
                if operator and operator != "__add__":
                    return operator
            parent = parent.parent()
        return None

    def get_current_cavity(self) -> tuple[str, str] | None:
        """Get current cavity info from active record.

        Returns:
            Tuple of (cavity_name, cryomodule) or None
        """
        if self.session and self.session.has_active_record():
            record = self.session.get_active_record()
            return (record.short_cavity_name, record.cryomodule)
        return None

    def log_message(self, message):
        """Add a message to the history log."""
        if hasattr(self, "history_text"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.history_text.append(f"[{timestamp}] {message}")

    def show_error(self, message):
        """Show error message dialog."""
        QMessageBox.critical(self, "Error", message)

    def show_info(self, title: str, message: str) -> None:
        """Show info message dialog."""
        QMessageBox.information(self, title, message)

    def update_timestamp(self):
        """Update the timestamp label."""
        if hasattr(self, "timestamp_label"):
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.timestamp_label.setText(f"Last Updated: {time_str}")

    def _bind_ui_widgets(self) -> None:
        """Bind UI widgets to self for easy access."""
        if hasattr(self, "ui") and hasattr(self.ui, "widgets"):
            for name, widget in self.ui.widgets.items():
                setattr(self, name, widget)

    def _on_step_progress(self, step_name: str, progress: int):
        """Handle step progress updates."""
        if hasattr(self, "local_current_step"):
            self.local_current_step.setText(step_name)
        if hasattr(self, "local_progress_bar"):
            self.local_progress_bar.setValue(progress)
        self.log_message(f"Executing step: {step_name}")
