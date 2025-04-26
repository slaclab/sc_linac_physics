import io
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
            self.active_processes[chassis_id] = {
                'process': process,
                'output_dir': data_dir,
                'filename': filename,
                # Store the actual config used for data parsing later
                'decimation': measurement_cfg.decimation
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
        try:
            data = bytes(process.readAllStandardOutput()).decode().strip()
            for line in data.split('\n'):
                if "Progress:" in line:
                    parts = line.split()
                    cavity_num = int(parts[2])
                    progress = int(parts[-1].strip('%'))
                    self.acquisitionProgress.emit(chassis_id, cavity_num, progress)
        except Exception as e:
            print(f"Error processing stdout: {e}")

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
        """Handle process completion"""
        process_info = None
        # Get and remove process
        if chassis_id in self.active_processes:
            process_info = self.active_processes.pop(chassis_id)

        try:
            status_str = "NormalExit" if exit_status == QProcess.NormalExit else "CrashExit"
            print(f"Process finished for {chassis_id}. Exit code: {exit_code}, Status: {status_str}")

            if process_info and exit_code == 0 and exit_status == QProcess.NormalExit:
                print(f"Acquisition process for {chassis_id} completed successfully. Processing output file...")
                output_path = process_info['output_dir'] / process_info['filename']
                # Delayed call
                QTimer.singleShot(300, lambda cid=chassis_id, op=output_path, pi=process_info:
                self._delayed_process_output(cid, op, pi))

            elif process_info:
                # When Failure
                error_msg = f"Acquisition process for {chassis_id} exited abnormally. Code: {exit_code}, Status: {status_str}."
                print(error_msg)  # Log the basic error
                stderr_final = ""
                stdout_final = ""

                try:
                    # Making sure reading all remaining output
                    stderr_final = bytes(process.readAllStandardError()).decode(errors='ignore').strip()
                    stdout_final = bytes(process.readAllStandardOutput()).decode(errors='ignore').strip()
                    if stderr_final:
                        print(f" Final STDERR ({chassis_id}): {stderr_final}")
                        error_msg += f"\nDetails: {stderr_final}"
                    if stdout_final:
                        print(f"Final STDOUT ({chassis_id}): {stdout_final}")
                except Exception as e_read:
                    print(f"Error reading final stderr/stdout for {chassis_id}: {e_read}")
                self.acquisitionError.emit(chassis_id, error_msg)
                print(f"Emitted error for abnormal exit: {chassis_id}")
            else:
                # Process finished
                print(f"Warning: Process finished for {chassis_id}, but no process info found.")
        except Exception as e:
            # Catch errors within the handle_finished logic
            print(f"CRITICAL: Error within handle_finished for {chassis_id}: {e}")
            traceback.print_exc()
            # Emit an error, with the chassis_id
            self.acquisitionError.emit(chassis_id or "Unknown Chassis",
                                       f"Internal error handling process finish: {str(e)}")
        finally:
            # Cleanup
            # Make sure the QProcess object is always scheduled for deletion
            if process:
                QTimer.singleShot(500, process.deleteLater)
                print(f"Scheduled QProcess deleteLater for {chassis_id}")

    def _delayed_process_output(self, chassis_id: str, output_path: Path, process_info: dict):
        """Processes the output file after a short delay."""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{current_time}] DEBUG: Attempting to process file after delay: {output_path}")

            # Check if its there right before reading
            if not output_path.exists():
                print(
                    f"WARN: File {output_path} not found immediately after delay. Waiting 200ms more for last attempt.")
                QTimer.singleShot(200, lambda cid=chassis_id, op=output_path, pi=process_info:
                self._process_output_file_final_attempt(cid, op, pi))
                return

            file_size = output_path.stat().st_size
            print(f"DEBUG: File exists. Size before reading: {file_size} bytes")
            if file_size == 0:
                print(f"WARN: File {output_path} exists but is empty. Skipping processing.")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} was empty.")
                return

            # Call original processing function
            self._process_output_file(chassis_id, output_path, process_info)
            # Emit completion signal only if processing works
            self.acquisitionComplete.emit(chassis_id)
            current_time_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{current_time_end}] DEBUG: Successfully processed file: {output_path}")

        except FileNotFoundError as e:
            # Maybe will be caught if file disappears between the exists() check and _read_data_file
            print(f"ERROR (Delayed): Output file not found: {e}")
            self.acquisitionError.emit(chassis_id, f"Output file missing or unreadable: {output_path.name}")
        except (ValueError, IndexError) as e:  # Catch parsing/indexing errors
            print(f"ERROR (Delayed): Failed to parse/process data from {output_path.name}: {e}")
            try:
                with open(output_path, 'r', errors='ignore') as f_err:
                    lines = f_err.readlines()
                    print(f"--- File Content Snippet ({output_path.name}) ---")
                    print("".join(lines[:5]))  # Print first 5 lines
                    if len(lines) > 10: print("...")
                    print("".join(lines[-5:]))  # Print last 5 lines
                    print("-----------------------------------------")
            except Exception as read_err:
                print(f"(Could not read file content for error diagnosis: {read_err})")
            self.acquisitionError.emit(chassis_id, f"Data parsing/indexing error in {output_path.name}: {e}")
        except Exception as e:  # Catch any other unexpected errors
            print(f"ERROR (Delayed): Unexpected error processing file {output_path.name}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Unexpected error processing file {output_path.name}: {str(e)}")

    def _process_output_file_final_attempt(self, chassis_id: str, output_path: Path, process_info: dict):
        """Last attempt to process the file if it wasn't found immediately after the first delay."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{current_time}] DEBUG: Final attempt to process file: {output_path}")
        try:
            # Check if its there one last time
            if not output_path.exists():
                raise FileNotFoundError(f"Output file not found after extra delay: {output_path}")

            file_size = output_path.stat().st_size
            print(f"DEBUG: File exists last try. Size before reading: {file_size} bytes")
            if file_size == 0:
                print(f"WARN: File {output_path} exists but is empty last try. Skipping processing.")
                self.acquisitionError.emit(chassis_id, f"Output file {output_path.name} was empty.")
                return

            # Call processing function
            self._process_output_file(chassis_id, output_path, process_info)
            # Emit completion signal only if processing works
            self.acquisitionComplete.emit(chassis_id)
            current_time_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{current_time_end}] DEBUG: Successfully processed file (final attempt): {output_path}")

        except FileNotFoundError as e:
            print(f"ERROR (Final Attempt): Output file definitively not found or unreadable: {e}")
            self.acquisitionError.emit(chassis_id, f"Output file missing or unreadable: {output_path.name}")
        except (ValueError, IndexError) as e:
            print(f"ERROR (Final Attempt): Failed to parse/process data from {output_path.name}: {e}")
            self.acquisitionError.emit(chassis_id, f"Data parsing/indexing error in {output_path.name}: {e}")
        except Exception as e:
            print(f"ERROR (Final Attempt): Unexpected error processing file {output_path.name}: {e}")
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Unexpected error processing file {output_path.name}: {str(e)}")

    def _process_output_file(self, chassis_id: str, output_path: Path, process_info: dict):
        """Reads and parses the completed data file."""
        if not output_path.exists():
            raise FileNotFoundError(f"Output file not found: {output_path}")

        print(f"Reading data file: {output_path}")
        header_lines, data = self._read_data_file(output_path)

        if data.size == 0:
            print(f"Warning: Data file {output_path} contains header but no data rows.")
            # Emit an error or warning
            self.acquisitionError.emit(chassis_id, f"Warning: Output file {output_path.name} contained no data rows.")
            return  # Stop processing this file

        channels = self._parse_channels(header_lines)

        # Check if number of channels matches data columns
        if len(channels) != data.shape[1]:
            raise ValueError(
                f"Mismatch between channels in header ({len(channels)}) and data columns ({data.shape[1]}) in {output_path}")

        # Convert data to channel specific arrays
        parsed_data = {}
        for idx, channel in enumerate(channels):
            parsed_data[channel] = data[:, idx]

        # Extract cavity number
        try:
            # Assuming filename format res_CMXX_cavY_... or similar
            cavity_num_str = output_path.stem.split('_')[2]  # e.g., cav3
            cavity_num = int(cavity_num_str.replace('cav', ''))
        except (IndexError, ValueError):
            print(
                f"Warning: Could not parse cavity number from filename {output_path.name}. Using default or placeholder.")
            cavity_num = 0

        decimation = process_info.get('decimation', 1)

        print(f"Emitting dataReceived for {chassis_id}, Cavity {cavity_num}")
        self.dataReceived.emit(chassis_id, {
            'cavity': cavity_num,
            'channels': parsed_data,
            'decimation': decimation
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
