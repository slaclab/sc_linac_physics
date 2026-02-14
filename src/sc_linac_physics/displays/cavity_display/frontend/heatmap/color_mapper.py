"""
Utility classes for LCLS fault heatmap display.

ColorMapper: Converts fault counts to colors (Blue -> White -> Red gradient)
"""

from typing import List

from PyQt5.QtGui import QColor


class ColorMapper:
    """Maps fault count values to colors using a Blue -> White -> Red gradient.

    - Blue (0 faults): No issues
    - White (midpoint): Moderate fault count
    - Red (max): High fault count
    """

    COLOR_LOW = QColor(0, 0, 255)
    COLOR_MID = QColor(255, 255, 255)
    COLOR_HIGH = QColor(255, 0, 0)

    def __init__(self, vmin: float = 0.0, vmax: float = 1.0) -> None:
        self._vmin = vmin
        self._vmax = vmax

    def set_range(self, vmin: float, vmax: float) -> None:
        self._vmin = vmin
        self._vmax = vmax

    @property
    def vmin(self) -> float:
        return self._vmin

    @property
    def vmax(self) -> float:
        return self._vmax

    def _normalize(self, value: float) -> float:
        """Normalize a value to the range [0, 1]."""
        if self._vmax == self._vmin:
            return 0.0

        normalized = (value - self._vmin) / (self._vmax - self._vmin)
        return max(0.0, min(1.0, normalized))

    def _interpolate_color(
        self, color1: QColor, color2: QColor, t: float
    ) -> QColor:
        """Linearly interpolate between two colors."""
        r = int(color1.red() + t * (color2.red() - color1.red()))
        g = int(color1.green() + t * (color2.green() - color1.green()))
        b = int(color1.blue() + t * (color2.blue() - color1.blue()))
        return QColor(r, g, b)

    def get_color(self, value: float) -> QColor:
        """Convert a fault count value to a QColor."""
        normalized = self._normalize(value)

        if normalized <= 0.5:
            # Blue to White (1st half of gradient)
            t = normalized * 2.0  # Scale [0, 0.5] to [0, 1]
            return self._interpolate_color(self.COLOR_LOW, self.COLOR_MID, t)
        else:
            # White to Red (2nd half of gradient)
            t = (normalized - 0.5) * 2.0  # Scale [0.5, 1] to [0, 1]
            return self._interpolate_color(self.COLOR_MID, self.COLOR_HIGH, t)

    def get_gradient_colors(self, num_steps: int = 256) -> List[QColor]:
        """Generate a list of colors for drawing a color bar."""
        if num_steps < 1:
            return []

        if num_steps == 1:
            return [self.get_color(self._vmin)]

        colors = []
        for i in range(num_steps):
            value = self._vmin + (self._vmax - self._vmin) * i / (num_steps - 1)
            colors.append(self.get_color(value))

        return colors
