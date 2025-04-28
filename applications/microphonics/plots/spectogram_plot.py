import pyqtgraph as pg
from PyQt5.QtCore import Qt

from applications.microphonics.plots.base_plot import BasePlot
from applications.microphonics.utils.data_processing import calculate_spectrogram


class SpectrogramPlot(BasePlot):
    """Spectrogram plot implementation for Microphonics GUI

    Displays time frequency analysis of cavity detuning data
    """

    def __init__(self, parent=None):
        """Initialize spectrogram plot w/ the right configurations"""
        config = {
            'title': "Spectrogram",
            'x_label': ('Time', 's'),
            'y_label': ('Frequency', 'Hz'),
            'x_range': (0, 1),
            'y_range': (0, self.SAMPLE_RATE / 2),
            'grid': True
        }
        super().__init__(parent, plot_type='spectrogram', config=config)

        # Additional setup for spectrogram
        self.image_items = {}
        self.colormap = pg.colormap.get('viridis')

    def _format_tooltip(self, plot_type, x, y):
        """Format tooltip text specifically for spectrogram plot

        Args:
            plot_type: Type of plot (unused in this implementation)
            x: X coordinate (time in seconds)
            y: Y coordinate (frequency in Hz)

        Returns:
            str: Formatted tooltip text
        """
        return f"Time: {x:.3f} s\nFrequency: {y:.1f} Hz"

    def update_plot(self, cavity_num, cavity_channel_data):
        """Update spectrogram plot w/ new data

        Args:
            cavity_num: Cavity number (1-8)
            buffer_data: Dictionary containing detuning data
        """
        df_data, is_valid = self._preprocess_data(cavity_channel_data, channel_type='DF')
        if not is_valid:
            print(f"SpectrogramPlot: No valid 'DF' data for cavity {cavity_num}")
            # Optionally hide existing image item
            if cavity_num in self.image_items:
                self.image_items[cavity_num].clear()
            return

        # Calculate spectrogram using utility function
        try:
            # Assuming calculate_spectrogram takes data array and sample rate
            f, t, Sxx = calculate_spectrogram(df_data, self.SAMPLE_RATE)
        except Exception as e:
            print(f"SpectrogramPlot: Error during spectrogram calculation for Cav {cavity_num}: {e}")
            return

        # Update plot using the helper method 
        self.update_spectrogram_plot(cavity_num, Sxx, t, f)

    def update_spectrogram_plot(self, cavity_num, Sxx, t, f):
        """Update spectrogram plot w/ calculated time frequency data

        Args:
            cavity_num: Cavity number (1-8)
            Sxx: 2D array of spectrogram values (dB)
            t: Array of time values (seconds)
            f: Array of frequency values (Hz)
        """
        if cavity_num not in self.image_items:
            # Create new image item
            img = pg.ImageItem()
            self.plot_widget.addItem(img)
            # Set colormap
            img.setLookupTable(self.colormap.getLookupTable())
            self.image_items[cavity_num] = img

            # Add a color bar if this is the first image
            if len(self.image_items) == 1:
                self.add_colorbar()

        # Get image item
        img = self.image_items[cavity_num]

        # Update image with the right scaling and position
        # The rect parameter defines the [left, top, width, height] in data coordinates
        img.setImage(Sxx, rect=[t[0], f[0], t[-1] - t[0], f[-1] - f[0]])

    def add_colorbar(self):
        """Add colorbar to spectrogram plot"""
        # Create colorbar
        colorbar = pg.ColorBarItem(
            values=(-120, 0),  # Default range for dB values
            colorMap=self.colormap,
            label='Power (dB)'
        )

        # Add to layout next to the plot
        colorbar.setImageItem(next(iter(self.image_items.values())))

    def toggle_cavity_visibility(self, cavity_num, state):
        """Toggle visibility of cavity data in spectrogram
        """
        visible = state == Qt.Checked
        if cavity_num in self.image_items:
            self.image_items[cavity_num].setVisible(visible)

    def clear_plot(self):
        """Clear all plot data"""
        super().clear_plot()
        # Clear image items separately
        for img in self.image_items.values():
            self.plot_widget.removeItem(img)
        self.image_items = {}
