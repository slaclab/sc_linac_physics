"""Widget that draws a `CurveSet` against time.

Wraps PyDM's `PyDMArchiverTimePlot`, which backfills each curve from the
archiver and then updates it live over Channel Access.
"""

import json
import os
from typing import Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from pydm.widgets import PyDMArchiverTimePlot
from pydm.widgets.archiver_time_plot import ArchivePlotCurveItem
from pydm.widgets.timeplot import updateMode

from sc_linac_physics.displays.plot.curve_set import (
    Curve,
    CurveSet,
    YRange,
    nth_color,
)
from sc_linac_physics.utils.archiver import ARCHIVER_BASE_URL

DEFAULT_TIME_SPAN_SECONDS = 3600


class ArchiverPlot(QWidget):
    """Time plot of one `CurveSet`.

    Curves are added and removed one at a time. Nothing already on the
    plot reconnects or re-fetches archive data when another curve changes.
    """

    def __init__(
        self,
        curve_set: Optional[CurveSet] = None,
        time_span: int = DEFAULT_TIME_SPAN_SECONDS,
        parent=None,
    ):
        super().__init__(parent)
        # PyDM's archiver plugin reads PYDM_ARCHIVER_URL on every request and
        # backfills nothing without it. Default it to the archiver that
        # utils/archiver.py uses; a value already in the environment wins.
        os.environ.setdefault("PYDM_ARCHIVER_URL", ARCHIVER_BASE_URL)
        self._title = ""
        self._y_ranges: Dict[str, YRange] = {}
        self._curves: Dict[str, Curve] = {}
        self._items: Dict[str, ArchivePlotCurveItem] = {}
        self._colors_used = 0

        self.plot = PyDMArchiverTimePlot()
        self.plot.setTimeSpan(time_span)
        self.plot.updateMode = updateMode.AtFixedRate
        self.plot.showLegend = True

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)
        self.setLayout(layout)

        if curve_set is not None:
            self.set_curve_set(curve_set)

    @property
    def curve_set(self) -> CurveSet:
        """What is on the plot now, in the order curves were added."""
        return CurveSet(
            title=self._title,
            curves=list(self._curves.values()),
            y_ranges=dict(self._y_ranges),
        )

    def set_curve_set(self, curve_set: CurveSet) -> None:
        """Replace everything on the plot with `curve_set`."""
        self.clear()
        self._title = curve_set.title
        self.plot.setPlotTitle(curve_set.title)
        self._y_ranges = dict(curve_set.y_ranges)
        for curve in curve_set.curves:
            self.add_curve(curve)

    def add_curve(self, curve: Curve) -> None:
        """Add one curve. A PV that is already plotted is skipped."""
        if curve.pv in self._curves:
            return

        if curve.color is None:
            curve = Curve(
                pv=curve.pv,
                label=curve.label,
                axis=curve.axis,
                color=nth_color(self._colors_used),
                dashed=curve.dashed,
            )
        self._colors_used += 1

        if curve.axis not in self.plot.plotItem.axes:
            self._add_axis(curve.axis)

        item = self.plot.addYChannel(
            y_channel=curve.pv,
            name=curve.label,
            color=QColor(*curve.color),
            lineStyle=Qt.DashLine if curve.dashed else Qt.SolidLine,
            yAxisName=curve.axis,
            useArchiveData=True,
        )
        # Draw each sample as holding until the next one ("right" in
        # pyqtgraph; "left" jumps to the next value early). The archiver
        # hands back the last sample before the window, which can be months
        # old; a straight line from it to the first live value showed the
        # new value back across the whole window.
        item.opts["stepMode"] = "right"
        item.updateItems(styleUpdate=True)
        self._items[curve.pv] = item
        self._curves[curve.pv] = curve

    def remove_curve(self, pv: str) -> None:
        """Remove the curve for `pv`, and its axis if nothing else uses it."""
        curve = self._curves.pop(pv, None)
        if curve is None:
            return
        self.plot.removeYChannel(self._items.pop(pv))
        if not any(c.axis == curve.axis for c in self._curves.values()):
            self._remove_axis(curve.axis)

    def clear(self) -> None:
        """Remove every curve and axis."""
        for pv in list(self._curves):
            self.remove_curve(pv)
        self._colors_used = 0

    def set_y_range(self, axis: str, y_range: Optional[YRange]) -> None:
        """Fix `axis` to `y_range`, or auto-scale it if `y_range` is None."""
        if y_range is None:
            self._y_ranges.pop(axis, None)
        else:
            self._y_ranges[axis] = y_range

        if axis in self.plot.plotItem.axes:
            self._apply_y_range(axis)

    def set_time_span(self, seconds: int) -> None:
        self.plot.setTimeSpan(seconds)

    def set_legend_visible(self, visible: bool) -> None:
        self.plot.showLegend = visible

    def _add_axis(self, axis: str) -> None:
        y_range = self._y_ranges.get(axis)
        if y_range is None:
            self.plot.addAxis(None, axis, "left", label=axis)
        else:
            self.plot.addAxis(
                None,
                axis,
                "left",
                label=axis,
                min_range=y_range[0],
                max_range=y_range[1],
                enable_auto_range=False,
            )
            # addAxis pads the range by a few percent; set it exactly.
            self._apply_y_range(axis)

    def _apply_y_range(self, axis: str) -> None:
        # Only auto-range and the view range change here. The old plotter
        # also called setLimits, which kept clamping the axis after the
        # operator switched back to auto-scale.
        axis_item = self.plot.plotItem.axes[axis]["item"]
        y_range = self._y_ranges.get(axis)
        if y_range is None:
            axis_item.auto_range = True
        else:
            axis_item.auto_range = False
            axis_item.linkedView().setYRange(*y_range, padding=0)

    def _remove_axis(self, axis: str) -> None:
        # PyDM hides an axis whose curves are all gone but keeps it, so
        # remove it ourselves. getYAxes is in the same order as
        # removeAxisAtIndex expects.
        names = [json.loads(a)["name"] for a in self.plot.getYAxes()]
        if axis in names:
            self.plot.removeAxisAtIndex(names.index(axis))
