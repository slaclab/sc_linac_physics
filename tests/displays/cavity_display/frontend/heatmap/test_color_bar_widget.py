import pytest

from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_bar_widget import (
    ColorBarWidget,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_mapper import (
    ColorMapper,
)


@pytest.fixture
def color_bar(color_mapper):
    w = ColorBarWidget(color_mapper=color_mapper, title="Faults", num_ticks=5)
    yield w
    w.deleteLater()


class TestColorBarInit:
    def test_creates_with_color_mapper(self, color_bar):
        assert color_bar._vmin == 0.0
        assert color_bar._vmax == 100.0

    def test_creates_with_none_mapper(self):
        w = ColorBarWidget(color_mapper=None, title="Test")
        assert w._vmin == 0.0
        assert w._vmax == 1.0
        w.deleteLater()

    def test_num_ticks_clamped_to_min_2(self):
        w = ColorBarWidget(num_ticks=0)
        assert w._num_ticks == 2
        w.deleteLater()

    def test_num_ticks_1_clamped_to_2(self):
        w = ColorBarWidget(num_ticks=1)
        assert w._num_ticks == 2
        w.deleteLater()

    def test_title_stored(self, color_bar):
        assert color_bar._title == "Faults"


class TestTickValues:
    def test_five_ticks_on_0_to_100(self, color_bar):
        ticks = color_bar._get_tick_values()
        assert len(ticks) == 5
        assert ticks[0] == 100.0
        assert ticks[-1] == 0.0
        assert ticks[2] == 50.0

    def test_vmin_equals_vmax(self):
        mapper = ColorMapper(vmin=50.0, vmax=50.0)
        w = ColorBarWidget(color_mapper=mapper, num_ticks=5)
        ticks = w._get_tick_values()
        assert ticks == [50.0, 50.0]
        w.deleteLater()

    def test_two_ticks_endpoints_only(self):
        mapper = ColorMapper(vmin=0.0, vmax=100.0)
        w = ColorBarWidget(color_mapper=mapper, num_ticks=2)
        ticks = w._get_tick_values()
        assert len(ticks) == 2
        assert ticks[0] == 100.0
        assert ticks[1] == 0.0
        w.deleteLater()

    def test_three_ticks_correct_spacing(self):
        mapper = ColorMapper(vmin=0.0, vmax=100.0)
        w = ColorBarWidget(color_mapper=mapper, num_ticks=3)
        ticks = w._get_tick_values()
        assert len(ticks) == 3
        assert ticks[0] == 100.0
        assert ticks[1] == 50.0
        assert ticks[2] == 0.0
        w.deleteLater()


class TestTickLabels:
    def test_integer_range(self, color_bar):
        assert color_bar._format_tick_label(75.0) == "75"
        assert color_bar._format_tick_label(0.0) == "0"
        assert color_bar._format_tick_label(100.0) == "100"

    def test_fractional_range(self):
        mapper = ColorMapper(vmin=0.0, vmax=0.5)
        w = ColorBarWidget(color_mapper=mapper)
        assert w._format_tick_label(0.25) == "0.2"
        w.deleteLater()

    def test_boundary_range_exactly_one(self):
        mapper = ColorMapper(vmin=0.0, vmax=1.0)
        w = ColorBarWidget(color_mapper=mapper)
        # range == 1.0, so >= 1.0 condition is met -> integer format
        assert w._format_tick_label(0.5) == "0"
        w.deleteLater()


class TestUpdateRange:
    def test_reads_new_values_from_mapper(self, color_bar):
        color_bar._color_mapper.set_range(0, 200)
        color_bar.update_range()
        assert color_bar._vmin == 0
        assert color_bar._vmax == 200

    def test_update_range_without_mapper_no_crash(self):
        w = ColorBarWidget(color_mapper=None)
        w.update_range()
        w.deleteLater()


class TestPaintEdgeCases:
    def test_no_crash_with_none_mapper(self):
        w = ColorBarWidget(color_mapper=None)
        w.resize(60, 200)
        w.repaint()
        w.deleteLater()

    def test_no_crash_at_tiny_size(self, color_bar):
        color_bar.resize(5, 5)
        color_bar.repaint()
