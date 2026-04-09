import math
from typing import Optional, List, TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QColor,
    QPainter,
    QFont,
    QPen,
    QLinearGradient,
)
from PyQt5.QtWidgets import QWidget, QSizePolicy

if TYPE_CHECKING:
    from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_mapper import (  # noqa: E501
        ColorMapper,
    )


class ColorBarWidget(QWidget):
    """Vertical color scale legend showing fault count to color mapping."""

    DEFAULT_WIDTH = 60
    DEFAULT_HEIGHT = 180
    BAR_WIDTH = 14
    TICK_LENGTH = 4
    LABEL_MARGIN = 4
    PADDING_TOP = 6
    PADDING_BOTTOM = 6
    NUM_TICKS = 5

    BORDER_COLOR = QColor(180, 180, 180)
    TICK_COLOR = QColor(200, 200, 200)
    LABEL_COLOR = QColor(200, 200, 200)
    LABEL_FONT_SIZE = 7
    BAR_X_OFFSET = 10
    GRADIENT_STOPS = 64

    def __init__(
        self,
        color_mapper: Optional["ColorMapper"] = None,
        title: str = "Faults",
        num_ticks: int = NUM_TICKS,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._color_mapper = color_mapper
        self._title = title
        self._num_ticks = max(2, num_ticks)

        self._vmin: float = 0.0
        self._vmax: float = 1.0

        if self._color_mapper:
            self._vmin = self._color_mapper.vmin
            self._vmax = self._color_mapper.vmax

        self.setMinimumWidth(self.DEFAULT_WIDTH)
        self.setMinimumHeight(self.DEFAULT_HEIGHT)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    @property
    def _log_scale(self) -> bool:
        if self._color_mapper:
            return self._color_mapper.log_scale
        return False

    def update_range(self) -> None:
        if self._color_mapper:
            self._vmin = self._color_mapper.vmin
            self._vmax = self._color_mapper.vmax
        self.update()

    def _get_tick_values(self) -> List[float]:
        if self._num_ticks < 2 or self._vmax == self._vmin:
            return [self._vmax, self._vmin]

        if self._log_scale and self._vmax > 0:
            log_max = math.log1p(self._vmax - self._vmin)
            step = log_max / (self._num_ticks - 1)
            return [
                self._vmin + math.expm1(log_max - i * step)
                for i in range(self._num_ticks)
            ]

        step = (self._vmax - self._vmin) / (self._num_ticks - 1)
        return [self._vmax - i * step for i in range(self._num_ticks)]

    def _value_to_bar_t(self, value: float) -> float:
        """Map a data value to a bar position (0=top/max, 1=bottom/min)."""
        if self._vmax == self._vmin:
            return 0.5

        if self._log_scale and self._vmax > self._vmin:
            log_range = math.log1p(self._vmax - self._vmin)
            if log_range == 0.0:
                return 0.5
            return 1.0 - math.log1p(value - self._vmin) / log_range

        return (self._vmax - value) / (self._vmax - self._vmin)

    def _format_tick_label(self, value: float) -> str:
        if self._vmax - self._vmin >= 1.0:
            return str(int(round(value)))
        return f"{value:.1f}"

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        widget_width = self.width()
        widget_height = self.height()

        # Title
        title_font = QFont()
        title_font.setPointSize(self.LABEL_FONT_SIZE + 1)
        title_font.setBold(True)
        painter.setFont(title_font)
        title_metrics = painter.fontMetrics()
        title_height = title_metrics.height()

        painter.setPen(self.LABEL_COLOR)
        painter.drawText(
            0,
            0,
            widget_width,
            title_height + self.PADDING_TOP,
            Qt.AlignHCenter | Qt.AlignBottom,
            self._title,
        )

        # Gradient bar
        bar_top = self.PADDING_TOP + title_height + 4
        bar_bottom = widget_height - self.PADDING_BOTTOM
        bar_height = bar_bottom - bar_top

        if bar_height < 10:
            painter.end()
            return

        bar_x = self.BAR_X_OFFSET

        # Top = yellow/high, bottom = navy/low
        gradient = QLinearGradient(bar_x, bar_top, bar_x, bar_bottom)

        if self._color_mapper:
            for i in range(self.GRADIENT_STOPS + 1):
                t = i / self.GRADIENT_STOPS
                # Sample in the same space as the scale (log or linear)
                # so the gradient shows an even color distribution.
                if self._log_scale and self._vmax > self._vmin:
                    log_range = math.log1p(self._vmax - self._vmin)
                    value = self._vmin + math.expm1(log_range * (1 - t))
                else:
                    value = self._vmax - t * (self._vmax - self._vmin)
                color = self._color_mapper.get_color(value)
                gradient.setColorAt(t, color)
        else:
            gradient.setColorAt(0.0, QColor(253, 231, 37))
            gradient.setColorAt(1.0, QColor(68, 1, 84))

        painter.setBrush(gradient)
        painter.setPen(QPen(self.BORDER_COLOR, 1))
        painter.drawRect(bar_x, bar_top, self.BAR_WIDTH, bar_height)

        # Tick marks and labels
        label_font = QFont()
        label_font.setPointSize(self.LABEL_FONT_SIZE)
        painter.setFont(label_font)
        painter.setPen(QPen(self.TICK_COLOR, 1))

        tick_values = self._get_tick_values()
        tick_x_start = bar_x + self.BAR_WIDTH
        tick_x_end = tick_x_start + self.TICK_LENGTH
        label_x = tick_x_end + self.LABEL_MARGIN

        for value in tick_values:
            t = self._value_to_bar_t(value)
            y = bar_top + t * bar_height

            painter.drawLine(
                int(tick_x_start),
                int(y),
                int(tick_x_end),
                int(y),
            )

            label = self._format_tick_label(value)
            label_rect_height = painter.fontMetrics().height()
            painter.drawText(
                int(label_x),
                int(y - label_rect_height / 2),
                widget_width - int(label_x),
                label_rect_height,
                Qt.AlignLeft | Qt.AlignVCenter,
                label,
            )

        painter.end()
