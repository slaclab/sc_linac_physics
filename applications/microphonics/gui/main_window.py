import traceback
from pathlib import Path
from typing import Dict

import numpy as np
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QMessageBox

)
from pydm import Display

from applications.microphonics.components.components import (
    ChannelSelectionGroup, DataLoadingGroup
)
from applications.microphonics.gui.async_data_manager import MeasurementConfig, AsyncDataManager
from applications.microphonics.gui.config_panel import ConfigPanel
from applications.microphonics.gui.data_loader import DataLoader
from applications.microphonics.gui.statistics_calculator import StatisticsCalculator
from applications.microphonics.gui.status_panel import StatusPanel
from applications.microphonics.plots.plot_panel import PlotPanel
from applications.microphonics.utils.pv_utils import format_pv_base


class MicrophonicsGUI(Display):
    """Main window for the Microphonics GUI Measurement system"""
    measurementError = pyqtSignal(str)

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("LCLS-II Microphonics Measurement")
        self.setMinimumSize(1200, 800)

        self.stats_calculator = StatisticsCalculator()

        # Error signal connection
        self.measurementError.connect(self._handle_measurement_error)

        # Data Manager
        self.data_manager = AsyncDataManager(self)

        # Connect job level signals
        self.data_manager.jobProgress.connect(self._handle_job_progress)
        self.data_manager.jobError.connect(self._handle_job_error)
        self.data_manager.jobComplete.connect(self._handle_job_complete)

        # Connect data manager signals
        self.data_manager.acquisitionProgress.connect(self._handle_progress)
        self.data_manager.acquisitionError.connect(self._handle_error)
        self.data_manager.acquisitionComplete.connect(self._handle_completion)

        # Main Layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        # Setting layout on display widget
        self.setLayout(main_layout)

        # Left and right panel layouts
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(2, 2, 2, 2)
        left_layout.setSpacing(5)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(0)

        # Initialize all panels
        self.init_panels()

        # Add panels to layouts
        self.setup_left_panel(left_layout)
        self.setup_right_panel(right_layout)

        # Add panels to main layout w/ adjusted proportions
        main_layout.addWidget(left_panel, stretch=4)  # 40% width
        main_layout.addWidget(right_panel, stretch=6)  # 60% width

        # Connect signals
        self.connect_signals()

        # Initialize measurement state
        self.measurement_running = False

        # Initialize data loader
        self.data_loader = DataLoader()

        # Connect data loader signals
        self.data_loader.dataLoaded.connect(lambda data: self._handle_new_data("file", data))
        self.data_loader.loadError.connect(self._handle_load_error)
        self.data_loader.loadProgress.connect(self._handle_load_progress)

    def ui_filename(self):
        """Return None because this display is created only in Python."""
        return None

    def init_panels(self):
        """Initialize all panels"""
        # Left panel components
        self.config_panel = ConfigPanel()
        self.status_panel = StatusPanel()
        self.channel_selection = ChannelSelectionGroup()
        self.data_loading = DataLoadingGroup()

        # Right panel components
        self.plot_panel = PlotPanel(self, config_panel_ref=self.config_panel)

    def setup_left_panel(self, layout: QVBoxLayout):
        """Setup left side of the window"""
        layout.addWidget(self.config_panel)
        layout.addWidget(self.channel_selection)
        layout.addWidget(self.data_loading)
        layout.addWidget(self.status_panel)
        layout.addStretch()

    def setup_right_panel(self, layout: QVBoxLayout):
        """Setup right side of the window"""
        layout.addWidget(self.plot_panel)

    def connect_signals(self):
        """Connect all panel signals"""
        # Config panel signals
        self.config_panel.configChanged.connect(self.on_config_changed)
        self.config_panel.measurementStarted.connect(self.start_measurement)
        self.config_panel.measurementStopped.connect(self.stop_measurement)
        self.config_panel.decimationSettingChanged.connect(self.plot_panel.refresh_plots_if_decimation_changed)

        # Data loading signals
        self.data_loading.fileSelected.connect(self.load_data)

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

    def _split_chassis_config(self, config: dict) -> Dict[str, Dict]:
        """Split configuration by chassis (A/B) and include channel selection"""
        result = {}

        # Get selected channels from ChannelSelectionGroup
        selected_channels_ui = self.channel_selection.get_selected_channels()
        print(f"Debug: Selected channels (from UI): {selected_channels_ui}")

        # For debug: hardcode channel selection
        channels_for_script = selected_channels_ui
        print(f"Debug: Channels actually sent to script: {channels_for_script}")

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
                if is_selected:  # Only process selected cavities
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
                    'pv_base': format_pv_base(base_channel, 'A'),
                    'config': MeasurementConfig(
                        channels=channels_for_script,
                        decimation=config['decimation'],
                        buffer_count=config['buffer_count']
                    ),
                    'cavities': rack_a_cavities
                }
                # Check which channels were actually used
                print(f"Debug: Added Rack A config (using {channels_for_script}): {result[chassis_id]}")

            if rack_b_cavities:
                chassis_id = f"{base_channel}:RESB"
                result[chassis_id] = {
                    'pv_base': format_pv_base(base_channel, 'B'),
                    'config': MeasurementConfig(
                        channels=channels_for_script,
                        decimation=config['decimation'],
                        buffer_count=config['buffer_count']
                    ),
                    'cavities': rack_b_cavities
                }
                # Checking which channel was used
                print(f"Debug: Added Rack B config (using {channels_for_script}): {result[chassis_id]}")

        print(f"\nDebug: Final result: {result}")
        return result

    def start_measurement(self):
        """Start the measurement process"""
        print("Start measurement clicked")
        try:
            # Remove cothread.Spawn and use QTimer
            QTimer.singleShot(0, self._start_measurement_async)
        except Exception as e:
            print(f"Error in start_measurement: {str(e)}")
            QMessageBox.critical(self, "Error", str(e))

    def _handle_measurement_error(self, error_msg):
        """Handle measurement errors"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(error_msg)
        msg_box.setWindowTitle("Error")
        msg_box.setModal(False)
        msg_box.show()

    def _start_measurement_async(self):
        """Async portion of start measurement"""
        try:
            self.plot_panel.clear_plots()  # Clear old plots before starting new measurement
            config = self.config_panel.get_config()
            print("Current config:", config)

            # Check for cross CM cavity selection
            selected_cavities = [num for num, selected in config['cavities'].items() if selected]
            low_cm = any(c <= 4 for c in selected_cavities)
            high_cm = any(c > 4 for c in selected_cavities)
            if low_cm and high_cm:
                print("Note: Cavities span both racks - will use parallel acquisition")

            if not any(config['cavities'].values()):
                raise ValueError("No cavities selected - please select at least one cavity")

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

            for cavity_num in range(1, 9):
                self.status_panel.update_statistics(cavity_num, {
                    'mean': 0.0,
                    'std': 0.0,
                    'min': 0.0,
                    'max': 0.0,
                    'outliers': 0
                })

    def _handle_error(self, chassis_id: str, error_msg: str):
        """Show modal error dialogs during tests"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(error_msg)
        msg_box.setWindowTitle("Error")
        msg_box.setModal(True)
        msg_box.show()

    def _handle_job_progress(self, overall_progress: int):
        """Handle overall job progress"""
        print(f"Overall job progress: {overall_progress}%")

    def _handle_job_error(self, error_msg: str):
        """Handle job-level errors"""
        print(f"Job error: {error_msg}")
        # Reset UI state
        self.measurement_running = False
        self.config_panel.set_measurement_running(False)
        self.channel_selection.setEnabled(True)
        self.data_loading.setEnabled(True)

        # Show error to user
        QMessageBox.critical(self, "Measurement Failed", error_msg)

    def _handle_job_complete(self, aggregated_data: dict):
        """Handle job completion w/ aggregated data from all racks"""
        print("DEBUG: Job completed, processing aggregated data")

        # Process aggregated data
        self._handle_new_data("measurement", aggregated_data)

        # Reset UI state
        self.measurement_running = False
        self.config_panel.set_measurement_running(False)
        self.channel_selection.setEnabled(True)
        self.data_loading.setEnabled(True)

    def _handle_completion(self, chassis_id: str):
        """Handle rack completion"""
        print(f"DEBUG: Rack {chassis_id} completed")

    def _handle_progress(self, chassis_id: str, cavity_num: int, progress: int):
        """Handle progress updates from measurement"""
        self.status_panel.update_cavity_status(
            cavity_num,
            "Running",
            progress,
            f"Buffer acquisition: {progress}%"
        )

    def _handle_new_data(self, source: str, data_dict: dict):
        """Handle new data from measurement or file"""
        print(f"DEBUG: _handle_new_data received from '{source}'")

        try:
            # Get list of cavities and nested cavity data
            cavity_list = data_dict.get('cavity_list', [])
            all_cavity_data = data_dict.get('cavities', {})

            if not cavity_list:
                print("WARN: _handle_new_data received empty cavity list or missing 'cavity_list' key.")
                return  # Nothing to process

            # Update stats for each cavity present i
            for cavity_num in cavity_list:
                cavity_channel_data = all_cavity_data.get(cavity_num)

                if not cavity_channel_data:
                    print(f"WARN: No channel data found for cavity {cavity_num} in data_dict['cavities'].")
                    continue

                df_data = cavity_channel_data.get('DF')

                # Check if DF data is valid for stats
                if df_data is not None and isinstance(df_data, np.ndarray) and df_data.size > 0:
                    try:
                        stats = self.stats_calculator.calculate_statistics(df_data)
                        panel_stats = self.stats_calculator.convert_to_panel_format(stats)

                        # Update stats display in the status panel
                        self.status_panel.update_statistics(cavity_num, panel_stats)
                    except Exception as stat_err:
                        # Log error but continue processing other cavities/plots
                        print(f"ERROR: Failed to calculate/update stats for Cav {cavity_num}: {stat_err}")
                        traceback.print_exc()
                else:
                    # Log if DF data is missing or invalid for stats
                    print(f"WARN: No valid 'DF' data found for statistics for cavity {cavity_num}.")

            print(f"DEBUG: Calling plot_panel.update_plots w/ data for cavities: {cavity_list}")
            self.plot_panel.update_plots(data_dict)

        except KeyError as ke:
            # Catch errors if expected keys are missing from data_dict
            print(f"ERROR in _handle_new_data: Missing key {ke} in received data dictionary.")
            traceback.print_exc()
        except Exception as e:
            # Catch any other unexpected errors during processing
            print(f"CRITICAL ERROR in _handle_new_data processing data from '{source}': {str(e)}")
            traceback.print_exc()

    def load_data(self, file_path: Path):
        """Load data from file and display using existing visualization code."""
        try:
            # Clear existing plots
            self.plot_panel.clear_plots()

            # Load and process the data using DataLoader
            self.data_loader.load_file(file_path)

        except Exception as e:
            self._handle_load_error(f"Failed to load data: {str(e)}")

    def _handle_load_error(self, error_msg: str):
        """Handle errors during data loading"""
        print(f"Error loading data: {error_msg}")
        self.data_loading.update_file_info("Error loading file")
        QMessageBox.critical(self, "Error", error_msg)

    def _handle_load_progress(self, progress: int):
        """Handle progress updates during data loading"""
        self.data_loading.update_file_info(f"Loading: {progress}%")

    def closeEvent(self, event):
        """Ensure clean shutdown"""
        if hasattr(self, 'data_manager'):
            self.data_manager.stop_all()
        super().closeEvent(event)
