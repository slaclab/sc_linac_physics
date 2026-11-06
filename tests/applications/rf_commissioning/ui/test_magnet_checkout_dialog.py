"""Tests for MagnetCheckoutDialog.save()."""

from unittest.mock import MagicMock


from sc_linac_physics.applications.rf_commissioning.models.persistence.database_errors import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.ui import (
    magnet_checkout_dialog,
)
from sc_linac_physics.applications.rf_commissioning.ui.magnet_checkout_dialog import (
    MagnetCheckoutDialog,
)


def test_save_conflict_shows_both_versions_and_returns_false(
    qtbot, monkeypatch
):
    session = MagicMock()
    session.get_cryomodule_record_with_version.return_value = None
    session.get_operators.return_value = ["alice"]
    session.save_cryomodule_record.side_effect = RecordConflictError(
        record_id=7, expected_version=3, actual_version=4
    )
    warning = MagicMock()
    monkeypatch.setattr(magnet_checkout_dialog.QMessageBox, "warning", warning)

    dlg = MagnetCheckoutDialog(session, "L1B", "01")
    qtbot.addWidget(dlg)
    dlg.status_combo.setCurrentText("PASS")
    dlg.operator_combo.setCurrentIndex(dlg.operator_combo.findData("alice"))

    assert dlg.save() is False
    message = warning.call_args[0][2]
    assert "Expected version 3" in message
    assert "database has version 4" in message
    assert warning.call_args[0][1] == "Save Conflict"
