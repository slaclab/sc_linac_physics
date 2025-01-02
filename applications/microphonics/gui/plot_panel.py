"""Plot panel for displaying microphonics measurement data"""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget
)


class PlotPanel(QWidget):
    """Panel for displaying various plot types for microphonics data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_plots()

    def setup_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

    def setup_plots(self):
        """Initialize all plot widgets"""
        # Create plot widgets
        self.plot_widgets = {
            'fft': pg.PlotWidget(title="FFT Analysis"),
            'histogram': pg.PlotWidget(title="Histogram"),
            'realtime': pg.PlotWidget(title="Real-time Data"),
            'spectrogram': pg.PlotWidget(title="Spectrogram")
        }

        # Configure FFT plot
        self.plot_widgets['fft'].setLabel('left', 'Amplitude')
        self.plot_widgets['fft'].setLabel('bottom', 'Frequency', units='Hz')
        self.plot_widgets['fft'].setXRange(0, 150)  # 0-150 Hz range per spec
        self.plot_widgets['fft'].showGrid(x=True, y=True)

        # Configure histogram plot
        self.plot_widgets['histogram'].setLabel('left', 'Count')
        self.plot_widgets['histogram'].setLabel('bottom', 'Detuning', units='Hz')
        self.plot_widgets['histogram'].setXRange(-200, 200)  # ±200 Hz range per spec
        self.plot_widgets['histogram'].showGrid(x=True, y=True)

        # Configure real-time plot
        self.plot_widgets['realtime'].setLabel('left', 'Amplitude')
        self.plot_widgets['realtime'].setLabel('bottom', 'Time', units='s')
        self.plot_widgets['realtime'].showGrid(x=True, y=True)

        # Configure spectrogram plot
        self.plot_widgets['spectrogram'].setLabel('left', 'Frequency', units='Hz')
        self.plot_widgets['spectrogram'].setLabel('bottom', 'Time', units='s')
        self.plot_widgets['spectrogram'].showGrid(x=True, y=True)

        # Add plots to tabs
        self.tab_widget.addTab(self.plot_widgets['fft'], "FFT Analysis")
        self.tab_widget.addTab(self.plot_widgets['histogram'], "Histogram")
        self.tab_widget.addTab(self.plot_widgets['realtime'], "Real-time")
        self.tab_widget.addTab(self.plot_widgets['spectrogram'], "Spectrogram")

        # Store plot data references
        self.plot_data = {}
        self.plot_curves = {}

    def update_fft_plot(self, cavity_num: int, freqs: np.ndarray, amplitudes: np.ndarray):
        """Update FFT plot for a cavity

        Args:
            cavity_num: Cavity number (1-8)
            freqs: Frequency array (Hz)
            amplitudes: Amplitude array
        """
        if cavity_num not in self.plot_curves:
            pen = pg.mkPen(color=self._get_cavity_color(cavity_num), width=2)
            self.plot_curves[cavity_num] = self.plot_widgets['fft'].plot(
                freqs, amplitudes,
                name=f"Cavity {cavity_num}",
                pen=pen
            )
        else:
            self.plot_curves[cavity_num].setData(freqs, amplitudes)

    def update_histogram_plot(self, cavity_num: int, bins: np.ndarray, counts: np.ndarray):
        """Update histogram plot for a cavity

        Args:
            cavity_num: Cavity number (1-8)
            bins: Bin edges array
            counts: Count array
        """
        if cavity_num not in self.plot_curves:
            pen = pg.mkPen(color=self._get_cavity_color(cavity_num), width=2)
            self.plot_curves[cavity_num] = self.plot_widgets['histogram'].plot(
                bins, counts,
                stepMode=True,
                name=f"Cavity {cavity_num}",
                pen=pen
            )
        else:
            self.plot_curves[cavity_num].setData(bins, counts)

    def update_realtime_plot(self, cavity_num: int, times: np.ndarray, values: np.ndarray):
        """Update real-time plot for a cavity

        Args:
            cavity_num: Cavity number (1-8)
            times: Time array (seconds)
            values: Data values array
        """
        if cavity_num not in self.plot_curves:
            pen = pg.mkPen(color=self._get_cavity_color(cavity_num), width=2)
            self.plot_curves[cavity_num] = self.plot_widgets['realtime'].plot(
                times, values,
                name=f"Cavity {cavity_num}",
                pen=pen
            )
        else:
            self.plot_curves[cavity_num].setData(times, values)

    def update_spectrogram(self, cavity_num: int, spectrogram_data: np.ndarray,
                           times: np.ndarray, freqs: np.ndarray):
        """Update spectrogram plot for a cavity

        Args:
            cavity_num: Cavity number (1-8)
            spectrogram_data: 2D array of spectrogram values
            times: Time array (seconds)
            freqs: Frequency array (Hz)
        """
        # Clear previous image if it exists
        if cavity_num in self.plot_data:
            self.plot_widgets['spectrogram'].removeItem(self.plot_data[cavity_num])

        # Create new image item
        img = pg.ImageItem()
        img.setImage(spectrogram_data)

        # Position and scale the image correctly
        img.scale(times[-1] / spectrogram_data.shape[1],
                  freqs[-1] / spectrogram_data.shape[0])

        self.plot_widgets['spectrogram'].addItem(img)
        self.plot_data[cavity_num] = img

    def clear_plots(self):
        """Clear all plots"""
        for plot in self.plot_widgets.values():
            plot.clear()
        self.plot_curves.clear()
        self.plot_data.clear()

    def remove_cavity_data(self, cavity_num: int):
        """Remove a cavity's data from all plots

        Args:
            cavity_num: Cavity number (1-8)
        """
        if cavity_num in self.plot_curves:
            for plot_type in ['fft', 'histogram', 'realtime']:
                if self.plot_curves[cavity_num] in self.plot_widgets[plot_type].items():
                    self.plot_widgets[plot_type].removeItem(self.plot_curves[cavity_num])
            del self.plot_curves[cavity_num]

        if cavity_num in self.plot_data:
            self.plot_widgets['spectrogram'].removeItem(self.plot_data[cavity_num])
            del self.plot_data[cavity_num]

    def _get_cavity_color(self, cavity_num: int) -> tuple:
        """Get color for a cavity number

        Args:
            cavity_num: Cavity number (1-8)

        Returns:
            RGB color tuple
        """
        # Define distinct colors for each cavity
        colors = [
            (31, 119, 180),  # blue
            (255, 127, 14),  # orange
            (44, 160, 44),  # green
            (214, 39, 40),  # red
            (148, 103, 189),  # purple
            (140, 86, 75),  # brown
            (227, 119, 194),  # pink
            (127, 127, 127),  # gray
        ]
        return colors[cavity_num - 1]

    def set_plot_config(self, config: dict):
        """Update plot configuration

        Args:
            config: Dictionary containing plot configuration
        """
        plot_type = config['plot_type']

        if plot_type == "FFT Analysis":
            self.plot_widgets['fft'].setXRange(0, config['fft']['max_freq'])

        elif plot_type == "Histogram":
            hist_range = config['histogram']['range']
            self.plot_widgets['histogram'].setXRange(-hist_range, hist_range)

        # Switch to the selected plot tab
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == plot_type:
                self.tab_widget.setCurrentIndex(i)
                break
