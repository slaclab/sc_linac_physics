from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtWidgets import QLayout, QWidget, QSizePolicy


class HeightForWidthWidget(QWidget):
    """QWidget that propagates the layout's hasHeightForWidth/heightForWidth to the parent layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def hasHeightForWidth(self) -> bool:
        return bool(self.layout() and self.layout().hasHeightForWidth())

    def heightForWidth(self, width: int) -> int:
        if self.layout() and self.layout().hasHeightForWidth():
            return self.layout().heightForWidth(width)
        return super().heightForWidth(width)

    def sizeHint(self) -> QSize:
        if self.layout() and self.layout().hasHeightForWidth():
            if self.width() > 0:
                w = self.width()
            elif self.minimumWidth() > 0:
                w = self.minimumWidth()
            else:
                w = 180
            return QSize(w, self.layout().heightForWidth(w))
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        if self.layout():
            return self.layout().minimumSize()
        return super().minimumSizeHint()


class FlowLayout(QLayout):
    """Wrapping row layout — items flow left-to-right, wrap to next row."""

    def __init__(self, parent=None, h_spacing: int = 6, v_spacing: int = 6):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self) -> int:
        return self._h_spacing

    def verticalSpacing(self) -> int:
        return self._v_spacing

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        r = rect.adjusted(left, top, -right, -bottom)
        x, y, line_h = r.x(), r.y(), 0
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            next_x = x + w + self._h_spacing
            if next_x - self._h_spacing > r.right() and line_h > 0:
                x = r.x()
                y += line_h + self._v_spacing
                next_x = x + w + self._h_spacing
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_h = max(line_h, h)
        return y + line_h - rect.y() + bottom
