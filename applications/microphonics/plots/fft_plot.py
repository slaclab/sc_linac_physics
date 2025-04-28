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
            'y_label': ('Relative Amplitude', ''),
            'x_range': (0, 150),
            'y_range': (0, 2.0),
            'grid': True
        }
        super().__init__(parent, plot_type='fft', config=config)
        self._max_amplitude = 2.0  # Track max amplitude for auto-scaling

    def _format_tooltip(self, plot_type, x, y):
        """Format tooltip text specifically for FFT plot

        Args:
            plot_type: Type of plot (unused in this implementation)
            x: X coordinate (frequency in Hz)
            y: Y coordinate (amplitude)

        Returns:
            str: Formatted tooltip text
        """
        return f"Frequency: {x:.1f} Hz\nAmplitude: {y:.6f}"

    def update_plot(self, cavity_num, cavity_channel_data):
        """Update FFT plot w/ new data

        Args:
            cavity_num: Cavity number (1-8)
            buffer_data: Dictionary containing detuning data
        """
        df_data, is_valid = self._preprocess_data(cavity_channel_data, channel_type='DF')
        if not is_valid:
            print(f"FFTPlot: No valid 'DF' data for cavity {cavity_num}")
            # Optionally clear/hide existing curve
            if cavity_num in self.plot_curves:
                self.plot_curves[cavity_num].setData([], [])
            return

        try:
            freqs, amplitudes = calculate_fft(df_data, self.SAMPLE_RATE)
        except Exception as e:
            print(f"FFTPlot: Error during FFT calculation for Cav {cavity_num}: {e}")
            return

        # Update plot using the helper method (no changes needed in update_fft_plot itself)
        self.update_fft_plot(cavity_num, freqs, amplitudes)

    def update_fft_plot(self, cavity_num, freqs, amplitudes):
        """Update FFT plot w/ calculated frequency data

        Args:
            cavity_num: Cavity number (1-8)
            freqs: Array of frequency values (Hz)
            amplitudes: Array of amplitude values (linear scale)
        """
        import numpy as np

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

        # Auto-adjust y-axis range if needed
        max_current = np.max(amplitudes) if len(amplitudes) > 0 else 0.1
        if max_current > self._max_amplitude:
            self._max_amplitude = max_current * 1.2  # Add 20% headroom
            if hasattr(self.plot_widget, 'setYRange'):
                try:
                    self.plot_widget.setYRange(0, self._max_amplitude)
                except Exception as e:
                    print(f"Warning: Could not set Y range: {e}")
