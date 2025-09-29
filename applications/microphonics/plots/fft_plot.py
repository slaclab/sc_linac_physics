import numpy as np

from applications.microphonics.gui.async_data_manager import BASE_HARDWARE_SAMPLE_RATE
from applications.microphonics.plots.base_plot import BasePlot
from applications.microphonics.utils.data_processing import calculate_fft


class FFTPlot(BasePlot):
    """FFT plot implementation for Microphonics GUI

    Displays frequency domain analysis of cavity detuning data
    """

    def __init__(self, parent=None):
        """Initialize the FFT plot w/ the right configuration"""
        config = {
            "title": "FFT Analysis (0-150 Hz)",
            "x_label": ("Frequency", "Hz"),
            "y_label": ("Relative Amplitude", ""),
            "x_range": (0, 150),
            "y_range": (0, 1.50),
            "grid": True,
        }
        super().__init__(parent, plot_type="fft", config=config)
        self.current_max_freq = self.config["x_range"][1]

    def set_plot_config(self, panel_wide_config):
        super().set_plot_config(panel_wide_config)
        fft_sub_config = {}
        if "fft" in self.config and isinstance(self.config["fft"], dict):
            fft_sub_config = self.config["fft"]
        if hasattr(self, "plot_widget"):
            if "max_freq" in fft_sub_config:
                self.current_max_freq = fft_sub_config["max_freq"]
            else:
                self.current_max_freq = self.config.get("x_range", (0, 150))[1]

            if (
                not isinstance(self.current_max_freq, (int, float))
                or self.current_max_freq <= 0
            ):
                print(
                    f"Warning (FFTPlot): Invalid max_freq '{self.current_max_freq}', defaulting to 150 Hz."
                )
                self.current_max_freq = 150

            self.plot_widget.setXRange(0, self.current_max_freq, padding=0)
            self.plot_widget.setTitle(
                f"FFT Analysis (0-{self.current_max_freq:.0f} Hz)"
            )

            y_range_to_set = self.config.get("y_range")
            if "y_range" in fft_sub_config:
                y_range_to_set = fft_sub_config["y_range"]

            if (
                y_range_to_set
                and isinstance(y_range_to_set, (list, tuple))
                and len(y_range_to_set) == 2
            ):
                self.plot_widget.setYRange(*y_range_to_set)
            else:
                default_y_range = self.config.get("y_range", (0, 1.5))
                self.plot_widget.setYRange(*default_y_range)

    def _format_tooltip(self, plot_type, x, y):
        """Format tooltip text for FFT plot

        Args:
            plot_type: Type of plot (unused in this implementation)
            x: X coordinate (frequency in Hz)
            y: Y coordinate (amplitude)

        Returns:
            str: Formatted tooltip text
        """
        return f"Frequency: {x:.1f} Hz\nAmplitude: {y:.3f}"

    def update_plot(self, cavity_num, cavity_channel_data):
        """Update FFT plot w/ new data

        Args:
            cavity_num: Cavity number (1-8)
            buffer_data: Dictionary containing detuning data
        """
        df_data, is_valid = self._preprocess_data(
            cavity_channel_data, channel_type="DF"
        )
        if not is_valid:
            print(f"FFTPlot: No valid DF data for cavity {cavity_num}")
            # Optionally clear/hide existing curve
            if cavity_num in self.plot_curves:
                self.plot_curves[cavity_num].setData([], [])
            return

        decimation = cavity_channel_data.get("decimation", 1)
        if not isinstance(decimation, (int, float)) or decimation <= 0:
            print(
                f"WARN (FFTPlot Cav {cavity_num}): Invalid decimation value '{decimation}'. Using 1."
            )
            decimation = 1
        effective_sample_rate = BASE_HARDWARE_SAMPLE_RATE / decimation

        try:
            freqs, amplitudes = calculate_fft(df_data, effective_sample_rate)
        except Exception as e:
            print(f"FFTPlot: Error during FFT calculation for Cav {cavity_num}: {e}")
            return
        if freqs.size > 0:
            mask = freqs <= self.current_max_freq
            freqs_to_plot = freqs[mask]
            amplitudes_to_plot = amplitudes[mask]

            if freqs.size > 0 and freqs_to_plot.size == 0:
                freqs_to_plot = np.array([])
                amplitudes_to_plot = np.array([])
        else:
            freqs_to_plot = np.array([])
            amplitudes_to_plot = np.array([])

        # Update plot using the helper method
        self.update_fft_plot(cavity_num, freqs_to_plot, amplitudes_to_plot)

    def update_fft_plot(self, cavity_num, freqs, amplitudes):
        """Update FFT plot w/ calculated frequency data

        Args:
            cavity_num: Cavity number (1-8)
            freqs: Array of frequency values (Hz)
            amplitudes: Array of amplitude values (linear scale)
        """

        pen = self._get_cavity_pen(cavity_num)

        if cavity_num not in self.plot_curves:
            # Create new curve
            curve = self.plot_widget.plot(
                freqs,
                amplitudes,
                pen=pen,
                name=f"Cavity {cavity_num}",
                skipFiniteCheck=True,
            )
            self.plot_curves[cavity_num] = curve
        else:
            # Update existing curve
            self.plot_curves[cavity_num].setData(
                freqs, amplitudes, skipFiniteCheck=True
            )
