import pyqtgraph as pg
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QPushButton

from applications.microphonics.gui.async_data_manager import BASE_HARDWARE_SAMPLE_RATE
from applications.microphonics.plots.base_plot import BasePlot
from applications.microphonics.utils.data_processing import calculate_spectrogram


class SpectrogramPlot(BasePlot):
    """Spectrogram plot implementation"""

    def __init__(self, parent=None):
        """Initialize spectrogram plot w/ the right configurations"""
        self.grid_columns = 2
        self.max_columns = 4
        self.max_cavities = 8

        # Plot management
        self.graphics_layout = None
        self.plot_items = {}
        self.image_items = {}
        self.cavity_data_cache = {}
        self.cavity_order = []
        self.cavity_is_visible_flags = {}
        self.master_plot_item_for_linking = None

        # Colorbar
        self.colormap = pg.colormap.get('viridis')
        self.colorbar = None

        # Grid controls
        self.grid_controls_widget = None
        self.columns_spinbox = None
        config = {
            'title': "Spectrogram",
            'grid': False
        }
        super().__init__(parent, plot_type='spectrogram', config=config)

    def setup_ui(self):
        """Setup UI w/ grid controls"""
        # Have Baseplot do its setup
        super().setup_ui()
        self._create_grid_controls()
        self.plot_container.insertWidget(0, self.grid_controls_widget)

    def _create_grid_controls(self):
        """Create UI controls for grid config"""
        self.grid_controls_widget = QWidget()
        controls_layout = QHBoxLayout(self.grid_controls_widget)
        controls_layout.setContentsMargins(5, 5, 5, 5)

        # Column control
        controls_layout.addWidget(QLabel("Grid Columns:"))
        self.columns_spinbox = QSpinBox()
        self.columns_spinbox.setMinimum(1)
        self.columns_spinbox.setMaximum(self.max_columns)
        self.columns_spinbox.setValue(self.grid_columns)
        self.columns_spinbox.valueChanged.connect(self._on_columns_changed)
        controls_layout.addWidget(self.columns_spinbox)

        # Auto arrange button
        auto_button = QPushButton("Auto Arrange")
        auto_button.clicked.connect(self._auto_arrange_grid)
        controls_layout.addWidget(auto_button)

        controls_layout.addStretch()

    def setup_plot(self):
        """Setup plot widget"""
        # Create GraphicsLayoutWidget
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.graphics_layout.setBackground('w')
        self.graphics_layout.setSizePolicy(pg.QtWidgets.QSizePolicy.Expanding,
                                           pg.QtWidgets.QSizePolicy.Expanding)

        self.plot_widget = self.graphics_layout

        self.plot_container.addWidget(self.graphics_layout)

        self._refresh_grid_layout()

    def _refresh_grid_layout(self):
        """Central method to refresh entire grid layout"""
        # Clear all
        self.graphics_layout.clear()
        self.plot_items.clear()
        self.image_items.clear()
        self.master_plot_item_for_linking = None

        # Figure out which cavities to show
        visible_cavities = []
        for cavity_num in self.cavity_order:
            if (self.cavity_is_visible_flags.get(cavity_num, False) and
                    cavity_num in self.cavity_data_cache):
                visible_cavities.append(cavity_num)

        if not visible_cavities:
            return

        # Calculate grid dimensions
        num_visible = len(visible_cavities)
        num_rows = (num_visible + self.grid_columns - 1) // self.grid_columns

        # Create plots in grid
        for idx, cavity_num in enumerate(visible_cavities):
            row = idx // self.grid_columns
            col = idx % self.grid_columns

            plot_item = self.graphics_layout.addPlot(
                row=row, col=col,
                title=f"Cavity {cavity_num}"
            )

            # Configure plot
            plot_item.setLabel('left', 'Frequency', units='Hz')
            plot_item.setLabel('bottom', 'Time', units='s')
            plot_item.showGrid(x=True, y=True, alpha=0.3)
            plot_item.getViewBox().setBackgroundColor('w')
            plot_item.getAxis('bottom').setPen('k')
            plot_item.getAxis('left').setPen('k')

            img = pg.ImageItem()
            img.setLookupTable(self.colormap.getLookupTable())
            plot_item.addItem(img)

            self.plot_items[cavity_num] = plot_item
            self.image_items[cavity_num] = img

            Sxx, t, f, _ = self.cavity_data_cache[cavity_num]
            if t.size > 0 and f.size > 0:
                img.setImage(Sxx.T)
                img.setRect(QRectF(t[0], f[0], t[-1] - t[0], f[-1] - f[0]))
                plot_item.setXRange(t[0], t[-1], padding=0)
                plot_item.setYRange(f[0], f[-1], padding=0)

            # Link X-axis
            if 'x_range' in self.config:
                plot_item.setXRange(*self.config['x_range'])
            elif 'spectrogram' in self.config and 'x_range' in self.config['spectrogram']:
                plot_item.setXRange(*self.config['spectrogram']['x_range'])
            else:
                plot_item.setXRange(t[0], t[-1], padding=0)

            plot_item.setYRange(f[0], f[-1], padding=0)

        # Add colorbar
        if visible_cavities:
            self._add_colorbar(num_rows)

    def _format_tooltip(self, plot_type, x, y):
        """Format tooltip text specifically for spectrogram plot"""
        return f"Time: {x:.3f} s\nFrequency: {y:.1f} Hz"

    def update_plot(self, cavity_num, cavity_channel_data):
        df_data, is_valid = self._preprocess_data(cavity_channel_data, channel_type='DF')
        if not is_valid:
            print(f"SpectrogramPlot: No valid 'DF' data for cavity {cavity_num}")
            if cavity_num in self.cavity_data_cache:
                del self.cavity_data_cache[cavity_num]
            self._refresh_grid_layout()
            return

        decimation = cavity_channel_data.get('decimation', 1)
        if not isinstance(decimation, (int, float)) or decimation <= 0:
            decimation = 1
        effective_sample_rate = BASE_HARDWARE_SAMPLE_RATE / decimation

        try:
            f, t, Sxx = calculate_spectrogram(df_data, effective_sample_rate)
            if Sxx is None or Sxx.size == 0 or t.size == 0 or f.size == 0:
                raise ValueError("Spectrogram calculation returned empty arrays.")
        except Exception as e:
            print(f"SpectrogramPlot: Error during spectrogram calculation for Cav {cavity_num}: {e}")
            if cavity_num in self.cavity_data_cache:
                del self.cavity_data_cache[cavity_num]
            self._refresh_grid_layout()
            return

        self.cavity_data_cache[cavity_num] = (Sxx, t, f, effective_sample_rate)

        if cavity_num not in self.cavity_order:
            self.cavity_order.append(cavity_num)
            self.cavity_order.sort()
            self.cavity_is_visible_flags[cavity_num] = True

        self._refresh_grid_layout()

    def _add_colorbar(self, num_rows):
        """Add colorbar to the grid layout"""
        # Create colorbar
        if self.colorbar is None:
            self.colorbar = pg.ColorBarItem(
                values=(-120, 0),
                colorMap=self.colormap,
                label='Power (dB)',
                width=15
            )

        # Add to layout in right column
        self.graphics_layout.addItem(self.colorbar, row=0, col=self.grid_columns,
                                     rowspan=num_rows)

        # Link to first available image
        if self.image_items:
            first_img = next(iter(self.image_items.values()))
            self.colorbar.setImageItem(first_img)

    def _on_columns_changed(self, value):
        """Handle column count change"""
        self.grid_columns = value
        self._refresh_grid_layout()

    def _auto_arrange_grid(self):
        """Automatically figure optimal grid layout"""
        num_visible = sum(1 for cav in self.cavity_order
                          if self.cavity_is_visible_flags.get(cav, False))

        if num_visible == 0:
            return

        if num_visible <= 2:
            optimal_cols = 1
        elif num_visible <= 4:
            optimal_cols = 2
        elif num_visible <= 6:
            optimal_cols = 3
        else:
            optimal_cols = 4

        self.columns_spinbox.setValue(optimal_cols)

    def toggle_cavity_visibility(self, cavity_num, state):
        """Toggle visibility of cavity data in spectrogram"""
        visible = state == Qt.Checked
        self.cavity_is_visible_flags[cavity_num] = visible
        self._refresh_grid_layout()

    def set_plot_config(self, config):
        """Update plot settings based on config"""
        self.config = config
        plot_specific_config = config.get('spectrogram', {})

        # Check if grid columns changed
        if 'grid_columns' in plot_specific_config:
            new_columns = plot_specific_config['grid_columns']
            if new_columns != self.grid_columns:
                self.columns_spinbox.setValue(new_columns)

        elif self.cavity_data_cache:
            self._refresh_grid_layout()

    def _show_tooltip(self, plot_type, ev):
        """Override tooltip behavior"""
        pass

    def clear_plot(self):
        """Clear all plot data"""
        self.cavity_data_cache.clear()
        self.cavity_order.clear()
        self.cavity_is_visible_flags.clear()

        self._refresh_grid_layout()
