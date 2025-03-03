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

            process = QProcess()
            process.setProgram(sys.executable)

            # Extract CM number from chassis_id (e.g., "ACCL:L0B:0100:RESA" -> "01")
            cm_num = chassis_id.split(':')[2][:2]

            # Format cavity numbers for filename
            cavity_str = '_'.join(map(str, sorted(config['cavities'])))

            # Generate filename w/ timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"res_CM{cm_num}_cav{cavity_str}_{timestamp}.dat"

            # Create directory structure and get full path
            data_dir = self._create_data_directory(chassis_id)

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
                'decimation': config['decimation'],
                'last_read': None
            }
            process.start()

            # Start checking for output files
            timer = QTimer()
            timer.timeout.connect(lambda: self._check_output_files(chassis_id))
            timer.start(1000)  # Check every sec

        except Exception as e:
            self.acquisitionError.emit(chassis_id, str(e))

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
                self.acquisitionError.emit(chassis_id, error)
        except Exception as e:
            print(f"Error processing stderr: {e}")

    def handle_finished(self, chassis_id: str, process: QProcess, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handle process completion"""
        try:
            # Clean up process first
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]

            if exit_code != 0 or exit_status == QProcess.CrashExit:
                self.acquisitionError.emit(chassis_id, f"Process exited with code {exit_code}")
            else:
                self.acquisitionComplete.emit(chassis_id)

            process.deleteLater()

        except Exception as e:
            print(f"Error in handle_finished: {e}")
            self.acquisitionError.emit(chassis_id, str(e))

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
        """Read data file generated by res_data_acq.py"""
        header_data = []
        with open(file_path) as f:
            lini = f.readline()
            while 'ACCL' not in lini:
                header_data.append(lini)
                lini = f.readline()
            next(f)
            next(f)
            header_data.append(lini)
            read_data = f.readlines()

        return header_data, read_data

    def _parse_channels(self, header_lines: List[str]) -> List[str]:
        """Parse channel names from res_data_acq.py file header"""
        for line in header_lines:
            if any(ch in line for ch in ['DAC', 'DF']):
                return line.strip().split()
        return ['DAC', 'DF']  # Default to essential channels
