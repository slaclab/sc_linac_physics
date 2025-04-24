import sys
from pathlib import Path

from PyQt5.QtCore import QProcess, QCoreApplication
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QTextEdit, QMessageBox, QSizePolicy
)

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
        # self.output_file_path = None
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
        # Hardcode Command Test
        hardcoded_data_dir = "/u1/lcls/physics/rf_lcls2/microphonics/LCLS/L1B/CM03/20250422"
        hardcoded_filename = "res_CM03_cav3_20250422_144715.dat"
        self.hardcoded_output_path_str = f"{hardcoded_data_dir}/{hardcoded_filename}"  # Logging
        python_executable = "python"

        hardcoded_args = [
            RES_DATA_ACQ_SCRIPT,
            "-D", hardcoded_data_dir,
            "-a", "ca://ACCL:L1B:0300:RESA:",
            "-wsp", "1",
            "-acav", "3",
            "-ch", "DF",
            "-c", "1",
            "-F", hardcoded_filename
        ]

        # Log and Start Process
        self._log("Starting QProcess (HARDCODED COMMAND)...")
        self._log(f"  Directory (Must Exist): {hardcoded_data_dir}")
        self._log(f"  Interpreter: {python_executable}")
        self._log(f"  Arguments: {hardcoded_args}")
        # Check if script exists and is executable
        script_path = Path(hardcoded_args[0])
        if not script_path.is_file():
            self._log(f"ERROR: Script not found at {hardcoded_args[0]}")
            self.start_button.setEnabled(True)
            return

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)  # Combine stdout/stderr for simplicity
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)  # Handle QProcess specific errors

        # Start the process w/ hardcoded command
        self.process.start(python_executable, hardcoded_args)
        # Check for immediate start errors (e.g., executable not found by QProcess)
        if not self.process.waitForStarted(2000):  # Wait 2s for start
            self._log(f"ERROR: Failed to start process. Error code: {self.process.error()}")
            self._process_finished(self.process.exitCode(), self.process.exitStatus())  # Trigger cleanup

    def _read_output(self):
        """Reads standard output from the process."""
        if not self.process: return
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode(errors='ignore')  # Decode bytes to string
        self.output_text.moveCursor(QTextEdit.End)
        self.output_text.insertPlainText(text)
        self.output_text.moveCursor(QTextEdit.End)

    def _process_error(self, error):
        """Handles errors reported by QProcess itself (e.g., failed to start)."""
        self._log(f"QProcess Error Occurred: {error}")

    def _process_finished(self, exitCode, exitStatus):
        """Handles the process finishing."""
        status_str = "Normal Exit" if exitStatus == QProcess.NormalExit else "Crash Exit"
        self._log(f"\n--- Process Finished ---")
        self._log(f"Exit Code: {exitCode}")
        self._log(f"Exit Status: {status_str}")

        # Check if the process exited successfully
        if exitCode == 0 and exitStatus == QProcess.NormalExit:
            self._log(f"SUCCESS: Acquisition likely completed (using hardcoded command).")
            # Now check if the expected output file exists
            if hasattr(self, 'hardcoded_output_path_str') and Path(self.hardcoded_output_path_str).exists():
                self._log(f"Output file should be at: {self.hardcoded_output_path_str}")
                self._log("MANUALLY CONFIRM if the file contains data rows after the header.")
            else:
                # Process succeeded, but if file is missing Log a warning.
                path_str = getattr(self, 'hardcoded_output_path_str', 'UNKNOWN HARDCODED PATH')
                self._log(f"WARNING: Process exited normally, but output file not found at {path_str}")
        else:
            # Process failed
            self._log(f"ERROR: Process exited abnormally (using hardcoded command).")
            # Still report the expected file path for checking
            if hasattr(self, 'hardcoded_output_path_str'):
                self._log(f"Check file (may be incomplete or empty): {self.hardcoded_output_path_str}")

        self.start_button.setEnabled(True)
        self.process = None

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
