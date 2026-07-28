# sc_linac_physics/displays/plot/embeddable_plots.py
import colorsys
import os
import logging
from datetime import datetime

import numpy as np
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from pydm.widgets import PyDMArchiverTimePlot
from pydm.widgets.timeplot import updateMode


logger = logging.getLogger(__name__)


def _mock_mode_enabled() -> bool:
    """Mock archiver is forced via env var (per-process)."""
    return os.getenv("SC_ARCHIVER_MOCK") == "1"


def connect_mock_archive_source(curve, pv_name=None) -> None:
    """In mock mode, feed a curve's archive requests from the mock archiver
    instead of PyDM's HTTP plugin. No-op in real mode.
    """
    if not _mock_mode_enabled():
        return

    pv = pv_name or getattr(curve, "address", None)
    if not pv:
        return

    def _feed(min_x, max_x, _cmd, c=curve, pv=pv):
        try:
            from sc_linac_physics.utils.archiver import get_values_over_time_range
            start = datetime.fromtimestamp(min_x)
            end = datetime.fromtimestamp(max_x)
            handler = get_values_over_time_range([pv], start, end)[pv]
            ts = np.array([t.timestamp() for t in handler.timestamps], dtype=float)
            vals = np.array([float(v) for v in handler.values], dtype=float)
            buf_size = getattr(c, "_archiveBufferSize", 8000)
            max_points = max(int(buf_size) - 100, 100)
            if ts.size > max_points:
                idx = np.linspace(0, ts.size - 1, max_points).astype(int)
                ts = ts[idx]
                vals = vals[idx]
            if ts.size == 0:
                return
            c.receiveArchiveData(np.array([ts, vals]))
        except Exception as e:
            logger.warning(f"Mock archive feed failed for {pv}: {e}")

    curve.archive_data_request_signal.connect(_feed)


class EmbeddableArchiverPlot(QWidget):
    """Lightweight embeddable archiver plot widget.

    This is the base plotting component that can be embedded anywhere
    without the full PyDM Display framework overhead.
    """

    def __init__(self, parent=None, title=None, time_span=3600):
        super().__init__(parent)

        self.plotted_pvs = {}  # {pv_name: axis_name}
        self.pv_curves = {}  # {pv_name: curve_object}

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # Create archiver plot
        self.archiver_plot = PyDMArchiverTimePlot()
        self.archiver_plot.setTimeSpan(time_span)
        self.archiver_plot.updateMode = updateMode.AtFixedRate
        self.archiver_plot.showLegend = True  # Let PyDM handle it

        if title:
            self.archiver_plot.setPlotTitle(title)

        layout.addWidget(self.archiver_plot)

    def _get_rainbow_color(self, index, total=None):
        """Get a color from the rainbow spectrum.

        Args:
            index: Color index (0-based)
            total: Total number of colors (defaults to current PV count)

        Returns:
            QColor object
        """
        if total is None:
            total = max(len(self.plotted_pvs), 1)

        hue = index / max(total, 1)
        saturation = 0.9
        value = 0.95

        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        return QColor(int(r * 255), int(g * 255), int(b * 255))

    def add_pv(
        self,
        pv_name,
        label=None,
        axis_name=None,
        line_style=None,
        color=None,
        **kwargs,
    ):
        """Add a PV to the plot.

        Args:
            pv_name: PV channel name
            label: Display label (defaults to PV name)
            axis_name: Y-axis name (defaults to "Y")
            line_style: Qt line style (e.g., QtCore.Qt.DashLine)
            color: QColor for the curve
            **kwargs: Additional arguments passed to addYChannel
        """
        if pv_name in self.plotted_pvs:
            return  # Already plotted

        if label is None:
            label = pv_name

        if axis_name is None:
            axis_name = "Y"

        if color is None:
            color = self._get_rainbow_color(len(self.plotted_pvs))

        # Track the PV
        self.plotted_pvs[pv_name] = axis_name

        # Build kwargs for addYChannel
        channel_kwargs = {
            "y_channel": pv_name,
            "name": label,
            "color": color,
            "yAxisName": axis_name,
            "useArchiveData": True,
        }

        if line_style is not None:
            channel_kwargs["lineStyle"] = line_style

        # Merge additional kwargs
        channel_kwargs.update(kwargs)

        # Add the channel - PyDM should handle legend automatically
        self.archiver_plot.addYChannel(**channel_kwargs)

        # Store curve reference for potential future use
        plot_item = self.archiver_plot.getPlotItem()
        if len(plot_item.curves) > 0:
            curve = plot_item.curves[-1]
            self.pv_curves[pv_name] = curve
            connect_mock_archive_source(curve, pv_name)

    def remove_pv(self, pv_name):
        """Remove a PV from the plot."""
        if pv_name not in self.plotted_pvs:
            return

        # Remove curve
        if pv_name in self.pv_curves:
            curve = self.pv_curves[pv_name]
            self.archiver_plot.removeYChannel(curve)
            del self.pv_curves[pv_name]

        del self.plotted_pvs[pv_name]

    def clear_all(self):
        """Clear all curves from the plot."""
        self.archiver_plot.clearCurves()
        self.plotted_pvs.clear()
        self.pv_curves.clear()

    def setTimeSpan(self, seconds):
        """Set the time span for the plot."""
        self.archiver_plot.setTimeSpan(seconds)

    def set_legend_visible(self, visible):
        """Set legend visibility."""
        self.archiver_plot.showLegend = visible

    def apply_axis_settings(self, settings):
        """Apply axis range settings.

        Args:
            settings: Dict of {axis_name: {'auto_scale': bool, 'range': (min, max)}}
        """
        plot_item = self.archiver_plot.getPlotItem()

        for axis_name, setting in settings.items():
            if hasattr(plot_item, "axes") and axis_name in plot_item.axes:
                axis_dict = plot_item.axes[axis_name]
                view_box = axis_dict.get("view", None)

                if view_box:
                    if setting["auto_scale"]:
                        view_box.enableAutoRange(axis="y")
                        view_box.setAutoVisible(y=True)
                        view_box.setLimits(yMin=None, yMax=None)
                    else:
                        if setting["range"]:
                            y_min, y_max = setting["range"]
                            view_box.disableAutoRange(axis="y")
                            view_box.setAutoVisible(y=False)
                            view_box.setYRange(y_min, y_max, padding=0)
                            view_box.setLimits(yMin=y_min, yMax=y_max)
                            view_box.updateViewRange()

        plot_item.update()
        self.archiver_plot.update()
