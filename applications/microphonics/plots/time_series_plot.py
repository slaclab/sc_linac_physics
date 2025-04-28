import numpy as np
from PyQt5.QtCore import QTimer

from applications.microphonics.plots.base_plot import BasePlot


class TimeSeriesPlot(BasePlot):
    """Time series plots"""

    def __init__(self, parent=None):
        config = {
            'title': "Time Series",
            'x_label': ('Time', 's'),
            'y_label': ('Detuning', 'Hz'),
            'x_range': (0, 1),
            'grid': True
        }

        super().__init__(parent, plot_type='time_series', config=config)

        # Initialize state for zoom optimization
        self._is_zooming = False
        self._zoom_timer = None

        # Data storage
        self._original_data = {}  # Store original data for each cavity
        self._decimated_data = {}  # Store decimated versions

        # Configure pyqtgraph optimizations for time series
        self.plot_widget.setDownsampling(ds=True, auto=True, mode='peak')

        # Set up viewbox limits and signals
        vb = self.plot_widget.getViewBox()
        vb.setLimits(xMin=0)  # Prevent negative time
        vb.sigRangeChangedManually.connect(self._on_range_changed)

    def _format_tooltip(self, plot_type, x, y):
        """Override base tooltip formatting"""
        return f"Time: {x:.3f} s\nDetuning: {y:.2f} Hz"

    def _decimate_data(self, times, values, target_points):
        """Decimation that still preserves important features"""
        if len(times) <= target_points:
            return times, values

        # Calculate importance of each point based on changes in values
        diffs = np.abs(np.diff(values))
        diffs = np.append(diffs, 0)

        # Normalize diffs to use as importance weights
        if np.max(diffs) > 0:
            importance = diffs / np.max(diffs)
        else:
            importance = np.ones_like(diffs)

        # Always keep endpoints, min and max
        must_keep = {0, len(times) - 1, np.argmin(values), np.argmax(values)}
        remaining = target_points - len(must_keep)

        if remaining <= 0:
            return times[list(must_keep)], values[list(must_keep)]

        # Create mask excluding must keep points
        mask = np.ones(len(times), dtype=bool)
        for idx in must_keep:
            mask[idx] = False

        # Adding small constant to make sure all points have some chance
        p = importance.copy()
        p[~mask] = 0
        p = p + 0.01
        p = p / np.sum(p)

        # Select additional points based on importance
        try:
            additional = np.random.choice(
                np.arange(len(times)),
                size=min(remaining, np.sum(mask)),
                replace=False,
                p=p[mask]
            )
            indices = sorted(list(must_keep) + list(additional))
        except ValueError:
            # Fallback to uniform sampling if weighted selection fails
            indices = np.linspace(0, len(times) - 1, target_points, dtype=int)

        return times[indices], values[indices]

    def _create_decimated_levels(self, times, values):
        """Create a few key decimation levels for the dataset"""
        data_len = len(times)
        result = {'original': (times, values)}

        # Create just a few strategic decimation levels
        if data_len > 100000:
            levels = [50000, 10000, 2000]
        elif data_len > 10000:
            levels = [5000, 1000]
        else:
            levels = [1000]

        for level in levels:
            if data_len > level:
                dec_times, dec_values = self._decimate_data(times, values, level)
                result[level] = (dec_times, dec_values)

        return result

    def _get_optimal_decimation(self, cavity_num, view_width):
        """Select appropriate decimation level based on view width"""
        if cavity_num not in self._decimated_data:
            return None

        decimations = self._decimated_data[cavity_num]
        original_times = decimations['original'][0]

        # Estimate visible points based on view
        total_range = original_times[-1] - original_times[0]
        if total_range == 0:
            return decimations['original']

        # Determine appropriate level based on view width
        if self._is_zooming:
            # Use more aggressive decimation during zooming
            target_points = 2000
        else:
            target_points = 5000

        # Find best available level
        levels = sorted([k for k in decimations.keys() if isinstance(k, int)])
        if not levels:
            return decimations['original']

        # Use smallest level that provides enough detail
        for level in levels:
            if level >= target_points:
                return decimations[level]

        # If we need more points than available will return original
        return decimations['original']

    def _filter_to_view(self, times, values, x_min, x_max):
        """Filter data to current view w/ some context points"""
        # Find points in visible range w/ padding
        padding = (x_max - x_min) * 0.1  # 10% padding
        visible = (times >= x_min - padding) & (times <= x_max + padding)

        if not np.any(visible):
            # If no points visible, return sparse subset
            step = max(len(times) // 100, 1)
            return times[::step], values[::step]

        # Get visible indices
        visible_indices = np.where(visible)[0]

        # If few enough points, use them all
        if len(visible_indices) <= 5000:
            return times[visible], values[visible]

        # Otherwise, decimate the visible points
        visible_times = times[visible]
        visible_values = values[visible]
        return self._decimate_data(visible_times, visible_values, 5000)

    def _on_range_changed(self):
        """Handle view range changes w/ optimized rendering"""
        self._is_zooming = True

        # Get current view range
        vb = self.plot_widget.getViewBox()
        view_range = vb.viewRange()
        x_min, x_max = view_range[0]

        # Update displayed data for visible cavities
        self._update_visible_curves(x_min, x_max)

        # Set timer to restore better quality after zooming stops
        if self._zoom_timer is not None:
            self._zoom_timer.stop()

        self._zoom_timer = QTimer()
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.timeout.connect(self._end_zoom)
        self._zoom_timer.start(200)  # 200ms delay

    def _end_zoom(self):
        """Update display w/ higher quality after zooming ends"""
        self._is_zooming = False

        # Get current view range
        vb = self.plot_widget.getViewBox()
        view_range = vb.viewRange()
        x_min, x_max = view_range[0]

        # Update w/ more points now that zooming has ended
        self._update_visible_curves(x_min, x_max)

        # Force refresh
        self.plot_widget.update()

    def _update_visible_curves(self, x_min, x_max):
        """Update all visible curves for current view"""
        for cavity_num in self.plot_curves:
            if hasattr(self, 'cavity_checkboxes') and cavity_num in self.cavity_checkboxes:
                if not self.cavity_checkboxes[cavity_num].isChecked():
                    continue

            if cavity_num in self._original_data:
                # Get a good decimation level
                view_width = x_max - x_min
                decimated = self._get_optimal_decimation(cavity_num, view_width)

                if decimated:
                    times, values = decimated
                    # Further filter to visible area
                    display_times, display_values = self._filter_to_view(times, values, x_min, x_max)

                    # Update the curve
                    self.plot_curves[cavity_num].setData(
                        display_times, display_values,
                        skipFiniteCheck=True
                    )

    def update_plot(self, cavity_num, cavity_channel_data):
        """Main method to update time series plot w/ new data"""
        # Extract and preprocess data
        df_data, is_valid = self._preprocess_data(cavity_channel_data, channel_type='DF')
        if not is_valid:
            print(f"TimeSeriesPlot: No valid 'DF' data for cavity {cavity_num}")
            # Optionally clear/hide existing curve
            if cavity_num in self.plot_curves:
                self.plot_curves[cavity_num].setData([], [])
            return

        num_points = len(df_data)
        if num_points == 0:
            print(f"TimeSeriesPlot: Preprocessed 'DF' data is empty for cavity {cavity_num}")
            return

        values = df_data

        effective_sample_rate = self.SAMPLE_RATE
        times = np.linspace(0, (num_points - 1) / effective_sample_rate, num_points)

        self._original_data[cavity_num] = (times, values)

        # Create decimated versions for different zoom levels
        self._decimated_data[cavity_num] = self._create_decimated_levels(times, values)

        # Create pen for this cavity
        pen = self._get_cavity_pen(cavity_num)

        # Plotting Logic uses derived times/values)
        if cavity_num not in self.plot_curves:
            # For initial creation, use a decimated version
            if len(times) > 2000:
                display_times, display_values = self._decimate_data(times, values, 2000)
            else:
                display_times, display_values = times, values

            curve = self.plot_widget.plot(
                display_times, display_values,
                pen=pen,
                name=f"Cavity {cavity_num}",
                clipToView=True,
                skipFiniteCheck=True,
                antialias=True
            )
            self.plot_curves[cavity_num] = curve
        else:
            # Update existing curve using appropriate decimation for current view
            vb = self.plot_widget.getViewBox()
            view_range = vb.viewRange()
            x_min, x_max = view_range[0]
            view_width = x_max - x_min

            decimated = self._get_optimal_decimation(cavity_num, view_width)
            if decimated:
                dec_times, dec_values = decimated
                display_times, display_values = self._filter_to_view(dec_times, dec_values, x_min, x_max)
                self.plot_curves[cavity_num].setData(
                    display_times, display_values,
                    skipFiniteCheck=True
                )

        if len(times) > 0:  # Check if times array is not empty
            view_window = 10
            if times[-1] > view_window:
                self.plot_widget.setXRange(max(0, times[-1] - view_window), times[-1])
            else:
                self.plot_widget.setXRange(0, times[-1])
        else:
            # Handle case with no time data
            self.plot_widget.setXRange(0, 1)

    def clear_plot(self):
        """Override clear_plot to also clear time series specific data structures"""
        # Call parent method first
        super().clear_plot()

        # Clear time series specific data structures
        self._original_data = {}
        self._decimated_data = {}
