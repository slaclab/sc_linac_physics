"""`sc-linac plotter`: pick PVs from the linac hierarchy and plot them.

The "Cryo signals" view is what `sc-linac cryo-signals` opens: one plot per
cryomodule in a linac. The old displays stay available as
`sc-linac plotter-old` and `sc-linac cryo-signals-old`.
"""

import resource
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from pydm import Display

from sc_linac_physics.displays.plot.archiver_plot import ArchiverPlot
from sc_linac_physics.displays.plot.cryo_signals import (
    DEFAULT_AXIS_RANGES,
    SELECTED_PV_ATTRIBUTES,
    axis_label,
    cryo_signals_curve_sets,
    grid_dimensions,
)
from sc_linac_physics.displays.plot.curve_set import Curve, YRange
from sc_linac_physics.displays.plot.plotted_list import PlottedList
from sc_linac_physics.displays.plot.pv_picker import PVPicker
from sc_linac_physics.displays.plot.utils import (
    AxisRangeDialog,
    get_pvs_all_groupings,
)
from sc_linac_physics.utils.sc_linac.decarad import Decarad
from sc_linac_physics.utils.sc_linac.linac import Machine

# Above CONFIRM_ABOVE curves the operator is asked first; MAX_CURVES is a hard
# stop. Both are guesses at what keeps the plot responsive, not measurements.
CONFIRM_ABOVE = 50
MAX_CURVES = 200

TIME_SPANS = {
    "5 minutes": 5 * 60,
    "15 minutes": 15 * 60,
    "30 minutes": 30 * 60,
    "1 hour": 3600,
    "2 hours": 2 * 3600,
    "6 hours": 6 * 3600,
    "12 hours": 12 * 3600,
    "24 hours": 24 * 3600,
}
DEFAULT_TIME_SPAN = "1 hour"

# Each ArchiverPlot holds about 8 open files (measured with 4 curves: PyDM
# opens a network manager per archiver channel). L3B's 20-plot cryo grid
# needs ~180, over half of macOS's default soft limit of 256, so the plotter
# raises its own soft limit toward the hard limit at startup.
OPEN_FILE_LIMIT = 4096

CUSTOM_VIEW = "Custom"
CRYO_VIEW = "Cryo signals"


def raise_open_file_limit(wanted: int = OPEN_FILE_LIMIT) -> None:
    """Raise this process's soft open-file limit to `wanted`, within the
    hard limit. Never lowers it."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = wanted if hard == resource.RLIM_INFINITY else min(wanted, hard)
    if soft != resource.RLIM_INFINITY and soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


class PlotterDisplay(Display):
    INITIAL_VIEW = CUSTOM_VIEW

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        raise_open_file_limit()
        self.setWindowTitle("SC Linac Plotter")
        self.machine = Machine()
        self.pv_groups = get_pvs_all_groupings(self.machine)
        # Not part of Machine: two units moved between cryomodules.
        self.decarads = [Decarad(1), Decarad(2)]

        self.plot = ArchiverPlot(
            empty_hint="Pick where and what on the left to plot."
        )
        self.plot.set_time_span(TIME_SPANS[DEFAULT_TIME_SPAN])
        # Cryo view: fixed ranges by cryomodule attribute, kept across
        # linac switches so an operator's changes stay put.
        self.cryo_ranges: Dict[str, Optional[YRange]] = dict(
            DEFAULT_AXIS_RANGES
        )
        self.cryo_plots: List[ArchiverPlot] = []
        self.cryo_grid = QGridLayout()
        # One legend for the whole grid: every cryomodule plot has the same
        # four curves in the same colors.
        self.cryo_legend = QLabel()
        cryo_layout = QVBoxLayout()
        cryo_layout.addWidget(self.cryo_legend)
        cryo_layout.addLayout(self.cryo_grid)
        cryo_page = QWidget()
        cryo_page.setLayout(cryo_layout)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.plot)
        self.pages.addWidget(cryo_page)

        self.selection_panel = self._selection_panel()
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.selection_panel)
        splitter.addWidget(self.pages)
        splitter.setSizes([300, 700])
        layout = QVBoxLayout()
        layout.addLayout(self._control_bar())
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.view_combo.setCurrentText(self.INITIAL_VIEW)
        self._on_view_changed(self.INITIAL_VIEW)

    @property
    def plots(self) -> List[ArchiverPlot]:
        """The plots in the current view."""
        if self.view_combo.currentText() == CRYO_VIEW:
            return self.cryo_plots
        return [self.plot]

    def ui_filename(self):
        return None

    def _control_bar(self) -> QHBoxLayout:
        """View, linac, time range, legend and Y ranges, in one row."""
        bar = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItems([CUSTOM_VIEW, CRYO_VIEW])
        self.view_combo.currentTextChanged.connect(self._on_view_changed)

        self.linac_label = QLabel("Linac:")
        self.linac_combo = QComboBox()
        for linac in self.machine.linacs:
            self.linac_combo.addItem(linac.name, linac)
        self.linac_combo.currentIndexChanged.connect(self.show_cryo_linac)

        self.time_span_combo = QComboBox()
        self.time_span_combo.addItems(TIME_SPANS)
        self.time_span_combo.setCurrentText(DEFAULT_TIME_SPAN)
        self.time_span_combo.currentTextChanged.connect(
            lambda text: self._for_each_plot("set_time_span", TIME_SPANS[text])
        )
        self.legend_check = QCheckBox("Show legend")
        self.legend_check.setChecked(True)
        self.legend_check.toggled.connect(self._on_legend_toggled)
        ranges = QPushButton("Y-axis ranges")
        ranges.clicked.connect(self.open_axis_ranges)

        for widget in (
            QLabel("View:"),
            self.view_combo,
            self.linac_label,
            self.linac_combo,
            QLabel("Time range:"),
            self.time_span_combo,
            self.legend_check,
            ranges,
        ):
            bar.addWidget(widget)
        bar.addStretch()
        return bar

    def _selection_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(320)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        self.picker = PVPicker(self.pv_groups, self.decarads)
        self.picker.curves_requested.connect(self.add_curves)
        self.plotted = PlottedList()
        self.plotted.remove_requested.connect(self.remove_curve)
        self.plotted.clear_requested.connect(self.clear)
        self.plotted.visibility_changed.connect(self.plot.set_curve_visible)
        # One splitter for where, what and plotted, so each can be resized.
        self.picker.splitter.addWidget(self.plotted)
        self.picker.splitter.setSizes([300, 300, 200])
        self.picker.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.picker)
        return panel

    def add_curves(self, curves: List[Curve]) -> None:
        plotted = {c.pv for c in self.plot.curve_set.curves}
        unique = {c.pv: c for c in reversed(curves)}  # first one per PV wins
        new = [c for c in reversed(unique.values()) if c.pv not in plotted]
        if not new:
            return
        total = len(plotted) + len(new)
        if total > MAX_CURVES:
            QMessageBox.warning(
                self,
                "Too many curves",
                f"That would make {total} curves. The plotter shows up to "
                f"{MAX_CURVES}. Pick fewer, or choose a narrower level.",
            )
            return
        if total > CONFIRM_ABOVE and not self._confirm(total):
            return
        for curve in new:
            self.plot.add_curve(curve)
            self.plotted.add(self.plot.curve(curve.pv))

    def _confirm(self, total: int) -> bool:
        answer = QMessageBox.question(
            self,
            "Add curves",
            f"Plot {total} curves? Large plots load slowly.",
        )
        return answer == QMessageBox.Yes

    def remove_curve(self, pv: str) -> None:
        self.plot.remove_curve(pv)
        self.plotted.remove(pv)

    def clear(self) -> None:
        self.plot.clear()
        self.plotted.clear()

    def _on_legend_toggled(self, shown: bool) -> None:
        self.plot.set_legend_visible(shown)
        self.cryo_legend.setVisible(shown)

    def _for_each_plot(self, method: str, value) -> None:
        for plot in self.plots:
            getattr(plot, method)(value)

    def _on_view_changed(self, view: str) -> None:
        cryo = view == CRYO_VIEW
        self.linac_label.setVisible(cryo)
        self.linac_combo.setVisible(cryo)
        self.selection_panel.setVisible(not cryo)
        self.pages.setCurrentIndex(1 if cryo else 0)
        if cryo and not self.cryo_plots:
            self.show_cryo_linac()

    def show_cryo_linac(self, _index=None) -> None:
        """Replace the cryo grid with one plot per cryomodule in the linac."""
        for plot in self.cryo_plots:
            plot.clear()
            self.cryo_grid.removeWidget(plot)
            plot.deleteLater()
        self.cryo_plots = []
        linac = self.linac_combo.currentData()
        if linac is None:
            return
        curve_sets = cryo_signals_curve_sets(linac, self.cryo_ranges)
        columns, _ = grid_dimensions(len(curve_sets))
        span = TIME_SPANS[self.time_span_combo.currentText()]
        for i, curve_set in enumerate(curve_sets):
            plot = ArchiverPlot(curve_set, time_span=span, axis_titles=False)
            plot.set_legend_visible(False)
            self.cryo_grid.addWidget(plot, i // columns, i % columns)
            self.cryo_plots.append(plot)
        self.cryo_legend.setText(
            "&nbsp;&nbsp;&nbsp;".join(
                f'<span style="color: rgb{c.color}">&#9632; {c.label}</span>'
                for c in self.cryo_plots[0].curve_set.curves
            )
            if self.cryo_plots
            else ""
        )

    def open_axis_ranges(self) -> None:
        curve_sets = [plot.curve_set for plot in self.plots]
        axes = list(
            dict.fromkeys(a for cs in curve_sets for a in cs.axis_names)
        )
        if not axes:
            QMessageBox.information(self, "No axes", "Add some PVs first.")
            return
        ranges = {}
        for curve_set in curve_sets:
            ranges.update(curve_set.y_ranges)
        current = {
            axis: {"auto_scale": axis not in ranges, "range": ranges.get(axis)}
            for axis in axes
        }
        dialog = AxisRangeDialog(axes, current, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        attribute_for = {axis_label(a): a for a in SELECTED_PV_ATTRIBUTES}
        cryo = self.view_combo.currentText() == CRYO_VIEW
        for axis, setting in dialog.get_settings().items():
            fixed = not setting["auto_scale"] and setting["range"]
            y_range = setting["range"] if fixed else None
            for plot in self.plots:
                plot.set_y_range(axis, y_range)
            if cryo and axis in attribute_for:
                self.cryo_ranges[attribute_for[axis]] = y_range
