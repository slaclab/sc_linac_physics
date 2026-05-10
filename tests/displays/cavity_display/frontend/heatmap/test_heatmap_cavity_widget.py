from unittest.mock import Mock

import pytest
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QMouseEvent

from sc_linac_physics.displays.cavity_display.frontend.heatmap.heatmap_cavity_widget import (
    HeatmapCavityWidget,
)


@pytest.fixture
def cavity_widget():
    w = HeatmapCavityWidget(cavity_num=3)
    yield w
    w.deleteLater()


class TestHeatmapCavityWidgetInit:
    def test_cavity_num_property(self, cavity_widget):
        assert cavity_widget.cavity_num == 3

    def test_initial_tooltip(self, cavity_widget):
        assert "Cavity 3" in cavity_widget.toolTip()
        assert "No data loaded" in cavity_widget.toolTip()

    def test_initial_color_is_default(self, cavity_widget):
        assert cavity_widget._color == HeatmapCavityWidget.DEFAULT_COLOR

    def test_initial_fault_count_is_none(self, cavity_widget):
        assert cavity_widget._fault_count is None

    def test_initial_highlight_is_false(self, cavity_widget):
        assert cavity_widget._highlight is False

    def test_cursor_is_pointing_hand(self, cavity_widget):
        assert cavity_widget.cursor().shape() == Qt.PointingHandCursor


class TestSetFaultData:
    def test_tooltip_updated(self, cavity_widget):
        cavity_widget.set_fault_data(
            42, QColor(255, 0, 0), "CM01 Cav 3\nAlarms: 42"
        )
        assert "CM01 Cav 3" in cavity_widget.toolTip()
        assert "Alarms: 42" in cavity_widget.toolTip()

    def test_state_stored(self, cavity_widget):
        cavity_widget.set_fault_data(
            10, QColor(128, 0, 255), "tip", highlight=True
        )
        assert cavity_widget._fault_count == 10
        assert cavity_widget._color.red() == 128
        assert cavity_widget._highlight is True

    def test_highlight_defaults_false(self, cavity_widget):
        cavity_widget.set_fault_data(5, QColor(0, 0, 255), "tip")
        assert cavity_widget._highlight is False


class TestDataPending:
    def test_data_pending_changes_color(self, cavity_widget):
        cavity_widget.set_data_pending()
        assert cavity_widget._color == HeatmapCavityWidget.DATA_PENDING_COLOR

    def test_data_pending_tooltip(self, cavity_widget):
        cavity_widget.set_data_pending()
        assert "Data received" in cavity_widget.toolTip()

    def test_data_pending_clears_highlight(self, cavity_widget):
        cavity_widget.set_fault_data(
            10, QColor(255, 0, 0), "tip", highlight=True
        )
        cavity_widget.set_data_pending()
        assert cavity_widget._highlight is False

    def test_paint_after_data_pending_no_crash(self, cavity_widget):
        cavity_widget.set_data_pending()
        cavity_widget.resize(30, 30)
        cavity_widget.repaint()


class TestErrorAndClear:
    def test_error_state_sets_tooltip(self, cavity_widget):
        cavity_widget.set_error_state("PV disconnected")
        assert "PV disconnected" in cavity_widget.toolTip()
        assert "Cavity 3" in cavity_widget.toolTip()

    def test_error_state_resets_color(self, cavity_widget):
        cavity_widget.set_fault_data(10, QColor(255, 0, 0), "tip")
        cavity_widget.set_error_state()
        assert cavity_widget._color == HeatmapCavityWidget.DEFAULT_COLOR

    def test_clear_resets_to_no_data(self, cavity_widget):
        cavity_widget.set_fault_data(
            10, QColor(255, 0, 0), "tip", highlight=True
        )
        cavity_widget.clear()
        assert "No data loaded" in cavity_widget.toolTip()
        assert cavity_widget._fault_count is None
        assert cavity_widget._highlight is False
        assert cavity_widget._color == HeatmapCavityWidget.DEFAULT_COLOR


class TestTextColor:
    def test_dark_background_gets_white_text(self, cavity_widget):
        cavity_widget._color = QColor(0, 0, 128)
        text_color = cavity_widget._get_text_color()
        assert text_color.red() == 255
        assert text_color.green() == 255
        assert text_color.blue() == 255

    def test_light_background_gets_black_text(self, cavity_widget):
        cavity_widget._color = QColor(255, 255, 200)
        text_color = cavity_widget._get_text_color()
        assert text_color.red() == 0
        assert text_color.green() == 0
        assert text_color.blue() == 0


class TestPaintEvent:
    def test_paint_default_no_crash(self, cavity_widget):
        cavity_widget.resize(30, 30)
        cavity_widget.repaint()

    def test_paint_with_highlight_no_crash(self, cavity_widget):
        cavity_widget.set_fault_data(
            10, QColor(255, 0, 0), "tip", highlight=True
        )
        cavity_widget.resize(30, 30)
        cavity_widget.repaint()

    def test_paint_after_error_state_no_crash(self, cavity_widget):
        cavity_widget.set_error_state("test error")
        cavity_widget.resize(30, 30)
        cavity_widget.repaint()


class TestClickSignal:
    def test_left_click_emits_signal(self, cavity_widget):
        spy = Mock()
        cavity_widget.clicked.connect(spy)

        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPoint(10, 10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        cavity_widget.mousePressEvent(event)
        spy.assert_called_once_with(3)


class TestSelection:
    def test_initial_selection_is_false(self, cavity_widget):
        assert cavity_widget.selected is False

    def test_set_selected_true(self, cavity_widget):
        cavity_widget.set_selected(True)
        assert cavity_widget.selected is True

    def test_set_selected_false(self, cavity_widget):
        cavity_widget.set_selected(True)
        cavity_widget.set_selected(False)
        assert cavity_widget.selected is False

    def test_clear_resets_selection(self, cavity_widget):
        cavity_widget.set_selected(True)
        cavity_widget.clear()
        assert cavity_widget.selected is False

    def test_paint_with_selection_no_crash(self, cavity_widget):
        cavity_widget.set_selected(True)
        cavity_widget.resize(30, 30)
        cavity_widget.repaint()

    def test_selected_border_color_is_distinct(self, cavity_widget):
        assert cavity_widget.SELECTED_BORDER_COLOR != cavity_widget.BORDER_COLOR
        assert (
            cavity_widget.SELECTED_BORDER_COLOR
            != cavity_widget.HIGHLIGHT_BORDER_COLOR
        )


class TestClickSignalFull:
    def test_right_click_does_not_emit(self, cavity_widget):
        spy = Mock()
        cavity_widget.clicked.connect(spy)

        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPoint(10, 10),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        cavity_widget.mousePressEvent(event)
        spy.assert_not_called()


class TestDoubleClickSignal:
    def test_left_double_click_emits_signal(self, cavity_widget):
        spy = Mock()
        cavity_widget.double_clicked.connect(spy)

        event = QMouseEvent(
            QMouseEvent.MouseButtonDblClick,
            QPoint(10, 10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        cavity_widget.mouseDoubleClickEvent(event)
        spy.assert_called_once_with(3)

    def test_right_double_click_does_not_emit(self, cavity_widget):
        spy = Mock()
        cavity_widget.double_clicked.connect(spy)

        event = QMouseEvent(
            QMouseEvent.MouseButtonDblClick,
            QPoint(10, 10),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        cavity_widget.mouseDoubleClickEvent(event)
        spy.assert_not_called()


class TestSizePolicy:
    def test_expanding_horizontal(self, cavity_widget):
        from PyQt5.QtWidgets import QSizePolicy

        assert (
            cavity_widget.sizePolicy().horizontalPolicy()
            == QSizePolicy.Expanding
        )

    def test_expanding_vertical(self, cavity_widget):
        from PyQt5.QtWidgets import QSizePolicy

        assert (
            cavity_widget.sizePolicy().verticalPolicy() == QSizePolicy.Expanding
        )
