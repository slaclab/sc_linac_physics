from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_data_fetcher import (
    CavityFaultResult,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_heatmap_display import (
    FaultHeatmapDisplay,
    HEATMAP_ROWS,
)
from tests.displays.cavity_display.frontend.heatmap.conftest import (
    make_result,
    make_error_result,
    make_machine,
)


def _count_expected_cm_widgets():
    total = 0
    for row_sections in HEATMAP_ROWS:
        for _, cm_names in row_sections:
            total += len(cm_names)
    return total


@pytest.fixture
def display():
    disp = FaultHeatmapDisplay()
    yield disp
    disp.close()


class TestFaultHeatmapDisplayInit:
    def test_creates_without_crash(self, display):
        assert display is not None

    def test_correct_number_of_cm_widgets(self, display):
        expected = _count_expected_cm_widgets()
        assert len(display._cm_widgets) == expected

    def test_initial_button_states(self, display):
        assert display._refresh_btn.isEnabled()
        assert not display._abort_btn.isEnabled()
        assert not display._fetch_selected_btn.isEnabled()
        assert not display._clear_selection_btn.isEnabled()

    def test_filter_checkboxes_default_on(self, display):
        assert display._cb_alarms.isChecked()
        assert display._cb_warnings.isChecked()
        assert display._cb_invalid.isChecked()

    def test_window_title(self, display):
        assert display.windowTitle() == "LCLS-II Fault Heatmap"

    def test_progress_bar_initial_state(self, display):
        assert display._progress_bar.value() == 0


class TestTimeRange:
    def test_default_range_is_one_hour(self, display):
        """Spec §4.3: default range = last 1 hour."""
        start = display._start_dt.dateTime().toPyDateTime()
        end = display._end_dt.dateTime().toPyDateTime()
        diff = end - start
        assert abs(diff.total_seconds() - 3600) < 5

    def test_set_quick_range_30min(self, display):
        display._set_quick_range(minutes=30)
        start = display._start_dt.dateTime().toPyDateTime()
        end = display._end_dt.dateTime().toPyDateTime()
        diff = end - start
        assert abs(diff.total_seconds() - 1800) < 5

    def test_set_quick_range_24hours(self, display):
        display._set_quick_range(hours=24)
        start = display._start_dt.dateTime().toPyDateTime()
        end = display._end_dt.dateTime().toPyDateTime()
        diff = end - start
        assert abs(diff.total_seconds() - 86400) < 5

    def test_set_quick_range_1_week(self, display):
        display._set_quick_range(days=7)
        start = display._start_dt.dateTime().toPyDateTime()
        end = display._end_dt.dateTime().toPyDateTime()
        diff = end - start
        assert abs(diff.total_seconds() - 7 * 86400) < 5

    def test_get_time_range_returns_datetimes(self, display):
        start, end = display._get_time_range()
        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        assert start < end

    def test_get_time_range_raises_on_invalid(self, display):
        now = datetime.now()
        display._start_dt.setDateTime(now)
        display._end_dt.setDateTime(now - timedelta(hours=1))
        with pytest.raises(
            ValueError, match="Start time must be before end time"
        ):
            display._get_time_range()


class TestFilterChanged:
    def test_filter_with_no_results_no_crash(self, display):
        display._cb_alarms.setChecked(False)

    def test_filter_change_recalculates(self, display):
        results = [
            make_result(
                cm_name="01", cavity_num=1, alarm=10, warning=5, invalid=3
            )
        ]
        display._results = results
        display._apply_results_to_heatmap(results)

        initial_count = display._get_filtered_count(results[0])
        assert initial_count == 18

        display._cb_warnings.setChecked(False)
        new_count = display._get_filtered_count(results[0])
        assert new_count == 13


class TestFetchLifecycle:
    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.heatmap"
        ".fault_heatmap_display.QMessageBox"
    )
    def test_refresh_without_machine_shows_dialog(self, mock_msgbox, display):
        display._on_refresh_clicked()
        mock_msgbox.information.assert_called_once()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.heatmap"
        ".fault_heatmap_display.QMessageBox"
    )
    def test_refresh_with_invalid_time_range_shows_warning(
        self, mock_msgbox, display
    ):
        now = datetime.now()
        display._start_dt.setDateTime(now)
        display._end_dt.setDateTime(now - timedelta(hours=1))
        display._on_refresh_clicked()
        mock_msgbox.warning.assert_called_once()

    def test_on_fetch_progress_updates_bar(self, display):
        display._on_fetch_progress(5, 16)
        assert display._progress_bar.value() == 5
        assert display._progress_bar.maximum() == 16

    def test_on_fetch_error_shows_message(self, display):
        display._on_fetch_error("Network timeout")
        assert "Network timeout" in display._status_label.text()
        assert display._refresh_btn.isEnabled()
        assert not display._abort_btn.isEnabled()

    def test_on_fetch_error_resets_progress_bar(self, display):
        display._progress_bar.setValue(5)
        display._on_fetch_error("Error")
        assert display._progress_bar.value() == 0

    def test_set_idle_state(self, display):
        display._refresh_btn.setEnabled(False)
        display._abort_btn.setEnabled(True)
        display._start_dt.setEnabled(False)
        display._end_dt.setEnabled(False)
        display._fetcher = Mock()

        display._set_idle_state()

        assert display._refresh_btn.isEnabled()
        assert not display._abort_btn.isEnabled()
        assert display._start_dt.isEnabled()
        assert display._end_dt.isEnabled()
        assert display._fetcher is None

    def test_on_abort_clicked(self, display):
        mock_fetcher = Mock()
        display._fetcher = mock_fetcher

        display._on_abort_clicked()

        mock_fetcher.abort.assert_called_once()
        assert not display._abort_btn.isEnabled()
        assert "Aborting" in display._status_label.text()

    def test_refresh_while_fetcher_running_is_noop(self, display):
        mock_fetcher = Mock()
        mock_fetcher.isRunning.return_value = True
        display._fetcher = mock_fetcher

        display._on_refresh_clicked()

        # Should return early without creating a new fetcher
        assert display._fetcher is mock_fetcher

    def test_on_cavity_result_error_sets_error_state(self, display):
        error_result = make_error_result(
            cm_name="01", cavity_num=1, error="PV timeout"
        )
        display._on_cavity_result(error_result)
        widget = display._cm_widgets.get("01")
        if widget:
            assert "PV timeout" in widget.cavity_widgets[1].toolTip()

    def test_on_cavity_result_success_shows_pending(self, display):
        ok_result = make_result(cm_name="01", cavity_num=1, alarm=5)
        display._on_cavity_result(ok_result)
        widget = display._cm_widgets.get("01")
        if widget:
            assert "Data received" in widget.cavity_widgets[1].toolTip()

    def test_on_cavity_result_unknown_cm_no_crash(self, display):
        result = make_result(cm_name="ZZNONEXISTENT", cavity_num=1)
        display._on_cavity_result(result)


class TestOnFetchFinished:
    def test_with_valid_results(self, display):
        results = [
            make_result(
                cm_name="01", cavity_num=1, alarm=10, warning=0, invalid=0
            ),
            make_result(
                cm_name="01", cavity_num=2, alarm=0, warning=0, invalid=0
            ),
        ]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = False

        display._on_fetch_finished(results)

        status = display._status_label.text()
        assert "faulted" in status
        assert "OK" in status
        assert "Max:" in status
        assert display._refresh_btn.isEnabled()

    def test_all_errors(self, display):
        results = [
            make_error_result(cm_name="01", cavity_num=1),
            make_error_result(cm_name="01", cavity_num=2),
        ]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = False

        display._on_fetch_finished(results)

        status = display._status_label.text()
        assert "0 cavities loaded" in status
        assert "2 errors" in status

    def test_mixed_valid_and_errors_shows_error_count(self, display):
        results = [
            make_result(
                cm_name="01", cavity_num=1, alarm=10, warning=0, invalid=0
            ),
            make_error_result(cm_name="01", cavity_num=2),
        ]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = False

        display._on_fetch_finished(results)

        status = display._status_label.text()
        assert "1 errors" in status or "1 error" in status
        assert "faulted" in status

    def test_aborted_shows_in_status(self, display):
        results = [make_result(cm_name="01", cavity_num=1)]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = True

        display._on_fetch_finished(results)

        assert "(aborted)" in display._status_label.text()

    def test_status_includes_timestamp(self, display):
        results = [make_result(cm_name="01", cavity_num=1)]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = False

        display._on_fetch_finished(results)

        assert "Updated" in display._status_label.text()


class TestApplyResults:
    def test_normal_results_color_mapped(self, display):
        results = [
            make_result(cm_name="01", cavity_num=1, alarm=10),
            make_result(cm_name="01", cavity_num=2, alarm=5),
        ]
        display._apply_results_to_heatmap(results)
        assert display._color_mapper.vmax > 0

    def test_all_zero_counts_vmax_set_to_one(self, display):
        results = [
            make_result(
                cm_name="01", cavity_num=1, alarm=0, warning=0, invalid=0
            ),
        ]
        display._apply_results_to_heatmap(results)
        assert display._color_mapper.vmax == 1

    def test_all_errors_returns_early(self, display):
        results = [make_error_result(cm_name="01", cavity_num=1)]
        display._apply_results_to_heatmap(results)

    def test_highlight_threshold_applied(self, display):
        # vmax=100, threshold = ceil(0.75 * 100) = 75
        # alarm=100 >= 75 AND > 0 -> highlight=True
        # alarm=10 < 75 -> highlight=False
        results = [
            make_result(
                cm_name="01", cavity_num=1, alarm=100, warning=0, invalid=0
            ),
            make_result(
                cm_name="01", cavity_num=2, alarm=10, warning=0, invalid=0
            ),
        ]
        display._apply_results_to_heatmap(results)

        cav1 = display._cm_widgets["01"].cavity_widgets[1]
        cav2 = display._cm_widgets["01"].cavity_widgets[2]
        assert cav1._highlight is True
        assert cav2._highlight is False

    def test_highlight_threshold_ceil_boundary(self, display):
        """Verify ceil prevents false positives: vmax=3, ceil(0.75*3)=3."""
        results = [
            make_result(
                cm_name="01", cavity_num=1, alarm=3, warning=0, invalid=0
            ),
            make_result(
                cm_name="01", cavity_num=2, alarm=2, warning=0, invalid=0
            ),
        ]
        display._apply_results_to_heatmap(results)

        cav1 = display._cm_widgets["01"].cavity_widgets[1]
        cav2 = display._cm_widgets["01"].cavity_widgets[2]
        # ceil(0.75 * 3) = ceil(2.25) = 3; only 3 >= 3
        assert cav1._highlight is True
        assert cav2._highlight is False

    def test_error_result_mixed_with_valid(self, display):
        results = [
            make_result(cm_name="01", cavity_num=1, alarm=10),
            make_error_result(cm_name="01", cavity_num=2),
        ]
        display._apply_results_to_heatmap(results)
        tooltip = display._cm_widgets["01"].cavity_widgets[2].toolTip()
        assert "PV timeout" in tooltip or "Error" in tooltip

    def test_unknown_cm_name_skipped_gracefully(self, display):
        """Result for a CM not in the display layout is silently skipped."""
        results = [
            make_result(cm_name="01", cavity_num=1, alarm=10),
            make_result(cm_name="ZZNONEXISTENT", cavity_num=1, alarm=5),
        ]
        display._apply_results_to_heatmap(results)


class TestBuildTooltip:
    def test_tooltip_contains_all_info(self, display):
        result = make_result(
            cm_name="01", cavity_num=3, alarm=10, warning=5, invalid=2
        )
        tooltip = display._build_tooltip(result, filtered_count=17)
        assert "CM01" in tooltip
        assert "Cavity 3" in tooltip
        assert "10" in tooltip
        assert "5" in tooltip
        assert "2" in tooltip
        assert "17" in tooltip

    def test_tooltip_includes_total(self, display):
        """Spec §4.6: tooltip shows total = alarm + warning + invalid."""
        result = make_result(
            cm_name="01", cavity_num=1, alarm=10, warning=5, invalid=3
        )
        tooltip = display._build_tooltip(result, filtered_count=18)
        assert "Total:    18" in tooltip

    def test_tooltip_with_hl_name(self, display):
        result = make_result(
            cm_name="H1", cavity_num=5, alarm=3, warning=1, invalid=0
        )
        tooltip = display._build_tooltip(result, filtered_count=4)
        assert "H1" in tooltip
        assert "Cavity 5" in tooltip


class TestSelectionState:
    def test_initial_selection_empty(self, display):
        assert len(display._selection) == 0

    def test_cavity_click_adds_to_selection(self, display):
        display._on_cavity_clicked("01", 3)
        assert ("01", 3) in display._selection

    def test_cavity_click_toggle_removes(self, display):
        display._on_cavity_clicked("01", 3)
        display._on_cavity_clicked("01", 3)
        assert ("01", 3) not in display._selection

    def test_cavity_click_updates_widget_selected(self, display):
        display._on_cavity_clicked("01", 3)
        assert display._cm_widgets["01"].cavity_widgets[3].selected is True

    def test_cavity_click_toggle_updates_widget_deselected(self, display):
        display._on_cavity_clicked("01", 3)
        display._on_cavity_clicked("01", 3)
        assert display._cm_widgets["01"].cavity_widgets[3].selected is False

    def test_multiple_cavities_selectable(self, display):
        display._on_cavity_clicked("01", 1)
        display._on_cavity_clicked("01", 5)
        assert ("01", 1) in display._selection
        assert ("01", 5) in display._selection
        assert len(display._selection) == 2

    def test_fetch_selected_btn_enabled_after_selection(self, display):
        display._on_cavity_clicked("01", 1)
        assert display._fetch_selected_btn.isEnabled()

    def test_fetch_selected_btn_disabled_after_deselect(self, display):
        display._on_cavity_clicked("01", 1)
        display._on_cavity_clicked("01", 1)
        assert not display._fetch_selected_btn.isEnabled()

    def test_clear_selection_btn_enabled_after_selection(self, display):
        display._on_cavity_clicked("01", 1)
        assert display._clear_selection_btn.isEnabled()

    def test_clear_selection_btn_disabled_initially(self, display):
        assert not display._clear_selection_btn.isEnabled()

    def test_status_label_shows_selection_count(self, display):
        display._on_cavity_clicked("01", 1)
        assert "1 cavity selected" in display._selection_label.text()

    def test_status_label_plural_selection(self, display):
        display._on_cavity_clicked("01", 1)
        display._on_cavity_clicked("01", 2)
        assert "2 cavities selected" in display._selection_label.text()

    def test_clear_selection_resets_all(self, display):
        display._on_cavity_clicked("01", 1)
        display._on_cavity_clicked("01", 3)
        display._clear_selection()
        assert len(display._selection) == 0
        assert not display._fetch_selected_btn.isEnabled()
        assert not display._clear_selection_btn.isEnabled()

    def test_clear_selection_deselects_widgets(self, display):
        display._on_cavity_clicked("01", 1)
        display._clear_selection()
        assert display._cm_widgets["01"].cavity_widgets[1].selected is False


class TestCMLabel:
    def test_cm_label_click_selects_all_eight(self, display):
        display._on_cm_label_clicked("01")
        assert len(display._selection) == 8
        for cav_num in range(1, 9):
            assert ("01", cav_num) in display._selection

    def test_cm_label_click_all_selected_deselects(self, display):
        display._on_cm_label_clicked("01")
        display._on_cm_label_clicked("01")
        for cav_num in range(1, 9):
            assert ("01", cav_num) not in display._selection

    def test_cm_label_partial_selection_selects_all(self, display):
        display._on_cavity_clicked("01", 1)
        display._on_cavity_clicked("01", 3)
        display._on_cm_label_clicked("01")
        # Should select all 8 since not all were selected
        for cav_num in range(1, 9):
            assert ("01", cav_num) in display._selection

    def test_cm_label_updates_widgets(self, display):
        display._on_cm_label_clicked("01")
        for cav_num in range(1, 9):
            assert (
                display._cm_widgets["01"].cavity_widgets[cav_num].selected
                is True
            )

    def test_cm_label_unknown_cm_no_crash(self, display):
        display._on_cm_label_clicked("ZZNONEXISTENT")


class TestFetchSelected:
    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.heatmap"
        ".fault_heatmap_display.QMessageBox"
    )
    def test_fetch_selected_without_machine_shows_dialog(
        self, mock_msgbox, display
    ):
        display._on_cavity_clicked("01", 1)
        display._on_fetch_selected_clicked()
        mock_msgbox.information.assert_called_once()

    def test_fetch_selected_with_no_selection_is_noop(self, display):
        display._on_fetch_selected_clicked()
        # Should not crash or change state
        assert display._fetcher is None

    def test_fetch_selected_while_fetcher_running_is_noop(self, display):
        display._on_cavity_clicked("01", 1)
        mock_fetcher = Mock()
        mock_fetcher.isRunning.return_value = True
        display._fetcher = mock_fetcher
        display._on_fetch_selected_clicked()
        assert display._fetcher is mock_fetcher

    def test_result_merging_replaces_matching(self, display):
        """New fetch results for same (cm, cav) replace old ones."""
        old_result = make_result(cm_name="01", cavity_num=1, alarm=5)
        display._results = [old_result]

        new_results = [
            make_result(cm_name="01", cavity_num=1, alarm=20),
        ]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = False
        display._on_fetch_finished(new_results)

        assert len(display._results) == 1
        assert display._results[0].alarm_count == 20

    def test_result_merging_preserves_existing(self, display):
        """Existing results for non-fetched cavities are kept."""
        existing = make_result(cm_name="01", cavity_num=1, alarm=5)
        display._results = [existing]

        new_results = [
            make_result(cm_name="01", cavity_num=2, alarm=10),
        ]
        display._fetcher = Mock()
        display._fetcher.is_abort_requested = False
        display._on_fetch_finished(new_results)

        assert len(display._results) == 2
        keys = {(r.cm_name, r.cavity_num) for r in display._results}
        assert keys == {("01", 1), ("01", 2)}

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.heatmap"
        ".fault_heatmap_display.QMessageBox"
    )
    def test_load_all_clears_selection(self, mock_msgbox, display):
        """Load Faults clears the selection set before starting."""
        display._on_cavity_clicked("01", 1)
        display._on_cavity_clicked("01", 3)
        assert len(display._selection) == 2

        # _on_refresh_clicked clears selection (but won't start fetch without a machine)
        display._on_refresh_clicked()
        assert len(display._selection) == 0

    def test_partial_clear_only_clears_filtered_cavities(self, display):
        """start_fetch with filter only clears the filtered widgets."""
        r1 = make_result(cm_name="01", cavity_num=1, alarm=10)
        r2 = make_result(cm_name="01", cavity_num=2, alarm=20)
        display._results = [r1, r2]
        display._apply_results_to_heatmap([r1, r2])

        # Verify cav 2 has data before partial clear
        assert (
            display._cm_widgets["01"].cavity_widgets[2]._fault_count is not None
        )

        # Simulate a partial clear for cavity 1 only
        cavity_filter = {("01", 1)}
        display._results = [
            r
            for r in display._results
            if (r.cm_name, r.cavity_num) not in cavity_filter
        ]
        for cm_name, cav_num in cavity_filter:
            cm_w = display._cm_widgets.get(cm_name)
            if cm_w:
                cav_w = cm_w.cavity_widgets.get(cav_num)
                if cav_w:
                    cav_w.clear()

        # Cavity 1 was cleared
        assert display._cm_widgets["01"].cavity_widgets[1]._fault_count is None
        # Cavity 2 was NOT cleared
        assert (
            display._cm_widgets["01"].cavity_widgets[2]._fault_count is not None
        )
        # Results list only has cavity 2
        assert len(display._results) == 1
        assert display._results[0].cavity_num == 2


class TestCleanup:
    def test_close_with_no_fetcher(self, display):
        display.close()

    def test_close_with_running_fetcher_graceful(self, display):
        mock_fetcher = Mock()
        mock_fetcher.isRunning.return_value = True
        mock_fetcher.wait.return_value = True  # graceful stop
        display._fetcher = mock_fetcher

        display.close()

        mock_fetcher.abort.assert_called_once()
        mock_fetcher.wait.assert_called_once()
        mock_fetcher.terminate.assert_not_called()

    def test_close_with_running_fetcher_force_terminate(self, display):
        mock_fetcher = Mock()
        mock_fetcher.isRunning.return_value = True
        mock_fetcher.wait.return_value = False  # timed out
        display._fetcher = mock_fetcher

        display.close()

        mock_fetcher.abort.assert_called_once()
        mock_fetcher.terminate.assert_called_once()
        assert mock_fetcher.wait.call_count == 2


class TestDoubleClick:
    def test_double_click_without_machine_no_crash(self, display):
        display._on_cavity_double_clicked("01", 1)

    def test_double_click_calls_show_fault_display(self, display):
        machine = make_machine(num_cavities=3)
        cavity = machine.linacs[0].cryomodules["01"].cavities[1]
        cavity.show_fault_display = Mock()
        display._machine = machine
        display._on_cavity_double_clicked("01", 1)
        cavity.show_fault_display.assert_called_once()

    def test_double_click_unknown_cm_no_crash(self, display):
        machine = make_machine(num_cavities=3)
        display._machine = machine
        display._on_cavity_double_clicked("NONEXISTENT", 1)


def _make_multi_tlc_result(
    cm_name: str = "01",
    cavity_num: int = 1,
    tlc_counts: dict = None,
) -> CavityFaultResult:
    """Create a CavityFaultResult with multiple TLC entries.

    Args:
        tlc_counts: dict mapping TLC code -> (alarm, warning, invalid, ok)
    """
    if tlc_counts is None:
        tlc_counts = {"PZT": (5, 0, 0, 100), "QPT": (3, 1, 0, 200)}
    fault_counts_by_tlc = {}
    for tlc, (alarm, warning, invalid, ok) in tlc_counts.items():
        fault_counts_by_tlc[tlc] = FaultCounter(alarm, ok, invalid, warning)
    return CavityFaultResult(
        cm_name=cm_name,
        cavity_num=cavity_num,
        fault_counts_by_tlc=fault_counts_by_tlc,
    )


class TestLinacSummaryBar:
    def test_section_labels_created(self, display):
        expected_sections = set()
        for row_sections in HEATMAP_ROWS:
            for section_name, _ in row_sections:
                expected_sections.add(section_name)
        assert set(display._section_labels.keys()) == expected_sections

    def test_initial_labels_show_dash(self, display):
        for label in display._section_labels.values():
            assert "\u2014" in label.text()  # em-dash

    def test_summary_updates_after_apply(self, display):
        results = [
            make_result(cm_name="01", cavity_num=1, alarm=10),
            make_result(cm_name="01", cavity_num=2, alarm=5),
        ]
        display._results = results
        display._apply_results_to_heatmap(results)
        assert "L0B: 15" in display._section_labels["L0B"].text()

    def test_summary_ignores_errors(self, display):
        results = [
            make_result(cm_name="01", cavity_num=1, alarm=10),
            make_error_result(cm_name="01", cavity_num=2),
        ]
        display._results = results
        display._apply_results_to_heatmap(results)
        assert "L0B: 10" in display._section_labels["L0B"].text()

    def test_summary_zero_for_section_with_no_results(self, display):
        results = [
            make_result(cm_name="01", cavity_num=1, alarm=5),
        ]
        display._results = results
        display._apply_results_to_heatmap(results)
        assert "L3B: 0" in display._section_labels["L3B"].text()


class TestTLCCombo:
    def test_combo_exists_with_default(self, display):
        assert display._tlc_combo.currentText() == "All Fault Types"

    def test_combo_has_one_item_initially(self, display):
        assert display._tlc_combo.count() == 1

    def test_populate_tlc_combo(self, display):
        display._results = [
            _make_multi_tlc_result(
                cm_name="01",
                cavity_num=1,
                tlc_counts={
                    "PZT": (5, 0, 0, 100),
                    "QPT": (3, 0, 0, 200),
                    "MGT": (1, 0, 0, 50),
                },
            )
        ]
        display._populate_tlc_combo()
        items = [
            display._tlc_combo.itemText(i)
            for i in range(display._tlc_combo.count())
        ]
        assert items == ["All Fault Types", "MGT", "PZT", "QPT"]

    def test_populate_preserves_selection(self, display):
        display._results = [
            _make_multi_tlc_result(
                tlc_counts={"PZT": (5, 0, 0, 0), "QPT": (3, 0, 0, 0)}
            )
        ]
        display._populate_tlc_combo()
        display._tlc_combo.setCurrentText("PZT")

        display._populate_tlc_combo()
        assert display._tlc_combo.currentText() == "PZT"

    def test_populate_resets_to_all_if_removed(self, display):
        display._results = [
            _make_multi_tlc_result(
                tlc_counts={"PZT": (5, 0, 0, 0), "QPT": (3, 0, 0, 0)}
            )
        ]
        display._populate_tlc_combo()
        display._tlc_combo.setCurrentText("QPT")

        # Rebuild without QPT
        display._results = [
            _make_multi_tlc_result(tlc_counts={"PZT": (5, 0, 0, 0)})
        ]
        display._populate_tlc_combo()
        assert display._tlc_combo.currentText() == "All Fault Types"

    def test_get_selected_tlc_default(self, display):
        assert display._get_selected_tlc() is None

    def test_get_selected_tlc_specific(self, display):
        display._results = [
            _make_multi_tlc_result(
                tlc_counts={"PZT": (5, 0, 0, 0), "QPT": (3, 0, 0, 0)}
            )
        ]
        display._populate_tlc_combo()
        display._tlc_combo.setCurrentText("PZT")
        assert display._get_selected_tlc() == "PZT"

    def test_get_filtered_count_all_tlcs(self, display):
        result = _make_multi_tlc_result(
            tlc_counts={
                "PZT": (5, 0, 0, 100),
                "QPT": (3, 1, 0, 200),
            }
        )
        count = display._get_filtered_count(result)
        assert count == 5 + 3 + 1  # alarm + alarm + warning = 9

    def test_get_filtered_count_specific_tlc(self, display):
        result = _make_multi_tlc_result(
            tlc_counts={
                "PZT": (5, 0, 0, 100),
                "QPT": (3, 1, 0, 200),
            }
        )
        display._results = [result]
        display._populate_tlc_combo()
        display._tlc_combo.setCurrentText("PZT")
        count = display._get_filtered_count(result)
        assert count == 5  # only PZT alarms

    def test_get_filtered_count_missing_tlc(self, display):
        result = _make_multi_tlc_result(tlc_counts={"PZT": (5, 0, 0, 100)})
        # Manually add a TLC that doesn't exist in results
        display._tlc_combo.addItem("XYZ")
        display._tlc_combo.setCurrentText("XYZ")
        count = display._get_filtered_count(result)
        assert count == 0

    def test_tlc_filter_updates_heatmap(self, display):
        """Selecting a specific TLC re-colors the heatmap."""
        result = _make_multi_tlc_result(
            cm_name="01",
            cavity_num=1,
            tlc_counts={
                "PZT": (10, 0, 0, 100),
                "QPT": (2, 0, 0, 200),
            },
        )
        display._results = [result]
        display._populate_tlc_combo()

        display._apply_results_to_heatmap(display._results)
        assert display._cm_widgets["01"]._cavity_counts[1] == 12

        display._tlc_combo.setCurrentText("PZT")
        assert display._cm_widgets["01"]._cavity_counts[1] == 10
