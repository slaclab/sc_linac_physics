import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QTimer

from applications.microphonics.utils.file_parser import FileParserError, load_and_process_file

logger = logging.getLogger(__name__)


class DataAcquisitionManager(QObject):
    acquisitionProgress = pyqtSignal(str, int, int)  # chassis_id, cavity_num, progress
    acquisitionError = pyqtSignal(str, str)  # chassis_id, error_message
    acquisitionComplete = pyqtSignal(str)  # chassis_id
    dataReceived = pyqtSignal(str, dict)  # chassis_id, data_dict

    # Get completion messages from res_data_acq.py stdout
    COMPLETION_MARKERS = [
        "Restoring acquisition settings...",
        "Done"  # This appears after Restoring
    ]
    PROGRESS_REGEX = re.compile(r"Acquired\s+(\d+)\s+/\s+(\d+)\s+buffers")

    def __init__(self):
        super().__init__()
        self.active_processes: Dict[str, Dict] = {}
        self.base_path = Path("/u1/lcls/physics/rf_lcls2/microphonics")
        self.script_path = Path("/usr/local/lcls/package/lcls2_llrf/srf/software/res_ctl/res_data_acq.py")

    def _create_data_directory(self, chassis_id: str) -> Path:
        """Create hierarchical data directory structure.

        Args:
            chassis_id: String like 'ACCL:L1B:0300:RESA'

        Returns:
            Path object pointing to the created directory
        """
        # Parse chassis_id components
        # Example: ACCL:L1B:0300:RESA -> facility=LCLS, linac=L1B, cryomodule=03
        parts = chassis_id.split(':')
        if len(parts) < 4:
            raise ValueError(f"Invalid chassis_id format: {chassis_id}")

        facility = "LCLS"
        linac = parts[1]  # e.g., L1B
        cryomodule = parts[2][:2]  # e.g. 03 from 0300
        date_str = datetime.now().strftime("%Y%m%d")
        data_path = self.base_path / facility / linac / f"CM{cryomodule}" / date_str
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def start_acquisition(self, chassis_id: str, config: Dict):
        """Start acquisition using QProcess"""
        try:
            if not config.get('cavities'):
                raise ValueError("No cavities specified")
            if not config.get('config'):
                raise ValueError("MeasurementConfig missing in config dict")

            measurement_cfg = config['config']  # MeasurementConfig object
            selected_cavities = sorted(config['cavities'])
            process = QProcess(self)

            # Filename and Directory Logic
            # Extract CM number from chassis_id
            try:
                cm_num = chassis_id.split(':')[2][:2]
            except IndexError:
                raise ValueError(f"Could not parse CM number from chassis_id: {chassis_id}")
            cavity_str_for_filename = ''.join(map(str, selected_cavities))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cm_part = f"CM{cm_num}"
            cav_part = f"cav{cavity_str_for_filename}"
            buffer_part = f"c{measurement_cfg.buffer_count}"
            filename = f"res_{cm_part}_{cav_part}_{buffer_part}_{timestamp}.dat"

            data_dir = self._create_data_directory(chassis_id)
            output_path = data_dir / filename

            # Arguement construction
            args = [
                '-D', str(data_dir),
                '-a', config['pv_base'],
                '-wsp', str(measurement_cfg.decimation),
                '-acav', *map(str, selected_cavities),
                '-ch', *measurement_cfg.channels,
                '-c', str(measurement_cfg.buffer_count),
                '-F', filename
            ]

            python_executable = sys.executable
            full_command_args = [str(self.script_path)] + args

            # Connect signals
            process.readyReadStandardOutput.connect(
                lambda: self.handle_stdout(chassis_id, process))
            process.readyReadStandardError.connect(
                lambda: self.handle_stderr(chassis_id, process))
            process.finished.connect(
                lambda exit_code, exit_status: self.handle_finished(chassis_id, process, exit_code, exit_status))

            # Store process info
            self.active_processes[chassis_id] = {
                'process': process,
                'output_path': output_path,
                # Store the actual config used for data parsing later
                'decimation': measurement_cfg.decimation,
                'expected_buffers': measurement_cfg.buffer_count,
                'completion_signal_received': False,  # Flag to track script completion message
                'last_progress': 0,
                'cavity_num_for_progress': config['cavities'][0] if config['cavities'] else 0
                # Use first cavity for progress reporting
            }
            process.start(python_executable, full_command_args)

            # Check for immediate start failure
            if not process.waitForStarted(5000):
                error_str = process.errorString()
                if chassis_id in self.active_processes:
                    del self.active_processes[chassis_id]
                # Emit error
                self.acquisitionError.emit(chassis_id, f"Failed to start acquisition process: {error_str}")
                return  # Stop further processing


        except Exception as e:
            logger.error(f"Failed to start acquisition for {chassis_id}: {e}", exc_info=True)
            self.acquisitionError.emit(chassis_id, f"Failed to start acquisition: {str(e)}")

    def handle_stdout(self, chassis_id: str, process: QProcess):
        """Handle standard output from process"""
        if chassis_id not in self.active_processes:
            return
        process_info = self.active_processes[chassis_id]
        try:
            current_process = process_info['process']
            if not current_process: return
            data = bytes(current_process.readAllStandardOutput()).decode(errors='ignore').strip()
            for line in data.splitlines():
                line = line.strip()
                if not line: continue
                # Check for completion markers first
                if any(marker in line for marker in self.COMPLETION_MARKERS):
                    if not process_info['completion_signal_received']:
                        process_info['completion_signal_received'] = True
                        if process_info['last_progress'] < 100:
                            cavity_num = process_info['cavity_num_for_progress']
                            self.acquisitionProgress.emit(chassis_id, cavity_num, 100)
                            process_info['last_progress'] = 100
                # Check for progress
                if not process_info['completion_signal_received']:
                    match = self.PROGRESS_REGEX.search(line)
                    if match:
                        try:
                            acquired = int(match.group(1))
                            total = int(match.group(2))
                            if total > 0:
                                progress = int((acquired / total) * 100)
                                # Only emit signal if progress has actually gone up
                                if progress > process_info['last_progress']:
                                    process_info['last_progress'] = progress
                                    cavity_num = process_info['cavity_num_for_progress']
                                    self.acquisitionProgress.emit(chassis_id, cavity_num, progress)
                                    logger.debug(
                                        f"Progress ({chassis_id}, Cav {cavity_num}): {progress}% ({acquired}/{total})")
                                    if acquired == total:
                                        logger.info(
                                            f"Final buffer acquired for {chassis_id} (progress {acquired}/{total}). Setting completion flag.")

                        except Exception as e_parse:
                            logger.warning(f"Could not parse progress from line '{line}': {e_parse}")

        except Exception as e:
            logger.error(f"Error processing stdout for {chassis_id}: {e}", exc_info=True)
            self.acquisitionError.emit(chassis_id, f"Internal error processing script output: {str(e)}")

    def handle_stderr(self, chassis_id: str, process: QProcess):
        """Handle standard error from process"""
        try:
            error = bytes(process.readAllStandardError()).decode().strip()
            if error:
                self.acquisitionError.emit(chassis_id, error)
        except Exception as e:
            logger.error(f"Failed to handle stderr for {chassis_id}: {e}", exc_info=True)

    def handle_finished(self, chassis_id: str, process: QProcess, exit_code: int, exit_status: QProcess.ExitStatus):
        """Process completion checking for completion signal."""

        if chassis_id not in self.active_processes:
            return

        process_info = self.active_processes.pop(chassis_id)
        process = process_info.get('process')

        try:
            status_str = "NormalExit" if exit_status == QProcess.NormalExit else "CrashExit"
            completion_received = process_info.get('completion_signal_received', False)
            output_path = process_info.get('output_path')

            # Read remaining output/error streams
            stdout_final = ""
            if process.state() != QProcess.NotRunning:
                try:
                    process.waitForReadyRead(100)
                    stderr_final = bytes(process.readAllStandardError()).decode(errors='ignore').strip()
                    stdout_final = bytes(process.readAllStandardOutput()).decode(errors='ignore').strip()
                    if stdout_final:
                        # Last check for completion markers
                        if not completion_received:
                            for line in stdout_final.splitlines():
                                if any(marker in line for marker in self.COMPLETION_MARKERS):
                                    process_info['completion_signal_received'] = True
                                    completion_received = True
                                    break
                except Exception as e_read:
                    logger.warning(f"Error reading final process output for {chassis_id}: {e_read}")

            # Worked Condition: Check exit code, status, and completion signal
            if exit_code == 0 and exit_status == QProcess.NormalExit and completion_received and output_path:

                # This is temporary I will change this
                QTimer.singleShot(20000, lambda p=output_path, pi=process_info:
                self._process_output_file_wrapper(chassis_id, p, pi))  # Calls wrapper directly

            # Failure Conditions
            else:
                error_details = []
                error_msg = f"Acquisition process for {chassis_id} failed or did not signal completion."
                error_details.append(error_msg)
                if exit_status != QProcess.NormalExit:
                    error_msg += f" Status: {status_str}."
                elif exit_code != 0:
                    error_details.append(f"Exit Code: {exit_code}.")

                if not completion_received:
                    error_details.append("Script did not signal completion via stdout.")
        except Exception as e:
            logger.critical(f"Unexpected error in handle_finished for {chassis_id}: {e}", exc_info=True)
            self.acquisitionError.emit(chassis_id, f"Unexpected error: {str(e)}")

        finally:
            if process:
                try:
                    process.readyReadStandardOutput.disconnect()
                except (TypeError, RuntimeError):
                    pass
                try:
                    process.readyReadStandardError.disconnect()
                except (TypeError, RuntimeError):
                    pass
                try:
                    process.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass
                # Schedule deletion
                QTimer.singleShot(0, process.deleteLater)
                if 'process' in process_info: process_info['process'] = None

    def _process_output_file_wrapper(self, chassis_id: str, output_path: Path, process_info: dict):
        """
        Wrapper to check file, call the central file parser, handle errors,
        and emit signals.
        """
        logging.debug(f"_process_output_file_wrapper entered for {chassis_id}, File: {output_path}")
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            logging.debug(f"[{current_time}] Attempting to process file: {output_path}")

            if not output_path.exists():
                logging.error(f"File {output_path} not found after wait!")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} missing after wait.")
                return

            file_size = output_path.stat().st_size
            logging.debug(f"File exists. Size: {file_size} bytes")
            if file_size == 0:
                logging.warning(f"File {output_path} exists but is empty. Aborting processing.")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} was empty.")
                return
            logging.debug(f"Calling load_and_process_file for {chassis_id}")
            parsed_data_dict = load_and_process_file(output_path)

            if parsed_data_dict and parsed_data_dict.get(
                    'cavities'):
                logging.debug(f"Successfully parsed data for {chassis_id}. Emitting signals.")

                parsed_data_dict['source'] = chassis_id
                parsed_data_dict['decimation'] = process_info.get('decimation', 1)

                self.dataReceived.emit(chassis_id, parsed_data_dict)
                self.acquisitionComplete.emit(chassis_id)

                current_time_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                logging.debug(f"[{current_time_end}] Successfully processed and emitted data for: {output_path}")
            else:

                logging.error(
                    f"load_and_process_file did not return valid data for {chassis_id} from {output_path.name}.")
                self.acquisitionError.emit(chassis_id, f"Failed to parse valid data from {output_path.name}")

        except (FileParserError, FileNotFoundError, ValueError) as e:
            logger.error(f"File processing failed for {chassis_id}: {e}")
            self.acquisitionError.emit(chassis_id, f"Data processing error: {e}")
        except Exception as e:
            logger.critical(f"Unexpected error processing file for {chassis_id}: {e}", exc_info=True)
            self.acquisitionError.emit(chassis_id, f"Unexpected error processing file {output_path.name}: {str(e)}")

    def stop_acquisition(self, chassis_id: str):
        """Stop a running acquisition process."""
        process_info = self.active_processes.get(chassis_id)
        if process_info:
            process = process_info.get('process')
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
