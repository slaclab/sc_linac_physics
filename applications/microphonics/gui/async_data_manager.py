from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtCore import QThread, pyqtSignal

from applications.microphonics.gui.data_acquisition import DataAcquisitionManager


@dataclass
class MeasurementConfig:
    """Configuration for measurement parameters"""
    channels: List[str]
    buffer_length: int = 16384
    sample_rate: int = 2000
    decimation: int = 1
    buffer_count: int = 65

    def validate(self) -> Optional[str]:
        """Validate configuration parameters"""
        if not self.channels:
            return "No channels specified"
        if self.decimation not in {1, 2, 4, 8}:
            return f"Invalid decimation value: {self.decimation}. Must be 1, 2, 4, or 8"
        if self.buffer_count < 1:
            return f"Invalid buffer count: {self.buffer_count}. Must be positive"
        return None

    def to_acquisition_config(self) -> Dict:
        """Converting to format needed by data acquisition manager"""
        return {
            'decimation': self.decimation,
            'buffer_count': self.buffer_count,
            'channels': self.channels
        }


class AsyncDataManager(QObject):
    """Manages asynch data acquisition across multiple chassis using res_data_acq.py

    So this class provides a high level interface for data acquisition, where it handles:
    - Configuration validation
    - Acquisition management
    - Signal routing from the data acquisition manager
    """
    acquisitionProgress = pyqtSignal(str, int, int)  # chassis_id, cavity_num, progress
    acquisitionError = pyqtSignal(str, str)  # chassis_id, error_message
    acquisitionComplete = pyqtSignal(str)  # chassis_id
    dataReceived = pyqtSignal(str, dict)  # chassis_id, data_dict

    def __init__(self):
        super().__init__()
        self.thread = QThread()
        self.data_manager = DataAcquisitionManager()

        # This connects signals 1st
        self.data_manager.acquisitionComplete.connect(self.acquisitionComplete)
        self.data_manager.acquisitionProgress.connect(self.acquisitionProgress)
        self.data_manager.acquisitionError.connect(self.acquisitionError)
        self.data_manager.dataReceived.connect(self.dataReceived)

        # Then add active acquisitions tracking
        self.active_acquisitions = set()

        # Then move to thread after connecting
        self.data_manager.moveToThread(self.thread)
        self.thread.start()

    def _validate_chassis_config(self, chassis_id: str, config: dict) -> Optional[str]:
        """Validate individual chassis configuration"""
        if not config.get('cavities'):
            return "No cavities specified for chassis"

        # THis checks for CM boundary crossing
        low_cm = any(c <= 4 for c in config['cavities'])
        high_cm = any(c > 4 for c in config['cavities'])
        if low_cm and high_cm:
            return "ERROR: Cavity selection crosses half-CM"

        if not config.get('pv_base'):
            return "Missing PV base address"

        return None

    def _validate_all_configs(self, chassis_config: Dict) -> List[Tuple[str, str]]:
        """Centralized validation for all chassis configs"""
        if not chassis_config:
            return [("", "No chassis configurations provided")]

        errors = []
        for chassis_id, config in chassis_config.items():
            # This validates chassis configurations
            if error := self._validate_chassis_config(chassis_id, config):
                errors.append((chassis_id, error))
                continue

            # This validates measurement configurations
            if error := config['config'].validate():
                errors.append((chassis_id, error))

        return errors

    def initiate_measurement(self, chassis_config: Dict):
        """Called from main thread to start measurement"""
        errors = self._validate_all_configs(chassis_config)
        if errors:
            for chassis_id, error in errors:
                self.acquisitionError.emit(chassis_id, error)
            return

        # Tracking active acquisitions
        for chassis_id in chassis_config.keys():
            self.active_acquisitions.add(chassis_id)

        # All configs are valid, now we start acquisitions
        for chassis_id, config in chassis_config.items():
            QTimer.singleShot(0, lambda cid=chassis_id, cfg=config:
            self.data_manager.start_acquisition(cid, cfg))

    def _handle_measurement(self, chassis_config):
        """Runs in worker thread context"""
        try:
            errors = self._validate_all_configs(chassis_config)
            if errors:
                # In worker thread, raise the first error
                chassis_id, error = errors[0]
                raise ValueError(f"Configuration error for {chassis_id}: {error}")

            for chassis_id, config in chassis_config.items():
                # Replacing the manual dict creation w/ the new method
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
        """Stop measurement for specific chassis"""
        try:
            if chassis_id in self.active_acquisitions:
                self.data_manager.stop_acquisition(chassis_id)
                self.active_acquisitions.remove(chassis_id)
        except Exception as e:
            self.acquisitionError.emit(chassis_id, f"Error stopping measurement: {str(e)}")

    def stop_all(self):
        """Stop all measurements and cleanup thread"""
        if hasattr(self, 'thread') and self.thread.isRunning():
            # This stops all active acquisitions
            for chassis_id in list(self.active_acquisitions):
                self.stop_measurement(chassis_id)

            # Cleaning up thread
            self.thread.quit()
            if not self.thread.wait(5000):
                self.thread.terminate()
                self.thread.wait()
