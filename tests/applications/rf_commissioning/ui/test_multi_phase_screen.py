"""Coverage-focused tests for multi_phase_screen container logic."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PyQt5.QtWidgets import QComboBox, QDialog, QLabel

import sc_linac_physics.applications.rf_commissioning.ui.multi_phase_screen as multi_phase_screen
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.multi_phase_screen import (
    MultiPhaseCommissioningDisplay,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
    LINAC_CM_MAP,
)


class _StaticCombo:
    def __init__(self, text: str):
        self._text = text

    def currentText(self) -> str:
        return self._text


@pytest.fixture
def display_stub():
    session = SimpleNamespace(
        get_operators=Mock(return_value=["Alice", "Bob"]),
        add_operator=Mock(),
        get_cryomodule_record=Mock(return_value=None),
        get_records_by_cryomodule=Mock(return_value=[]),
        get_cryomodule_record_with_version=Mock(return_value=None),
        get_cryomodule_record_id=Mock(return_value=None),
        save_cryomodule_record=Mock(),
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
    display_stub.cryomodule_combo = _StaticCombo("CM...")

    MultiPhaseCommissioningDisplay._on_cavity_selection_changed(display_stub)

    display_stub._refresh_magnet_badge.assert_called_once_with("CM...")
    display_stub._refresh_cavity_completion_label.assert_called_once_with(
        "CM..."
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


def test_on_linac_selection_changed_all_populates_all_cryomodules(display_stub):
    display_stub.linac_combo = _StaticCombo("All")
    display_stub.cryomodule_combo = QComboBox()

    MultiPhaseCommissioningDisplay._on_linac_selection_changed(display_stub)

    combo_items = [
        display_stub.cryomodule_combo.itemText(i)
        for i in range(display_stub.cryomodule_combo.count())
    ]
    assert combo_items[0] == "CM..."
    assert combo_items[1:] == sorted(ALL_CRYOMODULES)


def test_on_linac_selection_changed_linac_uses_shared_mapping(display_stub):
    display_stub.linac_combo = _StaticCombo("L1B")
    display_stub.cryomodule_combo = QComboBox()

    MultiPhaseCommissioningDisplay._on_linac_selection_changed(display_stub)

    combo_items = [
        display_stub.cryomodule_combo.itemText(i)
        for i in range(display_stub.cryomodule_combo.count())
    ]
    assert combo_items[0] == "CM..."
    assert combo_items[1:] == LINAC_CM_MAP[1]


def test_refresh_magnet_badge_maps_statuses(display_stub):
    linac = "L1B"

    display_stub.session.get_cryomodule_record.return_value = None
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    display_stub.session.get_cryomodule_record.return_value = SimpleNamespace(
        magnet_checkout=None
    )
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    display_stub.session.get_cryomodule_record.return_value = SimpleNamespace(
        magnet_checkout=SimpleNamespace(passed=True)
    )
    MultiPhaseCommissioningDisplay._refresh_magnet_badge(
        display_stub, "01", linac
    )

    display_stub.session.get_cryomodule_record.return_value = SimpleNamespace(
        magnet_checkout=SimpleNamespace(passed=False)
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
    display_stub.session.get_records_by_cryomodule.return_value = [
        SimpleNamespace(
            current_phase=CommissioningPhase.COMPLETE,
            overall_status="in_progress",
        ),
        SimpleNamespace(
            current_phase=CommissioningPhase.PIEZO_PRE_RF,
            overall_status="in_progress",
        ),
        SimpleNamespace(
            current_phase=CommissioningPhase.PIEZO_PRE_RF,
            overall_status="in_progress",
        ),
    ]

    MultiPhaseCommissioningDisplay._refresh_cavity_completion_label(
        display_stub, "01", "L1B"
    )

    assert display_stub.cavity_completion_label.text() == "1/8 Complete"


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
    display_stub.cryomodule_combo = _StaticCombo("CM...")
    info = Mock()
    monkeypatch.setattr(multi_phase_screen.QMessageBox, "information", info)

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    info.assert_called_once()


def test_open_magnet_checkout_screen_cancelled_does_nothing(
    display_stub, monkeypatch
):
    monkeypatch.setattr(
        multi_phase_screen,
        "get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )
    dialog_mock = Mock()
    dialog_mock.exec_.return_value = QDialog.Rejected
    monkeypatch.setattr(
        multi_phase_screen, "MagnetCheckoutDialog", lambda *a, **kw: dialog_mock
    )
    display_stub._refresh_magnet_badge = Mock()

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    dialog_mock.save.assert_not_called()
    display_stub._refresh_magnet_badge.assert_not_called()


def test_open_magnet_checkout_screen_saves_and_updates_header(
    display_stub, monkeypatch
):
    monkeypatch.setattr(
        multi_phase_screen,
        "get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )
    dialog_mock = Mock()
    dialog_mock.exec_.return_value = QDialog.Accepted
    dialog_mock.save.return_value = True
    monkeypatch.setattr(
        multi_phase_screen, "MagnetCheckoutDialog", lambda *a, **kw: dialog_mock
    )
    display_stub._refresh_magnet_badge = Mock()
    display_stub._refresh_cavity_completion_label = Mock()

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    dialog_mock.save.assert_called_once()
    display_stub._refresh_magnet_badge.assert_called_once_with("01", "L1B")
    display_stub._refresh_cavity_completion_label.assert_called_once_with("01")
    display_stub._update_sync_status.assert_called_once()


def test_open_magnet_checkout_screen_save_failure_skips_refresh(
    display_stub, monkeypatch
):
    monkeypatch.setattr(
        multi_phase_screen,
        "get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )
    dialog_mock = Mock()
    dialog_mock.exec_.return_value = QDialog.Accepted
    dialog_mock.save.return_value = False
    monkeypatch.setattr(
        multi_phase_screen, "MagnetCheckoutDialog", lambda *a, **kw: dialog_mock
    )
    display_stub._refresh_magnet_badge = Mock()

    MultiPhaseCommissioningDisplay._open_magnet_checkout_screen(display_stub)

    display_stub._refresh_magnet_badge.assert_not_called()


def test_update_cm_status_panel_ignores_none_and_updates_valid_record(
    display_stub,
):
    display_stub._linac_str = MultiPhaseCommissioningDisplay._linac_str

    MultiPhaseCommissioningDisplay._update_cm_status_panel(display_stub, None)
    display_stub._refresh_magnet_badge.assert_not_called()

    record = SimpleNamespace(cryomodule="01", linac=1)
    MultiPhaseCommissioningDisplay._update_cm_status_panel(display_stub, record)

    display_stub._refresh_magnet_badge.assert_called_once_with("01", "L1B")
    display_stub._refresh_cavity_completion_label.assert_called_once_with(
        "01", "L1B"
    )
