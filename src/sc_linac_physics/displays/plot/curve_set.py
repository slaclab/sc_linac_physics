"""What goes on a plot: curves and the Y axes they sit on.

Plain data with no Qt, so presets can be built and tested without a
display. `ArchiverPlot` draws a `CurveSet`.
"""

import colorsys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

RGB = Tuple[int, int, int]
YRange = Tuple[float, float]

# Golden-ratio hue steps keep consecutive colors far apart without knowing
# how many curves there will be, so a curve's color never changes when
# another curve is added.
_GOLDEN_RATIO = 0.618033988749895


def nth_color(n: int) -> RGB:
    """Return the color for the nth curve added to a plot."""
    hue = (n * _GOLDEN_RATIO) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


@dataclass(frozen=True)
class Curve:
    """One PV drawn against time.

    `color` of None means the plot assigns the next color when the curve
    is added.
    """

    pv: str
    label: str
    axis: str
    color: Optional[RGB] = None
    dashed: bool = False


@dataclass
class CurveSet:
    """Curves for one plot, plus fixed Y ranges for some of its axes.

    An axis missing from `y_ranges` auto-scales.
    """

    title: str = ""
    curves: List[Curve] = field(default_factory=list)
    y_ranges: Dict[str, YRange] = field(default_factory=dict)

    @property
    def axis_names(self) -> List[str]:
        """Axis names in the order their first curve appears."""
        return list(dict.fromkeys(curve.axis for curve in self.curves))
