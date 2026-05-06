from types import SimpleNamespace
from unittest.mock import Mock

from PyQt5.QtWidgets import (
    QDialog,
    QTableWidget,
    QWidget,
)

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.container import (
    header,
    progress_panel,
    records,
)


def _make_header_host():
    return SimpleNamespace(
        _on_cavity_selection_changed=Mock(),
        _on_operator_changed=Mock(),
        _populate_operator_combo=Mock(),
        _open_magnet_checkout_screen=Mock(),
        _open_batch_pre_rf_window=Mock(),
        _show_measurement_history=Mock(),
        _show_database_browser=Mock(),
    )


def test_build_header_panel_wires_controls_and_actions(qtbot):
    host = _make_header_host()

    panel = header.build_header_panel(host)
    qtbot.addWidget(panel)

    assert host.cryomodule_combo.count() > 1
    assert host.cavity_combo.count() == 9
    assert host.sync_status.text() == "○ No Record Loaded"
    assert host._populate_operator_combo.called

    buttons = panel.findChildren(type(host.open_magnet_checkout_btn))
    labels = {b.text() for b in buttons}
    assert "Open Magnet Checkout" in labels
    assert "Batch Pre-RF" in labels
    assert "📊 Measurements" in labels
    assert "🗄️ Database" in labels


def test_build_progress_bar_and_update_indicator_states(qtbot):
    host = QWidget()
    qtbot.addWidget(host)

    projection = {
        "current_phase": CommissioningPhase.SSA_CHAR,
        "phase_status": {
            CommissioningPhase.PIEZO_PRE_RF: SimpleNamespace(value="complete"),
            CommissioningPhase.SSA_CHAR: SimpleNamespace(value="failed"),
        },
    }
    host.session = SimpleNamespace(
        get_active_phase_projection=Mock(return_value=projection)
    )

    widget = progress_panel.build_compact_progress_bar(host)
    qtbot.addWidget(widget)

    assert len(host.phase_indicators) > 0
    assert len(host.phase_connectors) == len(host.phase_indicators) - 1

    progress_panel.update_progress_indicator(host, record=object())

    assert host.phase_indicators[CommissioningPhase.PIEZO_PRE_RF].text() == "✔"
    assert host.phase_indicators[CommissioningPhase.SSA_CHAR].text() == "✖"


def test_show_record_selector_renders_table_and_hooks_actions(
    qtbot, monkeypatch
):
    host = QWidget()
    host.load_record = Mock(return_value=True)
    host._update_sync_status = Mock()
    qtbot.addWidget(host)

    records_data = [
        {
            "id": 42,
            "start_time": "2026-01-01T01:02:03",
            "overall_status": "in_progress",
            "current_phase": "piezo_pre_rf",
            "updated_at": "2026-01-01T04:05:06",
        }
    ]

    load_selected = Mock()
    monkeypatch.setattr(records, "load_selected_record", load_selected)

    seen = {}

    class _AutoDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            seen["dialog"] = self

        def exec_(self):
            table = self.findChild(QTableWidget)
            assert table is not None
            assert table.rowCount() == 1
            table.selectRow(0)
            table.cellDoubleClicked.emit(0, 0)
            return QDialog.Rejected

    monkeypatch.setattr(records, "QDialog", _AutoDialog)

    records.show_record_selector(
        host,
        cavity_display_name="01_CAV1",
        linac="L1B",
        cryomodule="01",
        cavity_number="1",
        records=records_data,
    )

    assert load_selected.called


def test_load_selected_record_success_sets_settings(monkeypatch):
    table = QTableWidget()
    table.setColumnCount(1)
    table.setRowCount(1)
    table.setItem(0, 0, records.QTableWidgetItem("7"))
    table.selectRow(0)

    host = SimpleNamespace(
        load_record=Mock(return_value=True), _update_sync_status=Mock()
    )
    dialog = SimpleNamespace(accept=Mock())

    settings_spy = SimpleNamespace(setValue=Mock())
    monkeypatch.setattr(records, "QSettings", lambda *_a, **_k: settings_spy)

    records.load_selected_record(host, table, dialog)

    dialog.accept.assert_called_once()
    settings_spy.setValue.assert_called_once_with("last_record_id", 7)
