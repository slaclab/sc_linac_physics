from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.ui.container import (
    _HeaderMixin,
    _NoteActionsMixin,
    _NotesPanelMixin,
    _PersistenceMixin,
    _ProgressMixin,
    _RecordLifecycleMixin,
    _RecordSelectorMixin,
    _SyncMixin,
    _TabsMixin,
    note_actions,
    notes,
    persistence,
    record_lifecycle,
    records,
    sync,
    tab_state,
)


class _Stub(
    _TabsMixin,
    _SyncMixin,
    _PersistenceMixin,
    _RecordLifecycleMixin,
    _RecordSelectorMixin,
    _NotesPanelMixin,
    _NoteActionsMixin,
    _ProgressMixin,
    _HeaderMixin,
    QWidget,
):
    """Minimal QWidget stub that carries all mixin methods for unit testing."""


class _Signal:
    def __init__(self):
        self.connected = None

    def connect(self, cb):
        self.connected = cb


class _TabBar:
    def __init__(self):
        self.colors = {}

    def setTabTextColor(self, idx, color):
        self.colors[idx] = color


class _Tabs:
    def __init__(self):
        self.enabled = {}
        self.text = {}
        self.current = None
        self._bar = _TabBar()
        self.currentChanged = _Signal()
        self._count = 0

    def addTab(self, _widget, text):
        self.text[self._count] = text
        self._count += 1

    def count(self):
        return self._count

    def setTabEnabled(self, idx, value):
        self.enabled[idx] = value

    def setTabText(self, idx, value):
        self.text[idx] = value

    def tabBar(self):
        return self._bar

    def setCurrentIndex(self, idx):
        self.current = idx


@pytest.fixture
def host_stub(qtbot):
    host = _Stub()
    qtbot.addWidget(host)
    host.setLayout(QVBoxLayout())

    host.session = SimpleNamespace(
        get_active_phase_projection=Mock(return_value=None),
        has_active_record=Mock(return_value=False),
        get_active_record_id=Mock(return_value=None),
        get_active_record_version=Mock(return_value=1),
        get_record_with_version=Mock(return_value=None),
        get_operators=Mock(return_value=["Alice", "Bob"]),
        add_operator=Mock(),
        database=object(),
    )
    host.tabs = _Tabs()
    host.phase_specs = []
    host._phase_displays = []
    host._update_sync_status = Mock()
    host._update_tab_states = Mock()
    host.update_progress_indicator = Mock()
    host._load_notes = Mock()
    host._update_cm_status_panel = Mock()
    host.save_active_record = Mock()
    host._on_tab_changed = Mock()
    # Delegate to module-level aliases so monkeypatch on the alias still works.
    host._build_note_dialog = lambda *a, **kw: note_actions.build_note_dialog(
        host, *a, **kw
    )
    host._confirm_and_start_new = (
        lambda *a, **kw: records.confirm_and_start_new(host, *a, **kw)
    )

    host.cryomodule_combo = QComboBox()
    host.cryomodule_combo.addItem("Select CM...")
    host.cryomodule_combo.addItem("01")
    host.cavity_combo = QComboBox()
    host.cavity_combo.addItem("Select Cav...")
    host.cavity_combo.addItem("1")

    host.notes_phase_filter = QComboBox()
    host.notes_phase_filter.addItem("All", None)
    host.notes_table = QTableWidget()
    host._quick_add_note = lambda: None
    host._show_notes_context_menu = lambda _pos: None
    host.operator_combo = QComboBox()
    host.operator_combo.addItem("Select", "")
    host.operator_combo.addItem("Alice", "Alice")
    host.operator_combo.setCurrentIndex(1)

    host.sync_status = QLabel()
    host._update_banner = None
    host.load_record = Mock(return_value=True)
    host._reload_from_banner = lambda: sync.reload_from_banner(host)
    host._dismiss_banner = lambda: sync.dismiss_banner(host)
    host._handle_note_conflict = Mock()

    return host


def test_tab_state_icon_and_update_paths(host_stub):
    host_stub.phase_specs = [
        SimpleNamespace(phase=None, title="Overview"),
        SimpleNamespace(phase=CommissioningPhase.PIEZO_PRE_RF, title="P"),
        SimpleNamespace(phase=CommissioningPhase.SSA_CHAR, title="S"),
    ]
    host_stub.tabs.addTab(QWidget(), "Overview")
    host_stub.tabs.addTab(QWidget(), "P")
    host_stub.tabs.addTab(QWidget(), "S")

    tab_state.update_tab_states(host_stub)
    assert host_stub.tabs.enabled[1] is False
    assert host_stub.tabs.enabled[2] is False

    projection = {
        "current_phase": CommissioningPhase.SSA_CHAR,
        "phase_status": {
            CommissioningPhase.PIEZO_PRE_RF: SimpleNamespace(value="complete"),
            CommissioningPhase.SSA_CHAR: SimpleNamespace(value="failed"),
        },
    }
    host_stub.session.get_active_phase_projection.return_value = projection

    assert tab_state.get_phase_icon(host_stub, None) == "●"
    assert (
        tab_state.get_phase_icon(host_stub, CommissioningPhase.PIEZO_PRE_RF)
        == "✓"
    )
    assert (
        tab_state.get_phase_icon(host_stub, CommissioningPhase.SSA_CHAR) == "✗"
    )

    tab_state.update_tab_states(host_stub)
    assert host_stub.tabs.enabled[0] is True
    assert host_stub.tabs.enabled[1] is True
    assert host_stub.tabs.enabled[2] is True
    assert host_stub.tabs.tabBar().colors[2] == Qt.red


def test_tab_state_on_tab_changed_handles_conflict(host_stub):
    host_stub.session.has_active_record.return_value = True
    host_stub.save_active_record.side_effect = RecordConflictError(
        record_id=10,
        expected_version=1,
        actual_version=2,
    )

    tab_state.on_tab_changed(host_stub, 1)

    host_stub._update_sync_status.assert_called_once_with(
        False, "Unsaved changes"
    )


def test_record_lifecycle_start_load_and_advance(host_stub):
    display_with_controller = SimpleNamespace(
        controller=SimpleNamespace(update_pv_addresses=Mock()),
        refresh_from_record=Mock(),
        on_record_loaded=Mock(),
    )
    display_without_controller = SimpleNamespace(
        refresh_from_record=Mock(),
        on_record_loaded=Mock(),
    )
    host_stub._phase_displays = [
        display_with_controller,
        display_without_controller,
    ]
    host_stub.phase_specs = [
        SimpleNamespace(phase=CommissioningPhase.PIEZO_PRE_RF),
        SimpleNamespace(phase=CommissioningPhase.SSA_CHAR),
    ]

    record = SimpleNamespace(
        current_phase=CommissioningPhase.SSA_CHAR,
        cryomodule="01",
        cavity_number=1,
    )
    host_stub.session.start_new_record = Mock(return_value=(record, 10, False))

    created = record_lifecycle.start_new_record(host_stub, "01", "1")
    assert created is False
    assert host_stub.tabs.current == 1
    display_with_controller.controller.update_pv_addresses.assert_called_once_with(
        "01", "1"
    )

    host_stub.session.load_record = Mock(return_value=None)
    assert record_lifecycle.load_record(host_stub, 999) is False

    host_stub.session.load_record = Mock(return_value=record)
    assert record_lifecycle.load_record(host_stub, 10) is True
    assert host_stub.cryomodule_combo.currentText() == "01"
    assert host_stub.cavity_combo.currentText() == "1"

    record_lifecycle.on_phase_advanced(host_stub, record)
    host_stub._update_sync_status.assert_called_with(True, "Phase completed")


def test_sync_helpers_cover_change_and_reload_paths(host_stub, monkeypatch):
    sync.update_sync_status(host_stub, True)
    assert "Synced" in host_stub.sync_status.text()

    sync.update_sync_status(host_stub, False, "Remote")
    assert "Remote" in host_stub.sync_status.text()

    host_stub.session.has_active_record.return_value = True
    host_stub.session.get_active_record_id.return_value = 7
    host_stub.session.get_record_with_version.return_value = (
        object(),
        5,
    )
    host_stub.session.get_active_record_version.return_value = 3

    sync.check_for_external_changes(host_stub)
    assert host_stub._update_banner is not None

    # Banner already present should be a no-op.
    existing = host_stub._update_banner
    sync.show_update_banner(host_stub, 6, 5)
    assert host_stub._update_banner is existing

    monkeypatch.setattr(
        QMessageBox, "question", Mock(return_value=QMessageBox.Yes)
    )
    sync.reload_from_banner(host_stub)
    host_stub.load_record.assert_called_with(7)

    sync.dismiss_banner(host_stub)
    assert host_stub._update_banner is None

    monkeypatch.setattr(QMessageBox, "warning", Mock())
    conflict = RecordConflictError(
        record_id=10,
        expected_version=1,
        actual_version=2,
    )
    sync.handle_note_conflict(host_stub, conflict)


def test_persistence_save_and_merge_paths(host_stub, monkeypatch):
    host_stub.session.has_active_record.return_value = False
    assert persistence.save_active_record(host_stub) is False

    host_stub.session.has_active_record.return_value = True
    host_stub.session.save_active_record = Mock(return_value=True)
    host_stub.session.get_active_record = Mock(return_value=SimpleNamespace())
    assert persistence.save_active_record(host_stub) is True

    host_stub._handle_save_conflict = Mock(return_value=True)
    host_stub.session.save_active_record.side_effect = RecordConflictError(
        record_id=11,
        expected_version=1,
        actual_version=2,
    )
    assert persistence.save_active_record(host_stub) is True

    host_stub.session.get_active_record_id = Mock(return_value=12)
    host_stub.session.db = SimpleNamespace(
        get_record_with_version=Mock(return_value=None),
        save_record=Mock(),
    )
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    assert (
        persistence.handle_save_conflict(
            host_stub,
            RecordConflictError(
                record_id=12,
                expected_version=1,
                actual_version=2,
            ),
        )
        is False
    )

    class _CancelMerge:
        def __init__(self, *_a, **_k):
            pass

        def exec_(self):
            return 0

    monkeypatch.setattr(persistence, "MergeDialog", _CancelMerge)
    host_stub.session.get_record_with_version.return_value = (
        SimpleNamespace(),
        2,
    )
    host_stub.session.get_active_record = Mock(return_value=SimpleNamespace())
    assert (
        persistence.handle_save_conflict(
            host_stub,
            RecordConflictError(
                record_id=12,
                expected_version=1,
                actual_version=2,
            ),
        )
        is False
    )


def test_notes_loading_and_note_actions(host_stub, monkeypatch):
    panel = notes.build_enhanced_notes_panel(host_stub)
    assert panel is not None
    assert host_stub.notes_table.columnCount() == 4

    host_stub.session.has_active_record.return_value = False
    notes.load_notes(host_stub)
    assert host_stub.notes_table.rowCount() == 0

    host_stub.session.has_active_record.return_value = True
    host_stub.session.get_active_record = Mock(
        return_value=SimpleNamespace(
            current_phase=CommissioningPhase.PIEZO_PRE_RF
        )
    )
    host_stub.session.get_measurement_notes = Mock(
        return_value=[
            {
                "phase": CommissioningPhase.PIEZO_PRE_RF.value,
                "measurement_timestamp": "2026-01-01",
                "timestamp": "2026-01-02",
                "operator": "Alice",
                "note": "meas",
                "entry_id": 1,
                "note_index": 0,
            }
        ]
    )
    host_stub.session.get_general_notes = Mock(
        return_value=[
            {
                "timestamp": "2026-01-03",
                "operator": "Bob",
                "note": "general",
            }
        ]
    )

    notes.load_notes(host_stub)
    assert host_stub.notes_table.rowCount() == 2
    assert host_stub.notes_table.item(0, 3).text() == "general"

    host_stub.session.has_active_record.return_value = False
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    note_actions.quick_add_note(host_stub)
    warning.assert_called_once()


def test_note_edit_and_reference_paths(host_stub, monkeypatch):
    host_stub.notes_table.setColumnCount(4)
    host_stub.notes_table.setRowCount(1)
    ref_item = QTableWidgetItem("t")
    ref_item.setData(Qt.UserRole, ("general", 0))
    host_stub.notes_table.setItem(0, 0, ref_item)
    host_stub.notes_table.setItem(0, 2, QTableWidgetItem("Alice"))
    host_stub.notes_table.setItem(0, 3, QTableWidgetItem("hello"))
    host_stub.notes_table.selectRow(0)

    host_stub.session.update_general_note = Mock(return_value=True)
    monkeypatch.setattr(
        note_actions,
        "build_note_dialog",
        Mock(return_value=("Alice", "updated")),
    )

    note_actions.on_edit_note(host_stub)
    host_stub.session.update_general_note.assert_called_once_with(
        0,
        "Alice",
        "updated",
    )

    host_stub.notes_table.clearSelection()
    assert note_actions.get_selected_note_ref(host_stub) is None


def test_records_load_and_start_paths(host_stub, monkeypatch):
    host_stub.operator_combo.setCurrentIndex(0)
    warn = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warn)

    records.on_load_or_start(host_stub)
    warn.assert_called_once()

    host_stub.operator_combo.setCurrentIndex(1)
    host_stub.cryomodule_combo.setCurrentIndex(1)
    host_stub.cavity_combo.setCurrentIndex(1)
    host_stub.session.find_records_for_cavity = Mock(return_value=[])

    monkeypatch.setattr(records, "get_linac_for_cryomodule", lambda _cm: "L1B")
    called = Mock()
    monkeypatch.setattr(records, "confirm_and_start_new", called)
    records.on_load_or_start(host_stub)
    called.assert_called_once()

    # load_selected_record failure path
    table = QTableWidget()
    table.setColumnCount(1)
    table.setRowCount(1)
    table.setItem(0, 0, QTableWidgetItem("9"))
    table.selectRow(0)
    dialog = SimpleNamespace(accept=Mock())
    host_stub.load_record = Mock(return_value=False)
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    records.load_selected_record(host_stub, table, dialog)
    critical.assert_called_once()


def test_confirm_and_start_new_conflict_and_error(host_stub, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", Mock(return_value=QMessageBox.Yes)
    )
    monkeypatch.setattr(QMessageBox, "critical", Mock())

    host_stub.start_new_record = Mock(return_value=True)
    host_stub.session.append_general_note = Mock(
        side_effect=RecordConflictError(
            record_id=13,
            expected_version=1,
            actual_version=2,
        )
    )
    host_stub.operator_combo.setCurrentIndex(1)

    records.confirm_and_start_new(host_stub, "01-1", "L1B", "01", "1")
    host_stub._handle_note_conflict.assert_called_once()

    host_stub.start_new_record = Mock(side_effect=RuntimeError("boom"))
    records.confirm_and_start_new(host_stub, "01-1", "L1B", "01", "1")


def test_note_actions_operator_required_and_dialog_paths(
    host_stub, monkeypatch
):
    host_stub.session.has_active_record.return_value = True
    host_stub.operator_combo.setCurrentIndex(0)

    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    note_actions.quick_add_note(host_stub)

    # Accept path through quick-add.
    host_stub.operator_combo.setCurrentIndex(1)
    host_stub.session.append_general_note = Mock(return_value=True)
    monkeypatch.setattr(
        note_actions.QInputDialog,
        "getMultiLineText",
        Mock(return_value=("  note body  ", True)),
    )
    note_actions.quick_add_note(host_stub)
    host_stub.session.append_general_note.assert_called_once_with(
        "Alice",
        "note body",
    )

    # Cover build_note_dialog accepted and rejected return paths.
    monkeypatch.setattr(
        note_actions.QDialog, "exec_", lambda self: QDialog.Accepted
    )
    operator, text = note_actions.build_note_dialog(
        host_stub,
        "Edit",
        "Alice",
        "saved note",
    )
    assert operator == "Alice"
    assert text == "saved note"

    monkeypatch.setattr(
        note_actions.QDialog, "exec_", lambda self: QDialog.Rejected
    )
    operator, text = note_actions.build_note_dialog(host_stub, "Edit", "Alice")
    assert operator is None
    assert text is None


def test_persistence_merge_success_failure_and_dialogs(host_stub, monkeypatch):
    host_stub.session.has_active_record.return_value = True
    host_stub.session.get_active_record_id = Mock(return_value=5)
    host_stub.session.get_active_record = Mock(return_value=SimpleNamespace())
    host_stub.load_record = Mock(return_value=True)

    info = Mock()
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "information", info)
    monkeypatch.setattr(QMessageBox, "critical", critical)

    class _MergeAccepted:
        def __init__(self, *_a, **_k):
            pass

        def exec_(self):
            return QDialog.Accepted

        def get_merged_record(self):
            return SimpleNamespace()

    host_stub.session.get_record_with_version = Mock(
        return_value=(SimpleNamespace(), 7)
    )
    host_stub.session.save_record = Mock()
    monkeypatch.setattr(persistence, "MergeDialog", _MergeAccepted)
    assert (
        persistence.handle_save_conflict(
            host_stub,
            RecordConflictError(
                record_id=5, expected_version=1, actual_version=2
            ),
        )
        is True
    )
    assert host_stub.session.save_record.call_count == 1
    assert (
        host_stub.session.save_record.call_args.kwargs["expected_version"] == 7
    )

    host_stub.session.save_record = Mock(
        side_effect=RuntimeError("save failed")
    )
    assert (
        persistence.handle_save_conflict(
            host_stub,
            RecordConflictError(
                record_id=5, expected_version=1, actual_version=2
            ),
        )
        is False
    )
    assert critical.called


def test_persistence_merge_retries_on_second_conflict(host_stub, monkeypatch):
    host_stub.session.has_active_record.return_value = True
    host_stub.session.get_active_record_id = Mock(return_value=5)
    host_stub.session.get_active_record = Mock(return_value=SimpleNamespace())
    host_stub.load_record = Mock(return_value=True)

    info = Mock()
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "information", info)
    monkeypatch.setattr(QMessageBox, "critical", critical)

    dialog_calls = {"count": 0}

    class _MergeAccepted:
        def __init__(self, *_a, **_k):
            dialog_calls["count"] += 1

        def exec_(self):
            return QDialog.Accepted

        def get_merged_record(self):
            return SimpleNamespace()

    save_attempts = {"count": 0}

    def _save_record(_record, _record_id, expected_version):
        save_attempts["count"] += 1
        if save_attempts["count"] == 1:
            raise RecordConflictError(
                record_id=5,
                expected_version=7,
                actual_version=8,
            )

    host_stub.session.get_record_with_version = Mock(
        side_effect=[
            (SimpleNamespace(name="v7"), 7),
            (SimpleNamespace(name="v8"), 8),
        ]
    )
    host_stub.session.save_record = Mock(side_effect=_save_record)

    monkeypatch.setattr(persistence, "MergeDialog", _MergeAccepted)

    assert (
        persistence.handle_save_conflict(
            host_stub,
            RecordConflictError(
                record_id=5,
                expected_version=1,
                actual_version=2,
            ),
        )
        is True
    )

    assert dialog_calls["count"] == 2
    assert host_stub.session.save_record.call_count == 2
    assert (
        host_stub.session.save_record.call_args_list[0].kwargs[
            "expected_version"
        ]
        == 7
    )
    assert (
        host_stub.session.save_record.call_args_list[1].kwargs[
            "expected_version"
        ]
        == 8
    )
    assert info.called


def test_show_measurement_history_modeless_reuses_visible_dialog(
    host_stub, monkeypatch
):
    host_stub.session.has_active_record.return_value = False
    info_no_record = Mock()
    monkeypatch.setattr(QMessageBox, "information", info_no_record)
    persistence.show_measurement_history(host_stub)
    info_no_record.assert_called_once()

    host_stub.session.has_active_record.return_value = True

    called = {}

    class _HistoryDialog:
        def __init__(self, _session, parent=None):
            called["parent"] = parent
            called["init_count"] = called.get("init_count", 0) + 1
            called["visible"] = True

        def isVisible(self):
            return called["visible"]

        def show(self):
            called["show"] = called.get("show", 0) + 1

        def raise_(self):
            called["raised"] = called.get("raised", 0) + 1

        def activateWindow(self):
            called["activated"] = called.get("activated", 0) + 1

        def setAttribute(self, *_args, **_kwargs):
            called["set_attribute"] = True

        @property
        def destroyed(self):
            return SimpleNamespace(connect=lambda _cb: None)

    monkeypatch.setattr(persistence, "MeasurementHistoryDialog", _HistoryDialog)
    persistence.show_measurement_history(host_stub)
    assert called["show"] == 1
    assert called["set_attribute"] is True
    assert host_stub._measurement_history_dialog is not None

    # Second open should reuse existing visible modeless dialog.
    persistence.show_measurement_history(host_stub)
    assert called["init_count"] == 1
    assert called["show"] == 1
    assert called["raised"] >= 2
    assert called["activated"] >= 2


def test_show_database_browser_load_failure_shows_critical(
    host_stub, monkeypatch
):
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)

    host_stub.cryomodule_combo.setCurrentIndex(1)
    host_stub.cavity_combo.setCurrentIndex(1)

    class _DbDialogAccepted:
        def __init__(self, *_a, **_k):
            pass

        def exec_(self):
            return QDialog.Accepted

        def get_selected_record(self):
            return 55, {"ok": True}

    monkeypatch.setattr(persistence, "DatabaseBrowserDialog", _DbDialogAccepted)
    monkeypatch.setattr(
        "sc_linac_physics.utils.sc_linac.linac_utils.get_linac_for_cryomodule",
        lambda _cm: "L1B",
    )
    host_stub.load_record = Mock(return_value=False)
    persistence.show_database_browser(host_stub)
    assert critical.called


def test_tab_state_init_and_phase_icon_fallback_branches(host_stub):
    class _Display(QWidget):
        def __init__(self, parent=None, session=None):
            super().__init__(parent)
            self.session = session

    host_stub.phase_specs = [
        SimpleNamespace(
            phase=CommissioningPhase.PIEZO_PRE_RF,
            title="P",
            display_class=_Display,
        ),
        SimpleNamespace(
            phase=CommissioningPhase.SSA_CHAR, title="S", display_class=_Display
        ),
    ]

    tab_state.init_tabs(host_stub)
    assert host_stub.tabs.count() == 2
    assert host_stub.tabs.currentChanged.connected == host_stub._on_tab_changed

    # Projection is None path.
    host_stub.session.get_active_phase_projection.return_value = None
    assert (
        tab_state.get_phase_icon(host_stub, CommissioningPhase.PIEZO_PRE_RF)
        == "○"
    )

    # Fallback phase order path (no explicit status).
    host_stub.session.get_active_phase_projection.return_value = {
        "current_phase": CommissioningPhase.SSA_CHAR,
        "phase_status": {},
    }
    assert (
        tab_state.get_phase_icon(host_stub, CommissioningPhase.PIEZO_PRE_RF)
        == "✓"
    )
    assert (
        tab_state.get_phase_icon(host_stub, CommissioningPhase.FREQUENCY_TUNING)
        == "○"
    )


def test_quick_add_note_conflict_calls_handler(host_stub, monkeypatch):
    host_stub.session.has_active_record.return_value = True
    host_stub.operator_combo.setCurrentIndex(1)  # "Alice"

    monkeypatch.setattr(
        QInputDialog, "getMultiLineText", lambda *a, **kw: ("my note", True)
    )
    host_stub.session.append_general_note = Mock(
        side_effect=RecordConflictError(
            record_id=1, expected_version=1, actual_version=2
        )
    )
    note_actions.quick_add_note(host_stub)
    host_stub._handle_note_conflict.assert_called_once()


def test_quick_add_note_no_operator_shows_warning(host_stub, monkeypatch):
    host_stub.session.has_active_record.return_value = True
    host_stub.operator_combo.setCurrentIndex(0)  # "Select" → data ""
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    note_actions.quick_add_note(host_stub)
    warning.assert_called_once()


def test_show_notes_context_menu_empty_table_exits_early(host_stub):
    host_stub.notes_table.setRowCount(0)
    note_actions.show_notes_context_menu(host_stub, QPoint(0, 0))


def test_show_notes_context_menu_with_rows_shows_menu(host_stub, monkeypatch):
    host_stub.notes_table.setRowCount(1)
    mock_action = Mock()
    mock_menu = Mock()
    mock_menu.addAction.return_value = mock_action
    mock_menu.exec_.return_value = None  # No action selected
    monkeypatch.setattr(note_actions, "QMenu", lambda _parent: mock_menu)
    note_actions.show_notes_context_menu(host_stub, QPoint(0, 0))


def test_show_notes_context_menu_edit_action_calls_handler(
    host_stub, monkeypatch
):
    host_stub.notes_table.setRowCount(1)
    mock_action = Mock()
    mock_menu = Mock()
    mock_menu.addAction.return_value = mock_action
    mock_menu.exec_.return_value = (
        mock_action  # Return same object → triggers edit
    )
    monkeypatch.setattr(note_actions, "QMenu", lambda _parent: mock_menu)
    host_stub._on_edit_note = Mock()
    note_actions.show_notes_context_menu(host_stub, QPoint(0, 0))
    host_stub._on_edit_note.assert_called_once()


def test_on_edit_note_no_selection_returns_early(host_stub):
    host_stub.notes_table.setColumnCount(4)
    host_stub.notes_table.setRowCount(0)
    note_actions.on_edit_note(host_stub)  # Should not raise


def test_on_edit_note_dialog_cancelled_returns_early(host_stub, monkeypatch):
    host_stub.notes_table.setColumnCount(4)
    host_stub.notes_table.setRowCount(1)
    ref_item = QTableWidgetItem("t")
    ref_item.setData(Qt.UserRole, ("general", 0))
    host_stub.notes_table.setItem(0, 0, ref_item)
    host_stub.notes_table.setItem(0, 2, QTableWidgetItem("Alice"))
    host_stub.notes_table.setItem(0, 3, QTableWidgetItem("hello"))
    host_stub.notes_table.selectRow(0)

    monkeypatch.setattr(
        note_actions, "build_note_dialog", Mock(return_value=(None, None))
    )
    host_stub.session.update_general_note = Mock()
    note_actions.on_edit_note(host_stub)
    host_stub.session.update_general_note.assert_not_called()


def test_on_edit_note_measurement_type_calls_update(host_stub, monkeypatch):
    host_stub.notes_table.setColumnCount(4)
    host_stub.notes_table.setRowCount(1)
    ref_item = QTableWidgetItem("t")
    ref_item.setData(Qt.UserRole, ("measurement", (42, 0)))
    host_stub.notes_table.setItem(0, 0, ref_item)
    host_stub.notes_table.setItem(0, 2, QTableWidgetItem("Alice"))
    host_stub.notes_table.setItem(0, 3, QTableWidgetItem("old note"))
    host_stub.notes_table.selectRow(0)

    monkeypatch.setattr(
        note_actions,
        "build_note_dialog",
        Mock(return_value=("Alice", "new note")),
    )
    host_stub.session.update_measurement_note = Mock(return_value=True)
    note_actions.on_edit_note(host_stub)
    host_stub.session.update_measurement_note.assert_called_once_with(
        42, 0, "Alice", "new note"
    )
    host_stub._load_notes.assert_called()
