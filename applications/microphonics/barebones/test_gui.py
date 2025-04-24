import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QProcess, QCoreApplication
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QTextEdit, QMessageBox, QSizePolicy
)

PYTHON_EXECUTABLE = "python"
RES_DATA_ACQ_SCRIPT = "/usr/local/lcls/package/lcls2_llrf/srf/software/res_ctl/res_data_acq.py"
# Base directory for data storage
DATA_DIR_PATH = Path("/u1/lcls/physics/rf_lcls2/microphonics/")
# Hardcoded channel selection
CHANNEL_SELECTION = "DF"
# Cryomodule IDs (got from FFt_math.py)
CRYOMODULE_IDS = [
    'ACCL:L0B:01', 'ACCL:L1B:02', 'ACCL:L1B:03', 'ACCL:L1B:H1', 'ACCL:L1B:H2',
    'ACCL:L2B:04', 'ACCL:L2B:05', 'ACCL:L2B:06', 'ACCL:L2B:07', 'ACCL:L2B:08',
    'ACCL:L2B:09', 'ACCL:L2B:10', 'ACCL:L2B:11', 'ACCL:L2B:12', 'ACCL:L2B:13',
    'ACCL:L2B:14', 'ACCL:L2B:15', 'ACCL:L3B:16', 'ACCL:L3B:17', 'ACCL:L3B:18',
    'ACCL:L3B:19', 'ACCL:L3B:20', 'ACCL:L3B:21', 'ACCL:L3B:22', 'ACCL:L3B:23',
    'ACCL:L3B:24', 'ACCL:L3B:25', 'ACCL:L3B:26', 'ACCL:L3B:27', 'ACCL:L3B:28',
    'ACCL:L3B:29', 'ACCL:L3B:30', 'ACCL:L3B:31', 'ACCL:L3B:32', 'ACCL:L3B:33',
    'ACCL:L3B:34', 'ACCL:L3B:35',
]

# Default Values
DEFAULT_CM = 'ACCL:L1B:03'
DEFAULT_CAVITY = 3
DEFAULT_DECIMATION = 1
DEFAULT_BUFFERS = 1


class MinimalAcqApp(QWidget):
    def __init__(self):
        super().__init__()
        self.process = None
        self.output_file_path = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Minimal Microphonics Acquisition")
        self.setGeometry(300, 300, 700, 500)

        layout = QVBoxLayout(self)

        # Input Controls
        controls_layout = QHBoxLayout()

        # Cryomodule
        cm_layout = QVBoxLayout()
        cm_layout.addWidget(QLabel("Cryomodule:"))
        self.cm_combo = QComboBox()
        self.cm_combo.addItems(CRYOMODULE_IDS)
        try:
            default_index = CRYOMODULE_IDS.index(DEFAULT_CM)
            self.cm_combo.setCurrentIndex(default_index)
        except ValueError:
            self.cm_combo.setCurrentIndex(0)
        cm_layout.addWidget(self.cm_combo)
        controls_layout.addLayout(cm_layout, 0)

        # Cavity
        cav_layout = QVBoxLayout()
        cav_layout.addWidget(QLabel("Cavity (1-8)"))
        self.cavity_spin = QSpinBox()
        self.cavity_spin.setRange(1, 8)
        self.cavity_spin.setValue(DEFAULT_CAVITY)
        cav_layout.addWidget(self.cavity_spin)
        controls_layout.addLayout(cav_layout, 0)

        # Decimation
        dec_layout = QVBoxLayout()
        dec_layout.addWidget(QLabel("Decimation (-wsp):"))
        self.decimation_spin = QSpinBox()
        self.decimation_spin.setRange(1, 16)
        self.decimation_spin.setValue(DEFAULT_DECIMATION)
        dec_layout.addWidget(self.decimation_spin)
        controls_layout.addLayout(dec_layout, 0)

        # Buffers
        buf_layout = QVBoxLayout()
        buf_layout.addWidget(QLabel("Buffers (-c):"))
        self.buffers_spin = QSpinBox()
        self.buffers_spin.setRange(1, 1000)
        self.buffers_spin.setValue(DEFAULT_BUFFERS)
        buf_layout.addWidget(self.buffers_spin)
        controls_layout.addLayout(buf_layout, 0)

        layout.addLayout(controls_layout)

        # Start Button
        self.start_button = QPushButton("Start Acquisition")
        self.start_button.clicked.connect(self._start_acquisition)
        layout.addWidget(self.start_button)

        # Output Area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setLineWrapMode(QTextEdit.NoWrap)
        self.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(QLabel("Process Output:"))
        layout.addWidget(self.output_text)

        self.setLayout(layout)

    def _log(self, message):
        """Appends a message to the output text area."""
        self.output_text.append(message)
        QCoreApplication.processEvents()  # Make sure UI updates

    def _start_acquisition(self):
        """Gathers inputs, constructs arguments, and starts the QProcess."""
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Busy", "Acquisition is already running.")
            return

        self.output_text.clear()
        self.start_button.setEnabled(False)
        self.output_file_path = None

        # Gather Inputs
        cm_id = self.cm_combo.currentText()
        cavity = self.cavity_spin.value()
        decimation = self.decimation_spin.value()
        num_buffers = self.buffers_spin.value()

        # Parse Cryomodule ID
        try:
            parts = cm_id.split(':')
            if len(parts) != 3:
                raise ValueError(f"Invalid CM ID format: {cm_id}")
            linac = parts[1]  # e.g., L1B
            cm_num_str = parts[2]  # e.g., 03 (keep as string for formatting)
        except Exception as e:
            self._log(f"ERROR: Error parsing CM ID '{cm_id}': {e}")
            self.start_button.setEnabled(True)
            return

        # Construct PV Address
        # Determine Rack (A for 1-4, B for 5-8)
        rack_char = 'A' if 1 <= cavity <= 4 else 'B'
        # Pad CM number for PV (e.g., '03' -> '0300', 'H1' -> 'H100')
        cm_pv_part = cm_num_str
        if len(cm_pv_part) == 2 and cm_pv_part.isdigit():
            cm_pv_part += "00"
        elif len(cm_pv_part) == 2 and cm_pv_part.startswith('H'):
            cm_pv_part += "00"

        pv_address = f"ca://ACCL:{linac}:{cm_pv_part}:RES{rack_char}:"

        # Generate Data Directory Path
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")  # Format YYYYMMDD
        timestamp_hms = now.strftime("%H%M%S")  # Format HHMMSS

        # Structure: /base/LCLS/LINAC/CMXX/YYYYMMDD
        try:
            # Use upper() for LINAC and CM for consistency
            data_dir = DATA_DIR_PATH / "LCLS" / linac.upper() / f"CM{cm_num_str.upper()}" / date_str
        except Exception as e:
            self._log(f"ERROR: Failed to construct data directory path: {e}")
            self.start_button.setEnabled(True)
            return
        # Filename: res_CMXX_cavY_cZ_YYYYMMDD_HHMMSS.dat
        output_filename = f"res_CM{cm_num_str}_cav{cavity}_c{num_buffers}_{date_str}_{timestamp_hms}.dat"
        self.output_file_path = data_dir / output_filename  # Store full path

        # Create Data Directory
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            self._log(f"Ensured data directory exists: {data_dir}")
        except OSError as e:
            self._log(f"ERROR: Error creating data directory {data_dir}: {e}")
            self.start_button.setEnabled(True)
            return
        except Exception as e:  # Catch other potential errors
            self._log(f"ERROR: Unexpected error creating directory {data_dir}: {e}")
            self.start_button.setEnabled(True)
            return

        # Construct QProcess Arguments
        # Ensure all arguments passed to the script are strings
        script_args = [
            '-D', str(data_dir),  # Directory path
            '-a', pv_address,  # PV address
            '-wsp', str(decimation),  # Decimation
            '-acav', str(cavity),  # Active cavity
            '-ch', CHANNEL_SELECTION,  # Channel selection
            '-c', str(num_buffers),  # Number of buffers
            '-F', output_filename  # Filename (script combines with -D)
        ]

        # Log and Start Process
        self._log("Starting QProcess (Dynamic Command)...")
        self._log(f"  Data Directory: {data_dir}")
        self._log(f"  Output Filename: {output_filename}")
        self._log(f"  PV Address: {pv_address}")
        self._log(f"  Interpreter: {PYTHON_EXECUTABLE}")
        self._log(f"  Script: {RES_DATA_ACQ_SCRIPT}")
        self._log(f"  Script Arguments: {script_args}")

        # Check if script exists and is executable
        script_path = Path(RES_DATA_ACQ_SCRIPT)
        if not script_path.is_file():
            self._log(f"ERROR: Script not found at {RES_DATA_ACQ_SCRIPT}")
            self.start_button.setEnabled(True)
            return
        # Combine interpreter, script path, and arguments for QProcess.start
        full_command_args = [RES_DATA_ACQ_SCRIPT] + script_args

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)  # Combine stdout/stderr for simplicity
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)  # Handle QProcess specific errors
        # IMP CHANGE: Start python interpreter with script as first arg
        self.process.start(PYTHON_EXECUTABLE, full_command_args)

        # Check for immediate start errors
        if not self.process.waitForStarted(3000):  # Increased timeout slightly
            qprocess_error_str = self.process.errorString()
            self._log(f"ERROR: Failed to start process.")
            self._log(f"  QProcess Error Code: {self.process.error()}")
            self._log(f"  QProcess Error String: {qprocess_error_str}")
            # Try to get hints based on common errors
            if self.process.error() == QProcess.FailedToStart:
                self._log(f"  Hint: Check if '{PYTHON_EXECUTABLE}' is correct and in the system's PATH.")
                self._log(f"  Hint: Check permissions for the script and directories.")
            elif self.process.error() == QProcess.Crashed:
                self._log(f"  The process started but crashed immediately. Check script logs or run manually.")
            self._process_finished(self.process.exitCode(), self.process.exitStatus())  # Trigger cleanup

    def _read_output(self):
        """Reads standard output from the process."""
        if not self.process: return
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode(errors='ignore')  # Decode bytes to string
        self.output_text.moveCursor(QTextCursor.End)
        self.output_text.insertPlainText(text)
        self.output_text.moveCursor(QTextCursor.End)

    def _process_error(self, error):
        """Handles errors reported by QProcess itself (e.g., failed to start)."""
        self._log(f"QProcess Error Occurred: {error}")

    def _process_finished(self, exitCode, exitStatus):
        """Handles the process finishing."""
        status_str = "Normal Exit" if exitStatus == QProcess.NormalExit else "Crash Exit"
        self._log(f"\n--- Process Finished ---")
        self._log(f"Exit Code: {exitCode}")
        self._log(f"Exit Status: {status_str}")

        # Check if the process exited successfully and we expected a file
        if exitCode == 0 and exitStatus == QProcess.NormalExit:
            self._log(f"SUCCESS: Acquisition process completed normally.")
            if self.output_file_path:
                if self.output_file_path.exists():
                    self._log(f"Output file generated at: {self.output_file_path}")
                    try:
                        # Optional: Check if file has non-zero size as a basic check
                        if self.output_file_path.stat().st_size > 0:
                            self._log(f"  File size: {self.output_file_path.stat().st_size} bytes.")
                            self._log("  MANUALLY CONFIRM if the file contains valid data rows after the header.")
                        else:
                            self._log(f"  WARNING: Output file exists but is empty (0 bytes).")
                    except Exception as e:
                        self._log(f"  WARNING: Could not check file size: {e}")

                else:
                    # Process succeeded, but file is missing, Log a warning.
                    self._log(f"WARNING: Process exited normally, but output file NOT FOUND at the expected location:")
                    self._log(f"  Expected: {self.output_file_path}")
                    self._log(f"  Check script output above for potential errors writing the file.")
            else:
                self._log("NOTE: No specific output file path was tracked for this run.")

        else:
            # Process failed (non-zero exit code or crash)
            self._log(f"ERROR: Process exited abnormally.")
            if self.output_file_path:
                self._log(
                    f"Check if a partial or error file exists at: {self.output_file_path}")
            self._log(f"Review the process output above for error messages from the script.")

        # Re-enable the button and clear the process reference regardless of success/failure
        self.start_button.setEnabled(True)
        self.process = None  # Important to allow starting a new process

    def closeEvent(self, event):
        """Make sure process is terminated if GUI is closed."""
        if self.process and self.process.state() != QProcess.NotRunning:
            self._log("Terminating running process due to GUI closure...")
            self.process.terminate()  # Ask nicely first
            if not self.process.waitForFinished(1000):  # Wait 1s
                self._log("Process did not terminate gracefully, killing.")
                self.process.kill()
                self.process.waitForFinished(500)  # Wait briefly for kill
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Check if the target script exists before even creating the GUI
    if not Path(RES_DATA_ACQ_SCRIPT).is_file():
        QMessageBox.critical(None, "Error",
                             f"Acquisition script not found:\n{RES_DATA_ACQ_SCRIPT}\n\nPlease ensure the path is correct.")
        sys.exit(1)

    ex = MinimalAcqApp()
    ex.show()
    sys.exit(app.exec_())
