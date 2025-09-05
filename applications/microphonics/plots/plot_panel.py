from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QGroupBox,
    QHBoxLayout, QSizePolicy
)

from applications.microphonics.gui.config_panel import ConfigPanel
from applications.microphonics.plots.fft_plot import FFTPlot
from applications.microphonics.plots.histogram_plot import HistogramPlot
from applications.microphonics.plots.spectrogram_plot import SpectrogramPlot
from applications.microphonics.plots.time_series_plot import TimeSeriesPlot
from applications.microphonics.utils.ui_utils import create_checkboxes, create_pushbuttons


class PlotPanel(QWidget):
    """Container for all plot types w/ self contained configuration"""

    def __init__(self, parent=None, config_panel_ref=None):
        super().__init__(parent)
        self.config_panel = config_panel_ref

        # Default configuration
        self.config = {
            'plot_type': 'FFT Analysis',
            'fft': {
                'window_size': 1024,
                'max_freq': 150
            },
            'histogram': {
                'bins': 100,
                'range': 200
            },
            'spectrogram': {
                'window': 1.0,
                'colormap': 'viridis'
            }
        }
        self._last_data_dict_processed = None
        self._current_plotting_decimation = None
        self.cavity_checkboxes = {}
        self.select_lower_btn = None
        self.select_upper_btn = None
        self.lower_selected = False
        self.upper_selected = False
        self.tab_widget = None
        self.fft_plot = None
        self.histogram_plot = None
        self.time_series_plot = None
        self.spectrogram_plot = None
        self.setup_ui()

    def setup_ui(self):
        """Initialize the UI w/ tab layout containing all plot types"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Set size policy for the entire panel to expand
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add cavity visibility controls
        self.visibility_group = QGroupBox("Cavity Visibility")
        self.visibility_layout = QVBoxLayout()
        self.visibility_layout.setContentsMargins(5, 5, 5, 5)
        self.visibility_layout.setSpacing(2)

        # Horizontal layout for group selection buttons
        group_buttons_layout = QHBoxLayout()
        group_buttons_layout.setSpacing(5)

        # This creates toggle buttons for each rack
        button_items = {
            'lower': "Select Rack A (1-4)",
            'upper': "Select Rack B (5-8)"
        }
        buttons = create_pushbuttons(
            self,
            button_items,
            group_buttons_layout
        )
        # Assign buttons to class attributes
        self.select_lower_btn = buttons['lower']
        self.select_upper_btn = buttons['upper']
        # Connect button signals
        self.select_lower_btn.clicked.connect(self.toggle_lower_cavities)
        self.select_upper_btn.clicked.connect(self.toggle_upper_cavities)

        # Add group buttons to visibility layout
        self.visibility_layout.addLayout(group_buttons_layout)

        # Create horizontal layout for cavity checkboxes
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(2)

        # Create checkboxes for each cavity
        checkbox_items = {i: f"Cavity {i}" for i in range(1, 9)}
        self.cavity_checkboxes = create_checkboxes(
            self,
            checkbox_items,
            checkbox_layout,
            checked=False
        )
        # Connect signals afterward
        for cavity_num, checkbox in self.cavity_checkboxes.items():
            checkbox.stateChanged.connect(
                lambda state, cav=cavity_num: self.toggle_cavity_visibility(cav, state)
            )

        # Add checkbox layout to visibility layout
        self.visibility_layout.addLayout(checkbox_layout)

        self.visibility_group.setLayout(self.visibility_layout)
        # Set max height for the visibility group to keep it compact
        self.visibility_group.setMaximumHeight(100)
        layout.addWidget(self.visibility_group)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Connect tab change signal to update config
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # Create specialized plot widgets
        self.fft_plot = FFTPlot()
        self.histogram_plot = HistogramPlot()
        self.time_series_plot = TimeSeriesPlot()
        self.spectrogram_plot = SpectrogramPlot()

        # Add plots to tabs
        self.tab_widget.addTab(self.fft_plot, "FFT Analysis")
        self.tab_widget.addTab(self.histogram_plot, "Histogram")
        self.tab_widget.addTab(self.time_series_plot, "Time Series")
        self.tab_widget.addTab(self.spectrogram_plot, "Spectrogram")

        # Make sure the tab widget expands to fill available space
        layout.addWidget(self.tab_widget, stretch=10)

        # Initially set config for all plot types
        self._apply_config_to_all_plots()

    def on_tab_changed(self, index):
        """
        Handle tab changes by updating the plot type in configuration
        """
        tab_mapping = {
            0: 'FFT Analysis',
            1: 'Histogram',
            2: 'Time Series',
            3: 'Spectrogram'
        }
        self.config['plot_type'] = tab_mapping.get(index, 'FFT Analysis')

    def _apply_config_to_all_plots(self):
        """Apply configuration to all plot types"""
        import copy
        fft_config = copy.deepcopy(self.config)
        fft_config['plot_type'] = 'fft'

        hist_config = copy.deepcopy(self.config)
        hist_config['plot_type'] = 'histogram'

        time_config = copy.deepcopy(self.config)
        time_config['plot_type'] = 'time_series'

        spec_config = copy.deepcopy(self.config)
        spec_config['plot_type'] = 'spectrogram'

        # Apply to each plot
        self.fft_plot.set_plot_config(fft_config)
        self.histogram_plot.set_plot_config(hist_config)
        self.time_series_plot.set_plot_config(time_config)
        self.spectrogram_plot.set_plot_config(spec_config)

    def toggle_cavity_visibility(self, cavity_num, state):
        """Toggle visibility of cavity data across all plots"""
        self.fft_plot.toggle_cavity_visibility(cavity_num, state)
        self.histogram_plot.toggle_cavity_visibility(cavity_num, state)
        self.time_series_plot.toggle_cavity_visibility(cavity_num, state)
        self.spectrogram_plot.toggle_cavity_visibility(cavity_num, state)

    def toggle_lower_cavities(self):
        """Toggle selection of lower half cavities (1-4)"""
        self.lower_selected = not self.lower_selected
        for i in range(1, 5):
            self.cavity_checkboxes[i].setChecked(self.lower_selected)

        # Update button text
        self.select_lower_btn.setText(
            "Deselect Rack A (1-4)" if self.lower_selected else "Select Rack A (1-4)"
        )

    def toggle_upper_cavities(self):
        """Toggle selection of upper half cavities (5-8)"""
        self.upper_selected = not self.upper_selected
        for i in range(5, 9):
            self.cavity_checkboxes[i].setChecked(self.upper_selected)

        # Update button text
        self.select_upper_btn.setText(
            "Deselect Rack B (5-8)" if self.upper_selected else "Select Rack B (5-8)"
        )

    def _get_decimation_for_plotting(self) -> int:
        """Determines the decimation to use for plotting based on UI."""
        if self.config_panel:
            return self.config_panel.get_selected_decimation()
        else:
            print(f"PLOTPANEL WARNING: ConfigPanel ref missing. Using default decimation.")
            return ConfigPanel.DEFAULT_DECIMATION_VALUE

    def update_plots(self, data_dict: dict):
        """Update all plots w/ new data"""
        self._last_data_dict_processed = data_dict
        cavity_list = data_dict.get('cavity_list', [])
        all_cavity_data = data_dict.get('cavities', {})
        actual_plotting_decimation = self._get_decimation_for_plotting()
        self._current_plotting_decimation = actual_plotting_decimation

        for cavity_num in cavity_list:
            cavity_data_from_source = all_cavity_data.get(cavity_num)
            if cavity_data_from_source:
                data_for_this_plot_call = cavity_data_from_source.copy()
                data_for_this_plot_call['decimation'] = actual_plotting_decimation
                # Pass dictionary of channel data for this cavity to each plot types update method
                self.fft_plot.update_plot(cavity_num, data_for_this_plot_call)
                self.histogram_plot.update_plot(cavity_num, data_for_this_plot_call)
                self.time_series_plot.update_plot(cavity_num, data_for_this_plot_call)
                self.spectrogram_plot.update_plot(cavity_num, data_for_this_plot_call)
            else:
                print(f"PlotPanel: No data found for cavity {cavity_num} in received data_dict.")

    def refresh_plots_if_decimation_changed(self):
        """
        Checks if UI decimation changed from what was last used for plotting.
        and if so re plots the last processed data.
        """
        if not self.config_panel or not self._last_data_dict_processed:
            return

        new_ui_decimation = self.config_panel.get_selected_decimation()
        if self._current_plotting_decimation is None or self._current_plotting_decimation != new_ui_decimation:
            print(
                f"PlotPanel: UI Decimation changed from {self._current_plotting_decimation} to {new_ui_decimation}. Refreshing plots.")
            self.update_plots(self._last_data_dict_processed.copy())

    def clear_plots(self):
        """Clear all plot data"""
        self.fft_plot.clear_plot()
        self.histogram_plot.clear_plot()
        self.time_series_plot.clear_plot()
        self.spectrogram_plot.clear_plot()
