from sc_linac_physics.displays.plot.curve_set import Curve, CurveSet, nth_color


def test_nth_color_does_not_depend_on_curve_count():
    """A curve keeps its color when more curves are added after it."""
    first_five = [nth_color(n) for n in range(5)]
    first_fifty = [nth_color(n) for n in range(50)]
    assert first_fifty[:5] == first_five


def test_consecutive_colors_differ():
    colors = [nth_color(n) for n in range(20)]
    assert len(set(colors)) == len(colors)


def test_axis_names_in_first_appearance_order():
    curve_set = CurveSet(
        curves=[
            Curve("A", "a", axis="Y2"),
            Curve("B", "b", axis="Y1"),
            Curve("C", "c", axis="Y2"),
        ]
    )
    assert curve_set.axis_names == ["Y2", "Y1"]
