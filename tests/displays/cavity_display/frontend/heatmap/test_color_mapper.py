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

    def test_class_color_constants(self):
        assert ColorMapper.COLOR_LOW == QColor(0, 0, 255)
        assert ColorMapper.COLOR_MID == QColor(255, 255, 255)
        assert ColorMapper.COLOR_HIGH == QColor(255, 0, 0)


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
    def test_color_at_vmin_is_blue(self, color_mapper):
        color = color_mapper.get_color(0)
        assert color.red() == 0
        assert color.green() == 0
        assert color.blue() == 255

    def test_color_at_vmax_is_red(self, color_mapper):
        color = color_mapper.get_color(100)
        assert color.red() == 255
        assert color.green() == 0
        assert color.blue() == 0

    def test_color_at_midpoint_is_white(self, color_mapper):
        # normalized=0.5, takes the <= 0.5 branch with t=1.0 -> white
        color = color_mapper.get_color(50)
        assert color.red() == 255
        assert color.green() == 255
        assert color.blue() == 255

    def test_color_below_midpoint_exact_values(self, color_mapper):
        # value=25 on [0,100]: normalized=0.25, t=0.50
        color = color_mapper.get_color(25)
        assert color.red() == 127
        assert color.green() == 127
        assert color.blue() == 255

    def test_color_above_midpoint_exact_values(self, color_mapper):
        # value=75 on [0,100]: normalized=0.75, t=0.50
        color = color_mapper.get_color(75)
        assert color.red() == 255
        assert color.green() == 127
        assert color.blue() == 127

    def test_color_returns_qcolor_instance(self, color_mapper):
        assert isinstance(color_mapper.get_color(50), QColor)

    def test_color_with_negative_range(self):
        mapper = ColorMapper(vmin=-10.0, vmax=10.0)
        # midpoint=0.0 should be white
        color = mapper.get_color(0.0)
        assert color.red() == 255
        assert color.green() == 255
        assert color.blue() == 255


class TestColorMapperEdgeCases:
    def test_vmin_equals_vmax_returns_blue(self):
        mapper = ColorMapper(vmin=50.0, vmax=50.0)
        color = mapper.get_color(50)
        # _normalize returns 0.0, which maps to COLOR_LOW (blue)
        assert color.red() == 0
        assert color.blue() == 255

    def test_value_below_range_clamps_to_blue(self, color_mapper):
        color = color_mapper.get_color(-10)
        assert color.red() == 0
        assert color.blue() == 255

    def test_value_above_range_clamps_to_red(self, color_mapper):
        color = color_mapper.get_color(200)
        assert color.red() == 255
        assert color.blue() == 0

    def test_nan_value_returns_blue(self, color_mapper):
        # _normalize returns 0.0 for NaN -> maps to COLOR_LOW (blue)
        color = color_mapper.get_color(float("nan"))
        assert color.red() == 0
        assert color.green() == 0
        assert color.blue() == 255

    def test_inf_value_returns_blue(self, color_mapper):
        # _normalize returns 0.0 for inf -> maps to COLOR_LOW (blue)
        color = color_mapper.get_color(float("inf"))
        assert color.red() == 0
        assert color.green() == 0
        assert color.blue() == 255

    def test_negative_inf_value_returns_blue(self, color_mapper):
        # _normalize returns 0.0 for -inf -> maps to COLOR_LOW (blue)
        color = color_mapper.get_color(float("-inf"))
        assert color.red() == 0
        assert color.green() == 0
        assert color.blue() == 255

    def test_set_range_inverted_swaps(self):
        mapper = ColorMapper()
        mapper.set_range(100.0, 10.0)
        assert mapper.vmin == 10.0
        assert mapper.vmax == 100.0

    def test_set_range_inverted_colors_correct(self):
        mapper = ColorMapper()
        mapper.set_range(50.0, 0.0)
        # After swap: vmin=0, vmax=50
        color = mapper.get_color(0)
        assert color.blue() == 255  # low end = blue
        color = mapper.get_color(50)
        assert color.red() == 255  # high end = red
