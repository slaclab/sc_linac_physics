"""Pick PVs to plot: a tree of where, a list of what, and a free PV box.

`PVPicker` emits `curves_requested` with the curves to add. It plots
nothing itself, so any display can embed it next to an `ArchiverPlot`.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QSplitter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sc_linac_physics.displays.plot.curve_set import Curve
from sc_linac_physics.displays.plot.utils import HierarchicalPVs, PVGroup
from sc_linac_physics.utils.sc_linac.decarad import Decarad

PVKey = Tuple[str, str]  # (source class name, attribute name)


def axis_for(attribute: str) -> str:
    """One Y axis per attribute: 'ades_pv' and 'ades_pvs' -> 'ades'."""
    for suffix in ("_pvs", "_pv"):
        if attribute.endswith(suffix):
            return attribute[: -len(suffix)]
    return attribute


def readable(attribute: str) -> str:
    """'detune_best_pv' -> 'detune best'."""
    return axis_for(attribute).replace("_", " ")


def curves_for(
    group: PVGroup,
    keys: Iterable[PVKey],
    labels: Optional[Dict[str, str]] = None,
) -> List[Curve]:
    """Curves for every PV under `keys`, labeled from `labels` or by PV."""
    labels = labels or {}
    return [
        Curve(pv=pv, label=labels.get(pv, pv), axis=axis_for(attribute))
        for source, attribute in keys
        for pv in group[(source, attribute)]
    ]


@dataclass
class NodePVs:
    """What one tree node offers: its PVs, and labels for some of them."""

    pvs: PVGroup
    labels: Dict[str, str] = field(default_factory=dict)


def decarad_pvs(heads) -> NodePVs:
    """Dose-rate PVs for `heads`, labeled by decarad and head number.

    No cavity in the label: decarads are wheeled between cryomodules, so a
    head has no fixed cavity.
    """
    group = PVGroup()
    labels = {}
    for attribute, kind in (
        ("avg_dose_rate_pv", "avg"),
        ("raw_dose_rate_pv", "raw"),
    ):
        pvs = [getattr(head, attribute) for head in heads]
        group.pvs[("DecaradHead", attribute)] = pvs
        for head, pv in zip(heads, pvs):
            labels[pv] = (
                f"Decarad {head.decarad.number} head {head.number} {kind}"
            )
    return NodePVs(pvs=group, labels=labels)


class PVPicker(QWidget):
    curves_requested = pyqtSignal(list)

    def __init__(
        self,
        pv_groups: HierarchicalPVs,
        decarads: Iterable[Decarad] = (),
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # Plain section titles, not framed boxes, and tight spacing so the
        # lists get the height. No stylesheet: on macOS one on a parent
        # drops native rendering of every field inside it.

        where, where_layout = section("Where")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search, e.g. CM02 cavity 1")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setMinimumHeight(120)
        self.tree.currentItemChanged.connect(self._fill_attributes)
        where_layout.addWidget(self.search_edit)
        where_layout.addWidget(self.tree)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(where)

        what, what_layout = section("What")
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter, e.g. ades")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._filter_attributes)
        self.attributes = QTreeWidget()
        self.attributes.setHeaderHidden(True)
        self.attributes.setColumnCount(2)
        self.attributes.setRootIsDecorated(False)
        self.attributes.setMinimumHeight(120)
        self.attributes.setToolTip(
            "Double-click to plot, or select several and add."
        )
        self.attributes.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.attributes.itemDoubleClicked.connect(
            lambda item: self._request([item])
        )
        add = QPushButton("Add selected")
        add.clicked.connect(
            lambda: self._request(self.attributes.selectedItems())
        )
        what_layout.addWidget(self.filter_edit)
        hint = QLabel("Double-click to plot, or select several and add.")
        hint.setWordWrap(True)
        muted = hint.palette()
        muted.setColor(
            QPalette.WindowText, muted.color(QPalette.PlaceholderText)
        )
        hint.setPalette(muted)
        what_layout.addWidget(hint)
        what_layout.addWidget(self.attributes)
        what_layout.addWidget(add)
        self.pv_edit = QLineEdit()
        self.pv_edit.setPlaceholderText("Any PV, e.g. ACCL:L1B:0210:GACT")
        self.pv_edit.returnPressed.connect(self.add_typed_pv)
        add_pv = QPushButton("Add")
        add_pv.clicked.connect(self.add_typed_pv)
        pv_row = QHBoxLayout()
        pv_row.addWidget(self.pv_edit)
        pv_row.addWidget(add_pv)
        what_layout.addLayout(pv_row)
        self.splitter.addWidget(what)
        layout.addWidget(self.splitter)

        first_cavity = self._build_tree(pv_groups, list(decarads))
        if first_cavity is not None:
            self.tree.setCurrentItem(first_cavity)

    def _build_tree(
        self, groups: HierarchicalPVs, decarads
    ) -> Optional[QTreeWidgetItem]:
        """Machine > linac > CM > rack > cavity, then decarads > heads.

        Returns the first cavity, where the picker starts. Starting at
        Machine would offer every PV in the linac at once.
        """
        _node(self.tree, "Machine", NodePVs(groups.get_machine().pvs))
        cavities = []
        for linac_name in sorted(groups.linacs):
            linac = _node(
                self.tree, linac_name, NodePVs(groups.linacs[linac_name].pvs)
            )
            for cm_name in sorted(groups.cryomodules):
                cm = groups.cryomodules[cm_name]
                if cm.linac_name == linac_name:
                    cm_item = _node(linac, f"CM{cm_name}", NodePVs(cm.pvs))
                    cavities += _add_racks(cm_item, cm_name, groups)
        if decarads:
            _add_decarads(_node(self.tree, "Decarads", None), decarads)
        return cavities[0] if cavities else None

    def _current(self) -> Optional[NodePVs]:
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item is not None else None

    def _fill_attributes(self, *_) -> None:
        self.attributes.clear()
        node = self._current()
        if node is None:
            return
        for key in sorted(node.pvs.pvs, key=lambda k: (readable(k[1]), k[0])):
            source, attribute = key
            pvs = node.pvs.pvs[key]
            where = pvs[0] if len(pvs) == 1 else f"{len(pvs)} PVs ({source})"
            item = QTreeWidgetItem([readable(attribute), where])
            item.setData(0, Qt.UserRole, key)
            item.setToolTip(0, f"{source}.{attribute}")
            item.setForeground(
                1, self.palette().color(QPalette.PlaceholderText)
            )
            self.attributes.addTopLevelItem(item)
        self.attributes.resizeColumnToContents(0)
        self._filter_attributes(self.filter_edit.text())

    def _filter_attributes(self, text: str) -> None:
        text = text.lower()
        for i in range(self.attributes.topLevelItemCount()):
            item = self.attributes.topLevelItem(i)
            shown = text in item.text(0).lower() or text in item.text(1).lower()
            item.setHidden(not shown)

    def _search(self, text: str) -> None:
        """Show nodes whose path matches every word typed."""
        words = text.lower().split()
        for i in range(self.tree.topLevelItemCount()):
            _filter_node(self.tree.topLevelItem(i), "", words)

    def _request(self, items) -> None:
        node = self._current()
        keys = [item.data(0, Qt.UserRole) for item in items]
        if node is None or not keys:
            return
        # A PV that is the only one under its attribute gets a readable
        # label, e.g. "CM02 Cavity 1 aact". Several PVs keep their names,
        # since the node alone doesn't say which cavity each belongs to.
        labels = dict(node.labels)
        where = short_path(self.tree.currentItem())
        for source, attribute in keys:
            pvs = node.pvs[(source, attribute)]
            if len(pvs) == 1 and pvs[0] not in labels:
                labels[pvs[0]] = f"{where} {readable(attribute)}"
        self.curves_requested.emit(curves_for(node.pvs, keys, labels))

    def add_typed_pv(self) -> None:
        pv = self.pv_edit.text().strip()
        if pv:
            self.curves_requested.emit([Curve(pv=pv, label=pv, axis=pv)])
            self.pv_edit.clear()


def _add_racks(cm_item, cm_name: str, groups: HierarchicalPVs) -> list:
    """Rack and cavity nodes under one CM; returns the cavity nodes."""
    cavities = []
    for cm_key, rack_name in sorted(groups.racks):
        if cm_key != cm_name:
            continue
        rack = groups.racks[(cm_key, rack_name)]
        rack_item = _node(cm_item, f"Rack {rack_name}", NodePVs(rack.pvs))
        for (cm_key, number), cavity in sorted(groups.cavities.items()):
            if cm_key == cm_name and cavity.rack_name == rack_name:
                cavities.append(
                    _node(rack_item, f"Cavity {number}", NodePVs(cavity.pvs))
                )
    return cavities


def _add_decarads(parent, decarads) -> None:
    for decarad in decarads:
        heads = list(decarad.heads.values())
        unit = _node(parent, f"Decarad {decarad.number}", decarad_pvs(heads))
        for head in heads:
            _node(unit, f"Head {head.number}", decarad_pvs([head]))


def short_path(item: QTreeWidgetItem) -> str:
    """'L1B > CM02 > Rack A > Cavity 1' -> 'CM02 Cavity 1'.

    Drops the linac, which the CM implies, and a rack above a cavity.
    """
    names = []
    while item is not None:
        names.insert(0, item.text(0))
        item = item.parent()
    if len(names) > 1:
        names = names[1:]
    if len(names) == 3 and names[1].startswith("Rack "):
        names.pop(1)
    return " ".join(names)


def section(title: str):
    """A bold title over a tight layout; returns (widget, layout).

    A plain widget, not a QGroupBox: a group box's frame and margins cost
    the lists height, and a bold group box font would bold every child.
    """
    widget = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 6, 0, 0)
    layout.setSpacing(4)
    label = QLabel(title)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    layout.addWidget(label)
    widget.setLayout(layout)
    return widget, layout


def _node(parent, text: str, pvs: Optional[NodePVs]) -> QTreeWidgetItem:
    item = QTreeWidgetItem(parent, [text])
    item.setData(0, Qt.UserRole, pvs)
    if pvs is None:
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
    return item


def _filter_node(item: QTreeWidgetItem, path: str, words: List[str]) -> bool:
    path = f"{path} {item.text(0)}".lower()
    child_shown = False
    for i in range(item.childCount()):
        child_shown |= _filter_node(item.child(i), path, words)
    # Each typed word must start a word of the path, so "1" finds
    # "Cavity 1" but not every cavity under "L1B".
    path_words = path.split()
    shown = child_shown or all(
        any(p.startswith(word) for p in path_words) for word in words
    )
    item.setHidden(not shown)
    if words:
        item.setExpanded(child_shown)
    return shown
