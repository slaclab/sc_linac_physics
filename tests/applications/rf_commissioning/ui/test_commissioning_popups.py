"""Tests for standalone dialog widgets: DatabaseBrowserDialog,
MeasurementHistoryDialog, and MergeDialog."""

from datetime import datetime
from unittest.mock import MagicMock

from PyQt5.QtWidgets import QDialog

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseCheckpoint,
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

# ── shared helpers ──────────────────────────────────────────────────────────


def _record_dict(
    id=1,
    linac="L1B",
    cm="01",
    cav="1",
    phase="piezo_pre_rf",
    status="in_progress",
):
    return {
        "id": id,
        "linac": linac,
        "linac_number": linac,
        "cryomodule": cm,
        "cavity_number": cav,
        "current_phase": phase,
        "overall_status": status,
        "start_time": "2025-01-01T10:00:00",
        "end_time": None,
    }


def _db(records=None):
    db = MagicMock()
    db.get_all_records.return_value = records or []
    return db


def _cr(linac=1, cm="01", cav=1):
    return CommissioningRecord(linac=linac, cryomodule=cm, cavity_number=cav)


def _cp(phase=CommissioningPhase.PIEZO_PRE_RF, ts=None, operator="Alice"):
    return PhaseCheckpoint(
        phase=phase,
        timestamp=ts or datetime(2025, 1, 1, 10, 0, 0),
        operator=operator,
        step_name="test_step",
        success=True,
    )


def _session(has_record=True, history=None):
    s = MagicMock()
    s.has_active_record.return_value = has_record
    s.get_measurement_history.return_value = history or []
    return s


def _history_entry(
    id=1, phase="piezo_pre_rf", operator="Alice", notes=None, data=None
):
    return {
        "id": id,
        "timestamp": "2025-01-01T10:00:00",
        "phase": phase,
        "operator": operator,
        "notes": notes or [],
        "measurement_data": data or {},
    }


# ── DatabaseBrowserDialog ──────────────────────────────────────────────────


def test_db_browser_empty_db_shows_no_rows(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 0


def test_db_browser_records_populate_table(qtbot):
    dlg = DatabaseBrowserDialog(
        _db([_record_dict(id=1), _record_dict(id=2, cav="2")])
    )
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 2


def test_db_browser_initial_cm_filter_narrows_results(qtbot):
    records = [_record_dict(id=1, cm="01"), _record_dict(id=2, cm="02")]
    dlg = DatabaseBrowserDialog(_db(records), cryomodule_filter="01")
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1


def test_db_browser_initial_cavity_filter_narrows_results(qtbot):
    records = [_record_dict(id=1, cav="1"), _record_dict(id=2, cav="3")]
    dlg = DatabaseBrowserDialog(_db(records), cavity_filter="3")
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1


def test_db_browser_linac_filter_excludes_other_linacs(qtbot):
    records = [_record_dict(id=1, linac="L1B"), _record_dict(id=2, linac="L2B")]
    dlg = DatabaseBrowserDialog(_db(records), linac_filter="L1B")
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1


def test_db_browser_format_timestamp_valid_iso(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    assert "2025-01-15" in dlg._format_timestamp("2025-01-15T12:30:00")


def test_db_browser_format_timestamp_na_and_empty(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    assert dlg._format_timestamp("N/A") == "N/A"
    assert dlg._format_timestamp("") == "N/A"


def test_db_browser_format_timestamp_unparseable_returns_original(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    assert dlg._format_timestamp("not-a-date") == "not-a-date"


def test_db_browser_create_status_item_all_variants(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    for status in ("complete", "failed", "in_progress", "unknown"):
        item = dlg._create_status_item(status)
        assert item.text() == status.upper()


def test_db_browser_create_result_item_piezo_pass(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    rec = {"piezo_pre_rf": {"channel_a_passed": True, "channel_b_passed": True}}
    assert dlg._create_result_item("piezo_pre_rf", rec).text() == "PASS"


def test_db_browser_create_result_item_piezo_fail(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    rec = {
        "piezo_pre_rf": {"channel_a_passed": False, "channel_b_passed": True}
    }
    assert dlg._create_result_item("piezo_pre_rf", rec).text() == "FAIL"


def test_db_browser_create_result_item_other_phase_na(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    assert dlg._create_result_item("ssa_char", {}).text() == "N/A"


def test_db_browser_cm_filter_combo_filters_rows(qtbot):
    records = [_record_dict(id=1, cm="01"), _record_dict(id=2, cm="02")]
    dlg = DatabaseBrowserDialog(_db(records))
    qtbot.addWidget(dlg)
    idx = dlg.cryomodule_combo.findText("01")
    dlg.cryomodule_combo.setCurrentIndex(idx)
    assert dlg.table.rowCount() == 1


def test_db_browser_cavity_filter_combo_filters_rows(qtbot):
    records = [_record_dict(id=1, cav="1"), _record_dict(id=2, cav="5")]
    dlg = DatabaseBrowserDialog(_db(records))
    qtbot.addWidget(dlg)
    idx = dlg.cavity_combo.findText("5")
    dlg.cavity_combo.setCurrentIndex(idx)
    assert dlg.table.rowCount() == 1


def test_db_browser_clear_filters_restores_all_rows(qtbot):
    records = [_record_dict(id=1, cm="01"), _record_dict(id=2, cm="02")]
    dlg = DatabaseBrowserDialog(_db(records), cryomodule_filter="01")
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1
    dlg._clear_filters()
    assert dlg.table.rowCount() == 2


def test_db_browser_load_error_shown_in_label(qtbot):
    bad_db = MagicMock()
    bad_db.get_all_records.side_effect = Exception("boom")
    dlg = DatabaseBrowserDialog(bad_db)
    qtbot.addWidget(dlg)
    assert "Error" in dlg.info_label.text()


def test_db_browser_row_selection_enables_load_button(qtbot):
    dlg = DatabaseBrowserDialog(_db([_record_dict(id=42)]))
    qtbot.addWidget(dlg)
    assert not dlg.load_button.isEnabled()
    dlg.table.selectRow(0)
    assert dlg.load_button.isEnabled()
    assert dlg.selected_record_id == 42


def test_db_browser_deselecting_row_disables_load_button(qtbot):
    dlg = DatabaseBrowserDialog(_db([_record_dict(id=1)]))
    qtbot.addWidget(dlg)
    dlg.table.selectRow(0)
    dlg.table.clearSelection()
    assert not dlg.load_button.isEnabled()
    assert dlg.selected_record_id is None


def test_db_browser_double_click_with_selection_accepts(qtbot):
    dlg = DatabaseBrowserDialog(_db([_record_dict(id=1)]))
    qtbot.addWidget(dlg)
    dlg.table.selectRow(0)
    dlg._on_double_click(None)
    assert dlg.result() == QDialog.Accepted


def test_db_browser_double_click_without_selection_does_nothing(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    dlg._on_double_click(None)  # Should not raise


def test_db_browser_get_selected_record_after_selection(qtbot):
    dlg = DatabaseBrowserDialog(_db([_record_dict(id=7)]))
    qtbot.addWidget(dlg)
    dlg.table.selectRow(0)
    rec_id, rec = dlg.get_selected_record()
    assert rec_id == 7
    assert rec["id"] == 7


def test_db_browser_update_info_label_zero_records(qtbot):
    dlg = DatabaseBrowserDialog(_db())
    qtbot.addWidget(dlg)
    dlg._update_info_label(0, 0)
    assert "No records" in dlg.info_label.text()


def test_db_browser_record_with_end_time(qtbot):
    rec = _record_dict(id=1)
    rec["end_time"] = "2025-06-01T12:00:00"
    dlg = DatabaseBrowserDialog(_db([rec]))
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1


# ── MeasurementHistoryDialog ───────────────────────────────────────────────


def test_mhd_no_active_record_shows_empty_table(qtbot):
    dlg = MeasurementHistoryDialog(_session(has_record=False))
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 0
    assert "No active record" in dlg.count_label.text()


def test_mhd_phase_filter_argument_sets_combo(qtbot):
    dlg = MeasurementHistoryDialog(
        _session(), phase=CommissioningPhase.PIEZO_PRE_RF
    )
    qtbot.addWidget(dlg)
    assert dlg.current_phase == CommissioningPhase.PIEZO_PRE_RF


def test_mhd_history_entries_populate_table(qtbot):
    history = [_history_entry(id=1), _history_entry(id=2, operator="Bob")]
    dlg = MeasurementHistoryDialog(_session(history=history))
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 2
    assert "2 measurement" in dlg.count_label.text()


def test_mhd_missing_operator_shows_unknown(qtbot):
    history = [_history_entry(operator=None)]
    dlg = MeasurementHistoryDialog(_session(history=history))
    qtbot.addWidget(dlg)
    assert dlg.table.item(0, 2).text() == "Unknown"


def test_mhd_phase_filter_change_reloads(qtbot):
    s = _session()
    dlg = MeasurementHistoryDialog(s)
    qtbot.addWidget(dlg)
    calls_before = s.get_measurement_history.call_count
    dlg.phase_filter.setCurrentIndex(1)
    assert s.get_measurement_history.call_count > calls_before


def test_mhd_format_notes_empty_list(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    assert dlg._format_notes([]) == ""


def test_mhd_format_notes_with_timestamp(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    notes = [{"note": "hi", "operator": "Bob", "timestamp": "2025-01-01"}]
    result = dlg._format_notes(notes)
    assert "Bob" in result and "hi" in result


def test_mhd_format_notes_without_timestamp(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    notes = [{"note": "hi", "operator": "Carol", "timestamp": None}]
    assert "Carol: hi" in dlg._format_notes(notes)


def test_mhd_summarize_data_empty_and_none(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    assert dlg._summarize_measurement_data({}) == "No data"
    assert dlg._summarize_measurement_data(None) == "No data"


def test_mhd_summarize_data_numeric_and_bool(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    data = {"a": 1.5, "b": True, "c": "short"}
    result = dlg._summarize_measurement_data(data)
    assert "a=" in result and "b=" in result


def test_mhd_summarize_data_truncates_with_field_count(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    data = {str(i): i for i in range(6)}
    assert "(6 fields total)" in dlg._summarize_measurement_data(data)


def test_mhd_summarize_data_complex_only(qtbot):
    dlg = MeasurementHistoryDialog(_session())
    qtbot.addWidget(dlg)
    assert (
        dlg._summarize_measurement_data({"a": {"nested": True}})
        == "Complex data"
    )


def test_mhd_history_notes_shown_in_table(qtbot):
    notes = [
        {"note": "test note", "operator": "Alice", "timestamp": "2025-01-01"}
    ]
    history = [_history_entry(notes=notes, data={"val": 1.0})]
    dlg = MeasurementHistoryDialog(_session(history=history))
    qtbot.addWidget(dlg)
    assert "test note" in dlg.table.item(0, 3).text()


# ── MergeDialog ────────────────────────────────────────────────────────────


def test_merge_identical_records_no_fields_shown(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    assert dlg.content_layout.count() == 0


def test_merge_different_status_shows_field(qtbot):
    local = _cr()
    db_rec = _cr()
    db_rec.overall_status = "complete"
    dlg = MergeDialog(local, db_rec)
    qtbot.addWidget(dlg)
    assert dlg.content_layout.count() > 0


def test_merge_get_merged_record_before_accept_is_none(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    assert dlg.get_merged_record() is None


def test_merge_keep_all_local(qtbot):
    local = _cr()
    db_rec = _cr()
    db_rec.overall_status = "complete"
    dlg = MergeDialog(local, db_rec)
    qtbot.addWidget(dlg)
    dlg._keep_all_local()
    assert dlg.get_merged_record().overall_status == local.overall_status


def test_merge_keep_all_db(qtbot):
    local = _cr()
    db_rec = _cr()
    db_rec.overall_status = "complete"
    dlg = MergeDialog(local, db_rec)
    qtbot.addWidget(dlg)
    dlg._keep_all_db()
    assert dlg.get_merged_record().overall_status == "complete"


def test_merge_apply_merge_accepts_dialog(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    dlg._apply_merge()
    assert dlg.result() == QDialog.Accepted


def test_merge_on_field_choice_records_selection(qtbot):
    local = _cr()
    db_rec = _cr()
    db_rec.overall_status = "complete"
    dlg = MergeDialog(local, db_rec)
    qtbot.addWidget(dlg)
    dlg._on_field_choice("overall_status", "db")
    assert dlg._field_choices["overall_status"] == "db"


def test_merge_phase_status_db_choice_syncs_current_phase(qtbot):
    local = _cr()
    db_rec = _cr()
    db_rec.overall_status = "complete"
    dlg = MergeDialog(local, db_rec)
    qtbot.addWidget(dlg)
    dlg._field_choices["phase_status"] = "db"
    dlg._apply_merge()
    assert dlg.get_merged_record().current_phase == db_rec.current_phase


def test_merge_phase_history_deduplicates(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    cp = _cp()
    assert len(dlg._merge_phase_history([cp], [cp])) == 1


def test_merge_phase_history_combines_unique(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    cp1 = _cp(ts=datetime(2025, 1, 1), operator="Alice")
    cp2 = _cp(ts=datetime(2025, 1, 2), operator="Bob")
    assert len(dlg._merge_phase_history([cp1], [cp2])) == 2


def test_merge_phase_history_sorted_chronologically(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    cp_early = _cp(ts=datetime(2025, 1, 1))
    cp_late = _cp(ts=datetime(2025, 1, 3), operator="Bob")
    result = dlg._merge_phase_history([cp_late], [cp_early])
    assert result[0].timestamp < result[1].timestamp


def test_merge_phase_data_summary_none(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    assert dlg._phase_data_summary(None) == "No data"


def test_merge_phase_data_summary_with_to_dict(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    obj = MagicMock()
    obj.to_dict.return_value = {"field": 1.0, "ts": datetime(2025, 1, 1)}
    assert "field" in dlg._phase_data_summary(obj)


def test_merge_phase_data_summary_fallback_str(qtbot):
    dlg = MergeDialog(_cr(), _cr())
    qtbot.addWidget(dlg)
    assert dlg._phase_data_summary("raw") == "raw"
