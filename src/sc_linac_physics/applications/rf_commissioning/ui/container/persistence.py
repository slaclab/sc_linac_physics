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


def save_active_record(host) -> bool:
    """Save the active record with conflict detection."""
    if not host.session.has_active_record():
        return False

    try:
        success = host.session.save_active_record()
        if success:
            host._update_sync_status(True, "Saved")
            host.update_progress_indicator(host.session.get_active_record())
            host._update_tab_states()

        return success
    except RecordConflictError as error:
        return host._handle_save_conflict(error)


def _fetch_merge_target(host, record_id: int):
    """Fetch the latest database record/version for merge resolution."""
    result = host.session.db.get_record_with_version(record_id)
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


def handle_save_conflict(host, conflict: RecordConflictError) -> bool:
    """Handle optimistic locking conflict via merge dialog."""
    if not host.session.has_active_record():
        return False

    record_id = host.session.get_active_record_id()
    if not record_id:
        return False

    latest_conflict = conflict

    while True:
        result = _fetch_merge_target(host, record_id)
        if result is None:
            return False

        db_record, db_version = result
        expected_version = _get_expected_version(db_version, latest_conflict)
        merged_record = _get_merged_record(host, db_record)
        if not merged_record:
            return False

        try:
            host.session.db.save_record(
                merged_record,
                record_id,
                expected_version=expected_version,
            )
            host.load_record(record_id)

            QMessageBox.information(
                host,
                "Merge Successful",
                "Your changes have been merged and saved.",
            )
            host._update_sync_status(True, "Merged and saved")
            return True

        except Exception as error:
            if not _handle_merge_save_error(host, error):
                return False
            latest_conflict = error

    return False


def show_measurement_history(host) -> None:
    """Open dialog showing all measurement attempts."""
    if not host.session.has_active_record():
        QMessageBox.information(
            host,
            "No Active Record",
            "Please load or create a commissioning record first.",
        )
        return

    existing_dialog = getattr(host, "_measurement_history_dialog", None)
    if existing_dialog and existing_dialog.isVisible():
        existing_dialog.raise_()
        existing_dialog.activateWindow()
        return

    dialog = MeasurementHistoryDialog(host.session, parent=host)
    host._measurement_history_dialog = dialog
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.destroyed.connect(
        lambda _obj=None: setattr(host, "_measurement_history_dialog", None)
    )
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def show_database_browser(host) -> None:
    """Open database browser to select and load a record."""
    cryomodule = host.cryomodule_combo.currentText()
    cavity = host.cavity_combo.currentText()

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
        host.session.database,
        host,
        cryomodule_filter=cryomodule,
        cavity_filter=cavity,
        linac_filter=linac,
    )

    if dialog.exec_() != QDialog.Accepted:
        return

    record_id, record_data = dialog.get_selected_record()

    if not record_id or not record_data:
        return

    if not host.load_record(record_id):
        QMessageBox.critical(
            host, "Load Failed", f"Failed to load record {record_id}"
        )
