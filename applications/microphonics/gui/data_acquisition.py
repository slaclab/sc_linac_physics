import io
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

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
            # Basic validation first
            if not config.get('cavities'):
                raise ValueError("No cavities specified")

            # Check CM boundary crossing
            low_cm = any(c <= 4 for c in config['cavities'])
            high_cm = any(c > 4 for c in config['cavities'])
            if low_cm and high_cm:
                raise ValueError("ERROR: Cavity selection crosses half-CM")

            # Extract the nested MeasurementConfig object
            measurement_cfg = config['config']  # Get the MeasurementConfig object

            process = QProcess()

            # Filename and Directory Logic
            # Extract CM number from chassis_id
            try:
                cm_num = chassis_id.split(':')[2][:2]
            except IndexError:
                raise ValueError(f"Could not parse CM number from chassis_id: {chassis_id}")
            # Format cavity numbers for filename (using the cavities from the outer config)
            cavity_str = '_'.join(map(str, sorted(config['cavities'])))
            # Generate filename w/ timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"res_CM{cm_num}_cav{cavity_str}_{timestamp}.dat"
            # Create directory structure and get full path
            data_dir = self._create_data_directory(chassis_id)

            # Arguement construction
            args = [
                '-D', str(data_dir),
                '-a', config['pv_base'],
                '-wsp', str(measurement_cfg.decimation),
                '-acav', *map(str, config['cavities']),
                '-ch', *measurement_cfg.channels,
                '-c', str(measurement_cfg.buffer_count),
                '-F', filename
            ]

            python_executable = sys.executable
            full_command_args = [str(self.script_path)] + args

            print(f"Starting QProcess for {chassis_id}")
            print(f"Interpreter {python_executable}")
            print(f"Script Path: {self.script_path}")
            print(f"Script Args: {args}")
            print(f"Full Command to Execute: {[python_executable] + full_command_args}")
            print(f"Argument Types for Python: {[type(a) for a in full_command_args]}")

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
            process.start(python_executable, full_command_args)

            # Check for immediate start failure
            if not process.waitForStarted(3000):  # Wait up to 3 sec
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
                    process_info['completion_signal_received'] = True

                # Check for progress
                match = self.PROGRESS_REGEX.search(line)
                if match:
                    try:
                        acquired = int(match.group(1))
                        total = int(match.group(2))
                        # Validation and progress calculation
                        progress = int((acquired / total) * 100) if total > 0 else 0
                        process_info['last_progress'] = progress
                        cavity_num = process_info['cavity_num_for_progress']
                        self.acquisitionProgress.emit(chassis_id, cavity_num, progress)
                        print(f"Progress ({chassis_id}, Cav {cavity_num}): {progress}% ({acquired}/{total})")

                        # Backup completion check
                        if acquired == total:
                            print(f"INFO: Final buffer acquired message detected for {chassis_id}.")
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

    def handle_finished(self, chassis_id: str, exit_code: int, exit_status: QProcess.ExitStatus):
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
            try:
                if process.state() != QProcess.NotRunning:
                    pass
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

                QTimer.singleShot(10000, lambda p=output_path, pi=process_info:
                self._process_output_file_wrapper(chassis_id, p, pi))  # Calls wrapper directly

            # Failure Conditions
            else:
                error_details = []
                error_msg = f"Acquisition process for {chassis_id} failed or did not signal completion."
                error_details.append(error_msg)
                if exit_status != QProcess.NormalExit: error_msg += f" Status: {status_str}."
                if exit_code != 0: error_msg += f" Exit Code: {exit_code}."
                if not process_info['completion_signal_received']:  # Specific check
                    error_msg += " Script did not signal completion via expected stdout message."
                    print(
                        f"ERROR ({chassis_id}): Process finished normally but completion signal was not received.")
                    if exit_code == 0 and exit_status == QProcess.NormalExit:
                        print(
                            f"WARN ({chassis_id}): Process finished normally but completion signal was not received.")

                # Append stderr/stdout details if there
                if stderr_final:
                    error_details.append(f"\nScript Error: {stderr_final}")
                elif stdout_final and not completion_received:
                    error_details.append(f"\nFinal Script Output (max 200 chars): {stdout_final[:200]}...")
                full_error_msg = " ".join(error_details)
                print(f"ERROR_MSG_EMIT ({chassis_id}): {full_error_msg}")  # Log full error
                self.acquisitionError.emit(chassis_id, full_error_msg)

        except Exception as e:
            print(f"CRITICAL: Error within handle_finished for {chassis_id}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Internal error handling process finish: {str(e)}")
        finally:
            if process:
                try:
                    process.readyReadStandardOutput.disconnect()
                    process.readyReadStandardError.disconnect()
                    process.finished.disconnect()
                except TypeError:
                    pass  # Already disconnected
                except Exception as e_disconnect:
                    print(f"Warning: Error disconnecting signals for {chassis_id}: {e_disconnect}")
                QTimer.singleShot(0, process.deleteLater)

    def _process_output_file_wrapper(self, chassis_id: str, output_path: Path, process_info: dict):
        """Wrapper to catch exceptions during file processing."""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{current_time}] DEBUG: Attempting to process file: {output_path}")

            if not output_path.exists():
                print(f"ERROR: File {output_path} not found even after script completion signal!")
                self.acquisitionError.emit(chassis_id,
                                           f"Output file {output_path.name} missing despite script success.")
                return

            file_size = output_path.stat().st_size
            print(f"DEBUG: File exists. Size before reading: {file_size} bytes")
            if file_size == 0:
                print(f"WARN: File {output_path} exists but is empty. Skipping processing.")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} was empty.")
                return

            # Call the processing function
            self._process_output_file(chassis_id, output_path, process_info)

            # Emit completion signal only if processing works
            self.acquisitionComplete.emit(chassis_id)
            current_time_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{current_time_end}] DEBUG: Successfully processed file: {output_path}")

        except FileNotFoundError as e:
            self.acquisitionError.emit(chassis_id, f"Output file missing or unreadable: {output_path.name}")
        except (ValueError, IndexError) as e:  # Catch parsing/indexing errors specifically
            self.acquisitionError.emit(chassis_id, f"Data parsing/indexing error in {output_path.name}: {e}")
        except Exception as e:
            self.acquisitionError.emit(chassis_id, f"Unexpected error processing file {output_path.name}: {str(e)}")

    def _process_output_file(self, chassis_id: str, output_path: Path, process_info: dict):
        """Reads and parses the completed data file. (Error handling moved to wrapper)"""
        print(f"Reading data file: {output_path}")
        header_lines, data = self._read_data_file(output_path)

        channels = self._parse_channels(header_lines)

        if data.size == 0:
            print(f"Warning: Data array loaded from {output_path} is empty (size 0).")

        # Check channel/column mismatch only if data exists
        if data.size > 0 and len(channels) != data.shape[1]:
            raise ValueError(
                f"Mismatch between channels in header ({len(channels)}) "
                f"and data columns ({data.shape[1]}) in {output_path}"
            )
        parsed_data = {}
        if data.size > 0:
            if data.ndim == 1:
                if len(channels) == 1:
                    data = data.reshape(-1, 1)
                else:
                    raise ValueError("Internal logic error: 1D data shape inconsistent with multiple channels.")

            for idx, channel in enumerate(channels):
                parsed_data[channel] = data[:, idx]
        else:
            for channel in channels:
                parsed_data[channel] = np.array([])
        cavity_num = 0
        try:
            match = re.search(r'_cav(\d+)', output_path.stem)
            if match:
                cavity_num = int(match.group(1))
            else:
                # Fallback splitting
                parts = output_path.stem.split('_')
                cav_part = next((p for p in parts if p.startswith('cav')), None)
                if cav_part:
                    cav_num_str = cav_part.replace('cav', '').split('_')[0]
                    cavity_num = int(cav_num_str)
                else:
                    print(
                        f"Warning: Could not parse cavity number reliably from filename {output_path.name}. Using default 0.")
        except (IndexError, ValueError, TypeError) as e:
            print(f"Warning: Error parsing cavity number from filename {output_path.name}: {e}. Using default 0.")

        decimation = process_info.get('decimation', 1)

        print(f"Emitting dataReceived for {chassis_id}, Cavity {cavity_num}")
        self.dataReceived.emit(chassis_id, {
            'cavity': cavity_num,
            'channels': parsed_data,
            'decimation': decimation,
            'filepath': str(output_path)
        })

    def stop_acquisition(self, chassis_id: str):
        """Stop a running acquisition"""
        if chassis_id in self.active_processes:
            process_info = self.active_processes[chassis_id]
            process = process_info['process']
            process.terminate()
            # Force kill after timeout if not terminated
            QTimer.singleShot(2000, process.kill)

    def stop_all(self):
        """Stop all acquisitions"""
        for chassis_id in list(self.active_processes.keys()):
            self.stop_acquisition(chassis_id)

    def _read_data_file(self, file_path: Path) -> Tuple[List[str], np.ndarray]:
        """Read data file generated by res_data_acq.py, parsing numerical data."""
        
        print(f"\n!!! DEBUG: _read_data_file called for {file_path}")
        print("!!! DEBUG: Call stack:")
        traceback.print_stack()
        print("!!! DEBUG: --- End Call Stack ---\n")
        header_lines = []
        data_lines = []
        channel_header_found = False  # Flag to track if we found the specific header

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read Header Part
                line = f.readline()
                while line:  # Read until end of file
                    stripped_line = line.strip()

                    # Check for the specific channel header marker
                    if stripped_line.startswith('# ACCL:'):
                        header_lines.append(line)  # Keep the channel header line
                        channel_header_found = True
                        # Continue reading the rest of the file for data/comments
                        line = f.readline()
                        continue  # Move to next line

                    # If we haven't found the channel header yet treat lines as header
                    if not channel_header_found:
                        header_lines.append(line)
                    # If we have found the channel header check if line is data or comment
                    else:
                        if stripped_line and not stripped_line.startswith('#'):
                            data_lines.append(line)  # It's a data line
                        elif stripped_line.startswith('#'):
                            header_lines.append(line)  # It's a comment after channel header

                    # Read next line for the loop
                    line = f.readline()

            # File reading done

            # Check if the imp channel header was ever found
            if not channel_header_found:
                print(f"ERROR: Essential channel header line ('# ACCL:') not found in {file_path}")
                raise ValueError(f"Channel header line ('# ACCL:') not found in {file_path}")

            # Case where channel header was found but no data lines followed
            if not data_lines:
                print(f"Warning: No data lines found in file {file_path} after header.")
                num_channels = 0  # Default
                try:
                    # Still parse the header to get the expected column count
                    num_channels = len(self._parse_channels(header_lines))
                except Exception as parse_err:
                    print(f"Warning: Could not parse channels from header to get empty array shape: {parse_err}")
                # Return empty 2D array w/ correct # of columns
                return header_lines, np.empty((0, num_channels if num_channels > 0 else 0))

            # If data lines exist, attempt to load them
            data_io = io.StringIO("".join(data_lines))
            # Use ndmin=2 to ensure 2D output
            data = np.loadtxt(data_io, comments='#', ndmin=2)

            # Check for empty data AFTER loadtxt
            if data.size == 0:
                print(f"Warning: np.loadtxt resulted in an empty array (shape {data.shape}) for {file_path}.")
                return header_lines, data  # Return the empty 2D array

            print(f"Successfully parsed data shape {data.shape} from {file_path}")
            return header_lines, data

        # Exception Handlers
        except FileNotFoundError:
            print(f"Error: Data file not found during read: {file_path}")
            raise
        except ValueError as e:  # Catches header parsing (# ACCL: not found) or loadtxt errors
            print(f"Error parsing data in {file_path}: {e}")
            if data_lines:  # Only print data lines if loadtxt prob failed
                print("--- Problematic Data Lines (first 5) ---")
                for i, line in enumerate(data_lines):
                    if i < 5:
                        print(line.strip())
                    else:
                        break
                print("-----------------------------------------")
            raise ValueError(f"Failed to parse data from {file_path}: {e}") from e
        except Exception as e:  # Catch any other unexpected errors
            print(f"Unexpected error reading/parsing data file {file_path}: {e}")
            traceback.print_exc()
            raise

    # Make sure _parse_channels also only looks for # ACCL:
    def _parse_channels(self, header_lines: List[str]) -> List[str]:
        """Parse channel names (full PVs) from res_data_acq.py file header."""
        # Look for the line starting with # ACCL:
        for line in reversed(header_lines):  # Check recent lines first
            line_strip = line.strip()
            if line_strip.startswith('# ACCL:'):
                # Remove # strip whitespace split by space
                parsed_channels = line_strip.strip('# \n').split()
                print(f"Parsed channels from header ('# ACCL:'): {parsed_channels}")
                return parsed_channels
        # If the specific line is not found, raise an error
        raise ValueError("Channel header line ('# ACCL:') not found in provided header lines.")
