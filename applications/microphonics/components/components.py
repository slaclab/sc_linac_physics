from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QPushButton,
    QGridLayout, QFileDialog, QApplication
)


class ChannelSelectionGroup(QGroupBox):
    """Channel selection interface for cavity measurements.

    Provides a structured interface for selecting data channels:
    - Primary channels (DAC, DF) that are always enabled
    - Optional diagnostic channels that can be toggled
    """

    channelsChanged = pyqtSignal(list)  # Emitted when selection changes

    def __init__(self, parent=None):
        super().__init__("Channel Selection", parent)
        self.setup_ui()

    def setup_ui(self):
        """Create the channel selection interface with two sections:
        - Fixed primary channels
        - Expandable optional channels section
        """
        layout = QGridLayout()

        # Primary channels section (always visible)
        primary_label = QLabel("Primary Channels:")
        layout.addWidget(primary_label, 0, 0)

        # DAC channel - always enabled
        self.dac_check = QCheckBox("DAC")
        self.dac_check.setChecked(True)
        self.dac_check.setEnabled(False)
        layout.addWidget(self.dac_check, 0, 1)

        # DF channel - always enabled
        self.df_check = QCheckBox("DF")
        self.df_check.setChecked(True)
        self.df_check.setEnabled(False)
        layout.addWidget(self.df_check, 0, 2)

        # Toggle for optional channels visibility
        self.optional_toggle = QCheckBox("Show Optional Channels")
        self.optional_toggle.stateChanged.connect(self._toggle_optional_channels)
        layout.addWidget(self.optional_toggle, 1, 0, 1, 3)

        # Optional diagnostic channels section
        self.optional_group = QGroupBox("Optional Channels")
        optional_layout = QGridLayout()

        # Define available optional channels
        self.optional_channels = {
            'AINEG': QCheckBox("AINEG"),  # Negative input A
            'AVDIFF': QCheckBox("AVDIFF"),  # Voltage difference A
            'AIPOS': QCheckBox("AIPOS"),  # Positive input A
            'ADRV': QCheckBox("ADRV"),  # Drive signal A
            'BINEG': QCheckBox("BINEG"),  # Negative input B
            'BVDIFF': QCheckBox("BVDIFF"),  # Voltage difference B
            'BIPOS': QCheckBox("BIPOS"),  # Positive input B
            'BDRV': QCheckBox("BDRV")  # Drive signal B
        }

        # Arrange optional channels in grid layout
        row = 0
        col = 0
        for name, checkbox in self.optional_channels.items():
            optional_layout.addWidget(checkbox, row, col)
            checkbox.stateChanged.connect(self._on_channel_changed)
            col += 1
            if col > 2:  # Three channels per row
                col = 0
                row += 1

        self.optional_group.setLayout(optional_layout)
        layout.addWidget(self.optional_group, 2, 0, 1, 3)
        self.optional_group.hide()  # Initially hidden

        self.setLayout(layout)

    def _toggle_optional_channels(self, state):
        """Show or hide optional channels based on toggle state."""
        if state == Qt.Checked:
            self.optional_group.show()
        else:
            self.optional_group.hide()

        # Force layout update
        self.layout().activate()
        self.updateGeometry()
        QApplication.processEvents()

    def _on_channel_changed(self):
        """Handle changes in channel selection and emit update signal."""
        self.channelsChanged.emit(self.get_selected_channels())

    def get_selected_channels(self):
        """Get list of currently selected channel names.

        Returns:
            List including primary channels and any selected optional channels
        """
        channels = ['DAC', 'DF']  # Primary channels always included
        for name, checkbox in self.optional_channels.items():
            if checkbox.isChecked():
                channels.append(name)
        return channels


class PlotConfigGroup(QGroupBox):
    """Configuration interface for plot customization.

    Provides controls for adjusting visualization parameters:
    - Plot type selection
    - FFT analysis settings
    - Histogram configuration
    - Spectrogram parameters
    """

    configChanged = pyqtSignal(dict)  # Emitted when settings change

    def __init__(self, parent=None):
        super().__init__("Plot Configuration", parent)
        self.setup_ui()

    def setup_ui(self):
        """Create plot configuration interface with type-specific settings."""
        layout = QVBoxLayout()

        # Plot type selection
        type_layout = QHBoxLayout()
        type_label = QLabel("Plot Type:")
        self.plot_type = QComboBox()
        self.plot_type.addItems(["FFT Analysis", "Histogram", "Real-time", "Spectrogram"])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.plot_type)
        layout.addLayout(type_layout)

        # FFT analysis configuration
        self.fft_group = QGroupBox("FFT Settings")
        fft_layout = QHBoxLayout()

        # Window size control
        fft_layout.addWidget(QLabel("Window Size:"))
        self.fft_window = QSpinBox()
        self.fft_window.setRange(128, 16384)
        self.fft_window.setValue(1024)
        self.fft_window.valueChanged.connect(self._config_changed)
        fft_layout.addWidget(self.fft_window)

        # Frequency range control
        fft_layout.addWidget(QLabel("Max Frequency (Hz):"))
        self.max_freq = QSpinBox()
        self.max_freq.setRange(50, 1000)
        self.max_freq.setValue(150)
        self.max_freq.valueChanged.connect(self._config_changed)
        fft_layout.addWidget(self.max_freq)

        self.fft_group.setLayout(fft_layout)
        layout.addWidget(self.fft_group)

        # Histogram configuration
        self.hist_group = QGroupBox("Histogram Settings")
        hist_layout = QHBoxLayout()

        # Bin count control
        hist_layout.addWidget(QLabel("Bin Count:"))
        self.hist_bins = QSpinBox()
        self.hist_bins.setRange(10, 1000)
        self.hist_bins.setValue(100)
        self.hist_bins.valueChanged.connect(self._config_changed)
        hist_layout.addWidget(self.hist_bins)

        # Range control
        hist_layout.addWidget(QLabel("Range (±Hz):"))
        self.hist_range = QSpinBox()
        self.hist_range.setRange(50, 1000)
        self.hist_range.setValue(200)
        self.hist_range.valueChanged.connect(self._config_changed)
        hist_layout.addWidget(self.hist_range)

        self.hist_group.setLayout(hist_layout)
        layout.addWidget(self.hist_group)

        # Spectrogram configuration
        self.spec_group = QGroupBox("Spectrogram Settings")
        spec_layout = QHBoxLayout()

        # Time window control
        spec_layout.addWidget(QLabel("Time Window (s):"))
        self.spec_window = QDoubleSpinBox()
        self.spec_window.setRange(0.1, 10.0)
        self.spec_window.setValue(1.0)
        self.spec_window.valueChanged.connect(self._config_changed)
        spec_layout.addWidget(self.spec_window)

        # Colormap selection
        spec_layout.addWidget(QLabel("Colormap:"))
        self.colormap = QComboBox()
        self.colormap.addItems(["viridis", "plasma", "magma", "inferno"])
        self.colormap.currentTextChanged.connect(self._config_changed)
        spec_layout.addWidget(self.colormap)

        self.spec_group.setLayout(spec_layout)
        layout.addWidget(self.spec_group)

        self.setLayout(layout)

        # Connect plot type changes
        self.plot_type.currentTextChanged.connect(self.update_visible_settings)
        self.update_visible_settings(self.plot_type.currentText())

    def _config_changed(self):
        """Handle configuration changes and emit update signal."""
        self.configChanged.emit(self.get_config())

    def update_visible_settings(self, plot_type):
        """Show only relevant settings for selected plot type."""
        # Hide all configuration groups
        self.fft_group.hide()
        self.hist_group.hide()
        self.spec_group.hide()

        # Show settings for selected type
        target_group = None
        if plot_type == "FFT Analysis":
            target_group = self.fft_group
        elif plot_type == "Histogram":
            target_group = self.hist_group
        elif plot_type == "Spectrogram":
            target_group = self.spec_group

        if target_group:
            target_group.show()

        # Force layout update
        self.layout().activate()
        self.update()
        QApplication.processEvents()

    def get_config(self) -> dict:
        """Get current configuration for all plot types.

        Returns:
            Dictionary containing all visualization parameters
        """
        return {
            'plot_type': self.plot_type.currentText(),
            'fft': {
                'window_size': self.fft_window.value(),
                'max_freq': self.max_freq.value()
            },
            'histogram': {
                'bins': self.hist_bins.value(),
                'range': self.hist_range.value()
            },
            'spectrogram': {
                'window': self.spec_window.value(),
                'colormap': self.colormap.currentText()
            }
        }


class StatisticsPanel(QGroupBox):
    """Real-time statistical analysis display for cavity measurements.

    Shows key metrics for each cavity:
    - Mean detuning
    - Standard deviation
    - Range (min/max)
    - Outlier count
    """

    def __init__(self, parent=None):
        super().__init__("Statistical Analysis", parent)
        self.setup_ui()

    def setup_ui(self):
        """Create grid layout for statistical metrics display."""
        layout = QGridLayout()

        # Column headers
        headers = ["Cavity", "Mean", "Std Dev", "Min", "Max", "Outliers"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("font-weight: bold")
            layout.addWidget(label, 0, col)

        # Create display widgets for each cavity
        self.stat_widgets = {}
        for row in range(1, 9):  # Support 8 cavities
            cavity_label = QLabel(f"Cavity {row}")
            layout.addWidget(cavity_label, row, 0)

            # Initialize metric displays
            self.stat_widgets[row] = {
                'mean': QLabel("0.0"),  # Average detuning
                'std': QLabel("0.0"),  # Standard deviation
                'min': QLabel("0.0"),  # Minimum value
                'max': QLabel("0.0"),  # Maximum value
                'outliers': QLabel("0")  # Count of outliers
            }

            # Add metric displays to grid
            for col, (key, widget) in enumerate(self.stat_widgets[row].items(), 1):
                layout.addWidget(widget, row, col)

        self.setLayout(layout)

    def update_statistics(self, cavity_num, stats):
        """Update displayed statistics for specified cavity.

        Args:
            cavity_num: Cavity number (1-8)
            stats: Dictionary of calculated statistics
        """
        if cavity_num in self.stat_widgets:
            widgets = self.stat_widgets[cavity_num]
            # Update displays with formatted values
            widgets['mean'].setText(f"{stats['mean']:.2f}")
            widgets['std'].setText(f"{stats['std']:.2f}")
            widgets['min'].setText(f"{stats['min']:.2f}")
            widgets['max'].setText(f"{stats['max']:.2f}")
            widgets['outliers'].setText(str(stats['outliers']))


class DataLoadingGroup(QGroupBox):
    """Interface for loading previously recorded measurement data.

    Provides file selection from standard data directory:
    /u1/lcls/physics/rf_lcls2/microphonics/
    """

    dataLoaded = pyqtSignal(Path)  # Emitted when file selected

    def __init__(self, parent=None):
        super().__init__("Data Loading", parent)
        self.base_path = Path("/u1/lcls/physics/rf_lcls2/microphonics/")
        self.setup_ui()

    def setup_ui(self):
        """Create file loading interface with status display."""
        layout = QVBoxLayout()

        # File selection button
        self.load_button = QPushButton("Load Previous Data")
        self.load_button.clicked.connect(self.load_data)
        layout.addWidget(self.load_button)

        # Current file display
        self.file_info = QLabel("No file loaded")
        layout.addWidget(self.file_info)

        self.setLayout(layout)

    def load_data(self):
        """Open file selection dialog and handle chosen file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Previous Data",
            str(self.base_path),
            "Data Files (*.dat);;All Files (*.*)"
        )

        if file_path:
            path = Path(file_path)
            self.file_info.setText(f"Loaded: {path.name}")
            self.dataLoaded.emit(path)

    def get_selected_file(self) -> Optional[Path]:
        """Get path of currently loaded file.

        Returns:
            Path object for loaded file, or None if no file loaded
        """
        text = self.file_info.text()
        if text.startswith("Loaded: "):
            return self.base_path / text[8:]
        return None
