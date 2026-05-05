"""Coverage-focused tests for multi_phase_screen container logic."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PyQt5.QtWidgets import QComboBox, QDialog, QLabel, QTextEdit

import sc_linac_physics.applications.rf_commissioning.ui.multi_phase_screen as multi_phase_screen
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CryomoduleCheckoutRecord,
)
from sc_linac_physics.applications.rf_commissioning.ui.multi_phase_screen import (
    MultiPhaseCommissioningDisplay,
)


class _StaticCombo:
    def __init__(self, text: str):
        self._text = text

    def currentText(self) -> str:
        return self._text


@pytest.fixture
def display_stub():
    db = Mock()
    session = SimpleNamespace(
        db=db,
        get_operators=Mock(return_value=["Alice", "Bob"]),
        add_operator=Mock(),
    )
    return SimpleNamespace(
        session=session,
        cryomodule_combo=_StaticCombo("01"),
        cavity_combo=_StaticCombo("1"),
        operator_combo=QComboBox(),
        cavity_completion_label=QLabel(),
        magnet_status_badge=Mock(),
        start_new_record=Mock(return_value=True),
        _update_sync_status=Mock(),
        _refresh_magnet_badge=Mock(),
        _refresh_cavity_completion_label=Mock(),
    )


def test_on_cavity_selection_changed_skips_when_selection_invalid(display_stub):
    display_stub.cryomodule_combo = _StaticCombo("Select CM...")

    MultiPhaseCommissioningDisplay._on_cavity_selection_changed(display_stub)

    display_stub._refresh_magnet_badge.assert_called_once_with("Select CM...")
    display_stub._refresh_cavity_completion_label.assert_called_once_with(
        "Select CM..."
    )
    display_stub.start_new_record.assert_not_called()


def test_on_cavity_selection_changed_starts_or_loads(display_stub, monkeypatch):
    monkeypatch.setattr(
        multi_phase_screen,
        "get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )

    MultiPhaseCommissioningDisplay._on_cavity_selection_changed(display_stub)

    display_stub.start_new_record.assert_called_once_with("01", "1")
    display_stub._update_sync_status.assert_called_once_with(
        True,
        "New record started",
    )


def test_refresh_magnet_badge_maps_statuses(display_stub):
    linac = "L1B"

    display_stub.session.db.get_cryomodule_record.return_value = None
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    display_stub.session.db.get_cryomodule_record.return_value = (
        SimpleNamespace(magnet_checkout=None)
    )
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    display_stub.session.db.get_cryomodule_record.return_value = (
        SimpleNamespace(magnet_checkout=SimpleNamespace(passed=True))
    )
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    display_stub.session.db.get_cryomodule_record.return_value = (
        SimpleNamespace(magnet_checkout=SimpleNamespace(passed=False))
    )
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    assert display_stub.magnet_status_badge.set_status.call_args_list[-4:] == [
        call("PENDING"),
        call("PENDING"),
        call("PASS"),
        call("FAIL"),
    ]


def test_refresh_cavity_completion_label_counts_complete_records(display_stub):
    class _TerminalPhase:
        value = "terminal"

        @staticmethod
        def get_next_phase():
            return None

    display_stub.session.db.get_records_by_cryomodule.return_value = [
        SimpleNamespace(
            current_phase=CommissioningPhase.COMPLETE,
            overall_status="in_progress",
        ),
        SimpleNamespace(
            current_phase=_TerminalPhase(),
            overall_status="in_progress",
        ),
        SimpleNamespace(
            current_phase=CommissioningPhase.PIEZO_PRE_RF,
            overall_status="in_progress",
        ),
    ]

    MultiPhaseCommissioningDisplay._refresh_cavity_completion_label(
        display_stub, "01"
    )

    assert display_stub.cavity_completion_label.text() == "2/8 Complete"


def test_populate_operator_combo_adds_placeholder_and_restore(display_stub):
    MultiPhaseCommissioningDisplay._populate_operator_combo(
        display_stub, restore_selection="Bob"
    )

    assert display_stub.operator_combo.itemData(0) == ""
    assert (
        display_stub.operator_combo.itemData(
            display_stub.operator_combo.count() - 1
        )
        == "__add__"
    )
    assert display_stub.operator_combo.currentData() == "Bob"


def test_on_operator_changed_opens_add_dialog(display_stub):
    display_stub.operator_combo.addItem("Add", "__add__")
    display_stub.operator_combo.setCurrentIndex(0)
    display_stub._add_new_operator = Mock()

    MultiPhaseCommissioningDisplay._on_operator_changed(display_stub, 0)

    display_stub._add_new_operator.assert_called_once()


def test_add_new_operator_cancel_resets_selection(display_stub, monkeypatch):
    display_stub.operator_combo.addItem("placeholder", "")
    display_stub.operator_combo.addItem("Add", "__add__")
    display_stub.operator_combo.setCurrentIndex(1)

    class _Dialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(None)

        def exec_(self):
            return QDialog.Rejected

    monkeypatch.setattr(multi_phase_screen, "QDialog", _Dialog)

    MultiPhaseCommissioningDisplay._add_new_operator(display_stub)

    assert display_stub.operator_combo.currentIndex() == 0
    display_stub.session.add_operator.assert_not_called()


def test_open_magnet_checkout_screen_requires_cryomodule(
    display_stub, monkeypatch
):
    display_stub.cryomodule_combo = _StaticCombo("Select CM...")
    info = Mock()
    monkeypatch.setattr(multi_phase_screen.QMessageBox, "information", info)

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    info.assert_called_once()


def test_open_magnet_checkout_screen_requires_operator_for_pass(
    display_stub, monkeypatch
):
    monkeypatch.setattr(
        multi_phase_screen,
        "get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )
    display_stub.session.db.get_cryomodule_record_with_version.return_value = (
        CryomoduleCheckoutRecord(linac="L1B", cryomodule="01"),
        3,
    )
    display_stub.session.db.get_cryomodule_record_id.return_value = 9

    class _Dialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(None)

        def exec_(self):
            combos = self.findChildren(QComboBox)
            combos[0].setCurrentText("PASS")
            combos[1].setCurrentIndex(0)
            return QDialog.Accepted

    warn = Mock()
    monkeypatch.setattr(multi_phase_screen, "QDialog", _Dialog)
    monkeypatch.setattr(multi_phase_screen.QMessageBox, "warning", warn)

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    assert "Operator Required" in warn.call_args.args[1]
    display_stub.session.db.save_cryomodule_record.assert_not_called()


def test_open_magnet_checkout_screen_saves_and_updates_header(
    display_stub, monkeypatch
):
    monkeypatch.setattr(
        multi_phase_screen,
        "get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )
    display_stub.session.db.get_cryomodule_record_with_version.return_value = (
        CryomoduleCheckoutRecord(linac="L1B", cryomodule="01"),
        3,
    )
    display_stub.session.db.get_cryomodule_record_id.return_value = 9
    display_stub._refresh_magnet_badge = Mock()
    display_stub._refresh_cavity_completion_label = Mock()

    class _Dialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(None)

        def exec_(self):
            combos = self.findChildren(QComboBox)
            combos[0].setCurrentText("PASS")
            combos[1].setCurrentIndex(1)
            self.findChildren(QTextEdit)[0].setPlainText(" done ")
            return QDialog.Accepted

    monkeypatch.setattr(multi_phase_screen, "QDialog", _Dialog)

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    save_call = display_stub.session.db.save_cryomodule_record.call_args
    saved_record = save_call.args[0]
    assert saved_record.magnet_checkout.passed is True
    assert saved_record.magnet_checkout.operator == "Alice"
    assert saved_record.magnet_checkout.notes == "done"
    display_stub._refresh_magnet_badge.assert_called_once_with("01", "L1B")
    display_stub._refresh_cavity_completion_label.assert_called_once_with("01")
    display_stub._update_sync_status.assert_called_once()


def test_update_cm_status_panel_ignores_none_and_updates_valid_record(
    display_stub,
):
    MultiPhaseCommissioningDisplay._update_cm_status_panel(display_stub, None)
    display_stub._refresh_magnet_badge.assert_not_called()

    record = SimpleNamespace(cryomodule="01", linac="L1B")
    MultiPhaseCommissioningDisplay._update_cm_status_panel(display_stub, record)

    display_stub._refresh_magnet_badge.assert_called_once_with("01", "L1B")
    display_stub._refresh_cavity_completion_label.assert_called_once_with("01")
