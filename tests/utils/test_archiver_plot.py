import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from sc_linac_physics.utils.archiver import LOCAL_TZ  # noqa: E402
from sc_linac_physics.utils.archiver_plot import plot_over_time  # noqa: E402


def _series(name, values):
    index = pd.date_range(
        "2024-02-02 12:40", periods=len(values), freq="5min", tz=LOCAL_TZ
    )
    return pd.Series(values, index=index, name=name)


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_each_series_gets_its_own_labelled_axis():
    fig, axes = plot_over_time(
        _series("AMP", [1, 2, 3]), _series("RAD", [0, 5, 9])
    )

    assert len(axes) == 2
    assert [a.get_ylabel() for a in axes] == ["AMP", "RAD"]
    assert axes[0].lines[0].get_drawstyle() == "steps-post"


def test_ticks_are_local_time_and_date_shown_once():
    fig, (ax,) = plot_over_time(_series("AMP", [1, 2, 3, 4, 5]))
    fig.canvas.draw()

    labels = [t.get_text() for t in ax.get_xticklabels() if t.get_text()]
    assert "12:40" in labels
    assert "2024-Feb-02" in ax.xaxis.get_offset_text().get_text()


def test_draws_on_a_given_axis():
    _, given = plt.subplots()

    fig, axes = plot_over_time(_series("AMP", [1, 2]), ax=given)

    assert axes[0] is given


def test_third_axis_is_moved_out_so_labels_do_not_overlap():
    fig, axes = plot_over_time(
        _series("A", [1, 2]), _series("B", [3, 4]), _series("C", [5, 6])
    )

    assert axes[2].spines["right"].get_position() == ("outward", 60)
