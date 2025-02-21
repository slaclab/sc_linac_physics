from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtCore import QThread, pyqtSignal

from applications.microphonics.gui.data_acquisition import DataAcquisitionManager


@dataclass
class MeasurementConfig:
    """Configuration settings for cavity measurements.
    Handles validation and conversion of measurement parameters."""

    channels: List[str]  # Channel names to measure
    buffer_length: int = 16384  # Number of samples per buffer
    sample_rate: int = 2000  # Samples per second
    decimation: int = 1  # Sample rate reduction factor
    buffer_count: int = 65  # Number of buffers to collect

    def validate(self) -> Optional[str]:
        """Validate configuration parameters against system constraints.

        Returns:
            Error message string if invalid, None if valid
        """
        if not self.channels:
            return "No channels specified"
        if self.decimation not in {1, 2, 4, 8}:
            return f"Invalid decimation value: {self.decimation}. Must be 1, 2, 4, or 8"
        if self.buffer_count < 1:
            return f"Invalid buffer count: {self.buffer_count}. Must be positive"
        return None

    def to_acquisition_config(self) -> Dict:
        """Convert configuration to format expected by hardware interface.

        Returns:
            Dictionary with hardware-specific configuration parameters
        """
        return {
            'decimation': self.decimation,
            'buffer_count': self.buffer_count,
            'channels': self.channels
        }


class AsyncDataManager(QObject):
    """Manages asynchronous data acquisition across multiple cavity chassis.

    Provides thread-safe interface between GUI and hardware manager, handling:
    - Configuration validation and error checking
    - Async acquisition management and lifecycle
    - Signal routing for status updates and data flow
    """

    # Signal definitions for acquisition lifecycle events
    acquisitionProgress = pyqtSignal(str, int, int)  # chassis_id, cavity_num, progress
    acquisitionError = pyqtSignal(str, str)  # chassis_id, error_message
    acquisitionComplete = pyqtSignal(str)  # chassis_id
    dataReceived = pyqtSignal(str, dict)  # chassis_id, data_dict

    def __init__(self):
        """Initialize manager with worker thread and signal connections."""
        super().__init__()

        # Setup worker thread for hardware operations
        self.thread = QThread()
        self.data_manager = DataAcquisitionManager()

        # Connect signals before moving to thread to ensure proper routing
        self.data_manager.acquisitionComplete.connect(self.acquisitionComplete)
        self.data_manager.acquisitionProgress.connect(self.acquisitionProgress)
        self.data_manager.acquisitionError.connect(self.acquisitionError)
        self.data_manager.dataReceived.connect(self.dataReceived)

        # Track active acquisitions for lifecycle management
        self.active_acquisitions = set()

        # Move manager to worker thread after signal setup
        self.data_manager.moveToThread(self.thread)
        self.thread.start()

    def _validate_chassis_config(self, chassis_id: str, config: dict) -> Optional[str]:
        """Validate configuration for a single chassis.

        Checks:
        - Cavity selection is present
        - No crossing of CM boundaries (prevents hardware issues)
        - PV base address is specified

        Args:
            chassis_id: Identifier for the chassis
            config: Configuration dictionary for this chassis

        Returns:
            Error message if invalid, None if valid
        """
        if not config.get('cavities'):
            return "No cavities specified for chassis"

        # Prevent selection across CM boundaries - hardware limitation
        low_cm = any(c <= 4 for c in config['cavities'])
        high_cm = any(c > 4 for c in config['cavities'])
        if low_cm and high_cm:
            return "ERROR: Cavity selection crosses half-CM"

        if not config.get('pv_base'):
            return "Missing PV base address"

        return None

    def _validate_all_configs(self, chassis_config: Dict) -> List[Tuple[str, str]]:
        """Validate configurations for all chassis before measurement.

        Performs complete validation including:
        - Chassis-specific configuration
        - Measurement parameters
        - Hardware constraints

        Args:
            chassis_config: Dictionary mapping chassis IDs to their configs

        Returns:
            List of (chassis_id, error_message) tuples for any invalid configs
        """
        if not chassis_config:
            return [("", "No chassis configurations provided")]

        errors = []
        for chassis_id, config in chassis_config.items():
            # Check chassis-specific settings
            if error := self._validate_chassis_config(chassis_id, config):
                errors.append((chassis_id, error))
                continue

            # Validate measurement parameters
            if error := config['config'].validate():
                errors.append((chassis_id, error))

        return errors

    def initiate_measurement(self, chassis_config: Dict):
        """Start measurements across multiple chassis from main thread.

        Args:
            chassis_config: Dictionary mapping chassis IDs to their configurations
        """
        errors = self._validate_all_configs(chassis_config)
        if errors:
            for chassis_id, error in errors:
                self.acquisitionError.emit(chassis_id, error)
            return

        # Track new acquisitions
        for chassis_id in chassis_config.keys():
            self.active_acquisitions.add(chassis_id)

        # Schedule starts in worker thread
        for chassis_id, config in chassis_config.items():
            QTimer.singleShot(0, lambda cid=chassis_id, cfg=config:
            self.data_manager.start_acquisition(cid, cfg))

    def _handle_measurement(self, chassis_config):
        """Execute measurement in worker thread context.

        Handles validation and startup with proper error propagation.

        Args:
            chassis_config: Configuration for all chassis
        """
        try:
            errors = self._validate_all_configs(chassis_config)
            if errors:
                chassis_id, error = errors[0]
                raise ValueError(f"Configuration error for {chassis_id}: {error}")

            for chassis_id, config in chassis_config.items():
                self.data_manager.start_acquisition(
                    chassis_id,
                    config['config'].to_acquisition_config()
                )

        except Exception as e:
            self.acquisitionError.emit(chassis_id, str(e))
            self.stop_measurement(chassis_id)
        finally:
            self.thread.quit()

    def stop_measurement(self, chassis_id: str):
        """Stop acquisition for a specific chassis safely.

        Args:
            chassis_id: Identifier for chassis to stop
        """
        try:
            if chassis_id in self.active_acquisitions:
                self.data_manager.stop_acquisition(chassis_id)
                self.active_acquisitions.remove(chassis_id)
        except Exception as e:
            self.acquisitionError.emit(chassis_id, f"Error stopping measurement: {str(e)}")

    def stop_all(self):
        """Stop all active measurements and cleanup resources.

        Ensures proper shutdown of:
        - All active acquisitions
        - Worker thread
        - Hardware connections
        """
        if hasattr(self, 'thread') and self.thread.isRunning():
            # Clean up all active measurements
            for chassis_id in list(self.active_acquisitions):
                self.stop_measurement(chassis_id)

            # Ensure thread terminates
            self.thread.quit()
            if not self.thread.wait(5000):  # 5 second timeout
                self.thread.terminate()
                self.thread.wait()
