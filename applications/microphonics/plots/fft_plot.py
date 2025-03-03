from applications.microphonics.plots.base_plot import BasePlot
from applications.microphonics.utils.data_processing import calculate_fft


class FFTPlot(BasePlot):
    """FFT plot implementation for Microphonics GUI

    Displays frequency domain analysis of cavity detuning data
    """

    def __init__(self, parent=None):
        """Initialize the FFT plot w/ the right configuration"""
        config = {
            'title': "FFT Analysis (0-150 Hz)",
            'x_label': ('Frequency', 'Hz'),
            'y_label': ('Amplitude', 'dB'),
            'x_range': (0, 150),
            'y_range': (-140, 0),
            'grid': True
        }
        super().__init__(parent, plot_type='fft', config=config)

    def _format_tooltip(self, plot_type, x, y):
        """Format tooltip text specifically for FFT plot

        Args:
            plot_type: Type of plot (unused in this implementation)
            x: X coordinate (frequency in Hz)
            y: Y coordinate (amplitude in dB)

        Returns:
            str: Formatted tooltip text
        """
        return f"Frequency: {x:.1f} Hz\nAmplitude: {y:.2f} dB"

    def update_plot(self, cavity_num, buffer_data):
        """Update FFT plot w/ new data

        Args:
            cavity_num: Cavity number (1-8)
            buffer_data: Dictionary containing detuning data
        """
        # Preprocess data
        data_array, is_valid = self._preprocess_data(buffer_data)
        if not is_valid:
            print(f"No valid data for cavity {cavity_num}")
            return

        # Calculate FFT using utility function
        freqs, amplitudes = calculate_fft(data_array, self.SAMPLE_RATE)

        # Update plot
        self.update_fft_plot(cavity_num, freqs, amplitudes)

    def update_fft_plot(self, cavity_num, freqs, amplitudes):
        """Update FFT plot w/ calculated frequency data

        Args:
            cavity_num: Cavity number (1-8)
            freqs: Array of frequency values (Hz)
            amplitudes: Array of amplitude values (dB)
        """
        pen = self._get_cavity_pen(cavity_num)

        if cavity_num not in self.plot_curves:
            # Create new curve
            curve = self.plot_widget.plot(
                freqs, amplitudes,
                pen=pen,
                name=f"Cavity {cavity_num}",
                skipFiniteCheck=True
            )
            self.plot_curves[cavity_num] = curve
        else:
            # Update existing curve
            self.plot_curves[cavity_num].setData(
                freqs, amplitudes,
                skipFiniteCheck=True
            )
