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
    on_window_changed = Mock()
    return FitRegions(plot_widget, button, on_window_changed)


def _regions_on_plot(fit_regions):
    return [
        item
        for item in fit_regions.plot_widget.getPlotItem().items
        if isinstance(item, LinearRegionItem)
    ]


def test_regions_start_hidden(regions, run):
    regions.set_runs([run])
    assert _regions_on_plot(regions) == []
    assert regions.button.text() == FitRegions.SHOW_TEXT


def test_show_adds_one_region_per_run_spanning_its_data(regions, run):
    regions.set_runs([run])
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    assert region.getRegion() == pytest.approx((10.0, 30.0))
    assert regions.button.text() == FitRegions.HIDE_TEXT


def test_region_starts_at_existing_window(regions, run):
    run.fit_window = (15.0, 25.0)
    regions.set_runs([run])
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    assert region.getRegion() == pytest.approx((15.0, 25.0))


def test_drag_finish_reports_window(regions, run):
    regions.set_runs([run])
    regions.button.click()
    (region,) = _regions_on_plot(regions)
    region.setRegion((12.0, 28.0))
    region.sigRegionChangeFinished.emit(region)
    regions.on_window_changed.assert_called_with(run, (12.0, 28.0))


def test_hide_removes_regions_and_clears_windows(regions, run):
    other = q0_utils.DataRun()
    other.ll_data = {0.0: 95.0, 1.0: 94.0}
    run.fit_window = (15.0, 25.0)
    regions.set_runs([run, other])
    regions.button.click()
    regions.button.click()
    assert _regions_on_plot(regions) == []
    # Only the windowed run needs clearing
    regions.on_window_changed.assert_called_once_with(run, None)
    assert regions.button.text() == FitRegions.SHOW_TEXT


def test_set_runs_replaces_shown_regions(regions, run):
    regions.set_runs([run])
    regions.button.click()
    other = q0_utils.DataRun()
    other.ll_data = {0.0: 95.0, 1.0: 94.0}
    regions.set_runs([other])
    (region,) = _regions_on_plot(regions)
    assert region.getRegion() == pytest.approx((0.0, 1.0))


def test_run_without_data_gets_no_region(regions):
    regions.set_runs([q0_utils.DataRun()])
    regions.button.click()
    assert _regions_on_plot(regions) == []
