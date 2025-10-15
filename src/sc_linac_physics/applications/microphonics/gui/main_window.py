import logging
from pathlib import Path
from typing import Dict

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QMessageBox
from pydm import Display

from sc_linac_physics.applications.microphonics.components.components import (
    ChannelSelectionGroup,
    DataLoadingGroup,
)
from sc_linac_physics.applications.microphonics.gui.async_data_manager import (
    MeasurementConfig,
    AsyncDataManager,
)
from sc_linac_physics.applications.microphonics.gui.config_panel import ConfigPanel
from sc_linac_physics.applications.microphonics.gui.data_loader import DataLoader
from sc_linac_physics.applications.microphonics.gui.statistics_calculator import StatisticsCalculator
from sc_linac_physics.applications.microphonics.gui.status_panel import StatusPanel
from sc_linac_physics.applications.microphonics.plots.plot_panel import PlotPanel
from sc_linac_physics.applications.microphonics.utils.pv_utils import format_pv_base

logger = logging.getLogger(__name__)


class MicrophonicsGUI(Display):
    """Main window for the Microphonics GUI Measurement system"""

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("LCLS-II Microphonics Measurement")
        self.setMinimumSize(1200, 800)

        self.stats_calculator = StatisticsCalculator()

        # Data Manager
        self.data_manager = AsyncDataManager()

        # Connect job level signals
        self.data_manager.jobProgress.connect(self._handle_job_progress)
        self.data_manager.jobError.connect(self._handle_job_error)
        self.data_manager.jobComplete.connect(self._handle_job_complete)

        # Connect data manager signals
        self.data_manager.acquisitionProgress.connect(self._handle_progress)
        self.data_manager.acquisitionError.connect(
            lambda chassis_id, msg: self._show_error_message(f"Chassis {chassis_id}: {msg}", title="Acquisition Error")
        )
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

    def init_panels(self):
        """Initialize all panels"""
        # Left panel components
        self.config_panel = ConfigPanel()
        self.status_panel = StatusPanel()
        self.channel_selection = ChannelSelectionGroup()
        self.data_loading = DataLoadingGroup()

        # Right panel components
        self.plot_panel = PlotPanel(config_panel_ref=self.config_panel)

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
        self.data_loading.file_selected.connect(self.load_data)

    def on_config_changed(self, config: Dict):
        logger.info("Configuration changed: %s", config)
        try:
            # Update UI based on new configuration
            if not self.measurement_running:
                self.status_panel.reset_all()
                selected_cavities = config["cavities"]
                for cavity in selected_cavities:
                    self.status_panel.update_cavity_status(cavity, "Ready", 0, "Configured for measurement")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Configuration error: {str(e)}")

    def _split_chassis_config(self, config: dict) -> Dict[str, Dict]:
        """Split configuration by chassis (A/B) and include channel selection"""
        result = {}

        # Get selected channels from ChannelSelectionGroup
        selected_channels_ui = self.channel_selection.get_selected_channels()
        logger.debug("Selected channels (from UI): %s", selected_channels_ui)

        channels_for_script = selected_channels_ui
        logger.debug("Channels actually sent to script: %s", channels_for_script)

        if not config.get("modules"):
            logger.debug("No modules in config.")
            return result

        for module in config["modules"]:
            logger.debug("Processing module: %s", module)
            base_channel = module["base_channel"]

            # Group cavities by rack (A/B)
            rack_a_cavities = []
            rack_b_cavities = []

            for cavity_num, is_selected in config["cavities"].items():
                logger.debug("Checking cavity %s: selected=%s", cavity_num, is_selected)
                if is_selected:  # Only process selected cavities
                    if cavity_num <= 4:
                        rack_a_cavities.append(cavity_num)
                    else:
                        rack_b_cavities.append(cavity_num)
            logger.debug("Rack A cavities: %s", rack_a_cavities)
            logger.debug("Rack B cavities: %s", rack_b_cavities)

            # Create configs for each rack that has selected cavities
            if rack_a_cavities:
                chassis_id = f"{base_channel}:RESA"
                result[chassis_id] = {
                    "pv_base": format_pv_base(base_channel, "A"),
                    "config": MeasurementConfig(
                        channels=channels_for_script,
                        decimation=config["decimation"],
                        buffer_count=config["buffer_count"],
                    ),
                    "cavities": rack_a_cavities,
                }
                logger.debug("Added Rack A config: %s", result[chassis_id])

            if rack_b_cavities:
                chassis_id = f"{base_channel}:RESB"
                result[chassis_id] = {
                    "pv_base": format_pv_base(base_channel, "B"),
                    "config": MeasurementConfig(
                        channels=channels_for_script,
                        decimation=config["decimation"],
                        buffer_count=config["buffer_count"],
                    ),
                    "cavities": rack_b_cavities,
                }
                logger.debug("Added Rack B config: %s", result[chassis_id])

        logger.debug("Final chassis config: %s", result)
        return result

    def start_measurement(self):
        """Start the measurement process"""
        logger.info("Start measurement clicked")
        try:
            # Remove cothread.Spawn and use QTimer
            QTimer.singleShot(0, self._start_measurement_async)
        except Exception as e:
            logger.exception("Unexpected error in start_measurement")
            QMessageBox.critical(self, "Error", str(e))

    def _start_measurement_async(self):
        """Async portion of start measurement"""
        try:
            config = self.config_panel.get_config()
            # A check to see if any cavities are selected
            selected_cavities = [num for num, selected in config["cavities"].items() if selected]
            if not selected_cavities:
                self._show_error_message("Please select at least one cavity before starting.", is_modal=False)
                return
            self.plot_panel.clear_plots()  # Clear old plots before starting new measurement
            logger.info("Current config: %s", config)

            # Check for cross CM cavity selection
            low_cm = any(c <= 4 for c in selected_cavities)
            high_cm = any(c > 4 for c in selected_cavities)
            if low_cm and high_cm:
                logger.info("Cavities span both racks, using parallel acquisition.")

            chassis_config = self._split_chassis_config(config)
            if not chassis_config:
                raise ValueError(f"No valid chassis configuration created. Selected cavities: {selected_cavities}")

            logger.info("Split chassis config: %s", chassis_config)

            self._reset_measurement_ui_state(is_running=True)

            self.data_manager.initiate_measurement(chassis_config)
            logger.info("Measurement started successfully.")

        except Exception as e:
            logger.exception("Failed to start measurement")
            self._show_error_message(str(e))
            self.measurement_running = False
            self.config_panel.set_measurement_running(False)
            self.channel_selection.setEnabled(True)
            self.data_loading.setEnabled(True)

    def stop_measurement(self):
        """Stop the measurement process"""
        logger.info("Stop measurement called.")
        self.data_manager.stop_all()
        self._reset_measurement_ui_state(is_running=False)
        self.plot_panel.clear_plots()
        self.status_panel.reset_all()

    def _show_error_message(self, message: str, title: str = "Error", is_modal: bool = True):
        """Displays critical error message box."""
        logger.error("Displaying error to user: %s - %s", title, message)
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(message)
        msg_box.setWindowTitle(title)
        msg_box.setModal(is_modal)
        msg_box.show()

    def _reset_measurement_ui_state(self, is_running: bool):
        """Enable/disable UI components based on measurement state."""
        self.measurement_running = is_running
        self.config_panel.set_measurement_running(is_running)
        self.channel_selection.setEnabled(not is_running)
        self.data_loading.setEnabled(not is_running)

    def _handle_job_progress(self, overall_progress: int):
        """Handle overall job progress"""
        logger.info("Overall job progress: %s%%", overall_progress)

    def _handle_job_error(self, error_msg: str):
        """Handle job-level errors"""
        logger.error("Job error: %s", error_msg)
        # Reset UI state
        self._reset_measurement_ui_state(is_running=False)

        # Show error to user
        QMessageBox.critical(self, "Measurement Failed", error_msg)

    def _handle_job_complete(self, aggregated_data: dict):
        """Handle job completion w/ aggregated data from all racks"""
        logger.debug("Job completed, processing aggregated data.")

        # Process aggregated data
        self._handle_new_data("measurement", aggregated_data)

        # Reset UI state
        self.measurement_running = False
        self.config_panel.set_measurement_running(False)
        self.channel_selection.setEnabled(True)
        self.data_loading.setEnabled(True)

    def _handle_completion(self, chassis_id: str):
        """Handle rack completion"""
        logger.debug("Rack %s completed.", chassis_id)

    def _handle_progress(self, chassis_id: str, cavity_num: int, progress: int):
        """Handle progress updates from measurement"""
        self.status_panel.update_cavity_status(cavity_num, "Running", progress, f"Buffer acquisition: {progress}%")

    def _handle_new_data(self, source: str, data_dict: dict):
        """Handle new data from measurement or file"""
        logger.debug("_handle_new_data received from '%s'", source)

        try:
            cavity_list = data_dict.get("cavity_list", [])
            all_cavity_data = data_dict.get("cavities", {})

            if not cavity_list:
                logger.warning("Received data with no cavities.")
                return

            for cavity_num in cavity_list:
                cavity_channel_data = all_cavity_data.get(cavity_num)

                if not cavity_channel_data:
                    logger.warning("No channel data found for cavity %s in data_dict['cavities'].", cavity_num)
                    continue

                df_data = cavity_channel_data.get("DF")

                # Check if DF data is valid for stats
                try:
                    if df_data is not None and df_data.size > 0:
                        stats = self.stats_calculator.calculate_statistics(df_data)
                        panel_stats = self.stats_calculator.convert_to_panel_format(stats)
                        self.status_panel.update_statistics(cavity_num, panel_stats)
                    else:
                        logger.warning("No valid 'DF' data for statistics for cavity %s.", cavity_num)
                        self.status_panel.update_cavity_status(cavity_num, "Complete", 100, "No DF data for stats")

                except Exception:
                    logger.exception("Failed to calculate statistics for Cavity %s", cavity_num)
                    self._show_error_message(
                        f"Could not calculate statistics for Cavity {cavity_num}.",
                        title="Data Processing Warning",
                        is_modal=False,
                    )
            logger.debug("Calling plot_panel.update_plots w/ data for cavities: %s", cavity_list)
            self.plot_panel.update_plots(data_dict)

        except Exception:
            logger.exception("Critical error while processing new data from source '%s'", source)
            self._show_error_message("An unexpected error occurred while processing data.", title="Processing Error")

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
        logger.error("Error loading data: %s", error_msg)
        self.data_loading.update_file_info("Error loading file")
        QMessageBox.critical(self, "Error", error_msg)

    def _handle_load_progress(self, progress: int):
        """Handle progress updates during data loading"""
        self.data_loading.update_file_info(f"Loading: {progress}%")

    def closeEvent(self, event):
        """Ensure clean shutdown"""
        if hasattr(self, "data_manager"):
            self.data_manager.stop_all()
        super().closeEvent(event)
