"""`sc-linac plotter`: pick PVs from the linac hierarchy and plot them.

The "Cryo signals" view is what `sc-linac cryo-signals` opens: one plot per
cryomodule in a linac. The old displays stay available as
`sc-linac plotter-old` and `sc-linac cryo-signals-old`.
"""

from typing import Dict, Iterable, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
from sc_linac_physics.displays.plot.utils import (
    AxisRangeDialog,
    PVGroup,
    get_pvs_all_groupings,
)
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

CUSTOM_VIEW = "Custom"
CRYO_VIEW = "Cryo signals"

PVKey = Tuple[str, str]  # (source class name, attribute name)


def axis_for(attribute: str) -> str:
    """One Y axis per attribute: 'ades_pv' and 'ades_pvs' -> 'ades'."""
    for suffix in ("_pvs", "_pv"):
        if attribute.endswith(suffix):
            return attribute[: -len(suffix)]
    return attribute


def curves_for(group: PVGroup, keys: Iterable[PVKey]) -> List[Curve]:
    """Curves for every PV under `keys`, labeled by PV name."""
    return [
        Curve(pv=pv, label=pv, axis=axis_for(attribute))
        for source, attribute in keys
        for pv in group[(source, attribute)]
    ]


class PlotterDisplay(Display):
    INITIAL_VIEW = CUSTOM_VIEW

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("SC Linac Plotter")
        self.machine = Machine()
        self.pv_groups = get_pvs_all_groupings(self.machine)

        self.plot = ArchiverPlot()
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

        self.level_combo.setCurrentText("Machine")
        self._on_level_changed("Machine")
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
        layout = QVBoxLayout()
        panel.setLayout(layout)

        pick = QGroupBox("Pick PVs")
        pick_layout = QVBoxLayout()
        pick.setLayout(pick_layout)
        self.level_combo = QComboBox()
        self.level_combo.addItems(
            ["Machine", "Linac", "Cryomodule", "Rack", "Cavity"]
        )
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        self.object_combo = QComboBox()
        self.object_combo.currentIndexChanged.connect(self._fill_attributes)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("ades")
        self.filter_edit.textChanged.connect(self._filter_attributes)
        self.attribute_list = QListWidget()
        self.attribute_list.setSelectionMode(QListWidget.MultiSelection)
        for widget in (
            self.level_combo,
            self.object_combo,
            self.filter_edit,
            self.attribute_list,
        ):
            pick_layout.addWidget(widget)
        buttons = QHBoxLayout()
        for text, slot in (
            ("Select all", self._select_all_visible),
            ("Select none", self.attribute_list.clearSelection),
            ("Add to plot", self.add_selected),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        pick_layout.addLayout(buttons)

        pv_row = QHBoxLayout()
        self.pv_edit = QLineEdit()
        self.pv_edit.setPlaceholderText("ACCL:L1B:0210:GACT")
        self.pv_edit.returnPressed.connect(self.add_typed_pv)
        add_pv = QPushButton("Add PV")
        add_pv.clicked.connect(self.add_typed_pv)
        pv_row.addWidget(self.pv_edit)
        pv_row.addWidget(add_pv)
        pick_layout.addLayout(pv_row)
        layout.addWidget(pick)

        plotted = QGroupBox("Plotted")
        plotted_layout = QVBoxLayout()
        plotted.setLayout(plotted_layout)
        self.plotted_list = QListWidget()
        self.plotted_list.setSelectionMode(QListWidget.MultiSelection)
        self.count_label = QLabel()
        plotted_layout.addWidget(self.plotted_list)
        plotted_layout.addWidget(self.count_label)
        buttons = QHBoxLayout()
        for text, slot in (
            ("Remove selected", self.remove_selected),
            ("Clear all", self.clear),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        plotted_layout.addLayout(buttons)
        layout.addWidget(plotted)

        self._update_count()
        return panel

    def _on_level_changed(self, level: str) -> None:
        # The combo's item data is the PV group itself, so nothing is parsed
        # back out of the display text.
        groups = self.pv_groups
        if level == "Machine":
            entries = [("Machine", groups.get_machine())]
        elif level == "Linac":
            entries = [
                (name, groups.linacs[name]) for name in sorted(groups.linacs)
            ]
        elif level == "Cryomodule":
            entries = [
                (f"CM{name}", groups.cryomodules[name])
                for name in sorted(groups.cryomodules)
            ]
        elif level == "Rack":
            entries = [
                (f"CM{cm} rack {rack}", groups.racks[(cm, rack)])
                for cm, rack in sorted(groups.racks)
            ]
        else:
            entries = [
                (f"CM{cm} cavity {cav}", groups.cavities[(cm, cav)])
                for cm, cav in sorted(groups.cavities)
            ]
        self.object_combo.blockSignals(True)
        self.object_combo.clear()
        for text, group in entries:
            self.object_combo.addItem(text, group)
        self.object_combo.blockSignals(False)
        self._fill_attributes()

    def _current_group(self) -> PVGroup:
        holder = self.object_combo.currentData()
        return holder.pvs if holder is not None else PVGroup()

    def _fill_attributes(self) -> None:
        self.attribute_list.clear()
        group = self._current_group()
        for key in sorted(group.pvs):
            source, attribute = key
            item = QListWidgetItem(
                f"[{source}] {attribute} ({len(group.pvs[key])})"
            )
            item.setData(Qt.UserRole, key)
            self.attribute_list.addItem(item)
        self._filter_attributes(self.filter_edit.text())

    def _filter_attributes(self, text: str) -> None:
        for i in range(self.attribute_list.count()):
            item = self.attribute_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _select_all_visible(self) -> None:
        for i in range(self.attribute_list.count()):
            item = self.attribute_list.item(i)
            if not item.isHidden():
                item.setSelected(True)

    def add_selected(self) -> None:
        keys = [
            item.data(Qt.UserRole)
            for item in self.attribute_list.selectedItems()
        ]
        self.add_curves(curves_for(self._current_group(), keys))

    def add_typed_pv(self) -> None:
        pv = self.pv_edit.text().strip()
        if pv:
            self.add_curves([Curve(pv=pv, label=pv, axis=pv)])
            self.pv_edit.clear()

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
            item = QListWidgetItem(curve.pv)
            item.setData(Qt.UserRole, curve.pv)
            self.plotted_list.addItem(item)
        self._update_count()

    def _confirm(self, total: int) -> bool:
        answer = QMessageBox.question(
            self,
            "Add curves",
            f"Plot {total} curves? Large plots load slowly.",
        )
        return answer == QMessageBox.Yes

    def remove_selected(self) -> None:
        for item in self.plotted_list.selectedItems():
            self.plot.remove_curve(item.data(Qt.UserRole))
            self.plotted_list.takeItem(self.plotted_list.row(item))
        self._update_count()

    def clear(self) -> None:
        self.plot.clear()
        self.plotted_list.clear()
        self._update_count()

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

    def _update_count(self) -> None:
        count = len(self.plot.curve_set.curves)
        self.count_label.setText(
            f"{count} PV{'s' if count != 1 else ''} plotted"
        )


class CryoSignalsDisplay(PlotterDisplay):
    """The plotter, opened on the cryo signals view."""

    INITIAL_VIEW = CRYO_VIEW
