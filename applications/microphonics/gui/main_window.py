"""Main window for the Microphonics measurement application"""

from pathlib import Path
from typing import Dict, List

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMessageBox
)

from applications.microphonics.components.components import (
    ChannelSelectionGroup, PlotConfigGroup,
    StatisticsPanel, DataLoadingGroup
)
from applications.microphonics.gui.config_panel import ConfigPanel
from applications.microphonics.gui.plot_panel import PlotPanel
from applications.microphonics.gui.status_panel import StatusPanel


class MicrophonicsGUI(QMainWindow):
    """Main window for the LCLS-II Microphonics measurement system"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LCLS-II Microphonics Measurement")
        self.setMinimumSize(1200, 800)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create left and right panel layouts
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Initialize all panels
        self.init_panels()

        # Add panels to layouts
        self.setup_left_panel(left_layout)
        self.setup_right_panel(right_layout)

        # Add panels to main layout
        main_layout.addWidget(left_panel, stretch=4)  # 40% width
        main_layout.addWidget(right_panel, stretch=6)  # 60% width

        # Connect signals
        self.connect_signals()

        # Initialize measurement state
        self.measurement_running = False

    def init_panels(self):
        """Initialize all panels"""
        # Left panel components
        self.config_panel = ConfigPanel()
        self.channel_selection = ChannelSelectionGroup()
        self.data_loading = DataLoadingGroup()
        self.status_panel = StatusPanel()

        # Right panel components
        self.plot_config = PlotConfigGroup()
        self.plot_panel = PlotPanel()
        self.statistics = StatisticsPanel()

    def setup_left_panel(self, layout: QVBoxLayout):
        """Setup the left side of the window"""
        layout.addWidget(self.config_panel)
        layout.addWidget(self.channel_selection)
        layout.addWidget(self.data_loading)
        layout.addWidget(self.status_panel)
        layout.addStretch()

    def setup_right_panel(self, layout: QVBoxLayout):
        """Setup the right side of the window"""
        layout.addWidget(self.plot_config)
        layout.addWidget(self.plot_panel)
        layout.addWidget(self.statistics)

    def connect_signals(self):
        """Connect all panel signals"""
        # Config panel signals
        self.config_panel.configChanged.connect(self.on_config_changed)
        self.config_panel.measurementStarted.connect(self.start_measurement)
        self.config_panel.measurementStopped.connect(self.stop_measurement)

        # Channel selection signals
        self.channel_selection.channelsChanged.connect(self.on_channels_changed)

        # Plot configuration signals
        self.plot_config.configChanged.connect(self.plot_panel.set_plot_config)

        # Data loading signals
        self.data_loading.dataLoaded.connect(self.load_data)

    def on_config_changed(self, config: Dict):
        """Handle configuration changes"""
        try:
            # Update UI based on new configuration
            if not self.measurement_running:
                self.status_panel.reset_all()
                selected_cavities = config['cavities']
                for cavity in selected_cavities:
                    self.status_panel.update_cavity_status(
                        cavity,
                        "Ready",
                        0,
                        "Configured for measurement"
                    )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Configuration error: {str(e)}")

    def on_channels_changed(self, channels: List[str]):
        """Handle channel selection changes"""
        if self.measurement_running:
            return
        # Update UI based on selected channels
        pass

    def start_measurement(self):
        """Start the measurement process"""
        try:
            self.measurement_running = True
            config = self.config_panel.get_config()
            channels = self.channel_selection.get_selected_channels()

            # Update UI state
            self.config_panel.set_enabled(False)
            self.channel_selection.setEnabled(False)
            self.data_loading.setEnabled(False)

            # TODO: Initialize measurement hardware
            # TODO: Start data acquisition

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start measurement: {str(e)}")
            self.stop_measurement()

    def stop_measurement(self):
        """Stop the measurement process"""
        try:
            self.measurement_running = False

            # Update UI state
            self.config_panel.set_enabled(True)
            self.channel_selection.setEnabled(True)
            self.data_loading.setEnabled(True)

            # TODO: Stop data acquisition
            # TODO: Cleanup hardware

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error during measurement stop: {str(e)}")

    def load_data(self, file_path: Path):
        """Load data from file"""
        try:
            # TODO: Implement data loading
            # TODO: Update plots and statistics
            pass
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")

    def closeEvent(self, event):
        """Handle application close"""
        if self.measurement_running:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "A measurement is running. Do you want to stop it and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.stop_measurement()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
