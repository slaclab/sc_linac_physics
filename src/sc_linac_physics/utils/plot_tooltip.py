"""
Reusable tooltip for pyqtgraph plots.

Examples:
    tooltip = PlotTooltip(my_plot)
    tooltip = PlotTooltip(my_plot, lambda x, y: f"Freq: {x:.1f} Hz")
"""

from typing import Callable, Optional, Union

import pyqtgraph as pg


def format_default(x: float, y: float) -> str:
    """Default tooltip text showing X and Y values."""
    return f"X: {x:.2f}\nY: {y:.2f}"


class PlotTooltip:
    """
    Hover tooltip for pyqtgraph PlotWidget or PlotItem.

    Args:
        plot: The plot to attach the tooltip to.
        formatter: Function that takes (x, y) and returns the tooltip string.
    """

    def __init__(
        self,
        plot: Union[pg.PlotWidget, pg.PlotItem],
        formatter: Optional[Callable[[float, float], str]] = None,
    ):
        # Handle both PlotWidget and PlotItem
        if isinstance(plot, pg.PlotWidget):
            self._plot_item = plot.plotItem
            self._container = plot
        else:
            self._plot_item = plot
            self._container = plot

        self.formatter = formatter or format_default
        self.enabled = True

        self._tooltip = pg.TextItem(
            color=(255, 255, 255),
            fill=(0, 0, 0, 180),
            border=pg.mkPen(100, 100, 100),
        )
        self._tooltip.setZValue(1000)
        self._tooltip.hide()
        self._plot_item.addItem(self._tooltip)

        self._plot_item.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, pos):
        """Update tooltip when mouse moves over the plot."""
        if not self.enabled:
            self._tooltip.hide()
            return

        if not self._container.sceneBoundingRect().contains(pos):
            self._tooltip.hide()
            return

        mouse_point = self._plot_item.vb.mapSceneToView(pos)
        x, y = mouse_point.x(), mouse_point.y()

        try:
            text = self.formatter(x, y)
            self._tooltip.setText(text)
            self._tooltip.setPos(x, y)
            self._tooltip.show()
        except Exception as e:
            print(f"Tooltip format error: {e}")
            self._tooltip.hide()

    def set_formatter(self, formatter: Callable[[float, float], str]):
        """Change the tooltip formatter."""
        self.formatter = formatter

    def hide(self):
        """Hide tooltip."""
        self._tooltip.hide()

    def cleanup(self):
        """
        Remove the tooltip and disconnect signals.

        Call this before destroying a plot to avoid memory leaks.
        """
        try:
            self._plot_item.scene().sigMouseMoved.disconnect(
                self._on_mouse_moved
            )
        except (RuntimeError, TypeError):
            pass
        try:
            self._plot_item.removeItem(self._tooltip)
        except (RuntimeError, AttributeError):
            pass
