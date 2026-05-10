from PyQt5.QtGui import QColor

from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_mapper import (
    ColorMapper,
)


class TestColorMapperInit:
    def test_default_range(self):
        mapper = ColorMapper()
        assert mapper.vmin == 0.0
        assert mapper.vmax == 1.0

    def test_custom_range(self, color_mapper):
        assert color_mapper.vmin == 0.0
        assert color_mapper.vmax == 100.0

    def test_default_stops_exist(self):
        stops = ColorMapper.DEFAULT_STOPS
        assert isinstance(stops, list)
        assert len(stops) == 6
        for pos, color in stops:
            assert isinstance(pos, float)
            assert isinstance(color, QColor)

    def test_custom_stops(self):
        stops = [
            (0.0, QColor(0, 0, 0)),
            (1.0, QColor(255, 255, 255)),
        ]
        mapper = ColorMapper(vmin=0, vmax=100, stops=stops)
        color = mapper.get_color(50)
        assert color.red() == 127
        assert color.green() == 127
        assert color.blue() == 127


class TestSetRange:
    def test_updates_properties(self, color_mapper):
        color_mapper.set_range(5, 50)
        assert color_mapper.vmin == 5
        assert color_mapper.vmax == 50

    def test_equal_values(self):
        mapper = ColorMapper()
        mapper.set_range(5.0, 5.0)
        assert mapper.vmin == 5.0
        assert mapper.vmax == 5.0

    def test_negative_values(self):
        mapper = ColorMapper()
        mapper.set_range(-10.0, 10.0)
        assert mapper.vmin == -10.0
        assert mapper.vmax == 10.0


class TestColorMapperGradient:
    def test_color_at_vmin_is_dark_purple(self, color_mapper):
        color = color_mapper.get_color(0)
        assert color.red() == 68
        assert color.green() == 1
        assert color.blue() == 84

    def test_color_at_vmax_is_bright_yellow(self, color_mapper):
        color = color_mapper.get_color(100)
        assert color.red() == 253
        assert color.green() == 231
        assert color.blue() == 37

    def test_color_returns_qcolor_instance(self, color_mapper):
        assert isinstance(color_mapper.get_color(50), QColor)

    def test_color_monotonically_warms(self, color_mapper):
        """Green channel should monotonically non-decrease from vmin to vmax (viridis)."""
        prev_green = 0
        for val in [0, 20, 40, 60, 80, 100]:
            color = color_mapper.get_color(val)
            assert color.green() >= prev_green
            prev_green = color.green()

    def test_color_at_stop_boundary(self, color_mapper):
        # normalized=0.2 on [0,100] -> value=20 -> blue-purple stop
        color = color_mapper.get_color(20)
        assert color.red() == 65
        assert color.green() == 68
        assert color.blue() == 135


class TestColorMapperEdgeCases:
    def test_vmin_equals_vmax_returns_dark_purple(self):
        mapper = ColorMapper(vmin=50.0, vmax=50.0)
        color = mapper.get_color(50)
        # _normalize returns 0.0, which maps to first stop (dark purple)
        assert color.red() == 68
        assert color.green() == 1
        assert color.blue() == 84

    def test_value_below_range_clamps_to_dark_purple(self, color_mapper):
        color = color_mapper.get_color(-10)
        assert color.red() == 68
        assert color.green() == 1
        assert color.blue() == 84

    def test_value_above_range_clamps_to_yellow(self, color_mapper):
        color = color_mapper.get_color(200)
        assert color.red() == 253
        assert color.green() == 231
        assert color.blue() == 37

    def test_nan_value_returns_dark_purple(self, color_mapper):
        # _normalize returns 0.0 for NaN -> maps to first stop
        color = color_mapper.get_color(float("nan"))
        assert color.red() == 68
        assert color.green() == 1
        assert color.blue() == 84

    def test_inf_value_returns_dark_purple(self, color_mapper):
        # _normalize returns 0.0 for inf -> maps to first stop
        color = color_mapper.get_color(float("inf"))
        assert color.red() == 68
        assert color.green() == 1
        assert color.blue() == 84

    def test_negative_inf_value_returns_dark_purple(self, color_mapper):
        # _normalize returns 0.0 for -inf -> maps to first stop
        color = color_mapper.get_color(float("-inf"))
        assert color.red() == 68
        assert color.green() == 1
        assert color.blue() == 84

    def test_set_range_inverted_swaps(self):
        mapper = ColorMapper()
        mapper.set_range(100.0, 10.0)
        assert mapper.vmin == 10.0
        assert mapper.vmax == 100.0

    def test_set_range_inverted_colors_correct(self):
        mapper = ColorMapper()
        mapper.set_range(50.0, 0.0)
        # After swap: vmin=0, vmax=50
        color_low = mapper.get_color(0)
        assert color_low.red() == 68  # dark purple at low end
        color_high = mapper.get_color(50)
        assert color_high.red() == 253  # yellow at high end


class TestColorMapperLogScale:
    def test_log_scale_property(self):
        mapper = ColorMapper(log_scale=True)
        assert mapper.log_scale is True

    def test_log_scale_default_false(self):
        mapper = ColorMapper()
        assert mapper.log_scale is False

    def test_log_zero_is_dark_purple(self):
        mapper = ColorMapper(vmin=0, vmax=10000, log_scale=True)
        color = mapper.get_color(0)
        assert color.red() == 68  # dark purple

    def test_log_vmax_is_yellow(self):
        mapper = ColorMapper(vmin=0, vmax=10000, log_scale=True)
        color = mapper.get_color(10000)
        assert color.red() == 253  # bright yellow

    def test_log_spreads_mid_values(self):
        log_mapper = ColorMapper(vmin=0, vmax=10000, log_scale=True)
        lin_mapper = ColorMapper(vmin=0, vmax=10000, log_scale=False)

        log_color = log_mapper.get_color(100)
        lin_color = lin_mapper.get_color(100)

        assert log_color.green() > lin_color.green() + 50

    def test_log_monotonically_warms(self):
        """Green channel should monotonically non-decrease as values increase."""
        mapper = ColorMapper(vmin=0, vmax=10000, log_scale=True)
        values = [0, 1, 10, 100, 1000, 10000]
        greens = [mapper.get_color(v).green() for v in values]
        for i in range(len(greens) - 1):
            assert greens[i] <= greens[i + 1]
