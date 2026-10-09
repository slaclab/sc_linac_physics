"""ArchiverPlot against a real PyDMArchiverTimePlot, fake protocol."""

import os

import pytest

from sc_linac_physics.displays.plot.archiver_plot import ArchiverPlot
from sc_linac_physics.displays.plot.curve_set import Curve, CurveSet


@pytest.fixture
def plot(qtbot):
    widget = ArchiverPlot(
        CurveSet(
            title="test",
            curves=[
                Curve("fake://a1", "a1", axis="A"),
                Curve("fake://a2", "a2", axis="A", dashed=True),
                Curve("fake://b1", "b1", axis="B"),
            ],
            y_ranges={"B": (0.0, 10.0)},
        )
    )
    qtbot.addWidget(widget)
    yield widget
    widget.clear()


def axis_item(plot, name):
    return plot.plot.plotItem.axes[name]["item"]


def test_one_axis_per_name(plot):
    assert {"A", "B"} <= set(plot.plot.plotItem.axes)
    assert len(plot.plot.getYAxes()) == 2


def test_fixed_range_applied_at_creation(plot):
    assert axis_item(plot, "B").auto_range is False
    assert list(axis_item(plot, "B").range) == [0.0, 10.0]
    assert axis_item(plot, "A").auto_range is True


def test_back_to_auto_scale_after_fixed_range(plot):
    """The old plotter stayed clamped here because of setLimits."""
    plot.set_y_range("A", (1.0, 2.0))
    assert axis_item(plot, "A").auto_range is False
    view = axis_item(plot, "A").linkedView()
    assert not view.autoRangeEnabled()[1]
    plot.set_y_range("A", None)
    assert axis_item(plot, "A").auto_range is True
    # auto_range reads the linked ViewBox, but check the view directly too.
    assert view.autoRangeEnabled()[1]
    assert "A" not in plot.curve_set.y_ranges


def test_colors_stay_put_when_curves_are_added(plot):
    before = [c.color for c in plot.curve_set.curves]
    plot.add_curve(Curve("fake://c1", "c1", axis="C"))
    after = [c.color for c in plot.curve_set.curves]
    assert after[:3] == before


def test_duplicate_pv_is_skipped(plot):
    plot.add_curve(Curve("fake://a1", "again", axis="Z"))
    assert len(plot.curve_set.curves) == 3
    assert "Z" not in plot.plot.plotItem.axes


def test_removing_one_curve_leaves_others_connected(plot):
    kept = plot._items["fake://a2"]
    plot.remove_curve("fake://a1")
    assert plot._items["fake://a2"] is kept
    assert "A" in plot.plot.plotItem.axes


def test_removing_last_curve_on_axis_removes_axis(plot):
    plot.remove_curve("fake://b1")
    assert "B" not in plot.plot.plotItem.axes
    assert len(plot.plot.getYAxes()) == 1


def test_fixed_range_survives_axis_removal(plot):
    plot.remove_curve("fake://b1")
    plot.add_curve(Curve("fake://b2", "b2", axis="B"))
    assert list(axis_item(plot, "B").range) == [0.0, 10.0]


def test_clear_removes_everything(plot):
    plot.clear()
    assert plot.curve_set.curves == []
    assert plot.plot.getYAxes() == []


def test_set_curve_set_replaces_contents(plot):
    plot.set_curve_set(CurveSet(curves=[Curve("fake://x", "x", axis="X")]))
    assert [c.pv for c in plot.curve_set.curves] == ["fake://x"]
    assert len(plot.plot.getYAxes()) == 1


def test_archiver_url_defaults_to_utils_archiver(qtbot, monkeypatch):
    from sc_linac_physics.utils.archiver import ARCHIVER_BASE_URL

    monkeypatch.delenv("PYDM_ARCHIVER_URL", raising=False)
    qtbot.addWidget(ArchiverPlot())
    assert os.environ["PYDM_ARCHIVER_URL"] == ARCHIVER_BASE_URL


def test_archiver_url_already_set_is_kept(qtbot, monkeypatch):
    monkeypatch.setenv("PYDM_ARCHIVER_URL", "http://example.test")
    qtbot.addWidget(ArchiverPlot())
    assert os.environ["PYDM_ARCHIVER_URL"] == "http://example.test"


def test_curves_hold_each_sample_until_the_next(plot):
    item = plot._items["fake://a1"]
    item.archive_data_buffer[:, -1] = [1000.0, 0.0]
    item.archive_points_accumulated = 1
    item.data_buffer[:, -1] = [5000.0, 16.6]
    item.points_accumulated = 1
    item.redrawCurve()
    x, y = item.curve._generateStepModeData(
        item.curve.opts["stepMode"], *item.curve.getData(), baseline=None
    )
    # 0 holds from 1000 until 5000, then 16.6.
    assert list(zip(x, y)) == [
        (1000.0, 0.0),
        (5000.0, 0.0),
        (5000.0, 16.6),
        (5000.0, 16.6),
    ]
