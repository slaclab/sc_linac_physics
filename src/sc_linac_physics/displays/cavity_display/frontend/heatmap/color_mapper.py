import math

from PyQt5.QtGui import QColor


class ColorMapper:
    """Maps fault count values to a Blue -> White -> Red color gradient."""

    COLOR_LOW = QColor(0, 0, 255)
    COLOR_MID = QColor(255, 255, 255)
    COLOR_HIGH = QColor(255, 0, 0)

    def __init__(self, vmin: float = 0.0, vmax: float = 1.0) -> None:
        self._vmin = vmin
        self._vmax = vmax

    def set_range(self, vmin: float, vmax: float) -> None:
        if vmin > vmax:
            vmin, vmax = vmax, vmin
        self._vmin = vmin
        self._vmax = vmax

    @property
    def vmin(self) -> float:
        return self._vmin

    @property
    def vmax(self) -> float:
        return self._vmax

    def _normalize(self, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            return 0.0
        if self._vmax == self._vmin:
            return 0.0
        normalized = (value - self._vmin) / (self._vmax - self._vmin)
        return max(0.0, min(1.0, normalized))

    def _interpolate_color(
        self, color1: QColor, color2: QColor, t: float
    ) -> QColor:
        r = int(color1.red() + t * (color2.red() - color1.red()))
        g = int(color1.green() + t * (color2.green() - color1.green()))
        b = int(color1.blue() + t * (color2.blue() - color1.blue()))
        return QColor(r, g, b)

    def get_color(self, value: float) -> QColor:
        normalized = self._normalize(value)

        if normalized <= 0.5:
            t = normalized * 2.0
            return self._interpolate_color(self.COLOR_LOW, self.COLOR_MID, t)
        else:
            t = (normalized - 0.5) * 2.0
            return self._interpolate_color(self.COLOR_MID, self.COLOR_HIGH, t)
