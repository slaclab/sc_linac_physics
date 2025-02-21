import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget
)


class PlotPanel(QWidget):
    """Panel for displaying real-time cavity measurement visualizations.

    Provides multiple plot types:
    - FFT frequency analysis
    - Histogram of detuning distribution
    - Time series of cavity behavior
    - Spectrogram for time-frequency analysis
    """

    SAMPLE_RATE = 2000  # Base data acquisition rate in Hz

    def __init__(self, parent=None):
        """Initialize plot panel with default configuration."""
        super().__init__(parent)
        self.current_config = None  # Active plot configuration
        self.current_decimation = 1  # Sample rate reduction factor
        self.setup_ui()
        self.setup_plots()

    def setup_ui(self):
        """Create basic UI structure with tabbed plot layout."""
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

    def setup_plots(self):
        """Initialize all plot widgets with proper configurations and interactions.

        Sets up:
        - Plot layouts and axes
        - Interactive features (zoom, pan)
        - Data storage structures
        - Tooltips for data inspection
        """
        # Create plot widgets with initial configurations
        self.plot_widgets = {
            'fft': pg.PlotWidget(title="FFT Analysis"),
            'histogram': pg.PlotWidget(title="Histogram"),
            'time_series': pg.PlotWidget(title="Time Series"),
            'spectrogram': pg.PlotWidget(title="Spectrogram")
        }
        self.cavity_toggles = {}

        # Configure FFT analysis plot
        self.plot_widgets['fft'].setLabel('left', 'Amplitude')
        self.plot_widgets['fft'].setLabel('bottom', 'Frequency', units='Hz')
        self.plot_widgets['fft'].setXRange(0, 150)
        self.plot_widgets['fft'].showGrid(x=True, y=True)

        # Configure detuning histogram
        self.plot_widgets['histogram'].setLabel('left', 'Count')
        self.plot_widgets['histogram'].setLabel('bottom', 'Detuning', units='Hz')
        self.plot_widgets['histogram'].setXRange(-200, 200)
        self.plot_widgets['histogram'].showGrid(x=True, y=True)
        self.plot_widgets['histogram'].setLogMode(y=True)  # Log scale for counts

        # Configure time domain plot
        self.plot_widgets['time_series'].setLabel('left', 'Detuning (DF)', units='Hz')
        self.plot_widgets['time_series'].setLabel('bottom', 'Time', units='s')
        self.plot_widgets['time_series'].showGrid(x=True, y=True)

        # Configure time-frequency analysis plot
        self.plot_widgets['spectrogram'].setLabel('left', 'Frequency', units='Hz')
        self.plot_widgets['spectrogram'].setLabel('bottom', 'Time', units='s')
        self.plot_widgets['spectrogram'].showGrid(x=True, y=True)

        # Add plots to tab interface
        self.tab_widget.addTab(self.plot_widgets['fft'], "FFT Analysis")
        self.tab_widget.addTab(self.plot_widgets['histogram'], "Histogram")
        self.tab_widget.addTab(self.plot_widgets['time_series'], "Time Series")
        self.tab_widget.addTab(self.plot_widgets['spectrogram'], "Spectrogram")

        # Enable interactive features for each plot
        for plot_type, plot in self.plot_widgets.items():
            plot.setMouseEnabled(x=True, y=True)
            # Create rate-limited tooltip updates
            proxy = pg.SignalProxy(
                plot.scene().sigMouseMoved,
                rateLimit=60,
                slot=lambda evt, p=plot_type: self._show_tooltip(p, evt[0])
            )

        # Initialize data storage
        self.plot_data = {}  # Raw data storage
        self.plot_curves = {}  # Plot curve references
        self.tooltips = {}  # Tooltip widgets

    def clear_plots(self):
        """Reset all plots and data structures for new measurement.

        Cleans up:
        - Plot contents
        - Data storage
        - View ranges
        - Tooltips
        """
        try:
            # Clear plot content
            for plot_type, plot in self.plot_widgets.items():
                plot.clear()
                if plot_type in self.tooltips:
                    self.tooltips[plot_type].hide()

            # Reset data structures
            self.plot_curves.clear()
            self.plot_data.clear()

            # Reset view ranges to defaults
            self.plot_widgets['fft'].setXRange(0, 150)
            self.plot_widgets['histogram'].setXRange(-200, 200)
            self.plot_widgets['time_series'].setXRange(0, 1)
            self.plot_widgets['spectrogram'].setXRange(0, 1)
            self.plot_widgets['spectrogram'].setYRange(0, self.SAMPLE_RATE / 2)

        except Exception as e:
            print(f"Error clearing plots: {str(e)}")

    def _show_tooltip(self, plot_type: str, ev):
        """Display data values at mouse position for interactive inspection.

        Args:
            plot_type: Type of plot being inspected
            ev: Mouse event with position information
        """
        try:
            plot = self.plot_widgets[plot_type]
            view = plot.plotItem.vb
            if plot.sceneBoundingRect().contains(ev):
                mouse_point = view.mapSceneToView(ev)
                x, y = mouse_point.x(), mouse_point.y()

                # Format tooltip based on measurement type
                if plot_type == 'fft':
                    tooltip = f"Frequency: {x:.1f} Hz\nAmplitude: {y:.2f}"
                elif plot_type == 'histogram':
                    tooltip = f"Detuning: {x:.1f} Hz\nCount: {int(y)}"
                elif plot_type == 'time_series':
                    tooltip = f"Time: {x:.3f} s\nDetuning: {y:.2f} Hz"
                else:
                    return

                # Create or update tooltip
                if plot_type not in self.tooltips:
                    self.tooltips[plot_type] = pg.TextItem(
                        text=tooltip,
                        color=(255, 255, 255),
                        border='k',
                        fill=(0, 0, 0, 180)
                    )
                    plot.addItem(self.tooltips[plot_type])

                self.tooltips[plot_type].setText(tooltip)
                self.tooltips[plot_type].setPos(x, y)
                self.tooltips[plot_type].show()
        except Exception as e:
            print(f"Tooltip error: {str(e)}")

    def update_time_series(self, cavity_num: int, times: np.ndarray, values: np.ndarray):
        """Update time domain plot for specified cavity.

        Args:
            cavity_num: Cavity being measured
            times: Time points for measurements
            values: Measured detuning values
        """
        # Create time points matching data length
        num_points = len(values)
        times = np.linspace(0, (num_points - 1) / self.SAMPLE_RATE, num_points)

        # Create or update plot curve
        if cavity_num not in self.plot_curves:
            pen = pg.mkPen(color=self._get_cavity_color(cavity_num), width=2)
            self.plot_curves[cavity_num] = self.plot_widgets['time_series'].plot(
                times, values,
                name=f"Cavity {cavity_num}",
                pen=pen
            )
        else:
            self.plot_curves[cavity_num].setData(times, values)

    def _calculate_fft(self, data):
        """Calculate frequency spectrum of cavity measurements.

        Args:
            data: Time series data array

        Returns:
            Tuple of (frequencies, amplitudes)
        """
        n = len(data)
        fft = np.fft.rfft(data)
        fft_amp = (2.0 / n) * np.abs(fft)  # Scale to match original code
        freqs = np.fft.rfftfreq(n, d=1 / (self.SAMPLE_RATE / self.current_decimation))
        return freqs, fft_amp

    def _calculate_spectrogram(self, data):
        """Generate time-frequency representation of cavity behavior.

        Args:
            data: Time series data array

        Returns:
            Tuple of (frequencies, times, power_spectrum)
        """
        from scipy.signal import spectrogram
        nperseg = min(len(data), 256)  # Adjust window size for short data
        f, t, Sxx = spectrogram(data, fs=self.SAMPLE_RATE, nperseg=nperseg)
        return f, t, 10 * np.log10(Sxx)  # Convert to dB scale

    def _get_cavity_color(self, cavity_num):
        """Get consistent color for cavity visualization.

        Args:
            cavity_num: Cavity number (1-8)

        Returns:
            Color string for plot elements
        """
        # Color palette for cavity distinction
        colors = [
            '#1f77b4',  # Blue
            '#ff7f0e',  # Orange
            '#2ca02c',  # Green
            '#d62728',  # Red
            '#9467bd',  # Purple
            '#8c564b',  # Brown
            '#e377c2',  # Pink
            '#7f7f7f'  # Gray
        ]
        color_idx = (cavity_num - 1) % len(colors)
        return colors[color_idx]

    def update_fft_plot(self, cavity_num, freqs, amplitudes):
        """Update frequency domain plot for cavity.

        Args:
            cavity_num: Cavity being analyzed
            freqs: Frequency points
            amplitudes: Spectral amplitudes
        """
        if cavity_num not in self.plot_curves:
            color = self._get_cavity_color(cavity_num)
            pen = pg.mkPen(color=color, width=2)
            self.plot_curves[cavity_num] = self.plot_widgets['fft'].plot(
                freqs, amplitudes, pen=pen, name=f"Cavity {cavity_num}"
            )
        else:
            self.plot_curves[cavity_num].setData(freqs, amplitudes)

    def update_histogram_plot(self, cavity_num, bins, counts):
        """Update detuning distribution plot for cavity.

        Args:
            cavity_num: Cavity being analyzed
            bins: Histogram bin edges
            counts: Count in each bin
        """
        if cavity_num not in self.plot_curves:
            color = self._get_cavity_color(cavity_num)
            brush = pg.mkBrush(color=color)
            self.plot_curves[cavity_num] = self.plot_widgets['histogram'].plot(
                bins, counts, stepMode=True, fillLevel=0, brush=brush
            )
        else:
            self.plot_curves[cavity_num].setData(bins, counts)

    def update_spectrogram(self, cavity_num, Sxx, t, f):
        """Update time-frequency plot for cavity.

        Args:
            cavity_num: Cavity being analyzed
            Sxx: Power spectrum matrix
            t: Time points
            f: Frequency points
        """
        if cavity_num not in self.plot_data:
            img = pg.ImageItem()
            self.plot_widgets['spectrogram'].addItem(img)
            self.plot_data[cavity_num] = img
        self.plot_data[cavity_num].setImage(Sxx)

    def update_plots(self, cavity_num: int, buffer_data: dict):
        """Update all visualization types with new measurement data.

        Args:
            cavity_num: Cavity being measured
            buffer_data: Dictionary containing DAC and DF measurements
        """
        try:
            # Calculate and update frequency spectrum
            freqs, fft_amps = self._calculate_fft(buffer_data['DF'])
            self.update_fft_plot(cavity_num, freqs, fft_amps)

            # Calculate and update detuning distribution
            hist_min, hist_max = -200, 200
            counts, bins = np.histogram(
                buffer_data['DF'],
                bins=140,
                range=(hist_min, hist_max)
            )
            self.update_histogram_plot(cavity_num, bins[:-1], counts)

            # Update time domain plot
            num_points = len(buffer_data['DF'])
            times = np.linspace(0, (num_points - 1) / self.SAMPLE_RATE, num_points)
            self.update_time_series(cavity_num, times, buffer_data['DF'])

            # Update time-frequency analysis
            f, t, Sxx = self._calculate_spectrogram(buffer_data['DF'])
            self.update_spectrogram(cavity_num, Sxx, t, f)

        except Exception as e:
            print(f"Error updating plots for cavity {cavity_num}: {str(e)}")

    def set_plot_config(self, config):
        """Apply new plot configuration and update display settings.

        Args:
            config: Dictionary of plot settings
        """
        self.current_config = config
        plot_type = config.get('plot_type', 'FFT Analysis')

        # Map configuration to tab selection
        tab_mapping = {
            'FFT Analysis': 0,
            'Histogram': 1,
            'Real-time': 2,
            'Spectrogram': 3
        }
        tab_index = tab_mapping.get(plot_type, 0)
        self.tab_widget.setCurrentIndex(tab_index)
