"""UI components for the Microphonics GUI"""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QPushButton,
    QGridLayout, QFileDialog
)


class ChannelSelectionGroup(QGroupBox):
    """Group box for selecting data channels to acquire"""
    channelsChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__("Channel Selection", parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()

        # Primary channels (always enabled)
        primary_label = QLabel("Primary Channels:")
        layout.addWidget(primary_label, 0, 0)

        self.dac_check = QCheckBox("DAC")
        self.dac_check.setChecked(True)
        self.dac_check.setEnabled(False)  # Always enabled
        layout.addWidget(self.dac_check, 0, 1)

        self.df_check = QCheckBox("DF")
        self.df_check.setChecked(True)
        self.df_check.setEnabled(False)  # Always enabled
        layout.addWidget(self.df_check, 0, 2)

        # Optional channels
        optional_label = QLabel("Optional Channels:")
        layout.addWidget(optional_label, 1, 0)

        self.optional_channels = {
            'AINEG': QCheckBox("AINEG"),
            'AVDIFF': QCheckBox("AVDIFF"),
            'AIPOS': QCheckBox("AIPOS"),
            'ADRV': QCheckBox("ADRV"),
            'BINEG': QCheckBox("BINEG"),
            'BVDIFF': QCheckBox("BVDIFF"),
            'BIPOS': QCheckBox("BIPOS"),
            'BDRV': QCheckBox("BDRV")
        }

        row = 1
        col = 1
        for name, checkbox in self.optional_channels.items():
            layout.addWidget(checkbox, row, col)
            checkbox.stateChanged.connect(self._on_channel_changed)
            col += 1
            if col > 3:
                col = 1
                row += 1

        self.setLayout(layout)

    def _on_channel_changed(self):
        """Handle channel selection changes"""
        self.channelsChanged.emit(self.get_selected_channels())

    def get_selected_channels(self):
        """Get list of selected channel names"""
        channels = ['DAC', 'DF']  # Primary channels always included
        for name, checkbox in self.optional_channels.items():
            if checkbox.isChecked():
                channels.append(name)
        return channels


class PlotConfigGroup(QGroupBox):
    """Group box for plot configuration options"""
    configChanged = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__("Plot Configuration", parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Plot type selection
        type_layout = QHBoxLayout()
        type_label = QLabel("Plot Type:")
        self.plot_type = QComboBox()
        self.plot_type.addItems(["FFT Analysis", "Histogram", "Real-time", "Spectrogram"])
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.plot_type)
        layout.addLayout(type_layout)

        # FFT Config
        self.fft_group = QGroupBox("FFT Settings")
        fft_layout = QHBoxLayout()

        fft_layout.addWidget(QLabel("Window Size:"))
        self.fft_window = QSpinBox()
        self.fft_window.setRange(128, 16384)
        self.fft_window.setValue(1024)
        self.fft_window.valueChanged.connect(self._config_changed)
        fft_layout.addWidget(self.fft_window)

        fft_layout.addWidget(QLabel("Max Frequency (Hz):"))
        self.max_freq = QSpinBox()
        self.max_freq.setRange(50, 1000)
        self.max_freq.setValue(150)
        self.max_freq.valueChanged.connect(self._config_changed)
        fft_layout.addWidget(self.max_freq)

        self.fft_group.setLayout(fft_layout)
        layout.addWidget(self.fft_group)

        # Histogram Config
        self.hist_group = QGroupBox("Histogram Settings")
        hist_layout = QHBoxLayout()

        hist_layout.addWidget(QLabel("Bin Count:"))
        self.hist_bins = QSpinBox()
        self.hist_bins.setRange(10, 1000)
        self.hist_bins.setValue(100)
        self.hist_bins.valueChanged.connect(self._config_changed)
        hist_layout.addWidget(self.hist_bins)

        hist_layout.addWidget(QLabel("Range (±Hz):"))
        self.hist_range = QSpinBox()
        self.hist_range.setRange(50, 1000)
        self.hist_range.setValue(200)
        self.hist_range.valueChanged.connect(self._config_changed)
        hist_layout.addWidget(self.hist_range)

        self.hist_group.setLayout(hist_layout)
        layout.addWidget(self.hist_group)

        # Spectrogram Config
        self.spec_group = QGroupBox("Spectrogram Settings")
        spec_layout = QHBoxLayout()

        spec_layout.addWidget(QLabel("Time Window (s):"))
        self.spec_window = QDoubleSpinBox()
        self.spec_window.setRange(0.1, 10.0)
        self.spec_window.setValue(1.0)
        self.spec_window.valueChanged.connect(self._config_changed)
        spec_layout.addWidget(self.spec_window)

        spec_layout.addWidget(QLabel("Colormap:"))
        self.colormap = QComboBox()
        self.colormap.addItems(["viridis", "plasma", "magma", "inferno"])
        self.colormap.currentTextChanged.connect(self._config_changed)
        spec_layout.addWidget(self.colormap)

        self.spec_group.setLayout(spec_layout)
        layout.addWidget(self.spec_group)

        self.setLayout(layout)

        # Connect signals
        self.plot_type.currentTextChanged.connect(self.update_visible_settings)
        self.update_visible_settings(self.plot_type.currentText())

    def _config_changed(self):
        """Handle configuration changes"""
        self.configChanged.emit(self.get_config())

    def update_visible_settings(self, plot_type):
        """Show/hide settings based on plot type"""
        self.fft_group.setVisible(plot_type == "FFT Analysis")
        self.hist_group.setVisible(plot_type == "Histogram")
        self.spec_group.setVisible(plot_type == "Spectrogram")
        self._config_changed()

    def get_config(self) -> dict:
        """Get current plot configuration"""
        config = {
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
        return config


class StatisticsPanel(QGroupBox):
    """Panel for displaying statistical analysis"""

    def __init__(self, parent=None):
        super().__init__("Statistical Analysis", parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()

        # Statistics table
        headers = ["Cavity", "Mean", "Std Dev", "Min", "Max", "Outliers"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("font-weight: bold")
            layout.addWidget(label, 0, col)

        self.stat_widgets = {}
        for row in range(1, 9):  # 8 cavities
            cavity_label = QLabel(f"Cavity {row}")
            layout.addWidget(cavity_label, row, 0)

            self.stat_widgets[row] = {
                'mean': QLabel("0.0"),
                'std': QLabel("0.0"),
                'min': QLabel("0.0"),
                'max': QLabel("0.0"),
                'outliers': QLabel("0")
            }

            for col, (key, widget) in enumerate(self.stat_widgets[row].items(), 1):
                layout.addWidget(widget, row, col)

        self.setLayout(layout)

    def update_statistics(self, cavity_num, stats):
        """Update statistics for a cavity

        Args:
            cavity_num: Cavity number (1-8)
            stats: Dict containing mean, std, min, max, outliers
        """
        if cavity_num in self.stat_widgets:
            widgets = self.stat_widgets[cavity_num]
            widgets['mean'].setText(f"{stats['mean']:.2f}")
            widgets['std'].setText(f"{stats['std']:.2f}")
            widgets['min'].setText(f"{stats['min']:.2f}")
            widgets['max'].setText(f"{stats['max']:.2f}")
            widgets['outliers'].setText(str(stats['outliers']))


class DataLoadingGroup(QGroupBox):
    """Group box for loading previous data"""
    dataLoaded = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__("Data Loading", parent)
        self.base_path = Path("/u1/lcls/physics/rf_lcls2/microphonics/")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Load data button
        self.load_button = QPushButton("Load Previous Data")
        self.load_button.clicked.connect(self.load_data)
        layout.addWidget(self.load_button)

        # File info
        self.file_info = QLabel("No file loaded")
        layout.addWidget(self.file_info)

        self.setLayout(layout)

    def load_data(self):
        """Open file dialog to load previous data"""
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
        """Get currently selected file path"""
        text = self.file_info.text()
        if text.startswith("Loaded: "):
            return self.base_path / text[8:]
        return None
