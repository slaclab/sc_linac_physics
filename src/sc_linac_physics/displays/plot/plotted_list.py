"""The curves on a plot, each with its color, a show/hide box and a remove
button. Emits signals; the display that owns the plot acts on them."""

from typing import Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QHeaderView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from sc_linac_physics.displays.plot.curve_set import Curve


class PlottedList(QGroupBox):
    remove_requested = pyqtSignal(str)
    clear_requested = pyqtSignal()
    visibility_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__("Plotted", parent)
        self._items: Dict[str, QTreeWidgetItem] = {}
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Curve", "Axis", ""])
        self.tree.setRootIsDecorated(False)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 28)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.count_label = QLabel()
        clear = QPushButton("Clear all")
        clear.clicked.connect(self.clear_requested)

        bottom = QHBoxLayout()
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        bottom.addWidget(clear)
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        layout.addLayout(bottom)
        self.setLayout(layout)
        self._update_count()

    def add(self, curve: Curve) -> None:
        item = QTreeWidgetItem([curve.label, curve.axis, ""])
        item.setData(0, Qt.UserRole, curve.pv)
        item.setToolTip(0, curve.pv)
        item.setIcon(0, _swatch(curve.color))
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked)
        self.tree.addTopLevelItem(item)
        remove = QToolButton()
        remove.setText("×")
        remove.setToolTip(f"Remove {curve.label}")
        remove.clicked.connect(lambda: self.remove_requested.emit(curve.pv))
        self.tree.setItemWidget(item, 2, remove)
        self._items[curve.pv] = item
        self._update_count()

    def remove(self, pv: str) -> None:
        item = self._items.pop(pv, None)
        if item is not None:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._update_count()

    def clear(self) -> None:
        self.tree.clear()
        self._items.clear()
        self._update_count()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self.tree.selectedItems():
                self.remove_requested.emit(item.data(0, Qt.UserRole))
        else:
            super().keyPressEvent(event)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column == 0:
            self.visibility_changed.emit(
                item.data(0, Qt.UserRole),
                item.checkState(0) == Qt.Checked,
            )

    def _update_count(self) -> None:
        count = len(self._items)
        self.count_label.setText(f"{count} curve{'s' if count != 1 else ''}")


def _swatch(rgb) -> QIcon:
    pixmap = QPixmap(12, 12)
    pixmap.fill(QColor(*rgb) if rgb else QColor("gray"))
    return QIcon(pixmap)
