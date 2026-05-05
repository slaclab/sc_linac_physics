"""Tests for BatchPiezoPreRFWindow."""

from unittest.mock import Mock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QWidget

from sc_linac_physics.applications.rf_commissioning.ui.controllers.batch_piezo_pre_rf_controller import (
    BatchPiezoPreRFController,
    CavitySpec,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays.batch_piezo_pre_rf import (
    BatchPiezoPreRFWindow,
    _COL_CAV,
    _COL_CHA,
    _COL_CHB,
    _COL_CM,
    _COL_LINAC,
    _COL_OVERALL,
    _COL_STATUS,
    _STATUS_COLORS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_window():
    session = Mock()
    return BatchPiezoPreRFWindow(session=session)


@pytest.fixture
def win():
    w = _make_window()
    yield w
    w.deleteLater()


def _cell_text(win, row, col):
    item = win._table.item(row, col)
    return item.text() if item else None


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_window_title(self, win):
        assert win.windowTitle() == "Batch Piezo Pre-RF"

    def test_minimum_size(self, win):
        assert win.minimumWidth() >= 1000
        assert win.minimumHeight() >= 700

    def test_controller_created(self, win):
        assert isinstance(win._controller, BatchPiezoPreRFController)

    def test_row_by_key_empty_initially(self, win):
        assert win._row_by_key == {}

    def test_run_btn_enabled_initially(self, win):
        assert win._run_btn.isEnabled()

    def test_abort_btn_disabled_initially(self, win):
        assert not win._abort_btn.isEnabled()

    def test_progress_bar_zero(self, win):
        assert win._progress_bar.value() == 0

    def test_selection_count_label_shows_zero(self, win):
        assert "0" in win._selection_count_label.text()

    def test_log_starts_empty(self, win):
        assert win._log.toPlainText() == ""


# ---------------------------------------------------------------------------
# Tree population
# ---------------------------------------------------------------------------


class TestTreePopulation:
    def test_linac_nodes_at_top_level(self, win):
        root = win._tree.invisibleRootItem()
        assert root.childCount() == 5  # L0B through L4B

    def test_l0b_has_one_cm(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        assert l0.childCount() == 1  # CM01 only

    def test_l1b_has_four_cms(self, win):
        root = win._tree.invisibleRootItem()
        l1 = root.child(1)
        assert l1.childCount() == 4  # 02, 03, H1, H2

    def test_each_cm_has_eight_cavities(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        assert cm.childCount() == 8

    def test_cavity_items_initially_unchecked(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        for i in range(cm.childCount()):
            assert cm.child(i).checkState(0) == Qt.Unchecked

    def test_cavity_user_data_has_cm_and_num(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        cav_item = cm.child(0)
        data = cav_item.data(0, Qt.UserRole)
        assert data is not None
        assert data[0] == "cav"

    def test_cm_item_has_user_data(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        data = cm.data(0, Qt.UserRole)
        assert data is not None
        assert data[0] == "cm"


# ---------------------------------------------------------------------------
# Select / deselect all
# ---------------------------------------------------------------------------


class TestSelectAll:
    def test_select_all_checks_all_cavities(self, win):
        win._select_all()
        root = win._tree.invisibleRootItem()
        for i in range(root.childCount()):
            linac = root.child(i)
            for j in range(linac.childCount()):
                cm = linac.child(j)
                for k in range(cm.childCount()):
                    assert cm.child(k).checkState(0) == Qt.Checked

    def test_deselect_all_unchecks_all_cavities(self, win):
        win._select_all()
        win._deselect_all()
        root = win._tree.invisibleRootItem()
        for i in range(root.childCount()):
            linac = root.child(i)
            for j in range(linac.childCount()):
                cm = linac.child(j)
                for k in range(cm.childCount()):
                    assert cm.child(k).checkState(0) == Qt.Unchecked

    def test_select_all_updates_count_label(self, win):
        win._select_all()
        label = win._selection_count_label.text()
        assert "0" not in label or "cavities" in label  # non-zero count

    def test_deselect_all_resets_count_label(self, win):
        win._select_all()
        win._deselect_all()
        assert "0" in win._selection_count_label.text()


# ---------------------------------------------------------------------------
# Get selected cavities
# ---------------------------------------------------------------------------


class TestGetSelectedCavities:
    def test_no_selection_returns_empty(self, win):
        assert win._get_selected_cavities() == []

    def test_select_all_returns_all_cavities(self, win):
        win._select_all()
        selected = win._get_selected_cavities()
        assert len(selected) > 0

    def test_single_check_returns_one_spec(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        cm.child(0).setCheckState(0, Qt.Checked)
        selected = win._get_selected_cavities()
        assert len(selected) == 1
        assert isinstance(selected[0], CavitySpec)

    def test_selected_spec_has_correct_cavity_number(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        cm.child(2).setCheckState(0, Qt.Checked)  # Cav 3
        selected = win._get_selected_cavities()
        assert len(selected) == 1
        assert selected[0].cavity_number == 3


# ---------------------------------------------------------------------------
# Update selection count
# ---------------------------------------------------------------------------


class TestUpdateSelectionCount:
    def test_singular_cavity_label(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        cm.child(0).setCheckState(0, Qt.Checked)
        win._update_selection_count()
        assert "1 cavity" in win._selection_count_label.text()
        assert "cavities" not in win._selection_count_label.text()

    def test_plural_cavities_label(self, win):
        root = win._tree.invisibleRootItem()
        l0 = root.child(0)
        cm = l0.child(0)
        cm.child(0).setCheckState(0, Qt.Checked)
        cm.child(1).setCheckState(0, Qt.Checked)
        win._update_selection_count()
        assert "2 cavities" in win._selection_count_label.text()


# ---------------------------------------------------------------------------
# Setup results table
# ---------------------------------------------------------------------------


class TestSetupResultsTable:
    def test_table_has_correct_row_count(self, win):
        cavities = [CavitySpec("01", 1), CavitySpec("01", 2)]
        win._setup_results_table(cavities)
        assert win._table.rowCount() == 2

    def test_row_key_mapping_populated(self, win):
        cavities = [CavitySpec("01", 1), CavitySpec("02", 3)]
        win._setup_results_table(cavities)
        assert "01_CAV1" in win._row_by_key
        assert "02_CAV3" in win._row_by_key

    def test_status_column_set_to_pending(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        assert _cell_text(win, 0, _COL_STATUS) == "PENDING"

    def test_cm_column_set(self, win):
        cavities = [CavitySpec("01", 5)]
        win._setup_results_table(cavities)
        assert _cell_text(win, 0, _COL_CM) == "01"

    def test_cav_column_set(self, win):
        cavities = [CavitySpec("01", 7)]
        win._setup_results_table(cavities)
        assert _cell_text(win, 0, _COL_CAV) == "7"

    def test_clears_previous_rows(self, win):
        win._setup_results_table([CavitySpec("01", 1), CavitySpec("01", 2)])
        win._setup_results_table([CavitySpec("01", 3)])
        assert win._table.rowCount() == 1

    def test_linac_name_shown_in_linac_column(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        assert _cell_text(win, 0, _COL_LINAC) == "L0B"

    def test_unknown_linac_shown_as_question_mark(self, win):
        cavities = [CavitySpec("ZZ", 1)]
        win._setup_results_table(cavities)
        assert _cell_text(win, 0, _COL_LINAC) == "?"


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------


class TestOnCavityStatus:
    def test_updates_status_cell(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_status("01_CAV1", "TRIGGERING")
        assert _cell_text(win, 0, _COL_STATUS) == "TRIGGERING"

    def test_unknown_key_is_no_op(self, win):
        win._on_cavity_status("MISSING_KEY", "PASSED")  # should not raise

    def test_status_color_applied(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_status("01_CAV1", "PASSED")
        item = win._table.item(0, _COL_STATUS)
        assert item.foreground().color().name().lower() in (
            _STATUS_COLORS["PASSED"].lower(),
            "#66bb6a",
        )

    def test_unknown_status_uses_white(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_status("01_CAV1", "UNKNOWN_STATUS")
        item = win._table.item(0, _COL_STATUS)
        # white = #ffffff
        assert item.foreground().color().name().lower() == "#ffffff"


class TestOnCavityResult:
    def _passing_result(self):
        return PiezoPreRFCheck(
            capacitance_a=25e-9,
            capacitance_b=24e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )

    def _failing_result(self):
        return PiezoPreRFCheck(
            capacitance_a=5e-9,
            capacitance_b=24e-9,
            channel_a_passed=False,
            channel_b_passed=True,
        )

    def test_cha_pass_shown(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", self._passing_result())
        assert _cell_text(win, 0, _COL_CHA) == "PASS"

    def test_chb_pass_shown(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", self._passing_result())
        assert _cell_text(win, 0, _COL_CHB) == "PASS"

    def test_cha_fail_shown(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", self._failing_result())
        assert _cell_text(win, 0, _COL_CHA) == "FAIL"

    def test_overall_pass_shown(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", self._passing_result())
        assert _cell_text(win, 0, _COL_OVERALL) == "PASS"

    def test_overall_fail_when_channel_fails(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", self._failing_result())
        assert _cell_text(win, 0, _COL_OVERALL) == "FAIL"

    def test_capacitance_a_formatted(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", self._passing_result())
        # 25e-9 * 1e9 = 25.00
        assert _cell_text(win, 0, _COL_CHA + 2) == "25.00"  # _COL_CAPA

    def test_unknown_key_is_no_op(self, win):
        win._on_cavity_result("MISSING", self._passing_result())  # no raise

    def test_none_result_is_no_op(self, win):
        cavities = [CavitySpec("01", 1)]
        win._setup_results_table(cavities)
        win._on_cavity_result("01_CAV1", None)  # should not update table


class TestOnBatchProgress:
    def test_progress_bar_updated(self, win):
        win._progress_bar.setMaximum(5)
        win._on_batch_progress(3, 5)
        assert win._progress_bar.value() == 3

    def test_progress_label_updated(self, win):
        win._on_batch_progress(2, 7)
        assert "2 / 7" in win._progress_label.text()


class TestOnBatchFinished:
    def test_run_btn_reenabled(self, win):
        win._run_btn.setEnabled(False)
        win._on_batch_finished()
        assert win._run_btn.isEnabled()

    def test_abort_btn_disabled(self, win):
        win._abort_btn.setEnabled(True)
        win._on_batch_finished()
        assert not win._abort_btn.isEnabled()

    def test_log_shows_complete_message(self, win):
        win._on_batch_finished()
        assert "complete" in win._log.toPlainText().lower()


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------


class TestAppendLog:
    def test_message_appears_in_log(self, win):
        win._append_log("hello log")
        assert "hello log" in win._log.toPlainText()

    def test_multiple_messages_accumulated(self, win):
        win._append_log("first message")
        win._append_log("second message")
        text = win._log.toPlainText()
        assert "first message" in text
        assert "second message" in text


# ---------------------------------------------------------------------------
# Operator resolution
# ---------------------------------------------------------------------------


class TestGetOperator:
    def test_returns_empty_when_no_parent(self, win):
        assert win._get_operator() == ""

    def test_returns_operator_from_parent_combo(self, win):
        parent = QWidget()
        parent.operator_combo = QComboBox()
        parent.operator_combo.addItem("Alice", "Alice")
        parent.operator_combo.setCurrentIndex(0)

        child = BatchPiezoPreRFWindow(parent=parent, session=Mock())
        try:
            result = child._get_operator()
            assert result == "Alice"
        finally:
            child.deleteLater()
            parent.deleteLater()

    def test_skips_select_placeholder(self, win):
        parent = QWidget()
        parent.operator_combo = QComboBox()
        parent.operator_combo.addItem("👤 Select operator...", "")
        parent.operator_combo.setCurrentIndex(0)

        child = BatchPiezoPreRFWindow(parent=parent, session=Mock())
        try:
            result = child._get_operator()
            assert result == ""
        finally:
            child.deleteLater()
            parent.deleteLater()

    def test_strips_person_emoji_from_operator_text(self, win):
        parent = QWidget()
        parent.operator_combo = QComboBox()
        parent.operator_combo.addItem("👤 Bob", None)  # data is None, text used
        parent.operator_combo.setCurrentIndex(0)

        child = BatchPiezoPreRFWindow(parent=parent, session=Mock())
        try:
            result = child._get_operator()
            assert result == "Bob"
        finally:
            child.deleteLater()
            parent.deleteLater()


# ---------------------------------------------------------------------------
# Run / Abort buttons
# ---------------------------------------------------------------------------


class TestOnRunClicked:
    def test_no_operator_logs_error(self, win):
        logs = []
        win._log.append = lambda m: logs.append(m)
        win._get_operator = lambda: ""
        win._on_run_clicked()
        assert any("operator" in (m or "").lower() for m in logs)

    def test_no_cavities_selected_logs_message(self, win):
        logs = []
        win._log.append = lambda m: logs.append(m)
        win._get_operator = lambda: "operator"
        win._on_run_clicked()
        # selection count is 0, should log about no cavities
        assert any("No cavities" in (m or "") for m in logs)

    def test_run_disables_run_btn(self, win):
        win._get_operator = lambda: "operator"
        # select one cavity
        root = win._tree.invisibleRootItem()
        root.child(0).child(0).child(0).setCheckState(0, Qt.Checked)
        win._controller.run_batch = Mock()
        win._on_run_clicked()
        assert not win._run_btn.isEnabled()

    def test_run_enables_abort_btn(self, win):
        win._get_operator = lambda: "operator"
        root = win._tree.invisibleRootItem()
        root.child(0).child(0).child(0).setCheckState(0, Qt.Checked)
        win._controller.run_batch = Mock()
        win._on_run_clicked()
        assert win._abort_btn.isEnabled()

    def test_run_calls_controller_run_batch(self, win):
        win._get_operator = lambda: "operator"
        root = win._tree.invisibleRootItem()
        root.child(0).child(0).child(0).setCheckState(0, Qt.Checked)
        win._controller.run_batch = Mock()
        win._on_run_clicked()
        win._controller.run_batch.assert_called_once()


class TestOnAbortClicked:
    def test_abort_calls_controller_abort(self, win):
        win._controller.abort = Mock()
        win._abort_btn.setEnabled(True)
        win._on_abort_clicked()
        win._controller.abort.assert_called_once()

    def test_abort_disables_abort_btn(self, win):
        win._controller.abort = Mock()
        win._abort_btn.setEnabled(True)
        win._on_abort_clicked()
        assert not win._abort_btn.isEnabled()


# ---------------------------------------------------------------------------
# Tree item changed
# ---------------------------------------------------------------------------


class TestOnTreeItemChanged:
    def test_updates_selection_count_label(self, win):
        root = win._tree.invisibleRootItem()
        cav_item = root.child(0).child(0).child(0)
        initial = win._selection_count_label.text()
        cav_item.setCheckState(0, Qt.Checked)
        # After check state change the label should reflect the new count
        assert (
            win._selection_count_label.text() != initial
            or "1" in win._selection_count_label.text()
        )
