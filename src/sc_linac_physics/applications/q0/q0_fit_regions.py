from typing import Callable, List, Optional, Tuple

from PyQt5.QtWidgets import QPushButton
from pyqtgraph import LinearRegionItem, PlotWidget

from sc_linac_physics.applications.q0 import q0_utils

FitWindowCallback = Callable[
    [q0_utils.DataRun, Optional[Tuple[float, float]]], None
]


class FitRegions:
    """One draggable region per run on a liquid level plot.

    set_runs takes the runs and the callback of the Calibration or
    Q0Measurement that owns them. Dragging a region's edges reports that
    run's new fit window through on_window_changed(run, (lo, hi)) when the
    drag finishes. The owner passes it on to its set_fit_window.

    Hiding the regions clears every window (on_window_changed(run, None)),
    so a fit to part of a run is only in use while its region is on screen.
    For the same reason set_runs clears the windows of runs it drops,
    through the callback they came with. Nothing here saves a window.

    Based on the regions in slaclab/Q0Measurement#38 by Soham.
    """

    SHOW_TEXT = "Show Fit Regions"
    HIDE_TEXT = "Hide Fit Regions"
    TOOLTIP = (
        "Drag a region's edges to fit dLL/dt to part of a run. "
        "Hiding the regions fits all the data again. "
        "Fit regions are never saved."
    )

    def __init__(
        self,
        plot_widget: PlotWidget,
        button: QPushButton,
    ):
        self.plot_widget = plot_widget
        self.button = button
        self.shown = False
        self._regions: List[
            Tuple[LinearRegionItem, q0_utils.DataRun, FitWindowCallback]
        ] = []

        self.button.setText(self.SHOW_TEXT)
        self.button.setToolTip(self.TOOLTIP)
        self.button.clicked.connect(self.toggle)

    def set_runs(
        self,
        runs: List[q0_utils.DataRun],
        on_window_changed: FitWindowCallback,
    ) -> None:
        """Replace the regions with one per run that has data.

        A dropped run's window is cleared, since its region leaves the
        screen. Runs passed again keep their windows.
        """
        self._remove_from_plot()
        for _, old_run, old_callback in self._regions:
            kept = any(old_run is run for run in runs)
            if not kept and old_run.fit_window is not None:
                old_callback(old_run, None)
        self._regions = []
        for run in runs:
            if not run.ll_data:
                continue
            region = self._make_region(run)
            region.sigRegionChangeFinished.connect(
                lambda item, run=run, cb=on_window_changed: (
                    self._region_changed(item, run, cb)
                )
            )
            self._regions.append((region, run, on_window_changed))
        if self.shown:
            self._add_to_plot()

    def toggle(self) -> None:
        if self.shown:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        self.shown = True
        self.button.setText(self.HIDE_TEXT)
        self._add_to_plot()

    def hide(self) -> None:
        self.shown = False
        self.button.setText(self.SHOW_TEXT)
        self._remove_from_plot()
        for region, run, on_window_changed in self._regions:
            if run.fit_window is not None:
                on_window_changed(run, None)
            self._sync_region(region, run)

    @staticmethod
    def _data_span(run: q0_utils.DataRun) -> Tuple[float, float]:
        return min(run.ll_data), max(run.ll_data)

    def _make_region(self, run: q0_utils.DataRun) -> LinearRegionItem:
        span = self._data_span(run)
        return LinearRegionItem(
            values=run.fit_window or span,
            bounds=span,
            swapMode="block",
        )

    def _region_changed(
        self,
        region: LinearRegionItem,
        run: q0_utils.DataRun,
        on_window_changed: FitWindowCallback,
    ) -> None:
        lo, hi = region.getRegion()
        on_window_changed(run, (lo, hi))
        # The owner can refuse the window (fewer than two samples, or a
        # measurement running). Snap back so the region shows the fit in use.
        self._sync_region(region, run)

    def _sync_region(
        self, region: LinearRegionItem, run: q0_utils.DataRun
    ) -> None:
        """Move region to run's fit window, or its full span if none."""
        # Silently, so the move isn't reported as a drag
        region.blockSignals(True)
        region.setRegion(run.fit_window or self._data_span(run))
        region.blockSignals(False)

    def _add_to_plot(self) -> None:
        for region, _, _ in self._regions:
            self.plot_widget.addItem(region)

    def _remove_from_plot(self) -> None:
        for region, _, _ in self._regions:
            self.plot_widget.removeItem(region)
