from pathlib import Path
from typing import Dict, List

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMessageBox
)

from applications.microphonics.components.components import (
    ChannelSelectionGroup, PlotConfigGroup,
    DataLoadingGroup
)
from applications.microphonics.gui.async_data_manager import AsyncDataManager, MeasurementConfig
from applications.microphonics.gui.config_panel import ConfigPanel
from applications.microphonics.gui.plot_panel import PlotPanel
from applications.microphonics.gui.statistics_calculator import StatisticsCalculator
from applications.microphonics.gui.status_panel import StatusPanel


class MicrophonicsGUI(QMainWindow):
    """Main window for the LCLS-II Microphonics measurement system"""
    measurementError = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LCLS-II Microphonics Measurement")
        self.setMinimumSize(1200, 800)

        self.measurement_errors = []  # Track errors during measurement

        self.stats_calculator = StatisticsCalculator()
        self.cavity_data = {}  # Store data for statistics calculation

        # Add error signal connection
        self.measurementError.connect(self._handle_measurement_error)

        # Add data manager
        self.data_manager = AsyncDataManager()

        # Connect data manager signals
        self.data_manager.acquisitionProgress.connect(self._handle_progress)
        self.data_manager.acquisitionError.connect(self._handle_error)
        self.data_manager.dataReceived.connect(self._handle_new_data)
        self.data_manager.acquisitionComplete.connect(self._handle_completion)

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

        # Store the current channel selection
        self.current_channels = []

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
        print("Configuration changed:", config)
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

    def _split_chassis_config(self, config: dict) -> Dict[str, Dict]:
        """Split configuration by chassis (A/B) and include channel selection"""
        print("\nDebug: Starting _split_chassis_config")
        print(f"Debug: Input config: {config}")
        result = {}

        # Get selected channels from ChannelSelectionGroup
        selected_channels = self.channel_selection.get_selected_channels()
        print(f"Debug: Selected channels: {selected_channels}")

        if not config.get('modules'):
            print("Debug: No modules in config")
            return result

        for module in config['modules']:
            print(f"\nDebug: Processing module: {module}")
            base_channel = module['base_channel']

            # Group cavities by rack (A/B)
            rack_a_cavities = []
            rack_b_cavities = []

            for cavity_num, is_selected in config['cavities'].items():
                print(f"Debug: Checking cavity {cavity_num}: {is_selected}")
                if is_selected:  # Only add selected cavities
                    if cavity_num <= 4:
                        rack_a_cavities.append(cavity_num)
                    else:
                        rack_b_cavities.append(cavity_num)

            print(f"Debug: Rack A cavities: {rack_a_cavities}")
            print(f"Debug: Rack B cavities: {rack_b_cavities}")

            # Create configs for each rack that has selected cavities
            if rack_a_cavities:
                chassis_id = f"{base_channel}:RESA"
                result[chassis_id] = {
                    'pv_base': f"ca://{base_channel}:RESA:",  # Add trailing colon
                    'config': MeasurementConfig(
                        channels=selected_channels,
                        decimation=config['decimation'],
                        buffer_count=config['buffer_count']
                    ),
                    'cavities': rack_a_cavities
                }
                print(f"Debug: Added Rack A config: {result[chassis_id]}")

            if rack_b_cavities:
                chassis_id = f"{base_channel}:RESB"
                result[chassis_id] = {
                    'pv_base': f"ca://{base_channel}:RESB:",  # Add trailing colon
                    'config': MeasurementConfig(
                        channels=selected_channels,
                        decimation=config['decimation'],
                        buffer_count=config['buffer_count']
                    ),
                    'cavities': rack_b_cavities
                }
                print(f"Debug: Added Rack B config: {result[chassis_id]}")

        print(f"\nDebug: Final result: {result}")
        return result

    def start_measurement(self):
        """Start the measurement process"""
        print("Start measurement clicked")
        try:
            self.measurement_errors = []
            # Remove cothread.Spawn and use QTimer
            QTimer.singleShot(0, self._start_measurement_async)
        except Exception as e:
            print(f"Error in start_measurement: {str(e)}")
            QMessageBox.critical(self, "Error", str(e))

    def _handle_measurement_error(self, error_msg):
        """Handle measurement errors with non-modal dialog"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(error_msg)
        msg_box.setWindowTitle("Error")
        msg_box.setModal(False)  # Make dialog non-modal
        msg_box.show()

    def _start_measurement_async(self):
        """Async portion of start measurement"""
        try:
            self.plot_panel.clear_plots()  # Clear old plots before starting new measurement
            config = self.config_panel.get_config()
            print("Current config:", config)

            # Check for cross-CM cavity selection
            selected_cavities = [num for num, selected in config['cavities'].items() if selected]
            low_cm = any(c <= 4 for c in selected_cavities)
            high_cm = any(c > 4 for c in selected_cavities)
            if low_cm and high_cm:
                raise ValueError("ERROR: Cavity selection crosses half-CM")

            if not any(config['cavities'].values()):
                raise ValueError("No cavities selected - please select at least one cavity")

            self.current_channels = self.channel_selection.get_selected_channels()
            if not self.current_channels:
                raise ValueError("No channels selected for measurement")

            chassis_config = self._split_chassis_config(config)
            if not chassis_config:
                selected_cavities = [num for num, selected in config['cavities'].items() if selected]
                raise ValueError(f"No valid chassis configuration created. Selected cavities: {selected_cavities}")

            print("Chassis config:", chassis_config)

            self.measurement_running = True
            self.config_panel.set_measurement_running(True)
            self.channel_selection.setEnabled(False)
            self.data_loading.setEnabled(False)

            self.data_manager.initiate_measurement(chassis_config)
            print("Measurement started successfully")

        except Exception as e:
            print(f"Error in _start_measurement_async: {str(e)}")
            self.measurementError.emit(str(e))
            self.measurement_running = False
            self.config_panel.set_measurement_running(False)
            self.channel_selection.setEnabled(True)
            self.data_loading.setEnabled(True)

    def stop_measurement(self):
        """Stop the measurement process"""
        print("Stop measurement called")
        if self.measurement_running:
            self.plot_panel.clear_plots()  # Clear plots when stopping
            self.data_manager.stop_all()
            self.measurement_running = False
            self.config_panel.set_measurement_running(False)
            self.channel_selection.setEnabled(True)
            self.data_loading.setEnabled(True)
            self.measurement_errors.clear()

            # Clear stored cavity data and reset statistics
            self.cavity_data.clear()
            for cavity_num in range(1, 9):
                self.status_panel.update_statistics(cavity_num, {
                    'mean': 0.0,
                    'std': 0.0,
                    'min': 0.0,
                    'max': 0.0,
                    'outliers': 0
                })

            self.config_panel._config_changed()

    def _handle_new_data(self, chassis_id: str, data: dict):
        """Handle new data from measurement"""
        cavity_num = data['cavity']

        # Only process channels that were selected when measurement started
        buffer_data = {
            channel: data['channels'][channel]
            for channel in self.current_channels
            if channel in data['channels']
        }

        # Update plot panel with new data
        self.plot_panel.update_plots(cavity_num, buffer_data)

    def _handle_error(self, chassis_id: str, error_msg: str):
        """Show modal error dialogs during tests"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(error_msg)
        msg_box.setWindowTitle("Error")
        msg_box.setModal(True)  # Force modal for test detection
        msg_box.show()

    def _handle_completion(self, chassis_id: str):
        """Handle measurement completion"""
        # Check if all measurements are complete by checking active acquisitions
        if chassis_id in self.data_manager.active_acquisitions:
            self.data_manager.active_acquisitions.remove(chassis_id)

        if not self.data_manager.active_acquisitions:
            # All acquisitions are complete, reset GUI state
            self.measurement_running = False
            self.config_panel.set_measurement_running(False)
            self.channel_selection.setEnabled(True)
            self.data_loading.setEnabled(True)

    def _finalize_measurement(self):
        """Final measurement cleanup and status checks"""
        # 1. Check active processes from data manager
        active_processes = getattr(self.data_manager.data_manager, 'active_processes', {})

        # 2. Only proceed if ALL acquisitions completed
        if active_processes:
            return

        # 3. Update measurement state
        self.measurement_running = False
        self.config_panel.set_measurement_running(False)

        # 4. Handle errors/success
        if self.measurement_errors:
            # Show combined errors
            error_text = "\n".join(set(self.measurement_errors))  # Deduplicate
            QMessageBox.critical(self, "Measurement Errors", error_text)
        else:
            # Show success
            QMessageBox.information(self, "Complete",
                                    "Measurement completed successfully")

        # 5. Cleanup
        self.measurement_errors.clear()
        self.config_panel._config_changed()  # Refresh UI state

    def _handle_progress(self, chassis_id: str, cavity_num: int, progress: int):
        """Handle progress updates from measurement"""
        self.status_panel.update_cavity_status(
            cavity_num,
            "Running",
            progress,
            f"Buffer acquisition: {progress}%"
        )

    def _handle_new_data(self, chassis_id: str, data: dict):
        """Handle new data from measurement"""
        cavity_num = data['cavity']

        # Only process channels that were selected when measurement started
        buffer_data = {
            channel: data['channels'][channel]
            for channel in self.current_channels
            if channel in data['channels']
        }

        # Store DF data for statistics calculation
        if 'DF' in buffer_data:
            self.cavity_data[cavity_num] = buffer_data['DF']

            # Calculate statistics for this cavity
            stats = self.stats_calculator.calculate_statistics(buffer_data['DF'])
            panel_stats = self.stats_calculator.convert_to_panel_format(stats)

            # Update statistics panel
            self.status_panel.update_statistics(cavity_num, panel_stats)

        # Update plot panel with new data
        self.plot_panel.update_plots(cavity_num, buffer_data)

    def load_data(self, file_path: Path):
        """Load data from file"""
        try:
            # TODO: Implement data loading
            # TODO: Update plots
            pass
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")

    def closeEvent(self, event):
        """Ensure clean shutdown"""
        if hasattr(self, 'data_manager'):
            self.data_manager.stop_all()  # This calls the AsyncDataManager's stop_all
        super().closeEvent(event)
