import numpy as np

from applications.microphonics.plots.base_plot import BasePlot
from applications.microphonics.utils.data_processing import calculate_histogram


class HistogramPlot(BasePlot):
    """Histogram plot implementation for Microphonics GUI

    Displays distribution of detuning values to visualize the stat properties of cavity behavior.
    """

    def __init__(self, parent=None):
        """Initialize the histogram plot w/ appropriate configuration"""
        config = {
            'title': "Histogram (Auto Range)",
            'x_label': ('Detuning', 'Hz'),
            'y_label': ('Count', None),
            'log_y': True,
            'grid': True
        }
        # Initial range will be updated when data is received
        self.data_range = None
        self.num_bins = 140  # Default number of bins
        super().__init__(parent, plot_type='histogram', config=config)

    def _format_tooltip(self, plot_type, x, y):
        """Format tooltip text specifically for histogram plot

        Args:
            plot_type: Type of plot (unused in this implementation)
            x: X coordinate (detuning in Hz)
            y: Y coordinate (count)

        Returns:
            str: Formatted tooltip text
        """
        return f"Detuning: {x:.1f} Hz\nCount: {int(max(1, y))}"

    def update_plot(self, cavity_num, cavity_channel_data):
        """Update histogram plot w/ new data

        Args:
            cavity_num: Cavity number (1-8)
            buffer_data: Dictionary containing detuning data
        """
        # Preprocess data get the DF channel
        df_data, is_valid = self._preprocess_data(cavity_channel_data, channel_type='DF')
        if not is_valid:
            print(f"HistogramPlot: No valid 'DF' data for cavity {cavity_num}")
            # Optionally clear/hide existing curve
            if cavity_num in self.plot_curves:
                self.plot_curves[cavity_num].setData([], [])
            return

        # Calculate data range
        if self.data_range is None and df_data.size > 0:
            try:
                min_val = np.min(df_data)
                max_val = np.max(df_data)
                range_padding = 0.05 * (max_val - min_val)
                range_padding = max(range_padding, 0.5)
                self.data_range = (min_val - range_padding, max_val + range_padding)
                self.plot_widget.setTitle(f"Histogram ({self.data_range[0]:.1f} to {self.data_range[1]:.1f} Hz)")
                self.plot_widget.setXRange(*self.data_range)

            except ValueError:  # Handle empty array case if min/max fails
                print(f"HistogramPlot: Could not calculate range for Cav {cavity_num} (likely empty data).")
                return  # Don't proceed if range calculation fails

        elif df_data.size == 0:
            print(f"HistogramPlot: Empty data for Cav {cavity_num}, cannot calculate histogram.")
            if cavity_num in self.plot_curves:
                self.plot_curves[cavity_num].setData([], [])
            return

            # If data_range is still None (e.g., first update had empty data), skip
        if self.data_range is None:
            print(f"HistogramPlot: Data range not set for Cav {cavity_num}, skipping histogram calculation.")
            return

            # Calculate histogram using utility function
        try:
            bins, counts = calculate_histogram(df_data, bin_range=self.data_range, num_bins=self.num_bins)
        except Exception as e:
            print(f"HistogramPlot: Error during histogram calculation for Cav {cavity_num}: {e}")
            return

            # Update plot using the helper method
        self.update_histogram_plot(cavity_num, bins, counts)

    def _create_step_data(self, bins: np.ndarray, counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x_coords = np.repeat(bins, 2)

        y_coords = np.insert(np.repeat(counts, 2), 0, 1)
        y_coords[-1] = 1

        return x_coords, y_coords

    def update_histogram_plot(self, cavity_num, bins, counts):
        if len(bins) != len(counts) + 1:
            print(f"HistogramPlot Error (Cav {cavity_num}): Mismatch between bins and counts.")
            return

        pen = self._get_cavity_pen(cavity_num)
        
        valid_counts = np.maximum(counts, 1)

        x_values, y_values = self._create_step_data(bins, valid_counts)

        if cavity_num not in self.plot_curves:
            curve = self.plot_widget.plot(
                x_values, y_values,
                pen=pen,
                name=f"Cavity {cavity_num}"
            )
            self.plot_curves[cavity_num] = curve
        else:
            self.plot_curves[cavity_num].setData(x_values, y_values)
