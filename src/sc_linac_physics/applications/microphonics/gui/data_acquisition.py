import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QTimer

from sc_linac_physics.applications.microphonics.utils.file_parser import (
    FileParserError,
    load_and_process_file,
)

logger = logging.getLogger(__name__)


class DataAcquisitionManager(QObject):
    acquisitionProgress = pyqtSignal(
        str, int, int
    )  # chassis_id, cavity_num, progress
    acquisitionError = pyqtSignal(str, str)  # chassis_id, error_message
    acquisitionComplete = pyqtSignal(str)  # chassis_id
    dataReceived = pyqtSignal(str, dict)  # chassis_id, data_dict

    # Get completion messages from res_data_acq.py stdout
    COMPLETION_MARKERS = [
        "Restoring acquisition settings...",
        "Done",  # This appears after Restoring
    ]
    PROGRESS_REGEX = re.compile(r"Acquired\s+(\d+)\s+/\s+(\d+)\s+buffers")

    def __init__(self):
        super().__init__()
        self.active_processes: Dict[str, Dict] = {}
        self.base_path = Path("/u1/lcls/physics/rf_lcls2/microphonics")
        self.script_path = Path(
            "/usr/local/lcls/package/lcls2_llrf/srf/software/res_ctl/res_data_acq.py"
        )

    def _create_data_directory(self, chassis_id: str) -> Path:
        """Create hierarchical data directory structure.

        Args:
            chassis_id: String like 'ACCL:L1B:0300:RESA'

        Returns:
            Path object pointing to the created directory
        """
        # Parse chassis_id components
        # Example: ACCL:L1B:0300:RESA -> facility=LCLS, linac=L1B, cryomodule=03
        parts = chassis_id.split(":")
        if len(parts) < 4:
            raise ValueError(f"Invalid chassis_id format: {chassis_id}")

        facility = "LCLS"
        linac = parts[1]  # e.g., L1B
        cryomodule = parts[2][:2]  # e.g. 03 from 0300
        date_str = datetime.now().strftime("%Y%m%d")
        data_path = (
            self.base_path / facility / linac / f"CM{cryomodule}" / date_str
        )
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def _prepare_acquisition_environment(self, chassis_id: str, config: Dict):
        if not config.get("cavities"):
            raise ValueError("No cavities specified")
        if not config.get("config"):
            raise ValueError("MeasurementConfig missing in config dict")

        measurement_cfg = config["config"]
        selected_cavities = sorted(config["cavities"])

        cm_num = chassis_id.split(":")[2][:2]
        cavity_str = "".join(map(str, selected_cavities))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"res_CM{cm_num}_cav{cavity_str}_c{measurement_cfg.buffer_count}_{timestamp}.dat"

        data_dir = self._create_data_directory(chassis_id)
        output_path = data_dir / filename

        return output_path, selected_cavities

    def _build_acquisition_args(
        self, config: Dict, output_path: Path, selected_cavities: list
    ) -> list:
        measurement_cfg = config["config"]
        return [
            str(self.script_path),
            "-D",
            str(output_path.parent),
            "-a",
            config["pv_base"],
            "-wsp",
            str(measurement_cfg.decimation),
            "-acav",
            *map(str, selected_cavities),
            "-ch",
            *measurement_cfg.channels,
            "-c",
            str(measurement_cfg.buffer_count),
            "-F",
            output_path.name,
        ]

    def _update_progress_estimate(self, chassis_id: str):
        """Update progress estimate based on elapsed time"""
        if chassis_id not in self.active_processes:
            return

        process_info = self.active_processes[chassis_id]

        if process_info.get("actual_progress_received", False):
            timer = process_info.get("progress_timer")
            if timer and timer.isActive():
                timer.stop()
            return

        current_time = time.time()
        elapsed = current_time - process_info["start_time"]
        expected_duration = process_info["expected_duration"]

        estimated_progress = min(int((elapsed / expected_duration) * 100), 90)

        if estimated_progress > process_info["last_progress"]:
            process_info["last_progress"] = estimated_progress
            for cavity_num in process_info["cavities"]:
                self.acquisitionProgress.emit(
                    chassis_id, cavity_num, estimated_progress
                )

    def start_acquisition(self, chassis_id: str, config: Dict):
        """Start acquisition using QProcess"""
        try:
            (
                output_path,
                selected_cavities,
            ) = self._prepare_acquisition_environment(chassis_id, config)
            command_args = self._build_acquisition_args(
                config, output_path, selected_cavities
            )

            process = QProcess()
            process.readyReadStandardOutput.connect(
                lambda: self.handle_stdout(chassis_id, process)
            )
            process.readyReadStandardError.connect(
                lambda: self.handle_stderr(chassis_id, process)
            )
            process.finished.connect(
                lambda code, status: self.handle_finished(
                    chassis_id, process, code, status
                )
            )

            measurement_cfg = config["config"]
            expected_duration = (
                16384
                * measurement_cfg.decimation
                * measurement_cfg.buffer_count
            ) / 2000
            progress_timer = QTimer()
            progress_timer.timeout.connect(
                lambda: self._update_progress_estimate(chassis_id)
            )
            self.active_processes[chassis_id] = {
                "process": process,
                "output_path": output_path,
                "decimation": measurement_cfg.decimation,
                "expected_buffers": measurement_cfg.buffer_count,
                "completion_signal_received": False,
                "last_progress": 0,
                "cavities": selected_cavities,
                "start_time": time.time(),
                "expected_duration": expected_duration,
                "progress_timer": progress_timer,
                "actual_progress_received": False,
            }

            process.start(sys.executable, command_args)

            if not process.waitForStarted(5000):
                error_str = process.errorString()
                progress_timer.stop()
                progress_timer.deleteLater()
                if chassis_id in self.active_processes:
                    del self.active_processes[chassis_id]
                self.acquisitionError.emit(
                    chassis_id, f"Failed to start process: {error_str}"
                )
            else:
                progress_timer.start(2000)

        except Exception as e:
            logger.error(
                f"Failed to start acquisition for {chassis_id}: {e}",
                exc_info=True,
            )
            self.acquisitionError.emit(
                chassis_id, f"Failed to start acquisition: {str(e)}"
            )

    def _check_progress(self, line: str, chassis_id: str, process_info: dict):
        """Check for progress updates in the line"""
        match = self.PROGRESS_REGEX.search(line)
        if not match:
            return

        try:
            acquired = int(match.group(1))
            total = int(match.group(2))

            if total <= 0:
                return
            process_info["actual_progress_received"] = True
            timer = process_info.get("progress_timer")
            if timer and timer.isActive():
                timer.stop()

            progress = int((acquired / total) * 100)

            if progress > process_info["last_progress"]:
                process_info["last_progress"] = progress
                for cavity_num in process_info["cavities"]:
                    self.acquisitionProgress.emit(
                        chassis_id, cavity_num, progress
                    )

                if acquired == total:
                    logger.info(
                        f"Final buffer acquired for {chassis_id} (progress {acquired}/{total}). Completion flag set."
                    )

        except Exception as e_parse:
            logger.warning(
                f"Could not parse progress from line '{line}': {e_parse}"
            )

    def handle_stdout(self, chassis_id: str, process: QProcess):
        """Handle standard output from process"""
        if chassis_id not in self.active_processes:
            return

        process_info = self.active_processes[chassis_id]

        try:
            current_process = process_info["process"]
            if not current_process:
                return

            data = (
                bytes(current_process.readAllStandardOutput())
                .decode(errors="ignore")
                .strip()
            )

            for line in data.splitlines():
                line = line.strip()
                if not line:
                    continue

                self._process_stdout_line(line, chassis_id, process_info)

        except Exception as e:
            logger.error(
                f"Error processing stdout for {chassis_id}: {e}", exc_info=True
            )
            self.acquisitionError.emit(
                chassis_id, f"Internal error processing script output: {str(e)}"
            )

    def _process_stdout_line(
        self, line: str, chassis_id: str, process_info: dict
    ):
        """Process a single line of stdout output"""
        if process_info.get("completion_signal_received"):
            return

        if any(marker in line for marker in self.COMPLETION_MARKERS):
            process_info["completion_signal_received"] = True
            timer = process_info.get("progress_timer")
            if timer and timer.isActive():
                timer.stop()
            if process_info["last_progress"] < 100:
                for cavity_num in process_info["cavities"]:
                    self.acquisitionProgress.emit(chassis_id, cavity_num, 100)
                process_info["last_progress"] = 100
        else:
            self._check_progress(line, chassis_id, process_info)

    def handle_stderr(self, chassis_id: str, process: QProcess):
        """Handle standard error from process"""
        try:
            error = bytes(process.readAllStandardError()).decode().strip()
            if error:
                self.acquisitionError.emit(chassis_id, error)
        except Exception as e:
            logger.error(
                f"Failed to handle stderr for {chassis_id}: {e}", exc_info=True
            )

    def _was_acquisition_successful(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
        process_info: dict,
    ) -> bool:
        if not process_info.get("completion_signal_received"):
            process = process_info.get("process")
            if process:
                stdout_final = (
                    bytes(process.readAllStandardOutput())
                    .decode(errors="ignore")
                    .strip()
                )
                if any(
                    marker in stdout_final for marker in self.COMPLETION_MARKERS
                ):
                    process_info["completion_signal_received"] = True

        return (
            exit_code == 0
            and exit_status == QProcess.NormalExit
            and process_info.get("completion_signal_received", False)
            and process_info.get("output_path")
        )

    def _report_acquisition_failure(
        self,
        chassis_id: str,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
        stderr: str,
        completion_received: bool,
    ):
        details = [f"Acquisition for {chassis_id} failed."]
        if exit_status != QProcess.NormalExit:
            details.append("Process crashed.")
        elif exit_code != 0:
            details.append(f"Exit Code: {exit_code}.")
        if not completion_received:
            details.append("Script did not signal completion.")
        if stderr:
            details.append(f"Error Stream: '{stderr}'")

        full_error_message = " ".join(details)
        logger.error(f"Handling failure for {chassis_id}: {full_error_message}")
        self.acquisitionError.emit(chassis_id, full_error_message)

    def _cleanup_process_resources(self, process_info: dict):
        timer = process_info.get("progress_timer")
        if timer:
            if timer.isActive():
                timer.stop()
            timer.deleteLater()
        process = process_info.get("process")
        if not process:
            return
        for signal in [
            process.readyReadStandardOutput,
            process.readyReadStandardError,
            process.finished,
        ]:
            try:
                signal.disconnect()
            except (TypeError, RuntimeError):
                pass
        QTimer.singleShot(0, process.deleteLater)
        process_info["process"] = None

    def handle_finished(
        self,
        chassis_id: str,
        process: QProcess,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ):
        if chassis_id not in self.active_processes:
            return

        process_info = self.active_processes[chassis_id]
        try:
            timer = process_info.get("progress_timer")
            if timer and timer.isActive():
                timer.stop()
            if self._was_acquisition_successful(
                exit_code, exit_status, process_info
            ):
                output_path = process_info["output_path"]
                QTimer.singleShot(
                    20000,
                    lambda: self._process_output_file_wrapper(
                        chassis_id, output_path, process_info
                    ),
                )
            else:
                stderr_final = (
                    bytes(process.readAllStandardError())
                    .decode(errors="ignore")
                    .strip()
                )
                self._report_acquisition_failure(
                    chassis_id,
                    exit_code,
                    exit_status,
                    stderr_final,
                    process_info["completion_signal_received"],
                )
                if chassis_id in self.active_processes:
                    del self.active_processes[chassis_id]
        except Exception as e:
            logger.critical(
                f"Unexpected error in handle_finished for {chassis_id}: {e}",
                exc_info=True,
            )
            self.acquisitionError.emit(
                chassis_id, f"Unexpected error: {str(e)}"
            )
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]
        finally:
            self._cleanup_process_resources(process_info)

    def _process_output_file_wrapper(
        self, chassis_id: str, output_path: Path, process_info: dict
    ):
        """
        Wrapper to check file, call the central file parser, handle errors,
        and emit signals.
        """
        try:

            try:
                file_stats = output_path.stat()
                file_size = file_stats.st_size
            except FileNotFoundError:
                logger.error(f"File {output_path} not found after wait!")
                self.acquisitionError.emit(
                    chassis_id,
                    f"Output file {output_path.name} missing after wait.",
                )
                return
            if file_size == 0:
                logger.warning(
                    f"File {output_path} exists but is empty. Aborting processing."
                )
                self.acquisitionError.emit(
                    chassis_id, f"Output file {output_path.name} was empty."
                )
                return
            parsed_data_dict = load_and_process_file(output_path)

            if parsed_data_dict and parsed_data_dict.get("cavities"):

                parsed_data_dict["source"] = chassis_id
                parsed_data_dict["decimation"] = process_info.get(
                    "decimation", 1
                )

                self.dataReceived.emit(chassis_id, parsed_data_dict)
                self.acquisitionComplete.emit(chassis_id)

            else:
                logger.error(
                    f"load_and_process_file did not return valid data for {chassis_id} from {output_path.name}."
                )
                self.acquisitionError.emit(
                    chassis_id,
                    f"Failed to parse valid data from {output_path.name}",
                )

        except (FileParserError, FileNotFoundError, ValueError) as e:
            logger.error(f"File processing failed for {chassis_id}: {e}")
            self.acquisitionError.emit(
                chassis_id, f"Data processing error: {e}"
            )
        except Exception as e:
            logger.critical(
                f"Unexpected error processing file for {chassis_id}: {e}",
                exc_info=True,
            )
            self.acquisitionError.emit(
                chassis_id,
                f"Unexpected error processing file {output_path.name}: {str(e)}",
            )
        finally:
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]

    def stop_acquisition(self, chassis_id: str):
        """Stop a running acquisition process."""
        process_info = self.active_processes.get(chassis_id)
        if process_info:
            timer = process_info.get("progress_timer")
            if timer and timer.isActive():
                timer.stop()
            process = process_info.get("process")
            if process and process.state() != QProcess.NotRunning:
                process.terminate()
                if not process.waitForFinished(2000):
                    process.kill()
                    process.waitForFinished(1000)

        if chassis_id in self.active_processes:
            del self.active_processes[chassis_id]

    def stop_all(self):
        """Stop all acquisitions"""
        for chassis_id in list(self.active_processes.keys()):
            self.stop_acquisition(chassis_id)
