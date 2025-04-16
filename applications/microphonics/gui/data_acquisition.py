import io
import sys
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
        self.active_processes = {}  # chassis_id: QProcess
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

        facility = "LCLS"  # Hard-coded for now
        linac = parts[1]  # e.g., L1B
        cryomodule = parts[2][:2]  # e.g., 03 from 0300

        # Create date string
        date_str = datetime.now().strftime("%Y%m%d")

        # Construct the full path
        data_path = self.base_path / facility / linac / f"CM{cryomodule}" / date_str

        # Create directory structure if it doesn't exist
        data_path.mkdir(parents=True, exist_ok=True)

        return data_path

    # In DataAcquisitionManager.start_acquisition method:

    def start_acquisition(self, chassis_id: str, config: Dict):
        """Start acquisition using QProcess"""
        try:
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
            process.setProgram(sys.executable)  # Use sys.executable for portability

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

            # Fixed arguement construction
            args = [
                str(self.script_path),
                '-D', str(data_dir),
                '-a', config['pv_base'],
                '-wsp', str(measurement_cfg.decimation),
                '-acav', *map(str, config['cavities']),
                '-ch', *measurement_cfg.channels,
                '-c', str(measurement_cfg.buffer_count),
                '-F', filename
            ]

            print(f"Starting QProcess with args: {args}")
            process.setArguments(args)

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
                'decimation': measurement_cfg.decimation,
                'last_read': None,
                'timer': None  # Initialize timer key
            }
            process.start()
            print(f"QProcess for {chassis_id} started.")

            # Start checking for output files: Check if timer logic is needed/correct
            timer = QTimer()
            timer.timeout.connect(lambda: self._check_output_files(chassis_id))
            timer.start(1000)  # Check every sec
            self.active_processes[chassis_id]['timer'] = timer  # Store the timer

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
        try:
            # Convert QProcess::ExitStatus enum to string for logging
            status_str = "NormalExit" if exit_status == QProcess.NormalExit else "CrashExit"
            print(f"Process finished for {chassis_id}. Exit code: {exit_code}, Status: {status_str}")  # Debug log

            # Now trigger final check before cleanup
            if chassis_id in self.active_processes:
                process_info = self.active_processes[chassis_id]
                print(f"Stopping timer and triggering final file check for {chassis_id}")
                if process_info.get('timer'):
                    process_info['timer'].stop()  # Stop the timer

                try:
                    self._check_output_files(chassis_id)  # Perform last check
                except Exception as e:
                    print(f"Error during final file check for {chassis_id}: {e}")
                    self.acquisitionError.emit(chassis_id, f"Error processing final data: {e}")

            # Now clean up process entry
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]  # Remove after final check

            # Handle exit status
            if exit_code != 0 or exit_status == QProcess.CrashExit:
                error_msg = f"Acquisition process exited abnormally. Code: {exit_code}, Status: {status_str}."
                # Try reading any remaining stderr
                try:
                    stderr_final = bytes(process.readAllStandardError()).decode().strip()
                    if stderr_final:
                        print(f"!!! Final STDERR ({chassis_id}): {stderr_final}")
                        error_msg += f"\nFinal stderr: {stderr_final}"
                except Exception as e_read:
                    print(f"Error reading final stderr for {chassis_id}: {e_read}")

                self.acquisitionError.emit(chassis_id, error_msg)
                print(f"Emitted error for abnormal exit: {chassis_id}")  # Debug log
            else:
                print(f"Acquisition completed normally for {chassis_id}.")  # Debug log
                self.acquisitionComplete.emit(chassis_id)  # Emit completion signal

            process.deleteLater()  # Schedule QProcess object for deletion

        except Exception as e:
            print(f"Error in handle_finished for {chassis_id}: {e}")
            import traceback
            traceback.print_exc()
            self.acquisitionError.emit(chassis_id, f"Internal error handling process finish: {str(e)}")

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

    def _check_output_files(self, chassis_id: str) -> None:
        """Check for and parse new data files from res_data_acq.py"""
        if chassis_id not in self.active_processes:
            return

        process_info = self.active_processes[chassis_id]
        output_path = process_info['output_dir'] / process_info['filename']

        try:
            if output_path.exists() and output_path != process_info['last_read']:
                # Read and parse the data file
                header_lines, data = self._read_data_file(output_path)
                channels = self._parse_channels(header_lines)

                # Convert data to channel-specific arrays
                parsed_data = {}
                for idx, channel in enumerate(channels):
                    parsed_data[channel] = data[:, idx]

                # Emit parsed data
                cavity_num = int(output_path.stem.split('_')[1])

                # Get decimation from process info
                decimation = process_info.get('decimation', 1)  # Default to 1 if not found

                self.dataReceived.emit(chassis_id, {
                    'cavity': cavity_num,
                    'channels': parsed_data,
                    'decimation': decimation
                })

                process_info['last_read'] = output_path

        except Exception as e:
            print(f"Error reading data file: {e}")

    def _read_data_file(self, file_path: Path) -> Tuple[List[str], np.ndarray]:
        """Read data file generated by res_data_acq.py, parsing numerical data."""
        header_lines = []
        data_lines = []
        try:
            with open(file_path, 'r') as f:
                line = f.readline()
                # Read header until the line starting with ACCL or EOF
                while line and not line.strip().startswith('# ACCL:'):
                    header_lines.append(line)
                    line = f.readline()

                if not line:  # Check if marker was found
                    print(f"Warning: Header marker '# ACCL:' not found in {file_path}")
                    # Try find any line starting with #
                    channel_line_found = False
                    for header_line in reversed(header_lines):
                        if header_line.strip().startswith('#'):
                            header_lines.append(header_line)
                            channel_line_found = True
                            break
                    if not channel_line_found:
                        raise ValueError(f"Could not identify channel header in {file_path}")

                # Keep the marker line
                header_lines.append(line)

                # Read the rest of the lines, separating data from comments
                for data_line in f:
                    # Only keep lines that don't start with # and arent empty
                    stripped_line = data_line.strip()
                    if stripped_line and not stripped_line.startswith('#'):
                        data_lines.append(data_line)
                    elif stripped_line.startswith('#'):
                        header_lines.append(data_line)

            if not data_lines:
                print(f"Warning: No data lines found in file {file_path} after header.")
                return header_lines, np.empty((0, 0))  # Return empty array

            # Use numpy to load data from collected data lines
            # Use io.StringIO to treat the list of strings as a file for np.loadtxt
            data_io = io.StringIO("".join(data_lines))
            # Specify comments='#' to make sure no accidental data lines are skipped
            data = np.loadtxt(data_io, comments='#')

            # Handle cases where loadtxt might return a 1D array
            if data.ndim == 0:  # Single value
                data = data.reshape(1, 1)
            elif data.ndim == 1:
                # If only one row of data was read, reshape to (1, N)
                if len(data_lines) == 1:
                    data = data.reshape(1, -1)
                # Otherwise, assume it's a single column (N, 1)
                else:
                    data = data.reshape(-1, 1)

            print(f"Successfully parsed data shape {data.shape} from {file_path}")  # Debug log
            return header_lines, data

        except FileNotFoundError:
            print(f"Error: Data file not found during read: {file_path}")
            # Re-raise or return empty data? Re-raising is often better.
            raise
        except ValueError as e:
            print(f"Error parsing numerical data in {file_path}: {e}")
            # This often happens if a line contains non-numeric data not preceded by '#'
            print("--- Problematic Data Lines (first 5) ---")
            for i, line in enumerate(data_lines):
                if i < 5:
                    print(line.strip())
                else:
                    break
            print("-----------------------------------------")
            raise ValueError(f"Failed to parse numeric data from {file_path}: {e}") from e
        except Exception as e:
            print(f"Unexpected error reading/parsing data file {file_path}: {e}")
            raise  # Re-raise unexpected errors

    def _parse_channels(self, header_lines: List[str]) -> List[str]:
        """Parse channel names (full PVs) from res_data_acq.py file header."""
        # Look for line starting with # ACCL:
        for line in header_lines:
            line_strip = line.strip()
            if line_strip.startswith('# ACCL:'):
                # Remove #, strip whitespace, split by space
                parsed_channels = line_strip.strip('# \n').split()
                print(f"Parsed channels from header: {parsed_channels}")  # Debug log
                return parsed_channels
        # Fallback or error if line not found
        print(f"Warning: Channel header line ('# ACCL:') not found in header. Defaulting.")
        return ['DAC', 'DF']  # Current fallback
