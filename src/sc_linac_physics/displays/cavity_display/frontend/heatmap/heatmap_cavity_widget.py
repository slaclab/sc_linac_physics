from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush
from PyQt5.QtWidgets import QWidget, QSizePolicy


class HeatmapCavityWidget(QWidget):
    """Single cavity colored rectangle in the fault heatmap grid."""

    clicked = pyqtSignal(int)
    double_clicked = pyqtSignal(int)

    DEFAULT_COLOR = QColor(128, 128, 128)
    DATA_PENDING_COLOR = QColor(200, 200, 200)
    BORDER_COLOR = QColor(0, 0, 0)
    HIGHLIGHT_BORDER_COLOR = QColor(180, 0, 0)
    SELECTED_BORDER_COLOR = QColor(0, 180, 220)

    DEFAULT_WIDTH = 22
    DEFAULT_HEIGHT = 22
    BORDER_WIDTH = 1
    HIGHLIGHT_BORDER_WIDTH = 2
    SELECTED_BORDER_WIDTH = 2

    def __init__(
        self, cavity_num: int, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self._cavity_num = cavity_num
        self._color = self.DEFAULT_COLOR
        self._fault_count: Optional[int] = None
        self._highlight: bool = False
        self._selected: bool = False
        self.setMinimumSize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Cavity {cavity_num}\nNo data loaded")

    @property
    def cavity_num(self) -> int:
        return self._cavity_num

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_fault_data(
        self,
        count: int,
        color: QColor,
        tooltip: str,
        highlight: bool = False,
    ) -> None:
        self._fault_count = count
        self._color = color
        self._highlight = highlight
        self.setToolTip(tooltip)
        self.update()

    def set_error_state(self, error_msg: str = "Error loading data") -> None:
        self._fault_count = None
        self._color = self.DEFAULT_COLOR
        self._highlight = False
        self.setToolTip(f"Cavity {self._cavity_num}\n{error_msg}")
        self.update()

    def set_data_pending(self) -> None:
        """Show that data was received but final coloring is pending."""
        self._color = self.DATA_PENDING_COLOR
        self._highlight = False
        self.setToolTip(
            f"Cavity {self._cavity_num}\nData received, coloring..."
        )
        self.update()

    def clear(self) -> None:
        self._selected = False
        self.set_error_state("No data loaded")

    def _get_text_color(self) -> QColor:
        luminance = (
            0.299 * self._color.red()
            + 0.587 * self._color.green()
            + 0.114 * self._color.blue()
        )
        if luminance < 128:
            return QColor(255, 255, 255)
        return QColor(0, 0, 0)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._selected:
            border_color = self.SELECTED_BORDER_COLOR
            border_width = self.SELECTED_BORDER_WIDTH
        elif self._highlight:
            border_color = self.HIGHLIGHT_BORDER_COLOR
            border_width = self.HIGHLIGHT_BORDER_WIDTH
        else:
            border_color = self.BORDER_COLOR
            border_width = self.BORDER_WIDTH

        half_pen = border_width / 2.0
        painter.setBrush(QBrush(self._color))
        painter.setPen(QPen(border_color, border_width))
        painter.drawRect(
            int(half_pen),
            int(half_pen),
            int(self.width() - border_width),
            int(self.height() - border_width),
        )

        painter.setPen(self._get_text_color())
        font = QFont()
        font.setPointSize(max(5, int(self.height() * 0.4)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, str(self._cavity_num))

        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._cavity_num)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._cavity_num)
        super().mouseDoubleClickEvent(event)
