"""Persistence and conflict-resolution helpers for the commissioning container."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QMessageBox

from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.ui.database_browser_dialog import (
    DatabaseBrowserDialog,
)
from sc_linac_physics.applications.rf_commissioning.ui.measurement_history_dialog import (
    MeasurementHistoryDialog,
)
from sc_linac_physics.applications.rf_commissioning.ui.merge_dialog import (
    MergeDialog,
)


def _fetch_merge_target(host, record_id: int):
    """Fetch the latest database record/version for merge resolution."""
    result = host.session.get_record_with_version(record_id)
    if not result:
        QMessageBox.critical(
            host, "Error", "Failed to load database version for merge."
        )
        return None
    return result


def _get_merged_record(host, db_record):
    """Open merge dialog and return merged record when accepted."""
    local_record = host.session.get_active_record()
    merge_dialog = MergeDialog(local_record, db_record, parent=host)
    if merge_dialog.exec_() != QDialog.Accepted:
        host._update_sync_status(False, "Merge cancelled")
        return None
    return merge_dialog.get_merged_record()


def _get_expected_version(db_version, conflict: RecordConflictError) -> int:
    """Prefer fetched DB version; fall back to conflict's observed version."""
    if db_version is not None:
        return db_version
    return conflict.actual_version


def _handle_merge_save_error(host, error: Exception) -> bool:
    """Handle save errors; return True when caller should retry merge."""
    if isinstance(error, RecordConflictError):
        host._update_sync_status(False, "Record changed, re-merge required")
        return True

    QMessageBox.critical(
        host, "Save Failed", f"Failed to save merged record: {error}"
    )
    host._update_sync_status(False, "Save failed")
    return False


class _PersistenceMixin:
    def save_active_record(self) -> bool:
        """Save the active record with conflict detection."""
        if not self.session.has_active_record():
            return False

        try:
            success = self.session.save_active_record()
            if success:
                self._update_sync_status(True, "Saved")
                self.update_progress_indicator(self.session.get_active_record())
                self._update_tab_states()

            return success
        except RecordConflictError as error:
            return self._handle_save_conflict(error)

    def _handle_save_conflict(self, conflict: RecordConflictError) -> bool:
        """Handle optimistic locking conflict via merge dialog."""
        if not self.session.has_active_record():
            return False

        record_id = self.session.get_active_record_id()
        if not record_id:
            return False

        latest_conflict = conflict

        while True:
            result = _fetch_merge_target(self, record_id)
            if result is None:
                return False

            db_record, db_version = result
            expected_version = _get_expected_version(
                db_version, latest_conflict
            )
            merged_record = _get_merged_record(self, db_record)
            if not merged_record:
                return False

            try:
                self.session.save_record(
                    merged_record,
                    record_id,
                    expected_version=expected_version,
                )
                self.load_record(record_id)

                QMessageBox.information(
                    self,
                    "Merge Successful",
                    "Your changes have been merged and saved.",
                )
                self._update_sync_status(True, "Merged and saved")
                return True

            except Exception as error:
                if not _handle_merge_save_error(self, error):
                    return False
                latest_conflict = error

        return False

    def _show_measurement_history(self) -> None:
        """Open dialog showing all measurement attempts."""
        if not self.session.has_active_record():
            QMessageBox.information(
                self,
                "No Active Record",
                "Please load or create a commissioning record first.",
            )
            return

        existing_dialog = getattr(self, "_measurement_history_dialog", None)
        if existing_dialog and existing_dialog.isVisible():
            existing_dialog.raise_()
            existing_dialog.activateWindow()
            return

        dialog = MeasurementHistoryDialog(self.session, parent=self)
        self._measurement_history_dialog = dialog
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.destroyed.connect(
            lambda _obj=None: setattr(self, "_measurement_history_dialog", None)
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _show_database_browser(self) -> None:
        """Open database browser to select and load a record."""
        cryomodule = self.cryomodule_combo.currentText()
        cavity = self.cavity_combo.currentText()

        if cryomodule == "CM..." or not cryomodule:
            cryomodule = None

        if cavity == "Cav..." or not cavity:
            cavity = None

        linac = None
        if cryomodule:
            from sc_linac_physics.utils.sc_linac.linac_utils import (
                get_linac_for_cryomodule,
            )

            linac = get_linac_for_cryomodule(cryomodule)

        dialog = DatabaseBrowserDialog(
            self.session.database,
            self,
            cryomodule_filter=cryomodule,
            cavity_filter=cavity,
            linac_filter=linac,
        )

        if dialog.exec_() != QDialog.Accepted:
            return

        record_id, record_data = dialog.get_selected_record()

        if not record_id or not record_data:
            return

        if not self.load_record(record_id):
            QMessageBox.critical(
                self, "Load Failed", f"Failed to load record {record_id}"
            )


# Backward-compat aliases so existing tests continue to work.
save_active_record = _PersistenceMixin.save_active_record
handle_save_conflict = _PersistenceMixin._handle_save_conflict
show_measurement_history = _PersistenceMixin._show_measurement_history
show_database_browser = _PersistenceMixin._show_database_browser
