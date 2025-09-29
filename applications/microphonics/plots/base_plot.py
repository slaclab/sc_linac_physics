from typing import Tuple, Optional

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy


class BasePlot(QWidget):
    """Base class for all plot types in Microphonics GUI"""

    def __init__(self, parent=None, plot_type=None, config=None):
        """
        Initialize base plot w/ common functionality

        Args:
            parent: Parent widget
            plot_type: (fft, histogram, time_series, spectrogram)
            config: Optional configuration dictionary
        """
        super().__init__(parent)
        self.plot_type = plot_type
        self.config = config or {}
        self.plot_curves = {}
        self.tooltips = {}

        # Setup UI components common to all plots
        self.setup_ui()
        self.setup_plot()

    def setup_ui(self):
        """Initialize base user interface which is common to all plots"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to maximize space

        # Set size policy for the plot to expand in both directions
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Plot widget container
        self.plot_container = QVBoxLayout()
        self.plot_container.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.plot_container.setSpacing(0)  # Remove spacing
        layout.addLayout(self.plot_container)

    def setup_plot(self):
        """Setup the plot widget"""
        self.plot_widget = self._setup_plot_widget(self.plot_type, self.config)
        self.plot_container.addWidget(self.plot_widget)

    def _setup_plot_widget(self, plot_type, config):
        """
        Set up a plot widget with common configuration

        Args:
            plot_type: Type of plot
            config: Configuration dictionary

        Returns:
            pg.PlotWidget: Configured plot widget
        """
        # Default configuration if none provided
        if not config:
            config = {
                "title": f"{plot_type.replace('_', ' ').title()} Plot",
                "grid": True,
            }

        widget = pg.PlotWidget(title=config.get("title", ""))

        # Set labels if provided
        if "x_label" in config:
            widget.setLabel("bottom", config["x_label"][0], units=config["x_label"][1])
        if "y_label" in config:
            widget.setLabel("left", config["y_label"][0], units=config["y_label"][1])

        # Common configuration
        widget.setBackground("w")
        widget.getAxis("bottom").setPen("k")
        widget.getAxis("left").setPen("k")
        if config.get("grid", False):
            widget.showGrid(x=True, y=True, alpha=0.3)

        widget.setMinimumSize(600, 400)

        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        widget.plotItem.vb.setMouseEnabled(x=True, y=True)

        # Add legend (top-right corner)
        widget.addLegend(offset=(-30, 30))

        # Set log mode
        if config.get("log_y", False):
            widget.setLogMode(y=True)

        # Set ranges if provided
        if "x_range" in config:
            widget.setXRange(*config["x_range"])
        if "y_range" in config:
            widget.setYRange(*config["y_range"])

        # Connect signal for tooltips
        widget.scene().sigMouseMoved.connect(
            lambda ev: self._show_tooltip(plot_type, ev)
        )

        return widget

    def _get_cavity_pen(self, cavity_num):
        """
        Create a pen for the specified cavity w/ appropriate styling

        Args:
            cavity_num: Cavity number (1-8)

        Returns:
            pg.mkPen: Pen object for the cavity
        """
        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
        ]
        line_styles = [Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine]

        color = colors[(cavity_num - 1) % len(colors)]
        style = line_styles[(cavity_num - 1) % len(line_styles)]
        qcolor = pg.mkColor(color)
        qcolor.setAlpha(150)  # 60% opacity

        return pg.mkPen(qcolor, width=2, style=style)

    def _show_tooltip(self, plot_type, ev):
        """
        Show tooltip w/ data values on hover

        Args:
            plot_type: Type of plot
            ev: Mouse event
        """
        try:
            plot = self.plot_widget
            view = plot.plotItem.vb
            if plot.sceneBoundingRect().contains(ev):
                mouse_point = view.mapSceneToView(ev)
                x, y = mouse_point.x(), mouse_point.y()

                # Format tooltip based on plot type
                tooltip = self._format_tooltip(plot_type, x, y)
                if not tooltip:
                    return

                # Update/create tooltip label
                if plot_type not in self.tooltips:
                    self.tooltips[plot_type] = pg.TextItem(
                        text=tooltip,
                        color=(255, 255, 255),
                        border="k",
                        fill=(0, 0, 0, 180),
                    )
                    plot.addItem(self.tooltips[plot_type])

                self.tooltips[plot_type].setText(tooltip)
                self.tooltips[plot_type].setPos(x, y)
                self.tooltips[plot_type].show()
        except Exception as e:
            print(f"Tooltip error: {str(e)}")

    def _format_tooltip(self, plot_type, x, y):
        """
        Format tooltip text based on plot type

        Args:
            plot_type: Type of plot
            x: X coordinate
            y: Y coordinate

        Returns:
            str: Tooltip text
        """
        return f"X: {x:.2f}, Y: {y:.2f}"

    def _preprocess_data(
        self, cavity_channel_data: dict, channel_type: str = "DF"
    ) -> Tuple[Optional[np.ndarray], bool]:
        """
        Validate and preprocess data, centralizing common operations

        Args:
            buffer_data: The input data dictionary

        Returns:
            tuple: (data_array, is_valid)
        """

        if not cavity_channel_data:
            return None, False
            # Get specific channel data array
        data_array = cavity_channel_data.get(channel_type)

        # Validate data
        if (
            data_array is None
            or not isinstance(data_array, np.ndarray)
            or data_array.size == 0
        ):
            return None, False

        # Make sure data is numpy array w/ float64 type
        try:
            # Make sure it's a NumPy array and convert type if needed
            if not isinstance(data_array, np.ndarray):
                data_array = np.array(data_array)

            # Ensure float type for calculations
            if data_array.dtype != np.float64:
                data_array = data_array.astype(np.float64)

            return data_array, True
        except (TypeError, ValueError) as e:
            print(
                f"BasePlot: Error converting channel '{channel_type}' data to float64: {e}"
            )
            return None, False

    def toggle_cavity_visibility(self, cavity_num, state):
        """
        Toggle visibility of cavity data in plot

        Args:
            cavity_num: Cavity number
            state: Checkbox state (Qt.Checked or Qt.Unchecked)
        """
        visible = state == Qt.Checked
        if cavity_num in self.plot_curves:
            self.plot_curves[cavity_num].setVisible(visible)

    def clear_plot(self):
        """Clear all plot data"""
        self.plot_widget.clear()
        self.plot_curves = {}
        # Hide tooltip if it exists
        if self.plot_type in self.tooltips:
            self.tooltips[self.plot_type].hide()

    def update_plot(self, cavity_num, data):
        """
        Update plot w/ new data

        Args:
            cavity_num: Cavity number
            data: Data to plot
        """
        raise NotImplementedError("Subclasses must implement update_plot")

    def set_plot_config(self, config):
        """
        Update plot settings based on configuration

        Args:
            config: Configuration dictionary
        """
        # Store the config
        self.config = config

        # Get plot type specific config if available
        if self.plot_type == "fft" and "fft" in config:
            plot_config = config["fft"]
        elif self.plot_type == "histogram" and "histogram" in config:
            plot_config = config["histogram"]
        elif self.plot_type == "spectrogram" and "spectrogram" in config:
            plot_config = config["spectrogram"]
        else:
            plot_config = {}

        # Apply configuration to the plot widget
        if hasattr(self, "plot_widget"):
            # Update plot ranges if provided
            if "x_range" in plot_config:
                self.plot_widget.setXRange(*plot_config["x_range"])
            if "y_range" in plot_config:
                self.plot_widget.setYRange(*plot_config["y_range"])
