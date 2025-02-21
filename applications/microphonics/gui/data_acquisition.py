import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QTimer


class DataAcquisitionManager(QObject):
    """Manages data acquisition from RF cavity monitoring hardware.

    Handles:
    - Process management for data collection scripts
    - File system organization for data storage
    - Real-time data parsing and signal emission
    - Error handling and process lifecycle management
    """

    # Signal definitions for acquisition lifecycle events
    acquisitionProgress = pyqtSignal(str, int, int)  # chassis_id, cavity_num, progress
    acquisitionError = pyqtSignal(str, str)  # chassis_id, error_message
    acquisitionComplete = pyqtSignal(str)  # chassis_id
    dataReceived = pyqtSignal(str, dict)  # chassis_id, data_dict

    def __init__(self):
        """Initialize manager with system paths and process tracking."""
        super().__init__()
        self.active_processes = {}  # Tracks running acquisition processes

        # System paths for data and scripts
        self.base_path = Path("/u1/lcls/physics/rf_lcls2/microphonics")
        self.script_path = Path("/usr/local/lcls/package/lcls2_llrf/srf/software/res_ctl/res_data_acq.py")

    def _create_data_directory(self, chassis_id: str) -> Path:
        """Create hierarchical directory structure for data storage.

        Organizes data by:
        - Facility (LCLS)
        - Linac section (L1B, L2B, etc.)
        - Cryomodule (CM01, CM02, etc.)
        - Date (YYYYMMDD)

        Args:
            chassis_id: EPICS identifier (e.g., 'ACCL:L1B:0300:RESA')

        Returns:
            Path to created data directory

        Raises:
            ValueError: If chassis_id format is invalid
        """
        parts = chassis_id.split(':')
        if len(parts) < 4:
            raise ValueError(f"Invalid chassis_id format: {chassis_id}")

        # Extract components from chassis ID
        facility = "LCLS"
        linac = parts[1]  # e.g., L1B
        cryomodule = parts[2][:2]  # e.g., 03 from 0300

        # Create dated directory path
        date_str = datetime.now().strftime("%Y%m%d")
        data_path = self.base_path / facility / linac / f"CM{cryomodule}" / date_str
        data_path.mkdir(parents=True, exist_ok=True)

        return data_path

    def start_acquisition(self, chassis_id: str, config: Dict):
        """Start data acquisition process for specified chassis.

        Launches res_data_acq.py in separate process with:
        - Directory structure creation
        - Configuration validation
        - Signal handling setup
        - Output file monitoring

        Args:
            chassis_id: EPICS identifier for target chassis
            config: Acquisition parameters including cavities and channels
        """
        try:
            # Validate configuration
            if not config.get('cavities'):
                raise ValueError("No cavities specified")

            # Check for hardware constraint violations
            low_cm = any(c <= 4 for c in config['cavities'])
            high_cm = any(c > 4 for c in config['cavities'])
            if low_cm and high_cm:
                raise ValueError("ERROR: Cavity selection crosses half-CM")

            # Setup acquisition process
            process = QProcess()
            process.setProgram(sys.executable)

            # Extract configuration components
            cm_num = chassis_id.split(':')[2][:2]
            cavity_str = '_'.join(map(str, sorted(config['cavities'])))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"res_CM{cm_num}_cav{cavity_str}_{timestamp}.dat"

            # Create storage directory
            data_dir = self._create_data_directory(chassis_id)

            # Build script arguments
            args = [
                str(self.script_path),
                '-D', str(data_dir),
                '-a', config['pv_base'],
                '-wsp', str(config['decimation']),
                '-acav', *map(str, config['cavities']),
                '-ch', *config['channels'],
                '-c', str(config['buffer_count']),
                '-F', filename
            ]
            process.setArguments(args)

            # Connect process signals
            process.readyReadStandardOutput.connect(
                lambda: self.handle_stdout(chassis_id, process))
            process.readyReadStandardError.connect(
                lambda: self.handle_stderr(chassis_id, process))
            process.finished.connect(
                lambda exit_code, exit_status: self.handle_finished(chassis_id, process, exit_code, exit_status))

            # Store process information
            self.active_processes[chassis_id] = {
                'process': process,
                'output_dir': data_dir,
                'filename': filename,
                'decimation': config['decimation'],
                'last_read': None
            }
            process.start()

            # Begin output file monitoring
            timer = QTimer()
            timer.timeout.connect(lambda: self._check_output_files(chassis_id))
            timer.start(1000)  # Check every second

        except Exception as e:
            self.acquisitionError.emit(chassis_id, str(e))

    def handle_stdout(self, chassis_id: str, process: QProcess):
        """Process standard output from acquisition script.

        Parses progress information and emits status updates.

        Args:
            chassis_id: Associated chassis identifier
            process: Running acquisition process
        """
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
        """Handle error output from acquisition script.

        Args:
            chassis_id: Associated chassis identifier
            process: Running acquisition process
        """
        try:
            error = bytes(process.readAllStandardError()).decode().strip()
            if error:
                self.acquisitionError.emit(chassis_id, error)
        except Exception as e:
            print(f"Error processing stderr: {e}")

    def handle_finished(self, chassis_id: str, process: QProcess, exit_code: int, exit_status: QProcess.ExitStatus):
        """Process completion handler for acquisition script.

        Performs cleanup and emits completion or error signals.

        Args:
            chassis_id: Associated chassis identifier
            process: Completed acquisition process
            exit_code: Process exit code
            exit_status: Process exit status
        """
        try:
            # Clean up process tracking
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]

            # Check for errors
            if exit_code != 0 or exit_status == QProcess.CrashExit:
                self.acquisitionError.emit(chassis_id, f"Process exited with code {exit_code}")
            else:
                self.acquisitionComplete.emit(chassis_id)

            process.deleteLater()

        except Exception as e:
            print(f"Error in handle_finished: {e}")
            self.acquisitionError.emit(chassis_id, str(e))

    def stop_acquisition(self, chassis_id: str):
        """Stop acquisition for specified chassis.

        Attempts graceful termination with fallback to force kill.

        Args:
            chassis_id: Identifier for acquisition to stop
        """
        if chassis_id in self.active_processes:
            process_info = self.active_processes[chassis_id]
            process = process_info['process']
            process.terminate()
            # Force kill after 2 second timeout
            QTimer.singleShot(2000, process.kill)

    def stop_all(self):
        """Stop all active acquisitions and cleanup resources."""
        for chassis_id in list(self.active_processes.keys()):
            self.stop_acquisition(chassis_id)

    def _check_output_files(self, chassis_id: str) -> None:
        """Monitor and process output files from acquisition script.

        Checks for new data files, parses content, and emits data signals.

        Args:
            chassis_id: Chassis to check for new data
        """
        if chassis_id not in self.active_processes:
            return

        process_info = self.active_processes[chassis_id]
        output_path = process_info['output_dir'] / process_info['filename']

        try:
            if output_path.exists() and output_path != process_info['last_read']:
                # Parse new data file
                header_lines, data = self._read_data_file(output_path)
                channels = self._parse_channels(header_lines)

                # Organize data by channel
                parsed_data = {}
                for idx, channel in enumerate(channels):
                    parsed_data[channel] = data[:, idx]

                # Extract cavity number and emit data
                cavity_num = int(output_path.stem.split('_')[1])
                decimation = process_info.get('decimation', 1)

                self.dataReceived.emit(chassis_id, {
                    'cavity': cavity_num,
                    'channels': parsed_data,
                    'decimation': decimation
                })

                process_info['last_read'] = output_path

        except Exception as e:
            print(f"Error reading data file: {e}")

    def _read_data_file(self, file_path: Path) -> Tuple[List[str], np.ndarray]:
        """Read and parse acquisition data file.

        Args:
            file_path: Path to data file

        Returns:
            Tuple of header lines and numerical data array
        """
        header_data = []
        with open(file_path) as f:
            lini = f.readline()
            while 'ACCL' not in lini:
                header_data.append(lini)
                lini = f.readline()
            next(f)  # Skip additional header lines
            next(f)
            header_data.append(lini)
            read_data = f.readlines()

        return header_data, read_data

    def _parse_channels(self, header_lines: List[str]) -> List[str]:
        """Extract channel names from file header.

        Args:
            header_lines: List of header lines from data file

        Returns:
            List of channel names (defaults to ['DAC', 'DF'] if none found)
        """
        for line in header_lines:
            if any(ch in line for ch in ['DAC', 'DF']):
                return line.strip().split()
        return ['DAC', 'DF']  # Default channels
