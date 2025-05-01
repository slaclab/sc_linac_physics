import io
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QTimer


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
    # Regex to capture progress (more robust)
    PROGRESS_REGEX = re.compile(r"Acquired\s+(\d+)\s+/\s+(\d+)\s+buffers")
    PV_CAVITY_REGEX = re.compile(r"ACCL:L\dB:(\d{2})(\d)0:")
    PV_CHANNEL_REGEX = re.compile(r":PZT:([A-Z]+):WF")

    def __init__(self):
        super().__init__()
        self.active_processes: Dict[str, Dict] = {}
        self.base_path = Path("/u1/lcls/physics/rf_lcls2/microphonics")
        self.script_path = Path("/usr/local/lcls/package/lcls2_llrf/srf/software/res_ctl/res_data_acq.py")
        if not self.script_path.is_file():
            # Add check early
            print(f"Error: Acquisition script not found at {self.script_path}")

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
        # Checking if there is 4 parts after spliting
        if len(parts) < 4:
            raise ValueError(f"Invalid chassis_id format: {chassis_id}")

        facility = "LCLS"
        linac = parts[1]  # e.g., L1B
        cryomodule = parts[2][:2]  # e.g. 03 from 0300
        # Create date string
        date_str = datetime.now().strftime("%Y%m%d")
        # Construct the full path
        data_path = self.base_path / facility / linac / f"CM{cryomodule}" / date_str
        # Create directory structure if it doesn't exist
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    def start_acquisition(self, chassis_id: str, config: Dict):
        """Start acquisition using QProcess"""
        try:
            print(f"DEBUG: >>> Entered start_acquisition for {chassis_id}")
            if not config.get('cavities'):
                raise ValueError("No cavities specified")
            if not config.get('config'):
                raise ValueError("MeasurementConfig missing in config dict")

            measurement_cfg = config['config']  # MeasurementConfig object
            selected_cavities = sorted(config['cavities'])

            # Check CM boundary crossing
            low_cm = any(c <= 4 for c in config['cavities'])
            high_cm = any(c > 4 for c in config['cavities'])
            if low_cm and high_cm:
                raise ValueError("ERROR: Cavity selection crosses half-CM")

            process = QProcess()

            # Filename and Directory Logic
            # Extract CM number from chassis_id
            try:
                cm_num = chassis_id.split(':')[2][:2]
            except IndexError:
                raise ValueError(f"Could not parse CM number from chassis_id: {chassis_id}")
            # Format cavity numbers for filename
            cavity_str_for_filename = ''.join(map(str, selected_cavities))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cm_part = f"CM{cm_num}"
            cav_part = f"cav{cavity_str_for_filename}"
            # Include buffer count in filename
            buffer_part = f"c{measurement_cfg.buffer_count}"
            # Filename format
            filename = f"res_{cm_part}_{cav_part}_{buffer_part}_{timestamp}.dat"

            data_dir = self._create_data_directory(chassis_id)
            output_path = data_dir / filename
            print(f"DEBUG: Output file path set to: {output_path}")

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

            print(f"Starting QProcess for {chassis_id}")
            print(f"Full Command to Execute: {[python_executable] + full_command_args}")

            # Connect signals
            process.readyReadStandardOutput.connect(
                lambda: self.handle_stdout(chassis_id, process))
            process.readyReadStandardError.connect(
                lambda: self.handle_stderr(chassis_id, process))
            process.finished.connect(
                lambda exit_code, exit_status: self.handle_finished(chassis_id, process, exit_code, exit_status))

            # Store process info
            output_path = data_dir / filename
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
            print(f"DEBUG: About to start QProcess for {chassis_id}")
            process.start(python_executable, full_command_args)

            # Check for immediate start failure
            if not process.waitForStarted(5000):  # Wait up to 5 sec
                error_str = process.errorString()
                print(f"ERROR: Failed to start QProcess for {chassis_id}. QProcess Error: {error_str}")
                # Clean up immediately if start fails
                if chassis_id in self.active_processes:
                    del self.active_processes[chassis_id]
                # Emit error
                self.acquisitionError.emit(chassis_id, f"Failed to start acquisition process: {error_str}")
                return  # Stop further processing

            print(f"QProcess for {chassis_id} started successfully (PID: {process.processId()}).")

        except Exception as e:
            print(f"Error during start_acquisition for {chassis_id}: {e}")
            import traceback
            traceback.print_exc()  # Print full traceback for debugging
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
                print(f"STDOUT Line ({chassis_id}): {line}")  # Log each line
                # Check for completion markers first
                if any(marker in line for marker in self.COMPLETION_MARKERS):
                    print(f"INFO: Completion marker '{line}' detected for {chassis_id}.")
                    if not process_info['completion_signal_received']:
                        process_info['completion_signal_received'] = True
                        if process_info['last_progress'] < 100:
                            cavity_num = process_info['cavity_num_for_progress']
                            self.acquisitionProgress.emit(chassis_id, cavity_num, 100)
                            process_info['last_progress'] = 100
                            print(f"Progress ({chassis_id}, Cav {cavity_num}): 100% (Completion marker seen)")
                # Check for progress
                if not process_info['completion_signal_received']:
                    match = self.PROGRESS_REGEX.search(line)
                    if match:
                        try:
                            acquired = int(match.group(1))
                            total = int(match.group(2))
                            if total > 0:
                                progress = int((acquired / total) * 100)
                                if progress >= process_info['last_progress'] and progress <= 100:
                                    process_info['last_progress'] = progress
                                    cavity_num = process_info['cavity_num_for_progress']
                                    self.acquisitionProgress.emit(chassis_id, cavity_num, progress)
                                    print(
                                        f"Progress ({chassis_id}, Cav {cavity_num}): {progress}% ({acquired}/{total})")
                                    if acquired == total:
                                        print(
                                            f"INFO: Final buffer acquired message detected for {chassis_id} (progress {acquired}/{total}). Setting completion flag.")
                                        process_info['completion_signal_received'] = True

                        except ValueError:
                            print(f"WARN ({chassis_id}): Could not parse progress numbers from line: {line}")
                        except Exception as e_parse:
                            print(f"ERROR processing progress line for {chassis_id}: {e_parse}")

        except Exception as e:
            print(f"CRITICAL ERROR processing stdout for {chassis_id}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Internal error processing script output: {str(e)}")

    def handle_stderr(self, chassis_id: str, process: QProcess):
        """Handle standard error from process"""
        try:
            error = bytes(process.readAllStandardError()).decode().strip()
            if error:
                print(f"!!! STDERR ({chassis_id}): {error}")  # Debug log
                self.acquisitionError.emit(chassis_id, error)
        except Exception as e:
            print(f"Error processing stderr for {chassis_id}: {e}")

    def handle_finished(self, chassis_id: str, process: QProcess, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion checking for completion signal."""
        print(f"DEBUG: handle_finished entered for {chassis_id}. Exit code: {exit_code}, Status: {exit_status}")

        if chassis_id not in self.active_processes:
            print(f"WARN: handle_finished called for {chassis_id}, but it's not in active_processes.")
            return

        process_info = self.active_processes.pop(chassis_id)
        process = process_info.get('process')

        try:
            status_str = "NormalExit" if exit_status == QProcess.NormalExit else "CrashExit"
            print(f"Process finished for {chassis_id}. Exit code: {exit_code}, Status: {status_str}")
            completion_received = process_info.get('completion_signal_received', False)
            output_path = process_info.get('output_path')

            # Read remaining output/error streams
            stderr_final = ""
            stdout_final = ""
            if process.state() != QProcess.NotRunning:
                try:
                    process.waitForReadyRead(100)
                    stderr_final = bytes(process.readAllStandardError()).decode(errors='ignore').strip()
                    stdout_final = bytes(process.readAllStandardOutput()).decode(errors='ignore').strip()
                    if stderr_final: print(f" Final STDERR ({chassis_id}): {stderr_final}")
                    if stdout_final:
                        print(f" Final STDOUT ({chassis_id}): {stdout_final}")
                        # Last check for completion markers
                        if not completion_received:
                            for line in stdout_final.splitlines():
                                if any(marker in line for marker in self.COMPLETION_MARKERS):
                                    print(f"INFO: Completion marker found in final stdout for {chassis_id}.")
                                    process_info['completion_signal_received'] = True
                                    completion_received = True
                                    break
                except Exception as e_read:
                    print(f"Error reading final stderr/stdout for {chassis_id}: {e_read}")

            # Worked Condition: Check exit code, status, and completion signal
            if exit_code == 0 and exit_status == QProcess.NormalExit and completion_received and output_path:
                print(f"Acquisition process for {chassis_id} completed successfully AND signaled completion.")
                print(f"DIAGNOSTIC: Starting deliberate delay before reading {output_path}...")

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
                    if exit_code == 0 and exit_status == QProcess.NormalExit:
                        print(f"WARN ({chassis_id}): Process finished normally but completion signal was missing.")
                    else:
                        print(f"ERROR ({chassis_id}): Process finished abnormally and completion signal was missing.")

        except Exception as e:
            print(f"CRITICAL: Error within handle_finished for {chassis_id}: {e}")
            traceback.print_exc()
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
                print(f"DEBUG: Scheduled QProcess for {chassis_id} for deletion.")
                if 'process' in process_info: process_info['process'] = None

    def _process_output_file_wrapper(self, chassis_id: str, output_path: Path, process_info: dict):
        """Wrapper to catch exceptions during file processing and emit completion."""
        print(f"DEBUG: _process_output_file_wrapper entered for {chassis_id}")
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{current_time}] Attempting to process file: {output_path}")

            # Check file existence and size before processing
            if not output_path.exists():
                print(f"ERROR: File {output_path} not found after wait!")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} missing after wait.")
                return

            file_size = output_path.stat().st_size
            print(f"DEBUG: File exists. Size: {file_size} bytes")
            if file_size == 0:
                print(f"WARN: File {output_path} exists but is empty. Aborting processing.")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} was empty.")
                return

            # Call the core processing function
            print(f"DEBUG: Calling _process_output_file for {chassis_id}")
            parsed_data_dict = self._process_output_file(chassis_id, output_path, process_info)

            # Emit Signals only on completion
            if parsed_data_dict:
                print(f"DEBUG: Emitting dataReceived for {chassis_id}")
                self.dataReceived.emit(chassis_id, parsed_data_dict)

                # Emit overall completion after data is successfully processed and emitted
                print(f"DEBUG: Emitting acquisitionComplete for {chassis_id}")
                self.acquisitionComplete.emit(chassis_id)

                current_time_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{current_time_end}] Successfully processed and emitted data for: {output_path}")
            else:
                # Error should have been emitted within _process_output_file or _read_data_file
                print(
                    f"ERROR: _process_output_file did not return valid data for {chassis_id}. Completion not signaled.")

        except FileNotFoundError:
            print(f"ERROR: File not found during processing wrapper for {chassis_id}: {output_path}")
            self.acquisitionError.emit(chassis_id, f"Output file missing or unreadable: {output_path.name}")
        except (ValueError, IndexError) as e:
            print(f"ERROR: Data parsing/indexing error in wrapper for {chassis_id}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Data parsing error in {output_path.name}: {e}")
        except Exception as e:
            print(f"CRITICAL: Unexpected error processing file in wrapper for {chassis_id}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Unexpected error processing file {output_path.name}: {str(e)}")

    def _extract_cavity_channel_from_pv(self, pv_string: str) -> Optional[Tuple[int, str]]:
        """
        Extracts cavity number and channel type from PV string: ACCL:L<X>B:<CM><CAV>0:PZT:<TYPE>:WF
        """
        try:
            parts = pv_string.split(':')
            # Check structure: ACCL:LXB:CMCAV0:PZT:TYPE:WF
            if len(parts) >= 6 and parts[3] == 'PZT' and parts[5] == 'WF':
                segment3 = parts[2]  # e.g., '0250'
                if len(segment3) == 4 and segment3.endswith('0'):
                    # Cavity number is the 3rd character (index 2)
                    cav_num = int(segment3[2])
                    # Channel type is the 5th segment (index 4)
                    channel_type = parts[4]
                    return cav_num, channel_type
                else:
                    # Log warning if format of segment 3 is unexpected
                    print(f"WARN: PV segment '{segment3}' in '{pv_string}' doesn't match <CM><CAV>0 format.")
                    return None
            else:
                # Log warning if overall structure is wrong
                # print(f"WARN: PV string '{pv_string}' doesn't match expected format.") # Optional: reduce verbosity
                return None
        except (IndexError, ValueError) as e:
            # Log warning if indexing or int conversion fails
            print(f"WARN: Could not parse cavity/channel from PV '{pv_string}': {e}")
            return None

    def _process_output_file(self, chassis_id: str, output_path: Path, process_info: dict) -> Optional[Dict[str, Any]]:
        """
        Reads data file, parses header/data using PV names, structures output by cavity.
        Returns the structured data dictionary or none on failure.
        """
        print(f"DEBUG: _process_output_file entered for {chassis_id}, File: {output_path}")
        try:
            # Read header and data
            header_lines, data_array = self._read_data_file(output_path)
            if header_lines is None or data_array is None:
                # Error already logged
                self.acquisitionError.emit(chassis_id, f"Failed to read/parse data file: {output_path.name}")
                return None

            # Parse full PV channel names
            channel_pvs = self._parse_channels(header_lines)
            if not channel_pvs:
                # Error already logged
                self.acquisitionError.emit(chassis_id, f"Channel PVs not found in header: {output_path.name}")
                return None

            print(f"DEBUG: Found {len(channel_pvs)} channel PVs in header: {channel_pvs}")
            print(f"DEBUG: Data array shape: {data_array.shape}")

            # Prepare output structure
            output_data: Dict[str, Any] = {
                'cavities': {},
                'cavity_list': [],
                'decimation': process_info.get('decimation', 1),
                'filepath': str(output_path)
            }
            cavity_numbers_found = set()

            # Check for column mismatch
            expected_cols = len(channel_pvs)
            actual_cols = data_array.shape[1] if data_array.ndim == 2 else 0

            if data_array.size > 0 and actual_cols != expected_cols:
                print(
                    f"ERROR: Column mismatch in {output_path.name}! Header={expected_cols}, Data={actual_cols}. Assigning empty data.")
                data_array = np.empty((0, expected_cols), dtype=float)

            # Populate output structure by parsing PVs and assigning data columns
            for idx, pv_name in enumerate(channel_pvs):
                parsed_info = self._extract_cavity_channel_from_pv(pv_name)
                if parsed_info:
                    cav_num, channel_type = parsed_info
                    cavity_numbers_found.add(cav_num)

                    if cav_num not in output_data['cavities']:
                        output_data['cavities'][cav_num] = {}

                    # Assign data column if data exists and dimensions match
                    if data_array.ndim == 2 and idx < actual_cols and data_array.shape[0] > 0:
                        column_data = data_array[:, idx]
                        output_data['cavities'][cav_num][channel_type] = column_data
                    else:
                        # Assign empty array if no data rows, column mismatch, or parsing failed
                        output_data['cavities'][cav_num][channel_type] = np.array([], dtype=float)
                else:
                    # Case where PV parsing failed for this specific header entry
                    print(f"WARN: Skipping data column {idx} due to PV parsing failure: {pv_name}")

            output_data['cavity_list'] = sorted(list(cavity_numbers_found))
            print(
                f"DEBUG: Final processed data structure for {chassis_id}: Cavities found: {output_data['cavity_list']}")

            return output_data

        except ValueError as e:
            print(f"ERROR: ValueError processing file {output_path.name}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Data processing error in {output_path.name}: {e}")
            return None
        except IndexError as e:
            print(f"ERROR: IndexError processing file {output_path.name}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Data indexing error in {output_path.name}: {e}")
            return None
        except Exception as e:
            print(f"CRITICAL: Unexpected error in _process_output_file for {chassis_id}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Unexpected error processing file {output_path.name}: {str(e)}")
            return None

    def stop_acquisition(self, chassis_id: str):
        """Stop a running acquisition process."""
        print(f"Attempting to stop acquisition for {chassis_id}...")
        process_info = self.active_processes.get(chassis_id)
        if process_info:
            process = process_info.get('process')
            if process and process.state() != QProcess.NotRunning:
                print(f"Terminating process for {chassis_id} (PID: {process.processId()})...")
                process.terminate()
                if not process.waitForFinished(2000):
                    print(f"Process {chassis_id} did not terminate gracefully, killing...")
                    process.kill()
                    process.waitForFinished(1000)
            else:
                print(f"Process for {chassis_id} already stopped or not found in info dict.")

            # Remove from active list after attempting stop
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]
                print(f"Removed {chassis_id} from active processes list during stop.")
        else:
            print(f"No active acquisition found for {chassis_id} to stop.")

    def stop_all(self):
        """Stop all acquisitions"""
        for chassis_id in list(self.active_processes.keys()):
            self.stop_acquisition(chassis_id)

    def _read_data_file(self, file_path: Path) -> Tuple[Optional[List[str]], Optional[np.ndarray]]:
        """
        Reads data file, separates header/data based on '# ACCL:' line.
        Returns (header_lines, data_array).
        """
        print(f"DEBUG: _read_data_file attempting to read: {file_path}")
        header_lines: List[str] = []
        data_content_lines: List[str] = []
        channel_header_line_index: Optional[int] = None

        try:
            with file_path.open('r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()

            # Find the crucial channel header line ('# ACCL:')
            for i, line in enumerate(all_lines):
                if line.strip().startswith('# ACCL:'):
                    channel_header_line_index = i
                    break

            if channel_header_line_index is None:
                print(f"ERROR: Essential channel header line ('# ACCL:') not found in {file_path}")
                return None, None

            header_lines = all_lines[:channel_header_line_index + 1]

            for line in all_lines[channel_header_line_index + 1:]:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    data_content_lines.append(line)

            # Process data lines
            if not data_content_lines:
                print(f"Warning: No numerical data lines found after header in {file_path}.")
                num_channels = 0
                try:  # Try to get column count from header even if data is empty
                    channels = self._parse_channels(header_lines)
                    num_channels = len(channels) if channels else 0
                except ValueError:
                    print(f"Warning: Could not parse channels from header of empty data file {file_path}")
                # Return empty 2D array with right number of columns
                return header_lines, np.empty((0, num_channels), dtype=float)

            # Use StringIO for np.loadtxt
            data_io = io.StringIO("".join(data_content_lines))
            # Use ndmin=2 for 2D output specify float type
            data_array = np.loadtxt(data_io, comments='#', ndmin=2, dtype=float)

            # Check if loadtxt failed despite having lines
            if data_array.size == 0 and len(data_content_lines) > 0:
                print(f"ERROR: np.loadtxt failed to parse data content in {file_path}.")
                return header_lines, None

            print(
                f"DEBUG: Successfully read header ({len(header_lines)} lines) and data (shape {data_array.shape}) from {file_path}")
            return header_lines, data_array

        except FileNotFoundError:
            print(f"ERROR: Data file not found during read: {file_path}")
            return None, None
        except ValueError as e:
            print(f"ERROR: ValueError during file read/parse for {file_path}: {e}")
            return None, None
        except Exception as e:
            print(f"CRITICAL: Unexpected error reading/parsing file {file_path}: {e}")
            traceback.print_exc()
            return None, None

    # Make sure _parse_channels only looks for # ACCL:
    def _parse_channels(self, header_lines: List[str]) -> Optional[List[str]]:
        """
        Parse channel PV names from the specific # ACCL: line in header.
        Returns list of PV names or None if the line is not found/parsable.
        """
        channel_line: Optional[str] = None
        # Look for the line starting with # ACCL:
        for line in reversed(header_lines):  # Check recent lines first
            stripped_line = line.strip()
            if stripped_line.startswith('# ACCL:'):
                channel_line = stripped_line
                break

        if channel_line:
            try:
                # Remove #, strip whitespace, split by space
                parsed_channels = channel_line.strip('# \n').split()
                if not parsed_channels:  # Check if split resulted in empty list
                    print("WARN: Found '# ACCL:' line but no channels listed after it.")
                    return None
                print(f"DEBUG: Parsed channels from header: {parsed_channels}")
                return parsed_channels
            except Exception as e:
                print(f"ERROR: Failed to split/parse the found '# ACCL:' line: {channel_line} - {e}")
                return None
        else:
            # Case indicates the # ACCL: line wasn't in the input header_lines
            print("ERROR: Channel header line ('# ACCL:') not found in provided header lines during channel parsing.")
            return None
