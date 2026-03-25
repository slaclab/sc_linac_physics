from unittest.mock import Mock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from sc_linac_physics.displays.cavity_display.frontend.heatmap.heatmap_cm_widget import (
    HeatmapCMWidget,
    format_cm_display_name,
)


@pytest.fixture
def cm_widget():
    w = HeatmapCMWidget(cm_name="02")
    yield w
    w.deleteLater()


class TestFormatCMDisplayName:
    def test_numeric_name_gets_prefix(self):
        assert format_cm_display_name("01") == "CM01"

    def test_hl_name_stays_same(self):
        assert format_cm_display_name("H1") == "H1"

    def test_h2_stays_same(self):
        assert format_cm_display_name("H2") == "H2"

    def test_two_digit_numeric(self):
        assert format_cm_display_name("12") == "CM12"


class TestHeatmapCMWidgetInit:
    def test_creates_eight_cavity_widgets(self, cm_widget):
        assert len(cm_widget.cavity_widgets) == 8

    def test_cavity_nums_are_1_through_8(self, cm_widget):
        assert set(cm_widget.cavity_widgets.keys()) == {1, 2, 3, 4, 5, 6, 7, 8}

    def test_cm_name_property(self, cm_widget):
        assert cm_widget.cm_name == "02"

    def test_label_shows_formatted_name(self, cm_widget):
        assert cm_widget._label.text() == "CM02"


class TestUpdateCavity:
    def test_valid_cavity_num_updates(self, cm_widget):
        cm_widget.update_cavity(1, 5, QColor(255, 0, 0), "tooltip text")
        assert cm_widget.cavity_widgets[1]._fault_count == 5

    def test_valid_cavity_num_with_highlight(self, cm_widget):
        cm_widget.update_cavity(1, 5, QColor(255, 0, 0), "tip", highlight=True)
        assert cm_widget.cavity_widgets[1]._highlight is True

    def test_invalid_cavity_num_zero_ignored(self, cm_widget):
        cm_widget.update_cavity(0, 5, QColor(255, 0, 0), "tip")
        for w in cm_widget.cavity_widgets.values():
            assert w._fault_count is None

    def test_invalid_cavity_num_nine_ignored(self, cm_widget):
        cm_widget.update_cavity(9, 5, QColor(255, 0, 0), "tip")
        for w in cm_widget.cavity_widgets.values():
            assert w._fault_count is None


class TestSetCavityDataPending:
    def test_valid_cavity_shows_pending(self, cm_widget):
        cm_widget.set_cavity_data_pending(3)
        assert "Data received" in cm_widget.cavity_widgets[3].toolTip()

    def test_invalid_cavity_ignored(self, cm_widget):
        cm_widget.set_cavity_data_pending(0)
        for w in cm_widget.cavity_widgets.values():
            assert "No data loaded" in w.toolTip()


class TestSetCavityError:
    def test_sets_error_on_specific_cavity(self, cm_widget):
        cm_widget.set_cavity_error(3, "PV timeout")
        assert "PV timeout" in cm_widget.cavity_widgets[3].toolTip()

    def test_default_error_message(self, cm_widget):
        cm_widget.set_cavity_error(3)
        assert "Error loading data" in cm_widget.cavity_widgets[3].toolTip()

    def test_invalid_cavity_ignored(self, cm_widget):
        cm_widget.set_cavity_error(0, "err")
        # Verify no existing cavity was modified
        for w in cm_widget.cavity_widgets.values():
            assert "No data loaded" in w.toolTip()


class TestClearAll:
    def test_clear_all_resets_all_cavities(self, cm_widget):
        cm_widget.update_cavity(1, 10, QColor(255, 0, 0), "tip")
        cm_widget.update_cavity(5, 20, QColor(0, 0, 255), "tip")
        cm_widget.clear_all()
        for w in cm_widget.cavity_widgets.values():
            assert "No data loaded" in w.toolTip()


class TestClickableCMLabel:
    def test_cm_label_click_emits_signal(self, cm_widget):
        spy = Mock()
        cm_widget.cm_label_clicked.connect(spy)
        cm_widget._label.clicked.emit()
        spy.assert_called_once_with("02")

    def test_label_has_pointing_hand_cursor(self, cm_widget):
        assert cm_widget._label.cursor().shape() == Qt.PointingHandCursor


class TestSelectionMethods:
    def test_set_cavity_selected(self, cm_widget):
        cm_widget.set_cavity_selected(3, True)
        assert cm_widget.cavity_widgets[3].selected is True

    def test_set_cavity_selected_invalid_ignored(self, cm_widget):
        cm_widget.set_cavity_selected(0, True)
        for w in cm_widget.cavity_widgets.values():
            assert w.selected is False

    def test_select_all(self, cm_widget):
        cm_widget.select_all()
        for w in cm_widget.cavity_widgets.values():
            assert w.selected is True

    def test_deselect_all(self, cm_widget):
        cm_widget.select_all()
        cm_widget.deselect_all()
        for w in cm_widget.cavity_widgets.values():
            assert w.selected is False

    def test_all_selected_true(self, cm_widget):
        cm_widget.select_all()
        assert cm_widget.all_selected() is True

    def test_all_selected_false_when_partial(self, cm_widget):
        cm_widget.set_cavity_selected(1, True)
        assert cm_widget.all_selected() is False

    def test_clear_all_resets_selection(self, cm_widget):
        cm_widget.select_all()
        cm_widget.clear_all()
        assert cm_widget.all_selected() is False


class TestSignalPropagation:
    def test_cavity_click_propagates(self, cm_widget):
        spy = Mock()
        cm_widget.cavity_clicked.connect(spy)

        cm_widget.cavity_widgets[5].clicked.emit(5)
        spy.assert_called_once_with("02", 5)


class TestDoubleClickPropagation:
    def test_cavity_double_click_propagates(self, cm_widget):
        spy = Mock()
        cm_widget.cavity_double_clicked.connect(spy)

        cm_widget.cavity_widgets[5].double_clicked.emit(5)
        spy.assert_called_once_with("02", 5)


class TestSetScale:
    def test_set_scale_updates_label_font(self, cm_widget):
        cm_widget.set_scale(2.0)
        assert cm_widget._label.font().pointSize() == 18


class TestFaultTracking:
    def test_update_cavity_stores_count(self, cm_widget):
        cm_widget.update_cavity(1, 5, QColor(255, 0, 0), "tip")
        assert cm_widget._cavity_counts[1] == 5

    def test_label_shows_total(self, cm_widget):
        cm_widget.update_cavity(1, 5, QColor(255, 0, 0), "tip")
        cm_widget.update_cavity(2, 10, QColor(255, 0, 0), "tip")
        assert cm_widget._label.text() == "CM02 (15)"

    def test_label_no_data(self, cm_widget):
        assert cm_widget._label.text() == "CM02"

    def test_bar_no_data_color(self, cm_widget):
        assert cm_widget._last_bar_color == HeatmapCMWidget.BAR_NO_DATA_COLOR

    def test_bar_ok_color(self, cm_widget):
        cm_widget.update_cavity(1, 0, QColor(0, 0, 0), "tip")
        assert cm_widget._last_bar_color == HeatmapCMWidget.BAR_OK_COLOR

    def test_bar_faulted_color(self, cm_widget):
        cm_widget.update_cavity(1, 5, QColor(255, 0, 0), "tip")
        assert cm_widget._last_bar_color == HeatmapCMWidget.BAR_FAULTED_COLOR

    def test_bar_critical_color(self, cm_widget):
        cm_widget.update_cavity(1, 50, QColor(255, 0, 0), "tip", highlight=True)
        assert cm_widget._last_bar_color == HeatmapCMWidget.BAR_CRITICAL_COLOR

    def test_clear_resets_tracking(self, cm_widget):
        cm_widget.update_cavity(1, 10, QColor(255, 0, 0), "tip", highlight=True)
        cm_widget.clear_all()
        assert cm_widget._cavity_counts == {}
        assert cm_widget._has_highlight is False
        assert cm_widget._label.text() == "CM02"
        assert cm_widget._last_bar_color == HeatmapCMWidget.BAR_NO_DATA_COLOR

    def test_invalid_cavity_does_not_track(self, cm_widget):
        cm_widget.update_cavity(0, 5, QColor(255, 0, 0), "tip")
        assert cm_widget._cavity_counts == {}
