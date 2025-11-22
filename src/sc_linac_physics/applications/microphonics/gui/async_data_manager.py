from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, QThread
from PyQt5.QtCore import pyqtSignal

from sc_linac_physics.applications.microphonics.gui.data_acquisition import (
    DataAcquisitionManager,
)

BASE_HARDWARE_SAMPLE_RATE = 2000


@dataclass
class MeasurementConfig:
    """Configuration for measurement parameters"""

    channels: List[str]
    decimation: int = 2
    buffer_count: int = 1

    def validate(self) -> Optional[str]:
        """Validate configuration parameters"""
        if not self.channels:
            return "No channels specified"
        if self.decimation not in {1, 2, 4, 8}:
            return f"Invalid decimation value: {self.decimation}. Must be 1, 2, 4, or 8"
        if self.buffer_count < 1:
            return f"Invalid buffer count: {self.buffer_count}. Must be greater than 0"
        return None


class AsyncDataManager(QObject):
    """Manages asynch data acquisition across chassis using res_data_acq.py

    Provides an interface for data acquisition, where it handles:
    - Configuration validation
    - Acquisition management
    - Signal routing from the data acquisition manager
    """

    acquisitionProgress = pyqtSignal(
        str, int, int
    )  # chassis_id, cavity_num, progress
    acquisitionError = pyqtSignal(str, str)  # chassis_id, error_message
    acquisitionComplete = pyqtSignal(str)  # chassis_id
    # Job level signals
    jobProgress = pyqtSignal(int)  # overall job progress percentage
    jobError = pyqtSignal(str)  # job level error message
    jobComplete = pyqtSignal(dict)  # aggregated data from all racks

    def __init__(self, parent=None):
        super().__init__(parent)
        # Track workers and their threads
        self.active_workers = {}
        self.worker_progress = {}
        self.worker_data = {}
        self.job_chassis_ids = set()
        self.job_running = False

    def _validate_all_chassis_config(
        self, chassis_config: Dict
    ) -> List[Tuple[str, str]]:
        """Validate for all chassis configuration"""
        if not chassis_config:
            return [("", "No chassis configurations provided")]
        errors = []
        for chassis_id, config in chassis_config.items():
            if not config.get("cavities"):
                errors.append((chassis_id, "No cavities specified for chassis"))
            if not config.get("pv_base"):
                errors.append((chassis_id, "Missing PV base address"))
            if "config" in config and (error := config["config"].validate()):
                errors.append((chassis_id, error))

        return errors

    def initiate_measurement(self, chassis_config: Dict):
        """Called from main thread to start measurement"""
        if self.job_running:
            self.jobError.emit("A measurement job is already running")
            return
        errors = self._validate_all_chassis_config(chassis_config)
        if errors:
            for chassis_id, error in errors:
                self.acquisitionError.emit(chassis_id, error)
            return
        # Initialize job tracking
        self.job_running = True
        self.job_chassis_ids = set(chassis_config.keys())
        self.worker_progress = {
            chassis_id: 0 for chassis_id in self.job_chassis_ids
        }
        self.worker_data.clear()

        # Start parallel acquisitions
        for chassis_id, config in chassis_config.items():
            self._start_worker_for_chassis(chassis_id, config)

    def _start_worker_for_chassis(self, chassis_id: str, config: dict):
        """Create and start a worker thread for one chassis"""

        # Create thread and worker
        thread = QThread()
        worker = DataAcquisitionManager()

        worker.moveToThread(thread)
        # Connect worker signals to our handlers
        worker.acquisitionProgress.connect(self._handle_worker_progress)
        worker.acquisitionError.connect(self._handle_worker_error)
        worker.acquisitionComplete.connect(self._handle_worker_complete)
        worker.dataReceived.connect(self._handle_worker_data)

        # Store worker and thread
        self.active_workers[chassis_id] = (thread, worker)

        # Automatic cleanup
        thread.started.connect(
            lambda: worker.start_acquisition(chassis_id, config)
        )
        worker.acquisitionComplete.connect(thread.quit)
        worker.acquisitionError.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self.active_workers.pop(chassis_id, None)
        )
        # Schedule acquisition start
        thread.start()

    def _handle_worker_progress(
        self, chassis_id: str, cavity_num: int, progress: int
    ):
        """Handle progress from individual worker"""
        # Update worker progress
        self.worker_progress[chassis_id] = progress

        # Forward the progress
        self.acquisitionProgress.emit(chassis_id, cavity_num, progress)

        # Calculate and emit overall job progress
        if self.job_chassis_ids:
            total_progress = sum(self.worker_progress.values()) / len(
                self.job_chassis_ids
            )
            self.jobProgress.emit(int(total_progress))

    def _handle_worker_error(self, chassis_id: str, error: str):
        """Handle error from one worker will stop entire job"""
        print(f"ERROR: Worker {chassis_id} failed: {error}")

        self.job_running = False
        # Forward individual error
        self.acquisitionError.emit(chassis_id, error)

        # Emit job level error
        self.jobError.emit(f"Job failed - {chassis_id}: {error}")

        # Stop all workers for this job
        self._stop_all_workers()

    def _handle_worker_data(self, chassis_id: str, data: dict):
        """Store data from individual worker"""
        self.worker_data[chassis_id] = data

    def _handle_worker_complete(self, chassis_id: str):
        """Handle completion from individual worker"""
        # Forward individual completion
        self.acquisitionComplete.emit(chassis_id)
        if not self.job_running:
            return
        # Check if all workers are done
        if set(self.worker_data.keys()) == self.job_chassis_ids:
            self._complete_job()

    def _complete_job(self):
        """Aggregate data and emit job completion"""
        # Aggregate all cavity data
        aggregated_data = {
            "cavities": {},
            "cavity_list": [],
            "source": "multi-chassis",
            "decimation": None,
        }

        # Combine data from all workers
        for chassis_id, data in self.worker_data.items():
            if "cavities" in data:
                aggregated_data["cavities"].update(data["cavities"])
            if "cavity_list" in data:
                aggregated_data["cavity_list"].extend(data["cavity_list"])
            # Use decimation from first worker
            if aggregated_data["decimation"] is None and "decimation" in data:
                aggregated_data["decimation"] = data["decimation"]

        # Sort cavity list
        aggregated_data["cavity_list"] = sorted(
            set(aggregated_data["cavity_list"])
        )

        # Emit aggregated data
        self.jobComplete.emit(aggregated_data)

        self.job_running = False

    def stop_measurement(self, chassis_id: Optional[str] = None):
        """Stop measurement for specific chassis"""
        if chassis_id:
            self._stop_worker(chassis_id)
        else:
            self.stop_all()

    def stop_all(self):
        """Stop all measurements and cleanup thread"""
        self._stop_all_workers()
        self.job_running = False

    def _stop_all_workers(self):
        """Stop all active workers"""

        for chassis_id in list(self.active_workers.keys()):
            self._stop_worker(chassis_id)

    def _stop_worker(self, chassis_id: str):
        """Stop a specific worker"""
        worker_info = self.active_workers.get(chassis_id)
        if worker_info:
            thread, worker = worker_info

            # Stop acquisition
            worker.stop_acquisition(chassis_id)

            # Clean up thread
            thread.quit()
            if not thread.wait(5000):
                thread.terminate()
                thread.wait()

            # Remove from tracking
            self.active_workers.pop(chassis_id, None)
