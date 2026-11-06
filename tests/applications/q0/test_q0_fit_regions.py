from unittest.mock import Mock

import pytest
from PyQt5.QtWidgets import QPushButton
from pyqtgraph import LinearRegionItem, PlotWidget

from sc_linac_physics.applications.q0 import q0_utils
from sc_linac_physics.applications.q0.q0_fit_regions import FitRegions


@pytest.fixture
def run():
    data_run = q0_utils.DataRun()
    data_run.ll_data = {10.0: 95.0, 20.0: 94.0, 30.0: 93.0}
    return data_run


@pytest.fixture
def regions(qtbot):
    plot_widget = PlotWidget()
    button = QPushButton()
    qtbot.addWidget(plot_widget)
    qtbot.addWidget(button)
    fit_regions = FitRegions(plot_widget, button)
    fit_regions.on_window_changed = Mock()
    return fit_regions


def _regions_on_plot(fit_regions):
    return [
        item
        for item in fit_regions.plot_widget.getPlotItem().items
        if isinstance(item, LinearRegionItem)
    ]


def test_regions_start_hidden(regions, run):
    regions.set_runs([run], regions.on_window_changed)
    assert _regions_on_plot(regions) == []
    assert regions.button.text() == FitRegions.SHOW_TEXT


def test_show_adds_one_region_per_run_spanning_its_data(regions, run):
    regions.set_runs([run], regions.on_window_changed)
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    assert region.getRegion() == pytest.approx((10.0, 30.0))
    assert regions.button.text() == FitRegions.HIDE_TEXT


def test_region_starts_at_existing_window(regions, run):
    run.fit_window = (10.0, 20.0)
    regions.set_runs([run], regions.on_window_changed)
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    assert region.getRegion() == pytest.approx((10.0, 20.0))


def test_drag_finish_reports_window(regions, run):
    regions.set_runs([run], regions.on_window_changed)
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    # setRegion emits sigRegionChangeFinished, as the end of a drag does
    region.setRegion((12.0, 28.0))
    regions.on_window_changed.assert_called_once_with(run, (12.0, 28.0))


def test_hide_removes_regions_and_clears_windows(regions, run):
    other = q0_utils.DataRun()
    other.ll_data = {0.0: 95.0, 1.0: 94.0}
    run.fit_window = (10.0, 20.0)
    regions.set_runs([run, other], regions.on_window_changed)
    regions.button.click()
    regions.button.click()
    assert _regions_on_plot(regions) == []
    # Only the windowed run needs clearing
    regions.on_window_changed.assert_called_once_with(run, None)
    assert regions.button.text() == FitRegions.SHOW_TEXT


def test_set_runs_replaces_shown_regions(regions, run):
    regions.set_runs([run], regions.on_window_changed)
    regions.button.click()
    other = q0_utils.DataRun()
    other.ll_data = {0.0: 95.0, 1.0: 94.0}
    regions.set_runs([other], regions.on_window_changed)
    (region,) = _regions_on_plot(regions)
    assert region.getRegion() == pytest.approx((0.0, 1.0))


def test_run_without_data_gets_no_region(regions):
    regions.set_runs([q0_utils.DataRun()], regions.on_window_changed)
    regions.button.click()
    assert _regions_on_plot(regions) == []


def test_refused_drag_snaps_region_back(regions, run):
    # The owner rejects a window holding fewer than two samples; the
    # region must go back to the window actually in use.
    run.fit_window = (10.0, 20.0)
    regions.set_runs([run], regions.on_window_changed)
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    region.setRegion((11.0, 12.0))
    assert region.getRegion() == pytest.approx((10.0, 20.0))


def test_accepted_drag_keeps_region(regions, run):
    def accept(r, window):
        r.fit_window = window

    regions.set_runs([run], accept)
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    region.setRegion((10.0, 25.0))
    assert region.getRegion() == pytest.approx((10.0, 25.0))


def test_set_runs_clears_dropped_runs_through_their_owner(regions, run):
    # Trim CM01, then show CM02: CM01's window is cleared through CM01's
    # callback, so it isn't left active with no region on screen.
    old_owner = Mock()
    run.fit_window = (10.0, 20.0)
    regions.set_runs([run], old_owner)
    other = q0_utils.DataRun()
    other.ll_data = {0.0: 95.0, 1.0: 94.0}
    new_owner = Mock()

    regions.set_runs([other], new_owner)

    old_owner.assert_called_once_with(run, None)
    new_owner.assert_not_called()


def test_set_runs_keeps_windows_of_runs_passed_again(regions, run):
    owner = Mock()
    run.fit_window = (10.0, 20.0)
    regions.set_runs([run], owner)
    regions.set_runs([run], owner)
    owner.assert_not_called()
