import math
from typing import List, Optional, Tuple

from PyQt5.QtGui import QColor


class ColorMapper:
    """Maps a numeric value to a color on a navy-to-yellow gradient.

    Supports log scale for ranges that span several orders of magnitude.
    """

    DEFAULT_STOPS: List[Tuple[float, QColor]] = [
        (0.0, QColor(68, 1, 84)),  # dark purple
        (0.2, QColor(65, 68, 135)),  # blue purple
        (0.4, QColor(42, 120, 142)),  # teal
        (0.6, QColor(34, 168, 132)),  # green teal
        (0.8, QColor(122, 209, 81)),  # green yellow
        (1.0, QColor(253, 231, 37)),  # bright yellow
    ]

    def __init__(
        self,
        vmin: float = 0.0,
        vmax: float = 1.0,
        stops: Optional[List[Tuple[float, QColor]]] = None,
        log_scale: bool = False,
    ) -> None:
        self._vmin = vmin
        self._vmax = vmax
        self._stops = stops if stops is not None else list(self.DEFAULT_STOPS)
        self._log_scale = log_scale

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

    @property
    def log_scale(self) -> bool:
        return self._log_scale

    def _normalize(self, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            return 0.0
        if self._vmax == self._vmin:
            return 0.0

        if self._log_scale:
            # log1p(x) = ln(1+x), maps 0 -> 0 and spreads large ranges
            log_range = math.log1p(self._vmax - self._vmin)
            if log_range == 0.0:
                return 0.0
            clamped = max(self._vmin, min(self._vmax, value))
            return math.log1p(clamped - self._vmin) / log_range

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
        t = self._normalize(value)

        for i in range(len(self._stops) - 1):
            t0, c0 = self._stops[i]
            t1, c1 = self._stops[i + 1]
            if t <= t1:
                seg_t = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
                return self._interpolate_color(c0, c1, seg_t)

        return self._stops[-1][1]
